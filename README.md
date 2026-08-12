# RepoPilot

**AI Software Engineering Intelligence Platform**

[![Status](https://img.shields.io/badge/Status-Phase%201%20--%20Backend%20Foundation-blue)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

---

> **Disclaimer:** RepoPilot is an original educational and job-portfolio project built from scratch for learning purposes. It is **not** a production system used by any company, organization, or enterprise. No claims of real-world production deployment are made. All architecture and engineering decisions are documented transparently, including trade-offs and limitations.

---

## What is RepoPilot?

RepoPilot is an AI-powered platform that helps developers understand large, unfamiliar software repositories.

**The core problem:** A developer receives a large codebase they have never seen before. They need to understand its architecture, trace code flows, locate relevant files and functions, investigate bugs, perform code reviews, and plan changes — all without spending days reading every file manually.

RepoPilot aims to solve this by combining code parsing, hybrid search (keyword + semantic), and LLM-powered analysis to provide intelligent, evidence-backed answers about any repository.

## Planned Capabilities

> ⚠️ These are planned features. Development is in progress — see the [Roadmap](docs/ROADMAP.md) for current status.

- **Repository Ingestion** — Clone and process Git repositories
- **Code Parsing** — Extract functions, classes, imports, and relationships using Tree-sitter
- **Hybrid Search** — Combine keyword search and semantic embeddings for accurate code retrieval
- **Repository Q&A** — Ask natural language questions about any codebase
- **Evidence & Citations** — Every answer includes file paths, function names, and line numbers
- **Architecture Explanation** — Understand how components connect and how data flows
- **Bug Investigation** — Trace potential bugs through the code
- **Code Review** — AI-assisted review highlighting potential issues
- **Implementation Planning** — Generate plans for code changes with relevant context
- **Retrieval Evaluation** — Measure search quality with real benchmarks (no invented metrics)
- **Hallucination Tracking** — Monitor and report when the AI is uncertain or incorrect

## Tech Stack (Planned)

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | React + TypeScript + Vite | Type safety, fast dev server, modern tooling |
| Backend | Python + FastAPI | Async support, automatic API docs, Python ML ecosystem |
| Code Parsing | Tree-sitter | Language-agnostic AST parsing, used by major editors |
| Database | SQLite → PostgreSQL + pgvector | Start lightweight, scale when needed |
| Search | Keyword + Semantic + Reranking | Hybrid retrieval for accuracy |
| AI/LLM | Cloud APIs (replaceable provider) | No local GPU required, swap providers easily |
| Infrastructure | Git, Docker (later), CI/CD (later) | Standard professional tooling |

## Project Structure

```
repo-pilot/
├── README.md                  # You are here
├── .gitignore                 # Files Git should ignore
├── backend/
│   ├── requirements.txt       # Python dependencies
│   └── app/
│       ├── __init__.py        # Makes app/ a Python package
│       └── main.py            # FastAPI application entry point
└── docs/
    ├── ARCHITECTURE.md        # System architecture and design
    ├── ROADMAP.md             # Phased development plan
    └── DECISIONS.md           # Architecture Decision Records
```

## Current Status

**Phase 0 — Foundation** ✅ Complete

- [x] Create project documentation
- [x] Initialize Git repository
- [x] Set up development environment
- [x] Create project skeleton

**Phase 1 — Backend Foundation** 🔧 In Progress

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full development plan.

## Setup Instructions

### Prerequisites

- **Python 3.10+** — check with `python --version`
- **Git** — check with `git --version`

### 1. Clone the Repository

```bash
git clone https://github.com/rishav579/repo-pilot.git
cd repo-pilot
```

### 2. Create a Python Virtual Environment

A virtual environment isolates this project's Python packages from your system Python.

```bash
python -m venv .venv
```

### 3. Activate the Virtual Environment

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

You should see `(.venv)` appear at the start of your terminal prompt.

### 4. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### 5. Run the Backend Server

```bash
cd backend
uvicorn app.main:app --reload
```

The `--reload` flag auto-restarts the server when you change code (development only).

### 6. Verify It Works

Open your browser and visit:

- **Health check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) — should return `{"status": "ok"}`
- **API docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) — interactive Swagger UI

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design, components, data flow, AI pipeline
- [Roadmap](docs/ROADMAP.md) — Phased development plan (Phases 0–9)
- [Decisions](docs/DECISIONS.md) — Why each technology was chosen (Architecture Decision Records)

## License

This project is licensed under the MIT License.

---

*RepoPilot is built as a learning project to demonstrate AI/ML engineering skills. All technical decisions are documented with honest reasoning and trade-offs.*
