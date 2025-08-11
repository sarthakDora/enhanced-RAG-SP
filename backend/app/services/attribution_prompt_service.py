"""
Attribution Analysis Prompt Service

This service provides specialized prompts for attribution commentary generation
and Q&A modes when analyzing performance attribution documents.
"""

from typing import Dict, List, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AttributionMode(Enum):
    COMMENTARY = "commentary"
    QA = "qa"


class AssetClass(Enum):
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    UNKNOWN = "unknown"


class AttributionPromptService:
    """Service for generating attribution-specific prompts"""
    
    def __init__(self):
        self.equity_indicators = [
            'sector', 'gics', 'industry', 'security selection', 
            'stock', 'equity', 'market cap', 'style'
        ]
        self.fixed_income_indicators = [
            'duration', 'credit', 'currency', 'country', 'sovereign',
            'corporate', 'government', 'bond', 'yield', 'fx selection'
        ]
    
    def detect_asset_class(self, document_chunks: List[Dict[str, Any]]) -> AssetClass:
        """Auto-detect asset class from document content"""
        try:
            if not document_chunks:
                return AssetClass.UNKNOWN
                
            # Combine all document text for analysis
            combined_text = " ".join([
                chunk.get('content', '').lower() 
                for chunk in document_chunks
            ])
            
            equity_score = sum(1 for indicator in self.equity_indicators if indicator in combined_text)
            fixed_income_score = sum(1 for indicator in self.fixed_income_indicators if indicator in combined_text)
            
            logger.info(f"Asset class detection - Equity score: {equity_score}, Fixed Income score: {fixed_income_score}")
            
            if equity_score > fixed_income_score:
                return AssetClass.EQUITY
            elif fixed_income_score > equity_score:
                return AssetClass.FIXED_INCOME
            else:
                return AssetClass.UNKNOWN
                
        except Exception as e:
            logger.error(f"Asset class detection failed: {e}")
            return AssetClass.UNKNOWN
    
    def get_commentary_prompt(self, asset_class: AssetClass, document_chunks: List[Dict[str, Any]]) -> str:
        """Get structured commentary generation prompt"""
        
        if asset_class == AssetClass.EQUITY:
            return self._get_equity_commentary_prompt()
        elif asset_class == AssetClass.FIXED_INCOME:
            return self._get_fixed_income_commentary_prompt()
        else:
            return self._get_generic_commentary_prompt()
    
    def get_qa_prompt(self, asset_class: AssetClass) -> str:
        """Get Q&A mode prompt"""
        
        base_prompt = """You are a data analyst. Answer questions based only on the provided context from the uploaded document. 
If the answer is not in the document, say so.
Be concise and precise. Use numbers, dates, and references exactly as in the context.
"""
        
        if asset_class == AssetClass.EQUITY:
            return base_prompt + """
Focus on equity attribution analysis including:
- Sector allocation and selection effects
- Security selection performance
- Geographic allocation impacts
- Market capitalization effects
"""
        elif asset_class == AssetClass.FIXED_INCOME:
            return base_prompt + """
Focus on fixed income attribution analysis including:
- Duration and yield curve positioning
- Credit quality and selection effects
- Currency and country allocation
- Sovereign vs corporate bond performance
"""
        else:
            return base_prompt + """
Analyze the performance attribution data as provided in the document.
"""
    
    def _get_equity_commentary_prompt(self) -> str:
        """Equity-specific commentary prompt"""
        return """You are an expert equity performance attribution analyst. Analyze the provided attribution data and generate a comprehensive commentary following this exact structure:

## Executive Summary
Provide a 2-3 sentence high-level summary of portfolio performance vs benchmark, highlighting the primary drivers of over/underperformance.

## Performance Overview
- Total portfolio return vs benchmark return
- Active return (portfolio - benchmark)
- Key time period being analyzed
- Overall attribution effect breakdown

## Sector Attribution Analysis
Analyze sector-level attribution effects:
- **Top Contributing Sectors**: List the 3-5 sectors that contributed most positively to performance
- **Top Detracting Sectors**: List the 3-5 sectors that detracted most from performance
- For each sector, break down:
  - Allocation effect (overweight/underweight impact)
  - Selection effect (security picking impact)
  - Total effect

## Geographic Attribution Analysis
If geographic data is available:
- Country/region allocation effects
- Currency impacts
- Regional over/underweights and their performance impact

## Security Selection Insights
- Overall security selection effectiveness
- Notable individual security contributors/detractors
- Sector-specific selection patterns

## Data Notes
- Time period covered
- Benchmark used
- Attribution methodology
- Data source and calculation notes

**CRITICAL REQUIREMENTS:**
1. Use ONLY data from the provided context - no external information
2. Include specific numbers, percentages, and sector names exactly as shown
3. If data for any section is not available, state "Data not available in provided attribution report"
4. Maintain professional, analytical tone
5. All calculations and rankings must come strictly from the provided context"""

    def _get_fixed_income_commentary_prompt(self) -> str:
        """Fixed income-specific commentary prompt"""
        return """You are an expert fixed income performance attribution analyst. Analyze the provided attribution data and generate a comprehensive commentary following this exact structure:

## Executive Summary
Provide a 2-3 sentence high-level summary of portfolio performance vs benchmark, highlighting the primary drivers of over/underperformance.

## Performance Overview
- Total portfolio return vs benchmark return
- Active return (portfolio - benchmark)  
- Key time period being analyzed
- Overall attribution effect breakdown

## Duration and Yield Curve Attribution
Analyze duration and yield curve positioning:
- Duration allocation effects
- Yield curve positioning impact
- Interest rate sensitivity analysis

## Credit Attribution Analysis
- **Credit Quality Effects**: Investment grade vs high yield allocation impacts
- **Credit Selection Effects**: Individual security selection within credit categories
- **Credit Sector Analysis**: Performance by credit sector (corporate, sovereign, agency, etc.)

## Currency and Country Attribution
If applicable:
- Currency allocation effects
- FX selection impact
- Country/sovereign allocation performance
- Regional over/underweights and their performance impact

## Security Selection Insights
- Overall security selection effectiveness
- Notable individual security contributors/detractors
- Sector-specific selection patterns

## Data Notes
- Time period covered
- Benchmark used
- Attribution methodology
- Data source and calculation notes

**CRITICAL REQUIREMENTS:**
1. Use ONLY data from the provided context - no external information
2. Include specific numbers, percentages, and country/sector names exactly as shown
3. If data for any section is not available, state "Data not available in provided attribution report"
4. Maintain professional, analytical tone
5. All calculations and rankings must come strictly from the provided context"""

    def _get_generic_commentary_prompt(self) -> str:
        """Generic attribution commentary prompt"""
        return """You are an expert performance attribution analyst. Analyze the provided attribution data and generate a comprehensive commentary following this exact structure:

## Executive Summary
Provide a 2-3 sentence high-level summary of portfolio performance vs benchmark, highlighting the primary drivers of over/underperformance.

## Performance Overview
- Total portfolio return vs benchmark return
- Active return (portfolio - benchmark)
- Key time period being analyzed
- Overall attribution effect breakdown

## Attribution Analysis
Analyze the attribution effects as provided in the document:
- **Top Contributors**: List the top contributing factors to performance
- **Top Detractors**: List the top detracting factors from performance
- Break down allocation vs selection effects where available
- Include specific numerical impacts

## Key Insights
- Overall portfolio management effectiveness
- Notable trends or patterns
- Risk/return characteristics

## Data Notes
- Time period covered
- Benchmark used
- Attribution methodology
- Data source and calculation notes

**CRITICAL REQUIREMENTS:**
1. Use ONLY data from the provided context - no external information
2. Include specific numbers, percentages, and factor names exactly as shown
3. If data for any section is not available, state "Data not available in provided attribution report"
4. Maintain professional, analytical tone
5. All calculations and rankings must come strictly from the provided context"""

    def assemble_prompt(self, mode: AttributionMode, asset_class: AssetClass, 
                       document_chunks: List[Dict[str, Any]], user_query: str) -> str:
        """Assemble the complete prompt based on mode and context"""
        
        # Prepare document context
        context_sections = []
        context_sections.append("=== RELEVANT ATTRIBUTION DOCUMENT CONTENT ===")
        
        for i, chunk in enumerate(document_chunks, 1):
            filename = chunk.get('filename', 'Unknown Document')
            content = chunk.get('content', '')
            context_sections.append(f"\nSource {i} ({filename}):")
            context_sections.append(content)
        
        context_sections.append("\n=== END DOCUMENT CONTENT ===\n")
        
        # Get appropriate system prompt
        if mode == AttributionMode.COMMENTARY:
            system_prompt = self.get_commentary_prompt(asset_class, document_chunks)
        else:  # QA mode
            system_prompt = self.get_qa_prompt(asset_class)
        
        # Assemble final prompt
        final_prompt_parts = [
            system_prompt,
            "",
            "\n".join(context_sections),
            f"User Query: {user_query}"
        ]
        
        return "\n".join(final_prompt_parts)