from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Form, Depends
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import os
import uuid
import shutil
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from ..models.document import (
    DocumentType, DocumentUpload, DocumentSearchRequest, 
    DocumentSearchResponse, Document, DocumentMetadata
)
from ..services.document_processor import FinancialDocumentProcessor
from ..services.reranking_service import MultiStrategyReranker
from ..services.performance_attribution_service import PerformanceAttributionService
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
    files: List[UploadFile] = File(..., description="Upload files (max 1GB each)"),
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
                max_size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
                current_size_mb = file_size / (1024 * 1024)
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{file.filename}' is too large ({current_size_mb:.1f}MB). Maximum allowed size is {max_size_mb:.0f}MB"
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
                print(f"DEBUG: About to process document: {file_path}")
                document = await processor.process_document(
                    file_path, document_type, additional_metadata
                )
                print(f"DEBUG: Document processed, chunks: {len(document.chunks)}")
                
                # Store in Qdrant
                print(f"DEBUG: About to store {len(document.chunks)} chunks in Qdrant")
                print(f"DEBUG: Document metadata type: {type(document.metadata)}")
                if document.chunks:
                    first_chunk = document.chunks[0]
                    print(f"DEBUG: First chunk ID: {first_chunk.chunk_id}")
                    print(f"DEBUG: First chunk has embedding: {first_chunk.embedding is not None}")
                    if first_chunk.embedding:
                        print(f"DEBUG: First chunk embedding length: {len(first_chunk.embedding)}")
                        print(f"DEBUG: First chunk embedding type: {type(first_chunk.embedding)}")
                        if len(first_chunk.embedding) > 0:
                            print(f"DEBUG: First few embedding values: {first_chunk.embedding[:3]}")
                
                qdrant_service = request.app.state.qdrant_service
                try:
                    await qdrant_service.store_chunks(document.chunks, document.metadata)
                    print(f"DEBUG: Chunks stored successfully")
                except Exception as storage_error:
                    print(f"DEBUG: Storage failed: {type(storage_error).__name__}: {str(storage_error)}")
                    import traceback
                    print(f"DEBUG: Full traceback: {traceback.format_exc()}")
                    raise  # Re-raise to maintain the original behavior
                
                # Documents are now stored only in Qdrant - no memory storage

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
        document_store = request.app.state.shared_document_store
        metadata_store = {doc_id: doc.metadata for doc_id, doc in document_store.items()}
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
    """List all uploaded documents - fetch fresh data from Qdrant"""
    try:
        # Get services
        qdrant_service = request.app.state.qdrant_service
        
        logger.info(f"Fetching documents from collection: {qdrant_service.collection_name}")
        
        # Check if any collection exists (main or category collections)
        main_collection_exists = await qdrant_service.collection_exists()
        
        # Check category collections
        category_collections_exist = []
        for category_name, collection_name in qdrant_service.category_collections.items():
            exists = await qdrant_service.collection_exists(collection_name)
            if exists:
                category_collections_exist.append(collection_name)
        
        logger.info(f"Main collection exists: {main_collection_exists}")
        logger.info(f"Category collections exist: {category_collections_exist}")
        
        # If no collections exist, return empty
        if not main_collection_exists and not category_collections_exist:
            return {
                "documents": [],
                "total_count": 0,
                "debug_info": {
                    "collection_name": qdrant_service.collection_name,
                    "collection_exists": False,
                    "category_collections": category_collections_exist,
                    "error": "No collections exist in Qdrant"
                }
            }
        
        # Get all points from Qdrant collection and category collections
        all_points = await qdrant_service.get_all_points()
        logger.info(f"Found {len(all_points) if all_points else 0} total points across all collections")
        
        if not all_points:
            return {
                "documents": [],
                "total_count": 0,
                "debug_info": {
                    "collection_name": qdrant_service.collection_name,
                    "collection_exists": collection_exists,
                    "points_found": 0,
                    "error": "No points found in any collection",
                    "collections_checked": [qdrant_service.collection_name] + list(qdrant_service.category_collections.values())
                }
            }
        
        # Group chunks by document_id and build document metadata
        document_chunks = {}
        for point in all_points:
            payload = point.get("payload", {})
            doc_id = payload.get("document_id")
            if doc_id:
                if doc_id not in document_chunks:
                    document_chunks[doc_id] = []
                document_chunks[doc_id].append(payload)
        
        # Build documents list from Qdrant data
        documents = []
        for doc_id, chunks in document_chunks.items():
            if not chunks:
                continue
                
            # Get metadata from the first chunk
            first_chunk = chunks[0]
            
            documents.append({
                "document_id": doc_id,
                "filename": first_chunk.get("filename", f"document_{doc_id[:8]}.txt"),
                "document_type": first_chunk.get("document_type", "other"),
                "upload_timestamp": first_chunk.get("upload_timestamp", datetime.now().isoformat()),
                "total_pages": first_chunk.get("total_pages", 1),
                "total_chunks": len(chunks),  # Actual count from Qdrant
                "has_financial_data": first_chunk.get("has_financial_data", False),
                "confidence_score": first_chunk.get("confidence_score", 0.5),
                "tags": first_chunk.get("tags", [])
            })
        
        # Sort by upload time (newest first)
        documents.sort(key=lambda x: x["upload_timestamp"], reverse=True)
        
        logger.info(f"Successfully found {len(documents)} documents")
        
        return {
            "documents": documents,
            "total_count": len(documents),
            "debug_info": {
                "collection_name": qdrant_service.collection_name,
                "main_collection_exists": main_collection_exists,
                "category_collections_exist": category_collections_exist,
                "points_found": len(all_points),
                "documents_processed": len(documents),
                "status": "success"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to list documents from Qdrant: {e}")
        # Return error details for debugging
        return {
            "documents": [],
            "total_count": 0,
            "debug_info": {
                "collection_name": getattr(request.app.state, 'qdrant_service', {}).collection_name if hasattr(request.app.state, 'qdrant_service') else "unknown",
                "collection_exists": False,
                "error": str(e),
                "status": "error"
            }
        }

@router.post("/generate-commentary/{document_id}", response_model=Dict[str, Any])
async def generate_attribution_commentary(document_id: str, request: Request):
    """Generate performance attribution commentary for a performance attribution document"""
    try:
        # Get services
        qdrant_service = request.app.state.qdrant_service
        ollama_service = request.app.state.ollama_service
        document_store = request.app.state.shared_document_store
        performance_service = PerformanceAttributionService()
        
        # Get document metadata directly from Qdrant
        all_points = await qdrant_service.get_all_points()
        document_metadata = None
        for point in all_points:
            payload = point.get("payload", {})
            if payload.get("document_id") == document_id:
                document_metadata = {
                    "document_id": document_id,
                    "filename": payload.get("filename", "unknown"),
                    "document_type": payload.get("document_type", "other")
                }
                break
        
        if not document_metadata:
            raise HTTPException(status_code=404, detail="Document not found in Qdrant")
        
        if document_metadata["document_type"] != "performance_attribution":
            raise HTTPException(
                status_code=400, 
                detail="Document must be a performance attribution document"
            )
        
        # Get all points for this document from Qdrant
        all_points = await qdrant_service.get_all_points()
        document_chunks = []
        for point in all_points:
            payload = point.get("payload", {})
            if payload.get("document_id") == document_id:
                document_chunks.append(payload)
        
        if not document_chunks:
            raise HTTPException(status_code=404, detail="Document chunks not found in Qdrant")
        
        # Reconstruct table data from chunks
        tables_data = []
        for chunk in document_chunks:
            if chunk.get("chunk_type") == "table" and "table_data" in chunk:
                tables_data.append(chunk["table_data"])
        
        # If no table data in chunks, try to get from original document
        if not tables_data and hasattr(document, 'content_data') and document.content_data.get('tables'):
            tables_data = document.content_data['tables']
        
        if not tables_data:
            return {
                "success": False,
                "error": "No table data found for performance attribution analysis",
                "document_id": document_id
            }
        
        # Extract attribution data
        attribution_data = performance_service.extract_attribution_data_from_tables(tables_data)
        if not attribution_data:
            return {
                "success": False,
                "error": "No attribution data could be extracted from tables",
                "document_id": document_id
            }
        
        # Parse the attribution data
        parsed_data = performance_service.parse_attribution_table(attribution_data)
        if not parsed_data:
            return {
                "success": False,
                "error": "Could not parse attribution table data",
                "document_id": document_id
            }
        
        # Generate commentary
        commentary = await performance_service.generate_commentary(parsed_data, ollama_service)
        
        return {
            "success": True,
            "document_id": document_id,
            "filename": document_metadata["filename"],
            "commentary": commentary,
            "attribution_data": {
                "period": parsed_data.get("period_name"),
                "portfolio_return": parsed_data.get("portfolio_total_return"),
                "benchmark_return": parsed_data.get("benchmark_total_return"),
                "active_return": parsed_data.get("total_active_return"),
                "top_contributors": len(parsed_data.get("top_contributors", [])),
                "top_detractors": len(parsed_data.get("top_detractors", []))
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate commentary for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate commentary: {str(e)}")

@router.get("/{document_id}", response_model=Dict[str, Any])
async def get_document(document_id: str, request: Request):
    """Get document details - fetch fresh data from Qdrant"""
    try:
        # Get services
        qdrant_service = request.app.state.qdrant_service
        
        # Get all points from Qdrant collection
        all_points = await qdrant_service.get_all_points()
        
        # Find chunks for this document
        document_chunks = []
        for point in all_points:
            payload = point.get("payload", {})
            if payload.get("document_id") == document_id:
                document_chunks.append({
                    "chunk_id": point.get("id"),
                    "content": payload.get("content", "")[:200] + "..." if len(payload.get("content", "")) > 200 else payload.get("content", ""),
                    "chunk_type": payload.get("chunk_type", "text"),
                    "page_number": payload.get("page_number", 1),
                    "contains_financial_data": payload.get("contains_financial_data", False),
                    "confidence_score": payload.get("confidence_score", 0.5),
                    "full_content": payload.get("content", "")
                })
        
        if not document_chunks:
            raise HTTPException(status_code=404, detail="Document not found in Qdrant")
        
        # Get metadata from the first chunk
        first_chunk_payload = None
        for point in all_points:
            payload = point.get("payload", {})
            if payload.get("document_id") == document_id:
                first_chunk_payload = payload
                break
        
        if not first_chunk_payload:
            raise HTTPException(status_code=404, detail="Document metadata not found")
        
        metadata = {
            "filename": first_chunk_payload.get("filename", f"document_{document_id[:8]}.txt"),
            "document_type": first_chunk_payload.get("document_type", "other"),
            "upload_timestamp": first_chunk_payload.get("upload_timestamp", datetime.now().isoformat()),
            "total_pages": first_chunk_payload.get("total_pages", 1),
            "total_chunks": len(document_chunks),
            "has_financial_data": first_chunk_payload.get("has_financial_data", False),
            "confidence_score": first_chunk_payload.get("confidence_score", 0.5),
            "tags": first_chunk_payload.get("tags", [])
        }
        
        return {
            "document_id": document_id,
            "metadata": metadata,
            "chunks": document_chunks,
            "processing_status": "processed"  # Assume processed if in Qdrant
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id} from Qdrant: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")

@router.delete("/{document_id}")
async def delete_document(document_id: str, request: Request):
    """Delete a document and its chunks"""
    try:
        # Get services from app state  
        qdrant_service = request.app.state.qdrant_service
        
        # Check if document exists in Qdrant
        all_points = await qdrant_service.get_all_points()
        document_found = False
        filename_for_file_deletion = None
        file_id_for_file_deletion = None
        
        # Check Qdrant
        for point in all_points:
            payload = point.get("payload", {})
            if payload.get("document_id") == document_id:
                document_found = True
                filename_for_file_deletion = payload.get("filename")
                file_id_for_file_deletion = payload.get("custom_fields", {}).get("file_id")
                break
        
        if not document_found:
            raise HTTPException(status_code=404, detail="Document not found")
        
        logger.info(f"Deleting document {document_id}")
        
        # Delete from Qdrant (this is the only storage now)
        await qdrant_service.delete_document_chunks(document_id)
        logger.info(f"Deleted document chunks from Qdrant for document {document_id}")
        
        # Try to delete the uploaded file
        try:
            if file_id_for_file_deletion and filename_for_file_deletion:
                file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id_for_file_deletion}_{filename_for_file_deletion}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Deleted file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file for document {document_id}: {e}")
            pass  # File deletion is not critical
        
        return {"message": f"Document {document_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
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
    """Get document collection statistics - fetch fresh data from Qdrant"""
    try:
        # Get services
        qdrant_service = request.app.state.qdrant_service
        
        # Get all points from Qdrant collection
        all_points = await qdrant_service.get_all_points()
        
        if not all_points:
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "documents_with_financial_data": 0,
                "document_types": {},
                "average_chunks_per_document": 0
            }
        
        # Group chunks by document_id and analyze
        document_chunks = {}
        type_counts = {}
        docs_with_financial_data = 0
        
        for point in all_points:
            payload = point.get("payload", {})
            doc_id = payload.get("document_id")
            if doc_id:
                if doc_id not in document_chunks:
                    document_chunks[doc_id] = []
                document_chunks[doc_id].append(payload)
        
        # Analyze documents
        for doc_id, chunks in document_chunks.items():
            if not chunks:
                continue
                
            # Get metadata from the first chunk
            first_chunk = chunks[0]
            
            # Document type breakdown
            doc_type = first_chunk.get("document_type", "other")
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
            
            # Financial data stats
            if first_chunk.get("has_financial_data", False):
                docs_with_financial_data += 1
        
        total_docs = len(document_chunks)
        total_chunks = len(all_points)
        
        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "documents_with_financial_data": docs_with_financial_data,
            "document_types": type_counts,
            "average_chunks_per_document": total_chunks / total_docs if total_docs > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats from Qdrant: {e}")
        # Fallback to empty stats
        return {
            "total_documents": 0,
            "total_chunks": 0,
            "documents_with_financial_data": 0,
            "document_types": {},
            "average_chunks_per_document": 0
        }

@router.get("/debug/clear-cache", response_model=Dict[str, Any])
async def clear_memory_cache(request: Request):
    """Clear in-memory document and metadata stores"""
    try:
        document_store = request.app.state.shared_document_store
        metadata_store = request.app.state.shared_metadata_store
        
        doc_count = len(document_store)
        meta_count = len(metadata_store)
        
        document_store.clear()
        metadata_store.clear()
        
        return {
            "message": "Memory cache cleared successfully",
            "documents_cleared": doc_count,
            "metadata_cleared": meta_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@router.get("/debug/cache-status", response_model=Dict[str, Any])
async def check_cache_status(request: Request):
    """Check what's in memory cache vs Qdrant"""
    try:
        document_store = request.app.state.shared_document_store
        metadata_store = request.app.state.shared_metadata_store
        qdrant_service = request.app.state.qdrant_service
        
        # Get Qdrant data
        qdrant_points = await qdrant_service.get_all_points()
        
        return {
            "memory_cache": {
                "documents_count": len(document_store),
                "metadata_count": len(metadata_store),
                "document_ids": list(metadata_store.keys())  # Fixed: should show metadata_store keys
            },
            "qdrant": {
                "total_points": len(qdrant_points),
                "unique_documents": len(set(point.get("payload", {}).get("document_id") for point in qdrant_points if point.get("payload", {}).get("document_id")))
            }
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug/qdrant-status", response_model=Dict[str, Any])
async def debug_qdrant_status(request: Request):
    """Debug endpoint to check Qdrant connection and collection status"""
    try:
        qdrant_service = request.app.state.qdrant_service
        
        # Test basic connection
        try:
            await qdrant_service.health_check()
            connection_status = "connected"
        except Exception as e:
            connection_status = f"failed: {str(e)}"
        
        # Check collection existence
        try:
            collection_exists = await qdrant_service.collection_exists()
        except Exception as e:
            collection_exists = f"error: {str(e)}"
        
        # Get point count from all collections
        try:
            stats = await qdrant_service.get_collection_stats()
            point_count = stats.get("total_points", 0)
            collection_details = stats.get("collection_details", {})
            print(f"DEBUG: stats = {stats}")  # Debug output
            # Try to get a sample point from any non-empty collection
            sample_point = None
            for collection_name, details in collection_details.items():
                if details.get("points", 0) > 0:
                    try:
                        all_points = await qdrant_service.get_all_points()  # This will need updating too
                        if all_points:
                            sample_point = all_points[0]
                            break
                    except:
                        continue
        except Exception as e:
            print(f"DEBUG: Exception in get_collection_stats: {e}")
            point_count = f"error: {str(e)}"
            sample_point = None
            collection_details = {}
            
        return {
            "qdrant_url": qdrant_service.client.rest_uri if hasattr(qdrant_service.client, 'rest_uri') else "unknown",
            "collection_name": qdrant_service.collection_name,
            "connection_status": connection_status,
            "collection_exists": collection_exists,
            "point_count": point_count,
            "collection_details": collection_details,
            "sample_point": sample_point
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug/delete-check/{document_id}", response_model=Dict[str, Any])
async def debug_delete_check(document_id: str, request: Request):
    """Debug what the delete endpoint would see for a specific document"""
    try:
        document_store = request.app.state.shared_document_store
        metadata_store = request.app.state.shared_metadata_store
        qdrant_service = request.app.state.qdrant_service
        
        # Check Qdrant
        all_points = await qdrant_service.get_all_points()
        qdrant_document_ids = []
        found_in_qdrant = False
        
        for point in all_points:
            payload = point.get("payload", {})
            point_doc_id = payload.get("document_id")
            if point_doc_id:
                qdrant_document_ids.append(point_doc_id)
                if point_doc_id == document_id:
                    found_in_qdrant = True
        
        return {
            "target_document_id": document_id,
            "found_in_qdrant": found_in_qdrant,
            "found_in_metadata_store": document_id in metadata_store,
            "found_in_document_store": document_id in document_store,
            "metadata_store_count": len(metadata_store),
            "metadata_store_keys": list(metadata_store.keys()),
            "qdrant_document_ids": qdrant_document_ids,
            "qdrant_total_points": len(all_points)
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/clear-category/{document_type}")
async def clear_documents_by_category(document_type: str, request: Request):
    """Clear all documents for a specific document type/category"""
    try:
        qdrant_service = request.app.state.qdrant_service
        
        # Determine target collection based on document type
        target_collection = None
        if document_type == "performance_attribution":
            target_collection = qdrant_service.category_collections["performance_docs"]
        elif document_type == "financial_report":
            target_collection = qdrant_service.category_collections["technical_docs"]
        elif document_type == "market_analysis":
            target_collection = qdrant_service.category_collections["aum_docs"]
        else:
            target_collection = qdrant_service.collection_name
        
        # Check if collection exists
        if not await qdrant_service.collection_exists(target_collection):
            return {
                "message": f"No {document_type} documents found - collection doesn't exist",
                "documents_cleared": 0,
                "collection": target_collection
            }
        
        # Get all points from the target collection
        all_points = await qdrant_service.get_all_points()
        points_in_collection = []
        
        # Filter points that belong to this collection and document type
        for point in all_points:
            payload = point.get("payload", {})
            if payload.get("document_type") == document_type:
                points_in_collection.append(point)
        
        if not points_in_collection:
            return {
                "message": f"No {document_type} documents found to clear",
                "documents_cleared": 0,
                "collection": target_collection
            }
        
        # Group by document_id to count documents
        document_ids = set()
        for point in points_in_collection:
            payload = point.get("payload", {})
            doc_id = payload.get("document_id")
            if doc_id:
                document_ids.add(doc_id)
        
        # Delete documents by document_id
        deleted_count = 0
        for doc_id in document_ids:
            try:
                await qdrant_service.delete_document_chunks(doc_id)
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete document {doc_id}: {e}")
        
        # Also try to recreate the collection to ensure it's clean
        try:
            await qdrant_service.create_collection(target_collection)
        except Exception as e:
            logger.warning(f"Failed to recreate collection {target_collection}: {e}")
        
        return {
            "message": f"Cleared {deleted_count} {document_type} documents",
            "documents_cleared": deleted_count,
            "collection": target_collection,
            "total_points_cleared": len(points_in_collection)
        }
        
    except Exception as e:
        logger.error(f"Failed to clear {document_type} documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear documents: {str(e)}")

@router.post("/reload-metadata", response_model=Dict[str, Any])
async def reload_metadata_from_qdrant(request: Request):
    """Reload document metadata from Qdrant into shared memory stores"""
    try:
        # Get services
        qdrant_service = request.app.state.qdrant_service
        document_store = request.app.state.shared_document_store
        metadata_store = request.app.state.shared_metadata_store
        
        # Get all points from Qdrant collection
        all_points = await qdrant_service.get_all_points()
        
        if not all_points:
            return {
                "message": "No documents found in Qdrant collection",
                "documents_loaded": 0,
                "metadata_loaded": 0
            }
        
        # Group chunks by document_id and reconstruct document metadata
        document_chunks = {}
        for point in all_points:
            payload = point.get("payload", {})
            doc_id = payload.get("document_id")
            if doc_id:
                if doc_id not in document_chunks:
                    document_chunks[doc_id] = []
                document_chunks[doc_id].append(payload)
        
        # Reconstruct documents and metadata
        loaded_docs = 0
        loaded_metadata = 0
        
        for doc_id, chunks in document_chunks.items():
            try:
                # Get the first chunk to extract document metadata
                first_chunk = chunks[0]
                
                # Create DocumentMetadata from the first chunk's metadata
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
                
                # Store in shared metadata store
                metadata_store[doc_id] = doc_metadata
                loaded_metadata += 1
                
                logger.info(f"Loaded metadata for document {doc_id}: {doc_metadata.filename}")
                
            except Exception as e:
                logger.error(f"Failed to load metadata for document {doc_id}: {e}")
                continue
        
        return {
            "message": f"Reloaded {loaded_metadata} document metadata from Qdrant",
            "documents_found_in_qdrant": len(document_chunks),
            "metadata_loaded": loaded_metadata,
            "total_chunks_found": len(all_points)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload metadata: {str(e)}")