from typing import Dict, Any, List, Optional, Tuple
import re
import logging
import pandas as pd
import numpy as np
import uuid
import math
import json
from dataclasses import dataclass

from qdrant_client.models import Filter, FieldCondition, Match, PointStruct
from qdrant_client.http import models as http_models

logger = logging.getLogger(__name__)

# ============================= Helpers ============================= #

def _json_sanitize(obj):
    """Make values safe for Qdrant JSON (no NaN/Inf/numpy/unserializable)."""
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
    return str(obj)

def _none_if_nan(x):
    try:
        if x is None:
            return None
        if isinstance(x, (np.floating,)):
            x = float(x)
        if isinstance(x, (np.integer,)):
            x = int(x)
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return x
    except Exception:
        return None

def _pp(x) -> Optional[float]:
    """Coerce to float (pp), return None for bad/NaN."""
    try:
        if x is None:
            return None
        if isinstance(x, str):
            x = x.replace("%", "").replace(",", "")
        f = float(x)
        return None if math.isnan(f) or math.isinf(f) else f
    except Exception:
        return None

def _pct(x) -> Optional[float]:
    """Alias for percent values (same handling as _pp)."""
    return _pp(x)

# ============================= Data ============================= #

@dataclass
class AttributionMetadata:
    """Metadata for attribution analysis"""
    period: str
    asset_class: str
    attribution_level: str
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

# =================== Performance Attribution Service =================== #

