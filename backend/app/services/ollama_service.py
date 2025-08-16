import httpx
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
import time

from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.documents import Document as LangChainDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Qdrant as LangChainQdrant
from langchain_core.retrievers import BaseRetriever

from ..core.config import settings

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.embedding_model = settings.EMBEDDING_MODEL
        self.llm_model = settings.LLM_MODEL
        self.timeout = 300  # 5 minutes for LLM generation
        
        # Initialize LangChain components
        self.llm = OllamaLLM(
            model=self.llm_model,
            base_url=self.base_url,
            temperature=0.1
        )
        
        self.embeddings = OllamaEmbeddings(
            model=self.embedding_model,
            base_url=self.base_url
        )
        
        # Text splitter for document processing
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
    async def health_check(self) -> bool:
        """Check if Ollama is accessible and models are available"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Check if Ollama is running
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code != 200:
                    raise Exception(f"Ollama not accessible: {response.status_code}")
                
                models = response.json()
                model_names = [model["name"] for model in models.get("models", [])]
                
                # Check if required models are available
                if self.embedding_model not in model_names:
                    logger.warning(f"Embedding model {self.embedding_model} not found. Available models: {model_names}")
                    # Try to pull the model
                    await self._pull_model(self.embedding_model)
                
                if self.llm_model not in model_names:
                    logger.warning(f"LLM model {self.llm_model} not found. Available models: {model_names}")
                    # Try to pull the model
                    await self._pull_model(self.llm_model)
                
                return True
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            raise

    async def _pull_model(self, model_name: str) -> bool:
        """Pull a model from Ollama registry"""
        try:
            async with httpx.AsyncClient(timeout=600) as client:  # 10 minutes for model download
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name}
                )
                if response.status_code == 200:
                    logger.info(f"Successfully pulled model: {model_name}")
                    return True
                else:
                    logger.error(f"Failed to pull model {model_name}: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Error pulling model {model_name}: {e}")
            return False

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        try:
            embeddings = []
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for text in texts:
                    response = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json={
                            "model": self.embedding_model,
                            "prompt": text
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        embeddings.append(result["embedding"])
                    else:
                        logger.error(f"Failed to generate embedding: {response.text}")
                        # Return zero vector as fallback
                        embeddings.append([0.0] * 768)
            
            logger.info(f"Generated embeddings for {len(texts)} texts")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text using LangChain"""
        try:
            # Use LangChain embeddings
            embedding = await asyncio.to_thread(self.embeddings.embed_query, text)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding with LangChain: {e}")
            # Fallback to original method
            embeddings = await self.generate_embeddings([text])
            return embeddings[0]

    async def generate_response(
        self, 
        prompt: str, 
        context: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a response using the LLM"""
        try:
            start_time = time.time()
            
            # Build the full prompt
            full_prompt = self._build_prompt(prompt, context, system_prompt)
            print(full_prompt)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.llm_model,
                        "prompt": full_prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                            "top_k": 40,
                            "top_p": 0.9,
                            "repeat_penalty": 1.12
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    generation_time = time.time() - start_time
                    
                    return {
                        "response": result["response"].strip(),
                        "generation_time_ms": generation_time * 1000,
                        "prompt_eval_count": result.get("prompt_eval_count", 0),
                        "eval_count": result.get("eval_count", 0),
                        "total_duration": result.get("total_duration", 0),
                        "prompt": full_prompt
                    }
                else:
                    logger.error(f"Failed to generate response: {response.text}")
                    raise Exception(f"LLM generation failed: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise

    async def generate_response_stream(
        self, 
        prompt: str, 
        context: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response using the LLM"""
        try:
            full_prompt = self._build_prompt(prompt, context, system_prompt)
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.llm_model,
                        "prompt": full_prompt,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                            "top_k": 40,
                            "top_p": 0.9,
                            "repeat_penalty": 1.1
                        }
                    }
                ) as response:
                    if response.status_code == 200:
                        async for line in response.aiter_lines():
                            if line.strip():
                                try:
                                    data = json.loads(line)
                                    if "response" in data:
                                        yield data["response"]
                                    if data.get("done", False):
                                        break
                                except json.JSONDecodeError:
                                    continue
                    else:
                        raise Exception(f"Streaming generation failed: {response.status_code}")
                        
        except Exception as e:
            logger.error(f"Failed to generate streaming response: {e}")
            raise

    def _build_prompt(
        self, 
        user_prompt: str, 
        context: Optional[str] = None, 
        system_prompt: Optional[str] = None
    ) -> str:
        """Build a comprehensive prompt for financial RAG"""
        
        default_system_prompt = """You are a sophisticated financial AI assistant specialized in analyzing financial documents, reports, and data. You have access to a comprehensive knowledge base of financial documents including:

- Financial reports with revenue, EBITDA, and performance metrics
- Legal investment contracts and terms
- Compliance reports with regulatory matrices  
- Market analysis and performance attribution data

Guidelines for responses:
1. Provide accurate, precise financial analysis based on the provided context
2. Always cite specific sources when referencing data
3. Use proper financial terminology and calculations
4. Highlight any assumptions or limitations in your analysis
5. If context is insufficient, clearly state what additional information would be needed
6. Format numerical data clearly with appropriate units and currencies
7. Consider regulatory compliance and risk factors in your responses

When analyzing financial data:
- Verify calculations and ratios
- Consider industry benchmarks and standards
- Highlight trends and anomalies
- Provide context for performance metrics
- Consider seasonal and cyclical factors"""

        prompt_parts = []
        
        # Add system prompt
        if system_prompt:
            prompt_parts.append(f"SYSTEM: {system_prompt}")
        else:
            prompt_parts.append(f"SYSTEM: {default_system_prompt}")
        
        # # Add context if provided
        # if context:
        #     prompt_parts.append(f"CONTEXT: Based on the following financial documents and data:\n{context}")
        
        # Add user question
        # prompt_parts.append(f"USER: {user_prompt}")
        # prompt_parts.append("ASSISTANT:")
        prompt_parts.append(f"{user_prompt}")
        # prompt_parts.append("ASSISTANT:")
        
        return "\n\n".join(prompt_parts)

    async def summarize_document(self, content: str, document_type: str) -> str:
        """Generate a summary of a financial document"""
        prompt = f"""Please provide a comprehensive summary of this {document_type} document. Include:

1. Key financial metrics and figures
2. Main findings or conclusions
3. Important dates and periods
4. Risk factors or notable items
5. Executive summary points

Document content:
{content[:4000]}  # Truncate to avoid token limits
"""
        
        result = await self.generate_response(prompt, temperature=0.1)
        return result["response"]

    async def extract_financial_entities(self, content: str) -> Dict[str, List[str]]:
        """Extract financial entities from text"""
        prompt = f"""Extract financial entities from the following text. Return as JSON with these categories:

- companies: Company names
- metrics: Financial metrics (revenue, EBITDA, etc.)
- currencies: Currency mentions
- dates: Important dates
- people: Executive names
- locations: Geographic locations
- products: Product/service names

Text:
{content[:3000]}

Respond only with valid JSON."""

        try:
            result = await self.generate_response(prompt, temperature=0.0)
            # Try to parse as JSON
            import json
            entities = json.loads(result["response"])
            return entities
        except:
            # Fallback to empty dict if JSON parsing fails
            return {
                "companies": [],
                "metrics": [],
                "currencies": [],
                "dates": [],
                "people": [],
                "locations": [],
                "products": []
            }

    async def generate_rag_response(
        self,
        query: str,
        context_documents: List[Dict[str, Any]],
        conversation_history: List[Dict[str, str]] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Generate a response using RAG with document context"""
        try:
            start_time = time.time()
            
            # Prepare context from documents
            context_text = ""
            if context_documents:
                context_text = "\n\n".join([
                    f"Document: {doc.get('filename', 'Unknown')}\n{doc.get('content', '')}"
                    for doc in context_documents
                ])
            
            # Build conversation context
            conversation_context = ""
            if conversation_history:
                conversation_context = "\n".join([
                    f"{'Human' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                    for msg in conversation_history[-5:]  # Last 5 messages
                ])
            
            # Create the prompt template
            prompt_template = PromptTemplate(
                input_variables=["context", "conversation_history", "question"],
                template="""You are a sophisticated financial AI assistant. Use the following context from financial documents to answer the question. If the context doesn't contain relevant information, say so clearly.

DOCUMENT CONTEXT:
{context}

CONVERSATION HISTORY:
{conversation_history}

QUESTION: {question}

INSTRUCTIONS:
1. Base your answer primarily on the provided document context
2. Be specific and cite relevant details from the documents
3. If the context doesn't contain enough information, clearly state what additional information would be needed
4. Use proper financial terminology and provide accurate analysis
5. Consider the conversation history for continuity

ANSWER:"""
            )
            
            # Format the prompt
            formatted_prompt = prompt_template.format(
                context=context_text if context_text else "No document context available.",
                conversation_history=conversation_context if conversation_context else "No previous conversation.",
                question=query
            )
            
            # Generate response using LangChain LLM
            response = await asyncio.to_thread(self.llm.invoke, formatted_prompt)
            
            generation_time = time.time() - start_time
            
            return {
                "response": response.strip(),
                "generation_time_ms": generation_time * 1000,
                "context_used": len(context_documents),
                "has_context": bool(context_documents),
                "prompt": formatted_prompt
            }
            
        except Exception as e:
            logger.error(f"Failed to generate RAG response: {e}")
            raise
