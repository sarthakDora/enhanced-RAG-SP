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
from .router_service import RouterService, QueryType
from .multi_agent_pipeline import MultiAgentPipeline
from .attribution_prompt_service import AttributionPromptService, AttributionMode, AssetClass

logger = logging.getLogger(__name__)

# Import settings functions
from ..routers.settings import get_current_settings

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
        
        # Initialize router service
        self.router_service = RouterService()
        
        # Initialize multi-agent pipeline
        self.multi_agent_pipeline = MultiAgentPipeline(ollama_service, qdrant_service)
        
        # Initialize attribution prompt service
        self.attribution_prompt_service = AttributionPromptService()
        
        # In-memory storage for sessions (in production, use a database)
        self.sessions: Dict[str, ChatSession] = {}
        self.document_metadata_cache: Dict[str, Any] = {}
        
        # Update orchestrator's metadata store reference
        self.agent_orchestrator.metadata_store = self.document_metadata_cache
        
    async def create_session(self, title: str = "New Conversation", document_type: Optional[str] = None) -> ChatSession:
        """Create a new chat session"""
        now = datetime.now()
        session_id = str(uuid.uuid4())
        session = ChatSession(
            session_id=session_id,
            title=title,
            document_type=document_type,
            created_at=now,
            updated_at=now,
            last_activity=now,
            messages=[],
            is_active=True,
            active_documents=[],
            financial_context={}
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
        
        # Get custom prompts from settings if enabled
        settings = get_current_settings(request.session_id)
        custom_prompts = None
        if settings.prompts.use_custom_prompts:
            custom_prompts = {
                'system_prompt': settings.prompts.system_prompt,
                'query_prompt': settings.prompts.query_prompt,
                'response_format_prompt': settings.prompts.response_format_prompt
            }
            logger.info(f"Using custom prompts for session {request.session_id}")
        
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
            logger.info(f"Processing chat request with intelligent routing")
            
            # Get conversation history for context
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in session.messages[-10:]  # Last 10 messages
                if msg.role in ['user', 'assistant']
            ]
            
            # Classify the query using router service
            classification = self.router_service.classify_query(
                query=request.message,
                session_id=session.session_id,
                conversation_history=conversation_history
            )
            
            logger.info(f"Query classified as: {classification['query_type'].value} with confidence: {classification['confidence']}")
            logger.info(f"Routing decision: {classification['routing_decision']}")
            
            # Generate response context
            response_context = self.router_service.generate_response_context(classification, session.session_id)
            
            # TEMPORARY FIX: Force knowledge base search for performance attribution queries
            performance_keywords = ['performance', 'attribution', 'contributor', 'detractor', 'q2', '2025', 'top', 'best', 'worst']
            query_lower = request.message.lower()
            if any(keyword in query_lower for keyword in performance_keywords) and request.use_rag:
                print(f"DEBUG: OVERRIDE - Forcing knowledge base search for: '{request.message}'")
                logger.info(f"OVERRIDE: Forcing knowledge base search for performance query: '{request.message}'")
                classification['routing_decision'] = 'knowledge_base_search'
            
            # Process based on routing decision
            generation_start = time.time()
            agent_response = await self._process_by_routing_decision(
                classification, request, session, conversation_history, generation_start, custom_prompts
            )
            
            # Continue with existing logic...
            
            generation_time = (time.time() - generation_start) * 1000
            
            # Extract response components
            final_answer = agent_response.get("answer", "I couldn't process your request.")
            # Group sources by filename to avoid showing duplicate chunks from same file
            grouped_sources = self._group_sources_by_file(agent_response.get("sources", []))
            sources = self._convert_agent_sources_to_document_results(grouped_sources)
            context_documents = [
                {
                    'filename': source.get('filename', 'Unknown Document'),
                    'content': source.get('content', ''),
                    'document_type': source.get('document_type'),
                    'confidence': source.get('confidence', 0.0)
                }
                for source in grouped_sources
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
                prompt=agent_response.get("prompt", "Prompt not available"),
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
                session_active=session.is_active,
                prompt=agent_response.get("prompt", "Prompt not available")
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
        # Get custom prompts from settings if enabled
        settings = get_current_settings(request.session_id)
        custom_prompts = None
        if settings.prompts.use_custom_prompts:
            custom_prompts = {
                'system_prompt': settings.prompts.system_prompt,
                'query_prompt': settings.prompts.query_prompt,
                'response_format_prompt': settings.prompts.response_format_prompt
            }
        
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
                system_prompt=self._get_financial_system_prompt(custom_prompts)
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
                confidence_score=self._calculate_response_confidence(sources, collected_response),
                prompt="[Streaming response - prompt not captured in this mode]"
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
            # Get settings for this session to use in search
            settings = get_current_settings(request.session_id)
            
            # Generate query embedding
            query_embedding = await self.ollama_service.generate_embedding(request.message)
            
            # Create search request using session settings
            search_request = DocumentSearchRequest(
                query=request.message,
                top_k=request.top_k or settings.top_k,
                rerank_top_k=request.rerank_top_k or settings.rerank_top_k,
                similarity_threshold=request.similarity_threshold or settings.similarity_threshold,
                use_reranking=True,
                reranking_strategy=request.reranking_strategy or settings.reranking_strategy or "hybrid"
            )
            
            # Apply document type filter from session or request
            document_type_filter = request.document_type or session.document_type
            if document_type_filter:
                search_request.document_types = [document_type_filter]
            
            # Apply additional document filters if provided
            if request.document_filters:
                if "document_types" in request.document_filters and not document_type_filter:
                    search_request.document_types = request.document_filters["document_types"]
                if "fiscal_years" in request.document_filters:
                    search_request.fiscal_years = request.document_filters["fiscal_years"]
                if "companies" in request.document_filters:
                    search_request.companies = request.document_filters["companies"]
                if "tags" in request.document_filters:
                    search_request.tags = request.document_filters["tags"]
            
            # Determine target collection based on document type
            target_collection = None
            if document_type_filter:
                logger.info(f"Filtering by document type: {document_type_filter}")
                if document_type_filter == "performance_attribution":
                    target_collection = self.qdrant_service.category_collections["performance_docs"]
                    logger.info(f"Using performance attribution collection: {target_collection}")
                elif document_type_filter == "financial_report":
                    target_collection = self.qdrant_service.category_collections["technical_docs"]
                    logger.info(f"Using financial report collection: {target_collection}")
                elif document_type_filter == "market_analysis":
                    target_collection = self.qdrant_service.category_collections["aum_docs"]
                    logger.info(f"Using market analysis collection: {target_collection}")
                else:
                    logger.info(f"Unknown document type filter: {document_type_filter}, searching all collections")
            
            # Search in Qdrant (specific collection or all collections)
            initial_results = await self.qdrant_service.search_similar_chunks(
                query_embedding, search_request, self.document_metadata_cache, target_collection
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

    def _get_financial_system_prompt(self, custom_prompts: Dict[str, str] = None) -> str:
        """Get system prompt - custom if enabled, otherwise general purpose"""
        if custom_prompts and custom_prompts.get('system_prompt'):
            return custom_prompts['system_prompt']
        
        # Default general-purpose prompt with basic guard rails (when custom prompts are disabled)
        return """You are a helpful AI assistant that analyzes documents and answers questions based on provided context.

Guidelines:
1. Answer questions based on the provided document context
2. Be accurate and cite your sources when possible
3. If information is not available in the documents, say so clearly
4. Provide clear, well-structured responses
5. Maintain a professional tone
6. Do not make assumptions beyond what is stated in the documents"""

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

    def _group_sources_by_file(self, agent_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group sources by filename, keeping only the highest scoring chunk per file"""
        if not agent_sources:
            return []
        
        # Group by filename
        file_groups = {}
        for source in agent_sources:
            filename = source.get('filename', 'Unknown Document')
            confidence = source.get('confidence', 0.0)
            
            # Keep only the highest confidence source per file
            if filename not in file_groups or confidence > file_groups[filename]['confidence']:
                # Create a summary content instead of showing individual chunks
                file_groups[filename] = {
                    'filename': filename,
                    'content': f"Source: {filename}",  # Show just the filename instead of chunk content
                    'document_type': source.get('document_type', 'unknown'),
                    'confidence': confidence
                }
        
        # Return list sorted by confidence (highest first)
        return sorted(file_groups.values(), key=lambda x: x['confidence'], reverse=True)

    def _convert_agent_sources_to_document_results(self, agent_sources: List[Dict[str, Any]]) -> List[DocumentSearchResult]:
        """Convert agent orchestrator sources to DocumentSearchResult objects"""
        results = []
        
        for source in agent_sources:
            # Create a mock DocumentSearchResult for compatibility
            from ..models.document import DocumentMetadata, DocumentSearchResult, ConfidenceLevel
            from datetime import datetime
            from ..models.document import DocumentType

            confidence = source.get('confidence', 0.0)
            # Map confidence score to ConfidenceLevel
            if confidence >= 0.75:
                confidence_level = ConfidenceLevel.HIGH
            elif confidence >= 0.4:
                confidence_level = ConfidenceLevel.MEDIUM
            else:
                confidence_level = ConfidenceLevel.LOW

            metadata = DocumentMetadata(
                filename=source.get('filename', 'Unknown Document'),
                file_size=source.get('file_size', 1000),  # Default size
                file_type=source.get('file_type', '.txt'),  # Default type
                document_type=DocumentType.OTHER if source.get('document_type', 'unknown') == 'unknown' else source.get('document_type', DocumentType.OTHER),
                upload_timestamp=datetime.now(),  # Current timestamp as default
                total_pages=1,
                total_chunks=1,
                has_financial_data=True,
                confidence_score=confidence
            )

            result = DocumentSearchResult(
                chunk_id=f"agent_source_{hash(source.get('content', ''))}",
                document_id=f"doc_{hash(source.get('filename', 'unknown'))}",
                content=source.get('content', ''),
                score=confidence,
                confidence_level=confidence_level,
                document_metadata=metadata,
                chunk_metadata={
                    "page_number": 1,
                    "contains_financial_data": True,
                    "confidence_score": confidence
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
    
    async def _process_by_routing_decision(self, classification: Dict[str, Any], request: ChatRequest, 
                                         session: ChatSession, conversation_history: List[Dict], 
                                         generation_start: float, custom_prompts: Dict[str, str] = None) -> Dict[str, Any]:
        """Process query based on router's classification"""
        routing_decision = classification["routing_decision"]
        query_type = classification["query_type"]
        
        logger.info(f"Processing with routing decision: {routing_decision}")
        
        try:
            if routing_decision == "store_and_respond":
                # Handle personal information storage
                personal_info = classification.get("personal_info_extracted", {})
                response_text = self.router_service.format_personal_info_response(personal_info)
                
                return {
                    "answer": response_text,
                    "confidence": 0.95,
                    "sources": [],
                    "total_agents_used": 1,
                    "processing_time": (time.time() - generation_start),
                    "prompt": f"SYSTEM: Personal information storage handler\n\nUSER: {request.message}\n\nASSISTANT:",
                    "agent_responses": [{"agent": "personal_info_handler", "success": True, "confidence": 0.95}]
                }
            
            elif routing_decision == "greeting_with_memory":
                # Handle personalized greetings
                response_text = self.router_service.get_personalized_greeting(session.session_id)
                
                return {
                    "answer": response_text,
                    "confidence": 0.9,
                    "sources": [],
                    "total_agents_used": 1,
                    "processing_time": (time.time() - generation_start),
                    "prompt": f"SYSTEM: Personalized greeting handler\n\nUSER: {request.message}\n\nASSISTANT:",
                    "agent_responses": [{"agent": "greeting_handler", "success": True, "confidence": 0.9}]
                }
            
            elif routing_decision == "knowledge_base_search":
                # Handle document/knowledge base queries with fallback
                logger.info(f"ROUTING: Taking knowledge_base_search path for query: '{request.message}'")
                try:
                    result = await self._handle_knowledge_base_query(request, conversation_history, generation_start, custom_prompts)
                    logger.info(f"ROUTING: Knowledge base query returned {len(result.get('sources', []))} sources")
                    return result
                except Exception as e:
                    logger.error(f"Knowledge base query failed, falling back to general query: {e}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    return await self._handle_general_query(request, conversation_history, generation_start, with_memory=False, custom_prompts=custom_prompts)
            
            elif routing_decision == "conversational_with_context":
                # Handle conversational follow-ups
                use_rag = classification.get("requires_rag", False)
                if use_rag:
                    try:
                        return await self._handle_knowledge_base_query(request, conversation_history, generation_start, custom_prompts)
                    except Exception as e:
                        logger.error(f"RAG query failed, falling back to general query: {e}")
                        return await self._handle_general_query(request, conversation_history, generation_start, with_memory=True, custom_prompts=custom_prompts)
                else:
                    return await self._handle_general_query(request, conversation_history, generation_start, with_memory=True)
            
            else:  # general_knowledge
                # Handle general knowledge queries
                logger.info(f"ROUTING: Taking general_knowledge path for query: '{request.message}', routing_decision: {routing_decision}")
                return await self._handle_general_query(request, conversation_history, generation_start, custom_prompts=custom_prompts)
                
        except Exception as e:
            logger.error(f"Route processing failed for {routing_decision}: {e}")
            # Ultimate fallback - simple response
            return {
                "answer": "I encountered an error processing your request. Please try rephrasing your question or check if the system is properly configured.",
                "confidence": 0.1,
                "sources": [],
                "total_agents_used": 1,
                "processing_time": (time.time() - generation_start),
                "prompt": f"SYSTEM: Error fallback handler\n\nUSER: {request.message}\n\nASSISTANT:",
                "agent_responses": [{"agent": "error_fallback", "success": False, "confidence": 0.1, "error": str(e)}]
            }
    
    async def _handle_knowledge_base_query(self, request: ChatRequest, conversation_history: List[Dict], 
                                         generation_start: float, custom_prompts: Dict[str, str] = None) -> Dict[str, Any]:
        """Handle queries that require knowledge base/document search using multi-agent pipeline"""
        try:
            # Check if we have any uploaded documents
            logger.info(f"Document metadata cache status: {len(self.document_metadata_cache)} documents")
            if self.document_metadata_cache:
                logger.info(f"Available documents: {list(self.document_metadata_cache.keys())}")
            
            # If no documents in cache, try to sync from Qdrant one more time
            if not self.document_metadata_cache:
                logger.info("No documents in cache, attempting emergency sync from Qdrant...")
                try:
                    all_points = await self.qdrant_service.get_all_points()
                    if all_points:
                        logger.info(f"Found {len(all_points)} points in Qdrant, reconstructing metadata cache...")
                        
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
                                # Parse upload_timestamp properly
                                upload_ts = first_chunk.get("upload_timestamp")
                                if isinstance(upload_ts, str):
                                    try:
                                        upload_ts = datetime.fromisoformat(upload_ts.replace('Z', '+00:00'))
                                    except:
                                        upload_ts = datetime.now()
                                elif upload_ts is None:
                                    upload_ts = datetime.now()
                                
                                doc_metadata = DocumentMetadata(
                                    filename=first_chunk.get("filename", f"document_{doc_id[:8]}.txt"),
                                    file_size=first_chunk.get("file_size", 1000),
                                    file_type=first_chunk.get("file_type", ".txt"),
                                    document_type=first_chunk.get("document_type", "other"),
                                    upload_timestamp=upload_ts,
                                    total_pages=first_chunk.get("total_pages", 1),
                                    total_chunks=len(chunks),
                                    has_financial_data=first_chunk.get("has_financial_data", False),
                                    confidence_score=first_chunk.get("confidence_score", 0.5),
                                    tags=first_chunk.get("tags", []),
                                    custom_fields=first_chunk.get("custom_fields", {})
                                )
                                self.document_metadata_cache[doc_id] = doc_metadata
                                logger.info(f"Loaded document {doc_metadata.filename} (type: {doc_metadata.document_type}) from Qdrant sync")
                            except Exception as e:
                                logger.error(f"Failed to reconstruct metadata for document {doc_id}: {e}")
                                continue
                        
                        logger.info(f"Emergency sync completed: {len(self.document_metadata_cache)} documents loaded")
                    else:
                        logger.info("No points found in Qdrant during emergency sync")
                except Exception as e:
                    logger.error(f"Emergency sync from Qdrant failed: {e}")
            
            # Final check after emergency sync - but allow pipeline to search directly if cache is sparse
            if not self.document_metadata_cache:
                logger.warning("Document metadata cache is empty, but allowing pipeline to search Qdrant directly")
            else:
                logger.info(f"Proceeding with {len(self.document_metadata_cache)} documents in metadata cache")
            
            # Always let the pipeline try - it can search Qdrant directly even if metadata cache is empty
            
            logger.info(f"Processing knowledge base query with multi-agent pipeline: '{request.message}'")
            logger.info(f"Commentary mode enabled: {request.commentary_mode}")
            
            # Check if this is a performance attribution query
            performance_keywords = ['performance', 'attribution', 'contributor', 'detractor', 'q2', '2025', 'top', 'best', 'worst']
            is_performance_query = any(keyword in request.message.lower() for keyword in performance_keywords)
            
            if is_performance_query:
                logger.info("PERFORMANCE_ATTRIBUTION: Detected performance query - bypassing stale metadata cache")
                # Force fresh sync from Qdrant for performance queries to ensure we have latest data
                try:
                    all_points = await self.qdrant_service.get_all_points()
                    if all_points:
                        logger.info(f"PERFORMANCE_ATTRIBUTION: Force synced {len(all_points)} points from Qdrant")
                        # Set empty cache to force pipeline to search Qdrant directly
                        self.multi_agent_pipeline.set_document_metadata_cache({})
                    else:
                        logger.warning("PERFORMANCE_ATTRIBUTION: No points found during force sync")
                        self.multi_agent_pipeline.set_document_metadata_cache({})
                except Exception as e:
                    logger.error(f"PERFORMANCE_ATTRIBUTION: Force sync failed: {e}, proceeding with direct Qdrant search")
                    self.multi_agent_pipeline.set_document_metadata_cache({})
            else:
                # Normal queries use metadata cache
                self.multi_agent_pipeline.set_document_metadata_cache(self.document_metadata_cache or {})
            
            # Get session settings for search parameters
            settings = get_current_settings(request.session_id)
            
            # Use the multi-agent pipeline for intelligent processing
            search_params = {
                'top_k': request.top_k or settings.top_k,
                'rerank_top_k': request.rerank_top_k or settings.rerank_top_k,
                'similarity_threshold': request.similarity_threshold or settings.similarity_threshold,
                'reranking_strategy': request.reranking_strategy or settings.reranking_strategy or 'hybrid',
                'use_rag': request.use_rag if request.use_rag is not None else settings.use_rag,
                'temperature': request.temperature or settings.temperature,
                'max_tokens': request.max_tokens or settings.max_tokens
            }
            
            # TEMPORARY FIX: Use more permissive search parameters for performance queries
            if any(keyword in request.message.lower() for keyword in ['performance', 'attribution', 'q2', '2025']):
                search_params['similarity_threshold'] = min(search_params['similarity_threshold'], 0.3)
                search_params['top_k'] = max(search_params['top_k'], 10)
                print(f"DEBUG: Adjusted search params for performance query: threshold={search_params['similarity_threshold']}, top_k={search_params['top_k']}")
            
            print(f"DEBUG: Search params: {search_params}")
            
            # Check for attribution mode handling - trigger for any query when performance attribution is selected
            if request.document_type == "performance_attribution":
                if request.commentary_mode:
                    logger.info("🔷 ATTRIBUTION_COMMENTARY: Using structured commentary generation mode")
                    logger.info(f"Query: {request.message[:100]}...")
                    pipeline_result = await self._handle_attribution_commentary(
                        request, conversation_history, search_params, custom_prompts
                    )
                else:
                    logger.info("ATTRIBUTION_Q&A: Using document search Q&A mode")
                    logger.info(f"Query: {request.message[:100]}...")
                    pipeline_result = await self._handle_attribution_qa(
                        request, conversation_history, search_params, custom_prompts
                    )
            else:
                # Normal pipeline processing for non-attribution queries
                pipeline_result = await self.multi_agent_pipeline.process_query(
                    query=request.message,
                    conversation_history=conversation_history,
                    search_params=search_params,
                    custom_prompts=custom_prompts
                )
            
            logger.info(f"Multi-agent pipeline completed - Category: {pipeline_result.get('category')}, Sources: {len(pipeline_result.get('sources', []))}")
            
            return pipeline_result
            
        except Exception as e:
            logger.error(f"Multi-agent pipeline processing failed: {e}")
            return {
                "answer": "I encountered an error while processing your query through the intelligent analysis system. Please try rephrasing your question.",
                "confidence": 0.1,
                "sources": [],
                "total_agents_used": 1,
                "processing_time": (time.time() - generation_start),
                "prompt": f"SYSTEM: Pipeline error handler\n\nUSER: {request.message}\n\nASSISTANT:",
                "agent_responses": [{"agent": "pipeline_error_handler", "success": False, "confidence": 0.1, "error": str(e)}]
            }
    
    async def _handle_general_query(self, request: ChatRequest, conversation_history: List[Dict], 
                                  generation_start: float, with_memory: bool = False, custom_prompts: Dict[str, str] = None) -> Dict[str, Any]:
        """Handle general knowledge queries"""
        try:
            # Get personal context if memory is enabled
            personal_context = ""
            if with_memory:
                personal_info = self.router_service.conversation_memory.get_personal_info(request.session_id or "")
                if personal_info.get("name"):
                    personal_context = f"Remember that the user's name is {personal_info['name']}. "
            
            system_prompt = self._get_financial_system_prompt(custom_prompts) + f"\n\nIMPORTANT: This is a general knowledge question. Be clear that your response is not based on specific documents. {personal_context}"
            
            # Get session settings for temperature and max_tokens
            settings = get_current_settings(request.session_id)
            
            direct_response = await self.ollama_service.generate_response(
                prompt=request.message,
                context="",
                temperature=request.temperature or settings.temperature,
                max_tokens=request.max_tokens or settings.max_tokens,
                system_prompt=system_prompt
            )
            
            disclaimer = "\n\n*Note: This response is based on general knowledge, not specific uploaded documents.*"
            
            return {
                "answer": direct_response["response"] + disclaimer,
                "confidence": 0.7,
                "sources": [],
                "total_agents_used": 1,
                "processing_time": (time.time() - generation_start),
                "prompt": direct_response.get("prompt", "Prompt not available"),
                "agent_responses": [{"agent": "general_knowledge", "success": True, "confidence": 0.7}]
            }
            
        except Exception as e:
            logger.error(f"General query processing failed: {e}")
            return {
                "answer": "I encountered an error while processing your question. Please try again.",
                "confidence": 0.1,
                "sources": [],
                "total_agents_used": 1,
                "processing_time": (time.time() - generation_start),
                "prompt": f"SYSTEM: General query error handler\n\nUSER: {request.message}\n\nASSISTANT:",
                "agent_responses": [{"agent": "error_handler", "success": False, "confidence": 0.1}]
            }
    
    async def _handle_attribution_commentary(self, request: ChatRequest, conversation_history: List[Dict], 
                                           search_params: Dict[str, Any], custom_prompts: Dict[str, str] = None) -> Dict[str, Any]:
        """Handle attribution commentary mode with specialized prompts"""
        try:
            start_time = time.time()
            
            # First, search for relevant chunks
            logger.info(f"ATTRIBUTION_COMMENTARY: Searching for documents with type: {request.document_type}")
            sources = await self._search_documents(request, await self.get_session(request.session_id))
            logger.info(f"ATTRIBUTION_COMMENTARY: Initial search found {len(sources)} sources")
            # If no sources found, retry with looser parameters
            if not sources:
                logger.warning("No sources found for attribution commentary, retrying with looser search parameters")
                # Create a fallback request with lower similarity threshold and no document type filter
                fallback_request = ChatRequest(
                    session_id=request.session_id,
                    message=request.message,
                    document_type=None,
                    commentary_mode=request.commentary_mode,
                    use_rag=True,
                    top_k=15,
                    rerank_top_k=5,
                    similarity_threshold=0.1,
                    reranking_strategy="hybrid",
                    temperature=request.temperature,
                    max_tokens=request.max_tokens
                )
                sources = await self._search_documents(fallback_request, await self.get_session(request.session_id))
                logger.info(f"ATTRIBUTION_COMMENTARY: Fallback search found {len(sources)} sources")
            if not sources:
                logger.error("ATTRIBUTION_COMMENTARY: No attribution documents found after fallback search. Check document upload and indexing.")
                return {
                    "answer": "No attribution documents were found for analysis. Please ensure you have uploaded performance attribution reports and they are indexed correctly. If you just uploaded, try re-running after a few seconds.",
                    "confidence": 0.1,
                    "sources": [],
                    "total_agents_used": 1,
                    "processing_time": (time.time() - start_time),
                    "prompt": "No documents found for attribution analysis",
                    "agent_responses": [{"agent": "attribution_handler", "success": False, "confidence": 0.1}]
                }
            
            # Convert sources to format expected by attribution prompt service
            document_chunks = []
            for source in sources:
                chunk_content = source.content if hasattr(source, 'content') else ''
                chunk_filename = source.document_metadata.filename if source.document_metadata else 'Unknown Document'
                chunk_type = source.document_metadata.document_type if source.document_metadata else 'unknown'
                logger.info(f"ATTRIBUTION_COMMENTARY: Chunk {chunk_filename} content preview: {chunk_content[:200]}")
                document_chunks.append({
                    'filename': chunk_filename,
                    'content': chunk_content,
                    'document_type': chunk_type
                })
            # Fallback: If all chunks are empty, return error
            if all(not chunk['content'].strip() for chunk in document_chunks):
                logger.error("ATTRIBUTION_COMMENTARY: All document chunks are empty. Attribution data missing in Qdrant.")
                return {
                    "answer": "No attribution data found in the uploaded documents. Please check that your attribution report contains actual data and was processed correctly.",
                    "confidence": 0.1,
                    "sources": [],
                    "total_agents_used": 1,
                    "processing_time": (time.time() - start_time),
                    "prompt": "No attribution data found in document chunks",
                    "agent_responses": [{"agent": "attribution_handler", "success": False, "confidence": 0.1}]
                }
            
            # Detect asset class from document content
            asset_class_str = self.attribution_prompt_service.detect_asset_class(document_chunks)
            if asset_class_str == "equity":
                asset_class = AssetClass.EQUITY
            elif asset_class_str == "fixed_income":
                asset_class = AssetClass.FIXED_INCOME
            else:
                asset_class = AssetClass.UNKNOWN
            
            logger.info(f"ATTRIBUTION_COMMENTARY: Detected asset class: {asset_class_str}")
            
            # Assemble specialized attribution prompt
            attribution_prompt = self.attribution_prompt_service.assemble_prompt(
                mode=AttributionMode.COMMENTARY,
                asset_class=asset_class,
                document_chunks=document_chunks,
                user_query=request.message
            )
            
            logger.info(f"ATTRIBUTION_COMMENTARY: Generated specialized prompt (length: {len(attribution_prompt)} chars)")
            
            # Generate response using the specialized prompt
            settings = get_current_settings(request.session_id)
            response_data = await self.ollama_service.generate_response(
                prompt=request.message,
                context="",  # Context is built into the attribution prompt
                temperature=request.temperature or settings.temperature,
                max_tokens=request.max_tokens or settings.max_tokens,
                system_prompt=attribution_prompt
            )
            
            return {
                "answer": response_data["response"],
                "confidence": 0.9,  # High confidence for structured commentary
                "sources": [
                    {
                        'filename': chunk['filename'],
                        'content': f"Source: {chunk['filename']}",
                        'document_type': chunk.get('document_type', 'unknown'),
                        'confidence': 0.9
                    }
                    for chunk in document_chunks[:5]  # Limit to top 5 sources
                ],
                "total_agents_used": 1,
                "processing_time": (time.time() - start_time),
                "prompt": attribution_prompt,
                "agent_responses": [{"agent": "attribution_commentary", "success": True, "confidence": 0.9, "asset_class": asset_class_str}]
            }
            
        except Exception as e:
            logger.error(f"Attribution commentary processing failed: {e}")
            return {
                "answer": "I encountered an error while generating attribution commentary. Please try again.",
                "confidence": 0.1,
                "sources": [],
                "total_agents_used": 1,
                "processing_time": (time.time() - start_time if 'start_time' in locals() else 0),
                "prompt": "Attribution commentary error",
                "agent_responses": [{"agent": "attribution_error", "success": False, "confidence": 0.1, "error": str(e)}]
            }
    
    async def _handle_attribution_qa(self, request: ChatRequest, conversation_history: List[Dict], 
                                   search_params: Dict[str, Any], custom_prompts: Dict[str, str] = None) -> Dict[str, Any]:
        """Handle attribution Q&A mode - always search documents and send context to LLM"""
        try:
            start_time = time.time()
            
            logger.info("ATTRIBUTION_Q&A: Starting Q&A mode with document search")
            
            # Create a modified request that disables performance attribution mode
            # This ensures we use normal document search instead of performance attribution pipeline
            qa_request = ChatRequest(
                session_id=request.session_id,
                message=request.message,
                document_type=request.document_type,
                commentary_mode=False,  # Ensure this is false for Q&A
                use_rag=True,  # Always use RAG for Q&A
                top_k=search_params.get('top_k', 10),
                rerank_top_k=search_params.get('rerank_top_k', 3),
                similarity_threshold=search_params.get('similarity_threshold', 0.3),  # Lower threshold for more results
                reranking_strategy=search_params.get('reranking_strategy', 'hybrid'),
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            # Search for relevant documents using normal document search
            session = await self.get_session(request.session_id)
            sources = await self._search_documents(qa_request, session)
            
            if not sources:
                logger.warning("No sources found for Q&A - trying broader search")
                # Try with even lower threshold
                qa_request.similarity_threshold = 0.1
                sources = await self._search_documents(qa_request, session)
            
            if not sources:
                return {
                    "answer": "I couldn't find any documents to answer your question. Please upload some documents first.",
                    "confidence": 0.1,
                    "sources": [],
                    "total_agents_used": 1,
                    "processing_time": (time.time() - start_time),
                    "prompt": "No documents found for Q&A",
                    "agent_responses": [{"agent": "attribution_qa", "success": False, "confidence": 0.1}]
                }
            
            logger.info(f"ATTRIBUTION_Q&A: Found {len(sources)} sources for Q&A")
            
            # Build context from document sources
            context = self._build_context(sources, session)
            
            # Use simple Q&A system prompt
            system_prompt = """You are a data analyst. Answer questions based only on the provided context from the uploaded document. 
If the answer is not in the document, say so.
Be concise and precise. Use numbers, dates, and references exactly as in the context.
Focus on providing specific answers to the user's question."""
            
            # Add asset-class specific guidance if it's performance attribution
            if request.document_type == "performance_attribution":
                system_prompt += """

When answering about performance attribution data:
- Focus on specific sectors, countries, or securities mentioned
- Include exact attribution effects and percentages when available
- Mention allocation vs selection effects when relevant
- Reference specific time periods covered in the data"""
            
            logger.info(f"ATTRIBUTION_Q&A: Using context length: {len(context)} chars")
            
            # Generate response using normal document context
            settings = get_current_settings(request.session_id)
            response_data = await self.ollama_service.generate_response(
                prompt=request.message,
                context=context,  # Send actual document context
                temperature=request.temperature or settings.temperature,
                max_tokens=request.max_tokens or settings.max_tokens,
                system_prompt=system_prompt
            )
            
            return {
                "answer": response_data["response"],
                "confidence": 0.8,  # Good confidence for Q&A with sources
                "sources": sources,  # Return actual DocumentSearchResult objects
                "total_agents_used": 1,
                "processing_time": (time.time() - start_time),
                "prompt": response_data.get("prompt", system_prompt),
                "agent_responses": [{"agent": "document_qa", "success": True, "confidence": 0.8, "sources_found": len(sources)}]
            }
            
        except Exception as e:
            logger.error(f"Attribution Q&A processing failed: {e}")
            return {
                "answer": "I encountered an error while processing your question. Please try again.",
                "confidence": 0.1,
                "sources": [],
                "total_agents_used": 1,
                "processing_time": (time.time() - start_time if 'start_time' in locals() else 0),
                "prompt": "Attribution Q&A error",
                "agent_responses": [{"agent": "attribution_qa_error", "success": False, "confidence": 0.1, "error": str(e)}]
            }