/**
 * TypeScript Data Models for RepoPilot API Contracts
 */

export type RepositoryStatus = "registered" | "indexing" | "ready" | "failed" | "stale";

export interface RepositoryRecord {
  repository_id: string;
  canonical_path: string;
  display_name: string;
  status: RepositoryStatus;
  created_at: string;
  updated_at: string;
  last_indexed_at?: string | null;
  indexed_file_count: number;
  indexed_chunk_count: number;
  embedding_enabled: boolean;
  error_message?: string | null;
  source_type?: "local" | "github";
  github_url?: string | null;
}

export interface IndexingSummary {
  repository_id: string;
  status: RepositoryStatus;
  files_discovered: number;
  files_parsed: number;
  files_skipped: number;
  chunks_created: number;
  chunks_updated: number;
  chunks_deleted: number;
  embeddings_generated: number;
  embeddings_reused: number;
  duration_ms: number;
  error_message?: string | null;
}

export interface Citation {
  relative_path: string;
  index_number: number;
  is_valid: boolean;
  start_line?: number | null;
  end_line?: number | null;
  symbol_name?: string | null;
}

export interface PerformanceMetrics {
  retrieval_ms: number;
  evidence_selection_ms: number;
  context_assembly_ms: number;
  llm_generation_ms: number;
  total_ms: number;
}

export interface RAGRequest {
  repository_path: string;
  question: string;
  mode?: "auto" | "keyword" | "semantic" | "hybrid";
  top_k?: number;
  min_relevance_score?: number;
  max_context_chars?: number;
}

export interface RAGResponse {
  question: string;
  answer: string;
  status: "grounded" | "insufficient_evidence" | "error" | "unusable_output";
  citations: Citation[];
  retrieval_mode: string;
  retrieved_candidate_count: number;
  evidence_count: number;
  valid_citation_count: number;
  invalid_citation_count: number;
  context_character_count: number;
  context_truncated: boolean;
  provider_name: string;
  model_name: string;
  performance_ms: PerformanceMetrics;
}

export interface HealthResponse {
  status: string;
}
