from typing import Dict, Any, List, Optional, Tuple
import re
import logging
import pandas as pd
import numpy as np
import uuid
import asyncio
import math
from dataclasses import dataclass

from qdrant_client.models import Filter, FieldCondition, Match, PointStruct
from qdrant_client.http import models as http_models

logger = logging.getLogger(__name__)

# ----------------------------- Helpers ----------------------------- #

def _json_sanitize(obj):
    """Make dict/list/json values safe for Qdrant JSON (no NaN/Inf/numpy/or non-serializable)."""
    if obj is None:
        return None
    if isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (float, int, np.floating, np.integer)):
        val = float(obj) if isinstance(obj, (float, np.floating)) else int(obj)
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    if isinstance(obj, list):
        return [_json_sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _json_sanitize(v) for k, v in obj.items()}
    # Fallback to string for unsupported types
    return str(obj)

def _none_if_nan(x):
    try:
        if x is None:
            return None
        # support numpy scalars
        if isinstance(x, (np.floating,)):
            x = float(x)
        if isinstance(x, (np.integer,)):
            x = int(x)
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return x
    except Exception:
        return None

# ----------------------------- Data Classes ----------------------------- #

@dataclass
class AttributionMetadata:
    """Metadata for attribution analysis"""
    period: str
    asset_class: str  # "Equity" or "Fixed Income"
    attribution_level: str  # "Sector" or "Country"
    columns_present: List[str]
    has_fx: bool
    has_carry: bool
    has_roll: bool
    has_price: bool
    total_rows: int


@dataclass
class AttributionChunk:
    """Chunk ready for embedding & storage"""
    chunk_id: str
    chunk_type: str  # "row", "total", "ranking", "schema"
    text: str        # Text to embed
    payload: Dict[str, Any]
    embedding: Optional[List[float]] = None


# ---------------------- Performance Attribution Service ---------------------- #

