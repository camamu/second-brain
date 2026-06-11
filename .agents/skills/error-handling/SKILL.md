---
name: error-handling
description: Use when raising, catching, or translating exceptions anywhere in the Obsidian RAG project. Defines the ObsidianRagError exception hierarchy, which layer catches/translates which errors, logging with exc_info, and when to raise vs return empty/sentinel values. Trigger for any try/except block or new exception type.
---

# Skill: Error Handling

---

## Hierarchy of domain exceptions

All project-specific exceptions are defined in `src/domain/ports.py`.
They inherit from a single base class so callers can catch broadly or narrowly.

```python
# src/domain/ports.py

class ObsidianRagError(Exception):
    """Base exception for all domain errors in this project."""

class NoteNotFoundError(ObsidianRagError):
    def __init__(self, note_id: str) -> None:
        super().__init__(f"Note not found: '{note_id}'")
        self.note_id = note_id

class ChunkingError(ObsidianRagError):
    def __init__(self, note_id: str, reason: str) -> None:
        super().__init__(f"Failed to chunk note '{note_id}': {reason}")
        self.note_id = note_id

class EmbeddingError(ObsidianRagError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Embedding failed: {reason}")

class VectorStoreError(ObsidianRagError):
    def __init__(self, operation: str, reason: str) -> None:
        super().__init__(f"VectorStore '{operation}' failed: {reason}")

class VaultWriteError(ObsidianRagError):
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"Cannot write to vault at '{path}': {reason}")
```

Rules:
- Never raise `Exception` or `RuntimeError` directly — always a domain exception.
- Every domain exception carries context (which note, which operation, why it failed).
- Add new exception types here as new error cases emerge — do not reuse exceptions for unrelated failures.

---

## Where to catch and translate

**Adapters** are responsible for catching external exceptions and translating them into domain exceptions. Nothing above the adapter layer should ever see a `chromadb.errors.InvalidDimensionException` or an `httpx.ConnectError`.

```python
# src/adapters/vector_store/chroma_store.py

class ChromaVectorStore(VectorStore):
    def search(self, query: RetrievalQuery, embedder: ChunkEmbedder) -> list[SearchResult]:
        try:
            results = self._collection.query(...)
            return self._map_results(results)
        except Exception as exc:
            raise VectorStoreError("search", str(exc)) from exc
```

The `from exc` preserves the original traceback — never omit it.

```python
# src/adapters/obsidian_loader.py

def load_by_id(self, note_id: str) -> Note:
    path = self._resolve_path(note_id)
    if not path.exists():
        raise NoteNotFoundError(note_id)
    try:
        return self._parse(path)
    except Exception as exc:
        raise ChunkingError(note_id, str(exc)) from exc
```

---

## What each layer does with exceptions

| Layer | Responsibility |
|---|---|
| `adapters/` | Catch external errors, raise domain exceptions |
| `application/` | Let domain exceptions propagate upward — do not catch them |
| `agent/` | Catch domain exceptions, return user-friendly tool error messages |
| `app.py` (Chainlit) | Catch `ObsidianRagError`, display a clean message to the user |

```python
# src/agent/tools.py — catching in the agent layer

def search_vault(query: str) -> str:
    try:
        results = search_use_case.execute(RetrievalQuery(text=query))
        return format_results(results)
    except VectorStoreError as exc:
        logger.error("Search failed: %s", exc)
        return "No pude buscar en el vault. Comprueba que el índice está generado."
    except ObsidianRagError as exc:
        logger.error("Unexpected domain error during search: %s", exc)
        return "Ocurrió un error inesperado al buscar."
```

---

## Logging exceptions

Always log before translating or re-raising. Use `exc_info=True` to capture the full traceback.

```python
import logging
logger = logging.getLogger(__name__)

try:
    result = self._collection.query(...)
except Exception as exc:
    logger.error("ChromaDB query failed", exc_info=True)
    raise VectorStoreError("search", str(exc)) from exc
```

Never swallow exceptions silently:

```python
# Bad — hides the error completely
try:
    risky_operation()
except Exception:
    pass

# Bad — loses the original traceback
try:
    risky_operation()
except Exception as exc:
    raise VectorStoreError("op", str(exc))   # missing "from exc"

# Good
try:
    risky_operation()
except Exception as exc:
    logger.error("Operation failed", exc_info=True)
    raise VectorStoreError("op", str(exc)) from exc
```

---

## Validation errors

Validate preconditions at the boundary where data enters the system — in the adapter or use case, not deep in private methods.

```python
# src/application/ingest_vault.py

def execute(self) -> int:
    notes = self._loader.load_all()
    if not notes:
        logger.warning("Vault is empty — nothing to index")
        return 0
    ...
```

```python
# src/adapters/chunkers/fixed_size.py

def chunk(self, note: Note) -> list[Chunk]:
    if not note.content.strip():
        logger.warning("Skipping empty note: %s", note.id)
        return []
    ...
```

Prefer returning an empty list or a sentinel value over raising for expected edge cases (empty vault, empty note). Reserve exceptions for unexpected failures.

---

## Never do this

```python
# Never: bare except
try:
    ...
except:
    ...

# Never: catching Exception without re-raising or logging
try:
    ...
except Exception:
    return None   # silent failure

# Never: domain exceptions leaking infrastructure details
raise NoteNotFoundError(f"psycopg2.OperationalError: connection refused")
#                        ^^^ infrastructure detail — use a clean message

# Never: raising in __init__ for config errors — validate lazily or in a factory
class ChromaVectorStore(VectorStore):
    def __init__(self, path: str) -> None:
        if not Path(path).exists():
            raise VectorStoreError("init", f"Path not found: {path}")  # ok here
```

---

## Quick reference

| Situation | What to do |
|---|---|
| Note not found in vault | Raise `NoteNotFoundError(note_id)` |
| Chunking fails on a note | Raise `ChunkingError(note_id, reason)` |
| Ollama / Groq call fails | Raise `EmbeddingError(reason)` |
| ChromaDB operation fails | Raise `VectorStoreError(operation, reason)` |
| Cannot write to vault | Raise `VaultWriteError(path, reason)` |
| Empty vault or empty note | Log warning, return empty list |
| Agent tool error | Catch domain exception, return user-friendly string |
| Chainlit top level | Catch `ObsidianRagError`, show clean error in UI |
