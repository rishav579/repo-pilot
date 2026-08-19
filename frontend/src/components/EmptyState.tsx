import React from "react";
import { Terminal, AlertCircle, Clock, Database, Search } from "lucide-react";

interface EmptyStateProps {
  type: "no_backend" | "no_repo" | "indexing" | "no_query" | "insufficient_evidence";
  customMessage?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ type, customMessage }) => {
  switch (type) {
    case "no_backend":
      return (
        <div className="empty-state" style={{ borderColor: "rgba(239, 68, 68, 0.3)" }}>
          <AlertCircle size={36} className="empty-icon" style={{ color: "#ef4444" }} />
          <h4 style={{ color: "#f87171", fontSize: "1.1rem" }}>Backend Service Offline</h4>
          <p style={{ maxWidth: "480px", fontSize: "0.875rem" }}>
            {customMessage || "Unable to reach the RepoPilot backend. Please try again in a moment."}
          </p>
        </div>
      );

    case "no_repo":
      return (
        <div className="empty-state">
          <Database size={36} className="empty-icon" />
          <h4 style={{ fontSize: "1.1rem" }}>No Repository Selected</h4>
          <p style={{ maxWidth: "440px", fontSize: "0.875rem" }}>
            Register a local repository directory path in the left panel to begin scanning, parsing AST structure, and asking questions.
          </p>
        </div>
      );

    case "indexing":
      return (
        <div className="empty-state" style={{ borderColor: "rgba(245, 158, 11, 0.3)" }}>
          <Clock size={36} className="empty-icon animate-spin" style={{ color: "#f59e0b" }} />
          <h4 style={{ color: "#fbbf24", fontSize: "1.1rem" }}>Indexing Repository Codebase...</h4>
          <p style={{ maxWidth: "440px", fontSize: "0.875rem" }}>
            Scanning file inventory, extracting AST symbols with Tree-sitter, building FTS5 keyword index, and reranking pipeline.
          </p>
        </div>
      );

    case "insufficient_evidence":
      return (
        <div className="empty-state" style={{ borderColor: "rgba(245, 158, 11, 0.3)" }}>
          <Search size={36} className="empty-icon" style={{ color: "#f59e0b" }} />
          <h4 style={{ color: "#fbbf24", fontSize: "1.1rem" }}>Insufficient Evidence Found</h4>
          <p style={{ maxWidth: "480px", fontSize: "0.875rem" }}>
            The RAG pipeline did not find relevant code evidence in the repository to ground an answer for this question. RepoPilot safely refused to hallucinate.
          </p>
        </div>
      );

    default:
      return (
        <div className="empty-state">
          <Terminal size={36} className="empty-icon" />
          <h4 style={{ fontSize: "1.1rem" }}>Ready to Query Codebase</h4>
          <p style={{ maxWidth: "440px", fontSize: "0.875rem" }}>
            Type a natural language question above to query functions, endpoints, data flow, or architecture.
          </p>
        </div>
      );
  }
};
