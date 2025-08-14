"""
FastAPI router for attribution RAG endpoints.
Handles Excel upload, processing, and Q&A for performance attribution reports.
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import uuid
import tempfile
import os
import logging

from ..services.performance_attribution_service import PerformanceAttributionService
from ..services.ollama_service import OllamaService
from ..services.qdrant_service import QdrantService
from ..core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attribution", tags=["attribution"])

# Dependency injection
def get_ollama_service():
    return OllamaService()

def get_qdrant_service():
    return QdrantService()

def get_attribution_service(
    ollama: OllamaService = Depends(get_ollama_service),
    qdrant: QdrantService = Depends(get_qdrant_service)
):
    return PerformanceAttributionService(ollama, qdrant)


@router.post("/upload", response_model=Dict[str, Any])
async def upload_attribution_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service)
):
    """
    Upload and process an Excel attribution file.
    
    Creates session-scoped Qdrant collection with row-centric chunks.
    """
    try:
        # Validate file type
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported")
        
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Process the attribution file
            result = await attribution_service.process_attribution_file(tmp_file_path, session_id)

            # Add file info to result
            result.update({
                "filename": file.filename,
                "file_size": len(content),
                "upload_success": True
            })

            # Add chunk data for UI display
            if hasattr(attribution_service, 'last_chunks') and attribution_service.last_chunks:
                result["chunks"] = [
                    {
                        "filename": chunk.payload.get("bucket", "Unknown"),
                        "content": chunk.text,
                        "document_type": chunk.payload.get("asset_class", "unknown"),
                        "chunk_type": chunk.chunk_type
                    }
                    for chunk in getattr(attribution_service, 'last_chunks', [])
                ]
            elif "chunks" in result:
                # If process_attribution_file returns chunks
                result["chunks"] = [
                    {
                        "filename": chunk.get("bucket", "Unknown"),
                        "content": chunk.get("text", ""),
                        "document_type": chunk.get("asset_class", "unknown"),
                        "chunk_type": chunk.get("chunk_type", "row")
                    }
                    for chunk in result["chunks"]
                ]
            else:
                result["chunks"] = []

            logger.info(f"Successfully processed attribution file: {file.filename} for session {session_id}")
            return result
            
        finally:
            # Clean up temporary file with retry mechanism for Windows file locking
            import time
            for attempt in range(3):
                try:
                    os.unlink(tmp_file_path)
                    break
                except (OSError, PermissionError) as e:
                    if attempt < 2:
                        time.sleep(0.1)  # Wait 100ms before retry
                        continue
                    logger.warning(f"Could not delete temporary file after 3 attempts: {e}")
            
    except Exception as e:
        logger.error(f"Error processing attribution file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process attribution file: {str(e)}")


@router.post("/question", response_model=Dict[str, Any])
async def ask_attribution_question(
    session_id: str = Form(...),
    question: str = Form(...),
    mode: str = Form("qa", regex="^(qa|commentary)$"),
    context: Optional[str] = Form(None),
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service)
):
    """
    Ask a question about attribution data using RAG.
    
    Modes:
    - qa: Document-based Q&A (strict context adherence)
    - commentary: Generate professional PM commentary
    """
    try:
        if not question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        # Pass context to service if provided
        response = await attribution_service.answer_question(session_id, question, mode, context=context)
        
        logger.info(f"Answered attribution question for session {session_id}: {question[:50]}...")
        return response
        
    except ValueError as e:
        # Session not found or no data
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error answering attribution question: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {str(e)}")


@router.get("/session/{session_id}/stats", response_model=Dict[str, Any])
async def get_session_stats(
    session_id: str,
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service)
):
    """Get statistics for an attribution session."""
    try:
        stats = await attribution_service.get_session_stats(session_id)
        return stats
    except Exception as e:
        logger.error(f"Error getting session stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session stats: {str(e)}")


@router.delete("/session/{session_id}", response_model=Dict[str, Any])
async def clear_session(
    session_id: str,
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service)
):
    """Clear all attribution data for a session."""
    try:
        success = await attribution_service.clear_session(session_id)
        return {
            "session_id": session_id,
            "cleared": success,
            "message": "Session cleared successfully" if success else "Failed to clear session"
        }
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}")


@router.post("/commentary", response_model=Dict[str, Any])
async def generate_commentary(
    session_id: str = Form(...),
    period: Optional[str] = Form(None),
    context: Optional[str] = Form(None),
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service)
):
    """
    Generate professional attribution commentary for a session.
    
    Uses the commentary mode with institutional PM-grade output.
    """
    try:
        # Build commentary request
        if period:
            question = f"Generate {period} attribution commentary"
        else:
            question = "Generate attribution commentary"
        # Pass context to service if provided
        response = await attribution_service.answer_question(session_id, question, mode="commentary", context=context)
        
        logger.info(f"Generated commentary for session {session_id}")
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating commentary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate commentary: {str(e)}")


@router.get("/health")
async def health_check(
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service)
):
    """Health check for attribution service dependencies."""
    try:
        health_status = {
            "attribution_service": "ok",
            "ollama": "unknown",
            "qdrant": "unknown"
        }
        
        # Check Ollama health
        try:
            if attribution_service.ollama:
                await attribution_service.ollama.health_check()
                health_status["ollama"] = "ok"
        except Exception as e:
            health_status["ollama"] = f"error: {str(e)}"
        
        # Check Qdrant health
        try:
            if attribution_service.qdrant:
                await attribution_service.qdrant.health_check()
                health_status["qdrant"] = "ok"
        except Exception as e:
            health_status["qdrant"] = f"error: {str(e)}"
        
        # Overall health
        overall_healthy = all(status == "ok" for status in health_status.values())
        health_status["overall"] = "healthy" if overall_healthy else "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "overall": "error",
            "message": str(e)
        }


@router.get("/examples")
async def get_usage_examples():
    """Get usage examples for the attribution RAG API."""
    return {
        "upload_example": {
            "endpoint": "POST /attribution/upload",
            "description": "Upload Excel attribution file",
            "curl_example": '''curl -X POST "http://localhost:8000/attribution/upload" \\
  -F "file=@Q2_2025_Attribution.xlsx" \\
  -F "session_id=my_session_123"''',
            "response_example": {
                "status": "success",
                "session_id": "my_session_123",
                "collection_name": "attr_session_my_session_123",
                "chunks_created": 15,
                "period": "Q2 2025",
                "asset_class": "Equity",
                "attribution_level": "Sector"
            }
        },
        "qa_example": {
            "endpoint": "POST /attribution/question",
            "description": "Ask Q&A questions about attribution data",
            "curl_example": '''curl -X POST "http://localhost:8000/attribution/question" \\
  -F "session_id=my_session_123" \\
  -F "question=Which sectors had negative FX but positive selection?" \\
  -F "mode=qa"''',
            "response_example": {
                "mode": "qa",
                "question": "Which sectors had negative FX but positive selection?",
                "response": "Based on the attribution data, Technology sector had negative FX of -0.2 pp but positive selection of +1.8 pp.",
                "session_id": "my_session_123"
            }
        },
        "commentary_example": {
            "endpoint": "POST /attribution/commentary",
            "description": "Generate professional attribution commentary",
            "curl_example": '''curl -X POST "http://localhost:8000/attribution/commentary" \\
  -F "session_id=my_session_123" \\
  -F "period=Q2 2025"''',
            "response_example": {
                "mode": "commentary",
                "response": "**Executive Summary**\\nThe portfolio generated positive active return of +0.8 pp in Q2 2025...",
                "session_id": "my_session_123"
            }
        },
        "sample_questions": [
            "What were the top 3 contributors by total attribution?",
            "Which sectors had positive allocation effect?",
            "What was the total FX impact?",
            "Show me the rankings by total attribution",
            "Which countries had negative carry but positive selection?",
            "What was the portfolio total return vs benchmark?"
        ]
    }