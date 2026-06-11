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

No Makefile exists. No `pyproject.toml` — ruff and pytest run with bare defaults.

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

**Ports** (`src/domain/ports.py`): `IVaultReader`, `IVaultWriter`, `IBaseChunker`, `IEmbedder`, `IVectorStore`, `ILLMChat`, `IEvaluationRepo`. Port naming convention: `INounVerber`.

**Only implemented adapter**: `src/adapters/llm/ollama_chat.py` — wraps `ChatOllama` from `langchain-ollama`. Everything else under `src/adapters/` is an empty `__init__.py`.

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
GROQ_API_KEY=               # only when USE_LOCAL=false
CHUNKER_STRATEGY=fixed      # fixed|markdown|backlink
```

## Current state

Most of `src/` is empty stubs. Verify what exists before referencing it:

```bash
find src -name "*.py" ! -name "__init__.py"
```

As of the last commit on `feature/create-domain-entities`, only these files have real content:
- `src/domain/models.py` — all domain entities implemented
- `src/domain/ports.py` — all ABC interfaces implemented
- `src/adapters/llm/ollama_chat.py` — one concrete adapter
- `scripts/test_ollama_chat.py` — connectivity smoke test

`tests/unit/` and `tests/integration/` directories exist but contain no test files yet.  
`data/chroma_db/` is empty — the vault must be ingested before retrieval works.

## Implementation roadmap

Phased tasks are documented in `tasks/`:
- `fase-1-dominio.md` — domain models + ports + unit tests (in progress)
- `fase-2-ingesta.md` — ObsidianLoader, chunkers, ingest script
- `fase-3-vectorstore-llm.md` — ChromaDB adapter, LLM adapter, embedder
- `fase-4-casos-de-uso.md` — application use cases
- `fase-5-agente.md` through `fase-9-memoria-defensa.md` — agent, UI, evaluation, deploy
