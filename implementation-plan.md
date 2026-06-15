# Implementation Plan — Fase 4: Casos de uso (application layer)

> Documento de planificación previo a la implementación (skill
> `critical-task-planning`). Registro persistente y versionado del plan de la
> Fase 4. El tracking en vivo del harness, si se usa, es efímero; este fichero es
> la fuente de verdad del plan.
>
> El plan de la Fase 3 queda preservado en el historial de git (commit `1a6e62c`
> y anteriores); este fichero se sobrescribe por fase.

## 1. Contexto y decisión de fondo

La Fase 4 implementa la **capa de aplicación**: tres casos de uso que orquestan los
puertos del dominio sin conocer ChromaDB, Ollama ni el filesystem. Es la primera capa
que combina varios puertos a la vez, y el pegamento entre los adaptadores (Fase 2/3) y
el agente (Fase 5). También entrega `scripts/ingest.py`, el primer punto que ejecuta la
factory de extremo a extremo para indexar el vault real (hoy `data/chroma_db/` vacío).

### Deriva spec ↔ dominio (recurrencia del error-log, Fase 1→2 y 2→3)

La spec `tasks/fase-4-casos-de-uso.md` se escribió **antes** del refactor de puertos de
la Fase 3 (donde se decidió, con el usuario, inyectar el `ChunkEmbedder` en el
constructor del `VectorStore`). Por tanto la spec asume firmas que ya no existen. Igual
que en las dos fases anteriores, hay que resolver la divergencia *antes* de implementar
(lección de `docs/error-log.md`).

Divergencias detectadas (verificadas contra `src/domain/ports.py` y `models.py`):

| Spec Fase 4 | Dominio real (Fase 3) | Resolución |
|---|---|---|
| `store.add_chunks(chunks, embedder)` | `VectorStore.add_chunks(chunks)` | quitar `embedder` del argumento |
| `store.search(query, embedder)` | `VectorStore.search(query)` | quitar `embedder` del argumento |
| `IngestVault(loader, chunker, embedder, store)` | el `store` ya tiene el embedder | quitar `embedder` del ctor (param muerto) |
| `SearchNotes(store, embedder)` | el `store` ya tiene el embedder | quitar `embedder` del ctor (param muerto) |
| `execute_text(..., strategy: ChunkStrategy = FIXED_SIZE)` | `RetrievalQuery.strategy: Optional[str]` | tipar el param como `ChunkStrategy \| None = None`; pasar `.value` (o `None`) a la query |
| `scripts/ingest.py` instancia `embedder` y lo pasa | idem | el script no pasa `embedder` a `IngestVault` |

### Decisiones cerradas

1. **Coherencia con el puerto refactorizado de Fase 3 = fuente de verdad** (por encima de
   la firma literal de la spec de Fase 4). El embedder vive dentro del `VectorStore`; los
   casos de uso **no** reciben ni manejan embedder. Esto mantiene el principio de la Fase 3
   ("métodos del puerto limpios, embedder inyectado") y evita un parámetro muerto que
   confundiría al lector del TFM.
2. **`SearchNotes` queda como wrapper fino** sobre `store.search`. Aun siendo delgado, se
   mantiene como caso de uso porque (a) añade logging del nº de resultados, (b) ofrece
   `execute_text` para el agente (Fase 5), y (c) preserva la simetría de la capa.
3. **`execute_text` acepta `ChunkStrategy | None`** (API tipada para el agente) y traduce
   internamente a `str`/`None` al construir el `RetrievalQuery` (cuyo campo es `Optional[str]`).
4. **`execute_single` borra antes de indexar** (delete → chunk → add) para evitar chunks
   huérfanos al reindexar una nota editada. (Decisión ya registrada en
   `critical-task-planning.md`, fila "formato de ID de los Chunks".)

Verificado: `src/application/` está vacío (solo `__init__.py`); no hay nada que romper.
Los puertos a consumir existen con estas firmas: `NoteLoader.load_all()/load_by_id()`,
`NoteWriter.create(title, content, tags)/update(note_id, content)`,
`BaseChunker.chunk_many(notes)`, `VectorStore.add_chunks(chunks)/search(query)/delete_by_note(note_id)`,
`RetrievalQuery(query, top_k=5, min_score=0.0, strategy: Optional[str]=None)`.

