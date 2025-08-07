from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Form, Depends
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import os
import uuid
import shutil
import asyncio
from datetime import datetime

from ..models.document import (
    DocumentType, DocumentUpload, DocumentSearchRequest, 
    DocumentSearchResponse, Document, DocumentMetadata
)
from ..services.document_processor import FinancialDocumentProcessor
from ..services.reranking_service import MultiStrategyReranker
from ..core.config import settings

router = APIRouter()

# Note: Using shared stores from app state (initialized in main.py)

async def get_document_processor(request: Request) -> FinancialDocumentProcessor:
    """Dependency to get document processor"""
    ollama_service = request.app.state.ollama_service
    return FinancialDocumentProcessor(ollama_service)

@router.post("/upload", response_model=Dict[str, Any])
async def upload_documents(
    request: Request,
    files: List[UploadFile] = File(...),
    document_type: DocumentType = Form(DocumentType.OTHER),
    tags: Optional[str] = Form(None),
    processor: FinancialDocumentProcessor = Depends(get_document_processor)
):
    """Upload and process multiple financial documents"""
    try:
        uploaded_docs = []
        
        for file in files:
            # Validate file
            if not file.filename:
                continue
                
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension[1:] not in settings.allowed_extensions_list:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file type: {file_extension}"
                )
            
            # Check file size
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset to beginning
            
            if file_size > settings.MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} too large. Max size: {settings.MAX_FILE_SIZE} bytes"
                )
            
            # Save file
            file_id = str(uuid.uuid4())
            file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{file.filename}")
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Process document
            try:
                # Parse tags
                tag_list = []
                if tags:
                    tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
                
                # Additional metadata
                additional_metadata = {
                    'tags': tag_list,
                    'file_id': file_id
                }
                
                # Process the document
                document = await processor.process_document(
                    file_path, document_type, additional_metadata
                )
                
                # Store in Qdrant
                qdrant_service = request.app.state.qdrant_service
                await qdrant_service.store_chunks(document.chunks)
                
                # Store in shared memory stores (use database in production)
                document_store = request.app.state.shared_document_store
                metadata_store = request.app.state.shared_metadata_store
                document_store[document.document_id] = document
                metadata_store[document.document_id] = document.metadata
                
                uploaded_docs.append({
                    "document_id": document.document_id,
                    "filename": file.filename,
                    "status": "processed",
                    "chunks": len(document.chunks),
                    "metadata": {
                        "document_type": document.metadata.document_type,
                        "total_pages": document.metadata.total_pages,
                        "has_financial_data": document.metadata.has_financial_data,
                        "confidence_score": document.metadata.confidence_score
                    }
                })
                
            except Exception as e:
                # Clean up file if processing failed
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                uploaded_docs.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "message": f"Processed {len(uploaded_docs)} documents",
            "documents": uploaded_docs,
            "total_successful": len([doc for doc in uploaded_docs if doc.get("status") == "processed"])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")

