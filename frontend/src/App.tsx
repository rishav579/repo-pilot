import { useState, useEffect, useCallback } from "react";
import { Header } from "./components/Header";
import { RepositoryPanel } from "./components/RepositoryPanel";
import { QueryPanel } from "./components/QueryPanel";
import { AnswerPanel } from "./components/AnswerPanel";
import { EvidencePanel } from "./components/EvidencePanel";
import { EmptyState } from "./components/EmptyState";
import { api, ApiError } from "./api/client";
import type {
  IndexingSummary,
  RAGRequest,
  RAGResponse,
  RepositoryRecord,
} from "./api/types";

export function App() {
  const [isBackendOnline, setIsBackendOnline] = useState<boolean>(false);
  const [repositories, setRepositories] = useState<RepositoryRecord[]>([]);
  const [activeRepository, setActiveRepository] = useState<RepositoryRecord | null>(null);

  const [ragResponse, setRagResponse] = useState<RAGResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Poll backend health & fetch registered repositories
  const checkHealthAndFetchRepos = useCallback(async () => {
    try {
      await api.getHealth();
      setIsBackendOnline(true);

      const list = await api.listRepositories();
      setRepositories(list);

      // Auto-select first repository or keep current selection updated
      if (list.length > 0) {
        setActiveRepository((prev) => {
          if (!prev) return list[0];
          const updated = list.find((r) => r.repository_id === prev.repository_id);
          return updated || list[0];
        });
      } else {
        setActiveRepository(null);
      }
    } catch {
      setIsBackendOnline(false);
    }
  }, []);

  useEffect(() => {
    checkHealthAndFetchRepos();
    const interval = setInterval(checkHealthAndFetchRepos, 5000);
    return () => clearInterval(interval);
  }, [checkHealthAndFetchRepos]);

  // Handle repository registration
  const handleRegisterRepository = async (path: string) => {
    setError(null);
    setIsLoading(true);
    try {
      const record = await api.registerRepository(path);
      await checkHealthAndFetchRepos();
      setActiveRepository(record);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Registration failed: ${err.message}`);
      } else {
        setError(`Registration error: ${String(err)}`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Handle trigger indexing
  const handleTriggerIndexing = async (repoId: string, enableSemantic?: boolean): Promise<IndexingSummary | void> => {
    setError(null);
    setIsLoading(true);
    try {
      const summary = await api.triggerIndexing(repoId, enableSemantic);
      await checkHealthAndFetchRepos();
      return summary;
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Indexing failed: ${err.message}`);
      } else {
        setError(`Indexing error: ${String(err)}`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Handle repository deletion
  const handleDeleteRepository = async (repoId: string) => {
    setError(null);
    setIsLoading(true);
    try {
      await api.deleteRepository(repoId);
      if (activeRepository?.repository_id === repoId) {
        setActiveRepository(null);
        setRagResponse(null);
      }
      await checkHealthAndFetchRepos();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Delete failed: ${err.message}`);
      } else {
        setError(`Delete error: ${String(err)}`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Handle natural language query submission
  const handleQuerySubmit = async (req: RAGRequest) => {
    setError(null);
    setIsLoading(true);
    try {
      const resp = await api.queryRepository(req);
      setRagResponse(resp);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Query failed: ${err.message}`);
      } else {
        setError(`Query error: ${String(err)}`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      <Header isBackendOnline={isBackendOnline} />

      <main className="main-layout">
        {/* Left Sidebar: Repository List & Lifecycle Management */}
        <RepositoryPanel
          repositories={repositories}
          activeRepository={activeRepository}
          onSelectRepository={setActiveRepository}
          onRegisterRepository={handleRegisterRepository}
          onTriggerIndexing={handleTriggerIndexing}
          onDeleteRepository={handleDeleteRepository}
          isLoading={isLoading}
          error={error}
        />

        {/* Right Main Content Area */}
        <section className="workspace-panel">
          {!isBackendOnline ? (
            <EmptyState type="no_backend" />
          ) : !activeRepository ? (
            <EmptyState type="no_repo" />
          ) : activeRepository.status === "indexing" ? (
            <EmptyState type="indexing" />
          ) : (
            <div className="results-container">
              {/* Query Panel */}
              <QueryPanel
                activeRepository={activeRepository}
                onQuerySubmit={handleQuerySubmit}
                isLoading={isLoading}
              />

              {/* Answer & Evidence Panels */}
              {ragResponse ? (
                <>
                  <AnswerPanel response={ragResponse} />
                  <EvidencePanel citations={ragResponse.citations} />
                </>
              ) : (
                <EmptyState type="no_query" />
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
