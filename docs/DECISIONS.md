# RepoPilot — Architecture Decision Records

> **Document Status:** Living document. New decisions are appended as they are made.
>
> **Last Updated:** 2026-08-12 (Phase 0 — Foundation)

---

## What Are Architecture Decision Records?

An **Architecture Decision Record (ADR)** documents a significant technical decision: what was decided, why, what alternatives were considered, and what consequences follow.

**Why we keep ADRs:**
- In an interview, you can explain *why* you chose each technology — not just *what* you used
- They prevent revisiting already-decided questions
- They make trade-offs explicit and honest
- Future contributors (or future you) understand the reasoning

### ADR Format

Each decision follows this structure:

| Section | What It Contains |
|---------|-----------------|
| **Status** | Proposed / Accepted / Superseded |
| **Context** | What problem or need prompted this decision? |
| **Decision** | What did we decide? |
| **Reasoning** | Why this choice over the alternatives? |
| **Alternatives Considered** | What else did we evaluate? |
| **Consequences** | What follows from this decision — both good and bad? |

---

## ADR-001: Python + FastAPI for Backend

**Status:** Accepted

**Date:** 2026-08-12

### Context

RepoPilot's backend needs to:
- Serve a REST API to the frontend
- Integrate with ML/AI libraries (embeddings, LLM APIs)
- Parse code using Tree-sitter
- Handle file I/O for cloned repositories
- Be maintainable by a developer learning the stack

### Decision

Use **Python** as the backend language and **FastAPI** as the web framework.

### Reasoning

- **Python is the lingua franca of AI/ML.** Virtually all embedding models, LLM client libraries, and ML tools have first-class Python support. Using another language would mean fighting the ecosystem.
- **FastAPI provides async support** out of the box, which matters when making multiple LLM API calls or embedding requests.
- **FastAPI auto-generates API documentation** (Swagger UI at `/docs`), which is invaluable for development and portfolio presentation.
- **Type hints with Pydantic** give us request/response validation for free, catching bugs early.
- **Tree-sitter has official Python bindings** (`tree-sitter` and `tree-sitter-languages` packages).

### Alternatives Considered

| Alternative | Why Not |
|-------------|---------|
| **Flask** | No built-in async support, no automatic API docs, less modern |
| **Django** | Too heavyweight for an API service — we don't need its ORM, admin panel, or template engine |
| **Node.js / Express** | Would require JavaScript for backend, splitting the AI/ML work away from Python ecosystem |
| **Go / Rust** | Excellent performance but poor AI/ML library support, steeper learning curve |

### Consequences

- ✅ Seamless integration with all Python AI/ML libraries
- ✅ Auto-generated API docs for free
- ✅ Async support for I/O-bound operations
- ✅ Large community and extensive documentation
- ⚠️ Python is slower than Go/Rust for CPU-bound tasks (acceptable — our bottleneck is I/O and LLM API latency, not CPU)
- ⚠️ Need to manage Python virtual environments carefully

---

## ADR-002: React + TypeScript + Vite for Frontend

**Status:** Accepted

**Date:** 2026-08-12

### Context

RepoPilot needs a web frontend for:
- Submitting queries about repositories
- Displaying AI answers with citations
- Browsing repository structure and code
- Interactive UI elements (search, filtering, code highlighting)

### Decision

Use **React** with **TypeScript** and **Vite** as the build tool.

### Reasoning

- **React** is the most widely adopted frontend library. Knowing React is a strong signal on a resume.
- **TypeScript** catches bugs at compile time that JavaScript misses. When displaying structured data like citations, types prevent entire categories of runtime errors.
- **Vite** provides near-instant hot module replacement (HMR) during development — changes appear in the browser in milliseconds, not seconds.
- **Component-based architecture** lets us build reusable UI pieces (code viewer, citation card, search bar) that compose cleanly.

### Alternatives Considered

| Alternative | Why Not |
|-------------|---------|
| **Next.js** | Adds server-side rendering complexity we don't need — RepoPilot is an SPA talking to a FastAPI backend |
| **Vue.js** | Excellent framework but smaller job market presence than React |
| **Angular** | Steeper learning curve, more opinionated, heavier setup |
| **Plain HTML/CSS/JS** | No component reusability, harder to maintain as the UI grows |
| **Svelte** | Promising but smaller ecosystem and fewer learning resources |

