from typing import Dict, Any, List, Optional, Tuple, Union
import re
import logging
import pandas as pd
import numpy as np
import uuid
import asyncio
from datetime import datetime
from dataclasses import dataclass

from qdrant_client.models import PointStruct, Filter, FieldCondition, Match

logger = logging.getLogger(__name__)

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
    """Base class for attribution chunks"""
    chunk_id: str
    chunk_type: str  # "row", "total", "ranking", "schema"
    text: str  # Text to embed
    payload: Dict[str, Any]  # Qdrant payload
    embedding: Optional[List[float]] = None


class PerformanceAttributionService:
    """
    Specialized service for processing performance attribution documents and generating
    professional commentary using the institutional buy-side framework.
    """
    
    def __init__(self, ollama_service=None, qdrant_service=None):
        # Original prompts for compatibility
        self.ollama = ollama_service
        self.qdrant = qdrant_service
        self.embedding_model = "nomic-embed-text"
        self.system_prompt = """You are a buy-side performance attribution commentator for an institutional portfolio.
Your audience is portfolio managers and senior analysts.
Write concise, evidence-based commentary grounded ONLY in the provided table and derived stats.
Quantify all statements using percentage points (pp) for attribution and % for returns.
Break down performance into allocation (sector or country), security/issue selection, FX selection (if provided), and any other effects present in the data.
Do not invent data or macro narrative beyond what is in the context.
Tone: crisp, professional, and meaningful to experienced PMs.

Output structure (markdown):
1) Executive Summary (3–4 sentences)
2) Total Performance Drivers"""
        self.developer_prompt = """- Only use numbers given in the user prompt.
- Identify drivers explicitly as allocation, selection, FX, or other effects present.
- Rank top contributors/detractors strictly by Total Attribution (pp).
- Limit Executive Summary to 3–4 sentences; avoid filler.
- Do not add securities, macro factors, or assumptions not in context.
- Use one decimal place for pp values and retain +/- signs."""
        self.last_chunks = []

    def get_unified_prompt_template(self, 
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
                                  top_detractors: List[Dict[str, Any]]) -> str:
        """
        Generate the unified prompt template for performance attribution analysis.
        """
        
        # Format effects breakdown
        effects_breakdown_text = ""
        for effect, value in effects_breakdown.items():
            sign = "+" if value >= 0 else ""
            effects_breakdown_text += f"- {effect}: {sign}{value:.1f} pp\n"
        
        # Format top contributors
        contributors_text = ""
        for i, contributor in enumerate(top_contributors[:3], 1):
            contributors_text += f"{i}. {contributor['name']} ({contributor['attribution']:+.1f} pp)\n"
        
        # Format top detractors
        detractors_text = ""
        for i, detractor in enumerate(top_detractors[:2], 1):
            detractors_text += f"{i}. {detractor['name']} ({detractor['attribution']:+.1f} pp)\n"
        
        # Build the unified prompt
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
{effects_breakdown_text.strip()}
# Examples of effect names your data might include (use only those present):
# - Country/Allocation (pp)
# - Sector/Allocation (pp)
# - Issue/Security Selection (pp)
# - FX Selection (pp)
# - Run Yield / Carry (pp)
# - Roll Down (pp)
# - Price Return (pp)
# - Residual / Interaction / Total Management (pp)

Top 3 Contributors by Total Attribution (pp):
{contributors_text.strip()}

Top 2 Detractors by Total Attribution (pp):
{detractors_text.strip()}

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
<Optional, only if the data signals concentration, FX sensitivity, rate duration, or other notable patterns.>

