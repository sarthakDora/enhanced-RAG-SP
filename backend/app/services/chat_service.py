import uuid
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, AsyncGenerator
import json

from ..models.chat import (
    ChatSession, ChatMessage, ChatRequest, ChatResponse,
    ChatHistoryRequest, ChatHistoryResponse, SessionListResponse
)
from ..models.document import DocumentSearchRequest, DocumentSearchResult
from ..core.config import settings
from .ollama_service import OllamaService
from .qdrant_service import QdrantService
from .reranking_service import MultiStrategyReranker
from .agent_orchestrator import MultiAgentOrchestrator

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, ollama_service: OllamaService, qdrant_service: QdrantService):
        self.ollama_service = ollama_service
        self.qdrant_service = qdrant_service
        self.reranker = MultiStrategyReranker()
        
        # Initialize multi-agent orchestrator
        self.agent_orchestrator = MultiAgentOrchestrator(
            ollama_service=ollama_service,
            qdrant_service=qdrant_service
        )
        
        # In-memory storage for sessions (in production, use a database)
        self.sessions: Dict[str, ChatSession] = {}
        self.document_metadata_cache: Dict[str, Any] = {}
        
        # Update orchestrator's metadata store reference
        self.agent_orchestrator.metadata_store = self.document_metadata_cache
        
    async def create_session(self, title: str = "New Conversation") -> ChatSession:
        """Create a new chat session"""
        session_id = str(uuid.uuid4())
        session = ChatSession(
            session_id=session_id,
            title=title,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            last_activity=datetime.now()
        )
        
        self.sessions[session_id] = session
        logger.info(f"Created new chat session: {session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get an existing chat session"""
        session = self.sessions.get(session_id)
        if session:
            session.last_activity = datetime.now()
        return session

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat request and generate response"""
        start_time = time.time()
        
        # Get or create session
        if request.session_id:
            session = await self.get_session(request.session_id)
            if not session:
                session = await self.create_session()
        else:
            session = await self.create_session()
        
        # Add user message to session
        user_message = ChatMessage(
            message_id=str(uuid.uuid4()),
            session_id=session.session_id,
            role="user",
            content=request.message,
            timestamp=datetime.now()
        )
        session.messages.append(user_message)
        
        try:
            logger.info(f"Processing chat request with multi-agent orchestrator - use_rag: {request.use_rag}")
            
            # Prepare context for multi-agent processing
            context = {
                "session_id": session.session_id,
                "conversation_history": [
                    {"role": msg.role, "content": msg.content}
                    for msg in session.messages[-10:]  # Last 10 messages
                    if msg.role in ['user', 'assistant']
                ],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "document_filters": request.document_filters,
                "user_preferences": getattr(request, 'user_preferences', {})
            }
            
            # TEMPORARY FIX: Use direct document retrieval instead of multi-agent system
            generation_start = time.time()
            
            # Perform direct document search for comparison
            if request.use_rag:
                try:
                    # Generate query embedding
                    logger.info(f"Generating embedding for query: '{request.message}'")
                    query_embedding = await self.ollama_service.generate_embedding(request.message)
                    logger.info(f"Generated embedding with {len(query_embedding)} dimensions")
                    
                    # Create search request
                    from ..models.document import DocumentSearchRequest
                    search_request = DocumentSearchRequest(
                        query=request.message,
                        top_k=request.top_k or 10,
                        similarity_threshold=request.similarity_threshold or 0.3,
                        use_reranking=True,
                        rerank_top_k=request.rerank_top_k or 3
                    )
                    logger.info(f"Search request: top_k={search_request.top_k}, threshold={search_request.similarity_threshold}")
                    
                    # Search documents directly using the metadata cache
                    logger.info(f"Metadata cache has {len(self.document_metadata_cache)} documents")
                    logger.info(f"Metadata cache keys: {list(self.document_metadata_cache.keys())}")
                    
                    search_results = await self.qdrant_service.search_similar_chunks(
                        query_embedding=query_embedding,
                        search_request=search_request,
                        document_metadata=self.document_metadata_cache
                    )
                    
                    logger.info(f"Direct search found {len(search_results)} documents")
                    if search_results:
                        logger.info(f"First result score: {search_results[0].score}")
                    else:
                        logger.warning("No search results returned from Qdrant service")
                    
                    # Generate RAG response using the existing method
                    if search_results:
                        context_documents = []
                        for source in search_results:
                            context_documents.append({
                                'filename': source.document_metadata.filename if source.document_metadata else 'Unknown Document',
                                'content': source.content,
                                'document_type': source.document_metadata.document_type if source.document_metadata else None,
                                'confidence': source.score
                            })
                        
                        # Get conversation history
                        conversation_history = [
                            {"role": msg.role, "content": msg.content}
                            for msg in session.messages[-10:]
                            if msg.role in ['user', 'assistant']
                        ]
                        
                        response_data = await self.ollama_service.generate_rag_response(
                            query=request.message,
                            context_documents=context_documents,
                            conversation_history=conversation_history,
                            temperature=request.temperature
                        )
                        
                        # Create mock agent response format
                        agent_response = {
                            "answer": response_data["response"],
                            "confidence": 0.8,
                            "sources": [
                                {
                                    "filename": doc['filename'],
                                    "content": doc['content'][:200] + "...",
                                    "confidence": doc['confidence'],
                                    "document_type": doc.get('document_type', 'unknown')
                                }
                                for doc in context_documents
                            ],
                            "total_agents_used": 1,
                            "processing_time": (time.time() - generation_start),
                            "agent_responses": [{"agent": "document_retriever", "success": True, "confidence": 0.8}]
                        }
                    else:
                        # No documents found, use direct response
                        direct_response = await self.ollama_service.generate_response(
                            prompt=request.message,
                            context="",
                            temperature=request.temperature,
                            system_prompt=self._get_financial_system_prompt()
                        )
                        agent_response = {
                            "answer": direct_response["response"],
                            "confidence": 0.3,
                            "sources": [],
                            "total_agents_used": 1,
                            "processing_time": (time.time() - generation_start),
                            "agent_responses": [{"agent": "direct_responder", "success": True, "confidence": 0.3}]
                        }
                except Exception as e:
                    logger.error(f"Direct document retrieval failed: {e}")
                    # Fallback to basic response
                    direct_response = await self.ollama_service.generate_response(
                        prompt=request.message,
                        context="",
                        temperature=request.temperature
                    )
                    agent_response = {
                        "answer": direct_response["response"],
                        "confidence": 0.1,
                        "sources": [],
                        "total_agents_used": 1,
                        "processing_time": (time.time() - generation_start),
                        "agent_responses": [{"agent": "fallback", "success": True, "confidence": 0.1}]
                    }
            else:
                # Non-RAG request
                direct_response = await self.ollama_service.generate_response(
                    prompt=request.message,
                    context="",
                    temperature=request.temperature
                )
                agent_response = {
                    "answer": direct_response["response"],
                    "confidence": 0.7,
                    "sources": [],
                    "total_agents_used": 1,
                    "processing_time": (time.time() - generation_start),
                    "agent_responses": [{"agent": "direct_responder", "success": True, "confidence": 0.7}]
                }
            
            # Continue with existing logic...
            
            generation_time = (time.time() - generation_start) * 1000
            
            # Extract response components
            final_answer = agent_response.get("answer", "I couldn't process your request.")
            sources = self._convert_agent_sources_to_document_results(agent_response.get("sources", []))
            context_documents = [
                {
                    'filename': source.get('filename', 'Unknown Document'),
                    'content': source.get('content', ''),
                    'document_type': source.get('document_type'),
                    'confidence': source.get('confidence', 0.0)
                }
                for source in agent_response.get("sources", [])
            ]
            
            # Calculate search time from agent processing time
            search_time = max(0, generation_time * 0.3)  # Estimate search as 30% of total processing
            
            # Create response data structure for compatibility
            response_data = {
                "response": final_answer,
                "generation_time_ms": generation_time,
                "agent_metadata": {
                    "total_agents_used": agent_response.get("total_agents_used", 1),
                    "processing_time": agent_response.get("processing_time", generation_time / 1000),
                    "confidence": agent_response.get("confidence", 0.7),
                    "agent_responses": agent_response.get("agent_responses", [])
                }
            }
            
            # Create assistant message
            assistant_message = ChatMessage(
                message_id=str(uuid.uuid4()),
                session_id=session.session_id,
                role="assistant",
                content=response_data["response"],
                timestamp=datetime.now(),
                sources=sources,
                confidence_score=response_data.get("agent_metadata", {}).get("confidence", 
                    self._calculate_response_confidence(sources, response_data["response"])),
                processing_time_ms=generation_time,
                metadata=response_data.get("agent_metadata", {})
            )
            session.messages.append(assistant_message)
            
            # Update session
            session.updated_at = datetime.now()
            session.last_activity = datetime.now()
            
            # Cleanup old messages if necessary
            await self._cleanup_session_messages(session)
            
            total_time = (time.time() - start_time) * 1000
            
            # Create response
            response = ChatResponse(
                session_id=session.session_id,
                message_id=assistant_message.message_id,
                response=response_data["response"],
                sources=sources,
                search_time_ms=search_time,
                generation_time_ms=generation_time,
                total_time_ms=total_time,
                confidence_score=assistant_message.confidence_score,
                source_count=len(sources),
                context_used=bool(context_documents),
                message_count=len(session.messages),
                session_active=session.is_active
            )
            
            logger.info(f"Chat response generated for session {session.session_id} in {total_time:.2f}ms")
            return response
            
        except Exception as e:
            logger.error(f"Chat processing failed: {e}")
            # Add error message to session
            error_message = ChatMessage(
                message_id=str(uuid.uuid4()),
                session_id=session.session_id,
                role="assistant",
                content="I apologize, but I encountered an error while processing your request. Please try again.",
                timestamp=datetime.now(),
                metadata={"error": str(e)}
            )
            session.messages.append(error_message)
            raise

    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Stream chat response"""
        # Get or create session (similar to chat method)
        if request.session_id:
            session = await self.get_session(request.session_id)
            if not session:
                session = await self.create_session()
        else:
            session = await self.create_session()
        
        # Add user message
        user_message = ChatMessage(
            message_id=str(uuid.uuid4()),
            session_id=session.session_id,
            role="user",
            content=request.message,
            timestamp=datetime.now()
        )
        session.messages.append(user_message)
        
        try:
            # Search documents
            sources = []
            if request.use_rag:
                sources = await self._search_documents(request, session)
            
            # Prepare context documents for streaming RAG (simplified for now)
            context_documents = []
            for source in sources:
                context_documents.append({
                    'filename': source.document_metadata.filename if source.document_metadata else 'Unknown Document',
                    'content': source.content
                })
            
            # For streaming, we'll use the old method with context building for now
            context = self._build_context(sources, session)
            
            # Stream response
            collected_response = ""
            async for chunk in self.ollama_service.generate_response_stream(
                prompt=request.message,
                context=context,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                system_prompt=self._get_financial_system_prompt()
            ):
                collected_response += chunk
                yield chunk
            
            # Add assistant message to session
            assistant_message = ChatMessage(
                message_id=str(uuid.uuid4()),
                session_id=session.session_id,
                role="assistant",
                content=collected_response,
                timestamp=datetime.now(),
                sources=sources,
                confidence_score=self._calculate_response_confidence(sources, collected_response)
            )
            session.messages.append(assistant_message)
            
            # Update session
            session.updated_at = datetime.now()
            session.last_activity = datetime.now()
            
        except Exception as e:
            logger.error(f"Streaming chat failed: {e}")
            yield f"\n\nError: {str(e)}"

    async def _search_documents(self, request: ChatRequest, session: ChatSession) -> List[DocumentSearchResult]:
        """Search for relevant documents"""
        try:
            # Generate query embedding
            query_embedding = await self.ollama_service.generate_embedding(request.message)
            
            # Create search request
            search_request = DocumentSearchRequest(
                query=request.message,
                top_k=request.top_k,
                rerank_top_k=request.rerank_top_k,
                similarity_threshold=request.similarity_threshold,
                use_reranking=True,
                reranking_strategy="hybrid"
            )
            
            # Apply document filters if provided
            if request.document_filters:
                if "document_types" in request.document_filters:
                    search_request.document_types = request.document_filters["document_types"]
                if "fiscal_years" in request.document_filters:
                    search_request.fiscal_years = request.document_filters["fiscal_years"]
                if "companies" in request.document_filters:
                    search_request.companies = request.document_filters["companies"]
                if "tags" in request.document_filters:
                    search_request.tags = request.document_filters["tags"]
            
            # Search in Qdrant
            initial_results = await self.qdrant_service.search_similar_chunks(
                query_embedding, search_request, self.document_metadata_cache
            )
            
            # Rerank results
            if search_request.use_reranking and initial_results:
                final_results = await self.reranker.rerank_results(
                    initial_results, search_request, request.message
                )
            else:
                final_results = initial_results[:search_request.rerank_top_k]
            
            logger.info(f"Found {len(final_results)} relevant sources for query")
            return final_results
            
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            return []

    def _build_context(self, sources: List[DocumentSearchResult], session: ChatSession) -> str:
        """Build context from sources and chat history"""
        context_parts = []
        
        # Add recent conversation history
        recent_messages = session.messages[-6:]  # Last 3 exchanges
        if len(recent_messages) > 2:  # Only if there's actual history
            context_parts.append("CONVERSATION HISTORY:")
            for msg in recent_messages[:-1]:  # Exclude the current user message
                if msg.role == "user":
                    context_parts.append(f"User: {msg.content}")
                elif msg.role == "assistant":
                    context_parts.append(f"Assistant: {msg.content[:200]}...")  # Truncate
            context_parts.append("")
        
        # Add document sources
        if sources:
            context_parts.append("RELEVANT FINANCIAL DOCUMENTS:")
            for i, source in enumerate(sources, 1):
                doc_info = ""
                if source.document_metadata:
                    doc_parts = []
                    if source.document_metadata.filename:
                        doc_parts.append(f"File: {source.document_metadata.filename}")
                    if source.document_metadata.document_type:
                        doc_parts.append(f"Type: {source.document_metadata.document_type}")
                    if source.document_metadata.fiscal_year:
                        doc_parts.append(f"Year: {source.document_metadata.fiscal_year}")
                    if source.document_metadata.company_name:
                        doc_parts.append(f"Company: {source.document_metadata.company_name}")
                    
                    if doc_parts:
                        doc_info = f" ({', '.join(doc_parts)})"
                
                context_parts.append(f"Source {i}{doc_info}:")
                context_parts.append(source.content)
                context_parts.append("")
        
        return "\n".join(context_parts)

    def _get_financial_system_prompt(self) -> str:
        """Get system prompt optimized for financial document analysis"""
        return """You are FinanceGPT, an expert financial analyst AI with deep knowledge of financial documents, reports, and analysis. You specialize in:

- Financial statement analysis and interpretation
- Performance attribution and investment analysis  
- Regulatory compliance and risk assessment
- Market analysis and economic indicators
- Corporate finance and valuation

Key Guidelines:
1. ACCURACY: Always verify financial calculations and cite specific sources
2. CONTEXT: Consider industry standards, market conditions, and regulatory requirements
3. PRECISION: Use exact figures and proper financial terminology
4. RISK AWARENESS: Highlight assumptions, limitations, and potential risks
5. COMPLIANCE: Consider regulatory implications and disclosure requirements

When analyzing financial data:
- Verify mathematical calculations
- Consider seasonal and cyclical factors
- Compare against industry benchmarks
- Highlight trends and anomalies
- Provide context for performance metrics

Response Format:
- Start with a direct answer to the question
- Support with specific data from sources
- Include relevant calculations or analysis
- Note any limitations or assumptions
- Suggest follow-up analysis if helpful

Always cite your sources and indicate confidence levels when making assessments."""

    def _calculate_response_confidence(self, sources: List[DocumentSearchResult], response: str) -> float:
        """Calculate confidence score for the response"""
        if not sources:
            return 0.3  # Low confidence without sources
        
        # Base confidence from source scores
        source_scores = [source.score for source in sources]
        avg_source_score = sum(source_scores) / len(source_scores)
        
        # Number of sources factor
        source_count_factor = min(1.0, len(sources) / 3)  # Optimal around 3 sources
        
        # Response length factor (too short or too long might indicate issues)
        response_length = len(response.split())
        if response_length < 20:
            length_factor = 0.7
        elif response_length > 500:
            length_factor = 0.9
        else:
            length_factor = 1.0
        
        # Financial content match
        financial_terms = ['revenue', 'profit', 'assets', 'liability', 'equity', 'ebitda', 'cash flow']
        financial_match = sum(1 for term in financial_terms if term in response.lower())
        financial_factor = min(1.0, financial_match / 3)
        
        combined_confidence = (
            avg_source_score * 0.4 +
            source_count_factor * 0.2 +
            length_factor * 0.2 +
            financial_factor * 0.2
        )
        
        return min(0.95, max(0.1, combined_confidence))  # Clamp between 0.1 and 0.95

    def _convert_agent_sources_to_document_results(self, agent_sources: List[Dict[str, Any]]) -> List[DocumentSearchResult]:
        """Convert agent orchestrator sources to DocumentSearchResult objects"""
        results = []
        
        for source in agent_sources:
            # Create a mock DocumentSearchResult for compatibility
            from ..models.document import DocumentMetadata, DocumentSearchResult
            
            metadata = DocumentMetadata(
                filename=source.get('filename', 'Unknown Document'),
                document_type=source.get('document_type', 'unknown'),
                total_pages=1,
                total_chunks=1,
                has_financial_data=True,
                confidence_score=source.get('confidence', 0.0)
            )
            
            result = DocumentSearchResult(
                chunk_id=f"agent_source_{hash(source.get('content', ''))}",
                document_id=f"doc_{hash(source.get('filename', 'unknown'))}",
                content=source.get('content', ''),
                score=source.get('confidence', 0.0),
                document_metadata=metadata,
                chunk_metadata={
                    "page_number": 1,
                    "contains_financial_data": True,
                    "confidence_score": source.get('confidence', 0.0)
                }
            )
            
            results.append(result)
        
        return results

    async def _cleanup_session_messages(self, session: ChatSession):
        """Clean up old messages to maintain session memory limits"""
        if len(session.messages) > session.max_history:
            # Keep system messages and recent messages
            messages_to_keep = []
            
            # Keep system messages
            system_messages = [msg for msg in session.messages if msg.role == "system"]
            messages_to_keep.extend(system_messages)
            
            # Keep recent user/assistant messages
            recent_messages = [msg for msg in session.messages if msg.role in ["user", "assistant"]]
            recent_messages = recent_messages[-(session.max_history - len(system_messages)):]
            messages_to_keep.extend(recent_messages)
            
            session.messages = messages_to_keep
            logger.info(f"Cleaned up session {session.session_id}, keeping {len(messages_to_keep)} messages")

    async def get_chat_history(self, request: ChatHistoryRequest) -> ChatHistoryResponse:
        """Get chat history for a session"""
        session = await self.get_session(request.session_id)
        if not session:
            return ChatHistoryResponse(
                session_id=request.session_id,
                messages=[],
                total_messages=0,
                has_more=False
            )
        
        # Apply pagination
        start_idx = request.offset
        end_idx = start_idx + request.limit
        
        paginated_messages = session.messages[start_idx:end_idx]
        has_more = end_idx < len(session.messages)
        
        return ChatHistoryResponse(
            session_id=request.session_id,
            messages=paginated_messages,
            total_messages=len(session.messages),
            has_more=has_more
        )

    async def list_sessions(self, limit: int = 50) -> SessionListResponse:
        """List all chat sessions"""
        # Sort sessions by last activity
        sorted_sessions = sorted(
            self.sessions.values(),
            key=lambda s: s.last_activity,
            reverse=True
        )
        
        # Apply limit
        limited_sessions = sorted_sessions[:limit]
        
        return SessionListResponse(
            sessions=limited_sessions,
            total_sessions=len(self.sessions)
        )

    async def delete_session(self, session_id: str) -> bool:
        """Delete a chat session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

    async def cleanup_inactive_sessions(self, max_age_hours: int = 24):
        """Clean up inactive sessions"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        inactive_sessions = [
            session_id for session_id, session in self.sessions.items()
            if session.last_activity < cutoff_time
        ]
        
        for session_id in inactive_sessions:
            del self.sessions[session_id]
        
        if inactive_sessions:
            logger.info(f"Cleaned up {len(inactive_sessions)} inactive sessions")
        
        return len(inactive_sessions)