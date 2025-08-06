from typing import List, Dict, Any, Optional
import numpy as np
import logging
from datetime import datetime
import re

from ..models.document import DocumentSearchResult, DocumentSearchRequest
from ..core.config import settings

logger = logging.getLogger(__name__)

class MultiStrategyReranker:
    """
    Advanced reranking system with multiple strategies for financial documents
    """
    
    def __init__(self):
        self.strategies = {
            'semantic': self._semantic_rerank,
            'metadata': self._metadata_rerank,
            'financial': self._financial_rerank,
            'hybrid': self._hybrid_rerank
        }
        
        # Financial relevance keywords with weights
        self.financial_keywords = {
            'high_priority': {
                'revenue': 1.0, 'profit': 1.0, 'ebitda': 1.0, 'income': 0.9,
                'assets': 0.9, 'liabilities': 0.9, 'equity': 0.9, 'cash flow': 1.0,
                'performance': 0.8, 'attribution': 1.0, 'benchmark': 0.8,
                'roe': 0.9, 'roa': 0.9, 'debt to equity': 0.8
            },
            'medium_priority': {
                'quarter': 0.7, 'annual': 0.7, 'fiscal': 0.7, 'compliance': 0.7,
                'regulation': 0.6, 'audit': 0.6, 'risk': 0.6, 'volatility': 0.6,
                'portfolio': 0.7, 'fund': 0.7, 'investment': 0.7
            },
            'low_priority': {
                'company': 0.5, 'corporation': 0.5, 'business': 0.4,
                'market': 0.5, 'industry': 0.5, 'sector': 0.5
            }
        }
        
    async def rerank_results(
        self, 
        results: List[DocumentSearchResult], 
        search_request: DocumentSearchRequest,
        query: str
    ) -> List[DocumentSearchResult]:
        """
        Rerank search results using specified strategy
        """
        if not results or len(results) <= 1:
            return results
        
        strategy = search_request.reranking_strategy
        if strategy not in self.strategies:
            logger.warning(f"Unknown reranking strategy: {strategy}, using hybrid")
            strategy = 'hybrid'
        
        try:
            reranked_results = await self.strategies[strategy](results, search_request, query)
            
            # Limit to requested number of results
            final_results = reranked_results[:search_request.rerank_top_k]
            
            logger.info(f"Reranked {len(results)} results to {len(final_results)} using {strategy} strategy")
            return final_results
            
        except Exception as e:
            logger.error(f"Reranking failed with strategy {strategy}: {e}")
            # Fallback to original results
            return results[:search_request.rerank_top_k]

    async def _semantic_rerank(
        self, 
        results: List[DocumentSearchResult], 
        search_request: DocumentSearchRequest,
        query: str
    ) -> List[DocumentSearchResult]:
        """Rerank based on semantic similarity and content relevance"""
        
        # Calculate semantic scores
        for result in results:
            semantic_score = self._calculate_semantic_score(result.content, query)
            result.rerank_score = semantic_score
        
        # Sort by rerank score
        return sorted(results, key=lambda x: x.rerank_score or 0, reverse=True)

    async def _metadata_rerank(
        self, 
        results: List[DocumentSearchResult], 
        search_request: DocumentSearchRequest,
        query: str
    ) -> List[DocumentSearchResult]:
        """Rerank based on document metadata relevance"""
        
        for result in results:
            metadata_score = self._calculate_metadata_score(result, search_request)
            result.rerank_score = metadata_score
        
        return sorted(results, key=lambda x: x.rerank_score or 0, reverse=True)

    async def _financial_rerank(
        self, 
        results: List[DocumentSearchResult], 
        search_request: DocumentSearchRequest,
        query: str
    ) -> List[DocumentSearchResult]:
        """Rerank based on financial content relevance"""
        
        for result in results:
            financial_score = self._calculate_financial_score(result, query)
            result.rerank_score = financial_score
        
        return sorted(results, key=lambda x: x.rerank_score or 0, reverse=True)

    async def _hybrid_rerank(
        self, 
        results: List[DocumentSearchResult], 
        search_request: DocumentSearchRequest,
        query: str
    ) -> List[DocumentSearchResult]:
        """Hybrid reranking combining multiple strategies"""
        
        weights = {
            'semantic': 0.3,
            'metadata': 0.2,
            'financial': 0.3,
            'recency': 0.1,
            'confidence': 0.1
        }
        
        for result in results:
            # Calculate individual scores
            semantic_score = self._calculate_semantic_score(result.content, query)
            metadata_score = self._calculate_metadata_score(result, search_request)
            financial_score = self._calculate_financial_score(result, query)
            recency_score = self._calculate_recency_score(result)
            confidence_score = self._calculate_confidence_score(result)
            
            # Combine scores with weights
            hybrid_score = (
                weights['semantic'] * semantic_score +
                weights['metadata'] * metadata_score +
                weights['financial'] * financial_score +
                weights['recency'] * recency_score +
                weights['confidence'] * confidence_score
            )
            
            result.rerank_score = hybrid_score
        
        return sorted(results, key=lambda x: x.rerank_score or 0, reverse=True)

    def _calculate_semantic_score(self, content: str, query: str) -> float:
        """Calculate semantic relevance score"""
        content_lower = content.lower()
        query_lower = query.lower()
        
        # Simple keyword matching with position weighting
        query_words = query_lower.split()
        content_words = content_lower.split()
        
        if not query_words or not content_words:
            return 0.0
        
        # Exact phrase matching
        phrase_bonus = 2.0 if query_lower in content_lower else 0.0
        
        # Word overlap score
        query_set = set(query_words)
        content_set = set(content_words)
        overlap = len(query_set.intersection(content_set))
        overlap_score = overlap / len(query_set) if query_set else 0.0
        
        # Position weighting (earlier occurrences get higher scores)
        position_score = 0.0
        for word in query_words:
            if word in content_lower:
                position = content_lower.find(word)
                # Score decreases with position
                position_score += max(0, 1 - (position / len(content_lower)))
        
        position_score = position_score / len(query_words) if query_words else 0.0
        
        # Length penalty for very short chunks
        length_factor = min(1.0, len(content_words) / 50)
        
        total_score = (
            phrase_bonus * 0.4 +
            overlap_score * 0.4 +
            position_score * 0.2
        ) * length_factor
        
        return min(1.0, total_score)

    def _calculate_metadata_score(
        self, 
        result: DocumentSearchResult, 
        search_request: DocumentSearchRequest
    ) -> float:
        """Calculate metadata relevance score"""
        score = 0.0
        
        if not result.document_metadata:
            return 0.1
        
        # Document type relevance
        if search_request.document_types:
            if result.document_metadata.document_type in search_request.document_types:
                score += 0.3
        else:
            score += 0.1  # Baseline for no specific type filter
        
        # Fiscal year relevance
        if search_request.fiscal_years and result.document_metadata.fiscal_year:
            if result.document_metadata.fiscal_year in search_request.fiscal_years:
                score += 0.2
        
        # Company relevance
        if search_request.companies and result.document_metadata.company_name:
            if any(company.lower() in result.document_metadata.company_name.lower() 
                   for company in search_request.companies):
                score += 0.2
        
        # Tag relevance
        if search_request.tags and result.document_metadata.tags:
            tag_overlap = set(search_request.tags).intersection(set(result.document_metadata.tags))
            if tag_overlap:
                score += 0.2 * (len(tag_overlap) / len(search_request.tags))
        
        # Financial data bonus
        if result.document_metadata.has_financial_data:
            score += 0.1
        
        return min(1.0, score)

    def _calculate_financial_score(self, result: DocumentSearchResult, query: str) -> float:
        """Calculate financial content relevance score"""
        content_lower = result.content.lower()
        query_lower = query.lower()
        
        score = 0.0
        
        # Check for financial keywords in content
        for priority, keywords in self.financial_keywords.items():
            for keyword, weight in keywords.items():
                if keyword in content_lower:
                    score += weight * 0.1
        
        # Check for financial keywords in query
        query_financial_weight = 0.0
        for priority, keywords in self.financial_keywords.items():
            for keyword, weight in keywords.items():
                if keyword in query_lower:
                    query_financial_weight += weight
        
        # Boost score if query contains financial terms
        if query_financial_weight > 0:
            score *= (1 + query_financial_weight * 0.2)
        
        # Monetary amount detection bonus
        monetary_pattern = r'\$[\d,]+(?:\.\d{2})?'
        if re.search(monetary_pattern, result.content):
            score += 0.2
        
        # Percentage detection bonus
        percentage_pattern = r'\d+(?:\.\d+)?%'
        if re.search(percentage_pattern, result.content):
            score += 0.1
        
        # Table content bonus
        if result.chunk_metadata.get('chunk_type') == 'table':
            score += 0.3
        
        # Financial data flag bonus
        if result.chunk_metadata.get('contains_financial_data'):
            score += 0.2
        
        return min(1.0, score)

    def _calculate_recency_score(self, result: DocumentSearchResult) -> float:
        """Calculate recency score based on document age"""
        if not result.document_metadata or not result.document_metadata.upload_timestamp:
            return 0.5
        
        # Score based on how recent the document is
        now = datetime.now()
        doc_age_days = (now - result.document_metadata.upload_timestamp).days
        
        # Decay function: newer documents get higher scores
        if doc_age_days <= 30:
            return 1.0
        elif doc_age_days <= 90:
            return 0.8
        elif doc_age_days <= 365:
            return 0.6
        else:
            return 0.4

    def _calculate_confidence_score(self, result: DocumentSearchResult) -> float:
        """Calculate confidence score based on various quality metrics"""
        base_score = result.score  # Original similarity score
        
        # Chunk confidence
        chunk_confidence = result.chunk_metadata.get('confidence_score', 0.5)
        
        # Page number bonus (earlier pages often more important)
        page_bonus = 1.0
        if result.page_number:
            if result.page_number <= 3:
                page_bonus = 1.2
            elif result.page_number <= 10:
                page_bonus = 1.0
            else:
                page_bonus = 0.9
        
        # Content length factor
        content_length = len(result.content.split())
        length_factor = 1.0
        if content_length < 10:
            length_factor = 0.7  # Very short chunks are less reliable
        elif content_length > 200:
            length_factor = 1.1  # Longer chunks might be more informative
        
        combined_score = base_score * chunk_confidence * page_bonus * length_factor
        return min(1.0, combined_score)

    def get_reranking_explanation(self, result: DocumentSearchResult) -> Dict[str, Any]:
        """Get explanation of why a result was ranked at its position"""
        explanation = {
            'original_score': result.score,
            'rerank_score': result.rerank_score,
            'factors': {
                'semantic_relevance': 'Content matches query semantically',
                'financial_content': 'Contains relevant financial information',
                'metadata_match': 'Document metadata aligns with search criteria',
                'recency': 'Document is recent/current',
                'confidence': 'High confidence in extraction quality'
            }
        }
        
        return explanation