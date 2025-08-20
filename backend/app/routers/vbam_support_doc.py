"""
VBAM Component Router
Provides endpoints for VBAM multi-component support including IPR, Analytics Report, Factsheet, and Holdings and Risk.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import List, Optional, Dict, Any
import logging
import tempfile
import os
from pathlib import Path

from ..services.vbam_component_service import VBAMComponentService
from ..services.qdrant_service import QdrantService
from ..services.ollama_service import OllamaService

logger = logging.getLogger(__name__)

router = APIRouter()

def get_vbam_service() -> VBAMComponentService:
    """Dependency to get VBAM service instance"""
    # Get services from app state
    from fastapi import Request
    from starlette.requests import Request as StarletteRequest
    import inspect
    
    # Get the current request context
    frame = inspect.currentframe()
    while frame:
        if 'request' in frame.f_locals:
            request = frame.f_locals['request']
            if hasattr(request, 'app'):
                qdrant_service = request.app.state.qdrant_service
                ollama_service = request.app.state.ollama_service
                return VBAMComponentService(qdrant_service, ollama_service)
        frame = frame.f_back
    
    # Fallback - create new instances
    qdrant_service = QdrantService()
    ollama_service = OllamaService()
    return VBAMComponentService(qdrant_service, ollama_service)

@router.post("/initialize")
async def initialize_vbam_collections():
    """Initialize VBAM component collections"""
    try:
        vbam_service = get_vbam_service()
        success = await vbam_service.initialize_collections()
        
        if success:
            return {"message": "VBAM collections initialized successfully", "success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to initialize VBAM collections")
    
    except Exception as e:
        logger.error(f"Error initializing VBAM collections: {e}")
        raise HTTPException(status_code=500, detail=f"Error initializing VBAM collections: {str(e)}")

@router.post("/sample-data")
async def create_vbam_sample_data():
    """Create sample data for VBAM components"""
    try:
        vbam_service = get_vbam_service()
        
        # Create some sample documentation for each component
        sample_data = {
            "IPR": "Investment Performance Report Overview: This component provides comprehensive performance analysis including return statistics, risk metrics, and trailing performance data. Navigation: Access through the IPR tab in VBAM. Inputs: Portfolio data, benchmark selection, time periods. Outputs: Performance charts, statistical summaries, risk-adjusted returns.",
            "Analytics Report": "Analytics Report Overview: Advanced analytical tools for factor attribution and style box analysis. Navigation: Located in the Analytics section of VBAM. Inputs: Portfolio holdings, factor models, analysis periods. Outputs: Factor attribution charts, style drift analysis, performance drivers breakdown.",
            "Factsheet": "Factsheet Overview: Standardized investment summary documents with key statistics and holdings information. Navigation: Generate through the Factsheet module. Inputs: Portfolio selection, template choice, date range. Outputs: Professional factsheets, top holdings lists, sector allocations.",
            "Holdings and Risk": "Holdings and Risk Overview: Detailed portfolio composition and risk analysis tools. Navigation: Access via Risk Analytics dashboard. Inputs: Portfolio holdings data, risk models, stress scenarios. Outputs: Risk reports, concentration analysis, geographic breakdowns."
        }
        
        results = {}
        for component, content in sample_data.items():
            success = await vbam_service.process_component_document(
                component=component,
                content=content,
                filename=f"sample_{component.lower().replace(' ', '_')}_doc.txt"
            )
            results[component] = success
        
        return {
            "message": "Sample data created successfully",
            "results": results,
            "success": all(results.values())
        }
    
    except Exception as e:
        logger.error(f"Error creating sample data: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating sample data: {str(e)}")

@router.post("/upload/{component}")
async def upload_vbam_document(
    component: str,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None)
):
    """Upload and process a document for a specific VBAM component"""
    try:
        vbam_service = get_vbam_service()
        
        # Validate component
        valid_components = ["IPR", "Analytics Report", "Factsheet", "Holdings and Risk"]
        if component not in valid_components:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid component. Valid components: {valid_components}"
            )
        
        # Read file content
        content = await file.read()
        
        # Process based on file type
        if file.filename.lower().endswith('.docx'):
            # Save temporarily for docx processing
            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            try:
                success = await vbam_service.process_component_document(
                    component=component,
                    filename=file.filename,
                    file_path=temp_file_path
                )
            finally:
                # Clean up temp file
                os.unlink(temp_file_path)
        
        else:
            # Process as text content
            try:
                text_content = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    text_content = content.decode('latin-1')
                except UnicodeDecodeError:
                    raise HTTPException(status_code=400, detail="Unable to decode file content")
            
            success = await vbam_service.process_component_document(
                component=component,
                content=text_content,
                filename=file.filename
            )
        
        if success:
            return {
                "message": f"Document uploaded and processed successfully for {component}",
                "filename": file.filename,
                "component": component,
                "description": description,
                "success": True
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to process document")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading VBAM document: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

@router.post("/ask")
async def ask_vbam_question(request: Dict[str, Any]):
    """Ask a question across VBAM components with optional routing"""
    try:
        question = request.get("question")
        component = request.get("component")  # Optional specific component
        
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")
        
        vbam_service = get_vbam_service()
        result = await vbam_service.answer_component_question(question, component)
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing VBAM question: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")

@router.post("/search/{component}")
async def search_vbam_component(
    component: str,
    request: Dict[str, Any]
):
    """Search within a specific VBAM component"""
    try:
        question = request.get("question")
        top_k = request.get("top_k", 10)
        
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")
        
        # Validate component
        valid_components = ["IPR", "Analytics Report", "Factsheet", "Holdings and Risk"]
        if component not in valid_components:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid component. Valid components: {valid_components}"
            )
        
        vbam_service = get_vbam_service()
        results = await vbam_service.search_component(component, question, top_k)
        
        return {
            "component": component,
            "question": question,
            "results": results,
            "count": len(results)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching VBAM component: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching component: {str(e)}")

@router.post("/route")
async def route_vbam_question(request: Dict[str, Any]):
    """Route a question to the most appropriate VBAM component"""
    try:
        question = request.get("question")
        
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")
        
        vbam_service = get_vbam_service()
        component = vbam_service.route_question_to_component(question)
        
        return {
            "question": question,
            "routed_component": component,
            "confidence": "high" if component else "low"
        }
    
    except Exception as e:
        logger.error(f"Error routing VBAM question: {e}")
        raise HTTPException(status_code=500, detail=f"Error routing question: {str(e)}")

@router.get("/components")
async def get_vbam_components():
    """Get list of available VBAM components"""
    return {
        "components": ["IPR", "Analytics Report", "Factsheet", "Holdings and Risk"],
        "descriptions": {
            "IPR": "Investment Performance Report - Performance analysis and statistics",
            "Analytics Report": "Factor attribution and style box analysis",
            "Factsheet": "Investment summary documents and key statistics",
            "Holdings and Risk": "Portfolio composition and risk analysis"
        }
    }

@router.get("/stats")
async def get_vbam_stats():
    """Get statistics for all VBAM component collections"""
    try:
        vbam_service = get_vbam_service()
        stats = await vbam_service.get_component_stats()
        
        return {
            "component_stats": stats,
            "total_components": len(stats),
            "total_documents": sum(s.get("points_count", 0) for s in stats.values() if isinstance(s.get("points_count"), int))
        }
    
    except Exception as e:
        logger.error(f"Error getting VBAM stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

@router.delete("/component/{component}")
async def clear_vbam_component(component: str):
    """Clear all documents from a specific VBAM component"""
    try:
        # Validate component
        valid_components = ["IPR", "Analytics Report", "Factsheet", "Holdings and Risk"]
        if component not in valid_components:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid component. Valid components: {valid_components}"
            )
        
        vbam_service = get_vbam_service()
        success = await vbam_service.clear_component_collection(component)
        
        if success:
            return {
                "message": f"Cleared all documents from {component} component",
                "component": component,
                "success": True
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to clear {component} component")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing VBAM component: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing component: {str(e)}")