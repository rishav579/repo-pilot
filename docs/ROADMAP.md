# RepoPilot — Development Roadmap

> **Document Status:** Living document. Updated as phases are completed.
>
> **Last Updated:** 2026-08-12 (Phase 3 — Code Parsing Foundation)

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

**Why this phase exists:** Professional projects start with planning. A clear structure, documented decisions, and proper tooling prevent wasted effort later. This phase also ensures the project is presentable on GitHub from day one.

### Deliverables

- [x] Create project documentation (README, Architecture, Roadmap, Decisions)
- [x] Initialize Git repository
- [x] Create `.gitignore` for Python, Node.js, environment files, IDE configs
- [x] Set up Python backend project structure (`backend/`)
- [ ] Set up React + TypeScript + Vite frontend project structure (`frontend/`) — deferred to a later phase
- [ ] Create `.env.example` with placeholder environment variables — deferred until needed
- [ ] Set up basic logging configuration — deferred to Phase 1
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

## Phase 3 — Retrieval ⬚

**Objective:** Implement hybrid code retrieval combining keyword search and semantic (embedding-based) search.

**Why this phase exists:** Finding the right code chunks to answer a question is the most critical step. Poor retrieval means the LLM gets irrelevant context and produces bad answers. Hybrid retrieval significantly outperforms either method alone.

### Deliverables

- [ ] Embedding generation: convert code chunks to vector embeddings
- [ ] Vector storage: store and query embeddings (SQLite initially)
- [ ] Semantic search: find code by meaning, not just keywords
- [ ] Hybrid merger: combine keyword + semantic results with configurable weights
- [ ] Reranker: optionally re-score results with a cross-encoder
- [ ] API endpoint: `POST /api/repos/{id}/search` with hybrid search
- [ ] Chunking strategy: chunk by function/class, not arbitrary line counts
- [ ] Tests for retrieval quality

---

## Phase 4 — Repository Q&A ⬚

**Objective:** Accept natural language questions about a repository and return AI-generated answers using the RAG pipeline.

**Why this phase exists:** This is the core user-facing feature. Everything built so far (ingestion, parsing, indexing, retrieval) feeds into this: the user asks a question, we retrieve relevant code, and the LLM generates an answer.

### Deliverables

- [ ] LLM provider interface: abstract class with `generate(prompt, context)` method
- [ ] First LLM integration: implement one cloud provider (OpenAI, Claude, or Gemini)
- [ ] Prompt builder: assemble system prompt + user query + retrieved context
- [ ] Context window management: stay within the LLM's token limit
- [ ] API endpoint: `POST /api/repos/{id}/query` accepts natural language questions
- [ ] Basic frontend: text input for questions, display for answers
- [ ] Conversation-style Q&A (single-turn to start, multi-turn later)
- [ ] Error handling: LLM API failures, rate limits, empty results
- [ ] Tests for prompt building and response parsing

---

## Phase 5 — Evidence & Citations ⬚

**Objective:** Every AI answer must include specific file paths, function names, and line numbers as evidence. Verify citations against actual code.

**Why this phase exists:** An AI answer without evidence is just a guess. Citations let the user verify the answer and build trust. Verification catches hallucinations — cases where the AI invents file names or functions that don't exist.

### Deliverables

- [ ] Citation format: define a standard citation schema (file, function, lines)
- [ ] Prompt engineering: instruct the LLM to cite specific files and functions
- [ ] Citation extractor: parse citations from LLM responses
- [ ] Citation verification: check that each cited file/function actually exists
- [ ] Frontend: display citations as clickable links to source code
- [ ] Frontend: highlight cited code sections
- [ ] Flag unverifiable citations with a warning
- [ ] Tests for citation extraction and verification

---

## Phase 6 — Code Intelligence ⬚

**Objective:** Advanced code understanding features — architecture explanation, bug investigation, code review, and implementation planning.