### Consequences

- ✅ Strong resume signal — React + TypeScript is the most requested frontend stack
- ✅ Type safety prevents many UI bugs
- ✅ Fast development iteration with Vite
- ✅ Huge ecosystem of libraries (code highlighting, markdown rendering, etc.)
- ⚠️ React has a learning curve for beginners (acceptable — it's worth learning)
- ⚠️ Additional build step compared to plain HTML/JS

---

## ADR-003: SQLite First, PostgreSQL + pgvector Later

**Status:** Accepted

**Date:** 2026-08-12

### Context

RepoPilot needs persistent storage for:
- Repository metadata
- Parsed symbols (functions, classes, imports)
- Code chunks and keyword indices
- Vector embeddings for semantic search

The system should start simple but have a clear path to a production-grade database.

### Decision

Use **SQLite** for initial development (Phases 1–4). Migrate to **PostgreSQL + pgvector** when needed (Phase 9 or when multi-user support is added).

### Reasoning

- **SQLite requires zero setup** — no database server to install or configure. The database is a single file.
- **Python includes SQLite support** in the standard library (`sqlite3` module).
- **For single-user development**, SQLite performance is more than sufficient.
- **PostgreSQL + pgvector** provides native vector similarity search and robust concurrent access, but it adds operational complexity that would slow down early development.
- **Using a database abstraction layer** (e.g., SQLAlchemy or a custom repository pattern) makes the migration path straightforward.

### Alternatives Considered

| Alternative | Why Not |
|-------------|---------|
| **PostgreSQL from day one** | Requires installing and running a database server, adding unnecessary complexity during early development |
| **MongoDB** | Document database doesn't align well with the relational nature of our data (symbols, relationships, files) |
| **In-memory only** | Data lost on restart — unacceptable even for development |
| **ChromaDB / Pinecone / Weaviate** | Specialized vector databases that solve only the embedding storage problem, not the full data model |

### Consequences

- ✅ Zero-setup development — clone the repo and start coding
- ✅ Single-file database — easy to inspect, backup, delete, and restart
- ✅ No external service dependencies during early development
- ⚠️ SQLite has limited concurrent write support (fine for single-user, problematic for multi-user)
- ⚠️ SQLite does not have native vector search (we need a workaround or library for Phases 3–4)
- ⚠️ Migration effort required when moving to PostgreSQL (mitigated by using a database abstraction layer)

---

## ADR-004: Tree-sitter for Code Parsing

**Status:** Accepted

**Date:** 2026-08-12

### Context

RepoPilot needs to parse source code to extract:
- Function and class definitions
- Import statements
- Symbol relationships (calls, references)
- Line ranges and documentation

The parser must support multiple programming languages and produce structured output, not just raw text.

### Decision

Use **Tree-sitter** for parsing source code into Abstract Syntax Trees (ASTs).

### Reasoning

- **Tree-sitter is language-agnostic.** A single parsing framework supports Python, JavaScript, TypeScript, Go, Rust, Java, C, and 100+ other languages via grammar packages.
- **It produces concrete syntax trees** — every token in the source code is represented, with exact line/column positions.
- **It is battle-tested.** Tree-sitter powers syntax highlighting and code intelligence in GitHub, Neovim, Helix, Zed, and other major tools.
- **It is fast.** Tree-sitter parsers are written in C and can parse large files in milliseconds.
- **Python bindings** are available (`tree-sitter` package) with a straightforward API.

### Alternatives Considered

| Alternative | Why Not |
|-------------|---------|
| **Python `ast` module** | Only parses Python — we need multi-language support |
| **Regular expressions** | Fragile, can't handle nested structures, language-specific |
| **Language Server Protocol (LSP)** | Heavy — requires running a separate language server per language |
| **srcML** | Less widely adopted, fewer language grammars available |
| **Custom parsers** | Enormous effort to build and maintain for each language |

### Consequences

- ✅ One parsing framework for all supported languages
- ✅ Battle-tested by major tools (GitHub, Neovim, Zed)
- ✅ Exact line/column positions for every symbol
- ✅ Fast enough to parse large repositories
- ⚠️ Tree-sitter grammars vary in quality across languages (popular languages are well-supported)
- ⚠️ Extracting high-level semantic information (e.g., "this function handles authentication") requires additional logic on top of the AST

---

## ADR-005: Cloud LLM APIs with Replaceable Provider

**Status:** Accepted

**Date:** 2026-08-12

### Context

RepoPilot uses large language models (LLMs) to:
- Answer questions about code
- Explain architecture and data flows
- Investigate bugs and review code
- Generate implementation plans

We need to choose between running LLMs locally or using cloud APIs, and we need to decide whether to commit to one provider or support multiple.

### Decision

Use **cloud LLM APIs** (OpenAI, Anthropic Claude, Google Gemini) with a **replaceable provider interface** so the model can be swapped without changing application code.

### Reasoning

- **No GPU required.** Cloud APIs work from any machine — no expensive hardware needed for development.
- **Latest models available immediately.** When a new model is released, we just update the API call.
- **Provider independence** protects against price changes, API deprecation, or quality regression from any single provider.
- **The provider interface** (`generate(prompt, context) → response`) is simple to implement for each provider and makes A/B testing between models trivial.

### Alternatives Considered

| Alternative | Why Not |
|-------------|---------|
| **Local LLM only (Ollama, llama.cpp)** | Requires a powerful GPU, slower inference, smaller model sizes |
| **Single provider (e.g., OpenAI only)** | Vendor lock-in, can't compare models, risk if the API changes |
| **Fine-tuned model** | Enormous effort, requires training data we don't have yet, premature optimization |

### Consequences

- ✅ Works on any machine with internet access
- ✅ Access to the best available models immediately
- ✅ Easy to compare models (switch one config value)
- ✅ No GPU hardware cost
- ⚠️ Requires an API key and internet connection
- ⚠️ API calls cost money (mitigated by using small context windows and caching during development)
- ⚠️ Latency depends on the API provider (typically 1–5 seconds per call)

---

## ADR-006: Hybrid Retrieval (Keyword + Semantic + Reranking)

**Status:** Accepted

**Date:** 2026-08-12

### Context

When a user asks a question about a repository, we need to find the most relevant code chunks to include in the LLM prompt. The quality of this retrieval step determines the quality of the final answer.

### Decision

Use **hybrid retrieval** combining:
1. **Keyword search** (BM25 or full-text search) for exact name matching
2. **Semantic search** (vector similarity) for conceptual matching
3. **Reranking** (cross-encoder, optional) for improved precision

### Reasoning

- **Keyword search alone fails** when the user describes functionality without using exact code names (e.g., "the function that validates user passwords" won't match `check_credentials`).
- **Semantic search alone fails** when the user asks for exact names, error messages, or specific strings that embedding models may not preserve precisely.
- **Hybrid retrieval combines strengths:** keyword search catches exact matches while semantic search catches conceptual matches.
- **Research consistently shows** hybrid retrieval outperforms either method alone across information retrieval benchmarks.
- **Reranking** uses a cross-encoder model to re-score the top-N combined results, improving precision without running the expensive model on all chunks.

### Alternatives Considered

| Alternative | Why Not |
|-------------|---------|
| **Keyword search only** | Misses conceptually related code when exact terms don't match |
| **Semantic search only** | Can miss exact name matches and specific strings |
| **LLM-based retrieval** | Too slow and expensive to use the LLM just for finding relevant code |

### Consequences

- ✅ Significantly better retrieval quality than either method alone
- ✅ Configurable weights let us tune the balance per use case
- ✅ Reranking improves precision at low cost (only re-scores top-N)
- ⚠️ Two search indices to maintain (keyword + vector)
- ⚠️ Embedding generation adds processing time during ingestion
- ⚠️ Reranking adds a small amount of latency per query

---

## Decision Log

| ADR | Decision | Status |
|-----|----------|--------|
| 001 | Python + FastAPI for backend | Accepted |
| 002 | React + TypeScript + Vite for frontend | Accepted |
| 003 | SQLite first, PostgreSQL + pgvector later | Accepted |
| 004 | Tree-sitter for code parsing | Accepted |
| 005 | Cloud LLM APIs with replaceable provider | Accepted |
| 006 | Hybrid retrieval (keyword + semantic + reranking) | Accepted |

---

*New decisions will be added as ADR-007, ADR-008, etc. as the project progresses.*
