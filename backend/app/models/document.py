from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class DocumentType(str, Enum):
    FINANCIAL_REPORT = "financial_report"
    LEGAL_CONTRACT = "legal_contract"
    COMPLIANCE_REPORT = "compliance_report"
    MARKET_ANALYSIS = "market_analysis"
    PERFORMANCE_ATTRIBUTION = "performance_attribution"
    VBAM_SUPPORT = "vbam_support"
    OTHER = "other"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium" 
    LOW = "low"

class FinancialMetrics(BaseModel):
    revenue: Optional[float] = None
    ebitda: Optional[float] = None
    net_income: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    equity: Optional[float] = None
    cash_flow: Optional[float] = None
    debt_to_equity: Optional[float] = None
    roe: Optional[float] = None  # Return on Equity
    roa: Optional[float] = None  # Return on Assets
    profit_margin: Optional[float] = None

class DocumentMetadata(BaseModel):
    # Basic document info
    filename: str
    file_size: int
    file_type: str
    document_type: DocumentType
    upload_timestamp: datetime
    processed_timestamp: Optional[datetime] = None
    
    # Financial metadata
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[str] = None
    reporting_period: Optional[str] = None
    company_name: Optional[str] = None
    industry_sector: Optional[str] = None
    currency: Optional[str] = None
    
    # Document structure
    total_pages: int
    total_chunks: int
    has_tables: bool = False
    has_charts: bool = False
    has_financial_data: bool = False
    
    # Content analysis
    language: str = "en"
    confidence_score: float
    key_topics: List[str] = []
    named_entities: List[str] = []
    
    # Financial metrics
    financial_metrics: Optional[FinancialMetrics] = None
    
    # Performance attribution specific
    attribution_period: Optional[str] = None
    benchmark_name: Optional[str] = None
    portfolio_name: Optional[str] = None
    
    # Additional metadata
    tags: List[str] = []
    custom_fields: Dict[str, Any] = {}

class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    chunk_index: int
    
    # Positioning
    page_number: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    
    # Chunk metadata
    chunk_type: str = "text"  # text, table, chart, header, footer
    section_title: Optional[str] = None
    subsection_title: Optional[str] = None
    
    # Financial context
    contains_financial_data: bool = False
    financial_keywords: List[str] = []
    table_data: Optional[Dict[str, Any]] = None
    
    # Vector data
    embedding: Optional[List[float]] = None
    embedding_model: str
    
    # Processing metadata
    processed_timestamp: datetime
    confidence_score: float
    
    class Config:
        arbitrary_types_allowed = True

class Document(BaseModel):
    document_id: str
    metadata: DocumentMetadata
    chunks: List[DocumentChunk] = []
    processing_status: str = "pending"  # pending, processing, completed, failed
    error_message: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True

class DocumentUpload(BaseModel):
    filename: str
    content_type: str
    file_size: int
    document_type: DocumentType = DocumentType.OTHER
    tags: List[str] = []
    custom_fields: Dict[str, Any] = {}

class DocumentSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=20, le=100)
    rerank_top_k: int = Field(default=5, le=20)
    similarity_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    
    # Filters
    document_types: Optional[List[DocumentType]] = None
    fiscal_years: Optional[List[int]] = None
    companies: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    date_range: Optional[Dict[str, datetime]] = None
    
    # Search strategy
    use_reranking: bool = True
    reranking_strategy: str = "hybrid"  # semantic, metadata, financial, hybrid

class DocumentSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float
    rerank_score: Optional[float] = None
    confidence_level: ConfidenceLevel
    
    # Context
    document_metadata: DocumentMetadata
    chunk_metadata: Dict[str, Any]
    
    # Source attribution
    page_number: Optional[int] = None
    section_title: Optional[str] = None

class DocumentSearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[DocumentSearchResult]
    search_time_ms: float
    reranking_used: bool
    filters_applied: Dict[str, Any]