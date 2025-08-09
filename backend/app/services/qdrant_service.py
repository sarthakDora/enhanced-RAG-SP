from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct, Filter, FieldCondition, 
    Match, Range, PayloadSelector, SearchRequest, FilterSelector
)
from typing import List, Dict, Any, Optional
import uuid
import asyncio
from datetime import datetime
import logging
import httpx
import json

from ..core.config import settings
from ..models.document import DocumentChunk, DocumentSearchRequest, DocumentSearchResult, DocumentMetadata

logger = logging.getLogger(__name__)

class QdrantService:
    def __init__(self):
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
            timeout=30
        )
        self.collection_name = settings.COLLECTION_NAME
        self.embedding_dimension = 768  # nomic-embed-text dimension
        
    async def health_check(self) -> bool:
        """Check if Qdrant is accessible"""
        try:
            collections = self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            raise

    async def create_collection(self) -> bool:
        """Create the collection if it doesn't exist"""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dimension,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.collection_name}")
            else:
                logger.info(f"Collection already exists: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    async def store_chunks(self, chunks: List[DocumentChunk]) -> bool:
        """Store document chunks in Qdrant"""
        try:
            # Ensure collection exists
            await self.create_collection()
            points = []
            for chunk in chunks:
                if not chunk.embedding:
                    logger.warning(f"Chunk {chunk.chunk_id} has no embedding, skipping")
                    continue
                
                logger.info(f"Processing chunk {chunk.chunk_id} with embedding length: {len(chunk.embedding) if chunk.embedding else 0}")
                
                # Validate embedding format
                if not isinstance(chunk.embedding, list) or not chunk.embedding:
                    logger.error(f"Invalid embedding format for chunk {chunk.chunk_id}: {type(chunk.embedding)}")
                    continue
                
                # Use minimal payload first to test basic insertion
                payload = {
                    "document_id": str(chunk.document_id),
                    "content": str(chunk.content)[:1000],  # Truncate to avoid large payloads
                    "chunk_index": int(chunk.chunk_index)
                }
                
                # Ensure chunk_id is converted to proper format for Qdrant
                chunk_id_str = str(chunk.chunk_id)
                
                # Ensure vector is properly formatted as list of floats
                embedding_vector = [float(x) for x in chunk.embedding]
                
                # Use the most basic point format
                point = PointStruct(
                    id=chunk_id_str,
                    vector=embedding_vector,
                    payload=payload
                )
                points.append(point)
            
            if points:
                # Use REST API directly since Python client has format issues
                try:
                    await self._upsert_via_rest_api(points)
                    logger.info(f"Successfully stored {len(points)} chunks in Qdrant via REST API")
                except Exception as e:
                    logger.error(f"Failed to store chunks in Qdrant: {e}")
                    raise
            
            return True
        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            raise

    async def _upsert_via_rest_api(self, points: List[PointStruct]) -> bool:
        """Upsert points using REST API directly with correct format"""
        # Convert PointStruct objects to the format expected by Qdrant REST API
        points_data = []
        for point in points:
            point_dict = {
                "id": str(point.id),  # Ensure ID is string
                "vector": list(point.vector),  # Ensure vector is list
                "payload": dict(point.payload) if point.payload else {}  # Ensure payload is dict
            }
            points_data.append(point_dict)
        
        # Use the batch upsert endpoint which seems to work better
        request_body = {"points": points_data}
        
        # Make HTTP request to the correct endpoint
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Try the batch endpoint first
            response = await client.put(
                f"{settings.QDRANT_URL}/collections/{self.collection_name}/points/batch",
                json=request_body,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully upserted {len(points_data)} points via batch endpoint")
                return True
            else:
                # Try the regular points endpoint as fallback
                response = await client.put(
                    f"{settings.QDRANT_URL}/collections/{self.collection_name}/points",
                    json=request_body,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"Successfully upserted {len(points_data)} points via regular endpoint")
                    return True
                else:
                    logger.error(f"REST API upsert failed with status {response.status_code}: {response.text}")
                    raise Exception(f"REST API upsert failed: {response.status_code} - {response.text}")

    async def search_similar_chunks(
        self, 
        query_embedding: List[float], 
        search_request: DocumentSearchRequest,
        document_metadata: Dict[str, DocumentMetadata] = None
    ) -> List[DocumentSearchResult]:
        """Search for similar chunks with advanced filtering"""
        try:
            # Build filters
            filter_conditions = []
            
            if search_request.document_types:
                # This would require document_type in payload - we'll need to add this
                pass
            
            if search_request.fiscal_years:
                filter_conditions.append(
                    FieldCondition(
                        key="fiscal_year",
                        match=Match(any=search_request.fiscal_years)
                    )
                )
            
            if search_request.companies:
                filter_conditions.append(
                    FieldCondition(
                        key="company_name",
                        match=Match(any=search_request.companies)
                    )
                )
            
            if search_request.tags:
                filter_conditions.append(
                    FieldCondition(
                        key="tags",
                        match=Match(any=search_request.tags)
                    )
                )
            
            # Note: Confidence score filtering removed as it was causing search issues
            # The similarity_threshold is applied via score_threshold in the search call
            
            # Create filter
            search_filter = Filter(must=filter_conditions) if filter_conditions else None
            
            # Perform search
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=search_request.top_k,
                with_payload=True,
                score_threshold=search_request.similarity_threshold
            )
            
            # Convert to DocumentSearchResult
            results = []
            for result in search_results:
                try:
                    payload = result.payload
                    if not payload:
                        logger.warning(f"Empty payload for result {result.id}")
                        continue
                    
                    # Get document metadata (would need to be passed or fetched)
                    doc_metadata = None
                    if document_metadata and "document_id" in payload:
                        doc_metadata = document_metadata.get(payload["document_id"])
                    
                    # Create default metadata if none exists
                    if doc_metadata is None:
                        from ..models.document import DocumentMetadata, DocumentType
                        from datetime import datetime
                        doc_metadata = DocumentMetadata(
                            filename=payload.get("filename", f"document_{payload.get('document_id', 'unknown')[:8]}.txt"),
                            file_size=payload.get("file_size", 1000),  # Default size
                            file_type=payload.get("file_type", ".txt"),
                            document_type=DocumentType.OTHER,  # Use enum
                            upload_timestamp=datetime.now(),  # Current timestamp
                            total_pages=payload.get("total_pages", 1),
                            total_chunks=payload.get("total_chunks", 1),
                            has_financial_data=payload.get("has_financial_data", False),
                            confidence_score=payload.get("confidence_score", result.score)
                        )
                    
                    search_result = DocumentSearchResult(
                        chunk_id=str(result.id),
                        document_id=payload.get("document_id", "unknown"),
                        content=payload.get("content", ""),
                        score=result.score,
                        confidence_level=self._get_confidence_level(result.score),
                        document_metadata=doc_metadata,
                        chunk_metadata={
                            "page_number": payload.get("page_number", 1),
                            "chunk_type": payload.get("chunk_type", "text"),
                            "section_title": payload.get("section_title", ""),
                            "subsection_title": payload.get("subsection_title", ""),
                            "contains_financial_data": payload.get("contains_financial_data", False),
                            "financial_keywords": payload.get("financial_keywords", []),
                            "confidence_score": payload.get("confidence_score", result.score)
                        },
                        page_number=payload.get("page_number", 1),
                        section_title=payload.get("section_title", "")
                    )
                    results.append(search_result)
                except Exception as e:
                    logger.error(f"Failed to process search result {result.id}: {e}")
                    continue
            
            logger.info(f"Found {len(results)} similar chunks")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search chunks: {e}")
            raise

    def _get_confidence_level(self, score: float) -> str:
        """Convert similarity score to confidence level"""
        if score >= 0.8:
            return "high"
        elif score >= 0.6:
            return "medium"
        else:
            return "low"

    async def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific chunk by ID"""
        try:
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[chunk_id],
                with_payload=True,
                with_vectors=True
            )
            
            if result:
                return {
                    "id": result[0].id,
                    "payload": result[0].payload,
                    "vector": result[0].vector
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get chunk {chunk_id}: {e}")
            return None

    async def delete_document_chunks(self, document_id: str) -> bool:
        """Delete all chunks for a specific document"""
        try:
            # Use REST API directly to avoid typing issues
            filter_data = {
                "filter": {
                    "must": [
                        {
                            "key": "document_id",
                            "match": {"value": document_id}
                        }
                    ]
                }
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{settings.QDRANT_URL}/collections/{self.collection_name}/points/delete",
                    json=filter_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code in [200, 202]:
                    logger.info(f"Deleted chunks for document: {document_id}")
                    return True
                else:
                    logger.error(f"Failed to delete chunks: {response.status_code} - {response.text}")
                    raise Exception(f"Failed to delete chunks: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"Failed to delete chunks for document {document_id}: {e}")
            raise

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "total_points": info.points_count,
                "indexed_points": info.indexed_vectors_count,
                "status": info.status,
                "optimizer_status": info.optimizer_status,
                "vectors_config": {
                    "size": info.config.params.vectors.size,
                    "distance": info.config.params.vectors.distance
                }
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            raise

    async def get_all_points(self) -> List[Dict[str, Any]]:
        """Get all points from the collection"""
        try:
            # Scroll through all points in the collection
            points = []
            offset = None
            limit = 100  # Process in batches
            
            while True:
                scroll_result = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=limit,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False  # We don't need vectors for metadata reload
                )
                
                if not scroll_result[0]:  # No more points
                    break
                
                for point in scroll_result[0]:
                    points.append({
                        "id": str(point.id),
                        "payload": point.payload
                    })
                
                # Get next offset
                if len(scroll_result[0]) < limit:
                    break
                    
                offset = scroll_result[1]  # Next offset
            
            logger.info(f"Retrieved {len(points)} points from collection")
            return points
            
        except Exception as e:
            logger.error(f"Failed to get all points: {e}")
            return []