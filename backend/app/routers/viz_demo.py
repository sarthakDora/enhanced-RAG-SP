"""
Demo visualization router - completely separate file to avoid caching issues
"""
from fastapi import APIRouter, Form
from typing import Optional, Dict, Any

router = APIRouter(prefix="/viz", tags=["visualization-demo"])

@router.post("/demo")
async def create_demo_visualization(
    session_id: str = Form(...),
    prompt: str = Form(...),
    chart_type: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """
    Demo visualization endpoint that always returns working data.
    """
    # Demo attribution data
    demo_data = [
        {"name": "Technology", "total": 1.5, "allocation": 0.3, "selection": 1.2},
        {"name": "Healthcare", "total": -0.8, "allocation": -0.2, "selection": -0.6},
        {"name": "Financials", "total": 0.9, "allocation": 0.5, "selection": 0.4},
        {"name": "Energy", "total": -1.2, "allocation": -0.8, "selection": -0.4},
        {"name": "Consumer Discretionary", "total": 0.6, "allocation": 0.1, "selection": 0.5}
    ]
    
    return {
        "status": "success",
        "session_id": session_id,
        "title": f"Attribution Analysis - {chart_type or 'Bar'} Chart",
        "type": chart_type or "bar",
        "description": f"Demo visualization based on your request: {prompt}",
        "data": {
            "labels": [item["name"] for item in demo_data],
            "datasets": [{
                "label": "Total Attribution (pp)",
                "data": [item["total"] for item in demo_data]
            }]
        },
        "raw_data": [[item["name"], item["total"], item["allocation"], item["selection"]] for item in demo_data],
        "headers": ["Sector", "Total Attribution", "Allocation Effect", "Selection Effect"]
    }

@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify the demo router is working"""
    return {"message": "Demo visualization router is working!", "timestamp": "2024-08-15"}