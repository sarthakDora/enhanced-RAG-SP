import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import json

from ..models.chat import ChatRequest, ChatResponse
from ..models.document import DocumentSearchRequest, DocumentSearchResult
from .ollama_service import OllamaService
from .qdrant_service import QdrantService

logger = logging.getLogger(__name__)

class QueryCategory(Enum):
    """Categories for query classification"""
    PERFORMANCE_ATTRIBUTION = "performance_attribution"
    TECHNICAL = "technical" 
    AUM = "aum"  # Assets Under Management
    GENERAL = "general"

class QueryCategorizationAgent:
    """LLM-powered agent for categorizing user queries"""
    
    def __init__(self, ollama_service: OllamaService):
        self.ollama_service = ollama_service
        
    def get_categorization_prompt(self, query: str) -> str:
        """Generate prompt for query categorization"""
        return f"""You are a financial query categorization specialist. Analyze the user query and classify it into one of these categories:

CATEGORIES:
1. "performance_attribution" - Questions about investment performance, returns, attribution analysis, top/worst performers, sector performance, portfolio analysis, contribution analysis, detractors, contributors
2. "technical" - Questions about risk metrics (Sharpe ratio, beta, alpha), volatility, VaR, technical analysis, market trends, charts, indicators, technical patterns, statistical measures
3. "aum" - Questions about assets under management, fund size, capital flows, inflows/outflows, asset allocation, fund growth
4. "general" - General financial knowledge questions, definitions, explanations that don't fit the above categories

USER QUERY: "{query}"

INSTRUCTIONS:
- Consider the intent and focus of the query
- Look for keywords that indicate the category
- If the query asks about "top contributors", "detractors", "performance", "attribution" → performance_attribution
- If the query asks about "Sharpe ratio", "volatility", "beta", "VaR", "risk metrics", "technical indicators", "charts" → technical  
- If the query asks about "fund size", "AUM", "assets", "capital flows", "inflows", "outflows" → aum
- If unsure or general knowledge question → general

Respond with ONLY the category name (no quotes, no explanation):"""

    async def categorize_query(self, query: str) -> Tuple[QueryCategory, float]:
        """Categorize a user query using LLM"""
        try:
            prompt = self.get_categorization_prompt(query)
            
            response = await self.ollama_service.generate_response(
                prompt=prompt,
                context="",
                temperature=0.1,  # Low temperature for consistent categorization
                max_tokens=10,
                system_prompt="You are a precise query categorization system. Respond only with the exact category name."
            )
            
            category_text = response["response"].strip().lower()
            confidence = 0.8  # Default confidence
            
            # Map response to enum
            category_mapping = {
                "performance_attribution": QueryCategory.PERFORMANCE_ATTRIBUTION,
                "technical": QueryCategory.TECHNICAL,
                "aum": QueryCategory.AUM,
                "general": QueryCategory.GENERAL
            }
            
            category = category_mapping.get(category_text, QueryCategory.GENERAL)
            
            logger.info(f"Query '{query}' categorized as: {category.value}")
            return category, confidence
            
        except Exception as e:
            logger.error(f"Query categorization failed: {e}")
            return QueryCategory.GENERAL, 0.5

