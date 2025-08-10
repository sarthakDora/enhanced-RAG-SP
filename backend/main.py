import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from app.core.config import settings
from app.routers import documents, chat, health
from app.services.qdrant_service import QdrantService
from app.services.ollama_service import OllamaService

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting Enhanced RAG System for Financial Institution...")
    
    # Initialize services
    qdrant_service = QdrantService()
    ollama_service = OllamaService()
    
    # Verify connections
    try:
        await qdrant_service.health_check()
        print("Qdrant connection established")
    except Exception as e:
        print(f"Qdrant connection failed: {e}")
    
    try:
        await ollama_service.health_check()
        print("Ollama connection established")
    except Exception as e:
        print(f"Ollama connection failed: {e}")
    
    # Create single shared document store and metadata store
    from typing import Dict, Any
    shared_document_store: Dict[str, Any] = {}
    shared_metadata_store: Dict[str, Any] = {}

    # Store services and shared stores in app state
    app.state.qdrant_service = qdrant_service
    app.state.ollama_service = ollama_service
    app.state.shared_document_store = shared_document_store
    app.state.shared_metadata_store = shared_metadata_store
    
    # Auto-load existing metadata from Qdrant on startup
    try:
        print("Loading existing documents from Qdrant...")
        all_points = await qdrant_service.get_all_points()
        
        if all_points:
            # Group chunks by document_id and reconstruct metadata
            from app.models.document import DocumentMetadata
            from datetime import datetime
            import logging
            
            logger = logging.getLogger(__name__)
            document_chunks = {}
            
            for point in all_points:
                payload = point.get("payload", {})
                doc_id = payload.get("document_id")
                if doc_id:
                    if doc_id not in document_chunks:
                        document_chunks[doc_id] = []
                    document_chunks[doc_id].append(payload)
            
            # Reconstruct metadata for each document
            loaded_count = 0
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
                    loaded_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to load metadata for document {doc_id}: {e}")
                    continue
            
            print(f"Loaded {loaded_count} documents from Qdrant into memory cache")
        else:
            print("No existing documents found in Qdrant")
            
    except Exception as e:
        print(f"Failed to load existing documents from Qdrant: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down Enhanced RAG System...")

app = FastAPI(
    title="Enhanced RAG System API",
    description="Advanced RAG system for financial document processing with multi-strategy reranking",
    version="1.0.0",
    lifespan=lifespan,
    # Configure for large file uploads
    docs_url="/docs",
    redoc_url="/redoc"
)

# Custom middleware to handle large file uploads
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.status import HTTP_413_REQUEST_ENTITY_TOO_LARGE

class LargeFileMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check content length for file uploads
        content_length = request.headers.get("content-length")
        if content_length:
            content_length = int(content_length)
            if content_length > settings.MAX_REQUEST_SIZE:
                max_size_mb = settings.MAX_REQUEST_SIZE / (1024 * 1024)
                current_size_mb = content_length / (1024 * 1024)
                return JSONResponse(
                    status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "detail": f"Request too large ({current_size_mb:.1f}MB). Maximum allowed size is {max_size_mb:.0f}MB"
                    }
                )
        
        response = await call_next(request)
        return response

app.add_middleware(LargeFileMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

@app.get("/")
async def root():
    return {
        "message": "Enhanced RAG System API for Financial Institution",
        "version": "1.0.0",
        "status": "running"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info",
        # Configure for large file uploads
        limit_max_requests=1000,
        limit_concurrency=100,
        timeout_keep_alive=30,
        # Additional timeout settings for large files
        timeout_notify=300,  # 5 minutes for notifications
        h11_max_incomplete_event_size=1073741824,  # 1GB for large uploads
        # Override the default body size limit
        server_header=False,
        date_header=False,
        # Use asyncio loop for better memory handling
        loop="asyncio"
    )