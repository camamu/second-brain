---
name: python-clean-code
description: Use when writing or reviewing any Python code (.py files) in the Obsidian RAG project. Defines naming conventions, type hints, Google-style docstrings, function design limits, logging rules, and formatting standards for Python 3.11+. Trigger for any function, class, or module creation/edit.
---

# Skill: Python Clean Code

Target: Python 3.11+. These rules apply to every file in `src/`, `tests/`, and `scripts/`.

---

## Naming

| Element | Convention | Example |
|---|---|---|
| Module / file | `snake_case` | `obsidian_loader.py` |
| Class | `PascalCase` | `ObsidianLoader` |
| Function / method | `snake_case` | `load_by_id()` |
| Variable | `snake_case` | `chunk_list` |
| Constant | `UPPER_SNAKE` | `DEFAULT_CHUNK_SIZE` |
| Private attribute | `_single_leading` | `self._vault_path` |
| Abstract method (port) | no prefix | `def load_all()` |

Names must be **intention-revealing**. If you need a comment to explain what a variable holds, rename it instead.

```python
# Bad
d = load()
tmp = [x for x in d if x.t == "n"]

# Good
all_notes = loader.load_all()
regular_notes = [note for note in all_notes if note.note_type == NoteType.NOTE]
```

---

## Type hints

All public functions and methods must have complete type hints — parameters and return type.

```python
# Bad
def chunk(self, note):
    ...

# Good
def chunk(self, note: Note) -> list[Chunk]:
    ...
```

- Use `list[X]` / `dict[K, V]` (not `List`, `Dict` from `typing` — those are deprecated in 3.9+).
- Use `X | None` (not `Optional[X]` — pipe syntax is cleaner in 3.10+).
- Use `from __future__ import annotations` at the top of files with forward references.
- Dataclass fields: always annotated, use `field(default_factory=...)` for mutable defaults.

---

## Docstrings

Format: **Google style**. Required on all public classes and public methods.

```python
class ObsidianLoader(NoteLoader):
    """Loads notes from an Obsidian vault directory.

    Parses YAML frontmatter, extracts [[backlinks]], and maps the vault
    folder structure to Note domain entities.

    Args:
        vault_path: Absolute path to the root of the Obsidian vault.
    """

    def load_by_id(self, note_id: str) -> Note:
        """Load a single note by its ID (relative path without extension).

        Args:
            note_id: Relative path to the note from vault root, without .md.
                     Example: "01-proyectos/tfm/arquitectura"

        Returns:
            The parsed Note entity.

        Raises:
            NoteNotFoundError: If no file exists at the derived path.
        """
```

Private methods (`_method`) and one-liners can use a single-line docstring.
Skip docstrings on `__init__` when the class docstring already covers the arguments.

---

## Function design

- **One level of abstraction per function.** A function that loops, filters, AND formats is three functions.
- **Maximum 20 lines** per method (excluding docstring). If longer, extract.
- **Maximum 3 parameters** in public methods. If more are needed, group them into a dataclass.
- **No boolean flag parameters** — they signal the function does two things:

```python
# Bad
def load(self, include_archived: bool = False) -> list[Note]: ...

# Good
def load_active(self) -> list[Note]: ...
def load_all_including_archived(self) -> list[Note]: ...
```

- **Return early** to avoid deep nesting:

```python
# Bad
def load_by_id(self, note_id: str) -> Note:
    if self.exists(note_id):
        path = self._resolve_path(note_id)
        if path.exists():
            return self._parse(path)
        else:
            raise NoteNotFoundError(note_id)
    else:
        raise NoteNotFoundError(note_id)

# Good
def load_by_id(self, note_id: str) -> Note:
    if not self.exists(note_id):
        raise NoteNotFoundError(note_id)
    return self._parse(self._resolve_path(note_id))
```

---

## Classes

- **Single Responsibility**: one reason to change. `ObsidianLoader` loads notes — it does not parse metrics, build prompts, or write files.
- Prefer **composition over inheritance** except when implementing ports.
- Keep `__init__` simple: assign attributes, validate inputs, nothing else. No I/O in constructors.
- Use `@dataclass` for plain data containers (domain models). Use regular classes for objects with behavior.
- `@property` for computed attributes that feel like data (`note.word_count`). Avoid setters unless truly needed.

---

## Imports

Order (enforced by `isort`):
1. Standard library
2. Third-party (`langchain`, `chromadb`, `chainlit`)
3. Internal (`src.domain`, `src.adapters`)

```python
import logging
from pathlib import Path

import frontmatter
from langchain_ollama import OllamaEmbeddings

from src.domain.models import Note, NoteType
from src.domain.ports import NoteLoader, NoteNotFoundError
```

Rules:
- No wildcard imports (`from module import *`).
- No circular imports — if you need A from B and B from A, extract a third module C.
- Absolute imports always (`from src.domain.models import Note`, not `from ..domain.models`).

---

## Logging

Never use `print()` in production code. Use the standard `logging` module.

```python
import logging

logger = logging.getLogger(__name__)

# In methods:
logger.debug("Loading note: %s", note_id)
logger.info("Vault indexed: %d chunks created", chunk_count)
logger.warning("Note skipped — empty content: %s", note_id)
logger.error("Failed to parse frontmatter: %s", path, exc_info=True)
```

- One `logger = logging.getLogger(__name__)` per module, at module level.
- Use `%s` formatting in log calls (lazy evaluation), not f-strings.
- `exc_info=True` on error logs that catch exceptions.

---

## Constants and magic numbers

No magic numbers or strings inline:

```python
# Bad
chunks = self._split(content, 512, 50)

# Good
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50
chunks = self._split(content, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP)
```

Module-level constants in `UPPER_SNAKE_CASE`. If shared across modules, put them in `src/domain/models.py` or `src/infrastructure/config.py`.

---

## Line length and formatting

- Max **88 characters** per line (Black default).
- Use `pathlib.Path` instead of `os.path` string manipulation.
- Use f-strings for interpolation, `%s` only in log calls.
- No semicolons. One statement per line.
- Run `black` and `isort` before committing.

---

## What not to do

```python
# No: commented-out code
# result = old_search(query)
result = new_search(query)

# No: redundant comments that restate the code
# Increment i by 1
i += 1

# No: catching bare Exception
try:
    ...
except Exception:
    pass

# No: mutable default arguments
def process(notes: list[Note] = []) -> ...:   # list persists across calls!

# No: global state
_global_embedder = None   # use dependency injection instead
```
