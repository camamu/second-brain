# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TFM (academic project): conversational RAG agent over an Obsidian vault. Three chunking strategies (`fixed`, `markdown`, `backlink`) are the research contribution, evaluated via Precision@K and MRR. UI is Chainlit. See `AGENTS.md` for full stack details and current implementation status.

## Commands

```bash
source .venv/bin/activate                    # activate virtualenv
python scripts/test_ollama_chat.py           # verify Ollama connectivity
chainlit run src/app/__init__.py             # start chat UI (not yet implemented)
pytest tests/unit/                           # unit tests (no I/O, no network)
pytest tests/integration/                    # integration tests (ChromaDB in-memory + real Ollama)
pytest tests/unit/test_models.py -v         # run a single test file
ruff check src/                              # lint
ruff format src/                             # format
```

No Makefile exists. `pyproject.toml` exists with ruff and pytest configuration.

## Architecture

Hexagonal. The dependency rule is strict: inner layers never import from outer ones.

```
src/domain/          → entities (frozen dataclasses) + ABC ports — zero external deps
src/application/     → use cases (one class per file, one execute() method)
src/adapters/        → port implementations: chunkers, embedders, llm, loaders, vector_stores
src/agent/           → LangChain ReAct agent + tools (search_vault, create_note, edit_note)
src/app/             → Chainlit entrypoint
src/infrastructure/  → config loading (.env), dependency wiring
```

**Domain entities** (`src/domain/models.py`): `Note`, `Chunk`, `SearchResult`, `RetrievalQuery`, `EvaluationSample`, `EvaluationResult`, plus enums `ChunkStrategy` and `NoteType`. All are `@dataclass(frozen=True)`.

**Ports** (`src/domain/ports.py`): `NoteLoader`, `NoteWriter`, `BaseChunker`, `ChunkEmbedder`, `VectorStore`, `ConversationalLLM`, `IEvaluationRepo` + exceptions `ObsidianRagError`, `NoteNotFoundError`, `ChunkingError`, `EmbeddingError`, `VectorStoreError`, `VaultWriteError`, `ConfigError`.

**Implemented adapters** (Fase 2 + Fase 3):
- `src/adapters/obsidian_loader.py` — `ObsidianLoader` (implements `NoteLoader` + `NoteWriter`)
- `src/adapters/chunkers/fixed_size.py` — `FixedSizeChunker` + shared `split_text()`
- `src/adapters/chunkers/markdown_header.py` — `MarkdownHeaderChunker`
- `src/adapters/chunkers/backlink_aware.py` — `BacklinkAwareChunker` (injects `NoteLoader`)
- `src/adapters/chunkers/base.py` — re-exports `BaseChunker` from domain
- `src/adapters/llm/ollama_adapter.py` — `OllamaEmbedderAdapter` + `OllamaLLMAdapter`
- `src/adapters/llm/groq_adapter.py` — `HuggingFaceEmbedderAdapter` + `GroqLLMAdapter`
- `src/adapters/vector_stores/chroma_store.py` — `ChromaVectorStore` (1 collection/strategy, cosine)
- `src/infrastructure/config.py` — composition root / factory (reads `.env`, lazy imports)

## Key conventions

- Python 3.11+; full type hints on all public functions and `__init__` params
- Google-style docstrings on all classes and public methods
- Code in English; TFM-explanatory comments in Spanish
- 80-char line limit; `logging` not `print()`
- One adapter class per file; adapters receive injected config, never call `os.getenv()` directly
- Test naming: `test_<class>_<method>_<expected_result>`; pattern AAA (Arrange / Act / Assert)

## Environment variables

Create a `.env` file with:

```env
USE_LOCAL=true              # true=Ollama, false=Groq+HuggingFace
VAULT_PATH=                 # absolute path to Obsidian vault
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.2   # LLM model name in Ollama
OLLAMA_EMBED_MODEL=nomic-embed-text
GROQ_API_KEY=               # only when USE_LOCAL=false
GROQ_MODEL=llama-3.2-90b-text-preview
HF_EMBED_MODEL=nomic-ai/nomic-embed-text-v1
CHUNKER_STRATEGY=fixed      # fixed|markdown|backlink
CHROMA_PERSIST_DIR=data/chroma_db  # where ChromaDB stores its files
```

## Current state

Verify what exists before referencing it:

```bash
find src -name "*.py" ! -name "__init__.py"
```

As of `feature/add-chromadb` (Fase 4 complete), files with real content:
- `src/domain/models.py` — `Note`, `Chunk`, `SearchResult`, `RetrievalQuery`, `EvaluationSample`, `EvaluationResult`, `ChunkStrategy`, `NoteType`
- `src/domain/ports.py` — `NoteLoader`, `NoteWriter`, `BaseChunker`, `ChunkEmbedder`, `VectorStore`, `ConversationalLLM`, `IEvaluationRepo` + full exception hierarchy
- `src/adapters/obsidian_loader.py` — `ObsidianLoader`
- `src/adapters/chunkers/fixed_size.py` — `FixedSizeChunker`, `split_text()`
- `src/adapters/chunkers/markdown_header.py` — `MarkdownHeaderChunker`
- `src/adapters/chunkers/backlink_aware.py` — `BacklinkAwareChunker`
- `src/adapters/llm/ollama_adapter.py` — `OllamaEmbedderAdapter`, `OllamaLLMAdapter`
- `src/adapters/llm/groq_adapter.py` — `HuggingFaceEmbedderAdapter`, `GroqLLMAdapter`
- `src/adapters/vector_stores/chroma_store.py` — `ChromaVectorStore`
- `src/infrastructure/config.py` — factory: `get_llm`, `get_embedder`, `get_vector_store`, `get_note_loader`, `get_note_writer`, `get_chunker`, `get_chunker_from_env`
- `src/application/ingest_vault.py` — `IngestVault` (loader+chunker+store; `execute()`, `execute_single()`)
- `src/application/search_notes.py` — `SearchNotes` (store; `execute()`, `execute_text()`)
- `src/application/manage_notes.py` — `ManageNotes` (loader+writer+ingest; `create()`, `update()`, `get()`)
- `scripts/test_ollama_chat.py` — connectivity smoke test
- `scripts/ingest.py` — CLI de ingesta (`python scripts/ingest.py [--strategy fixed|markdown|backlink]`)
- `tests/unit/` — 73 tests passing (models, loader, chunkers, chroma_store, config, ingest_vault, search_notes, manage_notes)
- `tests/integration/test_ollama_integration.py` — 3 tests `@integration` (require Ollama)

`data/chroma_db/` is empty — run `python scripts/ingest.py` (with Ollama running) to populate it.

## Error log

`docs/error-log.md` tracks design and implementation mistakes caught during AI-assisted development. **Read it at the start of each phase** to avoid repeating them.

Current lessons:
- **Spec/domain name drift**: verify that entity and port names in the next phase's spec match the current domain before implementing. If they diverge, refactor the domain first.
- **Lint after merges**: always run `ruff check src/ tests/ --fix && ruff format src/ tests/` locally before pushing after any conflict resolution.

## Implementation roadmap

Phased tasks are documented in `tasks/`:
- `fase-1-dominio.md` — domain models + ports + unit tests (in progress)
- `fase-2-ingesta.md` — ObsidianLoader, chunkers, ingest script
- `fase-3-vectorstore-llm.md` — ChromaDB adapter, LLM adapter, embedder
- `fase-4-casos-de-uso.md` — application use cases
- `fase-5-agente.md` through `fase-9-memoria-defensa.md` — agent, UI, evaluation, deploy
