# RepoPilot

**AI Software Engineering Intelligence Platform & Grounded Repository Q&A Engine**

[![Status](https://img.shields.io/badge/Status-Phase%208%20--%20Full%20Product%20Integration-success)]()
[![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.14-blue)]()
[![Frontend](https://img.shields.io/badge/Frontend-React%2019%20%7C%20TypeScript%20%7C%20Vite-indigo)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

---

> **Disclaimer:** RepoPilot is an original educational and job-portfolio project built from scratch for learning and engineering demonstration purposes. It is **not** a production system used by any company, organization, or enterprise. No claims of real-world enterprise deployment are made. All architecture and engineering decisions are documented transparently with empirical evaluation metrics.

---

## What is RepoPilot?

RepoPilot is an AI-powered platform that helps developers understand large, unfamiliar software repositories.

**The Problem:** Onboarding into a large codebase requires hours of reading files manually to understand architecture, trace execution paths, and locate function definitions.

**The Solution:** RepoPilot combines local AST code parsing (Tree-sitter), hybrid search (FTS5 BM25 + Vector Embeddings + RRF Fusion), deterministic **Code-Aware Reranking**, and an offline-evaluable **Grounded RAG Pipeline** to deliver precise answers backed by line-numbered file citations.

---

## Major Features

- **Repository Ingestion & Lifecycle Management** — Register and monitor local repository status (`REGISTERED`, `INDEXING`, `READY`, `FAILED`).
- **AST Parsing & Chunking** — Extract functions, classes, methods, and relationships using AST structure.
- **Hybrid Code Retrieval** — Reciprocal Rank Fusion (RRF) combining SQLite FTS5 BM25 keyword retrieval and cosine similarity embeddings.
- **Code-Aware Reranker** — Deterministic re-scoring layer utilizing exact symbol names, filenames, route patterns (`/health`), signatures, and docstrings.
- **Grounded Repository Q&A (RAG)** — Grounded natural language answers with 100% citation validity and safe refusal when evidence is insufficient (`INSUFFICIENT_EVIDENCE`).
- **Developer UI** — Sleek, responsive React 19 + TypeScript + Vite dashboard with live API connection status, repository management, query controls, answer metrics, and citation cards.
- **Empirical Offline Evaluation** — Reproducible benchmark evaluation suite tracking Recall@K, MRR, Grounded Answer Rate, and Citation Validity.

---

## Technical Architecture & Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Frontend** | React 19 + TypeScript + Vite | Type safety, Vite dev server, crisp developer-tool UI |
| **Backend** | Python 3.14 + FastAPI | High performance async endpoints, automatic OpenAPI docs |
| **Code Parsing** | Tree-sitter + AST Parsing | Language-agnostic structural parsing for functions and classes |
| **Search & Storage** | SQLite FTS5 + SQLite Vector | Zero-dependency, offline-capable hybrid search engine |
| **Retrieval Reranking** | Custom Deterministic Code Reranker | High-precision re-scoring without external ML latency |
| **AI / RAG Pipeline** | Pluggable LLM Provider (Mock + OpenAI) | Offline-testable, grounded prompt assembly with citation verification |

---

## Offline Evaluation Metrics (Benchmark Suite)

Evaluated against 10 curated repository test cases:

- **Retrieval Recall@K:** `100.0%`
- **Retrieval MRR:** `1.0000` (Perfect Rank 1 relevant chunk retrieval)
- **Grounded Answer Rate:** `100.0%`
- **Citation Validity Rate:** `100.0%`
- **Insufficient Evidence Precision:** `100.0%`

---

## Local Setup & Quickstart

### Prerequisites

- **Python 3.10+** (`python --version`)
- **Node.js 18+** (`node --version`)
- **Git** (`git --version`)

---

### 1. Clone the Repository

```bash
git clone https://github.com/rishav579/repo-pilot.git
cd repo-pilot
```

---

### 2. Set Up & Start the Backend

```bash
# Create Python virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Install Python dependencies
pip install -r backend/requirements.txt

# Start FastAPI backend server
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend runs at `http://127.0.0.1:8000`:
- **Health Check:** `http://127.0.0.1:8000/health`
- **Interactive API Docs:** `http://127.0.0.1:8000/docs`

---

### 3. Set Up & Start the Frontend

In a new terminal window:

```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```

The frontend runs at `http://localhost:5173`.

---

## Demo Flow (Step-by-Step UI Workflow)

1. **Open RepoPilot Frontend** — Visit `http://localhost:5173` in your browser. Verify the green **API Engine Connected** badge.
2. **Register Repository** — Enter a local repository path (e.g. `C:/Users/wwwri/OneDrive/Documents/AI-PROJECTS/repo-pilot`) in the left panel and click **Register Repository**.
3. **Index Repository** — Select the repository card and click **Trigger Full Indexing**. Watch the status transition from `INDEXING` to `READY`.
4. **Ask a Question** — Type a natural language question (e.g. *"Where is scan_repository and validate_repository_path defined in scanner?"* or *"Where is SQLiteFTSIndex defined?"*) and click **Ask RepoPilot**.
5. **Inspect Grounded Answer & Evidence** — Review the generated answer, performance latency breakdown, and citation cards showing exact file paths, line ranges, and symbol names.

---

## Project Structure

```text
repo-pilot/
├── README.md                  # Project documentation
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI route controllers
│   │   ├── evaluation/        # Benchmark evaluation suite & runner
│   │   ├── services/
│   │   │   ├── indexing/      # FTS5 & Vector storage
│   │   │   ├── ingestion/     # Repository scanner
│   │   │   ├── parsing/       # Tree-sitter AST parser
│   │   │   ├── rag/           # Grounded RAG engine & prompt builder
│   │   │   ├── repository/    # Lifecycle service & database storage
│   │   │   └── retrieval/     # Keyword, hybrid RRF, and Code-Aware Reranker
│   │   └── main.py            # FastAPI application entry point
│   └── tests/                 # Unit & integration test suite (111 passed)
├── frontend/
│   ├── src/
│   │   ├── api/               # Typed TypeScript API client & models
│   │   ├── components/        # Header, RepositoryPanel, QueryPanel, AnswerPanel, EvidencePanel
│   │   ├── App.tsx            # Main workspace React component
│   │   └── index.css          # Dark theme developer-tool design system
│   └── package.json
└── docs/                      # Architecture ADRs and roadmap documentation
```

---

## Running Tests

### Backend Test Suite (Pytest)

```bash
cd backend
python -m pytest tests/ -v
```

### Retrieval Evaluation Benchmark

```bash
cd backend
python -m app.evaluation.eval_runner
```

### Frontend Build & Test Suite (Vitest)

```bash
cd frontend
npm run build
npm test
```

---

## License

This project is licensed under the MIT License.
