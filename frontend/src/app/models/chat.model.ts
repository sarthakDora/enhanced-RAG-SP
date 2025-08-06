import { DocumentSearchResult } from './document.model';

export interface ChatMessage {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  
  sources?: DocumentSearchResult[];
  confidence_score?: number;
  processing_time_ms?: number;
  
  metadata?: { [key: string]: any };
}

export interface ChatSession {
  session_id: string;
  user_id?: string;
  title: string;
  created_at: string;
  updated_at: string;
  
  messages: ChatMessage[];
  
  max_history: number;
  context_window: number;
  temperature: number;
  
  active_documents: string[];
  financial_context: { [key: string]: any };
  
  is_active: boolean;
  last_activity: string;
}

export interface ChatRequest {
  session_id?: string;
  message: string;
  
  use_rag?: boolean;
  top_k?: number;
  rerank_top_k?: number;
  similarity_threshold?: number;
  
  temperature?: number;
  max_tokens?: number;
  
  document_filters?: { [key: string]: any };
  financial_context?: { [key: string]: any };
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  response: string;
  sources: DocumentSearchResult[];
  
  search_time_ms: number;
  generation_time_ms: number;
  total_time_ms: number;
  
  confidence_score: number;
  source_count: number;
  context_used: boolean;
  
  message_count: number;
  session_active: boolean;
}

export interface TypingIndicator {
  session_id: string;
  is_typing: boolean;
  timestamp: string;
}

export interface ChatFilter {
  document_types?: string[];
  fiscal_years?: number[];
  companies?: string[];
  tags?: string[];
  date_range?: {
    start: string;
    end: string;
  };
}

export interface ChatSettings {
  temperature: number;
  max_tokens: number;
  top_k: number;
  rerank_top_k: number;
  similarity_threshold: number;
  use_rag: boolean;
  reranking_strategy: string;
}