class CategoryBasedContextRetriever:
    """Retrieves context from category-specific collections"""
    
    def __init__(self, qdrant_service: QdrantService, ollama_service: OllamaService):
        self.qdrant_service = qdrant_service
        self.ollama_service = ollama_service
        self.document_metadata_cache = {}
        
        # Map categories to collection names - use the actual collection names from QdrantService
        self.category_collections = {
            QueryCategory.PERFORMANCE_ATTRIBUTION: qdrant_service.category_collections["performance_docs"],
            QueryCategory.TECHNICAL: qdrant_service.category_collections["technical_docs"], 
            QueryCategory.AUM: qdrant_service.category_collections["aum_docs"],
            QueryCategory.GENERAL: qdrant_service.category_collections["general_docs"]
        }
        
    async def retrieve_context(self, query: str, category: QueryCategory, 
                             top_k: int = 10, similarity_threshold: float = 0.5) -> List[DocumentSearchResult]:
        """Retrieve relevant documents based on query and category"""
        target_collection = self.category_collections.get(category, "performance_docs")
        try:
            # Generate embedding for the query
            query_embedding = await self.ollama_service.generate_embedding(query)
            
            logger.info(f"Searching in collection: {target_collection} for category: {category.value}")
            
            # Create search request
            search_request = DocumentSearchRequest(
                query=query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                use_reranking=True,
                rerank_top_k=min(5, top_k // 2)
            )
            
            # Search in the category-specific collection
            # Check if the target collection exists, fallback to main collection if not
            if not await self.qdrant_service.collection_exists(target_collection):
                logger.info(f"Category collection {target_collection} doesn't exist, using main collection")
                target_collection = self.qdrant_service.collection_name
            else:
                logger.info(f"Using category-specific collection: {target_collection}")
            
            results = await self.qdrant_service.search_similar_chunks(
                query_embedding=query_embedding,
                search_request=search_request,
                document_metadata=self.document_metadata_cache,  # Use the metadata cache
                collection_name=target_collection
            )
            
            logger.info(f"Retrieved {len(results)} context documents for category {category.value}")
            return results
            
        except Exception as e:
            logger.error(f"Context retrieval failed for category {category.value}: {e}")
            return []

class ResponseGenerationAgent:
    """Generates detailed responses using structured prompts"""
    
    def __init__(self, ollama_service: OllamaService):
        self.ollama_service = ollama_service
        
    def get_category_specific_prompt(self, category: QueryCategory, query: str, context_docs: List[Dict]) -> str:
        """Generate category-specific system prompt"""
        
        base_prompt = """You are a specialized financial analysis AI assistant. Your role is to provide detailed, accurate responses based on the retrieved document context."""
        
        if category == QueryCategory.PERFORMANCE_ATTRIBUTION:
            return base_prompt + """

SPECIALIZATION: Performance Attribution Analysis
You are a buy-side performance attribution commentator for an institutional asset manager.
Your audience is portfolio managers and senior analysts.
Write concise, evidence-based commentary grounded ONLY in the provided context (tables, derived stats, and metadata).
Quantify every claim with percentage points (pp) and specify the period and level (total vs. sector).
Attribute drivers correctly (sector selection vs. security selection; include "total management/interaction" if provided).
Never invent data or security names. If information is missing, say so briefly.
Tone: crisp, professional, specific.

TASK FOR PERFORMANCE ATTRIBUTION QUERIES:
Using ONLY the context, draft attribution commentary for the requested period.
- Quantify each claim with precise pp deltas.
- Name top 2–3 positive contributors and 1–2 detractors and explain if the driver was sector selection, security selection, or both.
- Keep it data-first, no fluff.
- Do not show whole table inside response.
- Focus on actionable insights for portfolio managers.

Return clean markdown with sections:
- Executive summary (bullets)
- Total performance drivers  
- Sector-level highlights
- Risks/watch items (optional)

Rules:
- One decimal place for all pp values; keep +/- signs.
- Executive summary ~80–120 words; full note ~150–250 words.
- No JSON appendix or code blocks in response.

QUERY ANALYSIS: The user is asking about """ + query + """

CONTEXT ANALYSIS: Based on the retrieved documents, focus on performance metrics, attribution data, and ranking information with precise quantitative analysis."""

        elif category == QueryCategory.TECHNICAL:
            return base_prompt + """

SPECIALIZATION: Technical Analysis
You excel at technical analysis, market trends, risk metrics, volatility analysis, and technical indicators.

RESPONSE GUIDELINES:
1. Focus on technical patterns, indicators, and market analysis
2. Explain risk metrics and volatility measures clearly
3. Provide insights into market trends and technical signals
4. Use appropriate technical terminology
5. Reference charts, indicators, or technical data from documents

QUERY ANALYSIS: The user is asking about """ + query + """

CONTEXT ANALYSIS: Based on the retrieved documents, focus on technical analysis data, risk metrics, and market indicators."""

        elif category == QueryCategory.AUM:
            return base_prompt + """

SPECIALIZATION: Assets Under Management (AUM) Analysis
You excel at analyzing fund flows, asset allocation, capital movements, and AUM-related metrics.

RESPONSE GUIDELINES:
1. Focus on AUM figures, fund flows, and asset allocation data
2. Explain inflows, outflows, and net flows clearly
3. Provide insights into asset allocation changes over time
4. Reference specific fund sizes and growth metrics
5. Analyze trends in capital movements

QUERY ANALYSIS: The user is asking about """ + query + """

CONTEXT ANALYSIS: Based on the retrieved documents, focus on AUM data, fund flows, and asset allocation information."""

        else:  # GENERAL
            return base_prompt + """

SPECIALIZATION: General Financial Analysis
You provide comprehensive financial analysis across various topics using available document context.

RESPONSE GUIDELINES:
1. Provide accurate, well-structured responses based on document content
2. Explain financial concepts clearly when needed
3. Reference specific data points from the documents
4. Maintain professional financial analysis tone
5. Acknowledge limitations if information is not in the documents

QUERY ANALYSIS: The user is asking about """ + query + """

CONTEXT ANALYSIS: Based on the retrieved documents, provide a comprehensive response using available information."""

    async def generate_response(self, query: str, category: QueryCategory, 
                              context_docs: List[Dict], conversation_history: List[Dict] = None, 
                              custom_prompts: Dict[str, str] = None) -> Dict[str, Any]:
        """Generate a detailed response using category-specific structured prompts"""
        try:
            # Prepare context from documents
            context_text = self._build_structured_context(context_docs, category)
            
            # Get category-specific system prompt (using custom prompts if available)
            if custom_prompts and custom_prompts.get('system_prompt'):
                system_prompt = custom_prompts['system_prompt']
            else:
                system_prompt = self.get_category_specific_prompt(category, query, context_docs)
            
            # Build the main prompt
            main_prompt = f"""
DOCUMENT CONTEXT:
{context_text}

USER QUERY: {query}

INSTRUCTIONS:
1. Analyze the query in the context of the {category.value} specialization
2. Use the document context to provide a detailed, accurate response
3. Structure your response clearly with appropriate headings if needed
4. Include specific data points, figures, and references from the documents
5. If the query asks for rankings (like "top 3 detractors"), provide them clearly
6. Acknowledge if specific information is not available in the documents

Generate a comprehensive response:"""

            # Add conversation history if available
            if conversation_history:
                history_text = self._format_conversation_history(conversation_history[-6:])
                main_prompt = f"RECENT CONVERSATION:\n{history_text}\n\n{main_prompt}"
            
            # Generate response
            response = await self.ollama_service.generate_response(
                prompt=main_prompt,
                context="",  # Context is now in the main prompt
                temperature=0.7,
                max_tokens=800,
                system_prompt=system_prompt
            )
            
            return {
                "response": response["response"],
                "category": category.value,
                "context_docs_used": len(context_docs),
                "generation_method": "category_specific_structured",
                "prompt": response.get("prompt", "Prompt not available")
            }
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return {
                "response": "I encountered an error while generating the response. Please try rephrasing your question.",
                "category": category.value,
                "context_docs_used": 0,
                "generation_method": "error"
            }
    
    def _build_structured_context(self, context_docs: List[Dict], category: QueryCategory) -> str:
        """Build structured context based on category"""
        if not context_docs:
            return "No relevant documents found."
        
        context_parts = []
        
        for i, doc in enumerate(context_docs[:5], 1):  # Limit to top 5 docs
            filename = doc.get('filename', 'Unknown Document')
            content = doc.get('content', '')
            confidence = doc.get('confidence', 0.0)
            
            context_parts.append(f"""
Document {i}: {filename} (Relevance: {confidence:.2f})
Content: {content}
""")
        
        return "\n".join(context_parts)
    
    def _format_conversation_history(self, history: List[Dict]) -> str:
        """Format conversation history for context"""
        formatted = []
        for msg in history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:200]  # Limit length
            formatted.append(f"{role.title()}: {content}")
        return "\n".join(formatted)

