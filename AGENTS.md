# AGENTS.md — second-brain (Obsidian RAG Agent)

## What this is

TFM (academic project): conversational RAG agent over an Obsidian vault via Chainlit. Three chunking strategies are the research contribution (Precision@K + MRR evaluation).

**Status: scaffolding only.** `src/` packages exist but most are empty `__init__.py`. One adapter implemented (`src/adapters/llm/ollama_chat.py`). No real tests, scripts, or `.env.example` yet.

Do not assume components mentioned below (chunkers, ChromaDB store, ingest script, app entrypoint) are implemented — check the filesystem before referencing them.

## Stack

| Layer | Tech |
|---|---|
| LLM | Ollama (`llama3.2` / `qwen3.6:35b-a3b`) |
| Embeddings | Ollama `nomic-embed-text` |
| Vector store | ChromaDB (persisted to `data/chroma_db/`) |
| Orchestrator | LangChain |
| UI | Chainlit (`app.py`) |

## Architecture

Hexagonal, intent-driven. Internal layers must not depend on external ones:

```
src/domain/      → entities + ports (ABC interfaces)
src/application/ → use cases (Receive config from domain-only params)
src/adapters/    → LLM, chunkers, embedders, loaders, vector stores (implement ports)
src/agent/       → LangChain agent + tools
src/app/         → Chainlit entrypoint
src/infrastructure/ → config loading, dependency wiring
```

**Port naming**: `NounVerber` e.g. `NoteLoader`, `ChunkEmbedder`.
**All methods abstract**: full type hints on ABC methods and `__init__` params.
**Adapters receive injected config only** — no direct `os.getenv()`.

## Key conventions

- Python 3.11+, type hints on all public functions
- Google-style docstrings (classes and public methods)
- Code in English; Spanish only in TFM-explanatory comments
- 80-char line limit; `logging` not `print()`
- One adapter class per file, one use case class with `execute()` method

## Env variables (create `.env` from these)

```
USE_LOCAL=true          # true=Ollama, false=Groq+HuggingFace
VAULT_PATH=             # absolute path to Obsidian vault
OLLAMA_BASE_URL=http://localhost:11434
GROQ_API_KEY=           # only when USE_LOCAL=false
CHUNKER_STRATEGY=fixed  # fixed|markdown|backlink
```

## Commands

```bash
source .venv/bin/activate       # activate venv
python scripts/test_ollama_chat.py   # verify Ollama connectivity (only script that exists)
chainlit run src/app/__init__.py  # start chat UI (once app is implemented)
pytest tests/unit/              # unit tests (no I/O, no network)
pytest tests/integration/       # integration (ChromaDB in-memory + real Ollama ok)
```

Test naming: `test_<module>_<behavior>_<expected_result>`

## Data flow

```
Vault .md → ObsidianLoader → Chunker → Embedder → VectorStore (ChromaDB)
User query → Agent (ReAct) → search_vault tool → LLM response → Chainlit UI
```

Tools the agent provides: `search_vault`, `create_note`, `edit_note`

## Gotchas for agents

1. **Most of `src/` is empty stubs** — verify what actually exists with `find src -name "*.py"`; there are 14 total with most being blank `__init__.py`.
2. **Correct script name** — the only real script is `scripts/test_ollama_chat.py`, not `test_ollama.py`.
3. **No Makefile/task runner** — every command must be typed manually; no `npm test`, `make build`, etc.
4. **`scripts/test_ollama_chat.py` uses `sys.path.insert(0, ...)` to reach `src/`** — imports won't work without it; do not rely on pip install or package installs yet.
5. **OllamaChat hardcodes defaults** — `src/adapters/llm/ollama_chat.py:18-24` sets `model="llama3.2"`, `base_url`, and a system prompt in the signature; pass them explicitly (they're not loaded from env).
6. **README.md is a single-line tagline** — gives no navigational help.
7. **`data/chroma_db/` and tests directories are empty** — vault must be ingested before retrieval works; `tests/unit/` and `tests/integration/` contain no test files yet.
8. **No lint/typecheck config exists** — pyproject.toml, tox.ini, ruff.toml all absent. Tests run with bare `pytest`.

---

*Generated from filesystem inspection. Trust the code, not this file.*