**Why this phase exists:** Q&A is the foundation, but developers need more specialized tools. This phase builds higher-level analysis capabilities on top of the RAG pipeline.

### Deliverables

- [ ] Architecture explanation: describe how components connect and how data flows
- [ ] Bug investigation: given a bug description, trace likely causes through the code
- [ ] Code review: analyze a file or function for potential issues (error handling, edge cases, performance)
- [ ] Implementation planning: given a feature request, identify relevant files and suggest a plan
- [ ] Specialized prompts for each analysis type
- [ ] Frontend: distinct UI modes for each capability
- [ ] Tests for each analysis type

---

## Phase 7 — Controlled Agents & Tools ⬚

**Objective:** Introduce AI agents that can use tools (search, read file, trace calls) to answer complex multi-step questions.

**Why this phase exists:** Single-shot RAG works for simple questions but fails for complex ones like "How does a user login request flow from the frontend to the database?" An agent can iteratively search, read files, and trace call chains to build a comprehensive answer.

### Deliverables

- [ ] Tool definitions: search, read_file, list_symbols, trace_calls
- [ ] Agent loop: LLM decides which tool to use, receives results, decides next step
- [ ] Execution limits: maximum steps, timeout, token budget
- [ ] Observation logging: record every tool call and result for transparency
- [ ] Safety: agents can only read, never modify code
- [ ] Frontend: show agent's reasoning steps to the user
- [ ] Tests for agent execution and safety limits

---

## Phase 8 — Evaluation ⬚

**Objective:** Build a real evaluation pipeline that measures retrieval quality, answer quality, and hallucination rates using actual benchmarks.

**Why this phase exists:** Without evaluation, we are guessing whether the system works well. Real metrics let us improve the system systematically and demonstrate engineering rigor. No fake numbers — only measured results.

### Deliverables

- [ ] Evaluation dataset: create ground-truth Q&A pairs for a known repository
- [ ] Retrieval metrics: Precision@k, Recall@k, MRR — measured on real data
- [ ] Answer metrics: citation accuracy, citation relevance, answer correctness
- [ ] Hallucination tracking: log and measure hallucination rate
- [ ] Evaluation scripts: automated pipeline to run evaluations
- [ ] Results reporting: generate evaluation reports with actual numbers
- [ ] Compare retrieval strategies: keyword-only vs. semantic-only vs. hybrid
- [ ] Document results honestly, including failure cases

---

## Phase 9 — Deployment & Polish ⬚

**Objective:** Containerize the application, add CI/CD, polish the frontend, and prepare the project for portfolio presentation.

**Why this phase exists:** A portfolio project needs to be runnable, testable, and presentable. This phase closes the gap between "works on my machine" and "anyone can clone and run this."

### Deliverables

- [ ] Dockerfile for backend
- [ ] Dockerfile for frontend
- [ ] Docker Compose for full-stack local development
- [ ] GitHub Actions: run tests on every push
- [ ] GitHub Actions: lint and type-check
- [ ] Environment variable documentation
- [ ] Polish frontend UI/UX
- [ ] Write comprehensive setup guide in README
- [ ] Create demo video or screenshots
- [ ] Final documentation review

---

## Summary

| Phase | Name | Status |
|-------|------|--------|
| 0 | Foundation | ✅ Complete |
| 1 | Repository Ingestion Foundation | ✅ Complete |
| 2 | Code Parsing Foundation | ✅ Complete |
| 3 | Retrieval | ⬚ Not Started |
| 4 | Repository Q&A | ⬚ Not Started |
| 5 | Evidence & Citations | ⬚ Not Started |
| 6 | Code Intelligence | ⬚ Not Started |
| 7 | Controlled Agents & Tools | ⬚ Not Started |
| 8 | Evaluation | ⬚ Not Started |
| 9 | Deployment & Polish | ⬚ Not Started |

---

*Each phase will be developed incrementally with explanation, testing, and verification before moving to the next.*
