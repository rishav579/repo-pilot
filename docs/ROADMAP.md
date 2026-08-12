# RepoPilot — Development Roadmap

> **Document Status:** Living document. Updated as phases are completed.
>
> **Last Updated:** 2026-08-12 (Phase 6 — Production Repository Ingestion & End-to-End Q&A Workflow)

---

## Overview

RepoPilot is developed in **10 phases**, each building on the previous one. Every phase produces working, testable functionality — we never build something we cannot verify.

### Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Complete |
| 🔧 | In Progress |
| ⬚ | Not Started |

---

## Phase 0 — Foundation ✅

**Objective:** Set up the project structure, documentation, development environment, and tooling before writing any application code.

- [x] Create project documentation (README, Architecture, Roadmap, Decisions)
- [x] Initialize Git repository
- [x] Create `.gitignore` for Python, Node.js, environment files, IDE configs
- [x] Set up Python backend project structure (`backend/`)
- [x] Verify the project skeleton runs (backend health endpoint works)

---

## Phase 1 — Repository Ingestion Foundation ✅

**Objective:** Scan local repositories, catalog source files, extract metadata, and enforce exclusion rules.

- [x] File discovery: walks local repository and lists all files
- [x] File filtering: skip binary files, vendor directories, lock files
- [x] Language detection: identify programming language per file
- [x] Configurable exclusion rules (`config.py`)
- [x] API endpoint: `POST /repositories/scan` returns scan summary
- [x] Unit tests for scanner service (27 tests)

---

## Phase 2 — Code Parsing Foundation ✅

**Objective:** Parse source files using Tree-sitter to extract AST symbols (functions, classes, methods, interfaces, imports, line numbers, and signatures).

- [x] Tree-sitter integration: parse Python, JavaScript, and TypeScript
- [x] Symbol extraction: functions, classes, methods, interfaces with names, line ranges, docstrings
- [x] Import extraction: module names and import statements
- [x] Line number accuracy: 1-indexed start and end line ranges
- [x] API endpoint: `POST /repositories/parse` returns extracted symbols
- [x] Unit tests for parser service (10 parser tests, 37 total suite tests)

---

## Phase 3 — Code Retrieval & Hybrid Search ✅

**Objective:** Implement hybrid code retrieval combining keyword search (FTS5 + BM25) and semantic search (embeddings + cosine similarity) with RRF fusion.

- [x] Keyword search: FTS5 BM25 keyword matching
- [x] Chunking strategy: chunk by AST symbol (functions, classes, methods) & sliding window
- [x] Embedding abstraction: `BaseEmbeddingProvider` supporting Mock and OpenAI-compatible APIs
- [x] Vector storage & caching: SQLite vector table & `sha256(text + model)` embedding cache
- [x] Semantic search: cosine similarity vector search over indexed code chunks
- [x] Hybrid fusion: Reciprocal Rank Fusion (RRF) combining keyword + semantic results
- [x] API endpoint: `POST /repositories/search/keyword` with `mode="auto"|"keyword"|"semantic"|"hybrid"`
- [x] Unit test suite: 64 unit & integration tests covering retrieval quality, normalization, deduplication, and RRF fusion

---

## Phase 4 — Repository Q&A / RAG Engine ✅

**Objective:** Accept natural language questions about a repository and return grounded AI-generated answers with validated citations using the RAG pipeline.

- [x] RAG domain models: `Question`, `RetrievedEvidence`, `ContextBlock`, `Citation`, `RAGRequest`, `RAGResponse`
- [x] Evidence selection: filter minimum relevance threshold & limit evidence count
- [x] Context assembly & budgeting: format 1-indexed source blocks with character budget truncation
- [x] LLM abstraction: `BaseLLMProvider` supporting Mock and OpenAI-compatible Chat Completions
- [x] Grounded prompt builder: XML isolation for untrusted repository code to prevent prompt injection
- [x] Citation validation: extract and verify `[1]`, `[2]` bracketed citations against supplied evidence
- [x] Zero-hallucination sentinel: return `INSUFFICIENT_EVIDENCE` when no evidence exists or LLM cannot answer from code
- [x] API endpoint: `POST /repositories/query` for grounded Q&A
- [x] Offline Evaluation Framework (`eval_runner.py`): 87.5% Recall@K, 0.6458 MRR, 100% Citation Validity, 100% Insufficient Evidence Precision

---

## Phase 5 — Production Repository Ingestion & Lifecycle ✅

**Objective:** Turn real local repositories into registered, indexed, isolated, queryable knowledge bases with lifecycle state management and incremental indexing.

- [x] Repository domain model: `RepositoryRecord` with `RepositoryStatus` enum (`REGISTERED`, `INDEXING`, `READY`, `FAILED`, `STALE`)
- [x] Path validation & canonicalization: prevent duplicate registrations and path traversal attacks
- [x] Incremental indexing engine: SHA-256 content hashing skips unchanged files, updates changed files, purges deleted files
- [x] Repository scope isolation: explicit `repository_id` filtering in FTS5 and vector tables prevents cross-repository chunk leaks
- [x] Readiness validation checks: verify `RepositoryStatus` before executing Q&A queries
- [x] Management API endpoints: `POST /repositories`, `GET /repositories`, `GET /repositories/{id}`, `POST /repositories/{id}/index`
- [x] Developer CLI module (`app.cli`): command-line interface (`register`, `index`, `status`, `query`)
- [x] End-to-End test suite: 84 unit & integration tests covering registration, lifecycle transitions, incremental indexing, repository isolation, and management API

---

## Phase 6 — Code Intelligence & Advanced Analysis ⬚

**Objective:** Advanced code understanding features — architecture explanation, bug investigation, code review, and implementation planning.

---

## Summary Progress Matrix

| Phase | Name | Status |
|-------|------|--------|
| 0 | Foundation | ✅ Complete |
| 1 | Repository Ingestion Foundation | ✅ Complete |
| 2 | Code Parsing Foundation | ✅ Complete |
| 3 | Retrieval & Hybrid Search | ✅ Complete |
| 4 | Repository Q&A / RAG Engine | ✅ Complete |
| 5 | Production Ingestion & Lifecycle | ✅ Complete |
| 6 | Code Intelligence & Advanced Analysis | ⬚ Not Started |
| 7 | Controlled Agents & Tools | ⬚ Not Started |
| 8 | Deployment & Polish | ⬚ Not Started |
