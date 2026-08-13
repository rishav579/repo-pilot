import React from "react";
import { BookOpen, FileCode, CheckCircle2, AlertCircle } from "lucide-react";
import type { Citation } from "../api/types";

interface EvidencePanelProps {
  citations: Citation[];
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ citations }) => {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="evidence-section">
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <BookOpen size={18} style={{ color: "var(--accent-primary)" }} />
        <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>
          Retrieved Evidence & Grounded Citations ({citations.length})
        </h3>
      </div>

      <div className="evidence-grid">
        {citations.map((citation, idx) => (
          <div key={`${citation.relative_path}-${idx}`} className="evidence-card">
            <div className="evidence-card-header">
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span className="citation-num">[{citation.index_number}]</span>
                <span className="file-location">
                  {citation.relative_path}
                  {citation.start_line && citation.end_line
                    ? ` (L${citation.start_line}-L${citation.end_line})`
                    : ""}
                </span>
              </div>
              {citation.is_valid ? (
                <span
                  style={{ color: "#10b981", fontSize: "0.7rem", display: "inline-flex", alignItems: "center", gap: "0.2rem" }}
                  title="Citation verified against evidence block"
                >
                  <CheckCircle2 size={12} /> Valid
                </span>
              ) : (
                <span
                  style={{ color: "#ef4444", fontSize: "0.7rem", display: "inline-flex", alignItems: "center", gap: "0.2rem" }}
                  title="Unverified citation"
                >
                  <AlertCircle size={12} /> Unverified
                </span>
              )}
            </div>

            <div style={{ padding: "0.5rem 0.75rem", fontSize: "0.75rem", borderBottom: "1px solid var(--border-color)" }}>
              {citation.symbol_name ? (
                <span style={{ color: "var(--text-secondary)" }}>
                  <FileCode size={12} style={{ display: "inline", marginRight: "3px" }} />
                  Symbol: <strong>{citation.symbol_name}</strong>
                </span>
              ) : (
                <span style={{ color: "var(--text-muted)" }}>File Source Chunk</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
