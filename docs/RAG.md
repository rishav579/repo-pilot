# RepoPilot — Grounded Repository Q&A / RAG Engine

This document describes the design, architecture, and usage of the **Repository Q&A / RAG (Retrieval-Augmented Generation) Engine** in RepoPilot.

---

## 🏗️ RAG Pipeline Architecture

```text
User Question (POST /repositories/query)
                  ↓
   1. Question Validation & Normalization
                  ↓
   2. Repository Retrieval (Keyword / Semantic / Hybrid RRF)
                  ↓
   3. Evidence Selection (Min Score Filtering, Max Chunks Limit)
                  ↓
   4. Context Assembly & Budgeting (1-Indexed Source Blocks)
                  ↓
   5. Grounded Prompt Construction (Security Boundary Enforced)
                  ↓
   6. LLM Text Generation (Mock or OpenAI-compatible)
                  ↓
   7. Citation Extraction & Verification
                  ↓
   8. Structured Response (Grounded or Insufficient Evidence)
```

---

## 🛡️ Grounding & Security Guarantees

1. **Zero Hallucination Sentinel:** If no repository evidence meets the minimum relevance score, or if the LLM cannot answer strictly from evidence, the API returns `INSUFFICIENT_EVIDENCE`.
2. **Untrusted Evidence Isolation:** Source code snippets are wrapped in `<untrusted_retrieved_evidence>` tags with strict system rules. Prompt injection directives embedded inside source code comments or strings cannot hijack LLM system instructions.
3. **Validated Citations:** Every bracketed citation (e.g. `[1]`, `[2]`) in an LLM response is extracted and verified against the actual context blocks supplied. Unvalidated or hallucinated indices are filtered out.
4. **Offline Ready:** Operates 100% offline out-of-the-box using `MockLLMProvider` and `MockEmbeddingProvider`. No paid API keys or external services are required to test or run the engine.

---

## 📡 API Endpoint

### `POST /repositories/query`

#### Example Request

```json
{
  "repository_path": "c:/Users/wwwri/OneDrive/Documents/AI-PROJECTS/repo-pilot",
  "question": "Where is the health check endpoint defined?",
  "mode": "auto",
  "top_k": 5,
  "max_context_chars": 8000,
  "min_relevance_score": 0.01
}
```

#### Example Grounded Response

```json
{
  "question": "Where is the health check endpoint defined?",
  "answer": "Based on the provided codebase evidence in backend/app/main.py, the health check endpoint is defined in source block [1].\n\nReference citations: [1].",
  "status": "grounded",
  "citations": [
    {
      "index_number": 1,
      "relative_path": "backend/app/main.py",
      "chunk_id": "backend/app/main.py:L44-L56:health_check",
      "start_line": 44,
      "end_line": 56,
      "symbol_name": "health_check",
      "is_valid": true,
      "snippet_preview": "--- SOURCE BLOCK [1] ---\nFILE: backend/app/main.py\nCHUNK_ID: backend/app/main.py:L44-L56:health_check\n..."
    }
  ],
  "retrieval_mode": "auto",
  "evidence_count": 1,
  "context_truncated": false,
  "provider_name": "mock",
  "model_name": "mock-gpt-4"
}
```

---

## ⚙️ Configuration

Environment variables (read via `RetrievalConfig` and `RAGService`):

| Variable | Options | Default | Description |
|----------|---------|---------|-------------|
| `SEMANTIC_RETRIEVAL_ENABLED` | `"true"`, `"false"` | `"false"` | Enables semantic vector retrieval |
| `EMBEDDING_PROVIDER` | `"mock"`, `"openai"` | `"mock"` | Embedding provider type |
| `EMBEDDING_API_KEY` | string | `None` | Optional API key for external embedding provider |
| `LLM_PROVIDER` | `"mock"`, `"openai"` | `"mock"` | LLM provider type |
| `OPENAI_API_KEY` | string | `None` | Optional API key for external OpenAI-compatible LLM |

---

## 📊 Offline Evaluation & Production Hardening (Phase 5.1)

RepoPilot includes an offline RAG evaluation framework (`backend/app/evaluation/`) to measure retrieval quality, grounding precision, and latency without requiring network calls or paid APIs.

### Developer Evaluation Command

To run the offline evaluation suite locally:

```powershell
python -m app.evaluation.eval_runner
```

### Baseline Quality Metrics

| Metric | Target | Baseline Result | Description |
|--------|--------|-----------------|-------------|
| **Retrieval Recall@K** | $\ge 75\%$ | **100.0%** | Percentage of answerable questions where expected source files are retrieved |
| **Retrieval MRR** | $\ge 0.50$ | **0.6376** | Mean Reciprocal Rank of first relevant source file in candidate evidence |
| **Grounded Answer Rate** | $\ge 75\%$ | **87.5%** | Percentage of answerable questions producing grounded answers |
| **Citation Validity Rate** | $\ge 90\%$ | **100.0%** | Percentage of extracted citations mapped to valid context blocks |
| **Insufficient Evid Precision** | $\ge 90\%$ | **100.0%** | Percentage of unanswerable questions correctly returning `insufficient_evidence` |
| **Avg Latency** | $< 500\text{ ms}$ | **~113 ms** | Pipeline execution duration including retrieval and context assembly |

### Failure Analysis Cases Handled

- **Case A (No Results):** Returns structured `insufficient_evidence` response without hallucinating facts.
- **Case B (Low Score Evidence):** Filtered out by `min_relevance_score` threshold; returns `insufficient_evidence`.
- **Case C (LLM Provider Error):** Returns `status="error"` with structured error payload without crashing API.
- **Case D (Hallucinated Citations):** Extracted citation indices not matching context blocks are flagged (`is_valid=False`) and filtered.
- **Case E (Empty / Unusable LLM Text):** Detected and handled cleanly with `status="unusable_output"`.