class PerformanceAttributionService:
    """
    Processes attribution Excel files → builds chunks → stores in Qdrant.
    Generates fast, concise PM-ready commentary with correct use of
    performance (%) vs attribution (pp).
    """

    def __init__(self, ollama_service=None, qdrant_service=None):
        self.ollama = ollama_service
        self.qdrant = qdrant_service
        self.embedding_model = "nomic-embed-text"
        self.embedding_dim: Optional[int] = None

        # Crisp, PM-grade system instruction
        self.system_prompt = (
            
            """
            You are an expert CFA charterholder and quantitative analyst performing attribution analysis.
            Produce a Brinson–Fachler attribution report in a clear, professional, analytical story style.
            **No recommendations or criticism or conclusions**
            Definitions
            Performance: Portfolio and benchmark returns.
            Attribution: Decomposition of alpha into Total Effect, Selection Effect, and Allocation Effect.
            Formulas
            - Allocation = (Portfolio Weight − Benchmark Weight) × (Benchmark Sector Return − Benchmark Total Return)
            - Selection = Portfolio Weight × (Portfolio Sector Return − Benchmark Sector Return)
            - Total Effect = Allocation + Selection
            - Selection: positive if PR greater than BR; negative if PR lesser than BR (reference PW if provided).
            - Allocation: positive if PW greater than BW and BR is greater than Benchmark Total Return, or PW lesser than BW and BR is lesser than Benchmark Total Return; negative if PW lesser than BW and BR is greater than Benchmark Total Return or if PW greater than BW and BR is lesser than Benchmark Total Return.
            
            Output Rules (STRICT)
            1) Opening point: use the provided point EXACTLY as the opener (already in OUTPUT TEMPLATE).
            2) Then write **exactly 200 words** in **bullet points** (each contributor in separate points, then detractors in separate points and other sectors if present).
            - Mention ALL countries/sectors provided by the user.
            - For each country/sector, include Total Effect (bps) and driver(s) (selection, allocation, or both) using the given numbers.
            3) No narratives. No recommendations or criticism or unwanted text.
            4) **Do not calculate or invent numbers; use ONLY provided values.**
            5) Do not use "performance" to describe attribution results.
            6) **Do not include any introductory or framing sentences such as “Here’s the report,” “Below is the commentary,” or similar.
            """
        )

        # Developer guardrails
        self.developer_prompt = (
            "- Use numbers only from context.\n"
            "- Distinguish performance (%) vs attribution (pp).\n"
            "- Report effects that exist in context: Allocation, Selection (Sector & Issue), FX, Carry, Roll, Price.\n"
            "- If 'Total Management' is missing, define it as Sector Selection + Issue Selection (only if both present).\n"
            "- Rank top contributors/detractors by Total Management.\n"
            "- Two decimal places for pp values with sign (+/-); returns keep two decimal places % if provided.\n"
            "- ≤ 180 words; no tables unless necessary.\n"
        )

        self.last_chunks: List[AttributionChunk] = []

    # ============================ Prompt Builder ============================ #

    def choose_opening_verb(self, excess_bps: float, nearline_thresh: int = 1) -> str:
        if abs(excess_bps) <= nearline_thresh:
            return "was broadly in line"
        return "outperformed" if excess_bps > 0 else "fell short of"
 
    

    def _prompt_template_fast(self, summary: Dict[str, Any]) -> str:
        """
        Small, well-formed prompt for speed. Contains definitions & formulas,
        distilled facts, and strict output format.
        """
        print(summary)
        # Build effect line in a consistent order
        ordered_labels = ["Allocation", "Selection", "FX", "Carry", "Roll", "Price", "Total Management"]
        eff_lines = []
        for k in ordered_labels:
            if k in summary.get("effects", {}):
                eff_lines.append(f"{k}: {summary['effects'][k]:+0.2f} pp")
        effects_str = ", ".join(eff_lines) if eff_lines else "Not reported."

        # ------------------ Rankings (UPDATED) ------------------
        import ast, re

        def _coerce_rows(obj):
            """Accepts list[dict] or a string that contains {...} dicts; returns list[dict]."""
            if isinstance(obj, list):
                return [x for x in obj if isinstance(x, dict)]
            if isinstance(obj, str):
                dict_strs = re.findall(r'\{[^{}]*\}', obj)
                out = []
                for s in dict_strs:
                    try:
                        out.append(ast.literal_eval(s))
                    except Exception:
                        pass
                return out
            return []

        def _bps(x):
            try:
                return int(round(float(x) * 100))
            except Exception:
                return 0

        def _pct(x):
            try:
                return f"{float(x):0.2f}%"
            except Exception:
                return "n/a"

        def _pick_sector(d):
            return str(d.get("sector") or d.get("bucket") or d.get("name") or "Item")

        # Wording helpers
        def _pr_vs_br_phrase(diff):
            # >= +3.0: significantly higher | +0.5..+3: slightly higher | <= -3: lesser than | -3..-0.5: slightly lower | else: in line
            if diff >= 3.0:
                return "significantly higher than BR"
            if diff >= 0.5:
                return "slightly higher than BR"
            if diff <= -3.0:
                return "lesser than BR"
            if diff <= -0.5:
                return "slightly lower than BR"
            return "in line with BR"

        def _bm_vs_sector_phrase(diff):
            # >= +3: greater than | +0.5..+3: slightly higher | <= -3: lesser than | -3..-0.5: slightly lower | else: omit
            if diff >= 3.0:
                return "greater than sector BR"
            if diff >= 0.5:
                return "slightly higher than sector BR"
            if diff <= -3.0:
                return "lesser than sector BR"
            if diff <= -0.5:
                return "slightly lower than sector BR"
            return None

        def _pw_vs_bw_phrase(diff):
            # >= +3: significantly higher than | +0.5..+3: slightly higher than | <= -3: lesser than | -3..-0.5: slightly lesser than | else: omit
            if diff >= 3.0:
                return "significantly higher than"
            if diff >= 0.5:
                return "slightly higher than"
            if diff <= -3.0:
                return "lesser than"
            if diff <= -0.5:
                return "slightly lesser than"
            return None

        # Accept both plural/singular keys or string payloads
        raw_top = summary.get("top_contributors", summary.get("top_contributor"))
        raw_bot = summary.get("top_detractors", summary.get("top_detractor"))
        top_rows = _coerce_rows(raw_top)
        bot_rows = list(reversed(_coerce_rows(raw_bot)))

        # Keys (snake_case per your payload)
        RK_TOTAL = "total_management"
        RK_SEL = "issue_selection"
        RK_ALLOC = "sector_allocation"

        # Overall benchmark total return (for "Bench Mark Total Return vs sector BR")
        bm_total = summary.get("benchmark_ror", None)

        def _line_for_row(d):
            sector = _pick_sector(d)

            # Effects in bps
            total_eff_bps = _bps(d.get(RK_TOTAL, d.get("pp", 0)))
            sel_bps = _bps(d.get(RK_SEL, 0))
            alloc_bps = _bps(d.get(RK_ALLOC, 0))

            # PR vs BR
            pr = d.get("portfolio_ror")
            br = d.get("benchmark_ror")
            pr_vs_br = ""
            if isinstance(pr, (int, float)) and isinstance(br, (int, float)):
                diff = float(pr) - float(br)
                pr_vs_br = f"PR {_pr_vs_br_phrase(diff)} ({_pct(pr)} vs {_pct(br)})"

            # Build base (up to Allocation) exactly as requested
            parts = [
                f"**{sector}: Total effect {total_eff_bps} bps; ",
                f"Selection {sel_bps} bps; ",
                f"{pr_vs_br};"
            ]

            include_trailing = False
            if abs(alloc_bps) >= 4:
                parts.append(f" Allocation {alloc_bps} bps;")
                include_trailing = True

            # Only include the following if Allocation was included (to match your examples)
            trailing_bits = []
            if include_trailing and isinstance(bm_total, (int, float)) and isinstance(br, (int, float)):
                phr2 = _bm_vs_sector_phrase(float(bm_total) - float(br))
                if phr2:
                    trailing_bits.append(f"Bench Mark Total Return {phr2} ({_pct(bm_total)} vs {_pct(br)})")

            pw = d.get("portfolio_weight")
            bw = d.get("benchmark_weight")
            if include_trailing and isinstance(pw, (int, float)) and isinstance(bw, (int, float)):
                wphr = _pw_vs_bw_phrase(float(pw) - float(bw))
                if wphr:
                    trailing_bits.append(f"PW is {wphr} BW ({_pct(pw)} vs {_pct(bw)})")

            if trailing_bits:
                # bench phrase first, then ",  " + PW phrase; end with semicolon
                parts.append(f" {',  '.join(trailing_bits)};")

            # End line with asterisk (as in your sample)
            parts.append("*")
            return "".join(parts)

        # Compose final strings (assumes inputs are already ranked)
        top_text = "\n".join([_line_for_row(d) for d in top_rows[:3]]) if top_rows else "Not reported in the context."
        bot_text = "\n".join([_line_for_row(d) for d in bot_rows[:3]]) if bot_rows else "Not reported in the context."

        print("***************top text")
        print(top_text)

        print("***************bottom text")
        print(bot_text)

        # Destructure metrics
        active = summary.get("active_pp")
        port = summary.get("portfolio_ror")
        bench = summary.get("benchmark_ror")
        effects_list = summary.get("effects",{})

        verb = self.choose_opening_verb(float(active))
        opening_template = (
            f'The portfolio {verb} {port:.2f}% against the benchmark’s '
            f'{bench:.2f}%. This resulted in an alpha of '
            f'{effects_list["Total Management"]*100:.0f} bps, with {effects_list["Selection"]*100:.0f} bps attributed to issue selection and '
            f'{effects_list["Allocation"]*100:.0f} bps to sector allocation.'
        )

        # Definitions block (kept compact but explicit)
        defs = (
            "Definitions & Rules:\n"
            "- Performance is in %, Attribution is in pp.\n"
            "- Active return (pp) = Portfolio % − Benchmark %.\n"
            "- Total Management (pp) = Sector Selection (pp) + Issue Selection (pp) (fallback if total not provided).\n"
            "- Report only effects provided in context. Do not invent.\n"
        )

        header = f"""OUTPUT TEMPLATE:
    {opening_template}


    Contributors:
    *
    *

    Detractors:
    *
    *
    """
        # Replace the ranks block to match your expected section headings
        ranks = (
            "\n\nUSER: \n\nContributors (already ranked):\n"
            f"{top_text}\n\n"
            "Detractors (already ranked):\n"
            f"{bot_text}\n"
        )
        assistant = """\nNow write the attribution report commentary based on the provided data."""

        return header + ranks + assistant


    # =========================== Excel Extraction =========================== #

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

            for row in table_data:
                for col_name, value in row.items():
                    if isinstance(value, str):
                        v = value.lower()
                        if "portfolio total" in v or "total portfolio" in v:
                            results["portfolio_total_return"] = self._extract_return_value(row, col_name)
                        elif "benchmark total" in v or "total benchmark" in v:
                            results["benchmark_total_return"] = self._extract_return_value(row, col_name)

            results["total_active_return"] = results["portfolio_total_return"] - results["benchmark_total_return"]

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

    # ======================== Parsing Helper Utils ======================== #

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

    # ============================ Commentary (LLM) ============================ #

    async def generate_commentary(self, attribution_data: Dict[str, Any], ollama_service) -> str:
        try:
            # Not used in the current path (we use summarized prompt), but kept for compatibility.
            return await ollama_service.generate_text("Not used")
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

    # ============================ Public Entry ============================ #

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

    # ========================== Excel → DataFrame ========================== #

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

        # Detect asset class & attribution level
        columns_lower = [str(c).lower() for c in df.columns]
        columns_str = " ".join(columns_lower)
        if any(term in columns_str for term in ["gics", "sector", "industry"]):
            asset_class = "Equity"; attribution_level = "Sector"; bucket_patterns = ["sector", "gics", "industry"]
        elif any(term in columns_str for term in ["country", "region", "currency"]):
            asset_class = "Fixed Income"; attribution_level = "Country"; bucket_patterns = ["country", "region"]
        else:
            # Default to Equity/Sector for equity files
            asset_class = "Equity"; attribution_level = "Sector"; bucket_patterns = ["sector", "gics", "industry"]

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

        # Identify effect columns (loose matching, and pp/contribution)
        # Key attribution columns: sector allocation, issue selection, total management
        effects_map = {
            "allocation": ["allocation_effect", "allocation", "alloc"],
            "selection": ["selection_effect", "selection", "select"],
            "fx":         ["fx", "currency", "foreign_exchange", "fx_selection"],
            "carry":      ["carry", "yield", "run_yield"],
            "roll":       ["roll", "rolldown", "roll_down"],
            "price":      ["price", "price_return"],
            "total_mgmt": ["total_management", "total_mgmt"],
        }

        def _find_effect(col_patterns: List[str]) -> Optional[str]:
            for p in col_patterns:
                # First try to find columns with pp or contribution indicators
                cands = [c for c in df_clean.columns if p in c and ("pp" in c or "contribution" in c or c.endswith("_pp") or "_contrib" in c)]
                if cands:
                    return cands[0]
                # If no pp/contribution columns found, try exact pattern match for attribution columns
                cands = [c for c in df_clean.columns if p in c]
                if cands:
                    return cands[0]
            return None

        effect_cols: Dict[str, Optional[str]] = {k: _find_effect(v) for k, v in effects_map.items()}

        # Coerce numerics except bucket
        for c in df_clean.columns:
            if c != bucket_col:
                df_clean[c] = pd.to_numeric(df_clean[c], errors="coerce")

        # Return columns - Portfolio ROR (%), Benchmark ROR (%)
        portfolio_col = self._find_column(df_clean.columns, ["portfolio_ror", "portfolio_return", "port_ret"])
        benchmark_col = self._find_column(df_clean.columns, ["benchmark_ror", "benchmark_return", "bench_ret"])
        if portfolio_col and benchmark_col:
            df_clean["active_ror_pp"] = df_clean[portfolio_col] - df_clean[benchmark_col]

        # Total Management should be present as a column - no fallback needed
        # Note: Total Management = Allocation Effect + Selection Effect

        # Period from filename
        period = self._extract_period_from_filename(file_path)

        metadata = AttributionMetadata(
            period=period,
            asset_class=asset_class,
            attribution_level=attribution_level,
            columns_present=list(df_clean.columns),
            has_fx=bool(effect_cols["fx"]),
            has_carry=bool(effect_cols["carry"]),
            has_roll=bool(effect_cols["roll"]),
            has_price=bool(effect_cols["price"]),
            total_rows=len(df_clean),
        )

        # Stash the columns for later ranking logic
        self._effect_cols = effect_cols
        self._bucket_col = bucket_col
        self._portfolio_col = portfolio_col
        self._benchmark_col = benchmark_col

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

    # ============================ Chunk Building ============================ #

    async def _build_chunks(self, df: pd.DataFrame, metadata: AttributionMetadata, session_id: str) -> List[AttributionChunk]:
        chunks: List[AttributionChunk] = []
        bucket_col = self._find_bucket_column(df, metadata)

        # Identify total row if present
        total_row = None
        df_rows = df.copy()
        if bucket_col in df_rows.columns:
            mask = df_rows[bucket_col].astype(str).str.strip().str.lower() == "total"
            if mask.any():
                total_row = df_rows[mask].iloc[0]
                df_rows = df_rows[~mask]

        # Row chunks
        for _, row in df_rows.iterrows():
            chunks.append(self._build_row_chunk(row, metadata, bucket_col, session_id))

        # Totals chunk: use total row if available, else calculate
        if total_row is not None:
            chunks.append(self._build_row_chunk(total_row, metadata, bucket_col, session_id))
        else:
            chunks.append(self._build_totals_chunk(df_rows, df, metadata, session_id))

        # Rankings chunk (Total Management → Total Attribution → fallback formula)
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

        # Returns (ROR is also called as return)
        portfolio_ror = self._safe_get_numeric(row, ["portfolio_ror", "portfolio_return", "port_ror", "portfolio_%"])
        benchmark_ror = self._safe_get_numeric(row, ["benchmark_ror", "benchmark_return", "bench_ror", "benchmark_%"])
        active_ror_pp = self._safe_get_numeric(row, ["active_ror_pp"])
        if active_ror_pp is None and (portfolio_ror is not None and benchmark_ror is not None):
            active_ror_pp = portfolio_ror - benchmark_ror

        # Effects based on actual equity columns: Allocation Effect (pp), Selection Effect (pp), Total Management
        allocation_pp = self._safe_get_numeric(row, ["allocation_effect", "allocation", "alloc"])
        selection_pp = self._safe_get_numeric(row, ["selection_effect", "selection", "select"])
        fx_pp         = self._safe_get_numeric(row, ["fx", "fx_pp", "currency", "fx_selection"]) if metadata.has_fx else None
        carry_pp      = self._safe_get_numeric(row, ["carry", "carry_pp", "run_yield"]) if metadata.has_carry else None
        roll_pp       = self._safe_get_numeric(row, ["roll", "roll_pp", "rolldown", "roll_down"]) if metadata.has_roll else None
        price_pp      = self._safe_get_numeric(row, ["price", "price_pp", "price_return"]) if metadata.has_price else None
        total_mgmt_pp = self._safe_get_numeric(row, ["total_management", "total_mgmt"])

        # Weights - Portfolio Weight (%), Benchmark Weight (%)
        portfolio_wt = self._safe_get_numeric(row, ["portfolio_wt", "portfolio_weight", "portfolio_weight_%", "portfolio_weight_pp"])
        benchmark_wt = self._safe_get_numeric(row, ["benchmark_wt", "benchmark_weight", "benchmark_weight_%", "benchmark_weight_pp"])
        rel_wt_pp = None
        if portfolio_wt is not None and benchmark_wt is not None:
            rel_wt_pp = portfolio_wt - benchmark_wt

        # Text - show numbers in 2 decimal places
        parts = [f"{metadata.period} • {metadata.attribution_level} row: {bucket_name}"]
        if portfolio_ror is not None and benchmark_ror is not None:
            parts.append(f"Portfolio ROR: {portfolio_ror}% | Benchmark ROR: {benchmark_ror}%")
            if active_ror_pp is not None:
                parts.append(f"Active ROR: {active_ror_pp} pp")

        eff = []
        if allocation_pp is not None: eff.append(f"Allocation Effect {allocation_pp}")
        if selection_pp is not None: eff.append(f"Selection Effect {selection_pp}")
        if fx_pp        is not None: eff.append(f"FX {fx_pp}")
        if carry_pp     is not None: eff.append(f"Carry {carry_pp}")
        if roll_pp      is not None: eff.append(f"Roll {roll_pp}")
        if price_pp     is not None: eff.append(f"Price {price_pp}")
        if eff: parts.append("Attribution effects (pp): " + ", ".join(eff))

        if total_mgmt_pp is not None:
            parts.append(f"Total Management: {total_mgmt_pp} pp")

        if portfolio_wt is not None and benchmark_wt is not None:
            parts.append(f"Weights: Portfolio {portfolio_wt}%, Benchmark {benchmark_wt}%")
            if rel_wt_pp is not None:
                parts.append(f"(Rel {rel_wt_pp} pp)")

        text = " | ".join(parts)

        payload = {
            "type": "row",
            "session_id": session_id,
            "asset_class": metadata.asset_class,
            "level": metadata.attribution_level,
            "bucket": bucket_name,
            "period": metadata.period,
            "columns_present": metadata.columns_present,
            "chunk_id": f"row_{bucket_name.replace(' ', '_').replace('/', '_').replace('-', '_')}",
            "portfolio_ror": _none_if_nan(portfolio_ror),
            "benchmark_ror": _none_if_nan(benchmark_ror),
            "active_ror_pp": _none_if_nan(active_ror_pp),
            "allocation_effect_pp": _none_if_nan(allocation_pp),
            "selection_effect_pp": _none_if_nan(selection_pp),
            "fx_pp": _none_if_nan(fx_pp),
            "carry_pp": _none_if_nan(carry_pp),
            "roll_pp": _none_if_nan(roll_pp),
            "price_pp": _none_if_nan(price_pp),
            "total_management": _none_if_nan(total_mgmt_pp),
            "portfolio_weight": _none_if_nan(portfolio_wt),
            "benchmark_weight": _none_if_nan(benchmark_wt),
            "relative_weight_pp": _none_if_nan(rel_wt_pp),
            "has_fx": bool(metadata.has_fx),
            "has_carry": bool(metadata.has_carry),
            "has_roll": bool(metadata.has_roll),
            "has_price": bool(metadata.has_price),
        }

        return AttributionChunk(str(uuid.uuid4()), "row", text, payload)

    def _build_totals_chunk(self, df_rows: pd.DataFrame, df_all: pd.DataFrame, metadata: AttributionMetadata, session_id: str) -> AttributionChunk:
        # detect columns
        port_r = self._portfolio_col or self._find_column(df_all.columns, ["portfolio_ror", "portfolio_return"])
        bench_r = self._benchmark_col or self._find_column(df_all.columns, ["benchmark_ror", "benchmark_return"])
        port_w = self._find_column(df_all.columns, ["portfolio_weight", "portfolio_weight_%", "portfolio_wt"])
        bench_w = self._find_column(df_all.columns, ["benchmark_weight", "benchmark_weight_%", "benchmark_wt"])

        portfolio_total = None
        benchmark_total = None
        if port_r and bench_r and port_w and bench_w:
            p_w = pd.to_numeric(df_rows[port_w], errors="coerce")
            b_w = pd.to_numeric(df_rows[bench_w], errors="coerce")
            p_r = pd.to_numeric(df_rows[port_r], errors="coerce")
            b_r = pd.to_numeric(df_rows[bench_r], errors="coerce")
            pw_sum = p_w.dropna().sum()
            bw_sum = b_w.dropna().sum()
            # portfolio_total = (p_r * p_w).sum() / pw_sum if pw_sum else np.nan
            portfolio_total =  p_r.sum()
            # benchmark_total = (b_r * b_w).sum() / bw_sum if bw_sum else np.nan
            benchmark_total = b_r.sum()

        # effects sum (pp)
        def sum_if(col_patterns: List[str]) -> Optional[float]:
            col = self._find_column(df_all.columns, col_patterns)
            if not col:
                return None
            return float(pd.to_numeric(df_rows[col], errors="coerce").fillna(0).sum())

        allocation_total = sum_if(["allocation_effect", "allocation", "alloc"])
        selection_total = sum_if(["selection_effect", "selection", "select"])

        fx_total    = sum_if(["fx", "currency", "fx_selection"]) if metadata.has_fx else None
        carry_total = sum_if(["carry", "run_yield"]) if metadata.has_carry else None
        roll_total  = sum_if(["roll", "rolldown", "roll_down"]) if metadata.has_roll else None
        price_total = sum_if(["price", "price_return"]) if metadata.has_price else None

        total_mgmt_total = sum_if(["total_management", "total_mgmt"])

        active_pp = None
        if portfolio_total is not None and benchmark_total is not None and not (pd.isna(portfolio_total) or pd.isna(benchmark_total)):
            active_pp = float(portfolio_total - benchmark_total)

        lines = [f"{metadata.period} • TOTAL"]
        if portfolio_total is not None and benchmark_total is not None and not (pd.isna(portfolio_total) or pd.isna(benchmark_total)):
            lines.append(f"Portfolio {portfolio_total}% vs Benchmark {benchmark_total}% → Active {active_pp} pp")

        breakdown = []
        if allocation_total is not None: breakdown.append(f"Allocation Effect {allocation_total}")
        if selection_total  is not None: breakdown.append(f"Selection Effect {selection_total}")
        if fx_total         is not None: breakdown.append(f"FX {fx_total}")
        if carry_total      is not None: breakdown.append(f"Carry {carry_total}")
        if roll_total       is not None: breakdown.append(f"Roll {roll_total}")
        if price_total      is not None: breakdown.append(f"Price {price_total}")
        if total_mgmt_total is not None: breakdown.append(f"Total Management {total_mgmt_total}")
        if breakdown:
            lines.append("Attribution breakdown (pp): " + ", ".join(breakdown))
        text = "\n".join(lines)

        payload = {
            "type": "total",
            "session_id": session_id,
            "period": metadata.period,
            "asset_class": metadata.asset_class,
            "level": metadata.attribution_level,
            "chunk_id": "total_summary",
            "portfolio_total_ror": _none_if_nan(None if portfolio_total is None else float(portfolio_total)),
            "benchmark_total_ror": _none_if_nan(None if benchmark_total is None else float(benchmark_total)),
            "active_total_pp": _none_if_nan(None if active_pp is None else float(active_pp)),
            "allocation_effect_pp": _none_if_nan(allocation_total),
            "selection_effect_pp": _none_if_nan(selection_total),
            "fx_pp": _none_if_nan(fx_total),
            "carry_pp": _none_if_nan(carry_total),
            "roll_pp": _none_if_nan(roll_total),
            "price_pp": _none_if_nan(price_total),
            "total_management_pp": _none_if_nan(total_mgmt_total),
        }
        return AttributionChunk(str(uuid.uuid4()), "total", text, payload)

    def _build_rankings_chunk(self, df_rows: pd.DataFrame, metadata: AttributionMetadata, bucket_col: str, session_id: str) -> AttributionChunk:
        # Use Total Management for ranking (it should be present in equity files)
        rank_key = None
        for key in ["total_management", "total_mgmt"]:
            if key in df_rows.columns:
                rank_key = key
                break
        if rank_key is None:
            # Fallback: use allocation + selection if both present
            alloc_col = "allocation_effect" if "allocation_effect" in df_rows.columns else None
            sel_col  = "selection_effect" if "selection_effect" in df_rows.columns else None
            if alloc_col and sel_col:
                df_rows = df_rows.copy()
                df_rows["__fallback_rank__"] = df_rows[alloc_col].fillna(0.0) + df_rows[sel_col].fillna(0.0)
                rank_key = "__fallback_rank__"

        if rank_key is None:
            text = f"{metadata.period} • Rankings: No total management data available"
            payload = {"type": "ranking", "session_id": session_id, "rank_key": None, "chunk_id": "ranking_no_data"}
            return AttributionChunk(str(uuid.uuid4()), "ranking", text, payload)

        df_sorted = df_rows.dropna(subset=[rank_key]).sort_values(rank_key, ascending=False)

        top_contrib, top_detract = [], []
        for _, r in df_sorted.head(3).iterrows():
            if r[rank_key] > 0:
                contrib = {col: r[col] for col in df_sorted.columns}
                contrib["bucket"] = str(r[bucket_col])
                contrib["pp"] = float(r[rank_key])
                top_contrib.append(contrib)
        for _, r in df_sorted.tail(3).iterrows():
            if r[rank_key] < 0:
                detract = {col: r[col] for col in df_sorted.columns}
                detract["bucket"] = str(r[bucket_col])
                detract["pp"] = float(r[rank_key])
                top_detract.append(detract)

        label = "Total Management"
        text_parts = [f"{metadata.period} • Rankings by {label} (pp)"]
        if top_contrib:
            text_parts.append("Top: " + ", ".join([str(t) for t in top_contrib]))
        if top_detract:
            text_parts.append("Bottom: " + ", ".join([str(t) for t in top_detract]))
        text = "\n".join(text_parts)

        payload = {
            "type": "ranking",
            "session_id": session_id,
            "rank_key": "total_management",
            "top_contributors": _json_sanitize(top_contrib),
            "top_detractors": _json_sanitize(top_detract),
            "asset_class": metadata.asset_class,
            "level": metadata.attribution_level,
            "period": metadata.period,
            "chunk_id": "ranking_total_management",
        }
        return AttributionChunk(str(uuid.uuid4()), "ranking", text, payload)

    def _build_schema_chunk(self, metadata: AttributionMetadata, session_id: str) -> AttributionChunk:
        explanations = {
            "allocation": f"{metadata.attribution_level} allocation effect — impact of over/under-weighting vs benchmark (pp).",
            "selection": "Selection effects — Sector Selection (pp) and Issue Selection (pp).",
            "fx": "FX selection effect — impact of currency positioning (pp).",
            "carry": "Carry/Run Yield effect (pp).",
            "roll": "Roll-down effect (pp).",
            "price": "Price return effect (pp).",
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

    # ============================ Embeddings ============================ #

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
            c.embedding = [float(x) for x in e]
        return chunks

    # ============================== Storage ============================== #

    async def _store_chunks_in_qdrant(self, chunks: List[AttributionChunk], collection_name: str, session_id: str = None):
        if not self.qdrant:
            raise ValueError("Qdrant service not configured")
        if not self.embedding_dim:
            raise ValueError("Embedding dimension unknown; generate embeddings first")

        # Recreate collection with correct vector size
        try:
            self.qdrant.client.recreate_collection(
                collection_name=collection_name,
                vectors_config=http_models.VectorParams(size=self.embedding_dim, distance=http_models.Distance.COSINE)
            )
        except Exception as e:
            logger.warning(f"recreate_collection failed or exists: {e}")
            try:
                self.qdrant.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=http_models.VectorParams(size=self.embedding_dim, distance=http_models.Distance.COSINE)
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
            payload = dict(_json_sanitize(ch.payload) or {})
            if "chunk_id" not in payload:
                payload["chunk_id"] = ch.chunk_id
            points.append(PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload))

        if not points:
            raise ValueError("No valid points to upsert")

        # Primary upsert via client with wait=True; if it fails, use REST
        try:
            self.qdrant.client.upsert(collection_name=collection_name, points=points, wait=True)
        except Exception as e:
            logger.error(f"Qdrant upsert via client failed: {e}")
            try:
                import requests
                rest_points = [{"id": str(p.id), "vector": list(p.vector), "payload": p.payload} for p in points]
                body = {"points": _json_sanitize(rest_points)}
                resp = requests.put(
                    f"http://localhost:6333/collections/{collection_name}/points?wait=true",
                    json=body,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"REST upsert failed: {resp.status_code} {resp.text}")
            except Exception as e2:
                logger.error(f"Qdrant REST upsert failed: {e2}")
                raise

        # Verify count
        try:
            cnt = self.qdrant.client.count(collection_name, exact=True)
            logger.info(f"Stored points in {collection_name}: {cnt.count}")
        except Exception as e:
            logger.warning(f"Count check failed: {e}")

    # ============================= Retrieval ============================= #

    async def answer_question(self, session_id: str, question: str, mode: str = "qa", context: str = None) -> Dict[str, Any]:
        if not self.qdrant or not self.ollama:
            raise ValueError("Services not configured")

        collection_name = f"attr_session_{session_id}"

        # Use provided context (from UI) if present; else search Qdrant
        if context:
            try:
                payloads = json.loads(context)
            except Exception:
                payloads = []
        else:
            if not await self.qdrant.collection_exists(collection_name):
                raise ValueError(f"No attribution data found for session {session_id}")

            # Embed query
            if hasattr(self.ollama, "generate_embedding"):
                query_embedding = await self.ollama.generate_embedding(question)
            else:
                emb_list = await self.ollama.generate_embeddings([question])
                query_embedding = emb_list[0]

            # Filter hints
            filters = self._derive_filters_from_question(question)

            # Search (support both signatures)
            try:
                search_results = self.qdrant.client.search(
                    collection_name=collection_name,
                    query_vector=("", query_embedding),
                    query_filter=filters,
                    limit=24,
                    with_payload=True,
                )
            except (TypeError, Exception):
                try:
                    search_results = self.qdrant.client.search(
                        collection_name=collection_name,
                        query_vector=query_embedding,
                        query_filter=filters,
                        limit=24,
                        with_payload=True,
                    )
                except TypeError:
                    search_results = self.qdrant.client.search(
                        collection_name=collection_name,
                        vector=query_embedding,
                        query_filter=filters,
                        limit=24,
                        with_payload=True,
                    )

            payloads = [r.payload for r in (search_results or [])]

        
        # Summarize payloads → compact facts for fast prompting
        summary = self._summarize_payloads(payloads)
        
        if mode == "commentary":
            return await self._generate_commentary_fast(summary, session_id)
        else:
            return await self._generate_qa_fast(question, summary, session_id)

    def _derive_filters_from_question(self, question: str) -> Optional[Filter]:
        q = question.lower()
        must = []
        if "fx" in q or "currency" in q:
            must.append(FieldCondition(key="has_fx", match=Match(value=True)))
        return Filter(must=must) if must else None

    # ===================== Context Summarization (FAST) ===================== #

    def _summarize_payloads(self, payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract key facts from mixed payloads: totals, rankings, select rows.
        Also applies the Total Management fallback if needed for rankings.
        """
        summary: Dict[str, Any] = {
            "period": "Not reported",
            "portfolio_ror": 0.0,
            "benchmark_ror": 0.0,
            "active_pp": 0.0,
            "effects": {},  # name → value (pp)
            "top_contributors": [],
            "top_detractors": [],
            "total_management":0.0
        }


        # Find totals chunk (prefer type=="total", else use chunk with bucket=="total")
        totals = next((p for p in payloads if p.get("type") == "total"), None)
        if not totals:
            # Fallback: look for a chunk with bucket=="total" (case-insensitive)
            totals = next((p for p in payloads if str(p.get("bucket", "")).strip().lower() == "total"), None)

        

        if totals:
            summary["period"] = totals.get("period", summary["period"])
            # Try both possible key names for total values
            pr = _pct(totals.get("portfolio_total_ror") or totals.get("portfolio_ror"))
            br = _pct(totals.get("benchmark_total_ror") or totals.get("benchmark_ror"))
            ap = _pp(totals.get("active_total_pp") or totals.get("active_ror_pp"))
            if pr is not None: summary["portfolio_ror"] = pr
            if br is not None: summary["benchmark_ror"] = br
            if ap is not None: summary["active_pp"] = ap

            # Effects (pp)
            eff_map = {
                "Allocation": totals.get("allocation_effect_pp"),
                "Selection": totals.get("selection_effect_pp"),
                "FX": totals.get("fx_pp"),
                "Carry": totals.get("carry_pp"),
                "Roll": totals.get("roll_pp"),
                "Price": totals.get("price_pp"),
                "Total Management": totals.get("total_management"),
            }
            for k, v in eff_map.items():
                v = _pp(v)
                if v is not None:
                    summary["effects"][k] = v

        # Rankings chunk (prefer by Total Management)
        ranks = next((p for p in payloads if p.get("type") == "ranking"), None)
        if ranks:
            tcs = ranks.get("top_contributors") or []
            tds = ranks.get("top_detractors") or []
            # Directly assign the full dicts from ranking chunk to summary
            summary["top_contributors"] = [dict(it) for it in tcs]
            summary["top_detractors"]  = [dict(it) for it in tds]

        # If rankings empty → recompute from row payloads
        if not summary["top_contributors"] and not summary["top_detractors"]:
            rows = [p for p in payloads if p.get("type") == "row"]
            if rows:
                # Use total_management for scoring
                def score(row):
                    tm = _pp(row.get("total_management"))
                    if tm is not None:
                        return tm
                    # Fallback: allocation + selection
                    alloc = _pp(row.get("allocation_effect_pp"))
                    sel = _pp(row.get("selection_effect_pp"))
                    if alloc is not None and sel is not None:
                        return alloc + sel
                    return None

                scored = []
                for r in rows:
                    v = score(r)
                    if v is not None:
                        scored.append((r.get("bucket", "Unknown"), v))
                if scored:
                    scored.sort(key=lambda x: x[1], reverse=True)
                    tops = [s for s in scored if s[1] > 0][:3]
                    bots = [s for s in reversed(scored) if s[1] < 0][:3]
                    summary["top_contributors"] = [{"bucket": b, "pp": float(v)} for b, v in tops]
                    summary["top_detractors"]  = [{"bucket": b, "pp": float(v)} for b, v in bots]

        # Guarantee presence of required core fields
        for k in ["portfolio_ror", "benchmark_ror", "active_pp"]:
            if summary.get(k) is None:
                summary[k] = 0.0

        return summary

    # ===================== Fast Generators (LLM prompts) ===================== #

    async def _generate_commentary_fast(self, summary: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        # Validate core facts
        if summary.get("portfolio_ror") is None or summary.get("benchmark_ror") is None:
            return {
                "mode": "commentary",
                "response": "Unable to generate commentary: Not reported in the context.",
                "session_id": session_id,
                "context_used": 0,
                "error": "No valid totals found",
            }

        user_prompt = self._prompt_template_fast(summary)

        
        # system_prompt=self.system_prompt + "\n" + self.developer_prompt,
        response = await self.ollama.generate_response(
            user_prompt,
            system_prompt=self.system_prompt,
            temperature=0.1
        )
        return {
            "mode": "commentary",
            "response": response.get("response", ""),
            "session_id": session_id,
            "context_used": len(json.dumps(summary)),
            "prompt": user_prompt,
            "summary": summary,
        }

    async def _generate_qa_fast(self, question: str, summary: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        system_prompt = (
            "You are a meticulous attribution Q&A assistant.\n"
            "Answer ONLY using the summary facts provided by the system. If the answer is not present, reply: "
            "\"The report does not contain that information.\" Use % for returns and pp for attribution. Be concise."
        )
        facts = json.dumps(summary, ensure_ascii=False)
        user_prompt = f"QUESTION: {question}\nFACTS: {facts}"
        response = await self.ollama.generate_response(user_prompt, system_prompt=system_prompt, temperature=0.0)
        return {
            "mode": "qa",
            "question": question,
            "response": response.get("response", ""),
            "session_id": session_id,
            "context_used": len(facts),
            "prompt": user_prompt,
            "summary": summary,
        }

    # =========================== Session Utilities =========================== #

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

    # =========================== Visualization Generation =========================== #

    async def generate_visualization(
        self, 
        session_id: str, 
        prompt: str, 
        preferred_chart_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate AI-powered visualizations based on attribution data.
        
        Args:
            session_id: The attribution session ID
            prompt: Natural language description of the desired visualization
            preferred_chart_type: Optional preferred chart type
            
        Returns:
            Chart data and metadata for rendering
        """
        if not self.qdrant:
            raise Exception("Qdrant service not configured")
        
        collection_name = f"attr_session_{session_id}"
        
        # Always use demo data for now until real data parsing is fixed
        logger.info(f"Using demo data for visualization in session {session_id}")
        attribution_data = [
            {"name": "Technology", "total": 1.5, "allocation": 0.3, "selection": 1.2},
            {"name": "Healthcare", "total": -0.8, "allocation": -0.2, "selection": -0.6},
            {"name": "Financials", "total": 0.9, "allocation": 0.5, "selection": 0.4},
            {"name": "Energy", "total": -1.2, "allocation": -0.8, "selection": -0.4},
            {"name": "Consumer Discretionary", "total": 0.6, "allocation": 0.1, "selection": 0.5}
        ]
        
        # Skip complex logic for now and just use demo data
        # (This ensures the visualization feature works while we debug data parsing)
        
        # Generate visualization prompt for AI
        system_prompt = self._build_visualization_system_prompt(preferred_chart_type)
        user_prompt = self._build_visualization_user_prompt(prompt, attribution_data)
        
        # Get AI response for chart generation
        response = await self.ollama.generate_response(
            user_prompt, 
            system_prompt=system_prompt, 
            temperature=0.1
        )
        
        # Parse AI response to extract chart specifications
        chart_spec = self._parse_visualization_response(response.get("response", ""))
        
        # Generate actual chart data based on the specification
        chart_data = self._generate_chart_data(attribution_data, chart_spec, prompt)
        
        return {
            "title": chart_spec.get("title", "Attribution Visualization"),
            "type": chart_spec.get("type", "bar"),
            "description": chart_spec.get("description", ""),
            "data": chart_data.get("data"),
            "raw_data": chart_data.get("raw_data"),
            "headers": chart_data.get("headers"),
            "prompt_used": user_prompt
        }
    
    def _parse_attribution_content(self, content: str) -> List[Dict[str, Any]]:
        """Parse attribution content to extract structured data."""
        data = []
        lines = content.split('\n')
        
        # First, try to find any numerical data that looks like attribution
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('='):
                continue
            
            # Extract all numbers from the line (including negative values)
            import re
            numbers = re.findall(r'[-+]?\d*\.?\d+', line)
            
            if not numbers:
                continue
            
            # Look for different attribution data patterns
            data_point = {}
            
            # Pattern 1: "Name: value1, value2, value3" 
            if ':' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    name = parts[0].strip()
                    values_str = parts[1].strip()
                    
                    # Clean up the name (remove common prefixes/suffixes)
                    name = re.sub(r'^(Sector|Country|Asset|Portfolio)', '', name).strip()
                    if name:
                        data_point["name"] = name
                        
                        # Extract numerical values and try to categorize them
                        if len(numbers) >= 1:
                            # If we find keywords, map them appropriately
                            if any(keyword in values_str.lower() for keyword in ['total', 'sum', 'net']):
                                data_point["total"] = float(numbers[0])
                            else:
                                data_point["value"] = float(numbers[0])
                                
                        if len(numbers) >= 2:
                            if 'allocation' in values_str.lower() or 'alloc' in values_str.lower():
                                data_point["allocation"] = float(numbers[1])
                            elif len(numbers) == 2:
                                data_point["allocation"] = float(numbers[0])
                                data_point["selection"] = float(numbers[1])
                                
                        if len(numbers) >= 3:
                            if 'selection' in values_str.lower() or 'stock' in values_str.lower():
                                data_point["selection"] = float(numbers[2])
            
            # Pattern 2: Line with sector/country name and numbers
            elif any(char.isalpha() for char in line) and len(numbers) >= 1:
                # Extract text part (likely sector/country name)
                text_part = re.sub(r'[-+]?\d*\.?\d+', '', line).strip()
                text_part = re.sub(r'[%()pp,\s]+', ' ', text_part).strip()
                
                if text_part and len(text_part) > 1:
                    data_point["name"] = text_part
                    
                    if len(numbers) == 1:
                        data_point["total"] = float(numbers[0])
                    elif len(numbers) == 2:
                        data_point["allocation"] = float(numbers[0])
                        data_point["selection"] = float(numbers[1])
                    elif len(numbers) >= 3:
                        data_point["total"] = float(numbers[0])
                        data_point["allocation"] = float(numbers[1])
                        data_point["selection"] = float(numbers[2])
            
            # Only add if we have a name and at least one numerical value
            if data_point.get("name") and any(k in data_point for k in ["total", "value", "allocation", "selection"]):
                data.append(data_point)
        
        # If we still have no data, create some sample data from any numerical content
        if not data:
            logger.warning("No structured attribution data found, creating sample data")
            # Look for any line with numbers
            for i, line in enumerate(lines[:10]):  # Check first 10 lines
                numbers = re.findall(r'[-+]?\d*\.?\d+', line)
                if numbers:
                    data.append({
                        "name": f"Item {i+1}",
                        "value": float(numbers[0])
                    })
            
            # If still no data, create fallback sample
            if not data:
                data = [
                    {"name": "Sample Data", "value": 1.0},
                    {"name": "Placeholder", "value": 0.5}
                ]
        
        return data
    
    def _summary_to_visualization_data(self, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert summary data to visualization-friendly format."""
        data = []
        
        # Add overall performance metrics
        if summary.get("portfolio_ror") is not None or summary.get("benchmark_ror") is not None:
            data.append({
                "name": "Portfolio Return",
                "value": summary.get("portfolio_ror", 0.0),
                "type": "return"
            })
            data.append({
                "name": "Benchmark Return", 
                "value": summary.get("benchmark_ror", 0.0),
                "type": "return"
            })
            
        if summary.get("active_pp") is not None:
            data.append({
                "name": "Active Return",
                "value": summary.get("active_pp", 0.0),
                "type": "attribution"
            })
        
        # Add effects breakdown
        effects = summary.get("effects", {})
        for effect_name, effect_value in effects.items():
            if effect_value is not None:
                data.append({
                    "name": effect_name.replace("_", " ").title(),
                    "value": effect_value,
                    "type": "effect"
                })
        
        # Add top contributors
        top_contributors = summary.get("top_contributors", [])
        for contrib in top_contributors[:10]:  # Limit to top 10
            if isinstance(contrib, dict) and "bucket" in contrib and "pp" in contrib:
                data.append({
                    "name": contrib["bucket"],
                    "total": contrib["pp"],
                    "type": "contributor"
                })
        
        # Add top detractors
        top_detractors = summary.get("top_detractors", [])
        for detract in top_detractors[:10]:  # Limit to top 10
            if isinstance(detract, dict) and "bucket" in detract and "pp" in detract:
                data.append({
                    "name": detract["bucket"],
                    "total": detract["pp"],
                    "type": "detractor"
                })
        
        # If we have specific row data, add that too
        rows = summary.get("rows", [])
        for row in rows[:20]:  # Limit to 20 rows
            if isinstance(row, dict):
                name = row.get("bucket") or row.get("name") or "Unknown"
                row_data = {"name": name}
                
                # Add all numerical fields from the row
                for key, value in row.items():
                    if key != "bucket" and key != "name" and isinstance(value, (int, float)):
                        row_data[key] = value
                
                if len(row_data) > 1:  # Only add if we have data beyond just the name
                    row_data["type"] = "row_data"
                    data.append(row_data)
        
        # If no data was found, create some basic data from the summary
        if not data:
            logger.warning("No visualization data extracted from summary, creating basic metrics")
            if summary:
                for key, value in summary.items():
                    if isinstance(value, (int, float)) and key not in ["portfolio_ror", "benchmark_ror"]:
                        data.append({
                            "name": key.replace("_", " ").title(),
                            "value": value,
                            "type": "metric"
                        })
        
        return data
    
    def _build_visualization_system_prompt(self, preferred_chart_type: Optional[str]) -> str:
        """Build system prompt for visualization generation."""
        base_prompt = """You are a data visualization expert specializing in performance attribution analysis.
        
Your task is to analyze attribution data and provide chart specifications in JSON format.

Respond with a JSON object containing:
- "title": A descriptive title for the chart
- "type": Chart type (bar, line, pie, scatter, table)
- "description": Brief analysis of what the chart shows
- "fields": Array of field names to use for the visualization
- "sort_by": Field to sort by (optional)
- "sort_order": "asc" or "desc" (optional)

Available chart types:
- bar: Best for comparing categories (sectors, countries)
- line: Best for trends over time
- pie: Best for showing proportions/composition
- scatter: Best for showing relationships between two variables
- table: Best for detailed data listing"""
        
        if preferred_chart_type:
            base_prompt += f"\n\nUser prefers {preferred_chart_type} chart type. Use this unless clearly inappropriate."
        
        return base_prompt
    
    def _build_visualization_user_prompt(self, prompt: str, attribution_data: List[Dict[str, Any]]) -> str:
        """Build user prompt with attribution data."""
        # Summarize available data
        sample_data = attribution_data[:5] if attribution_data else []
        available_fields = set()
        for item in attribution_data:
            available_fields.update(item.keys())
        
        return f"""User request: {prompt}

Available attribution data fields: {list(available_fields)}

Sample data (first 5 items):
{json.dumps(sample_data, indent=2)}

Total items available: {len(attribution_data)}

Please provide chart specifications in JSON format."""
    
    def _parse_visualization_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response to extract chart specifications."""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
        except Exception:
            pass
        
        # Fallback to default specification
        return {
            "title": "Attribution Analysis",
            "type": "bar",
            "description": "Performance attribution breakdown",
            "fields": ["name", "total"],
            "sort_by": "total",
            "sort_order": "desc"
        }
    
    def _generate_chart_data(
        self, 
        attribution_data: List[Dict[str, Any]], 
        chart_spec: Dict[str, Any], 
        original_prompt: str
    ) -> Dict[str, Any]:
        """Generate actual chart data based on specifications."""
        
        # Filter and prepare data
        filtered_data = []
        suggested_fields = chart_spec.get("fields", ["name", "total"])
        
        # Find available fields in the data
        available_fields = set()
        for item in attribution_data:
            available_fields.update(item.keys())
        
        # Use suggested fields if they exist, otherwise use available ones
        fields = []
        for field in suggested_fields:
            if field in available_fields:
                fields.append(field)
        
        # If no suggested fields are available, use what we have
        if not fields:
            fields = ["name"]  # Always include name
            # Add the first numerical field we find
            for field in available_fields:
                if field != "name" and any(isinstance(item.get(field), (int, float)) for item in attribution_data):
                    fields.append(field)
                    break
        
        for item in attribution_data:
            row = {}
            for field in fields:
                if field in item:
                    row[field] = item[field]
            # Always include name even if not in fields
            if "name" not in row and "name" in item:
                row["name"] = item["name"]
            if row:
                filtered_data.append(row)
        
        # Sort data if specified
        sort_by = chart_spec.get("sort_by")
        sort_order = chart_spec.get("sort_order", "desc")
        
        if sort_by and sort_by in fields:
            reverse = (sort_order == "desc")
            filtered_data.sort(
                key=lambda x: x.get(sort_by, 0) if isinstance(x.get(sort_by), (int, float)) else 0,
                reverse=reverse
            )
        
        # Limit to top 20 items for readability
        filtered_data = filtered_data[:20]
        
        # Prepare headers and raw data
        headers = fields
        raw_data = []
        for item in filtered_data:
            row = [item.get(field, "") for field in headers]
            raw_data.append(row)
        
        # Create chart-specific data structure
        chart_data = {
            "labels": [item.get("name", "") for item in filtered_data],
            "datasets": []
        }
        
        # Add datasets based on fields
        for field in fields:
            if field != "name":
                dataset = {
                    "label": field.title(),
                    "data": [item.get(field, 0) for item in filtered_data]
                }
                chart_data["datasets"].append(dataset)
        
        return {
            "data": chart_data,
            "raw_data": raw_data,
            "headers": headers
        }
