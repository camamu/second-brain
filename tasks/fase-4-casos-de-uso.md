# Fase 4 — Casos de uso (application layer)

## Contexto

Los casos de uso orquestan la lógica de negocio combinando puertos. No saben nada de ChromaDB, Ollama ni ficheros — solo trabajan con las interfaces abstractas del dominio.

**Ficheros a crear:**
- `src/application/ingest_vault.py`
- `src/application/search_notes.py`
- `src/application/manage_notes.py`
- `scripts/ingest.py`
- `tests/unit/test_ingest_vault.py`
- `tests/unit/test_search_notes.py`
- `tests/unit/test_manage_notes.py`

**Dependencias**: solo `src.domain.*` (models y ports). Nunca importar adaptadores.

---

## Tareas

### T4.1 — Implementar `IngestVault`

Fichero: `src/application/ingest_vault.py`

```python
class IngestVault:
    def __init__(
        self,
        loader: NoteLoader,
        chunker: BaseChunker,
        embedder: ChunkEmbedder,
        store: VectorStore,
    ) -> None:
```

**`execute() -> int`**:
1. `notes = self._loader.load_all()`
2. Si no hay notas, log warning y devolver 0.
3. `chunks = self._chunker.chunk_many(notes)`
4. Si no hay chunks, log warning y devolver 0.
5. `self._store.add_chunks(chunks, self._embedder)`
6. Log info con el número de notas procesadas y chunks indexados.
7. Devolver `len(chunks)`.

**`execute_single(note_id: str) -> int`**:
1. Carga una sola nota con `self._loader.load_by_id(note_id)`.
2. Elimina los chunks anteriores de esa nota: `self._store.delete_by_note(note_id)`.
3. Genera nuevos chunks y los indexa.
4. Devuelve el número de chunks creados.
5. Útil para reindexar una nota después de editarla.

### T4.2 — Implementar `SearchNotes`

Fichero: `src/application/search_notes.py`

```python
class SearchNotes:
    def __init__(
        self,
        store: VectorStore,
        embedder: ChunkEmbedder,
    ) -> None:
```

**`execute(query: RetrievalQuery) -> list[SearchResult]`**:
1. `results = self._store.search(query, self._embedder)`
2. Log info con la query y el número de resultados.
3. Devolver results.

**`execute_text(text: str, top_k: int = 5, strategy: ChunkStrategy = ChunkStrategy.FIXED_SIZE) -> list[SearchResult]`**:
1. Método de conveniencia que construye un `RetrievalQuery` y llama a `execute`.
2. Útil para el agente, que trabaja con strings directamente.

### T4.3 — Implementar `ManageNotes`

Fichero: `src/application/manage_notes.py`

```python
class ManageNotes:
    def __init__(
        self,
        loader: NoteLoader,
        writer: NoteWriter,
        ingest: IngestVault,
    ) -> None:
```

**`create(title: str, content: str, tags: list[str]) -> Note`**:
1. `note = self._writer.create(title, content, tags)`
2. Reindexar la nueva nota: `self._ingest.execute_single(note.id)`
3. Log info.
4. Devolver la nota creada.

**`update(note_id: str, content: str) -> Note`**:
1. `note = self._writer.update(note_id, content)`
2. Reindexar: `self._ingest.execute_single(note.id)`
3. Log info.
4. Devolver la nota actualizada.

**`get(note_id: str) -> Note`**:
1. `return self._loader.load_by_id(note_id)`

### T4.4 — Crear `scripts/ingest.py`

Script CLI que indexa todo el vault. Es un punto de entrada — puede importar de infrastructure.

```python
#!/usr/bin/env python
"""CLI script to ingest the entire Obsidian vault into the vector store."""

import sys
import logging
from src.infrastructure.config import (
    get_note_loader, get_chunker_from_env, get_embedder, get_vector_store
)
from src.application.ingest_vault import IngestVault

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
    logger = logging.getLogger(__name__)

    loader = get_note_loader()
    chunker = get_chunker_from_env()
    embedder = get_embedder()
    store = get_vector_store()

    ingest = IngestVault(loader, chunker, embedder, store)

    logger.info("Starting vault ingestion...")
    count = ingest.execute()
    logger.info("Done. %d chunks indexed.", count)

if __name__ == "__main__":
    main()
```

Opcionalmente, aceptar un argumento `--strategy` para elegir chunker sin cambiar el .env:

```bash
python scripts/ingest.py                    # usa el .env
python scripts/ingest.py --strategy fixed
python scripts/ingest.py --strategy markdown
python scripts/ingest.py --strategy backlink
```

---

## Tests

### T4.5 — `tests/unit/test_ingest_vault.py`

Todos los puertos mockeados con `MagicMock(spec=Port)`.

- `test_ingest_vault_execute_loads_all_notes`
- `test_ingest_vault_execute_chunks_all_notes`
- `test_ingest_vault_execute_adds_chunks_to_store`
- `test_ingest_vault_execute_returns_chunk_count`
- `test_ingest_vault_execute_empty_vault_returns_zero`
- `test_ingest_vault_execute_single_reindexes_one_note`
- `test_ingest_vault_execute_single_deletes_old_chunks_first`

### T4.6 — `tests/unit/test_search_notes.py`

- `test_search_notes_execute_delegates_to_store`
- `test_search_notes_execute_returns_store_results`
- `test_search_notes_execute_text_builds_query_correctly`

### T4.7 — `tests/unit/test_manage_notes.py`

- `test_manage_notes_create_writes_and_reindexes`
- `test_manage_notes_update_writes_and_reindexes`
- `test_manage_notes_get_delegates_to_loader`

---

## Reglas de implementación

- Las clases de application/ solo importan de `src.domain.*`.
- Todas las dependencias llegan por constructor (inyección).
- Un método público `execute()` por caso de uso (excepto ManageNotes que tiene varios, agrupados por semántica).
- No instanciar adaptadores dentro de los casos de uso — nunca.
- `scripts/ingest.py` es el único punto donde se llama a la factory.

---

## Criterio de completado

- [ ] `python scripts/ingest.py` indexa el vault completo sin errores
- [ ] Los tres casos de uso tienen cobertura 100% en tests unitarios
- [ ] `pytest tests/unit/test_ingest_vault.py tests/unit/test_search_notes.py tests/unit/test_manage_notes.py -v` pasa
