export enum DocumentType {
  FINANCIAL_REPORT = 'financial_report',
  LEGAL_CONTRACT = 'legal_contract',
  COMPLIANCE_REPORT = 'compliance_report',
  MARKET_ANALYSIS = 'market_analysis',
  PERFORMANCE_ATTRIBUTION = 'performance_attribution',
  OTHER = 'other'
}

export enum ConfidenceLevel {
  HIGH = 'high',
  MEDIUM = 'medium',
  LOW = 'low'
}

export interface FinancialMetrics {
  revenue?: number;
  ebitda?: number;
  net_income?: number;
  total_assets?: number;
  total_liabilities?: number;
  equity?: number;
  cash_flow?: number;
  debt_to_equity?: number;
  roe?: number;
  roa?: number;
  profit_margin?: number;
}

export interface DocumentMetadata {
  filename: string;
  file_size: number;
  file_type: string;
  document_type: DocumentType;
  upload_timestamp: string;
  processed_timestamp?: string;
  
  fiscal_year?: number;
  fiscal_quarter?: string;
  reporting_period?: string;
  company_name?: string;
  industry_sector?: string;
  currency?: string;
  
  total_pages: number;
  total_chunks: number;
  has_tables: boolean;
  has_charts: boolean;
  has_financial_data: boolean;
  
  language: string;
  confidence_score: number;
  key_topics: string[];
  named_entities: string[];
  
  financial_metrics?: FinancialMetrics;
  
  attribution_period?: string;
  benchmark_name?: string;
  portfolio_name?: string;
  
  tags: string[];
  custom_fields: { [key: string]: any };
}

export interface DocumentSearchResult {
  chunk_id: string;
  document_id: string;
  content: string;
  score: number;
  rerank_score?: number;
  confidence_level: ConfidenceLevel;
  
  document_metadata: DocumentMetadata;
  chunk_metadata: { [key: string]: any };
  
  page_number?: number;
  section_title?: string;
}

export interface DocumentSearchRequest {
  query: string;
  top_k?: number;
  rerank_top_k?: number;
  similarity_threshold?: number;
  
  document_types?: DocumentType[];
  fiscal_years?: number[];
  companies?: string[];
  tags?: string[];
  date_range?: { start: string; end: string };
  
  use_reranking?: boolean;
  reranking_strategy?: string;
}

export interface DocumentSearchResponse {
  query: string;
  total_results: number;
  results: DocumentSearchResult[];
  search_time_ms: number;
  reranking_used: boolean;
  filters_applied: { [key: string]: any };
}

export interface DocumentUpload {
  filename: string;
  content_type: string;
  file_size: number;
  document_type: DocumentType;
  tags: string[];
  custom_fields: { [key: string]: any };
}

export interface DocumentListItem {
  document_id: string;
  filename: string;
  document_type: DocumentType;
  upload_timestamp: string;
  total_pages: number;
  total_chunks: number;
  has_financial_data: boolean;
  confidence_score: number;
  tags: string[];
}

export interface DocumentStats {
  total_documents: number;
  total_chunks: number;
  documents_with_financial_data: number;
  document_types: { [key: string]: number };
  average_chunks_per_document: number;
}