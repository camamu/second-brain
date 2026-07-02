# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TFM (academic project): conversational RAG agent over an Obsidian vault. Three chunking strategies (`fixed`, `markdown`, `backlink`) are the research contribution, evaluated via Precision@K and MRR. UI is Chainlit. `AGENTS.md` is stale (describes an earlier scaffolding-only state) — prefer this file and `find src -name "*.py"` over it.

## Commands

```bash
source .venv/bin/activate                    # activate virtualenv
python scripts/test_ollama_chat.py           # verify Ollama connectivity
python scripts/test_groq.py                  # verify Groq connectivity
python scripts/ingest.py [--strategy fixed|markdown|backlink]  # ingest vault into ChromaDB
chainlit run app.py                          # start chat UI (app.py at repo root delegates to src/app)
pytest tests/unit/                           # unit tests (no I/O, no network)
pytest tests/integration/                    # integration tests (ChromaDB in-memory + real Ollama)
pytest tests/unit/test_models.py -v         # run a single test file
ruff check src/ tests/                       # lint
ruff format src/ tests/                      # format
mypy src                                     # type check (configurado en pyproject.toml)
scripts/format.sh                            # ruff format + check --fix over src/tests/scripts/evaluation
python scripts/check_architecture.py         # enforce hexagonal dependency rule (also runs in CI)
```

No Makefile exists. `pyproject.toml` exists with ruff and pytest configuration. CI workflows in `.github/workflows/`: `lint.yml`, `typecheck.yml`, `test-unit.yml`, `architecture-check.yml`, `build-docker.yml`, `create-release.yml`, `deploy-hf-spaces.yml`.

## Architecture

Hexagonal. The dependency rule is strict: inner layers never import from outer ones.

```
src/domain/          → entities (frozen dataclasses) + ABC ports — zero external deps
src/application/     → use cases (one class per file, one execute() method)
src/adapters/        → port implementations: chunkers, embedders, llm, loaders, vector_stores
src/agent/           → LangChain ReAct agent + tools (search_vault, create_note, edit_note)
src/app/             → Chainlit entrypoint (imported by app.py at repo root)
src/infrastructure/  → config loading (.env), dependency wiring
```

**Domain entities** (`src/domain/models.py`): `Note`, `Chunk`, `SearchResult`, `RetrievalQuery`, `EvaluationSample`, `EvaluationResult`, plus enums `ChunkStrategy` and `NoteType`. All are `@dataclass(frozen=True)`.

**Ports** (`src/domain/ports.py`): `NoteLoader`, `NoteWriter`, `BaseChunker`, `ChunkEmbedder`, `VectorStore`, `ConversationalLLM`, `IEvaluationRepo` + exceptions `ObsidianRagError`, `NoteNotFoundError`, `ChunkingError`, `EmbeddingError`, `VectorStoreError`, `VaultWriteError`, `ConfigError`.