## 2. Mapa de cambios

### Ficheros nuevos

| Fichero | Contenido |
|---|---|
| `src/application/ingest_vault.py` | `IngestVault` (orquesta loader+chunker+store) |
| `src/application/search_notes.py` | `SearchNotes` (wrapper de `store.search`) |
| `src/application/manage_notes.py` | `ManageNotes` (writer + reindex vía `IngestVault`) |
| `scripts/ingest.py` | CLI de ingesta del vault completo (con `--strategy`) |
| `tests/unit/test_ingest_vault.py` | tests con puertos `MagicMock(spec=...)` |
| `tests/unit/test_search_notes.py` | tests del wrapper y `execute_text` |
| `tests/unit/test_manage_notes.py` | tests de create/update/get + reindex |

### Firmas finales (antes → después respecto a la spec)

| Spec Fase 4 | Plan (implementado) |
|---|---|
| `IngestVault(loader, chunker, embedder, store)` | `IngestVault(loader, chunker, store)` |
| `store.add_chunks(chunks, embedder)` | `store.add_chunks(chunks)` |
| `SearchNotes(store, embedder)` | `SearchNotes(store)` |
| `store.search(query, embedder)` | `store.search(query)` |
| `execute_text(text, top_k=5, strategy: ChunkStrategy=FIXED_SIZE)` | `execute_text(text, top_k=5, strategy: ChunkStrategy \| None = None)` |

> No se modifica el dominio en esta fase: el refactor ya se hizo en Fase 3. La
> divergencia se resuelve adaptando la spec de Fase 4 al puerto, no al revés.

## 3. Especificación de componentes

### `IngestVault` (`src/application/ingest_vault.py`)

- `__init__(self, loader: NoteLoader, chunker: BaseChunker, store: VectorStore) -> None`.
- `execute() -> int`:
  1. `notes = self._loader.load_all()`.
  2. Si `not notes` → `logger.warning(...)`, `return 0`.
  3. `chunks = self._chunker.chunk_many(notes)`.
  4. Si `not chunks` → `logger.warning(...)`, `return 0`.
  5. `self._store.add_chunks(chunks)`.
  6. `logger.info("Ingested %d notes -> %d chunks", len(notes), len(chunks))`.
  7. `return len(chunks)`.
- `execute_single(note_id: str) -> int`:
  1. `note = self._loader.load_by_id(note_id)` (propaga `NoteNotFoundError`).
  2. `self._store.delete_by_note(note_id)` (borra chunks viejos primero).
  3. `chunks = self._chunker.chunk_many([note])`.
  4. `self._store.add_chunks(chunks)`.
  5. `logger.info(...)`; `return len(chunks)`.
- No captura `VectorStoreError`/`ChunkingError`: se propagan al llamador (script/agente).

### `SearchNotes` (`src/application/search_notes.py`)

- `__init__(self, store: VectorStore) -> None`.
- `execute(query: RetrievalQuery) -> list[SearchResult]`:
  1. `results = self._store.search(query)`.
  2. `logger.info("Search '%s' -> %d results", query.query, len(results))`.
  3. `return results`.
- `execute_text(self, text: str, top_k: int = 5, strategy: ChunkStrategy | None = None) -> list[SearchResult]`:
  1. `strategy_value = strategy.value if strategy else None`.
  2. `query = RetrievalQuery(query=text, top_k=top_k, strategy=strategy_value)`.
  3. `return self.execute(query)`.

### `ManageNotes` (`src/application/manage_notes.py`)

- `__init__(self, loader: NoteLoader, writer: NoteWriter, ingest: IngestVault) -> None`.
- `create(title: str, content: str, tags: list[str]) -> Note`:
  1. `note = self._writer.create(title, content, tags)`.
  2. `self._ingest.execute_single(note.id)`.
  3. `logger.info(...)`; `return note`.
- `update(note_id: str, content: str) -> Note`:
  1. `note = self._writer.update(note_id, content)`.
  2. `self._ingest.execute_single(note.id)`; `logger.info(...)`; `return note`.
