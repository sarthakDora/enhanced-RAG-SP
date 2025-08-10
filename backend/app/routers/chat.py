
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List
import json
import asyncio
import logging
from datetime import datetime

from ..models.chat import (
    ChatRequest, ChatResponse, ChatHistoryRequest, 
    ChatHistoryResponse, SessionListResponse
)
from ..services.chat_service import ChatService

router = APIRouter()
logger = logging.getLogger(__name__)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(json.dumps(message))
            except:
                self.disconnect(session_id)

manager = ConnectionManager()

async def get_chat_service(request: Request) -> ChatService:
    """Dependency to get chat service with auto-sync metadata"""
    ollama_service = request.app.state.ollama_service
    qdrant_service = request.app.state.qdrant_service
    chat_service = ChatService(ollama_service, qdrant_service)

    # Get shared metadata store
    shared_metadata_store = request.app.state.shared_metadata_store
    
    # Auto-sync: Always check Qdrant for documents and sync if needed
    try:
        logger.info("Checking Qdrant for documents to sync metadata cache...")
        all_points = await qdrant_service.get_all_points()
        
        if all_points:
            # Check if we need to sync (either empty cache or point count mismatch)
            qdrant_doc_count = len(set(point.get("payload", {}).get("document_id") for point in all_points if point.get("payload", {}).get("document_id")))
            cache_doc_count = len(shared_metadata_store)
            
            logger.info(f"Qdrant has {qdrant_doc_count} unique documents, cache has {cache_doc_count}")
            
            if cache_doc_count != qdrant_doc_count or not shared_metadata_store:
                logger.info("Re-syncing metadata cache from Qdrant...")
                # Clear existing cache and rebuild
                shared_metadata_store.clear()
                
                from ..models.document import DocumentMetadata
                from datetime import datetime
                
                document_chunks = {}
                for point in all_points:
                    payload = point.get("payload", {})
                    doc_id = payload.get("document_id")
                    if doc_id:
                        if doc_id not in document_chunks:
                            document_chunks[doc_id] = []
                        document_chunks[doc_id].append(payload)
                
                # Reconstruct metadata
                for doc_id, chunks in document_chunks.items():
                    try:
                        first_chunk = chunks[0]
                        doc_metadata = DocumentMetadata(
                            filename=first_chunk.get("filename", f"document_{doc_id[:8]}.txt"),
                            file_size=first_chunk.get("file_size", 1000),
                            file_type=first_chunk.get("file_type", ".txt"),
                            document_type=first_chunk.get("document_type", "other"),
                            upload_timestamp=first_chunk.get("upload_timestamp", datetime.now().isoformat()),
                            total_pages=first_chunk.get("total_pages", 1),
                            total_chunks=len(chunks),
                            has_financial_data=first_chunk.get("has_financial_data", False),
                            confidence_score=first_chunk.get("confidence_score", 0.5),
                            tags=first_chunk.get("tags", []),
                            custom_fields=first_chunk.get("custom_fields", {})
                        )
                        shared_metadata_store[doc_id] = doc_metadata
                    except Exception as e:
                        logger.error(f"Failed to sync metadata for document {doc_id}: {e}")
                        continue
                
                logger.info(f"Synced {len(shared_metadata_store)} documents from Qdrant")
            else:
                logger.info("Metadata cache is already in sync with Qdrant")
        else:
            logger.info("No documents found in Qdrant")
    except Exception as e:
        logger.error(f"Auto-sync failed: {e}")

    # Ensure all values in shared_metadata_store are DocumentMetadata objects
    from ..models.document import DocumentMetadata
    for k, v in list(shared_metadata_store.items()):
        if isinstance(v, dict):
            try:
                shared_metadata_store[k] = DocumentMetadata(**v)
            except Exception as e:
                # Remove invalid/corrupt metadata
                del shared_metadata_store[k]

    chat_service.document_metadata_cache = shared_metadata_store
    chat_service.agent_orchestrator.metadata_store = shared_metadata_store

    return chat_service

