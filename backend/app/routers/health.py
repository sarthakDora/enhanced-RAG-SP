from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
import asyncio

router = APIRouter()

@router.get("/health", response_model=Dict[str, Any])
async def health_check(request: Request):
    """Health check endpoint"""
    try:
        # Check Qdrant connection
        qdrant_status = "unknown"
        try:
            qdrant_service = request.app.state.qdrant_service
            await qdrant_service.health_check()
            qdrant_status = "healthy"
        except Exception as e:
            qdrant_status = f"unhealthy: {str(e)}"
        
        # Check Ollama connection
        ollama_status = "unknown"
        try:
            ollama_service = request.app.state.ollama_service
            await ollama_service.health_check()
            ollama_status = "healthy"
        except Exception as e:
            ollama_status = f"unhealthy: {str(e)}"
        
        # Overall status
        overall_status = "healthy" if (
            "healthy" in qdrant_status and "healthy" in ollama_status
        ) else "degraded"
        
        return {
            "status": overall_status,
            "services": {
                "qdrant": qdrant_status,
                "ollama": ollama_status
            },
            "version": "1.0.0"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/health/qdrant", response_model=Dict[str, Any])
async def qdrant_health(request: Request):
    """Qdrant specific health check"""
    try:
        qdrant_service = request.app.state.qdrant_service
        await qdrant_service.health_check()
        
        # Get collection stats
        stats = await qdrant_service.get_collection_stats()
        
        return {
            "status": "healthy",
            "service": "qdrant",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Qdrant health check failed: {str(e)}")

@router.get("/health/ollama", response_model=Dict[str, Any])
async def ollama_health(request: Request):
    """Ollama specific health check"""
    try:
        ollama_service = request.app.state.ollama_service
        await ollama_service.health_check()
        
        return {
            "status": "healthy",
            "service": "ollama",
            "embedding_model": ollama_service.embedding_model,
            "llm_model": ollama_service.llm_model
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama health check failed: {str(e)}")