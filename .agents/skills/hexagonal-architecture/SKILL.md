---
name: hexagonal-architecture
description: Use whenever creating, moving, or reviewing any file under src/ in the Obsidian RAG project — defines the domain/application/adapters/agent/infrastructure layer map, the dependency rule between them, and how to write ports, adapters, use cases, and the infrastructure factory. Trigger for any new class, new port, new adapter, or when deciding where a piece of code belongs.
---

# Skill: Hexagonal Architecture (Ports & Adapters)

## Layer map

```
src/
├── domain/          # Core — zero external dependencies
│   ├── models.py    # Dataclasses: Note, Chunk, SearchResult, ...
│   └── ports.py     # Abstract interfaces (ABC): NoteLoader, BaseChunker, ...
├── application/     # Use cases — depends only on domain
├── adapters/        # Concrete implementations of ports
├── agent/           # LangChain agent and tools
└── infrastructure/  # Config, env vars, dependency factory
```

---

## Dependency rule (non-negotiable)

```
domain ← application ← adapters
                      ← agent
         infrastructure assembles everything
```

- `domain` imports: stdlib only. Never langchain, chromadb, ollama, or any third-party lib.
- `application` imports: `src.domain.*` only. Never imports adapters or infrastructure.
- `adapters` imports: `src.domain.*` + the specific external library it wraps.
- `agent` imports: `src.domain.*` + `src.application.*` + langchain.
- `infrastructure` imports: everything — it is the composition root.

**If you find yourself importing an adapter from application, stop. Define a port instead.**

---

## Defining a port

Ports live in `src/domain/ports.py`. Every port is an abstract class:

```python
from abc import ABC, abstractmethod
from src.domain.models import Note

class NoteLoader(ABC):
    @abstractmethod
    def load_all(self) -> list[Note]: ...

    @abstractmethod
    def load_by_id(self, note_id: str) -> Note: ...
```

Rules:
- Port names: `NounVerber` pattern — `NoteLoader`, `ChunkEmbedder`, `VectorStore`.
- Every method has full type hints.
- No implementation logic inside ports (except trivial convenience methods that call other abstract methods).
- Domain exceptions (`NoteNotFoundError`, etc.) are also defined in `ports.py`.

---

## Writing an adapter

Adapters live in `src/adapters/`. One file per adapter.

```python
# src/adapters/obsidian_loader.py
from src.domain.models import Note
from src.domain.ports import NoteLoader, NoteNotFoundError

class ObsidianLoader(NoteLoader):
    def __init__(self, vault_path: str) -> None:
        self._vault_path = vault_path   # receives config, does not read env vars

    def load_all(self) -> list[Note]:
        ...

    def load_by_id(self, note_id: str) -> Note:
        ...
```

Rules:
- Adapters receive their dependencies via `__init__`, never via `os.getenv()`.
- Adapters translate external exceptions into domain exceptions:
  ```python
  except FileNotFoundError:
      raise NoteNotFoundError(note_id)
  ```
- Never import one adapter from another adapter.

---

## Writing a use case

Use cases live in `src/application/`. One class per use case, one public method `execute()`.

```python
# src/application/ingest_vault.py
from src.domain.ports import NoteLoader, BaseChunker, ChunkEmbedder, VectorStore

class IngestVault:
    def __init__(
        self,
        loader: NoteLoader,
        chunker: BaseChunker,
        embedder: ChunkEmbedder,
        store: VectorStore,
    ) -> None:
        self._loader = loader
        self._chunker = chunker
        self._embedder = embedder
        self._store = store

    def execute(self) -> int:
        """Returns the number of chunks indexed."""
        notes = self._loader.load_all()
        chunks = self._chunker.chunk_many(notes)
        self._store.add_chunks(chunks, self._embedder)
        return len(chunks)
```

Rules:
- Use cases depend only on port interfaces, never on concrete adapters.
- Constructor receives all dependencies — no `import` of adapters inside the class.
- `execute()` is the single public entry point.

---

## Dependency factory (infrastructure)

`src/infrastructure/config.py` is the composition root — the only place that knows about both ports and adapters:

```python
# src/infrastructure/config.py
import os
from src.domain.ports import NoteLoader, ChunkEmbedder, ConversationalLLM
from src.adapters.obsidian_loader import ObsidianLoader

def get_note_loader() -> NoteLoader:
    return ObsidianLoader(vault_path=os.environ["VAULT_PATH"])

def get_llm() -> ConversationalLLM:
    if os.getenv("USE_LOCAL", "true").lower() == "true":
        from src.adapters.llm.ollama_adapter import OllamaLLM
        return OllamaLLM(model=os.environ["OLLAMA_MODEL"])
    else:
        from src.adapters.llm.groq_adapter import GroqLLM
        return GroqLLM(api_key=os.environ["GROQ_API_KEY"])
```

Rules:
- Only `infrastructure` does conditional imports based on environment.
- Entry points (`app.py`, `scripts/ingest.py`) call factory functions — they never instantiate adapters directly.
- Keep factory functions small: one function per port type.

---

## Quick checklist before committing

- [ ] No adapter imported from `domain/` or `application/`
- [ ] No `os.getenv()` outside `infrastructure/`
- [ ] Every new port defined in `domain/ports.py`
- [ ] Every adapter translates external exceptions to domain exceptions
- [ ] Use cases depend only on port interfaces