@router.get("/debug/metadata", response_model=Dict[str, Any])
async def debug_metadata_store(request: Request):
    """Debug endpoint to check shared metadata store"""
    try:
        shared_store = request.app.state.shared_metadata_store
        return {
            "shared_metadata_count": len(shared_store),
            "shared_metadata_keys": list(shared_store.keys()),
            "sample_metadata": list(shared_store.values())[0].__dict__ if shared_store else None
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug/chat-service-cache", response_model=Dict[str, Any])
async def debug_chat_service_cache(request: Request, chat_service: ChatService = Depends(get_chat_service)):
    """Debug endpoint to check chat service document metadata cache"""
    try:
        return {
            "chat_service_cache_count": len(chat_service.document_metadata_cache),
            "chat_service_cache_keys": list(chat_service.document_metadata_cache.keys()),
            "sample_cache_metadata": list(chat_service.document_metadata_cache.values())[0].__dict__ if chat_service.document_metadata_cache else None,
            "agent_orchestrator_cache_count": len(chat_service.agent_orchestrator.metadata_store) if hasattr(chat_service.agent_orchestrator, 'metadata_store') else "N/A"
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/debug/force-sync", response_model=Dict[str, Any])
async def force_sync_metadata(request: Request):
    """Force sync metadata from Qdrant to shared store"""
    try:
        shared_metadata_store = request.app.state.shared_metadata_store
        qdrant_service = request.app.state.qdrant_service
        
        # Clear existing cache
        shared_metadata_store.clear()
        
        # Force reload from Qdrant
        all_points = await qdrant_service.get_all_points()
        
        if all_points:
            from ..models.document import DocumentMetadata
            from datetime import datetime
            
            document_chunks = {}
            for point in all_points:
                payload = point.get("payload", {})
                doc_id = payload.get("document_id")
                if doc_id:
                    if doc_id not in document_chunks:
                        document_chunks[doc_id] = []
                    document_chunks[doc_id].append(payload)
            
            # Reconstruct metadata
            for doc_id, chunks in document_chunks.items():
                try:
                    first_chunk = chunks[0]
                    doc_metadata = DocumentMetadata(
                        filename=first_chunk.get("filename", f"document_{doc_id[:8]}.txt"),
                        file_size=first_chunk.get("file_size", 1000),
                        file_type=first_chunk.get("file_type", ".txt"),
                        document_type=first_chunk.get("document_type", "other"),
                        upload_timestamp=first_chunk.get("upload_timestamp", datetime.now().isoformat()),
                        total_pages=first_chunk.get("total_pages", 1),
                        total_chunks=len(chunks),
                        has_financial_data=first_chunk.get("has_financial_data", False),
                        confidence_score=first_chunk.get("confidence_score", 0.5),
                        tags=first_chunk.get("tags", []),
                        custom_fields=first_chunk.get("custom_fields", {})
                    )
                    shared_metadata_store[doc_id] = doc_metadata
                except Exception as e:
                    logger.error(f"Failed to sync metadata for document {doc_id}: {e}")
                    continue
        
        return {
            "message": "Force sync completed",
            "documents_synced": len(shared_metadata_store),
            "qdrant_points": len(all_points) if all_points else 0,
            "document_ids": list(shared_metadata_store.keys())
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/debug/auto-repair", response_model=Dict[str, Any])
async def auto_repair_system(request: Request):
    """Auto-repair common system issues"""
    try:
        fixes_applied = []
        qdrant_service = request.app.state.qdrant_service
        shared_metadata_store = request.app.state.shared_metadata_store
        
        # Fix 1: Ensure collection exists
        collection_exists = await qdrant_service.collection_exists()
        if not collection_exists:
            await qdrant_service.create_collection()
            fixes_applied.append("Created missing Qdrant collection")
        
        # Fix 2: Force metadata sync
        shared_metadata_store.clear()
        all_points = await qdrant_service.get_all_points()
        
        if all_points:
            from ..models.document import DocumentMetadata
            from datetime import datetime
            
            document_chunks = {}
            for point in all_points:
                payload = point.get("payload", {})
                doc_id = payload.get("document_id")
                if doc_id:
                    if doc_id not in document_chunks:
                        document_chunks[doc_id] = []
                    document_chunks[doc_id].append(payload)
            
            # Reconstruct metadata
            for doc_id, chunks in document_chunks.items():
                try:
                    first_chunk = chunks[0]
                    doc_metadata = DocumentMetadata(
                        filename=first_chunk.get("filename", f"document_{doc_id[:8]}.txt"),
                        file_size=first_chunk.get("file_size", 1000),
                        file_type=first_chunk.get("file_type", ".txt"),
                        document_type=first_chunk.get("document_type", "other"),
                        upload_timestamp=first_chunk.get("upload_timestamp", datetime.now().isoformat()),
                        total_pages=first_chunk.get("total_pages", 1),
                        total_chunks=len(chunks),
                        has_financial_data=first_chunk.get("has_financial_data", False),
                        confidence_score=first_chunk.get("confidence_score", 0.5),
                        tags=first_chunk.get("tags", []),
                        custom_fields=first_chunk.get("custom_fields", {})
                    )
                    shared_metadata_store[doc_id] = doc_metadata
                except Exception as e:
                    logger.error(f"Failed to reconstruct metadata for document {doc_id}: {e}")
                    continue
            
            fixes_applied.append(f"Synced {len(shared_metadata_store)} documents to metadata cache")
        
        # Fix 3: Test services
        try:
            ollama_service = request.app.state.ollama_service
            await ollama_service.health_check()
            fixes_applied.append("Verified Ollama connection")
        except Exception as e:
            fixes_applied.append(f"Ollama connection issue: {str(e)}")
        
        return {
            "message": "Auto-repair completed",
            "fixes_applied": fixes_applied,
            "documents_found": len(shared_metadata_store),
            "qdrant_points": len(all_points) if all_points else 0,
            "system_status": "ready" if shared_metadata_store else "needs_documents"
        }
        
    except Exception as e:
        return {"error": str(e), "fixes_applied": fixes_applied}

@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: Request,
    chat_request: ChatRequest
):
    """Send a message and get response"""
    try:
        chat_service = await get_chat_service(request)
        response = await chat_service.chat(chat_request)
        return response
        
    except Exception as e:
        logger.error(f"Chat message failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@router.post("/stream")
async def stream_message(
    request: Request,
    chat_request: ChatRequest
):
    """Stream chat response"""
    try:
        chat_service = await get_chat_service(request)
        
        async def generate_response():
            try:
                yield f"data: {json.dumps({'type': 'start', 'session_id': chat_request.session_id})}\n\n"
                
                response_chunks = []
                async for chunk in chat_service.chat_stream(chat_request):
                    response_chunks.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                # Send completion message
                full_response = ''.join(response_chunks)
                yield f"data: {json.dumps({'type': 'complete', 'content': full_response})}\n\n"
                
            except Exception as e:
                error_msg = f"Streaming failed: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
        
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except Exception as e:
        logger.error(f"Chat streaming failed: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat"""
    try:
        await manager.connect(websocket, session_id)
        logger.info(f"WebSocket connected for session: {session_id}")
        
        # Get services (this is a bit hacky for WebSocket, consider dependency injection)
        # In production, you'd want to properly inject these dependencies
        
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Send typing indicator
                await manager.send_message(session_id, {
                    "type": "typing",
                    "is_typing": True
                })
                
                # Create chat request
                chat_request = ChatRequest(
                    session_id=session_id,
                    message=message_data.get("message", ""),
                    use_rag=message_data.get("use_rag", True),
                    top_k=message_data.get("top_k", 10),
                    rerank_top_k=message_data.get("rerank_top_k", 3),
                    temperature=message_data.get("temperature", 0.1)
                )
                
                # Process with chat service (simplified for WebSocket)
                # Note: This is a simplified version. In production, you'd want proper service injection
                
                # Send response back
                await manager.send_message(session_id, {
                    "type": "response",
                    "message": "This is a WebSocket response placeholder. Implement full chat service integration.",
                    "sources": [],
                    "confidence_score": 0.8
                })
                
                # Stop typing indicator
                await manager.send_message(session_id, {
                    "type": "typing",
                    "is_typing": False
                })
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await manager.send_message(session_id, {
                    "type": "error",
                    "error": "Invalid JSON message"
                })
            except Exception as e:
                await manager.send_message(session_id, {
                    "type": "error", 
                    "error": str(e)
                })
    
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        manager.disconnect(session_id)
        logger.info(f"WebSocket disconnected for session: {session_id}")

@router.post("/sessions", response_model=Dict[str, str])
async def create_session(
    request: Request,
    title: str = "New Conversation",
    document_type: str = None
):
    """Create a new chat session"""
    try:
        chat_service = await get_chat_service(request)
        session = await chat_service.create_session(title, document_type)
        
        return {
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    limit: int = 50
):
    """List all chat sessions"""
    try:
        chat_service = await get_chat_service(request)
        response = await chat_service.list_sessions(limit)
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

@router.get("/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    request: Request,
    session_id: str,
    limit: int = 50,
    offset: int = 0
):
    """Get chat history for a session"""
    try:
        chat_service = await get_chat_service(request)
        
        history_request = ChatHistoryRequest(
            session_id=session_id,
            limit=limit,
            offset=offset
        )
        
        response = await chat_service.get_chat_history(history_request)
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chat history: {str(e)}")

@router.delete("/sessions/{session_id}", response_model=Dict[str, str])
async def delete_session(
    request: Request,
    session_id: str
):
    """Delete a chat session"""
    try:
        chat_service = await get_chat_service(request)
        success = await chat_service.delete_session(session_id)
        
        if success:
            return {"message": f"Session {session_id} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

@router.get("/sessions/{session_id}", response_model=Dict[str, Any])
async def get_session(
    request: Request,
    session_id: str
):
    """Get session details"""
    try:
        chat_service = await get_chat_service(request)
        session = await chat_service.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "message_count": len(session.messages),
            "is_active": session.is_active,
            "last_activity": session.last_activity.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")

@router.post("/sessions/{session_id}/title", response_model=Dict[str, str])
async def update_session_title(
    request: Request,
    session_id: str,
    title: str
):
    """Update session title"""
    try:
        chat_service = await get_chat_service(request)
        session = await chat_service.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session.title = title
        session.updated_at = datetime.now()
        
        return {"message": "Session title updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update session title: {str(e)}")

@router.post("/cleanup", response_model=Dict[str, Any])
async def cleanup_inactive_sessions(
    request: Request,
    max_age_hours: int = 24
):
    """Clean up inactive sessions"""
    try:
        chat_service = await get_chat_service(request)
        cleaned_count = await chat_service.cleanup_inactive_sessions(max_age_hours)
        
        return {
            "message": f"Cleaned up {cleaned_count} inactive sessions",
            "cleaned_sessions": cleaned_count,
            "max_age_hours": max_age_hours
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")