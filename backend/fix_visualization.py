"""
Quick fix for visualization endpoint - run this script to patch the router
"""
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def patch_visualization_endpoint():
    """Replace the visualization endpoint with working demo code"""
    router_file = os.path.join(os.path.dirname(__file__), 'app', 'routers', 'attribution.py')
    
    # Read the current file
    with open(router_file, 'r') as f:
        content = f.read()
    
    # Find and replace the visualization function
    start_marker = '@router.post("/visualization")'
    end_marker = 'raise HTTPException(status_code=500, detail=f"Failed to generate visualization: {str(e)}")'
    
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker, start_idx) + len(end_marker)
    
    if start_idx == -1 or end_idx == -1:
        print("Could not find visualization function to replace")
        return
    
    # New working function
    new_function = '''@router.post("/visualization")
async def generate_attribution_visualization(
    session_id: str = Form(...),
    prompt: str = Form(...),
    chart_type: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Generate AI-powered visualizations - DEMO MODE"""
    
    # Return demo data immediately
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
        "title": f"Attribution Analysis",
        "type": chart_type or "bar",
        "description": f"Demo visualization: {prompt}",
        "data": {
            "labels": [item["name"] for item in demo_data],
            "datasets": [{
                "label": "Total Attribution (pp)",
                "data": [item["total"] for item in demo_data]
            }]
        },
        "raw_data": [[item["name"], item["total"], item["allocation"], item["selection"]] for item in demo_data],
        "headers": ["Sector", "Total Attribution", "Allocation Effect", "Selection Effect"]
    }'''
    
    # Replace the function
    new_content = content[:start_idx] + new_function + content[end_idx:]
    
    # Write back to file
    with open(router_file, 'w') as f:
        f.write(new_content)
    
    print("✅ Visualization endpoint patched successfully!")
    print("Now restart your server with: python -m uvicorn main:app --reload --port 8000")

if __name__ == "__main__":
    patch_visualization_endpoint()