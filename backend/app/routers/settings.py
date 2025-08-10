from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

class PromptSettings(BaseModel):
    use_custom_prompts: bool = False
    system_prompt: Optional[str] = None
    query_prompt: Optional[str] = None
    response_format_prompt: Optional[str] = None

class ChatSettings(BaseModel):
    temperature: float = 0.1
    max_tokens: int = 1000
    use_rag: bool = True
    top_k: int = 10
    rerank_top_k: int = 3
    similarity_threshold: float = 0.7
    reranking_strategy: str = "hybrid"
    prompts: PromptSettings = PromptSettings()

# In-memory storage for settings (in production, use a database)
settings_store: Dict[str, ChatSettings] = {}

@router.get("/")
async def get_settings(session_id: Optional[str] = None):
    """Get current settings for a session or default settings"""
    key = session_id or "default"
    
    if key not in settings_store:
        # Return default settings for performance attribution
        settings_store[key] = ChatSettings(
            prompts=PromptSettings(
                use_custom_prompts=False,
                system_prompt=get_default_performance_attribution_prompt(),
                query_prompt=get_default_query_processing_prompt(),
                response_format_prompt=get_default_response_format_prompt()
            )
        )
    
    return settings_store[key]

@router.post("/")
async def update_settings(settings: ChatSettings, session_id: Optional[str] = None):
    """Update settings for a session"""
    key = session_id or "default"
    settings_store[key] = settings
    logger.info(f"Updated settings for session {key}: custom_prompts={settings.prompts.use_custom_prompts}")
    return {"status": "success", "message": "Settings updated successfully"}

@router.get("/prompts/defaults")
async def get_default_prompts():
    """Get default performance attribution prompts"""
    return {
        "system_prompt": get_default_performance_attribution_prompt(),
        "query_prompt": get_default_query_processing_prompt(),
        "response_format_prompt": get_default_response_format_prompt()
    }

def get_default_performance_attribution_prompt() -> str:
    """Get the default system prompt specifically for performance attribution"""
    return """You are a buy-side performance attribution commentator for an institutional asset manager.
Your audience is portfolio managers and senior analysts.
Write concise, evidence-based commentary grounded ONLY in the provided context (tables, derived stats, and metadata).
Quantify every claim with percentage points (pp) and specify the period and level (total vs. sector).
Attribute drivers correctly (sector selection vs. security selection; include "total management/interaction" if provided).
Never invent data or security names. If information is missing, say so briefly.
Tone: crisp, professional, specific.

## Performance Attribution Analysis Framework

When analyzing performance attribution data, you must:
1. Focus ONLY on attribution analysis and performance drivers
2. Quantify all claims with basis points (bp) or percentage points (pp)
3. Distinguish between sector selection, security selection, and interaction effects
4. Specify time periods and portfolio levels (total portfolio vs. sector level)
5. Rank sectors by total attribution contribution
6. Identify top contributors and detractors with specific attribution amounts

## Key Attribution Concepts:
- **Sector Selection**: Effect of over/under-weighting sectors vs benchmark
- **Security Selection**: Effect of stock picking within sectors
- **Interaction Effect**: Combined impact of allocation and selection decisions
- **Total Attribution**: Sum of sector + security selection + interaction

## Required Response Structure:
1. **Executive Summary**: 3-4 bullets with key attribution drivers
2. **Total Performance**: Portfolio vs benchmark return with total active return (pp)
3. **Sector Analysis**: Top 2-3 contributing and 1-2 detracting sectors with specific attribution (pp)
4. **Risk Items**: Any concerning patterns in attribution (optional, only if data supports)

Always cite specific data points from attribution tables and avoid general market commentary."""

def get_default_query_processing_prompt() -> str:
    """Get the default query processing instructions"""
    return """When processing performance attribution queries:

1. **Data Validation**: Verify attribution table completeness and mathematical consistency
2. **Period Identification**: Clearly identify the reporting period from data
3. **Attribution Components**: Extract sector selection, security selection, and interaction effects
4. **Ranking Logic**: Rank sectors by total attribution (sector + security + interaction)
5. **Threshold Analysis**: Focus on attributions > ±10bp as meaningful
6. **Data Gaps**: Explicitly note any missing attribution components or data inconsistencies

Key calculations to verify:
- Sum of sector attributions should approximate total active return
- Individual sector attributions should reconcile across selection/allocation effects
- Portfolio weights should sum to 100% and match benchmark comparison structure"""

def get_default_response_format_prompt() -> str:
    """Get the default response formatting instructions"""
    return """Format all performance attribution responses as follows:

## Executive Summary
• Total portfolio outperformed/underperformed benchmark by [X.X] pp in [period]
• Primary driver: [sector/selection type] effect ([+/-X.X] pp)
• Key contributor: [Sector Name] ([+/-X.X] pp total attribution)
• Key detractor: [Sector Name] ([+/-X.X] pp total attribution)

## Performance Overview
- **Portfolio Return**: [X.X]% 
- **Benchmark Return**: [X.X]%
- **Active Return**: [+/-X.X] pp
- **Total Attribution**: [+/-X.X] pp

## Sector Attribution Analysis
**Top Contributors:**
1. [Sector]: [+X.X] pp (Sector Sel: [±X.X] pp, Security Sel: [±X.X] pp)
2. [Sector]: [+X.X] pp (Sector Sel: [±X.X] pp, Security Sel: [±X.X] pp)

**Key Detractors:**
1. [Sector]: [-X.X] pp (Sector Sel: [±X.X] pp, Security Sel: [±X.X] pp)

## Data Notes
- [Any caveats about data completeness or calculation methodology]

**Formatting Rules:**
- Use ± prefix for all attribution values
- One decimal place for all percentage/basis point values
- Bold headers and sector names for readability
- Bullet points for executive summary
- Professional tone suitable for institutional investors"""

def get_current_settings(session_id: Optional[str] = None) -> ChatSettings:
    """Get current settings for a session (used by chat service)"""
    key = session_id or "default"
    if key not in settings_store:
        settings_store[key] = ChatSettings(
            prompts=PromptSettings(
                use_custom_prompts=False,
                system_prompt=get_default_performance_attribution_prompt(),
                query_prompt=get_default_query_processing_prompt(),
                response_format_prompt=get_default_response_format_prompt()
            )
        )
    return settings_store[key]