- `get(note_id: str) -> Note`: `return self._loader.load_by_id(note_id)`.

### `scripts/ingest.py`

- Punto de entrada → **sí** puede importar de `infrastructure` y `application`.
- `argparse` con `--strategy {fixed,markdown,backlink}` opcional.
  - Sin flag → `get_chunker_from_env()`.
  - Con flag → `get_chunker(ChunkStrategy(value))`.
- `loader = get_note_loader()`, `chunker`, `store = get_vector_store()`.
- `ingest = IngestVault(loader, chunker, store)`; `count = ingest.execute()`; log final.

## 4. Tests

Todos con puertos mockeados `MagicMock(spec=Port)`, patrón AAA, naming
`test_<class>_<method>_<expected>` (skill `testing-strategy`).

### `tests/unit/test_ingest_vault.py`
- `test_ingest_vault_execute_loads_all_notes`
- `test_ingest_vault_execute_chunks_all_notes`
- `test_ingest_vault_execute_adds_chunks_to_store`
- `test_ingest_vault_execute_returns_chunk_count`
- `test_ingest_vault_execute_empty_vault_returns_zero` (loader devuelve `[]`)
- `test_ingest_vault_execute_no_chunks_returns_zero` (chunker devuelve `[]`)
- `test_ingest_vault_execute_single_reindexes_one_note`
- `test_ingest_vault_execute_single_deletes_old_chunks_first`
  (verificar orden: `delete_by_note` llamado **antes** que `add_chunks`)

### `tests/unit/test_search_notes.py`
- `test_search_notes_execute_delegates_to_store`
- `test_search_notes_execute_returns_store_results`
- `test_search_notes_execute_text_builds_query_correctly` (verifica `query`, `top_k`)
- `test_search_notes_execute_text_translates_strategy_to_value`
  (pasar `ChunkStrategy.MARKDOWN_HEADER` → `RetrievalQuery.strategy == "markdown"`)
- `test_search_notes_execute_text_none_strategy_passes_none`

### `tests/unit/test_manage_notes.py`
- `test_manage_notes_create_writes_and_reindexes`
- `test_manage_notes_update_writes_and_reindexes`
- `test_manage_notes_get_delegates_to_loader`

## 5. Bloques "Análisis previo" (puntos arriesgados)

### Análisis previo: embedder en los casos de uso (deriva spec ↔ puerto)
**Aspecto crítico**: la spec de Fase 4 inyecta `ChunkEmbedder` en `IngestVault`/`SearchNotes`
y lo pasa a `add_chunks`/`search`, pero el puerto `VectorStore` (refactor Fase 3) ya
contiene el embedder y sus métodos no lo aceptan.
**Opciones consideradas**:
1. Seguir la spec literal: añadir `embedder` al ctor aunque no se use → parámetro muerto,
   acopla la capa de aplicación a un concepto que el puerto ya resolvió, y rompería en
   runtime (`add_chunks` no acepta 2º argumento).
2. Adaptar la spec al puerto: los casos de uso no conocen el embedder; el `store` (creado
   por la factory con su embedder) basta.
**Decisión**: Opción 2 — coherente con la decisión cerrada de Fase 3 y con el contrato
real del puerto; mantiene la capa de aplicación dependiendo solo de abstracciones limpias.
**Riesgo aceptado**: la spec de Fase 4 queda desactualizada respecto al código. Mitigación:
documentar la deriva en `docs/error-log.md` y marcar los criterios en la spec.

### Análisis previo: tipo de `strategy` en `execute_text`
**Aspecto crítico**: `RetrievalQuery.strategy` es `Optional[str]`, pero la spec tipa el
param de `execute_text` como `ChunkStrategy`.
**Opciones consideradas**:
1. Aceptar `str` directamente → simple pero sin seguridad de tipos para el agente.
2. Aceptar `ChunkStrategy | None` y traducir a `.value` → API tipada, error temprano.
**Decisión**: Opción 2 — el agente (Fase 5) trabaja con el enum; la traducción a `str`
se encapsula en el caso de uso, respetando el tipo del campo del dominio.
**Riesgo aceptado**: ninguno relevante; `None` se delega a la estrategia por defecto del store.

