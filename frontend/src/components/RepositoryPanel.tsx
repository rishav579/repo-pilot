import React, { useState } from "react";
import { FolderGit2, Plus, Play, RefreshCw, Database, CheckCircle2, AlertCircle, Clock } from "lucide-react";
import type { IndexingSummary, RepositoryRecord } from "../api/types";

interface RepositoryPanelProps {
  repositories: RepositoryRecord[];
  activeRepository: RepositoryRecord | null;
  onSelectRepository: (repo: RepositoryRecord) => void;
  onRegisterRepository: (path: string) => Promise<void>;
  onTriggerIndexing: (repoId: string, enableSemantic?: boolean) => Promise<IndexingSummary | void>;
  isLoading: boolean;
  error: string | null;
}

export const RepositoryPanel: React.FC<RepositoryPanelProps> = ({
  repositories,
  activeRepository,
  onSelectRepository,
  onRegisterRepository,
  onTriggerIndexing,
  isLoading,
  error,
}) => {
  const [repoPathInput, setRepoPathInput] = useState<string>("");
  const [enableSemantic, setEnableSemantic] = useState<boolean>(false);
  const [isRegistering, setIsRegistering] = useState<boolean>(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoPathInput.trim()) return;
    setIsRegistering(true);
    try {
      await onRegisterRepository(repoPathInput.trim());
      setRepoPathInput("");
    } finally {
      setIsRegistering(false);
    }
  };

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "ready":
        return (
          <span className="badge badge-ready" style={{ display: "inline-flex", alignItems: "center", gap: "0.2rem" }}>
            <CheckCircle2 size={10} /> Ready
          </span>
        );
      case "indexing":
        return (
          <span className="badge badge-indexing" style={{ display: "inline-flex", alignItems: "center", gap: "0.2rem" }}>
            <Clock size={10} className="animate-spin" /> Indexing
          </span>
        );
      case "failed":
        return (
          <span className="badge badge-failed" style={{ display: "inline-flex", alignItems: "center", gap: "0.2rem" }}>
            <AlertCircle size={10} /> Failed
          </span>
        );
      default:
        return <span className="badge badge-registered">Registered</span>;
    }
  };

  return (
    <aside className="sidebar-panel">
      <div className="panel-header">
        <FolderGit2 size={16} /> Repository Ingestion
      </div>

      {/* Register Repository Form */}
      <form onSubmit={handleRegister} className="input-group">
        <label className="input-label" htmlFor="repo-path">
          Local Repository Root Path
        </label>
        <input
          id="repo-path"
          type="text"
          className="text-input mono-input"
          placeholder="e.g. C:/Projects/repo-pilot"
          value={repoPathInput}
          onChange={(e) => setRepoPathInput(e.target.value)}
          disabled={isLoading || isRegistering}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={isLoading || isRegistering || !repoPathInput.trim()}
          style={{ width: "100%", marginTop: "0.25rem" }}
        >
          <Plus size={16} /> Register Repository
        </button>
      </form>

      {error && (
        <div
          style={{
            padding: "0.75rem",
            backgroundColor: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.2)",
            borderRadius: "0.375rem",
            color: "#f87171",
            fontSize: "0.8rem",
          }}
        >
          {error}
        </div>
      )}

      {/* Registered Repositories List */}
      <div className="input-group" style={{ marginTop: "0.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="input-label">Registered Repositories ({repositories.length})</span>
        </div>

        {repositories.length === 0 ? (
          <div
            style={{
              padding: "1.5rem 1rem",
              textAlign: "center",
              border: "1px dashed var(--border-color)",
              borderRadius: "0.375rem",
              fontSize: "0.8rem",
              color: "var(--text-muted)",
            }}
          >
            No repositories registered yet. Add a local path above to begin indexing.
          </div>
        ) : (
          <div className="repo-list">
            {repositories.map((repo) => {
              const isActive = activeRepository?.repository_id === repo.repository_id;
              return (
                <div
                  key={repo.repository_id}
                  className={`repo-card ${isActive ? "active" : ""}`}
                  onClick={() => onSelectRepository(repo)}
                >
                  <div className="repo-card-top">
                    <span className="repo-name">{repo.display_name}</span>
                    {renderStatusBadge(repo.status)}
                  </div>
                  <div className="repo-path">{repo.canonical_path}</div>

                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      marginTop: "0.25rem",
                    }}
                  >
                    <span>
                      <Database size={11} style={{ display: "inline", marginRight: "3px" }} />
                      {repo.indexed_file_count} files / {repo.indexed_chunk_count} chunks
                    </span>
                    <span>{repo.repository_id}</span>
                  </div>

                  {isActive && (
                    <div style={{ marginTop: "0.5rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                      <label
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.375rem",
                          cursor: "pointer",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={enableSemantic}
                          onChange={(e) => setEnableSemantic(e.target.checked)}
                        />
                        Enable Vector Embeddings
                      </label>
                      <button
                        className="btn btn-secondary"
                        style={{ width: "100%", fontSize: "0.8rem", padding: "0.4rem 0.6rem" }}
                        disabled={isLoading || repo.status === "indexing"}
                        onClick={(e) => {
                          e.stopPropagation();
                          onTriggerIndexing(repo.repository_id, enableSemantic);
                        }}
                      >
                        {repo.status === "indexing" ? (
                          <>
                            <RefreshCw size={14} className="animate-spin" /> Indexing Code...
                          </>
                        ) : (
                          <>
                            <Play size={14} /> Trigger Full Indexing
                          </>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
};
