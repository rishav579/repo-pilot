import type {
  HealthResponse,
  IndexingSummary,
  RAGRequest,
  RAGResponse,
  RepositoryRecord,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      let errorDetail = `HTTP ${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        if (body.detail) {
          errorDetail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        }
      } catch {
        // Ignore json parse error if response body is non-json
      }
      throw new ApiError(errorDetail, response.status);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      `Network or server connection failure: ${error instanceof Error ? error.message : String(error)}`,
      0
    );
  }
}

export const api = {
  /** Check backend health endpoint */
  getHealth: (): Promise<HealthResponse> => request<HealthResponse>("/health"),

  /** Register a local repository directory */
  registerRepository: (path: string): Promise<RepositoryRecord> =>
    request<RepositoryRecord>("/repositories", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),

  /** List all registered repositories */
  listRepositories: (): Promise<RepositoryRecord[]> =>
    request<RepositoryRecord[]>("/repositories"),

  /** Get repository record by ID or path */
  getRepositoryStatus: (repositoryId: string): Promise<RepositoryRecord> =>
    request<RepositoryRecord>(`/repositories/${encodeURIComponent(repositoryId)}`),

  /** Trigger scanning, parsing, and indexing for a repository */
  triggerIndexing: (repositoryId: string, enableSemantic?: boolean): Promise<IndexingSummary> =>
    request<IndexingSummary>(`/repositories/${encodeURIComponent(repositoryId)}/index`, {
      method: "POST",
      body: JSON.stringify({ enable_semantic: enableSemantic }),
    }),

  /** Execute grounded repository Q&A query */
  queryRepository: (req: RAGRequest): Promise<RAGResponse> =>
    request<RAGResponse>("/repositories/query", {
      method: "POST",
      body: JSON.stringify(req),
    }),
};
