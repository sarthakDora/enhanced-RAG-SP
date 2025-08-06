from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from .document import DocumentSearchResult

class ChatMessage(BaseModel):
    message_id: str
    session_id: str
    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    
    # For assistant messages
    sources: Optional[List[DocumentSearchResult]] = None
    confidence_score: Optional[float] = None
    processing_time_ms: Optional[float] = None
    
    # Metadata
    metadata: Dict[str, Any] = {}

class ChatSession(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    title: str = "New Conversation"
    created_at: datetime
    updated_at: datetime
    
    # Messages
    messages: List[ChatMessage] = []
    
    # Session settings
    max_history: int = 50
    context_window: int = 4000
    temperature: float = 0.1
    
    # Financial context
    active_documents: List[str] = []  # document_ids
    financial_context: Dict[str, Any] = {}
    
    # Status
    is_active: bool = True
    last_activity: datetime

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    
    # Search parameters
    use_rag: bool = True
    top_k: int = Field(default=10, le=50)
    rerank_top_k: int = Field(default=3, le=10)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Generation parameters
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1000, le=4000)
    
    # Context filters
    document_filters: Optional[Dict[str, Any]] = None
    financial_context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    response: str
    sources: List[DocumentSearchResult] = []
    
    # Performance metrics
    search_time_ms: float
    generation_time_ms: float
    total_time_ms: float
    
    # Quality metrics
    confidence_score: float
    source_count: int
    context_used: bool
    
    # Session info
    message_count: int
    session_active: bool

class ChatHistoryRequest(BaseModel):
    session_id: str
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)

class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]
    total_messages: int
    has_more: bool

class SessionListResponse(BaseModel):
    sessions: List[ChatSession]
    total_sessions: int
    
class TypingIndicator(BaseModel):
    session_id: str
    is_typing: bool
    timestamp: datetime