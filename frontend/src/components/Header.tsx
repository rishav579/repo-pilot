import React from "react";
import { Terminal, Activity } from "lucide-react";

interface HeaderProps {
  isBackendOnline: boolean;
}

export const Header: React.FC<HeaderProps> = ({ isBackendOnline }) => {
  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-icon">
          <Terminal size={22} />
        </div>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span className="brand-title">RepoPilot</span>
            <span
              style={{
                fontSize: "0.7rem",
                color: "#94a3b8",
                backgroundColor: "#1e293b",
                padding: "0.1rem 0.4rem",
                borderRadius: "0.25rem",
              }}
            >
              v0.1.0
            </span>
          </div>
          <p className="brand-subtitle">
            AI Software Engineering Intelligence Platform & Grounded Repository Q&A Engine
          </p>
        </div>
      </div>

      <div>
        <span className={`status-badge ${isBackendOnline ? "online" : "offline"}`}>
          <Activity size={12} />
          <span className="status-dot"></span>
          {isBackendOnline ? "API Engine Connected" : "Backend Offline"}
        </span>
      </div>
    </header>
  );
};