Constraints:
- Use one decimal place for pp values and retain +/- signs.
- Cite only numbers present in the context (or simple arithmetic already shown).
- If an effect column (e.g., FX) is not present, do not mention it."""

        return prompt

    def extract_attribution_data_from_tables(self, tables: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Extract performance attribution data from Excel tables.
        Look for common attribution table structures.
        """
        attribution_data = None
        
        for table in tables:
            if not table.get('data'):
                continue
            
            # Look for attribution-specific columns
            first_row = table['data'][0] if table['data'] else {}
            column_names = [str(k).lower() for k in first_row.keys()]
            
            # Check if this looks like a performance attribution table
            attribution_indicators = [
                'attribution', 'allocation', 'selection', 'contribution',
                'active', 'portfolio', 'benchmark', 'return'
            ]
            
            if any(indicator in ' '.join(column_names) for indicator in attribution_indicators):
                logger.info(f"Found potential attribution table with columns: {list(first_row.keys())}")
                
                # Extract the data
                attribution_data = {
                    'table_data': table['data'],
                    'columns': list(first_row.keys()),
                    'sheet_name': table.get('sheet_name', 'Unknown'),
                    'shape': table.get('shape', [0, 0])
                }
                break
        
        return attribution_data

    def parse_attribution_table(self, attribution_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse attribution table data and extract key metrics.
        """
        if not attribution_data:
            return None
        
        try:
            table_data = attribution_data['table_data']
            columns = attribution_data['columns']
            
            # Initialize results
            results = {
                'period_name': 'Q2 2025',  # Default, could be extracted from filename
                'asset_class': 'Mixed',    # Could be inferred from data
                'attribution_level': 'Sector',  # Default
                'portfolio_total_return': 0.0,
                'benchmark_total_return': 0.0,
                'total_active_return': 0.0,
                'effects_breakdown': {},
                'top_contributors': [],
                'top_detractors': [],
                'tabular_data': self._format_table_for_display(table_data, columns)
            }
            
            # Try to extract total returns if present
            for row in table_data:
                for col_name, value in row.items():
                    if isinstance(value, str):
                        # Look for total portfolio/benchmark returns
                        value_str = value.lower()
                        if 'portfolio total' in value_str or 'total portfolio' in value_str:
                            # Try to extract number from next columns or same row
                            results['portfolio_total_return'] = self._extract_return_value(row, col_name)
                        elif 'benchmark total' in value_str or 'total benchmark' in value_str:
                            results['benchmark_total_return'] = self._extract_return_value(row, col_name)
            
            # Calculate active return
            results['total_active_return'] = results['portfolio_total_return'] - results['benchmark_total_return']
            
            # Extract attribution effects and rankings
            attribution_rows = []
            for row in table_data:
                # Skip header/summary rows
                if self._is_data_row(row):
                    attribution_rows.append(row)
            
            # Sort by total attribution if available
            total_attr_column = self._find_total_attribution_column(columns)
            if total_attr_column and attribution_rows:
                try:
                    sorted_rows = sorted(
                        attribution_rows,
                        key=lambda r: self._safe_float_conversion(r.get(total_attr_column, 0)),
                        reverse=True
                    )
                    
                    # Extract top contributors and detractors
                    for row in sorted_rows[:3]:
                        attr_value = self._safe_float_conversion(row.get(total_attr_column, 0))
                        if attr_value > 0:
                            results['top_contributors'].append({
                                'name': self._get_security_name(row),
                                'attribution': attr_value,
                                'details': row
                            })
                    
                    for row in reversed(sorted_rows[-2:]):
                        attr_value = self._safe_float_conversion(row.get(total_attr_column, 0))
                        if attr_value < 0:
                            results['top_detractors'].append({
                                'name': self._get_security_name(row),
                                'attribution': attr_value,
                                'details': row
                            })
                except Exception as e:
                    logger.warning(f"Error sorting attribution data: {e}")
            
            # Extract effects breakdown
            effects = ['Allocation', 'Selection', 'FX Selection', 'Total Attribution']
            for effect in effects:
                effect_column = self._find_column_containing(columns, effect.lower())
                if effect_column:
                    total_effect = sum(
                        self._safe_float_conversion(row.get(effect_column, 0)) 
                        for row in attribution_rows
                    )
                    results['effects_breakdown'][effect] = total_effect
            
            return results
            
        except Exception as e:
            logger.error(f"Error parsing attribution table: {e}")
            return None

    def _format_table_for_display(self, table_data: List[Dict], columns: List[str]) -> str:
        """Format table data for display in the prompt."""
        if not table_data:
            return "No data available"
        
        # Create table header
        header = " | ".join(columns)
        separator = " | ".join(["-" * len(col) for col in columns])
        
        # Add data rows
        rows = []
        for row_data in table_data[:10]:  # Limit to first 10 rows
            row = " | ".join([str(row_data.get(col, "")) for col in columns])
            rows.append(row)
        
        return f"{header}\n{separator}\n" + "\n".join(rows)

    def _extract_return_value(self, row: Dict, current_col: str) -> float:
        """Extract return value from row, looking in adjacent columns."""
        # Look for numeric values in the same row
        for col_name, value in row.items():
            if col_name != current_col:
                numeric_value = self._safe_float_conversion(value)
                if numeric_value != 0:
                    return numeric_value
        return 0.0

    def _is_data_row(self, row: Dict) -> bool:
        """Check if row contains actual security/sector data vs headers/totals."""
        # Simple heuristic: if first column looks like a security/sector name
        first_value = str(list(row.values())[0]).lower()
        skip_indicators = ['total', 'portfolio', 'benchmark', 'breakdown', 'summary']
        return not any(indicator in first_value for indicator in skip_indicators)

    def _find_total_attribution_column(self, columns: List[str]) -> Optional[str]:
        """Find the column that contains total attribution values."""
        for col in columns:
            col_lower = col.lower()
            if 'total attribution' in col_lower or 'total' in col_lower and 'pp' in col_lower:
                return col
        return None

    def _find_column_containing(self, columns: List[str], search_term: str) -> Optional[str]:
        """Find column name containing the search term."""
        for col in columns:
            if search_term in col.lower():
                return col
        return None

    def _get_security_name(self, row: Dict) -> str:
        """Extract security/sector name from row (typically first column)."""
        if not row:
            return "Unknown"
        return str(list(row.values())[0])

    def _safe_float_conversion(self, value: Any) -> float:
        """Safely convert value to float, handling strings with % and other formats."""
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove common formatting
            cleaned = re.sub(r'[%,\$]', '', value.strip())
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        
        return 0.0

    async def generate_commentary(self, attribution_data: Dict[str, Any], ollama_service) -> str:
        """
        Generate performance attribution commentary using the parsed data and LLM.
        """
        try:
            # Create the full prompt
            prompt = self.get_unified_prompt_template(
                period_name=attribution_data.get('period_name', 'Q2 2025'),
                asset_class=attribution_data.get('asset_class', 'Mixed'),
                attribution_level=attribution_data.get('attribution_level', 'Sector'),
                tabular_data=attribution_data.get('tabular_data', ''),
                columns_present=list(attribution_data.get('effects_breakdown', {}).keys()),
                portfolio_total_return=attribution_data.get('portfolio_total_return', 0.0),
                benchmark_total_return=attribution_data.get('benchmark_total_return', 0.0),
                total_active_return=attribution_data.get('total_active_return', 0.0),
                effects_breakdown=attribution_data.get('effects_breakdown', {}),
                top_contributors=attribution_data.get('top_contributors', []),
                top_detractors=attribution_data.get('top_detractors', [])
            )
            
            # Generate commentary using the LLM
            full_prompt = f"{self.system_prompt}\n\n{self.developer_prompt}\n\n{prompt}"
            
            # Use the LLM to generate the commentary
            commentary = await ollama_service.generate_text(full_prompt)
            
            return commentary
            
        except Exception as e:
            logger.error(f"Error generating commentary: {e}")
            return f"Error generating performance attribution commentary: {str(e)}"

    def enhance_document_metadata(self, metadata: Dict[str, Any], attribution_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance document metadata with performance attribution specific information.
        """
        if attribution_data:
            metadata['performance_attribution'] = {
                'period': attribution_data.get('period_name'),
                'asset_class': attribution_data.get('asset_class'),
                'attribution_level': attribution_data.get('attribution_level'),
                'portfolio_return': attribution_data.get('portfolio_total_return'),
                'benchmark_return': attribution_data.get('benchmark_total_return'),
                'active_return': attribution_data.get('total_active_return'),
                'top_contributors_count': len(attribution_data.get('top_contributors', [])),
                'top_detractors_count': len(attribution_data.get('top_detractors', [])),
                'effects_present': list(attribution_data.get('effects_breakdown', {}).keys())
            }
        
        return metadata
    
    async def process_attribution_file(self, file_path: str, session_id: str) -> Dict[str, Any]:
        """
        Main entry point: parse Excel file and build attribution RAG collection.
        
        Returns:
            Dict with processing results including chunk count and metadata
        """
        try:
            # Step 1: Parse and normalize DataFrame
            df, metadata = await self._parse_and_normalize_excel(file_path)
            # Step 2: Build chunks
            chunks = await self._build_chunks(df, metadata, session_id)
            self.last_chunks = chunks
            # Step 3: Generate embeddings
            chunks_with_embeddings = await self._generate_embeddings(chunks)
            # Step 4: Store in Qdrant
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
                        "bucket": chunk.payload.get("bucket", "Unknown"),
                        "text": chunk.text,
                        "asset_class": chunk.payload.get("asset_class", "unknown"),
                        "chunk_type": chunk.chunk_type
                    }
                    for chunk in chunks
                ]
            }
            
        except Exception as e:
            logger.error(f"Error processing attribution file: {e}")
            raise

    async def _parse_and_normalize_excel(self, file_path: str) -> Tuple[pd.DataFrame, AttributionMetadata]:
        """Step 1: Parse Excel and detect asset class/attribution level"""
        
        # Read Excel file
        excel_file = pd.ExcelFile(file_path)
        
        # Try different sheet names for attribution data
        sheet_candidates = ["Attribution", "Performance", "Summary", excel_file.sheet_names[0]]
        df = None
        
        for sheet_name in sheet_candidates:
            if sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                break
        
        if df is None:
            raise ValueError("No suitable attribution sheet found")
        
        # Detect asset class and attribution level
        columns_lower = [str(col).lower() for col in df.columns]
        columns_str = " ".join(columns_lower)
        
        # Asset class detection
        if any(term in columns_str for term in ["gics", "sector", "industry"]):
            asset_class = "Equity"
            attribution_level = "Sector"
            bucket_column_patterns = ["sector", "gics", "industry"]
        elif any(term in columns_str for term in ["country", "region", "currency"]):
            asset_class = "Fixed Income"
            attribution_level = "Country"
            bucket_column_patterns = ["country", "region"]
        else:
            # Default assumption
            asset_class = "Equity"
            attribution_level = "Sector"
            bucket_column_patterns = ["sector"]
        
        # Canonicalize column names (lower snake case)
        df_clean = df.copy()
        df_clean.columns = [self._canonicalize_column_name(col) for col in df.columns]
        
        # Identify bucket column (sector/country)
        bucket_col = None
        for pattern in bucket_column_patterns:
            candidates = [col for col in df_clean.columns if pattern in col]
            if candidates:
                bucket_col = candidates[0]
                break
        
        if bucket_col is None:
            # Use first string column
            for col in df_clean.columns:
                if df_clean[col].dtype == 'object':
                    bucket_col = col
                    break
        
        if bucket_col is None:
            raise ValueError("Could not identify bucket column (sector/country)")
        
        # Remove rows with empty bucket values
        df_clean = df_clean.dropna(subset=[bucket_col])
        
        # Identify effects columns and flags
        effects_map = {
            'allocation': ['allocation', 'alloc'],
            'selection': ['selection', 'select', 'security_selection'],
            'fx': ['fx', 'currency', 'foreign_exchange'],
            'carry': ['carry', 'yield'],
            'roll': ['roll', 'rolldown'],
            'price': ['price', 'price_return']
        }
        
        effect_columns = {}
        flags = {}
        
        for effect_name, patterns in effects_map.items():
            found_col = None
            for pattern in patterns:
                candidates = [col for col in df_clean.columns if pattern in col and ('pp' in col or 'contribution' in col)]
                if candidates:
                    found_col = candidates[0]
                    break
            
            effect_columns[effect_name] = found_col
            flags[f'has_{effect_name}'] = found_col is not None
        
        # Coerce numeric columns
        numeric_cols = [col for col in df_clean.columns if col != bucket_col]
        for col in numeric_cols:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
        
        # Compute derived columns
        portfolio_col = self._find_column(df_clean.columns, ['portfolio_ror', 'portfolio_return', 'port_ret'])
        benchmark_col = self._find_column(df_clean.columns, ['benchmark_ror', 'benchmark_return', 'bench_ret'])
        
        if portfolio_col and benchmark_col:
            df_clean['active_ror_pp'] = df_clean[portfolio_col] - df_clean[benchmark_col]
        
        # Compute total attribution
        available_effects = [col for col in effect_columns.values() if col is not None]
        if available_effects:
            df_clean['total_attr_pp'] = df_clean[available_effects].sum(axis=1, skipna=True)
        
        # Extract period from filename or use default
        period = self._extract_period_from_filename(file_path)
        
        # Create metadata
        metadata = AttributionMetadata(
            period=period,
            asset_class=asset_class,
            attribution_level=attribution_level,
            columns_present=list(df_clean.columns),
            has_fx=flags.get('has_fx', False),
            has_carry=flags.get('has_carry', False),
            has_roll=flags.get('has_roll', False),
            has_price=flags.get('has_price', False),
            total_rows=len(df_clean)
        )
        
        return df_clean, metadata

    def _canonicalize_column_name(self, col: str) -> str:
        """Convert column name to lower snake case"""
        # Convert to string and lowercase
        col_str = str(col).lower()
        # Replace spaces and special chars with underscores
        col_str = re.sub(r'[^\w]', '_', col_str)
        # Remove multiple underscores
        col_str = re.sub(r'_+', '_', col_str).strip('_')
        return col_str

    def _find_column(self, columns: List[str], patterns: List[str]) -> Optional[str]:
        """Find column matching any of the patterns"""
        for pattern in patterns:
            candidates = [col for col in columns if pattern in col]
            if candidates:
                return candidates[0]
        return None

    def _extract_period_from_filename(self, file_path: str) -> str:
        """Extract period from filename"""
        filename = file_path.split('\\')[-1].split('/')[-1]
        
        # Look for Q# YYYY pattern
        quarter_match = re.search(r'Q(\d)\s*(\d{4})', filename, re.IGNORECASE)
        if quarter_match:
            return f"Q{quarter_match.group(1)} {quarter_match.group(2)}"
        
        # Look for year
        year_match = re.search(r'(\d{4})', filename)
        if year_match:
            return f"Q2 {year_match.group(1)}"
        
        return "Q2 2025"  # Default

    async def _build_chunks(self, df: pd.DataFrame, metadata: AttributionMetadata, session_id: str) -> List[AttributionChunk]:
        """Step 2: Build row, totals, rankings, and schema chunks"""
        
        chunks = []
        bucket_col = self._find_bucket_column(df, metadata)
        logger.info(f"Building chunks for {len(df)} rows using bucket column: {bucket_col}")
        
        # A) Row chunks (one per sector/country)
        for idx, row in df.iterrows():
            chunk = self._build_row_chunk(row, metadata, bucket_col, session_id)
            chunks.append(chunk)
            logger.debug(f"Built row chunk: {chunk.chunk_id}, text length: {len(chunk.text)}")
        
        # B) Totals chunk
        totals_chunk = self._build_totals_chunk(df, metadata, session_id)
        chunks.append(totals_chunk)
        logger.debug(f"Built totals chunk: {totals_chunk.chunk_id}, text length: {len(totals_chunk.text)}")
        
        # C) Rankings chunk
        rankings_chunk = self._build_rankings_chunk(df, metadata, bucket_col, session_id)
        chunks.append(rankings_chunk)
        logger.debug(f"Built rankings chunk: {rankings_chunk.chunk_id}, text length: {len(rankings_chunk.text)}")
        
        # D) Schema/Glossary chunk (optional)
        schema_chunk = self._build_schema_chunk(metadata, session_id)
        chunks.append(schema_chunk)
        logger.debug(f"Built schema chunk: {schema_chunk.chunk_id}, text length: {len(schema_chunk.text)}")
        
        logger.info(f"Built {len(chunks)} total chunks")
        return chunks

    def _find_bucket_column(self, df: pd.DataFrame, metadata: AttributionMetadata) -> str:
        """Find the column containing sector/country names"""
        if metadata.attribution_level == "Sector":
            patterns = ["sector", "gics", "industry"]
        else:
            patterns = ["country", "region"]
        
        for pattern in patterns:
            candidates = [col for col in df.columns if pattern in col]
            if candidates:
                return candidates[0]
        
        # Fallback to first object column
        for col in df.columns:
            if df[col].dtype == 'object':
                return col
        
        return df.columns[0]

    def _build_row_chunk(self, row: pd.Series, metadata: AttributionMetadata, bucket_col: str, session_id: str) -> AttributionChunk:
        """Build a row chunk for a single sector/country"""
        
        bucket_name = str(row[bucket_col])
        
        # Extract key metrics
        portfolio_ror = self._safe_get_numeric(row, ['portfolio_ror', 'portfolio_return'])
        benchmark_ror = self._safe_get_numeric(row, ['benchmark_ror', 'benchmark_return'])
        active_ror_pp = self._safe_get_numeric(row, ['active_ror_pp']) or (portfolio_ror - benchmark_ror if portfolio_ror and benchmark_ror else None)
        
        allocation_pp = self._safe_get_numeric(row, ['allocation', 'allocation_pp'])
        selection_pp = self._safe_get_numeric(row, ['selection', 'selection_pp'])
        fx_pp = self._safe_get_numeric(row, ['fx', 'fx_pp']) if metadata.has_fx else None
        carry_pp = self._safe_get_numeric(row, ['carry', 'carry_pp']) if metadata.has_carry else None
        roll_pp = self._safe_get_numeric(row, ['roll', 'roll_pp']) if metadata.has_roll else None
        price_pp = self._safe_get_numeric(row, ['price', 'price_pp']) if metadata.has_price else None
        
        total_attr_pp = self._safe_get_numeric(row, ['total_attr_pp', 'total_attribution'])
        
        portfolio_wt = self._safe_get_numeric(row, ['portfolio_wt', 'port_weight'])
        benchmark_wt = self._safe_get_numeric(row, ['benchmark_wt', 'bench_weight'])
        rel_wt_pp = (portfolio_wt - benchmark_wt) if portfolio_wt and benchmark_wt else None
        
        # Build text for embedding
        text_parts = [
            f"{metadata.period} • {metadata.attribution_level} row: {bucket_name}"
        ]
        
        if portfolio_ror is not None and benchmark_ror is not None:
            text_parts.append(f"Portfolio ROR: {portfolio_ror:.1f}% | Benchmark ROR: {benchmark_ror:.1f}%")
            if active_ror_pp is not None:
                text_parts.append(f"Active ROR: {active_ror_pp:+.1f} pp")
        
        # Attribution effects
        effects_text = []
        if allocation_pp is not None:
            effects_text.append(f"Allocation {allocation_pp:+.1f}")
        if selection_pp is not None:
            effects_text.append(f"Selection {selection_pp:+.1f}")
        if fx_pp is not None:
            effects_text.append(f"FX {fx_pp:+.1f}")
        if carry_pp is not None:
            effects_text.append(f"Carry {carry_pp:+.1f}")
        if roll_pp is not None:
            effects_text.append(f"Roll {roll_pp:+.1f}")
        if price_pp is not None:
            effects_text.append(f"Price {price_pp:+.1f}")
        
        if effects_text:
            text_parts.append(f"Attribution effects (pp): {', '.join(effects_text)}")
        
        if total_attr_pp is not None:
            text_parts.append(f"Total Attribution: {total_attr_pp:+.1f} pp")
        
        if portfolio_wt is not None and benchmark_wt is not None:
            text_parts.append(f"Weights: Portfolio {portfolio_wt:.1f}%, Benchmark {benchmark_wt:.1f}%")
            if rel_wt_pp is not None:
                text_parts.append(f"(Rel {rel_wt_pp:+.1f} pp)")
        
        text = " | ".join(text_parts)
        
        # Build payload
        payload = {
            "type": "row",
            "session_id": session_id,
            "asset_class": metadata.asset_class,
            "level": metadata.attribution_level,
            "bucket": bucket_name,
            "period": metadata.period,
            "columns_present": metadata.columns_present,
            "portfolio_ror": portfolio_ror,
            "benchmark_ror": benchmark_ror,
            "active_ror_pp": active_ror_pp,
            "allocation_pp": allocation_pp,
            "selection_pp": selection_pp,
            "fx_pp": fx_pp,
            "carry_pp": carry_pp,
            "roll_pp": roll_pp,
            "price_pp": price_pp,
            "total_attr_pp": total_attr_pp,
            "portfolio_wt": portfolio_wt,
            "benchmark_wt": benchmark_wt,
            "rel_wt_pp": rel_wt_pp,
            "has_fx": metadata.has_fx,
            "has_carry": metadata.has_carry,
            "has_roll": metadata.has_roll,
            "has_price": metadata.has_price
        }
        
        chunk_id = f"row_{bucket_name.replace(' ', '_').replace('/', '_').replace('-', '_')}"
        return AttributionChunk(chunk_id, "row", text, payload)

    def _build_totals_chunk(self, df: pd.DataFrame, metadata: AttributionMetadata, session_id: str) -> AttributionChunk:
        """Build totals summary chunk"""
        
        # Sum up totals
        portfolio_total = df.filter(regex='portfolio.*ror|portfolio.*return').sum(axis=1).sum()
        benchmark_total = df.filter(regex='benchmark.*ror|benchmark.*return').sum(axis=1).sum()
        active_pp = portfolio_total - benchmark_total
        
        allocation_total = df.filter(regex='allocation').sum(axis=1).sum() if 'allocation' in str(df.columns) else None
        selection_total = df.filter(regex='selection').sum(axis=1).sum() if 'selection' in str(df.columns) else None
        fx_total = df.filter(regex='fx').sum(axis=1).sum() if metadata.has_fx else None
        carry_total = df.filter(regex='carry').sum(axis=1).sum() if metadata.has_carry else None
        roll_total = df.filter(regex='roll').sum(axis=1).sum() if metadata.has_roll else None
        price_total = df.filter(regex='price').sum(axis=1).sum() if metadata.has_price else None
        
        # Build text
        text_parts = [
            f"{metadata.period} • TOTAL",
            f"Portfolio {portfolio_total:.1f}% vs Benchmark {benchmark_total:.1f}% → Active {active_pp:+.1f} pp"
        ]
        
        breakdown_parts = []
        if allocation_total is not None:
            breakdown_parts.append(f"Allocation {allocation_total:+.1f}")
        if selection_total is not None:
            breakdown_parts.append(f"Selection {selection_total:+.1f}")
        if fx_total is not None:
            breakdown_parts.append(f"FX {fx_total:+.1f}")
        if carry_total is not None:
            breakdown_parts.append(f"Carry {carry_total:+.1f}")
        if roll_total is not None:
            breakdown_parts.append(f"Roll {roll_total:+.1f}")
        if price_total is not None:
            breakdown_parts.append(f"Price {price_total:+.1f}")
        
        if breakdown_parts:
            text_parts.append(f"Attribution breakdown (pp): {', '.join(breakdown_parts)}")
        
        text = "\n".join(text_parts)
        
        payload = {
            "type": "total",
            "session_id": session_id,
            "period": metadata.period,
            "asset_class": metadata.asset_class,
            "level": metadata.attribution_level,
            "portfolio_total": portfolio_total,
            "benchmark_total": benchmark_total,
            "active_pp": active_pp,
            "allocation_pp": allocation_total,
            "selection_pp": selection_total,
            "fx_pp": fx_total,
            "carry_pp": carry_total,
            "roll_pp": roll_total,
            "price_pp": price_total
        }
        
        return AttributionChunk("total_summary", "total", text, payload)

    def _build_rankings_chunk(self, df: pd.DataFrame, metadata: AttributionMetadata, bucket_col: str, session_id: str) -> AttributionChunk:
        """Build rankings chunk with top contributors/detractors"""
        
        # Find total attribution column
        total_attr_col = self._find_column(df.columns, ['total_attr_pp', 'total_attribution'])
        
        if total_attr_col is None:
            # No rankings possible
            text = f"{metadata.period} • Rankings: No total attribution data available"
            payload = {"type": "ranking", "session_id": session_id, "rank_key": None}
            return AttributionChunk("ranking_no_data", "ranking", text, payload)
        
        # Sort by total attribution
        df_sorted = df.sort_values(total_attr_col, ascending=False)
        
        # Top contributors (positive)
        top_contributors = []
        for _, row in df_sorted.head(3).iterrows():
            attr_val = row[total_attr_col]
            if pd.notna(attr_val) and attr_val > 0:
                top_contributors.append({
                    "bucket": str(row[bucket_col]),
                    "pp": float(attr_val)
                })
        
        # Top detractors (negative)
        top_detractors = []
        for _, row in df_sorted.tail(3).iterrows():
            attr_val = row[total_attr_col]
            if pd.notna(attr_val) and attr_val < 0:
                top_detractors.append({
                    "bucket": str(row[bucket_col]),
                    "pp": float(attr_val)
                })
        
        # Build text
        text_parts = [f"{metadata.period} • Rankings by Total Attribution (pp)"]
        
        if top_contributors:
            contrib_text = ", ".join([f"{item['bucket']} {item['pp']:+.1f}" for item in top_contributors])
            text_parts.append(f"Top: {contrib_text}")
        
        if top_detractors:
            detract_text = ", ".join([f"{item['bucket']} {item['pp']:+.1f}" for item in top_detractors])
            text_parts.append(f"Bottom: {detract_text}")
        
        text = "\n".join(text_parts)
        
        payload = {
            "type": "ranking",
            "session_id": session_id,
            "rank_key": "total_attr_pp",
            "top_contributors": top_contributors,
            "top_detractors": top_detractors
        }
        
        return AttributionChunk("ranking_total_attr_pp", "ranking", text, payload)

    def _build_schema_chunk(self, metadata: AttributionMetadata, session_id: str) -> AttributionChunk:
        """Build schema/glossary chunk explaining effects"""
        
        explanations = {
            "allocation": f"{metadata.attribution_level} allocation effect - impact of over/under-weighting relative to benchmark",
            "selection": "Security/issue selection effect - impact of choosing specific securities within each category",
            "fx": "Foreign exchange selection effect - impact of currency positioning decisions",
            "carry": "Carry/yield effect - impact of yield income and carry positioning",
            "roll": "Roll down effect - impact of yield curve positioning and time decay",
            "price": "Price return effect - impact of credit spread and price movements"
        }
        
        present_effects = []
        if metadata.has_fx:
            present_effects.append(explanations["fx"])
        if metadata.has_carry:
            present_effects.append(explanations["carry"])
        if metadata.has_roll:
            present_effects.append(explanations["roll"])
        if metadata.has_price:
            present_effects.append(explanations["price"])
        
        # Always include allocation and selection
        present_effects.insert(0, explanations["allocation"])
        present_effects.insert(1, explanations["selection"])
        
        text_parts = [
            f"{metadata.period} • Attribution Effects Glossary",
            f"Asset Class: {metadata.asset_class}",
            f"Attribution Level: {metadata.attribution_level}",
            "",
            "Effects in this analysis:"
        ]
        
        for effect in present_effects:
            text_parts.append(f"• {effect}")
        
        text = "\n".join(text_parts)
        
        payload = {
            "type": "schema",
            "session_id": session_id,
            "columns_present": metadata.columns_present,
            "asset_class": metadata.asset_class,
            "attribution_level": metadata.attribution_level,
            "effects_present": {
                "allocation": True,
                "selection": True,
                "fx": metadata.has_fx,
                "carry": metadata.has_carry,
                "roll": metadata.has_roll,
                "price": metadata.has_price
            }
        }
        
        return AttributionChunk("schema_glossary", "schema", text, payload)

    def _safe_get_numeric(self, row: pd.Series, patterns: List[str]) -> Optional[float]:
        """Safely get numeric value from row using column patterns"""
        for pattern in patterns:
            for col in row.index:
                if pattern in col.lower():
                    val = row[col]
                    if pd.notna(val) and isinstance(val, (int, float)):
                        return float(val)
        return None

    async def _generate_embeddings(self, chunks: List[AttributionChunk]) -> List[AttributionChunk]:
        """Step 3: Generate embeddings for all chunks"""
        if not self.ollama:
            raise ValueError("Ollama service not configured")
        
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        
        # Extract texts for batch embedding
        texts = [chunk.text for chunk in chunks]
        logger.info(f"Text samples: {[text[:100] + '...' if len(text) > 100 else text for text in texts[:3]]}")
        
        # Generate embeddings using Ollama
        try:
            embeddings = await self.ollama.generate_embeddings(texts)
            logger.info(f"Generated {len(embeddings)} embeddings")
            
            if embeddings and len(embeddings) > 0:
                logger.info(f"First embedding type: {type(embeddings[0])}, length: {len(embeddings[0]) if hasattr(embeddings[0], '__len__') else 'N/A'}")
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
        
        # Attach embeddings to chunks
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk.embedding = embedding
            logger.debug(f"Chunk {i} ({chunk.chunk_id}): embedding type={type(embedding)}, length={len(embedding) if hasattr(embedding, '__len__') else 'N/A'}")
        
        return chunks

    async def _store_chunks_in_qdrant(self, chunks: List[AttributionChunk], collection_name: str, session_id: str = None):
        """Step 4: Store chunks in Qdrant collection"""
        if not self.qdrant:
            raise ValueError("Qdrant service not configured")
        
        # Create session-scoped collection
        await self.qdrant.create_collection(collection_name)
        
        # Convert to Qdrant points
        points = []
        for i, chunk in enumerate(chunks):
            try:
                # Validate chunk data
                if not chunk.embedding:
                    logger.error(f"Chunk {chunk.chunk_id} has no embedding, skipping")
                    continue
                
                if not isinstance(chunk.embedding, list):
                    logger.error(f"Chunk {chunk.chunk_id} embedding is not a list: {type(chunk.embedding)}")
                    continue
                
                if len(chunk.embedding) != 768:  # nomic-embed-text dimension
                    logger.error(f"Chunk {chunk.chunk_id} embedding has wrong dimension: {len(chunk.embedding)}, expected 768")
                    continue
                
                logger.info(f"Chunk {chunk.chunk_id} passed validation: embedding type={type(chunk.embedding)}, length={len(chunk.embedding)}")
                
                # Ensure chunk ID is string and valid - already cleaned in chunk creation
                chunk_id = str(chunk.chunk_id)
                
                # Ensure embedding is list of floats
                embedding_vector = [float(x) for x in chunk.embedding]
                
                # Validate no NaN or infinite values
                if any(not (-1e10 < float(x) < 1e10) for x in embedding_vector):
                    logger.error(f"Chunk {chunk_id} has invalid embedding values (NaN/Inf)")
                    continue
                
                # Ensure payload is a dict with proper types
                if not isinstance(chunk.payload, dict):
                    logger.error(f"Chunk {chunk_id} payload is not a dict: {type(chunk.payload)}")
                    continue
                
                # Clean up payload - ensure all values are JSON serializable
                clean_payload = {}
                for key, value in chunk.payload.items():
                    if value is None:
                        clean_payload[key] = None
                    elif isinstance(value, (str, int, float, bool)):
                        clean_payload[key] = value
                    elif isinstance(value, list):
                        clean_payload[key] = [str(item) if item is not None else None for item in value]
                    else:
                        clean_payload[key] = str(value)
                
                # Create point as dict directly to avoid import issues
                point_dict = {
                    "id": chunk_id,
                    "vector": embedding_vector,
                    "payload": clean_payload
                }
                points.append(point_dict)
                logger.debug(f"Successfully created point {chunk_id}")
                
            except Exception as e:
                logger.error(f"Error processing chunk {i}: {e}")
                continue
        
        # Upsert points
        if not points:
            raise ValueError("No valid points to store after validation")
            
        logger.info(f"Attempting to store {len(points)} validated points to collection {collection_name}")
        
        try:
            # Use REST API approach due to client-server version incompatibility
            import requests
            import json
            import uuid

            # Validate points before upserting
            valid_points = []
            for i, point_dict in enumerate(points):
                try:
                    # Check vector format
                    if not isinstance(point_dict["vector"], list) or len(point_dict["vector"]) != 768:
                        logger.error(f"Point {i} has invalid vector: type={type(point_dict['vector'])}, length={len(point_dict['vector']) if hasattr(point_dict['vector'], '__len__') else 'N/A'}")
                        continue
                    
                    # Check for NaN or infinite values in vector
                    vector = [float(x) for x in point_dict["vector"]]
                    if any(not isinstance(v, (int, float)) or not (-1e10 < v < 1e10) for v in vector):
                        logger.error(f"Point {i} has invalid vector values (NaN/Inf)")
                        continue
                    
                    # Create point with UUID (required by v1.7.0 server)
                    point_uuid = str(uuid.uuid4())
                    point = {
                        "id": point_uuid,
                        "vector": vector,
                        "payload": point_dict["payload"]
                    }
                    
                    valid_points.append(point)
                    logger.debug(f"Point {i} ({point['id']}) passed validation")
                    
                except Exception as validation_error:
                    logger.error(f"Error validating point {i}: {validation_error}")
                    continue
            
            if not valid_points:
                logger.error("No valid points to store after validation")
                raise ValueError("All points failed validation")

            if len(valid_points) != len(points):
                logger.warning(f"Only {len(valid_points)}/{len(points)} points passed validation")

            logger.info(f"Storing {len(valid_points)} points in collection {collection_name} using REST API")

            # Store points using REST API (PUT with batch format works with v1.7.0)
            qdrant_url = "http://localhost:6333"  # Use the same URL as QdrantService
            endpoint = f"{qdrant_url}/collections/{collection_name}/points"

            point_data = {
                "points": valid_points
            }

            logger.info(f"Sending {len(valid_points)} points to {endpoint}")
            response = requests.put(
                endpoint,
                json=point_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "ok":
                    logger.info(f"Successfully stored {len(valid_points)} attribution chunks via REST API - Operation ID: {result.get('result', {}).get('operation_id')}")
                    
                    # Wait for indexing and verify points were stored
                    import time
                    time.sleep(1)  # Brief wait for indexing
                    
                    try:
                        collection_info = self.qdrant.client.get_collection(collection_name)
                        logger.info(f"Collection {collection_name} now has {collection_info.points_count} points")
                    except Exception as e:
                        logger.warning(f"Could not verify point count: {e}")
                else:
                    raise ValueError(f"REST API returned non-ok status: {result}")
            else:
                raise ValueError(f"REST API request failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Failed to upsert points to collection {collection_name}: {e}")
            # Log detailed error information
            if points:
                first_point = points[0]
                logger.error(f"First point debug info:")
                logger.error(f"  ID: '{first_point['id']}' (type: {type(first_point['id'])})")
                logger.error(f"  Vector length: {len(first_point['vector'])} (type: {type(first_point['vector'])})")
                logger.error(f"  Vector sample: {first_point['vector'][:3]}...")
                logger.error(f"  Payload type: {type(first_point['payload'])}")
                logger.error(f"  Payload keys: {list(first_point['payload'].keys())}")
                
                # Check if any payload values might be problematic
                for key, value in first_point['payload'].items():
                    logger.error(f"  Payload[{key}]: {type(value)} = {str(value)[:100]}...")
            
            # Try to get more specific error information
            import traceback
            logger.error(f"Full error traceback: {traceback.format_exc()}")
            raise
        
        logger.info(f"Stored {len(points)} attribution chunks in collection {collection_name}")

    async def answer_question(self, session_id: str, question: str, mode: str = "qa", context: str = None) -> Dict[str, Any]:
        """Answer questions using the attribution RAG system, optionally using provided context."""
        if not self.qdrant or not self.ollama:
            raise ValueError("Services not configured")
        collection_name = f"attr_session_{session_id}"
        # If context is provided from frontend, use it directly
        if context:
            logger.info(f"Using context provided from frontend for session {session_id}")
            context_json = context
        else:
            # Otherwise, build context from semantic search
            if not await self.qdrant.collection_exists(collection_name):
                raise ValueError(f"No attribution data found for session {session_id}")
            query_embedding = await self.ollama.generate_embedding(question)
            filters = self._derive_filters_from_question(question)
            search_results = self.qdrant.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                query_filter=filters,
                limit=12,
                with_payload=True,
                score_threshold=0.70
            )
            if not search_results:
                logger.warning(f"No relevant chunks found for session {session_id} and question '{question}'. Context will be empty.")
            import json
            context_json = json.dumps([result.payload for result in search_results], indent=2)
        context = context_json
        # Generate response based on mode
        if mode == "commentary":
            return await self._generate_commentary_response(context, session_id)
        else:
            return await self._generate_qa_response(question, context, session_id)

    def _derive_filters_from_question(self, question: str) -> Optional[Filter]:
        """Derive Qdrant filters from question text"""
        question_lower = question.lower()
        filter_conditions = []
        
        # Effect type filter
        if "fx" in question_lower or "currency" in question_lower:
            filter_conditions.append(
                FieldCondition(key="has_fx", match=Match(value=True))
            )
        
        return Filter(must=filter_conditions) if filter_conditions else None

    async def _generate_commentary_response(self, context: str, session_id: str) -> Dict[str, Any]:
        """Generate commentary mode response"""
        
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

        response = await self.ollama.generate_response(
            user_prompt,
            system_prompt=self.system_prompt,
            temperature=0.1
        )
        return {
            "mode": "commentary",
            "response": response["response"],
            "session_id": session_id,
            "context_used": len(context.split('\n')),
            "prompt": user_prompt  # Include the prompt sent to LLM
        }

    async def _generate_qa_response(self, question: str, context: str, session_id: str) -> Dict[str, Any]:
        """Generate Q&A mode response"""
        
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

        response = await self.ollama.generate_response(
            user_prompt,
            system_prompt=system_prompt,
            temperature=0.0
        )
        return {
            "mode": "qa",
            "question": question,
            "response": response["response"],
            "session_id": session_id,
            "context_used": len(context.split('\n')),
            "prompt": user_prompt  # Include prompt sent to LLM
        }

    async def clear_session(self, session_id: str) -> bool:
        """Clear attribution data for a session"""
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
        """Get statistics for an attribution session"""
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
                "total_chunks": info.points_count,
                "indexed_chunks": info.indexed_vectors_count,
                "status": info.status
            }
        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            return {"exists": False, "error": str(e)}