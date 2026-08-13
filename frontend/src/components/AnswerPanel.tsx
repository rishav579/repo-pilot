import React from "react";
import { CheckCircle, AlertTriangle, XCircle, Clock, Cpu, FileText } from "lucide-react";
import type { RAGResponse } from "../api/types";

interface AnswerPanelProps {
  response: RAGResponse | null;
}

export const AnswerPanel: React.FC<AnswerPanelProps> = ({ response }) => {
  if (!response) return null;

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "grounded":
        return (
          <span
            className="status-badge"
            style={{
              backgroundColor: "rgba(16, 185, 129, 0.15)",
              color: "#10b981",
              border: "1px solid rgba(16, 185, 129, 0.3)",
            }}
          >
            <CheckCircle size={14} /> Grounded Evidence Answer
          </span>
        );
      case "insufficient_evidence":
        return (
          <span
            className="status-badge"
            style={{
              backgroundColor: "rgba(245, 158, 11, 0.15)",
              color: "#f59e0b",
              border: "1px solid rgba(245, 158, 11, 0.3)",
            }}
          >
            <AlertTriangle size={14} /> Insufficient Evidence Fallback
          </span>
        );
      default:
        return (
          <span
            className="status-badge"
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              color: "#ef4444",
              border: "1px solid rgba(239, 68, 68, 0.3)",
            }}
          >
            <XCircle size={14} /> {status}
          </span>
        );
    }
  };

  return (
    <div className="answer-card">
      <div className="answer-header">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <FileText size={18} style={{ color: "var(--accent-primary)" }} />
          <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Grounded Answer</h3>
        </div>
        {renderStatusBadge(response.status)}
      </div>

      <div className="answer-text">{response.answer}</div>

      {/* RAG Engine Performance Metrics Bar */}
      <div
        style={{
          marginTop: "1rem",
          paddingTop: "0.75rem",
          borderTop: "1px solid var(--border-color)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "0.75rem",
        }}
      >
        <div className="metrics-bar">
          <span>
            <Clock size={12} style={{ display: "inline", marginRight: "3px" }} />
            Total: {response.performance_ms.total_ms}ms
          </span>
          <span>Retrieval: {response.performance_ms.retrieval_ms}ms</span>
          <span>LLM Gen: {response.performance_ms.llm_generation_ms}ms</span>
          <span>Candidates: {response.retrieved_candidate_count}</span>
          <span>Mode: {response.retrieval_mode}</span>
        </div>

        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          <Cpu size={12} style={{ display: "inline", marginRight: "3px" }} />
          {response.provider_name} ({response.model_name})
        </div>
      </div>
    </div>
  );
};
