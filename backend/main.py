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
    
    # Create shared document metadata store
    from typing import Dict, Any
    shared_metadata_store: Dict[str, Any] = {}
    shared_document_store: Dict[str, Any] = {}
    
    # Store services and shared stores in app state
    app.state.qdrant_service = qdrant_service
    app.state.ollama_service = ollama_service
    app.state.shared_metadata_store = shared_metadata_store
    app.state.shared_document_store = shared_document_store
    
    yield
    
    # Shutdown
    print("Shutting down Enhanced RAG System...")

app = FastAPI(
    title="Enhanced RAG System API",
    description="Advanced RAG system for financial document processing with multi-strategy reranking",
    version="1.0.0",
    lifespan=lifespan
)

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
        log_level="info"
    )