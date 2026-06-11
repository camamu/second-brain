---
name: testing-strategy
description: Use when writing or reviewing any test file under tests/ in the Obsidian RAG project. Defines unit vs integration test separation, naming conventions, AAA structure, mocking ports with spec=, fixtures in conftest.py, and coverage targets per layer. Trigger for any new test or test file.
---

# Skill: Testing Strategy

Framework: `pytest`. Tests live in `tests/unit/` and `tests/integration/`.

---

## Two test categories

### Unit tests (`tests/unit/`)
- Zero I/O: no files, no network, no real ChromaDB, no real Ollama.
- Test one class or function in isolation.
- All external dependencies replaced with fakes or mocks.
- Must run in milliseconds. If a unit test is slow, it is not a unit test.

### Integration tests (`tests/integration/`)
- May use the real filesystem, real ChromaDB (in-memory), and real Ollama.
- Test that two or more components work together correctly.
- Slower — run separately from unit tests in CI.
- Use `pytest.mark.integration` to tag them.

```python
# tests/integration/test_ingest_vault.py
import pytest

@pytest.mark.integration
def test_ingest_vault_indexes_all_notes(tmp_vault, real_embedder):
    ...
```

---

## Naming convention

Pattern: `test_<module>_<behaviour>_<expected_result>`

```python
def test_fixed_size_chunker_chunk_empty_note_returns_empty_list(): ...
def test_obsidian_loader_load_by_id_missing_note_raises_not_found(): ...
def test_chroma_store_search_returns_results_ranked_by_score(): ...
def test_ingest_vault_execute_returns_chunk_count(): ...
```

The name must be a complete sentence describing what is being asserted.
Never name tests `test_1`, `test_ok`, or `test_error`.

---

## What to test

Test **behaviour**, not implementation details.

```python
# Bad — tests internal state, breaks if you rename _chunks
def test_chunker():
    chunker = FixedSizeChunker(chunk_size=100)
    chunker.chunk(note)
    assert len(chunker._chunks) == 3   # internal attribute

# Good — tests the contract (what chunk() promises to return)
def test_fixed_size_chunker_chunk_splits_long_note_into_multiple_chunks():
    chunker = FixedSizeChunker(chunk_size=100, overlap=10)
    note = Note(id="n1", title="Test", content="word " * 200, path="/p")
    chunks = chunker.chunk(note)
    assert len(chunks) > 1
    assert all(c.note_id == "n1" for c in chunks)
    assert all(c.strategy == ChunkStrategy.FIXED_SIZE for c in chunks)
```

Every test should have a single logical assertion (multiple `assert` lines are fine if they test the same behaviour).

---

## Mocking ports, not adapters

Always mock **port interfaces**, never concrete adapters. This keeps tests decoupled from implementation details.

```python
from unittest.mock import MagicMock
from src.domain.ports import NoteLoader, VectorStore
from src.domain.models import Note
from src.application.ingest_vault import IngestVault

def test_ingest_vault_execute_calls_store_with_chunks():
    # Arrange
    mock_loader = MagicMock(spec=NoteLoader)
    mock_loader.load_all.return_value = [
        Note(id="n1", title="T", content="some content", path="/p")
    ]
    mock_chunker = MagicMock(spec=BaseChunker)
    mock_chunker.chunk_many.return_value = [fake_chunk]
    mock_embedder = MagicMock(spec=ChunkEmbedder)
    mock_store = MagicMock(spec=VectorStore)

    use_case = IngestVault(mock_loader, mock_chunker, mock_embedder, mock_store)

    # Act
    count = use_case.execute()

    # Assert
    mock_store.add_chunks.assert_called_once_with([fake_chunk], mock_embedder)
    assert count == 1
```

Use `spec=PortClass` in `MagicMock` — it enforces that the mock only exposes methods that exist on the real interface.

---

## Fixtures

Define reusable fixtures in `tests/conftest.py`:

```python
# tests/conftest.py
import pytest
from src.domain.models import Note, NoteType, ChunkStrategy
from src.domain.models import Chunk

@pytest.fixture
def sample_note() -> Note:
    return Note(
        id="proyectos/tfm",
        title="TFM Notes",
        content="## Introducción\nEste es el TFM.\n\n## Arquitectura\nHexagonal.",
        path="/vault/proyectos/tfm.md",
        tags=["tfm", "arquitectura"],
    )

@pytest.fixture
def sample_chunk(sample_note: Note) -> Chunk:
    return Chunk(
        id="proyectos/tfm_0",
        note_id=sample_note.id,
        content="Este es el TFM.",
        strategy=ChunkStrategy.FIXED_SIZE,
        index=0,
    )
```

Rules for fixtures:
- Keep fixtures minimal — only what the test needs.
- Use `tmp_path` (built-in pytest fixture) for tests that need real files.
- Never share mutable state between tests.

---

## Arrange / Act / Assert structure

Every test follows the AAA pattern, separated by blank lines:

```python
def test_markdown_chunker_chunk_creates_one_chunk_per_heading(sample_note):
    # Arrange
    chunker = MarkdownHeaderChunker()

    # Act
    chunks = chunker.chunk(sample_note)

    # Assert
    assert len(chunks) == 2
    assert chunks[0].heading == "Introducción"
    assert chunks[1].heading == "Arquitectura"
```

No inline comments needed when the structure is clear. Add a comment only when the arrange step is non-obvious.

---

## Testing exceptions

```python
import pytest
from src.domain.ports import NoteNotFoundError

def test_obsidian_loader_load_by_id_nonexistent_note_raises_not_found(tmp_path):
    loader = ObsidianLoader(vault_path=str(tmp_path))

    with pytest.raises(NoteNotFoundError) as exc_info:
        loader.load_by_id("does/not/exist")

    assert exc_info.value.note_id == "does/not/exist"
```

Always assert on the exception content, not just its type.

---

## Coverage targets

| Layer | Target |
|---|---|
| `domain/` | 100% — pure logic, no excuses |
| `application/` | 100% — use cases are the core value |
| `adapters/` | ≥ 80% — integration tests cover the rest |
| `agent/` | ≥ 70% — tool definitions and agent config |

Run coverage with:
```bash
pytest tests/unit/ --cov=src --cov-report=term-missing
```

---

## What not to test

- Private methods (`_method`) directly — test them through their public caller.
- Framework internals (LangChain, ChromaDB) — trust the library.
- Configuration loading — verify via integration test, not unit.
- Trivial getters/properties with no logic.