**Implemented adapters**:
- `src/adapters/obsidian_loader.py` — `ObsidianLoader` (implements `NoteLoader` + `NoteWriter`)
- `src/adapters/chunkers/fixed_size.py` — `FixedSizeChunker` + shared `split_text()`
- `src/adapters/chunkers/markdown_header.py` — `MarkdownHeaderChunker`
- `src/adapters/chunkers/backlink_aware.py` — `BacklinkAwareChunker` (injects `NoteLoader`)
- `src/adapters/chunkers/base.py` — re-exports `BaseChunker` from domain
- `src/adapters/llm/ollama_adapter.py` — `OllamaEmbedderAdapter` + `OllamaLLMAdapter`
- `src/adapters/llm/groq_adapter.py` — `HuggingFaceEmbedderAdapter` + `GroqLLMAdapter`
- `src/adapters/llm/ollama_chat.py` — `OllamaChat`, legacy smoke-test helper used only by `scripts/test_ollama_chat.py`; not part of the production LLM path (that's `ollama_adapter.py`/`groq_adapter.py`)
- `src/adapters/vector_stores/chroma_store.py` — `ChromaVectorStore` (1 collection/strategy, cosine)
- `src/adapters/evaluation_repo.py` — `EvaluationRepo` (implements `IEvaluationRepo`)
- `src/infrastructure/config.py` — composition root / factory (reads `.env`, lazy imports)

**Agent** (`src/agent/`):
- `src/agent/agent.py` — `create_agent()` builds a LangChain `AgentExecutor` (ReAct, `handle_parsing_errors` set to a Spanish-language guidance string, `max_iterations=10`, default `early_stopping_method="force"` so the executor never raises on max-iterations or on repeated parsing failures — it returns gracefully instead)
- `src/agent/tools.py` — `create_search_tool`, `create_note_tool`, `create_edit_tool` wrapping `SearchNotes`/`ManageNotes`

**App** (`src/app/` + `app.py`):
- `app.py` (repo root) — `chainlit run` entrypoint, delegates via `from src.app import *`
- `src/app/__init__.py` — actual Chainlit handlers (`@cl.on_chat_start`, `@cl.on_message`), chunking-strategy picker, readonly mode via `is_readonly()`

## Key conventions

- Python 3.11+; full type hints on all public functions and `__init__` params
- Google-style docstrings on all classes and public methods
- Code in English; TFM-explanatory comments in Spanish
- 80-char line limit; `logging` not `print()`
- One adapter class per file; adapters receive injected config, never call `os.getenv()` directly
- Test naming: `test_<class>_<method>_<expected_result>`; pattern AAA (Arrange / Act / Assert)

## Environment variables

Copy `.env.example` to `.env` and fill in the values (source of truth — verify against it before trusting this list):

```env
USE_LOCAL=true              # true=Ollama, false=Groq+HuggingFace
VAULT_PATH=                 # absolute path to Obsidian vault
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2       # LLM model name in Ollama
OLLAMA_EMBED_MODEL=nomic-embed-text
GROQ_API_KEY=               # only when USE_LOCAL=false
GROQ_MODEL=llama-3.3-70b-versatile
HF_EMBED_MODEL=nomic-ai/nomic-embed-text-v1
READONLY_MODE=false         # true disables create_note/edit_note tools (recommended in prod)
CHROMA_PERSIST_DIR=data/chroma_db  # where ChromaDB stores its files
CHUNKER_STRATEGY=fixed      # fixed|markdown|backlink
CHUNK_SIZE=512
CHUNK_OVERLAP=50
LOG_LEVEL=INFO
```

## Current state

Verify what exists before referencing it:

```bash
find src -name "*.py" ! -name "__init__.py"
```

As of Fase 5/6 complete (agent + Chainlit UI), files with real content:
- `src/domain/models.py` — `Note`, `Chunk`, `SearchResult`, `RetrievalQuery`, `EvaluationSample`, `EvaluationResult`, `ChunkStrategy`, `NoteType`
- `src/domain/ports.py` — `NoteLoader`, `NoteWriter`, `BaseChunker`, `ChunkEmbedder`, `VectorStore`, `ConversationalLLM`, `IEvaluationRepo` + full exception hierarchy
- `src/adapters/obsidian_loader.py` — `ObsidianLoader`
- `src/adapters/chunkers/fixed_size.py` — `FixedSizeChunker`, `split_text()`
- `src/adapters/chunkers/markdown_header.py` — `MarkdownHeaderChunker`
- `src/adapters/chunkers/backlink_aware.py` — `BacklinkAwareChunker`
- `src/adapters/llm/ollama_adapter.py` — `OllamaEmbedderAdapter`, `OllamaLLMAdapter`
- `src/adapters/llm/groq_adapter.py` — `HuggingFaceEmbedderAdapter`, `GroqLLMAdapter`
- `src/adapters/vector_stores/chroma_store.py` — `ChromaVectorStore`
- `src/adapters/evaluation_repo.py` — `EvaluationRepo`
- `src/infrastructure/config.py` — factory: `get_llm`, `get_langchain_llm`, `get_embedder`, `get_vector_store`, `get_note_loader`, `get_note_writer`, `get_chunker`, `get_chunker_from_env`, `is_readonly`
- `src/application/ingest_vault.py` — `IngestVault` (loader+chunker+store; `execute()`, `execute_single()`)
- `src/application/search_notes.py` — `SearchNotes` (store; `execute()`, `execute_text()`)
- `src/application/manage_notes.py` — `ManageNotes` (loader+writer+ingest; `create()`, `update()`, `get()`)
- `src/agent/agent.py`, `src/agent/tools.py` — ReAct agent + tools (see Architecture above)
- `app.py`, `src/app/__init__.py` — Chainlit entrypoint
- `scripts/test_ollama_chat.py`, `scripts/test_groq.py` — connectivity smoke tests
- `scripts/ingest.py` — CLI de ingesta (`python scripts/ingest.py [--strategy fixed|markdown|backlink]`)
- `scripts/check_architecture.py` — enforces the hexagonal dependency rule, run in CI
- `tests/unit/` — 98 tests passing (models, loader, chunkers, chroma_store, config, ingest_vault, search_notes, manage_notes, agent, tools, metrics)
- `tests/integration/test_ollama_integration.py` — 3 tests `@integration` (require Ollama)

`data/chroma_db/` is populated by running `python scripts/ingest.py` (with Ollama running, or Groq/HF configured via `USE_LOCAL=false`).

## Error log

`docs/error-log.md` tracks design and implementation mistakes caught during AI-assisted development. **Read it at the start of each phase** to avoid repeating them.

Current lessons:
- **Spec/domain name drift**: verify that entity and port names in the next phase's spec match the current domain before implementing. If they diverge, refactor the domain first.
- **Lint after merges**: always run `ruff check src/ tests/ --fix && ruff format src/ tests/` locally before pushing after any conflict resolution.
- **Small models mix `Action`/`Final Answer` in one ReAct turn**: models ≤3B params (e.g. `llama3.2`) tend to emit both an `Action:`/`Action Input:` block and a `Final Answer:` in the same completion, which LangChain's ReAct parser rejects. Recommended minimum: ≥7B instruction-tuned models for write operations (`create_note`/`edit_note`); small models are fine for `search_vault`-only demos. See the full model compatibility table in `docs/error-log.md` (2026-06-18 entry).
- **Bug fixes need regression tests written in the same change**: a prior fix to `handle_parsing_errors`/`early_stopping_method` shipped without tests and had to be retrofitted; write the test that reproduces the exact failing scenario before considering a fix done.

## Implementation roadmap

Phased tasks are documented in `tasks/` (see `tasks/README.md` for the index):
- `fase-0-entorno.md` — project scaffolding, tooling
- `fase-1-dominio.md` — domain models + ports + unit tests
- `fase-2-ingesta.md` — ObsidianLoader, chunkers, ingest script
- `fase-3-vectorstore-llm.md` — ChromaDB adapter, LLM adapter, embedder
- `fase-4-casos-de-uso.md` — application use cases
- `fase-5-agente.md` — ReAct agent + tools
- `fase-6-chainlit.md` — Chainlit UI
- `fase-7-evaluacion.md` — Precision@K / MRR evaluation
- `fase-8-despliegue.md` — Hugging Face Spaces deploy
- `fase-9-memoria-defensa.md` — TFM writeup / defense prep
- `ci-plan.md` — CI workflow design (see `.github/workflows/`)
