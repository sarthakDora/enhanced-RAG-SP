from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os

class Settings(BaseSettings):
    # Ollama Configuration
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    EMBEDDING_MODEL: str = Field(default="nomic-embed-text:latest")
    # LLM_MODEL: str = Field(default="llama3.2:latest")
    LLM_MODEL: str = Field(default="gemma3:latest")
    
    # Qdrant Configuration
    QDRANT_URL: str = Field(default="http://localhost:6333")
    QDRANT_API_KEY: str = Field(default="")
    COLLECTION_NAME: str = Field(default="financial_documents")
    
    # FastAPI Configuration
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=True)
    
    # File Processing Configuration
    MAX_FILE_SIZE: int = Field(default=1073741824)  # 1GB (increased for Excel files)
    ALLOWED_EXTENSIONS: str = Field(default="pdf,docx,txt,xlsx,xls")
    UPLOAD_DIR: str = Field(default="./uploads")
    PROCESSED_DIR: str = Field(default="./processed")
    
    # Upload Configuration
    MAX_REQUEST_SIZE: int = Field(default=1073741824)  # 1GB request body limit
    UPLOAD_TIMEOUT: int = Field(default=600)  # 10 minutes timeout for large Excel files
    
    # Vector Search Configuration
    DEFAULT_TOP_K: int = Field(default=20)
    RERANK_TOP_K: int = Field(default=5)
    SIMILARITY_THRESHOLD: float = Field(default=0.7)
    
    # Financial Metadata Configuration
    EXTRACT_FINANCIAL_METRICS: bool = Field(default=True)
    EXTRACT_TABLES: bool = Field(default=True)
    EXTRACT_CHARTS: bool = Field(default=True)
    OCR_ENABLED: bool = Field(default=True)
    
    # Chat Configuration
    MAX_CHAT_HISTORY: int = Field(default=50)
    CONVERSATION_TIMEOUT: int = Field(default=3600)  # 1 hour
    
    # Security
    SECRET_KEY: str = Field(default="your-secret-key-change-this-in-production")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.PROCESSED_DIR, exist_ok=True)
        os.makedirs("logs", exist_ok=True)
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(',')]

settings = Settings()