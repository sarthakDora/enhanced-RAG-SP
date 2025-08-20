"""
FastAPI router for attribution RAG endpoints.
Handles Excel upload, processing, and Q&A for performance attribution reports.
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from typing import Optional, Dict, Any, List, Literal
import uuid
import tempfile
import os
import logging
from functools import lru_cache

from ..services.performance_attribution_service import PerformanceAttributionService
from ..services.ollama_service import OllamaService
from ..services.qdrant_service import QdrantService
from ..core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attribution", tags=["attribution"])

# ---------------------------------------------------------------------
# Dependency injection (singleton clients)
# ---------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_ollama_service() -> OllamaService:
    return OllamaService()

@lru_cache(maxsize=1)
def get_qdrant_service() -> QdrantService:
    return QdrantService()

def get_attribution_service(
    ollama: OllamaService = Depends(get_ollama_service),
    qdrant: QdrantService = Depends(get_qdrant_service),
) -> PerformanceAttributionService:
    return PerformanceAttributionService(ollama, qdrant)

# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------

@router.post("/upload")
async def upload_attribution_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service),
) -> Dict[str, Any]:
    """
    Upload and process an Excel attribution file.
    Creates session-scoped Qdrant collection with row-centric chunks.
    """
    try:
        # Validate file type (case-insensitive)
        fname = (file.filename or "").lower()
        if not (fname.endswith(".xlsx") or fname.endswith(".xls") or fname.endswith(".xlsm")):
            raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls, .xlsm) are supported")

        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())

        # Save uploaded file temporarily
        tmp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(fname)[1] or ".xlsx") as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_file_path = tmp_file.name

            # Process the attribution file
            result = await attribution_service.process_attribution_file(tmp_file_path, session_id)

            # Add file info to result
            result.update({
                "filename": file.filename,
                "file_size": len(content),
                "session_id": session_id,
                "upload_success": True,
            })

            # Normalize chunk data for UI display
            # Prefer the chunks already in `result`; else echo from attribution_service.last_chunks
            if "chunks" in result and isinstance(result["chunks"], list) and result["chunks"]:
                result["chunks"] = [
                    {
                        "filename": c.get("bucket", "Unknown"),
                        "content": c.get("text", ""),
                        "document_type": c.get("asset_class", "unknown"),
                        "chunk_type": c.get("chunk_type", "row"),
                    }
                    for c in result["chunks"]
                ]
            elif getattr(attribution_service, "last_chunks", None):
                result["chunks"] = [
                    {
                        "filename": ch.payload.get("bucket", "Unknown"),
                        "content": ch.text,
                        "document_type": ch.payload.get("asset_class", "unknown"),
                        "chunk_type": ch.chunk_type,
                    }
                    for ch in attribution_service.last_chunks
                ]
            else:
                result["chunks"] = []

            logger.info(f"Successfully processed attribution file: {file.filename} for session {session_id}")
            return result

        finally:
            # Clean up temporary file (retry to avoid Windows file locks)
            if tmp_file_path and os.path.exists(tmp_file_path):
                import time
                for attempt in range(3):
                    try:
                        os.unlink(tmp_file_path)
                        break
                    except (OSError, PermissionError) as e:
                        if attempt < 2:
                            time.sleep(0.15)
                            continue
                        logger.warning(f"Could not delete temporary file after 3 attempts: {e}")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing attribution file")
        raise HTTPException(status_code=500, detail=f"Failed to process attribution file: {str(e)}")


@router.post("/question")
async def ask_attribution_question(
    session_id: str = Form(...),
    question: str = Form(...),
    mode: Literal["qa", "commentary"] = Form("qa"),
    context: Optional[str] = Form(None),
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service),
) -> Dict[str, Any]:
    """
    Ask a question about attribution data using RAG.

    Modes:
    - qa: Document-based Q&A (strict context adherence)
    - commentary: Generate professional PM commentary
    """
    try:
        if not question or not question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        response = await attribution_service.answer_question(session_id, question, mode, context=context)
        logger.info(f"Answered attribution question for session {session_id}: {question[:80]}...")
        return response

    except ValueError as e:
        # Session not found or no data
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error answering attribution question")
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {str(e)}")


@router.get("/session/{session_id}/stats")
async def get_session_stats(
    session_id: str,
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service),
) -> Dict[str, Any]:
    """Get statistics for an attribution session."""
    try:
        stats = await attribution_service.get_session_stats(session_id)
        return stats
    except Exception as e:
        logger.exception("Error getting session stats")
        raise HTTPException(status_code=500, detail=f"Failed to get session stats: {str(e)}")


@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service),
) -> Dict[str, Any]:
    """Clear all attribution data for a session."""
    try:
        success = await attribution_service.clear_session(session_id)
        return {
            "session_id": session_id,
            "cleared": success,
            "message": "Session cleared successfully" if success else "Failed to clear session",
        }
    except Exception as e:
        logger.exception("Error clearing session")
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}")


@router.post("/commentary")
async def generate_commentary(
    session_id: str = Form(...),
    period: Optional[str] = Form(None),
    context: Optional[str] = Form(None),
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service),
) -> Dict[str, Any]:
    """
    Generate professional attribution commentary for a session.
    Uses the commentary mode with institutional PM-grade output.
    """
    try:
        question = f"Generate {period} attribution commentary" if period else "Generate attribution commentary"
        response = await attribution_service.answer_question(session_id, question, mode="commentary", context=context)
        logger.info(f"Generated commentary for session {session_id}")
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error generating commentary")
        raise HTTPException(status_code=500, detail=f"Failed to generate commentary: {str(e)}")


@router.get("/health")
async def health_check(
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service),
) -> Dict[str, Any]:
    """Health check for attribution service dependencies."""
    try:
        health_status = {
            "attribution_service": "ok",
            "ollama": "unknown",
            "qdrant": "unknown",
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

        overall_healthy = all(v == "ok" for v in health_status.values())
        health_status["overall"] = "healthy" if overall_healthy else "degraded"
        return health_status

    except Exception as e:
        logger.exception("Health check error")
        return {"overall": "error", "message": str(e)}


@router.get("/collections")
async def list_collections(
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service),
) -> Dict[str, Any]:
    """List all available collections and their statistics."""
    try:
        # Get all session collections
        session_collections = await attribution_service.qdrant.list_session_collections()
        
        # Get collection statistics
        collections_info = []
        
        for session_id, collection_name in session_collections.items():
            try:
                # Get collection info
                collection_exists = await attribution_service.qdrant.collection_exists(collection_name)
                if collection_exists:
                    # Get collection stats
                    stats = await attribution_service.qdrant.get_collection_info(collection_name)
                    collections_info.append({
                        "session_id": session_id,
                        "collection_name": collection_name,
                        "points_count": stats.get("points_count", 0),
                        "vectors_count": stats.get("vectors_count", 0),
                        "status": "active"
                    })
            except Exception as e:
                logger.warning(f"Failed to get stats for collection {collection_name}: {e}")
                collections_info.append({
                    "session_id": session_id,
                    "collection_name": collection_name,
                    "points_count": 0,
                    "vectors_count": 0,
                    "status": "error"
                })
        
        return {
            "collections": collections_info,
            "total_collections": len(collections_info),
            "active_sessions": len(session_collections)
        }
        
    except Exception as e:
        logger.exception("Error listing collections")
        raise HTTPException(status_code=500, detail=f"Failed to list collections: {str(e)}")



@router.get("/examples")
async def get_usage_examples() -> Dict[str, Any]:
    """Get usage examples for the attribution RAG API."""
    return {
        "upload_example": {
            "endpoint": "POST /attribution/upload",
            "description": "Upload Excel attribution file",
            "curl_example": '''curl -X POST "http://localhost:8000/attribution/upload" \
  -F "file=@Q2_2025_Attribution.xlsx" \
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
            "curl_example": '''curl -X POST "http://localhost:8000/attribution/question" \
  -F "session_id=my_session_123" \
  -F "question=Which sectors had negative FX but positive selection?" \
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
            "curl_example": '''curl -X POST "http://localhost:8000/attribution/commentary" \
  -F "session_id=my_session_123" \
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


@router.post("/visualization")
async def generate_attribution_visualization(
    session_id: str = Form(...),
    prompt: str = Form(...),
    chart_type: Optional[str] = Form(None),
    attribution_service: PerformanceAttributionService = Depends(get_attribution_service),
) -> Dict[str, Any]:
    """
    Generate AI-powered visualizations based on attribution data.
    
    Args:
        session_id: The attribution session ID
        prompt: Natural language description of the desired visualization
        chart_type: Optional preferred chart type (bar, line, pie, scatter, table)
        
    Returns:
        Chart data and metadata for rendering
    """
    try:
        logger.info(f"Generating visualization for session {session_id} with prompt: {prompt}")
        
        if not session_id or not session_id.strip():
            raise HTTPException(status_code=400, detail="Session ID is required")
        
        if not prompt or not prompt.strip():
            raise HTTPException(status_code=400, detail="Visualization prompt is required")
        
        # Use the enhanced attribution service to fetch fresh data from Qdrant
        result = await attribution_service.generate_visualization(
            session_id=session_id.strip(),
            prompt=prompt.strip(),
            preferred_chart_type=chart_type
        )
        
        return {
            "status": "success",
            "session_id": session_id,
            "title": result.get("title", "Generated Visualization"),
            "type": result.get("type", "bar"),
            "description": result.get("description"),
            "data": result.get("data"),
            "raw_data": result.get("raw_data"),
            "headers": result.get("headers"),
            "prompt_used": result.get("prompt_used"),
            "data_source": result.get("data_source", "unknown")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating visualization for session {session_id}")
        raise HTTPException(status_code=500, detail=f"Failed to generate visualization: {str(e)}")