@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(
    request: Request,
    search_request: DocumentSearchRequest
):
    """Search for documents using RAG"""
    try:
        start_time = datetime.now()
        
        # Get services
        ollama_service = request.app.state.ollama_service
        qdrant_service = request.app.state.qdrant_service
        reranker = MultiStrategyReranker()
        
        # Generate query embedding
        query_embedding = await ollama_service.generate_embedding(search_request.query)
        
        # Search in Qdrant
        metadata_store = request.app.state.shared_metadata_store
        initial_results = await qdrant_service.search_similar_chunks(
            query_embedding, search_request, metadata_store
        )
        
        # Apply reranking if requested
        final_results = initial_results
        if search_request.use_reranking and initial_results:
            final_results = await reranker.rerank_results(
                initial_results, search_request, search_request.query
            )
        
        # Calculate search time
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Build response
        response = DocumentSearchResponse(
            query=search_request.query,
            total_results=len(final_results),
            results=final_results,
            search_time_ms=search_time,
            reranking_used=search_request.use_reranking,
            filters_applied={
                "document_types": search_request.document_types,
                "fiscal_years": search_request.fiscal_years,
                "companies": search_request.companies,
                "tags": search_request.tags,
                "similarity_threshold": search_request.similarity_threshold
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/list", response_model=Dict[str, Any])
async def list_documents(request: Request):
    """List all uploaded documents"""
    try:
        # Get shared metadata store
        metadata_store = request.app.state.shared_metadata_store
        documents = []
        for doc_id, metadata in metadata_store.items():
            documents.append({
                "document_id": doc_id,
                "filename": metadata.filename,
                "document_type": metadata.document_type,
                "upload_timestamp": metadata.upload_timestamp,
                "total_pages": metadata.total_pages,
                "total_chunks": metadata.total_chunks,
                "has_financial_data": metadata.has_financial_data,
                "confidence_score": metadata.confidence_score,
                "tags": metadata.tags
            })
        
        # Sort by upload time (newest first)
        documents.sort(key=lambda x: x["upload_timestamp"], reverse=True)
        
        return {
            "documents": documents,
            "total_count": len(documents)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

@router.get("/{document_id}", response_model=Dict[str, Any])
async def get_document(document_id: str, request: Request):
    """Get document details"""
    try:
        document_store = request.app.state.shared_document_store
        if document_id not in document_store:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = document_store[document_id]
        
        return {
            "document_id": document_id,
            "metadata": document.metadata.dict(),
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                    "chunk_type": chunk.chunk_type,
                    "page_number": chunk.page_number,
                    "contains_financial_data": chunk.contains_financial_data,
                    "confidence_score": chunk.confidence_score
                }
                for chunk in document.chunks
            ],
            "processing_status": document.processing_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")

@router.delete("/{document_id}", response_model=Dict[str, str])
async def delete_document(document_id: str, request: Request):
    """Delete a document and its chunks"""
    try:
        if document_id not in document_store:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from Qdrant
        qdrant_service = request.app.state.qdrant_service
        await qdrant_service.delete_document_chunks(document_id)
        
        # Delete from shared memory stores
        document_store = request.app.state.shared_document_store
        metadata_store = request.app.state.shared_metadata_store
        document = document_store.pop(document_id)
        metadata_store.pop(document_id)
        
        # Try to delete the uploaded file
        try:
            file_id = document.metadata.custom_fields.get('file_id')
            if file_id:
                file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{document.metadata.filename}")
                if os.path.exists(file_path):
                    os.remove(file_path)
        except Exception as e:
            # File deletion is not critical
            pass
        
        return {"message": f"Document {document_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@router.get("/{document_id}/chunks/{chunk_id}", response_model=Dict[str, Any])
async def get_chunk(document_id: str, chunk_id: str, request: Request):
    """Get specific chunk details"""
    try:
        qdrant_service = request.app.state.qdrant_service
        chunk_data = await qdrant_service.get_chunk_by_id(chunk_id)
        
        if not chunk_data:
            raise HTTPException(status_code=404, detail="Chunk not found")
        
        return {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "payload": chunk_data["payload"],
            "has_embedding": chunk_data["vector"] is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chunk: {str(e)}")

@router.get("/stats/overview", response_model=Dict[str, Any])
async def get_document_stats(request: Request):
    """Get document collection statistics"""
    try:
        document_store = request.app.state.shared_document_store
        total_docs = len(document_store)
        total_chunks = sum(doc.metadata.total_chunks for doc in document_store.values())
        
        # Document type breakdown
        type_counts = {}
        for doc in document_store.values():
            doc_type = doc.metadata.document_type
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        
        # Financial data stats
        docs_with_financial_data = sum(
            1 for doc in document_store.values() 
            if doc.metadata.has_financial_data
        )
        
        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "documents_with_financial_data": docs_with_financial_data,
            "document_types": type_counts,
            "average_chunks_per_document": total_chunks / total_docs if total_docs > 0 else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")