class MultiAgentPipeline:
    """Orchestrates the multi-agent pipeline for enhanced RAG"""
    
    def __init__(self, ollama_service: OllamaService, qdrant_service: QdrantService):
        self.categorization_agent = QueryCategorizationAgent(ollama_service)
        self.context_retriever = CategoryBasedContextRetriever(qdrant_service, ollama_service)
        self.response_agent = ResponseGenerationAgent(ollama_service)
        self.document_metadata_cache = {}
        
    def set_document_metadata_cache(self, metadata_cache: Dict[str, Any]):
        """Set the document metadata cache from chat service"""
        self.document_metadata_cache = metadata_cache
        self.context_retriever.document_metadata_cache = metadata_cache
        
    async def process_query(self, query: str, conversation_history: List[Dict] = None, 
                          search_params: Dict = None, custom_prompts: Dict[str, str] = None) -> Dict[str, Any]:
        """Process query through the complete multi-agent pipeline"""
        start_time = time.time()
        pipeline_metadata = {
            "stages": [],
            "total_time": 0,
            "category": None,
            "context_docs_count": 0
        }
        
        try:
            # Stage 1: Query Categorization
            logger.info(f"Stage 1: Categorizing query - '{query}'")
            stage1_start = time.time()
            
            category, categorization_confidence = await self.categorization_agent.categorize_query(query)
            
            stage1_time = time.time() - stage1_start
            pipeline_metadata["stages"].append({
                "stage": "categorization",
                "time_ms": stage1_time * 1000,
                "result": category.value,
                "confidence": categorization_confidence
            })
            pipeline_metadata["category"] = category.value
            
            # Stage 2: Context Retrieval
            logger.info(f"Stage 2: Retrieving context for category - {category.value}")
            stage2_start = time.time()
            
            search_config = search_params or {}
            top_k = search_config.get('top_k', 10)
            similarity_threshold = search_config.get('similarity_threshold', 0.5)
            
            context_results = await self.context_retriever.retrieve_context(
                query=query,
                category=category,
                top_k=top_k,
                similarity_threshold=similarity_threshold
            )
            
            # Convert context results to dict format for response generation
            context_docs = []
            for result in context_results:
                context_docs.append({
                    'filename': result.document_metadata.filename if result.document_metadata else 'Unknown Document',
                    'content': result.content,
                    'confidence': result.score,
                    'document_type': result.document_metadata.document_type if result.document_metadata else None
                })
            
            stage2_time = time.time() - stage2_start
            pipeline_metadata["stages"].append({
                "stage": "context_retrieval", 
                "time_ms": stage2_time * 1000,
                "documents_found": len(context_docs),
                "category_collection": self.context_retriever.category_collections.get(category, "default")
            })
            pipeline_metadata["context_docs_count"] = len(context_docs)
            
            # Stage 3: Response Generation
            logger.info(f"Stage 3: Generating response using {len(context_docs)} context documents")
            stage3_start = time.time()
            
            response_data = await self.response_agent.generate_response(
                query=query,
                category=category,
                context_docs=context_docs,
                conversation_history=conversation_history,
                custom_prompts=custom_prompts
            )
            
            stage3_time = time.time() - stage3_start
            pipeline_metadata["stages"].append({
                "stage": "response_generation",
                "time_ms": stage3_time * 1000,
                "method": response_data.get("generation_method", "unknown")
            })
            
            # Compile final response
            total_time = time.time() - start_time
            pipeline_metadata["total_time"] = total_time * 1000
            
            final_response = {
                "answer": response_data["response"],
                "category": category.value,
                "categorization_confidence": categorization_confidence,
                "sources": [
                    {
                        "filename": doc['filename'],
                        "content": doc['content'][:200] + "...",
                        "confidence": doc['confidence'],
                        "document_type": doc.get('document_type', 'unknown')
                    }
                    for doc in context_docs
                ],
                "pipeline_metadata": pipeline_metadata,
                "confidence": min(0.95, categorization_confidence + 0.1) if context_docs else 0.3,
                "total_agents_used": 3,
                "processing_time": total_time,
                "prompt": response_data.get("prompt", "Prompt not available"),
                "agent_responses": [
                    {"agent": "categorization", "success": True, "confidence": categorization_confidence, "result": category.value},
                    {"agent": "context_retrieval", "success": len(context_docs) > 0, "confidence": 0.8, "documents": len(context_docs)},
                    {"agent": "response_generation", "success": True, "confidence": 0.9, "method": response_data.get("generation_method")}
                ]
            }
            
            logger.info(f"Multi-agent pipeline completed in {total_time:.2f}s - Category: {category.value}, Documents: {len(context_docs)}")
            return final_response
            
        except Exception as e:
            logger.error(f"Multi-agent pipeline failed: {e}")
            return {
                "answer": "I encountered an error while processing your query through the multi-agent pipeline. Please try again.",
                "category": "error",
                "categorization_confidence": 0.0,
                "sources": [],
                "pipeline_metadata": pipeline_metadata,
                "confidence": 0.1,
                "total_agents_used": 0,
                "processing_time": time.time() - start_time,
                "agent_responses": [{"agent": "error_handler", "success": False, "confidence": 0.1, "error": str(e)}]
            }