### Orden delete→add en `execute_single`
Decisión ya registrada en `critical-task-planning.md`: *"borrar todos los chunks de la
nota antes de reindexar"*. Evita chunks huérfanos cuando una nota cambia de nº de chunks.

## 6. Orden de ejecución (con gates)

1. (Hecho) Crear este `implementation-plan.md`. Verificar firma de `get_vector_store`
   y `get_chunker` en `config.py` para cablear bien `scripts/ingest.py --strategy`.
2. `IngestVault` + `test_ingest_vault.py` → **gate**: `pytest tests/unit/test_ingest_vault.py -v`.
3. `SearchNotes` + `test_search_notes.py` → **gate**: `pytest tests/unit/test_search_notes.py -v`.
4. `ManageNotes` + `test_manage_notes.py` → **gate**: `pytest tests/unit/test_manage_notes.py -v`.
5. `scripts/ingest.py` (depende de los tres casos de uso y de la factory).
6. **gate final**: `ruff check src/ tests/ scripts/ --fix && ruff format src/ tests/ scripts/`
   y `pytest tests/unit -q` (todos verdes, incluidos los 57 previos).
7. (Manual, requiere Ollama + vault real) `python scripts/ingest.py` indexa sin errores.
8. Sincronizar docs: `CLAUDE.md`, criterios en `tasks/fase-4-casos-de-uso.md`,
   entrada en `docs/error-log.md` (deriva spec↔dominio Fase 3→4).

## 7. Criterio de completado

- [x] Los tres casos de uso implementados; importan **solo** de `src.domain.*`.
- [x] Ningún caso de uso instancia adaptadores ni recibe/usa `embedder`.
- [x] `execute_single` borra antes de añadir (test del orden verde).
- [x] `execute_text` traduce `ChunkStrategy → str` correctamente.
- [x] `pytest tests/unit/test_ingest_vault.py tests/unit/test_search_notes.py tests/unit/test_manage_notes.py -v` pasa.
- [ ] `python scripts/ingest.py` indexa el vault completo sin errores (manual, con Ollama).
- [x] `ruff check` y `ruff format` limpios; docs sincronizadas; error-log actualizado.

## 8. TODOs por funcionalidad

### 🧩 Casos de uso — Ingesta
- [x] `IngestVault.__init__(loader, chunker, store)` (sin embedder).
- [x] `execute()` con guardas de vault vacío / sin chunks y logging.
- [x] `execute_single(note_id)` con orden delete → chunk → add.

### 🔎 Casos de uso — Búsqueda
- [x] `SearchNotes.__init__(store)` (sin embedder).
- [x] `execute(query)` con logging.
- [x] `execute_text(text, top_k, strategy: ChunkStrategy | None)` con traducción a `.value`.

### ✍️ Casos de uso — Gestión de notas
- [x] `ManageNotes.__init__(loader, writer, ingest)`.
- [x] `create` / `update` con reindex vía `execute_single`.
- [x] `get` delegando en `loader.load_by_id`.

### 🖥️ Script CLI
- [x] `scripts/ingest.py` con `argparse --strategy` y wiring vía factory.
- [x] Coherencia chunker ↔ store: `--strategy` sobreescribe `CHUNKER_STRATEGY` en env antes de instanciar la factory.

### 🧪 Tests
- [x] `test_ingest_vault.py` (8 tests, incl. orden delete-antes-de-add).
- [x] `test_search_notes.py` (5 tests, incl. traducción de strategy).
- [x] `test_manage_notes.py` (3 tests).
- [x] Gate: `pytest tests/unit -q` verde (57 previos + 16 nuevos = 73/73).

### 📚 Documentación y sincronización
- [x] Actualizar `CLAUDE.md` (capa `application/` y `scripts/ingest.py`).
- [x] Marcar criterios en `tasks/fase-4-casos-de-uso.md`.
- [x] Entrada en `docs/error-log.md` (recurrencia deriva spec↔dominio, Fase 3→4).

### ✅ Verificación final
- [x] `ruff check src/ tests/ scripts/ --fix && ruff format ...`.
- [x] `pytest tests/unit -q` verde (73/73).
- [ ] (Manual) `python scripts/ingest.py` indexa el vault (requiere Ollama + vault).
