"""
Multi-Agent Orchestrator for Enhanced RAG System
Implements state-of-the-art multi-agent architecture for financial document analysis
"""

from typing import Dict, List, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
import json
import asyncio

from .ollama_service import OllamaService


class AgentType(str, Enum):
    QUERY_DECOMPOSER = "query_decomposer"
    DOCUMENT_RETRIEVER = "document_retriever"
    FINANCIAL_ANALYZER = "financial_analyzer"
    PORTFOLIO_ANALYZER = "portfolio_analyzer"
    DIRECT_RESPONDER = "direct_responder"
    RESPONSE_SYNTHESIZER = "response_synthesizer"


class QueryIntent(str, Enum):
    DOCUMENT_RELATED = "document_related"
    PORTFOLIO_ANALYSIS = "portfolio_analysis"
    FINANCIAL_CALCULATION = "financial_calculation"
    GENERAL_FINANCIAL = "general_financial"
    DIRECT_ANSWER = "direct_answer"


class AgentTask(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    agent_type: AgentType = Field(..., description="Type of agent to handle this task")
    intent: QueryIntent = Field(..., description="Intent classification")
    query: str = Field(..., description="Original or decomposed query")
    context: Dict[str, Any] = Field(default_factory=dict, description="Task context")
    dependencies: List[str] = Field(default_factory=list, description="Task dependencies")
    priority: int = Field(default=1, description="Task priority (1=high, 3=low)")
    status: str = Field(default="pending", description="Task status")
    result: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    agent_type: AgentType
    task_id: str
    success: bool
    result: Dict[str, Any]
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    execution_time: float


class QueryDecomposerAgent:
    """Decomposes complex queries into manageable sub-tasks"""
    
    def __init__(self, ollama_service: OllamaService):
        self.ollama_service = ollama_service
        
    async def decompose_query(self, query: str, context: Dict[str, Any] = None) -> List[AgentTask]:
        """Decompose a complex query into sub-tasks with intent classification"""
        
        decomposition_prompt = f"""
        You are a query decomposition agent for a financial RAG system. Analyze this query and determine:
        1. The main intent (document_related, portfolio_analysis, financial_calculation, general_financial, direct_answer)
        2. Whether it needs decomposition into sub-tasks
        3. If it references uploaded documents or requires knowledge base search
        
        Query: "{query}"
        Context: {json.dumps(context or {}, indent=2)}
        
        Respond with JSON in this format:
        {{
            "intent": "intent_type",
            "requires_documents": true/false,
            "complexity": "simple/medium/complex",
            "sub_tasks": [
                {{
                    "query": "sub-query text",
                    "intent": "intent_type",
                    "agent_type": "agent_type",
                    "priority": 1-3,
                    "dependencies": []
                }}
            ],
            "reasoning": "explanation of decomposition"
        }}
        
        Available agent types: query_decomposer, document_retriever, financial_analyzer, portfolio_analyzer, direct_responder, response_synthesizer
        """
        
        try:
            response = await self.ollama_service.generate_response(decomposition_prompt)
            
            # Parse JSON response
            result = json.loads(response)
            
            # Create AgentTask objects
            tasks = []
            for i, sub_task in enumerate(result.get("sub_tasks", [])):
                task = AgentTask(
                    task_id=f"task_{i}_{datetime.now().timestamp()}",
                    agent_type=AgentType(sub_task["agent_type"]),
                    intent=QueryIntent(sub_task["intent"]),
                    query=sub_task["query"],
                    context=context or {},
                    dependencies=sub_task.get("dependencies", []),
                    priority=sub_task.get("priority", 1)
                )
                tasks.append(task)
            
            return tasks
            
        except Exception as e:
            # Smart fallback: if use_rag is True in context, create document retrieval task
            if context and context.get("use_rag", False):
                return [
                    AgentTask(
                        task_id=f"doc_retrieval_{datetime.now().timestamp()}",
                        agent_type=AgentType.DOCUMENT_RETRIEVER,
                        intent=QueryIntent.DOCUMENT_RELATED,
                        query=query,
                        context=context or {},
                        priority=1
                    ),
                    AgentTask(
                        task_id=f"response_synthesis_{datetime.now().timestamp()}",
                        agent_type=AgentType.RESPONSE_SYNTHESIZER,
                        intent=QueryIntent.DOCUMENT_RELATED,
                        query=query,
                        context=context or {},
                        priority=2
                    )
                ]
            else:
                # Fallback: create a single direct response task
                return [AgentTask(
                    task_id=f"fallback_{datetime.now().timestamp()}",
                    agent_type=AgentType.DIRECT_RESPONDER,
                    intent=QueryIntent.DIRECT_ANSWER,
                    query=query,
                    context=context or {},
                    priority=1
                )]


class DocumentRetrieverAgent:
    """Retrieves relevant documents from knowledge base"""
    
    def __init__(self, ollama_service: OllamaService, qdrant_service=None):
        self.ollama_service = ollama_service
        self.qdrant_service = qdrant_service
        
    async def retrieve_documents(self, task: AgentTask) -> AgentResponse:
        """Retrieve relevant documents for a query"""
        start_time = datetime.now()
        
        try:
            if not self.qdrant_service:
                return AgentResponse(
                    agent_type=AgentType.DOCUMENT_RETRIEVER,
                    task_id=task.task_id,
                    success=False,
                    result={"error": "Qdrant service not available"},
                    reasoning="Cannot retrieve documents without vector database",
                    confidence=0.0,
                    execution_time=0.0
                )
            
            # Generate query embedding
            query_embedding = await self.ollama_service.generate_embedding(task.query)
            
            # Create proper DocumentSearchRequest object
            from ..models.document import DocumentSearchRequest
            search_request = DocumentSearchRequest(
                query=task.query,
                top_k=10,
                similarity_threshold=0.25,  # Lower threshold for financial data
                use_reranking=True,
                rerank_top_k=5
            )
            
            # Search documents
            search_results = await self.qdrant_service.search_similar_chunks(
                query_embedding=query_embedding,
                search_request=search_request,
                document_metadata=task.context.get("metadata_store", {})
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResponse(
                agent_type=AgentType.DOCUMENT_RETRIEVER,
                task_id=task.task_id,
                success=True,
                result={
                    "documents": search_results,
                    "total_found": len(search_results)
                },
                reasoning=f"Retrieved {len(search_results)} relevant documents using semantic search",
                confidence=0.8 if search_results else 0.2,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResponse(
                agent_type=AgentType.DOCUMENT_RETRIEVER,
                task_id=task.task_id,
                success=False,
                result={"error": str(e)},
                reasoning=f"Document retrieval failed: {str(e)}",
                confidence=0.0,
                execution_time=execution_time
            )


class FinancialAnalyzerAgent:
    """Analyzes financial data and performs calculations"""
    
    def __init__(self, ollama_service: OllamaService):
        self.ollama_service = ollama_service
        
    async def analyze_financial_data(self, task: AgentTask) -> AgentResponse:
        """Perform financial analysis based on the task"""
        start_time = datetime.now()
        
        analysis_prompt = f"""
        You are a financial analysis expert. Analyze the following query and provide detailed insights.
        
        Query: {task.query}
        Context: {json.dumps(task.context, indent=2)}
        
        Provide analysis for:
        1. Key financial metrics and ratios
        2. Performance trends and patterns
        3. Risk assessment
        4. Actionable insights
        5. Data quality assessment
        
        Format your response as JSON:
        {{
            "analysis": "detailed analysis text",
            "key_metrics": ["metric1", "metric2"],
            "insights": ["insight1", "insight2"],
            "recommendations": ["rec1", "rec2"],
            "risk_factors": ["risk1", "risk2"],
            "confidence_level": 0.0-1.0,
            "data_sources": ["source1", "source2"]
        }}
        """
        
        try:
            response = await self.ollama_service.generate_response(analysis_prompt)
            result = json.loads(response)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResponse(
                agent_type=AgentType.FINANCIAL_ANALYZER,
                task_id=task.task_id,
                success=True,
                result=result,
                reasoning="Completed comprehensive financial analysis",
                confidence=result.get("confidence_level", 0.7),
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResponse(
                agent_type=AgentType.FINANCIAL_ANALYZER,
                task_id=task.task_id,
                success=False,
                result={"error": str(e)},
                reasoning=f"Financial analysis failed: {str(e)}",
                confidence=0.0,
                execution_time=execution_time
            )


class PortfolioAnalyzerAgent:
    """Specialized agent for portfolio performance analysis"""
    
    def __init__(self, ollama_service: OllamaService):
        self.ollama_service = ollama_service
        
    async def analyze_portfolio(self, task: AgentTask) -> AgentResponse:
        """Analyze portfolio performance, attribution, and metrics"""
        start_time = datetime.now()
        
        portfolio_prompt = f"""
        You are a portfolio analysis expert specializing in performance attribution, AUM analysis, and investment performance.
        
        Query: {task.query}
        Context: {json.dumps(task.context, indent=2)}
        
        Provide comprehensive portfolio analysis including:
        1. Performance attribution analysis
        2. Top/bottom performers identification
        3. AUM (Assets Under Management) insights
        4. Risk-adjusted returns
        5. Benchmark comparisons
        6. Sector/asset allocation analysis
        
        Format response as JSON:
        {{
            "performance_summary": "overall performance summary",
            "top_performers": [
                {{"name": "asset", "performance": "X%", "attribution": "reason"}}
            ],
            "bottom_performers": [
                {{"name": "asset", "performance": "X%", "attribution": "reason"}}
            ],
            "aum_analysis": "AUM insights and trends",
            "risk_metrics": {{"sharpe_ratio": 0.0, "volatility": "X%", "max_drawdown": "X%"}},
            "attribution_factors": ["factor1", "factor2"],
            "recommendations": ["rec1", "rec2"],
            "confidence": 0.0-1.0
        }}
        """
        
        try:
            response = await self.ollama_service.generate_response(portfolio_prompt)
            result = json.loads(response)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResponse(
                agent_type=AgentType.PORTFOLIO_ANALYZER,
                task_id=task.task_id,
                success=True,
                result=result,
                reasoning="Completed portfolio performance analysis",
                confidence=result.get("confidence", 0.8),
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResponse(
                agent_type=AgentType.PORTFOLIO_ANALYZER,
                task_id=task.task_id,
                success=False,
                result={"error": str(e)},
                reasoning=f"Portfolio analysis failed: {str(e)}",
                confidence=0.0,
                execution_time=execution_time
            )


class DirectResponderAgent:
    """Handles direct questions that don't require document retrieval"""
    
    def __init__(self, ollama_service: OllamaService):
        self.ollama_service = ollama_service
        
    async def generate_direct_response(self, task: AgentTask) -> AgentResponse:
        """Generate direct response using LLM knowledge"""
        start_time = datetime.now()
        
        direct_prompt = f"""
        You are a financial expert AI assistant. Answer this question directly using your knowledge.
        Be precise, professional, and provide actionable information.
        
        Question: {task.query}
        Context: {json.dumps(task.context, indent=2)}
        
        Provide a comprehensive answer that includes:
        1. Direct answer to the question
        2. Relevant financial principles or concepts
        3. Practical implications
        4. Any important disclaimers or considerations
        """
        
        try:
            response = await self.ollama_service.generate_response(direct_prompt)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResponse(
                agent_type=AgentType.DIRECT_RESPONDER,
                task_id=task.task_id,
                success=True,
                result={"answer": response},
                reasoning="Generated direct response using LLM knowledge",
                confidence=0.7,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResponse(
                agent_type=AgentType.DIRECT_RESPONDER,
                task_id=task.task_id,
                success=False,
                result={"error": str(e)},
                reasoning=f"Direct response failed: {str(e)}",
                confidence=0.0,
                execution_time=execution_time
            )


class ResponseSynthesizerAgent:
    """Synthesizes responses from multiple agents into coherent final answer"""
    
    def __init__(self, ollama_service: OllamaService):
        self.ollama_service = ollama_service
        
    async def synthesize_responses(
        self, 
        original_query: str,
        agent_responses: List[AgentResponse],
        context: Dict[str, Any] = None
    ) -> AgentResponse:
        """Synthesize multiple agent responses into coherent final response"""
        start_time = datetime.now()
        
        # Prepare synthesis prompt
        responses_text = ""
        for resp in agent_responses:
            if resp.success:
                responses_text += f"\n\n{resp.agent_type.value} response:\n"
                responses_text += f"Reasoning: {resp.reasoning}\n"
                responses_text += f"Result: {json.dumps(resp.result, indent=2)}\n"
                responses_text += f"Confidence: {resp.confidence}\n"
        
        synthesis_prompt = f"""
        You are a response synthesis expert. Combine the following agent responses into a coherent, 
        comprehensive answer to the original query.
        
        Original Query: {original_query}
        Context: {json.dumps(context or {}, indent=2)}
        
        Agent Responses:
        {responses_text}
        
        Create a unified response that:
        1. Directly answers the original question
        2. Integrates insights from all successful agent responses
        3. Maintains professional financial advisory tone
        4. Includes relevant data and evidence
        5. Provides actionable recommendations where appropriate
        6. Notes any limitations or uncertainties
        
        Format as a clear, well-structured response suitable for financial professionals.
        """
        
        try:
            synthesized_response = await self.ollama_service.generate_response(synthesis_prompt)
            
            # Calculate overall confidence based on agent responses
            successful_responses = [r for r in agent_responses if r.success]
            overall_confidence = (
                sum(r.confidence for r in successful_responses) / len(successful_responses)
                if successful_responses else 0.0
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResponse(
                agent_type=AgentType.RESPONSE_SYNTHESIZER,
                task_id=f"synthesis_{datetime.now().timestamp()}",
                success=True,
                result={
                    "final_answer": synthesized_response,
                    "agent_count": len(agent_responses),
                    "successful_agents": len(successful_responses),
                    "confidence": overall_confidence
                },
                reasoning="Synthesized responses from multiple specialized agents",
                confidence=overall_confidence,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResponse(
                agent_type=AgentType.RESPONSE_SYNTHESIZER,
                task_id=f"synthesis_error_{datetime.now().timestamp()}",
                success=False,
                result={"error": str(e)},
                reasoning=f"Response synthesis failed: {str(e)}",
                confidence=0.0,
                execution_time=execution_time
            )


class MultiAgentOrchestrator:
    """Orchestrates multiple agents to handle complex financial queries"""
    
    def __init__(
        self, 
        ollama_service: OllamaService,
        qdrant_service=None,
        document_metadata_store: Dict[str, Any] = None
    ):
        self.ollama_service = ollama_service
        self.qdrant_service = qdrant_service
        self.metadata_store = document_metadata_store or {}
        
        # Initialize agents
        self.query_decomposer = QueryDecomposerAgent(ollama_service)
        self.document_retriever = DocumentRetrieverAgent(ollama_service, qdrant_service)
        self.financial_analyzer = FinancialAnalyzerAgent(ollama_service)
        self.portfolio_analyzer = PortfolioAnalyzerAgent(ollama_service)
        self.direct_responder = DirectResponderAgent(ollama_service)
        self.response_synthesizer = ResponseSynthesizerAgent(ollama_service)
        
    async def process_query(
        self, 
        query: str, 
        context: Dict[str, Any] = None,
        use_rag: bool = True
    ) -> Dict[str, Any]:
        """Main orchestration method for processing complex queries"""
        
        # Add metadata store to context
        full_context = {
            **(context or {}),
            "metadata_store": self.metadata_store,
            "use_rag": use_rag
        }
        
        # Step 1: If RAG is enabled, force document retrieval (bypass complex decomposition for now)
        if use_rag:
            tasks = [
                AgentTask(
                    task_id=f"forced_doc_retrieval_{datetime.now().timestamp()}",
                    agent_type=AgentType.DOCUMENT_RETRIEVER,
                    intent=QueryIntent.DOCUMENT_RELATED,
                    query=query,
                    context=full_context,
                    priority=1
                )
            ]
        else:
            # Step 1: Decompose query into tasks
            tasks = await self.query_decomposer.decompose_query(query, full_context)
        
        # Step 2: Execute tasks based on their types
        agent_responses = []
        
        for task in tasks:
            task.context.update(full_context)
            
            if task.agent_type == AgentType.DOCUMENT_RETRIEVER:
                response = await self.document_retriever.retrieve_documents(task)
            elif task.agent_type == AgentType.FINANCIAL_ANALYZER:
                response = await self.financial_analyzer.analyze_financial_data(task)
            elif task.agent_type == AgentType.PORTFOLIO_ANALYZER:
                response = await self.portfolio_analyzer.analyze_portfolio(task)
            elif task.agent_type == AgentType.DIRECT_RESPONDER:
                response = await self.direct_responder.generate_direct_response(task)
            else:
                # Default to direct responder
                response = await self.direct_responder.generate_direct_response(task)
            
            agent_responses.append(response)
        
        # Step 3: Synthesize responses
        if len(agent_responses) > 1:
            final_response = await self.response_synthesizer.synthesize_responses(
                query, agent_responses, full_context
            )
        else:
            final_response = agent_responses[0] if agent_responses else AgentResponse(
                agent_type=AgentType.DIRECT_RESPONDER,
                task_id="fallback",
                success=False,
                result={"error": "No agents available"},
                reasoning="System fallback",
                confidence=0.0,
                execution_time=0.0
            )
        
        # Return structured response
        return {
            "answer": final_response.result.get("final_answer", final_response.result.get("answer", "I couldn't process your query.")),
            "confidence": final_response.confidence,
            "agent_responses": [
                {
                    "agent": resp.agent_type.value,
                    "success": resp.success,
                    "confidence": resp.confidence,
                    "execution_time": resp.execution_time
                }
                for resp in agent_responses
            ],
            "total_agents_used": len(agent_responses),
            "processing_time": sum(resp.execution_time for resp in agent_responses),
            "sources": self._extract_sources(agent_responses)
        }
    
    def _extract_sources(self, agent_responses: List[AgentResponse]) -> List[Dict[str, Any]]:
        """Extract document sources from agent responses"""
        sources = []
        
        for response in agent_responses:
            if (response.agent_type == AgentType.DOCUMENT_RETRIEVER and 
                response.success and 
                "documents" in response.result):
                
                for doc in response.result["documents"]:
                    sources.append({
                        "filename": doc.get("document_metadata", {}).get("filename", "Unknown"),
                        "content": doc.get("content", "")[:200] + "...",
                        "confidence": doc.get("score", 0.0),
                        "document_type": doc.get("document_metadata", {}).get("document_type", "unknown")
                    })
        
        return sources