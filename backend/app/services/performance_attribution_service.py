from typing import Dict, Any, List, Optional
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class PerformanceAttributionService:
    """
    Specialized service for processing performance attribution documents and generating
    professional commentary using the institutional buy-side framework.
    """
    
    def __init__(self):
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
3) Highlights (top 3 contributors and top 2 detractors, with reasons)
4) Risks / Watch Items (optional if justified by data)

Rules:
- Use one decimal place for pp values and retain +/- signs.
- All numbers must appear in the provided data or be simple arithmetic from it.
- Avoid generic phrases; focus on material drivers."""

        self.developer_prompt = """- Only use numbers given in the user prompt.
- Identify drivers explicitly as allocation, selection, FX, or other effects present.
- Rank top contributors/detractors strictly by Total Attribution (pp).
- Limit Executive Summary to 3–4 sentences; avoid filler.
- Do not add securities, macro factors, or assumptions not in context.
- Use one decimal place for pp values and retain +/- signs."""

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