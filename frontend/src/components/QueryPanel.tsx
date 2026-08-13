import React, { useState } from "react";
import { Search, Sparkles, Sliders } from "lucide-react";
import type { RAGRequest, RepositoryRecord } from "../api/types";

interface QueryPanelProps {
  activeRepository: RepositoryRecord | null;
  onQuerySubmit: (req: RAGRequest) => Promise<void>;
  isLoading: boolean;
}

export const QueryPanel: React.FC<QueryPanelProps> = ({
  activeRepository,
  onQuerySubmit,
  isLoading,
}) => {
  const [question, setQuestion] = useState<string>("");
  const [mode, setMode] = useState<"auto" | "keyword" | "semantic" | "hybrid">("auto");
  const [topK, setTopK] = useState<number>(8);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || !activeRepository || isLoading) return;

    onQuerySubmit({
      repository_path: activeRepository.canonical_path,
      question: question.trim(),
      mode,
      top_k: topK,
      min_relevance_score: 0.005,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      handleSubmit(e);
    }
  };

  return (
    <div className="query-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Sparkles size={18} style={{ color: "var(--accent-primary)" }} />
          <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Ask Codebase Question</h3>
        </div>
        {activeRepository && (
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            Repo: {activeRepository.display_name} ({activeRepository.status})
          </span>
        )}
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
        <textarea
          className="textarea-input"
          style={{ minHeight: "90px", resize: "vertical" }}
          placeholder={
            activeRepository && activeRepository.status === "ready"
              ? 'Ask any natural language question about the repository (e.g. "Where is authentication or scanner implemented?", "Where is SQLiteFTSIndex defined?")'
              : activeRepository
              ? "Repository is not ready for querying yet. Please trigger indexing first."
              : "Select or register a repository to start asking questions."
          }
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!activeRepository || activeRepository.status !== "ready" || isLoading}
        />

        <div className="query-controls">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={
              !question.trim() ||
              !activeRepository ||
              activeRepository.status !== "ready" ||
              isLoading
            }
          >
            {isLoading ? (
              <>
                <Search size={16} className="animate-spin" /> Querying RAG Pipeline...
              </>
            ) : (
              <>
                <Search size={16} /> Ask RepoPilot (Ctrl+Enter)
              </>
            )}
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            style={{ fontSize: "0.8rem", padding: "0.4rem 0.6rem" }}
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            <Sliders size={14} /> Pipeline Settings
          </button>
        </div>

        {showAdvanced && (
          <div
            style={{
              padding: "0.875rem",
              backgroundColor: "var(--bg-dark)",
              border: "1px solid var(--border-color)",
              borderRadius: "0.375rem",
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "1rem",
              fontSize: "0.8rem",
            }}
          >
            <div className="input-group">
              <label className="input-label">Retrieval Mode</label>
              <select
                className="select-input"
                value={mode}
                onChange={(e) => setMode(e.target.value as any)}
              >
                <option value="auto">Auto (Hybrid/Keyword with Code Reranker)</option>
                <option value="keyword">Keyword (FTS5 BM25 + Code Reranker)</option>
                <option value="hybrid">Hybrid (RRF + Code Reranker)</option>
                <option value="semantic">Semantic (Cosine Vector + Code Reranker)</option>
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">Max Evidence Top-K ({topK})</label>
              <input
                type="range"
                min="1"
                max="20"
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value, 10))}
              />
            </div>
          </div>
        )}
      </form>
    </div>
  );
};
