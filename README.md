# RepoPilot

**AI Software Engineering Intelligence Platform**

[![Status](https://img.shields.io/badge/Status-Phase%200%20--%20Foundation-blue)]()
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
└── docs/
    ├── ARCHITECTURE.md        # System architecture and design
    ├── ROADMAP.md             # Phased development plan
    └── DECISIONS.md           # Architecture Decision Records
```

> This structure will expand as development progresses through each phase.

## Current Status

**Phase 0 — Foundation** (In Progress)

- [x] Create project documentation
- [ ] Initialize Git repository
- [ ] Set up development environment
- [ ] Create project skeleton

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full development plan.

## Setup Instructions

> 🚧 Setup instructions will be added when the application code is created in later phases.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design, components, data flow, AI pipeline
- [Roadmap](docs/ROADMAP.md) — Phased development plan (Phases 0–9)
- [Decisions](docs/DECISIONS.md) — Why each technology was chosen (Architecture Decision Records)

## License

This project is licensed under the MIT License.

---

*RepoPilot is built as a learning project to demonstrate AI/ML engineering skills. All technical decisions are documented with honest reasoning and trade-offs.*
