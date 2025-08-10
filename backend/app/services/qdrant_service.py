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
        
        # Category-specific collections
        self.category_collections = {
            "performance_docs": f"{settings.COLLECTION_NAME}_performance",
            "technical_docs": f"{settings.COLLECTION_NAME}_technical",
            "aum_docs": f"{settings.COLLECTION_NAME}_aum",
            "general_docs": f"{settings.COLLECTION_NAME}_general"
        }
        
    async def health_check(self) -> bool:
        """Check if Qdrant is accessible"""
        try:
            collections = self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            raise

    async def create_collection(self, collection_name: str = None) -> bool:
        """Create the collection if it doesn't exist"""
        try:
            target_collection = collection_name or self.collection_name
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if target_collection not in collection_names:
                self.client.create_collection(
                    collection_name=target_collection,
                    vectors_config=VectorParams(
                        size=self.embedding_dimension,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {target_collection}")
            else:
                logger.info(f"Collection already exists: {target_collection}")
            return True
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    async def create_category_collections(self) -> bool:
        """Create all category-specific collections"""
        try:
            # Create main collection
            await self.create_collection()
            
            # Create category-specific collections
            for category_key, collection_name in self.category_collections.items():
                await self.create_collection(collection_name)
                logger.info(f"Ensured category collection exists: {category_key} -> {collection_name}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to create category collections: {e}")
            return False

    def categorize_document(self, filename: str, content: str) -> str:
        """Automatically categorize document based on content and filename"""
        content_lower = content.lower()
        filename_lower = filename.lower()
        
        # Performance attribution keywords
        performance_keywords = [
            'performance', 'attribution', 'contributor', 'detractor', 'return', 'alpha',
            'benchmark', 'outperform', 'underperform', 'sector contribution', 'security selection',
            'allocation effect', 'portfolio return', 'relative performance', 'tracking error'
        ]
        
        # Technical analysis keywords
        technical_keywords = [
            'volatility', 'risk', 'var', 'sharpe', 'beta', 'correlation', 'drawdown',
            'technical analysis', 'indicators', 'momentum', 'trend', 'signal', 'pattern'
        ]
        
        # AUM keywords
        aum_keywords = [
            'assets under management', 'aum', 'fund size', 'capital flow', 'inflow', 'outflow',
            'net flow', 'fund growth', 'asset allocation', 'fund assets', 'total assets'
        ]
        
        # Count keyword matches
        performance_score = sum(1 for kw in performance_keywords if kw in content_lower or kw in filename_lower)
        technical_score = sum(1 for kw in technical_keywords if kw in content_lower or kw in filename_lower)
        aum_score = sum(1 for kw in aum_keywords if kw in content_lower or kw in filename_lower)
        
        # Determine category based on highest score
        scores = {
            'performance_docs': performance_score,
            'technical_docs': technical_score,
            'aum_docs': aum_score
        }
        
        max_category = max(scores, key=scores.get)
        max_score = scores[max_category]
        
        # If no strong signals, default to performance (most common)
        if max_score == 0:
            return 'performance_docs'
        
        return max_category

    async def store_chunks(self, chunks: List[DocumentChunk], document_metadata: 'DocumentMetadata' = None, category: str = None) -> bool:
        """Store document chunks in Qdrant"""
        try:
            print(f"DEBUG: store_chunks called with {len(chunks)} chunks")
            if chunks:
                logger.warning(f"DEBUG: First chunk ID: {chunks[0].chunk_id}, has embedding: {chunks[0].embedding is not None}")
                if chunks[0].embedding:
                    logger.warning(f"DEBUG: Embedding length: {len(chunks[0].embedding)}")
                logger.warning(f"DEBUG: Document metadata provided: {document_metadata is not None}")
            # Determine target collection
            if category:
                target_collection = self.category_collections.get(category, self.collection_name)
                # Ensure category collection exists
                await self.create_collection(target_collection)
            else:
                # Auto-categorize if not specified
                if document_metadata and chunks:
                    sample_content = ' '.join([chunk.content[:200] for chunk in chunks[:3]])
                    category = self.categorize_document(document_metadata.filename, sample_content)
                    target_collection = self.category_collections.get(category, self.collection_name)
                    await self.create_collection(target_collection)
                    logger.info(f"Auto-categorized document '{document_metadata.filename}' as '{category}'")
                else:
                    target_collection = self.collection_name
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
                
                # Store complete metadata in payload for proper document listing
                payload = {
                    "document_id": str(chunk.document_id),
                    "content": str(chunk.content),
                    "chunk_index": int(chunk.chunk_index),
                    "chunk_type": str(chunk.chunk_type) if chunk.chunk_type else "text",
                    "page_number": int(chunk.page_number) if chunk.page_number else 1,
                    "contains_financial_data": bool(chunk.contains_financial_data),
                    "confidence_score": float(chunk.confidence_score) if chunk.confidence_score else 0.5,
                    "section_title": str(chunk.section_title) if chunk.section_title else "",
                    "subsection_title": str(chunk.subsection_title) if chunk.subsection_title else "",
                    "financial_keywords": chunk.financial_keywords if chunk.financial_keywords else [],
                    # Add document metadata to each chunk for easier querying
                    "filename": document_metadata.filename if document_metadata else f"document_{str(chunk.document_id)[:8]}.txt",
                    "document_type": document_metadata.document_type if document_metadata else "other",
                    "upload_timestamp": document_metadata.upload_timestamp.isoformat() if document_metadata and hasattr(document_metadata, 'upload_timestamp') else datetime.now().isoformat(),
                    "total_pages": document_metadata.total_pages if document_metadata else 1,
                    "has_financial_data": document_metadata.has_financial_data if document_metadata else False,
                    "tags": document_metadata.tags if document_metadata else [],
                    "custom_fields": document_metadata.custom_fields if document_metadata and hasattr(document_metadata, 'custom_fields') else {}
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
                logger.warning(f"DEBUG: About to upsert {len(points)} points to collection {target_collection}")
                # Validate points before upserting
                valid_points = []
                for i, point in enumerate(points):
                    try:
                        # Check point structure
                        if not hasattr(point, 'id') or not hasattr(point, 'vector') or not hasattr(point, 'payload'):
                            logger.error(f"Point {i} missing required attributes")
                            continue
                        
                        # Check vector format
                        if not isinstance(point.vector, list) or len(point.vector) != self.embedding_dimension:
                            logger.error(f"Point {i} has invalid vector: type={type(point.vector)}, length={len(point.vector) if hasattr(point.vector, '__len__') else 'N/A'}")
                            continue
                        
                        # Check for NaN or infinite values in vector
                        if any(not isinstance(v, (int, float)) or not (-1e10 < v < 1e10) for v in point.vector):
                            logger.error(f"Point {i} has invalid vector values (NaN/Inf)")
                            continue
                        
                        valid_points.append(point)
                    except Exception as validation_error:
                        logger.error(f"Error validating point {i}: {validation_error}")
                        continue
                
                if not valid_points:
                    logger.error("No valid points to store after validation")
                    raise ValueError("All points failed validation")
                
                if len(valid_points) != len(points):
                    logger.warning(f"Only {len(valid_points)}/{len(points)} points passed validation")
                
                # Use Python client directly (REST API has compatibility issues with v1.7.0)
                try:
                    operation_info = self.client.upsert(
                        collection_name=target_collection,
                        points=valid_points
                    )
                    logger.info(f"Successfully stored {len(valid_points)} chunks in Qdrant via Python client - Status: {operation_info.status}")
                except Exception as e:
                    logger.error(f"Failed to store chunks in Qdrant: {type(e).__name__}: {str(e)}")
                    
                    # Additional debugging for common issues
                    if "vector" in str(e).lower():
                        logger.error("Vector-related error detected. Checking first valid point:")
                        if valid_points:
                            first_point = valid_points[0]
                            logger.error(f"  Point ID: {first_point.id}")
                            logger.error(f"  Vector type: {type(first_point.vector)}")
                            logger.error(f"  Vector length: {len(first_point.vector)}")
                            logger.error(f"  Vector sample: {first_point.vector[:5] if len(first_point.vector) >= 5 else first_point.vector}")
                            logger.error(f"  Expected dimension: {self.embedding_dimension}")
                    
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    raise
            
            return True
        except Exception as e:
            logger.error(f"Failed to store chunks: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise


    async def search_similar_chunks(
        self, 
        query_embedding: List[float], 
        search_request: DocumentSearchRequest,
        document_metadata: Dict[str, DocumentMetadata] = None,
        collection_name: str = None
    ) -> List[DocumentSearchResult]:
        """Search for similar chunks with advanced filtering across all collections"""
        try:
            all_results = []
            
            # If specific collection is requested, search only that collection
            if collection_name:
                target_collections = [collection_name]
            else:
                # Search across all collections (main + category-specific)
                target_collections = [self.collection_name] + list(self.category_collections.values())
            
            # Search each collection
            for target_collection in target_collections:
                # Check if collection exists first
                if not await self.collection_exists(target_collection):
                    logger.info(f"Collection {target_collection} does not exist, skipping")
                    continue
                    
                collection_results = await self._search_single_collection(
                    query_embedding, search_request, document_metadata, target_collection
                )
                all_results.extend(collection_results)
            
            # Sort all results by score and limit to top_k
            all_results.sort(key=lambda x: x.score, reverse=True)
            return all_results[:search_request.top_k]
            
        except Exception as e:
            logger.error(f"Failed to search chunks: {e}")
            raise

    async def _search_single_collection(
        self, 
        query_embedding: List[float], 
        search_request: DocumentSearchRequest,
        document_metadata: Dict[str, DocumentMetadata] = None,
        target_collection: str = None
    ) -> List[DocumentSearchResult]:
        """Search for similar chunks in a single collection"""
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
                collection_name=target_collection,
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
            # Check if collection exists first
            if not await self.collection_exists():
                logger.info(f"Collection {self.collection_name} does not exist, returning None")
                return None
                
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
            # Check if collection exists first
            if not await self.collection_exists():
                logger.info(f"Collection {self.collection_name} does not exist, nothing to delete")
                return True  # Consider it successful since there's nothing to delete
            
            # Use Python client to delete points by filter
            from qdrant_client.models import Filter, FieldCondition, Match
            
            delete_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=Match(value=document_id)
                    )
                ]
            )
            
            operation_info = self.client.delete(
                collection_name=self.collection_name,
                points_selector=delete_filter
            )
            
            logger.info(f"Deleted chunks for document: {document_id} - Status: {operation_info.status}")
            return True
                    
        except Exception as e:
            logger.error(f"Failed to delete chunks for document {document_id}: {e}")
            raise

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics from all collections"""
        try:
            all_collections = [self.collection_name] + list(self.category_collections.values())
            
            total_points = 0
            total_indexed = 0
            collection_details = {}
            
            for collection_name in all_collections:
                try:
                    if await self.collection_exists(collection_name):
                        info = self.client.get_collection(collection_name)
                        collection_details[collection_name] = {
                            "points": info.points_count,
                            "indexed": info.indexed_vectors_count,
                            "status": info.status
                        }
                        total_points += info.points_count
                        total_indexed += info.indexed_vectors_count
                    else:
                        collection_details[collection_name] = {
                            "points": 0,
                            "indexed": 0,
                            "status": "not_exists"
                        }
                except Exception as e:
                    logger.warning(f"Failed to get stats for collection {collection_name}: {e}")
                    collection_details[collection_name] = {
                        "points": 0,
                        "indexed": 0,
                        "status": "error"
                    }
            
            return {
                "total_points": total_points,
                "indexed_points": total_indexed,
                "status": "ok" if total_points > 0 else "empty",
                "collection_details": collection_details,
                "vectors_config": {
                    "size": 768,
                    "distance": "cosine"
                }
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "total_points": 0,
                "indexed_points": 0,
                "status": "error",
                "optimizer_status": "error",
                "vectors_config": {
                    "size": 0,
                    "distance": "cosine"
                }
            }

    async def collection_exists(self, collection_name: str = None) -> bool:
        """Check if the collection exists"""
        try:
            target_collection = collection_name or self.collection_name
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            return target_collection in collection_names
        except Exception as e:
            logger.error(f"Failed to check collection existence: {e}")
            return False

    async def get_all_points(self) -> List[Dict[str, Any]]:
        """Get all points from all collections"""
        try:
            all_collections = [self.collection_name] + list(self.category_collections.values())
            all_points = []
            
            for collection_name in all_collections:
                try:
                    # Check if collection exists first
                    if not await self.collection_exists(collection_name):
                        logger.info(f"Collection {collection_name} does not exist, skipping")
                        continue
                    
                    # Scroll through all points in this collection
                    points = []
                    offset = None
                    limit = 100  # Process in batches
                    
                    while True:
                        scroll_result = self.client.scroll(
                            collection_name=collection_name,
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
                                "payload": point.payload,
                                "collection": collection_name  # Add collection info
                            })
                        
                        # Get next offset
                        if len(scroll_result[0]) < limit:
                            break
                            
                        offset = scroll_result[1]  # Next offset
                    
                    all_points.extend(points)
                    logger.info(f"Retrieved {len(points)} points from collection {collection_name}")
                
                except Exception as e:
                    logger.warning(f"Failed to get points from collection {collection_name}: {e}")
                    continue
            
            logger.info(f"Retrieved {len(all_points)} total points from all collections")
            return all_points
            
        except Exception as e:
            logger.error(f"Failed to get all points: {e}")
            return []