class PerformanceAttributionService:
    """
    Specialized service for processing performance attribution documents and generating
    professional commentary using an institutional buy-side framework.
    """

    def __init__(self, ollama_service=None, qdrant_service=None):
        self.ollama = ollama_service
        self.qdrant = qdrant_service
        self.embedding_model = "nomic-embed-text"
        self.embedding_dim: Optional[int] = None

        self.system_prompt = """You are a buy-side performance attribution commentator for an institutional portfolio.
Your audience is portfolio managers and senior analysts.
Write concise, evidence-based commentary grounded ONLY in the provided table and derived stats.
Quantify all statements using percentage points (pp) for attribution and % for returns.
Break down performance into allocation (sector or country), security/issue selection, FX selection (if provided), and any other effects present in the data.
Do not invent data or macro narrative beyond what is in the context.
Tone: crisp, professional, and meaningful to experienced PMs.

Output structure (markdown):
1) Executive Summary (3–4 sentences)
2) Total Performance Drivers
"""

        self.developer_prompt = """- Only use numbers given in the user prompt.
- Identify drivers explicitly as allocation, selection, FX, or other effects present.
- Rank top contributors/detractors strictly by Total Attribution (pp) (aka Total Management).
- Limit Executive Summary to 3–4 sentences; avoid filler.
- Do not add securities, macro factors, or assumptions not in context.
- Use one decimal place for pp values and retain +/- signs.
"""

        self.last_chunks: List[AttributionChunk] = []

    # ---------------------------- Prompt Builder ---------------------------- #

    def get_unified_prompt_template(
        self,
        period_name: str,
        asset_class: str,
        attribution_level: str,
        tabular_data: str,
        columns_present: List[str],
        portfolio_total_return: float,
        benchmark_total_return: float,
        total_active_return: float,
        effects_breakdown: Dict[str, float],
        top_contributors: List[Dict[str, Any]],
        top_detractors: List[Dict[str, Any]],
    ) -> str:
        effects_lines = []
        for effect, value in effects_breakdown.items():
            effects_lines.append(f"- {effect}: {value:+.1f} pp")
        effects_breakdown_text = "\n".join(effects_lines)

        contributors_text = "\n".join(
            f"{i}. {c['name']} ({c['attribution']:+.1f} pp)"
            for i, c in enumerate(top_contributors[:3], 1)
        )
        detractors_text = "\n".join(
            f"{i}. {d['name']} ({d['attribution']:+.1f} pp)"
            for i, d in enumerate(top_detractors[:2], 1)
        )

        prompt = f"""Period: {period_name}
Asset Class: {asset_class}
Attribution Level: {attribution_level}  # "Country" or "Sector"

# Attribution Table ({attribution_level}-level)
{tabular_data}
# Columns present: {', '.join(columns_present)}
# Notes: Attribution effects are in pp; returns are in %.

# Derived Stats
Portfolio Total Return: {portfolio_total_return:.2f}%
Benchmark Total Return: {benchmark_total_return:.2f}%
Active Return: {total_active_return:+.2f} pp

Breakdown (only effects present in the table):
{effects_breakdown_text}

Top 3 Contributors by Total Attribution (pp):
{contributors_text}

Top 2 Detractors by Total Attribution (pp):
{detractors_text}

# Task
Using ONLY the table and derived stats above, generate a concise portfolio attribution commentary for {period_name} following this markdown:

**Executive Summary**
<3–4 sentences summarizing active return, main drivers (by effect), and breadth of performance. Keep it crisp and PM-focused.>

**Total Performance Drivers**
- Portfolio ROR: {portfolio_total_return:.2f}% | Benchmark ROR: {benchmark_total_return:.2f}%
- Active return: {total_active_return:+.1f} pp
- Attribution breakdown: {', '.join([f"{k} = {v:+.1f} pp" for k, v in effects_breakdown.items()])}

**{attribution_level}-Level Highlights**
- <Top contributor 1>: quantify and name the specific effect(s) that drove it.
- <Top contributor 2>: same.
- <Top contributor 3>: same.
- <Top detractor 1>: quantify and specify effect(s).
- <Top detractor 2>: quantify and specify effect(s).

**Risks / Watch Items**
<Optional, only if the data signals concentration, FX sensitivity, rate/duration, or other notable patterns.>

Constraints:
- Use one decimal place for pp values and retain +/- signs.
- Cite only numbers present in the context (or simple arithmetic already shown).
- If an effect column (e.g., FX) is not present, do not mention it.
"""
        return prompt

    # --------------------------- Excel Extraction --------------------------- #

    def extract_attribution_data_from_tables(self, tables: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the first likely attribution table in a pre-parsed Excel structure."""
        for table in tables:
            if not table.get("data"):
                continue
            first_row = table["data"][0] if table["data"] else {}
            column_names = [str(k).lower() for k in first_row.keys()]
            indicators = ["attribution", "allocation", "selection", "contribution", "active", "portfolio", "benchmark", "return"]
            if any(ind in " ".join(column_names) for ind in indicators):
                return {
                    "table_data": table["data"],
                    "columns": list(first_row.keys()),
                    "sheet_name": table.get("sheet_name", "Unknown"),
                    "shape": table.get("shape", [0, 0]),
                }
        return None

    def parse_attribution_table(self, attribution_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse attribution-like dict (from prior extraction path)."""
        if not attribution_data:
            return None
        try:
            table_data = attribution_data["table_data"]
            columns = attribution_data["columns"]

            results = {
                "period_name": "Q2 2025",
                "asset_class": "Mixed",
                "attribution_level": "Sector",
                "portfolio_total_return": 0.0,
                "benchmark_total_return": 0.0,
                "total_active_return": 0.0,
                "effects_breakdown": {},
                "top_contributors": [],
                "top_detractors": [],
                "tabular_data": self._format_table_for_display(table_data, columns),
            }

            # try totals (heuristic in this path)
            for row in table_data:
                for col_name, value in row.items():
                    if isinstance(value, str):
                        v = value.lower()
                        if "portfolio total" in v or "total portfolio" in v:
                            results["portfolio_total_return"] = self._extract_return_value(row, col_name)
                        elif "benchmark total" in v or "total benchmark" in v:
                            results["benchmark_total_return"] = self._extract_return_value(row, col_name)

            results["total_active_return"] = results["portfolio_total_return"] - results["benchmark_total_return"]

            # identify data rows, total attribution column
            attribution_rows = [r for r in table_data if self._is_data_row(r)]
            total_attr_col = self._find_total_attribution_column(columns)

            if total_attr_col and attribution_rows:
                try:
                    sorted_rows = sorted(
                        attribution_rows,
                        key=lambda r: self._safe_float_conversion(r.get(total_attr_col, 0)),
                        reverse=True,
                    )
                    for r in sorted_rows[:3]:
                        val = self._safe_float_conversion(r.get(total_attr_col, 0))
                        if val > 0:
                            results["top_contributors"].append(
                                {"name": self._get_bucket_name_from_row(r), "attribution": val, "details": r}
                            )
                    for r in reversed(sorted_rows[-2:]):
                        val = self._safe_float_conversion(r.get(total_attr_col, 0))
                        if val < 0:
                            results["top_detractors"].append(
                                {"name": self._get_bucket_name_from_row(r), "attribution": val, "details": r}
                            )
                except Exception as e:
                    logger.warning(f"Sort error: {e}")

            for effect in ["Allocation", "Selection", "FX Selection", "Total Attribution"]:
                col = self._find_column_containing(columns, effect.lower())
                if col:
                    total_effect = sum(self._safe_float_conversion(r.get(col, 0)) for r in attribution_rows)
                    results["effects_breakdown"][effect] = total_effect

            return results
        except Exception as e:
            logger.error(f"Error parsing attribution table: {e}")
            return None

    # -------------------------- Parsing Helper Utils ------------------------- #

    def _format_table_for_display(self, table_data: List[Dict], columns: List[str]) -> str:
        if not table_data:
            return "No data available"
        header = " | ".join(columns)
        separator = " | ".join(["-" * len(col) for col in columns])
        rows = []
        for row_data in table_data[:10]:
            row = " | ".join([str(row_data.get(col, "")) for col in columns])
            rows.append(row)
        return f"{header}\n{separator}\n" + "\n".join(rows)

    def _extract_return_value(self, row: Dict, current_col: str) -> float:
        for col_name, value in row.items():
            if col_name != current_col:
                num = self._safe_float_conversion(value)
                if num != 0:
                    return num
        return 0.0

    def _is_data_row(self, row: Dict) -> bool:
        first_value = str(list(row.values())[0]).lower()
        skip = ["total", "portfolio", "benchmark", "breakdown", "summary"]
        return not any(s in first_value for s in skip)

    def _find_total_attribution_column(self, columns: List[str]) -> Optional[str]:
        for col in columns:
            c = col.lower()
            if "total attribution" in c or ("total" in c and "pp" in c) or "total_management" in c:
                return col
        return None

    def _find_column_containing(self, columns: List[str], needle: str) -> Optional[str]:
        for col in columns:
            if needle in col.lower():
                return col
        return None

    def _get_bucket_name_from_row(self, row: Dict) -> str:
        if not row:
            return "Unknown"
        return str(list(row.values())[0])

    def _safe_float_conversion(self, value: Any) -> float:
        if isinstance(value, (int, float, np.floating, np.integer)) and not pd.isna(value):
            return float(value)
        if isinstance(value, str):
            cleaned = re.sub(r"[%,\$]", "", value.strip())
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0

    # --------------------------- Commentary (LLM) --------------------------- #

    async def generate_commentary(self, attribution_data: Dict[str, Any], ollama_service) -> str:
        try:
            prompt = self.get_unified_prompt_template(
                period_name=attribution_data.get("period_name", "Q2 2025"),
                asset_class=attribution_data.get("asset_class", "Mixed"),
                attribution_level=attribution_data.get("attribution_level", "Sector"),
                tabular_data=attribution_data.get("tabular_data", ""),
                columns_present=list(attribution_data.get("effects_breakdown", {}).keys()),
                portfolio_total_return=attribution_data.get("portfolio_total_return", 0.0),
                benchmark_total_return=attribution_data.get("benchmark_total_return", 0.0),
                total_active_return=attribution_data.get("total_active_return", 0.0),
                effects_breakdown=attribution_data.get("effects_breakdown", {}),
                top_contributors=attribution_data.get("top_contributors", []),
                top_detractors=attribution_data.get("top_detractors", []),
            )
            full_prompt = f"{self.system_prompt}\n\n{self.developer_prompt}\n\n{prompt}"
            commentary = await ollama_service.generate_text(full_prompt)
            return commentary
        except Exception as e:
            logger.error(f"Error generating commentary: {e}")
            return f"Error generating performance attribution commentary: {str(e)}"

    def enhance_document_metadata(self, metadata: Dict[str, Any], attribution_data: Dict[str, Any]) -> Dict[str, Any]:
        if attribution_data:
            metadata["performance_attribution"] = {
                "period": attribution_data.get("period_name"),
                "asset_class": attribution_data.get("asset_class"),
                "attribution_level": attribution_data.get("attribution_level"),
                "portfolio_return": attribution_data.get("portfolio_total_return"),
                "benchmark_return": attribution_data.get("benchmark_total_return"),
                "active_return": attribution_data.get("total_active_return"),
                "top_contributors_count": len(attribution_data.get("top_contributors", [])),
                "top_detractors_count": len(attribution_data.get("top_detractors", [])),
                "effects_present": list(attribution_data.get("effects_breakdown", {}).keys()),
            }
        return metadata

    # --------------------------- Public Entry Point -------------------------- #

    async def process_attribution_file(self, file_path: str, session_id: str) -> Dict[str, Any]:
        """
        Parse Excel → build chunks → embed → store in Qdrant.
        """
        try:
            df, metadata = await self._parse_and_normalize_excel(file_path)
            chunks = await self._build_chunks(df, metadata, session_id)
            self.last_chunks = chunks
            chunks_with_embeddings = await self._generate_embeddings(chunks)
            collection_name = f"attr_session_{session_id}"
            await self._store_chunks_in_qdrant(chunks_with_embeddings, collection_name)
            return {
                "status": "success",
                "session_id": session_id,
                "collection_name": collection_name,
                "chunks_created": len(chunks_with_embeddings),
                "metadata": metadata.__dict__,
                "period": metadata.period,
                "asset_class": metadata.asset_class,
                "attribution_level": metadata.attribution_level,
                "chunks": [
                    {
                        "bucket": c.payload.get("bucket", "Unknown"),
                        "text": c.text,
                        "asset_class": c.payload.get("asset_class", "unknown"),
                        "chunk_type": c.chunk_type,
                    }
                    for c in chunks
                ],
            }
        except Exception as e:
            logger.error(f"Error processing attribution file: {e}")
            raise

    # --------------------------- Excel → DataFrame --------------------------- #

    async def _parse_and_normalize_excel(self, file_path: str) -> Tuple[pd.DataFrame, AttributionMetadata]:
        # Use context manager so Windows can delete the temp file later
        with pd.ExcelFile(file_path) as xls:
            sheet_candidates = ["Attribution", "Performance", "Summary", xls.sheet_names[0]]
            df: Optional[pd.DataFrame] = None
            for s in sheet_candidates:
                if s in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=s)
                    break
        if df is None:
            raise ValueError("No suitable attribution sheet found")

        # Detect asset class & level
        columns_lower = [str(c).lower() for c in df.columns]
        columns_str = " ".join(columns_lower)
        if any(term in columns_str for term in ["gics", "sector", "industry"]):
            asset_class = "Equity"; attribution_level = "Sector"; bucket_patterns = ["sector", "gics", "industry"]
        elif any(term in columns_str for term in ["country", "region", "currency"]):
            asset_class = "Fixed Income"; attribution_level = "Country"; bucket_patterns = ["country", "region"]
        else:
            asset_class = "Equity"; attribution_level = "Sector"; bucket_patterns = ["sector"]

        # Canonicalize columns
        df_clean = df.copy()
        df_clean.columns = [self._canonicalize_column_name(c) for c in df.columns]

        # Bucket column
        bucket_col = None
        for p in bucket_patterns:
            cand = [c for c in df_clean.columns if p in c]
            if cand:
                bucket_col = cand[0]; break
        if bucket_col is None:
            for c in df_clean.columns:
                if df_clean[c].dtype == "object":
                    bucket_col = c; break
        if bucket_col is None:
            raise ValueError("Could not identify bucket column (sector/country)")

        # Drop empty buckets
        df_clean = df_clean.dropna(subset=[bucket_col])

        # Identify effects
        effects_map = {
            "allocation": ["allocation", "alloc", "country_allocation", "sector_allocation"],
            "selection":  ["selection", "select", "security_selection", "issue_selection"],
            "fx":         ["fx", "currency", "foreign_exchange", "fx_selection"],
            "carry":      ["carry", "yield", "run_yield"],
            "roll":       ["roll", "rolldown", "roll_down"],
            "price":      ["price", "price_return"],
        }
        effect_columns: Dict[str, Optional[str]] = {}
        flags: Dict[str, bool] = {}
        for name, pats in effects_map.items():
            found = None
            for p in pats:
                cands = [c for c in df_clean.columns if p in c and ("pp" in c or "contribution" in c or c.endswith("_pp"))]
                if cands:
                    found = cands[0]; break
            effect_columns[name] = found
            flags[f"has_{name}"] = found is not None

        # Coerce numerics except bucket
        numeric_cols = [c for c in df_clean.columns if c != bucket_col]
        for c in numeric_cols:
            df_clean[c] = pd.to_numeric(df_clean[c], errors="coerce")

        # Return columns
        portfolio_col = self._find_column(df_clean.columns, ["portfolio_ror", "portfolio_return", "port_ret"])
        benchmark_col = self._find_column(df_clean.columns, ["benchmark_ror", "benchmark_return", "bench_ret"])
        if portfolio_col and benchmark_col:
            df_clean["active_ror_pp"] = df_clean[portfolio_col] - df_clean[benchmark_col]

        # Total attribution (if not present)
        available_effects = [col for col in effect_columns.values() if col is not None]
        if available_effects and "total_attr_pp" not in df_clean.columns:
            df_clean["total_attr_pp"] = df_clean[available_effects].sum(axis=1, skipna=True)

        # Period from filename
        period = self._extract_period_from_filename(file_path)

        metadata = AttributionMetadata(
            period=period,
            asset_class=asset_class,
            attribution_level=attribution_level,
            columns_present=list(df_clean.columns),
            has_fx=flags.get("has_fx", False),
            has_carry=flags.get("has_carry", False),
            has_roll=flags.get("has_roll", False),
            has_price=flags.get("has_price", False),
            total_rows=len(df_clean),
        )
        return df_clean, metadata

    def _canonicalize_column_name(self, col: str) -> str:
        col_str = str(col).lower()
        col_str = re.sub(r"[^\w]", "_", col_str)
        col_str = re.sub(r"_+", "_", col_str).strip("_")
        return col_str

    def _find_column(self, columns: List[str], patterns: List[str]) -> Optional[str]:
        for p in patterns:
            cands = [c for c in columns if p in c]
            if cands:
                return cands[0]
        return None

    def _extract_period_from_filename(self, file_path: str) -> str:
        filename = file_path.split("\\")[-1].split("/")[-1]
        q = re.search(r"Q(\d)\s*(\d{4})", filename, re.IGNORECASE)
        if q:
            return f"Q{q.group(1)} {q.group(2)}"
        y = re.search(r"(\d{4})", filename)
        if y:
            return f"Q2 {y.group(1)}"
        return "Q2 2025"

    # --------------------------- Chunk Building --------------------------- #

    async def _build_chunks(self, df: pd.DataFrame, metadata: AttributionMetadata, session_id: str) -> List[AttributionChunk]:
        chunks: List[AttributionChunk] = []
        bucket_col = self._find_bucket_column(df, metadata)

        # Exclude any summary rows labeled "total"
        df_rows = df.copy()
        if bucket_col in df_rows.columns:
            df_rows = df_rows[df_rows[bucket_col].astype(str).str.strip().str.lower().ne("total")]

        # Row chunks
        for _, row in df_rows.iterrows():
            chunks.append(self._build_row_chunk(row, metadata, bucket_col, session_id))

        # Totals chunk (weighted returns, effect sums)
        chunks.append(self._build_totals_chunk(df_rows, df, metadata, session_id))

        # Rankings chunk
        chunks.append(self._build_rankings_chunk(df_rows, metadata, bucket_col, session_id))

        # Schema chunk
        chunks.append(self._build_schema_chunk(metadata, session_id))

        return chunks

    def _find_bucket_column(self, df: pd.DataFrame, metadata: AttributionMetadata) -> str:
        patterns = ["sector", "gics", "industry"] if metadata.attribution_level == "Sector" else ["country", "region"]
        for p in patterns:
            cands = [c for c in df.columns if p in c]
            if cands:
                return cands[0]
        for c in df.columns:
            if df[c].dtype == "object":
                return c
        return df.columns[0]

    def _build_row_chunk(self, row: pd.Series, metadata: AttributionMetadata, bucket_col: str, session_id: str) -> AttributionChunk:
        bucket_name = str(row[bucket_col])

        # Returns
        portfolio_ror = self._safe_get_numeric(row, ["portfolio_ror", "portfolio_return"])
        benchmark_ror = self._safe_get_numeric(row, ["benchmark_ror", "benchmark_return"])
        active_ror_pp = self._safe_get_numeric(row, ["active_ror_pp"])
        if active_ror_pp is None and (portfolio_ror is not None and benchmark_ror is not None):
            active_ror_pp = portfolio_ror - benchmark_ror

        # Effects
        allocation_pp = self._safe_get_numeric(row, ["allocation", "allocation_pp", "country_allocation", "sector_allocation"])
        selection_pp  = self._safe_get_numeric(row, ["selection", "selection_pp", "security_selection", "issue_selection"])
        fx_pp         = self._safe_get_numeric(row, ["fx", "fx_pp", "currency", "fx_selection"]) if metadata.has_fx else None
        carry_pp      = self._safe_get_numeric(row, ["carry", "carry_pp", "run_yield"]) if metadata.has_carry else None
        roll_pp       = self._safe_get_numeric(row, ["roll", "roll_pp", "rolldown", "roll_down"]) if metadata.has_roll else None
        price_pp      = self._safe_get_numeric(row, ["price", "price_pp", "price_return"]) if metadata.has_price else None
        total_attr_pp = self._safe_get_numeric(row, ["total_attr_pp", "total_attribution", "total_management"])

        # Weights
        portfolio_wt = self._safe_get_numeric(row, ["portfolio_wt", "portfolio_weight", "portfolio_weight_%"])
        benchmark_wt = self._safe_get_numeric(row, ["benchmark_wt", "benchmark_weight", "benchmark_weight_%"])
        rel_wt_pp = None
        if portfolio_wt is not None and benchmark_wt is not None:
            rel_wt_pp = portfolio_wt - benchmark_wt

        # Text
        parts = [f"{metadata.period} • {metadata.attribution_level} row: {bucket_name}"]
        if portfolio_ror is not None and benchmark_ror is not None:
            parts.append(f"Portfolio ROR: {portfolio_ror:.1f}% | Benchmark ROR: {benchmark_ror:.1f}%")
            if active_ror_pp is not None:
                parts.append(f"Active ROR: {active_ror_pp:+.1f} pp")

        eff = []
        if allocation_pp is not None: eff.append(f"Allocation {allocation_pp:+.1f}")
        if selection_pp  is not None: eff.append(f"Selection {selection_pp:+.1f}")
        if fx_pp        is not None: eff.append(f"FX {fx_pp:+.1f}")
        if carry_pp     is not None: eff.append(f"Carry {carry_pp:+.1f}")
        if roll_pp      is not None: eff.append(f"Roll {roll_pp:+.1f}")
        if price_pp     is not None: eff.append(f"Price {price_pp:+.1f}")
        if eff: parts.append("Attribution effects (pp): " + ", ".join(eff))

        if total_attr_pp is not None:
            parts.append(f"Total Attribution (aka Total Management): {total_attr_pp:+.1f} pp")

        if portfolio_wt is not None and benchmark_wt is not None:
            parts.append(f"Weights: Portfolio {portfolio_wt:.1f}%, Benchmark {benchmark_wt:.1f}%")
            if rel_wt_pp is not None:
                parts.append(f"(Rel {rel_wt_pp:+.1f} pp)")

        text = " | ".join(parts)

        payload = {
            "type": "row",
            "session_id": session_id,
            "asset_class": metadata.asset_class,
            "level": metadata.attribution_level,
            "bucket": bucket_name,
            "period": metadata.period,
            "columns_present": metadata.columns_present,
            "chunk_id": f"row_{bucket_name.replace(' ', '_').replace('/', '_').replace('-', '_')}",  # preserve original id
            "portfolio_ror": _none_if_nan(portfolio_ror),
            "benchmark_ror": _none_if_nan(benchmark_ror),
            "active_ror_pp": _none_if_nan(active_ror_pp),
            "allocation_pp": _none_if_nan(allocation_pp),
            "selection_pp": _none_if_nan(selection_pp),
            "fx_pp": _none_if_nan(fx_pp),
            "carry_pp": _none_if_nan(carry_pp),
            "roll_pp": _none_if_nan(roll_pp),
            "price_pp": _none_if_nan(price_pp),
            "total_attr_pp": _none_if_nan(total_attr_pp),
            "portfolio_wt": _none_if_nan(portfolio_wt),
            "benchmark_wt": _none_if_nan(benchmark_wt),
            "rel_wt_pp": _none_if_nan(rel_wt_pp),
            "has_fx": bool(metadata.has_fx),
            "has_carry": bool(metadata.has_carry),
            "has_roll": bool(metadata.has_roll),
            "has_price": bool(metadata.has_price),
        }

        # Note: Qdrant IDs must be int or UUID; use UUID here
        chunk_uuid = str(uuid.uuid4())
        return AttributionChunk(chunk_uuid, "row", text, payload)

    def _build_totals_chunk(self, df_rows: pd.DataFrame, df_all: pd.DataFrame, metadata: AttributionMetadata, session_id: str) -> AttributionChunk:
        # detect columns
        port_r = self._find_column(df_all.columns, ["portfolio_ror", "portfolio_return"])
        bench_r = self._find_column(df_all.columns, ["benchmark_ror", "benchmark_return"])
        port_w = self._find_column(df_all.columns, ["portfolio_weight", "portfolio_weight_%"])
        bench_w = self._find_column(df_all.columns, ["benchmark_weight", "benchmark_weight_%"])

        portfolio_total = None
        benchmark_total = None
        if port_r and bench_r and port_w and bench_w:
            p_w = pd.to_numeric(df_rows[port_w], errors="coerce")
            b_w = pd.to_numeric(df_rows[bench_w], errors="coerce")
            p_r = pd.to_numeric(df_rows[port_r], errors="coerce")
            b_r = pd.to_numeric(df_rows[bench_r], errors="coerce")
            pw_sum = p_w.dropna().sum()
            bw_sum = b_w.dropna().sum()
            portfolio_total = (p_r * p_w).sum() / pw_sum if pw_sum else np.nan
            benchmark_total = (b_r * b_w).sum() / bw_sum if bw_sum else np.nan

        # effects sum (pp)
        def sum_if(col_patterns: List[str]) -> Optional[float]:
            col = self._find_column(df_all.columns, col_patterns)
            if not col:
                return None
            return float(pd.to_numeric(df_rows[col], errors="coerce").fillna(0).sum())

        allocation_total = sum_if(["allocation", "allocation_effect", "country_allocation", "sector_allocation"])
        selection_total  = sum_if(["selection", "selection_effect", "security_selection", "issue_selection"])
        fx_total         = sum_if(["fx", "currency", "fx_selection"]) if metadata.has_fx else None
        carry_total      = sum_if(["carry", "run_yield"]) if metadata.has_carry else None
        roll_total       = sum_if(["roll", "rolldown", "roll_down"]) if metadata.has_roll else None
        price_total      = sum_if(["price", "price_return"]) if metadata.has_price else None

        active_pp = None
        if portfolio_total is not None and benchmark_total is not None and not (pd.isna(portfolio_total) or pd.isna(benchmark_total)):
            active_pp = float(portfolio_total - benchmark_total)

        lines = [f"{metadata.period} • TOTAL"]
        if portfolio_total is not None and benchmark_total is not None and not (pd.isna(portfolio_total) or pd.isna(benchmark_total)):
            lines.append(f"Portfolio {portfolio_total:.1f}% vs Benchmark {benchmark_total:.1f}% → Active {active_pp:+.1f} pp")

        breakdown = []
        for label, val in [("Allocation", allocation_total), ("Selection", selection_total),
                           ("FX", fx_total), ("Carry", carry_total), ("Roll", roll_total), ("Price", price_total)]:
            if val is not None:
                breakdown.append(f"{label} {val:+.1f}")
        if breakdown:
            lines.append("Attribution breakdown (pp): " + ", ".join(breakdown))
        text = "\n".join(lines)

        payload = {
            "type": "total",
            "session_id": session_id,
            "period": metadata.period,
            "asset_class": metadata.asset_class,
            "level": metadata.attribution_level,
            "chunk_id": "total_summary",  # preserve logical label
            "portfolio_total_ror": _none_if_nan(None if portfolio_total is None else float(portfolio_total)),
            "benchmark_total_ror": _none_if_nan(None if benchmark_total is None else float(benchmark_total)),
            "active_total_pp": _none_if_nan(None if active_pp is None else float(active_pp)),
            "allocation_pp": _none_if_nan(allocation_total),
            "selection_pp": _none_if_nan(selection_total),
            "fx_pp": _none_if_nan(fx_total),
            "carry_pp": _none_if_nan(carry_total),
            "roll_pp": _none_if_nan(roll_total),
            "price_pp": _none_if_nan(price_total),
        }
        return AttributionChunk(str(uuid.uuid4()), "total", text, payload)

    def _build_rankings_chunk(self, df_rows: pd.DataFrame, metadata: AttributionMetadata, bucket_col: str, session_id: str) -> AttributionChunk:
        total_attr_col = self._find_column(df_rows.columns, ["total_attr_pp", "total_attribution", "total_management"])
        if total_attr_col is None:
            text = f"{metadata.period} • Rankings: No total attribution data available"
            payload = {"type": "ranking", "session_id": session_id, "rank_key": None, "chunk_id": "ranking_no_data"}
            return AttributionChunk(str(uuid.uuid4()), "ranking", text, payload)

        df_sorted = df_rows.dropna(subset=[total_attr_col]).sort_values(total_attr_col, ascending=False)

        top_contrib, top_detract = [], []
        for _, r in df_sorted.head(3).iterrows():
            if r[total_attr_col] > 0:
                top_contrib.append({"bucket": str(r[bucket_col]), "pp": float(r[total_attr_col])})
        for _, r in df_sorted.tail(3).iterrows():
            if r[total_attr_col] < 0:
                top_detract.append({"bucket": str(r[bucket_col]), "pp": float(r[total_attr_col])})

        text_parts = [f"{metadata.period} • Rankings by Total Attribution (pp)  (Total Attribution ≡ Total Management)"]
        if top_contrib:
            text_parts.append("Top: " + ", ".join([f"{t['bucket']} {t['pp']:+.1f}" for t in top_contrib]))
        if top_detract:
            text_parts.append("Bottom: " + ", ".join([f"{t['bucket']} {t['pp']:+.1f}" for t in top_detract]))
        text = "\n".join(text_parts)

        payload = {
            "type": "ranking",
            "session_id": session_id,
            "rank_key": "total_attr_pp",
            "top_contributors": _json_sanitize(top_contrib),
            "top_detractors": _json_sanitize(top_detract),
            "asset_class": metadata.asset_class,
            "level": metadata.attribution_level,
            "period": metadata.period,
            "chunk_id": "ranking_total_attr_pp",
        }
        return AttributionChunk(str(uuid.uuid4()), "ranking", text, payload)

    def _build_schema_chunk(self, metadata: AttributionMetadata, session_id: str) -> AttributionChunk:
        explanations = {
            "allocation": f"{metadata.attribution_level} allocation effect - impact of over/under-weighting vs benchmark",
            "selection": "Security/issue selection effect - impact of picking securities within each category",
            "fx": "Foreign exchange selection effect - impact of currency positioning decisions",
            "carry": "Carry/yield effect - income and carry positioning",
            "roll": "Roll-down effect - yield-curve positioning and time decay",
            "price": "Price return effect - credit spread and price moves",
        }
        present = [explanations["allocation"], explanations["selection"]]
        if metadata.has_fx: present.append(explanations["fx"])
        if metadata.has_carry: present.append(explanations["carry"])
        if metadata.has_roll: present.append(explanations["roll"])
        if metadata.has_price: present.append(explanations["price"])

        text = "\n".join(
            [
                f"{metadata.period} • Attribution Effects Glossary",
                f"Asset Class: {metadata.asset_class}",
                f"Attribution Level: {metadata.attribution_level}",
                "",
                "Effects in this analysis:",
            ]
            + [f"• {e}" for e in present]
        )
        payload = {
            "type": "schema",
            "session_id": session_id,
            "columns_present": metadata.columns_present,
            "asset_class": metadata.asset_class,
            "attribution_level": metadata.attribution_level,
            "effects_present": {
                "allocation": True,
                "selection": True,
                "fx": bool(metadata.has_fx),
                "carry": bool(metadata.has_carry),
                "roll": bool(metadata.has_roll),
                "price": bool(metadata.has_price),
            },
            "chunk_id": "schema_glossary",
        }
        return AttributionChunk(str(uuid.uuid4()), "schema", text, payload)

    def _safe_get_numeric(self, row: pd.Series, patterns: List[str]) -> Optional[float]:
        for p in patterns:
            for col in row.index:
                if p in col.lower():
                    val = row[col]
                    if pd.notna(val):
                        try:
                            return float(val)
                        except Exception:
                            try:
                                return float(str(val).replace("%", "").replace(",", ""))
                            except Exception:
                                pass
        return None

    # ----------------------------- Embeddings ----------------------------- #

    async def _generate_embeddings(self, chunks: List[AttributionChunk]) -> List[AttributionChunk]:
        if not self.ollama:
            raise ValueError("Ollama service not configured")
        texts = [c.text for c in chunks]
        embeddings = await self.ollama.generate_embeddings(texts)
        if not embeddings or len(embeddings) != len(texts):
            raise RuntimeError(f"Embedding service returned {len(embeddings) if embeddings else 0} vectors for {len(texts)} texts")
        self.embedding_dim = len(embeddings[0])
        for c, e in zip(chunks, embeddings):
            if len(e) != self.embedding_dim:
                raise RuntimeError(f"Embedding length mismatch: expected {self.embedding_dim}, got {len(e)}")
            # ensure pure floats
            c.embedding = [float(x) for x in e]
        return chunks

    # ------------------------------- Storage ------------------------------ #

    async def _store_chunks_in_qdrant(self, chunks: List[AttributionChunk], collection_name: str, session_id: str = None):
        if not self.qdrant:
            raise ValueError("Qdrant service not configured")
        if not self.embedding_dim:
            raise ValueError("Embedding dimension unknown; generate embeddings first")

        # Recreate collection with correct vector size to avoid stale config mismatches
        try:
            self.qdrant.client.recreate_collection(
                collection_name=collection_name,
                vectors_config=http_models.VectorParams(
                    size=self.embedding_dim,
                    distance=http_models.Distance.COSINE
                )
            )
        except Exception as e:
            logger.warning(f"recreate_collection failed or collection exists: {e}")
            try:
                self.qdrant.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=http_models.VectorParams(
                        size=self.embedding_dim,
                        distance=http_models.Distance.COSINE
                    )
                )
            except Exception as e2:
                logger.info(f"create_collection result: {e2}")

        # Build sanitized PointStruct list
        points: List[PointStruct] = []
        for ch in chunks:
            if not isinstance(ch.embedding, list) or len(ch.embedding) != self.embedding_dim:
                logger.error(f"Skipping {ch.chunk_id}: bad embedding")
                continue
            vector = [float(x) for x in ch.embedding]
            # Merge the logical chunk_id into payload so we can retrieve it later
            payload = dict(_json_sanitize(ch.payload) or {})
            if "chunk_id" not in payload:
                payload["chunk_id"] = ch.chunk_id  # store uuid as well

            # Use UUID ONLY for Qdrant id
            points.append(PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload))

        if not points:
            raise ValueError("No valid points to upsert")

        # Primary upsert via client with wait=True
        try:
            self.qdrant.client.upsert(collection_name=collection_name, points=points, wait=True)
        except Exception as e:
            logger.error(f"Qdrant upsert via client failed: {e}")

            # REST fallback
            import requests
            rest_points = [{"id": str(p.id), "vector": {"": list(p.vector[""])}, "payload": p.payload} for p in points]
            body = _json_sanitize(rest_points)
            resp = requests.put(
                f"http://localhost:6333/collections/{collection_name}/points?wait=true",
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            if resp.status_code != 200:
                raise RuntimeError(f"REST upsert failed: {resp.status_code} {resp.text}")

        # Verify count
        try:
            cnt = self.qdrant.client.count(collection_name, exact=True)
            logger.info(f"Stored points in {collection_name}: {cnt.count}")
        except Exception as e:
            logger.warning(f"Count check failed: {e}")

    # ------------------------------ Retrieval ----------------------------- #

    async def answer_question(self, session_id: str, question: str, mode: str = "qa", context: str = None) -> Dict[str, Any]:
        if not self.qdrant or not self.ollama:
            raise ValueError("Services not configured")

        collection_name = f"attr_session_{session_id}"

        # Use provided context (from UI) if present
        if context:
            context_json = context
        else:
            if not await self.qdrant.collection_exists(collection_name):
                raise ValueError(f"No attribution data found for session {session_id}")

            # Embed query
            if hasattr(self.ollama, "generate_embedding"):
                query_embedding = await self.ollama.generate_embedding(question)
            else:
                emb_list = await self.ollama.generate_embeddings([question])
                query_embedding = emb_list[0]

            filters = self._derive_filters_from_question(question)

            # Search with named vector (empty string for default)
            try:
                search_results = self.qdrant.client.search(
                    collection_name=collection_name,
                    query_vector=("", query_embedding),
                    query_filter=filters,
                    limit=12,
                    with_payload=True,
                )
            except (TypeError, Exception):
                # Fallback to older format
                try:
                    search_results = self.qdrant.client.search(
                        collection_name=collection_name,
                        query_vector=query_embedding,
                        query_filter=filters,
                        limit=12,
                        with_payload=True,
                    )
                except TypeError:
                    search_results = self.qdrant.client.search(
                        collection_name=collection_name,
                        vector=query_embedding,
                        query_filter=filters,
                        limit=12,
                        with_payload=True,
                    )

            import json
            logger.info(f"Search found {len(search_results or [])} results for question: {question} (mode: {mode})")
            context_json = json.dumps([r.payload for r in (search_results or [])], indent=2)
            logger.info(f"Context JSON length: {len(context_json)} characters for mode: {mode}")

        # Generate response
        if mode == "commentary":
            return await self._generate_commentary_response(context_json, session_id)
        else:
            return await self._generate_qa_response(question, context_json, session_id)

    def _derive_filters_from_question(self, question: str) -> Optional[Filter]:
        q = question.lower()
        must = []
        if "fx" in q or "currency" in q:
            must.append(FieldCondition(key="has_fx", match=Match(value=True)))
        return Filter(must=must) if must else None

    async def _generate_commentary_response(self, context: str, session_id: str) -> Dict[str, Any]:
        # Validate context is not empty or meaningless
        context_lines = [line.strip() for line in context.split('\n') if line.strip()]
        if len(context_lines) < 3 or not any('portfolio' in line.lower() or 'return' in line.lower() or 'attribution' in line.lower() for line in context_lines):
            logger.warning(f"Commentary validation failed: {len(context_lines)} context lines found, session: {session_id}")
            return {
                "mode": "commentary",
                "response": "Unable to generate commentary: No valid attribution data found in the context. Please ensure the attribution file was uploaded and processed successfully, and that the session contains performance attribution data.",
                "session_id": session_id,
                "context_used": 0,
                "error": "No valid context provided",
            }
        
        user_prompt = f"""
CONTEXT:
{context}

Generate professional attribution commentary following this structure:
1) Executive Summary (3-4 sentences)
2) Total Performance Drivers
3) Top Contributors/Detractors
4) Key Risks/Watch Items (if justified by data)

Use one decimal place for pp values and retain +/- signs.
"""
        response = await self.ollama.generate_response(user_prompt, system_prompt=self.system_prompt, temperature=0.1)
        return {
            "mode": "commentary",
            "response": response.get("response", ""),
            "session_id": session_id,
            "context_used": len(context_lines),
            "prompt": user_prompt,
        }

    async def _generate_qa_response(self, question: str, context: str, session_id: str) -> Dict[str, Any]:
        # Validate context is not empty or meaningless
        context_lines = [line.strip() for line in context.split('\n') if line.strip()]
        if len(context_lines) < 3 or not any('portfolio' in line.lower() or 'return' in line.lower() or 'attribution' in line.lower() for line in context_lines):
            logger.warning(f"Q&A validation failed: {len(context_lines)} context lines found for question: {question}, session: {session_id}")
            return {
                "mode": "qa",
                "question": question,
                "response": "Unable to answer question: No valid attribution data found in the context. Please ensure the attribution file was uploaded and processed successfully, and that the session contains performance attribution data.",
                "session_id": session_id,
                "context_used": 0,
                "error": "No valid context provided",
            }
        
        system_prompt = """You are a meticulous attribution Q&A assistant.
Answer ONLY using the CONTEXT from the user's uploaded document (tables, derived stats, excerpts).
If the answer is not present in CONTEXT, reply: "The report does not contain that information."
Be concise and numeric. Use % for returns and pp for attribution."""
        user_prompt = f"""
QUESTION: {question}

CONTEXT:
{context}

RESPONSE RULES:
- Use only numbers/fields in CONTEXT
- Rank or sum if asked, else quote exact row values
- If data insufficient, state it explicitly
"""
        response = await self.ollama.generate_response(user_prompt, system_prompt=system_prompt, temperature=0.0)
        return {
            "mode": "qa",
            "question": question,
            "response": response.get("response", ""),
            "session_id": session_id,
            "context_used": len(context_lines),
            "prompt": user_prompt,
        }

    # --------------------------- Session Utilities -------------------------- #

    async def clear_session(self, session_id: str) -> bool:
        if not self.qdrant:
            return False
        collection_name = f"attr_session_{session_id}"
        try:
            if await self.qdrant.collection_exists(collection_name):
                self.qdrant.client.delete_collection(collection_name)
                logger.info(f"Cleared attribution session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing session {session_id}: {e}")
            return False

    async def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        if not self.qdrant:
            return {"exists": False, "error": "Qdrant service not configured"}
        collection_name = f"attr_session_{session_id}"
        if not await self.qdrant.collection_exists(collection_name):
            return {"exists": False}
        try:
            info = self.qdrant.client.get_collection(collection_name)
            return {
                "exists": True,
                "session_id": session_id,
                "collection_name": collection_name,
                "total_chunks": getattr(info, "points_count", None),
                "indexed_chunks": getattr(info, "indexed_vectors_count", None),
                "status": getattr(info, "status", None),
            }
        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            return {"exists": False, "error": str(e)}
