# Plan de implementación — Fase 2 (Adaptadores de ingesta)

> Documento de planificación generado tras aplicar la skill `critical-task-planning`.
> Recoge **todas** las decisiones tomadas antes de escribir código, el mapa de
> renombrado del dominio, los análisis previos de los puntos arriesgados y el
> orden de ejecución con sus *gates* de verificación.

---

## 0. Contexto y decisión de fondo

El fichero `tasks/fase-2-ingesta.md` describe un diseño que **contradice** tanto el
dominio ya implementado en Fase 1 (`src/domain/models.py`, `src/domain/ports.py`,
mergeado en PR #1 y #2) como las convenciones documentadas en `CLAUDE.md`.

**Decisión tomada (usuario):**
1. **El fichero de fase es la fuente de verdad**, también para los **nombres**.
2. Se **añaden** `note_type` y `path` a `Note`.
3. Se **añade** `exists()` al puerto de lectura.
4. Al terminar, se **sincroniza la documentación** (`CLAUDE.md`,
   `tasks/fase-2-ingesta.md`) y se registra la deriva en `docs/error-log.md`.

Consecuencia: Fase 2 incluye un **refactor amplio del dominio** (capa interna del
hexágono) y la reescritura de los tests de Fase 1 que dependen de los nombres
antiguos.

---

## 1. Mapa de renombrado del dominio (fase = canónico)

### `src/domain/models.py · Note`
| Antes | Después |
|---|---|
| `note_id: str` | **`id: str`** |
| — | **`path: str`** (ruta absoluta del `.md`) |
| — | **`note_type: NoteType = NoteType.OTHER`** |
| `title, content, frontmatter, tags, backlinks, created_at, updated_at` | se mantienen |

- Actualizar `__post_init__` (`self.note_id` → `self.id`).
- Actualizar `with_tags()` para propagar `path` y `note_type`.
- Properties (`tag_string`, `backlink_string`, `word_count`, `is_empty`, …) se mantienen.
- **Notas vacías**: el *loader* normaliza contenido whitespace-only a `""` y emite
  `logger.warning`; así se respeta la validación de dominio sin debilitarla
  (`content=""` es válido; `"   "` no).

### `src/domain/models.py · Chunk`
| Antes | Después |
|---|---|
| `chunk_id: str` | **`id: str`** |
| `position: int` | **`index: int`** |
| `strategy: str` | **`strategy: ChunkStrategy`** (enum, no `.value`) |
| — | **`heading: Optional[str] = None`** |
| `note_id, token_count, metadata` | se mantienen |

- Actualizar `__post_init__` (`self.chunk_id` → `self.id`).
- Se conserva la invariante "content no vacío debe tener ≥ 10 caracteres".

### `src/domain/models.py · ChunkStrategy`
| Member antes | Member después | `.value` |
|---|---|---|
| `FIXED` | **`FIXED_SIZE`** | `"fixed"` |
| `MARKDOWN` | **`MARKDOWN_HEADER`** | `"markdown"` |
| `BACKLINK` | **`BACKLINK_AWARE`** | `"backlink"` |

- **Los `.value` se mantienen** (`fixed/markdown/backlink`) para no romper
  `CHUNKER_STRATEGY=fixed|markdown|backlink` del `.env`.

### `src/domain/ports.py`
| Antes | Después |
|---|---|
| `IVaultReader` | **`NoteLoader`** |
| `IVaultWriter` | **`NoteWriter`** |
| `IBaseChunker` | **`BaseChunker`** |

**`NoteLoader`** (lectura):
- `load()` → **`load_by_id(note_id: str) -> Note`**
- **+ `exists(note_id: str) -> bool`** (método abstracto nuevo)
- conserva **`load_all() -> list[Note]`**
- `load_by_tags()` se mantiene (capacidad existente, no la usa Fase 2)

**`NoteWriter`** (escritura):
- **`create(title: str, content: str, tags: list[str]) -> Note`**
- **`update(note_id: str, content: str) -> Note`**
- `delete()` se **omite** (no lo pide la fase; se reintroducirá si Fase 5 lo necesita)

**`BaseChunker`**:
- `chunk(note: Note) -> list[Chunk]` (abstracto) se mantiene.
- `chunk_many()` se **corrige**: actualmente hace `except: pass` (silencia errores,
  viola la skill `error-handling`). Pasará a loguear con `exc_info=True` y a
  traducir/propagar como `ChunkingError`.

**Excepciones** (`ObsidianRagError` y subclases) ya existen y no se tocan:
`NoteNotFoundError`, `ChunkingError`, `VaultWriteError`.

### Deuda técnica aceptada (fuera de Fase 2)
- `SearchResult` y `EvaluationSample` **no se tocan**: siguen con `chunk_id`/`note_id`.
  Queda la inconsistencia temporal `Chunk.id` vs `SearchResult.chunk_id`, anotada
  para resolver en Fase 3.

---

## 2. Dependencias y archivos

### Dependencia externa nueva
- `python-frontmatter` (no instalado actualmente).
- **No existe `requirements.txt`** → crearlo y añadir la dependencia
  (más las ya usadas: `langchain-ollama`, `langchain-core`, `pytest`, `ruff`).

### Archivos a crear
- `src/adapters/obsidian_loader.py` — `ObsidianLoader` (implementa `NoteLoader` + `NoteWriter`)
- `src/adapters/chunkers/base.py` — re-exporta `BaseChunker` del dominio
- `src/adapters/chunkers/fixed_size.py` — `FixedSizeChunker`
- `src/adapters/chunkers/markdown_header.py` — `MarkdownHeaderChunker`
- `src/adapters/chunkers/backlink_aware.py` — `BacklinkAwareChunker`
- `tests/unit/test_obsidian_loader.py`
- `tests/unit/test_chunkers.py`
- `docs/error-log.md` (no existe `docs/` aún)

### Archivos a modificar
- `src/domain/models.py`, `src/domain/ports.py` (refactor sección 1)
- `tests/conftest.py`, `tests/unit/test_models.py` (renombrado a nombres nuevos)
- `tasks/fase-2-ingesta.md`, `CLAUDE.md` (sincronización final)

### Nota de ubicación
- Existe `src/adapters/document_loaders/` (vacío). La fase pide
  `src/adapters/obsidian_loader.py` (plano) → se sigue la fase. El directorio
  `document_loaders/` se deja o se elimina al sincronizar.

---

## 3. Especificación de los adaptadores

### T2.1 — `ObsidianLoader` (`src/adapters/obsidian_loader.py`)
Constructor: `vault_path: str`. Única dependencia externa: `frontmatter`.
Todas las excepciones externas (`FileNotFoundError`, etc.) se traducen a
excepciones de dominio. `logger = logging.getLogger(__name__)`.

**`load_all() -> list[Note]`**
1. Recorre recursivamente `vault_path` buscando `*.md`.
2. `python-frontmatter` separa YAML del contenido.
3. `title` ← frontmatter o nombre de fichero (sin extensión).
4. `tags` ← frontmatter (`tags: [...]`).
5. `note_type` ← frontmatter `type` mapeado a `NoteType` (default `OTHER` si falta/no mapea).
6. `created_at`/`updated_at` ← frontmatter.
7. `backlinks` ← regex sobre `[[nombre]]`; los alias `[[nombre|alias]]` extraen solo `nombre`.
8. `id` ← ruta relativa desde `vault_path` sin `.md`
   (`/vault/01-proyectos/tfm.md` → `01-proyectos/tfm`).
9. `path` ← ruta absoluta del `.md`.
10. Contenido whitespace-only → `""` + `logger.warning`.

**`load_by_id(note_id: str) -> Note`**
1. Ruta = `vault_path / (note_id + ".md")`.
2. Si no existe → `NoteNotFoundError(note_id)`.
3. Parseo idéntico a `load_all`.

**`exists(note_id: str) -> bool`**
1. Comprueba existencia del fichero en disco.

**`create(title: str, content: str, tags: list[str]) -> Note`**
1. Path = `vault_path/00-inbox/{title_slug}.md`.
2. Escribe frontmatter YAML + contenido.
3. Si ya existe → `VaultWriteError`.
4. Devuelve la `Note` creada.

**`update(note_id: str, content: str) -> Note`**
1. Carga la nota con `load_by_id`.
2. Preserva el frontmatter original, reemplaza solo el contenido.
3. Reescribe el fichero.
4. Devuelve la `Note` actualizada.

### T2.2 — `FixedSizeChunker` (`src/adapters/chunkers/fixed_size.py`)
Constructor: `chunk_size: int = 512`, `chunk_overlap: int = 50` (caracteres).

**`chunk(note: Note) -> list[Chunk]`**
1. Contenido vacío → `[]`.
2. Divide `note.content` en fragmentos de `chunk_size` con solapamiento `chunk_overlap`.
3. Cada `Chunk`: `id=f"{note.id}_{index}"`, `note_id=note.id`,
   `strategy=ChunkStrategy.FIXED_SIZE`, `index`, `heading=None`,
   `metadata={"tags": note.tags, "note_type": note.note_type.value, "path": note.path}`.
4. Nota que cabe en un chunk → un único `Chunk`.
5. **Descartar/fusionar** fragmentos con `content.strip()` < 10 chars (invariante de `Chunk`).
   La lógica de split se expone como **función de módulo reutilizable** (la usará también
   el `BacklinkAwareChunker`): *no herencia*.

### T2.3 — `MarkdownHeaderChunker` (`src/adapters/chunkers/markdown_header.py`)
Constructor: sin parámetros.

**`chunk(note: Note) -> list[Chunk]`**
1. Contenido vacío → `[]`.
2. Divide por cabeceras `##` / `###` (regex sobre líneas que empiezan por `## ` o `### `).
3. Texto antes de la primera cabecera → chunk con `heading=None`.
4. Cada sección → chunk con `heading` = texto de la cabecera (sin `#`).
5. Mismo formato de `id`/`note_id`/`strategy`/`metadata` que `FixedSizeChunker`
   (`strategy=ChunkStrategy.MARKDOWN_HEADER`).
6. Sin cabeceras → un único chunk con toda la nota.
7. Secciones con `content.strip()` < 10 chars se **fusionan** con la sección siguiente
   (con `logger.debug`), para no romper la invariante de `Chunk`.

### T2.4 — `BacklinkAwareChunker` (`src/adapters/chunkers/backlink_aware.py`) — aportación original
Constructor: `loader: NoteLoader` (inyección de dependencia; **nunca** instancia
`ObsidianLoader` directamente).

**`chunk(note: Note) -> list[Chunk]`**
1. Contenido vacío → `[]`.
2. Parte del contenido de la nota principal.
3. Para cada backlink en `note.backlinks`:
   - Si `loader.exists(backlink_id)` → `loader.load_by_id(backlink_id)`.
   - Añade contexto: `"\n\n--- Nota enlazada: {linked.title} ---\n{linked.content[:200]}"`
     (corte en límite de palabra).
4. Resultado: **un único chunk enriquecido** (`strategy=ChunkStrategy.BACKLINK_AWARE`).
5. Si el resultado supera **2000 caracteres**, trocear con la **función de split
   compartida** de `FixedSizeChunker` (reutilización, no herencia).
6. `metadata` incluye: `tags`, `note_type`, `path`, y `linked_notes: [ids enlazadas]`.

---

## 4. Tests

### T2.5 — `tests/unit/test_obsidian_loader.py` (fixture `tmp_vault`)
- `test_obsidian_loader_load_all_returns_all_notes_in_vault`
- `test_obsidian_loader_load_all_parses_frontmatter_correctly`
- `test_obsidian_loader_load_all_extracts_backlinks`
- `test_obsidian_loader_load_all_extracts_aliased_backlinks`
- `test_obsidian_loader_load_by_id_returns_correct_note`
- `test_obsidian_loader_load_by_id_nonexistent_raises_not_found`
- `test_obsidian_loader_exists_returns_true_for_existing_note`
- `test_obsidian_loader_exists_returns_false_for_missing_note`
- `test_obsidian_loader_create_writes_file_with_frontmatter`
- `test_obsidian_loader_create_existing_file_raises_write_error`
- `test_obsidian_loader_update_preserves_frontmatter`
- `test_obsidian_loader_update_nonexistent_raises_not_found`
- `test_obsidian_loader_load_all_skips_non_md_files`
- `test_obsidian_loader_load_all_handles_empty_note`

> La fixture `tmp_vault` existe en `conftest.py` pero sus notas usan `# H1` y no traen
> `type:` en el frontmatter. Habrá que **ampliarla** (o añadir notas) para cubrir
> `note_type`, alias de backlinks y nota vacía.

### T2.6 — `tests/unit/test_chunkers.py`
- `test_fixed_size_chunker_splits_long_content`
- `test_fixed_size_chunker_single_chunk_for_short_content`
- `test_fixed_size_chunker_empty_note_returns_empty_list`
- `test_fixed_size_chunker_overlap_creates_overlapping_content`
- `test_fixed_size_chunker_chunk_ids_are_sequential`
- `test_fixed_size_chunker_metadata_includes_tags`
- `test_markdown_header_chunker_splits_by_headings`
- `test_markdown_header_chunker_preserves_heading_text`
- `test_markdown_header_chunker_no_headings_returns_single_chunk`
- `test_markdown_header_chunker_text_before_first_heading`
- `test_markdown_header_chunker_empty_note_returns_empty_list`
- `test_backlink_aware_chunker_enriches_with_linked_notes`
- `test_backlink_aware_chunker_ignores_missing_backlinks`
- `test_backlink_aware_chunker_empty_note_returns_empty_list`
- `test_backlink_aware_chunker_long_result_is_split`
- `test_all_chunkers_set_correct_strategy_enum`

> `BacklinkAwareChunker`: mockear `NoteLoader` con `spec=` (sin acceso real a ficheros),
> según la skill `testing-strategy`. Patrón AAA en todos los tests.

---

## 5. Análisis previos (skill `critical-task-planning`)

### Análisis previo: BacklinkAwareChunker (aportación original del TFM)
**Aspecto crítico**: enriquecer con notas enlazadas sin (a) recursión infinita en
ciclos `A↔B`, (b) reventar el contexto, ni (c) acoplar el chunker al `ObsidianLoader`.
**Opciones**: 1) enriquecer **1 nivel**, 200 chars por backlink (lo que dice la fase);
2) expansión recursiva multi-nivel del subgrafo (más potente pero con ciclos, coste y
peor reproducibilidad en la evaluación).
**Decisión**: Opción 1 — reproducible para Precision@K/MRR; la inyección de `NoteLoader`
+ `exists()` antes de `load_by_id()` mantiene el hexágono limpio. Multi-nivel queda
como trabajo futuro en la memoria.
**Riesgo aceptado**: 200 chars puede cortar a media frase y meter ruido. Mitigación:
cortar en límite de palabra, prefijar `--- Nota enlazada: {title} ---` para trazabilidad,
y trocear con la función de split de `FixedSizeChunker` si se superan 2000 chars.

### Análisis previo: chunks degenerados (< 10 caracteres)
**Aspecto crítico**: `Chunk.__post_init__` lanza `ValueError` si `content` no vacío tiene
< 10 chars; markdown (sección casi vacía) y el remanente de fixed pueden producirlos →
la ingesta petaría con datos reales.
**Opciones**: 1) relajar la validación del dominio (debilita la entidad, toca Fase 1);
2) que cada chunker descarte/fusione fragmentos con `content.strip()` < 10 chars.
**Decisión**: Opción 2 — la regla de 10 chars es invariante válida; el adaptador se
adapta. Cero cambios extra en la entidad.
**Riesgo aceptado**: perder texto muy corto entre cabeceras. Mitigación: fusionarlo con
la sección siguiente y `logger.debug`.

### Análisis previo: ID de Chunk
Decisión ya registrada en `critical-task-planning.md` (ejemplo del propio skill):
`f"{note_id}_{index}"` + borrado previo por nota en reindexación. En Fase 2 solo se
genera el ID con ese formato; el `delete_by_note_id` (en `IVectorStore`) se cablea en Fase 3.

---

## 6. Orden de ejecución y gates de verificación

```
0. pip install python-frontmatter  →  crear requirements.txt
1. Refactor src/domain/models.py + src/domain/ports.py
   → reescribir tests/conftest.py + tests/unit/test_models.py
   → GATE: pytest tests/unit/test_models.py -v  (debe quedar verde)
2. T2.1 ObsidianLoader  +  T2.5 tests
   → GATE: pytest tests/unit/test_obsidian_loader.py -v
3. T2.2 FixedSizeChunker (+ función de split compartida)
   T2.3 MarkdownHeaderChunker
   T2.4 BacklinkAwareChunker
   + T2.6 tests
   → GATE: pytest tests/unit/test_chunkers.py -v
4. Sincronización de documentación:
   - docs/error-log.md (deriva spec ↔ dominio, con la alternativa descartada)
   - tasks/fase-2-ingesta.md (a lo realmente construido)
   - CLAUDE.md (nombres de puertos/entidades nuevos)
5. GATE final: pytest tests/unit/ -v  +  ruff check src/  +  ruff format src/
```

---

## 7. Criterio de completado

- [x] `python-frontmatter` instalado y en `requirements.txt`.
- [x] Dominio refactorizado; `pytest tests/unit/test_models.py` en verde.
- [x] `ObsidianLoader` carga un vault real correctamente (frontmatter, tags,
      `note_type`, backlinks con alias, notas vacías).
- [x] Los tres chunkers producen `Chunk` con IDs únicos, `strategy` correcto y
      metadata correcta; ninguno viola la invariante de 10 chars.
- [x] `BacklinkAwareChunker` recibe `NoteLoader` por inyección; sin imports cruzados
      entre adaptadores; reutiliza la función de split (no herencia).
- [x] Todos los tests pasan: `pytest tests/unit/ -v`.
- [x] `ruff check src/` y `ruff format src/` limpios.
- [ ] `docs/error-log.md`, `tasks/fase-2-ingesta.md` y `CLAUDE.md` sincronizados.

---

## 8. Reglas de implementación (recordatorio)

- `ObsidianLoader` solo importa `frontmatter` como dependencia externa.
- Los chunkers solo importan de `src.domain.*`.
- `BacklinkAwareChunker` recibe `NoteLoader` por constructor; nunca instancia
  `ObsidianLoader`.
- Todas las excepciones externas se traducen a excepciones de dominio.
- `logger = logging.getLogger(__name__)` por módulo; nunca `print()`.
- Python 3.11+, type hints completos, docstrings Google-style, límite 80 chars.
- Tests: nomenclatura `test_<clase>_<método>_<resultado>`, patrón AAA, mocks con `spec=`.

---

## 9. TODOs por funcionalidad

Lista de tareas agrupadas por funcionalidad. Cada bloque es independiente y se
puede abordar/commitear por separado. El orden recomendado de ejecución está en
la sección 6.

### 🔧 Setup y dependencias
- [x] Instalar `python-frontmatter` en el entorno virtual.
- [x] Crear `requirements.txt` con: `python-frontmatter`, `langchain-ollama`,
      `langchain-core`, `pytest`, `ruff`.

### 🧩 Dominio (refactor)
- [x] `Note`: renombrar `note_id` → `id`; añadir `path: str` y
      `note_type: NoteType = NoteType.OTHER`; actualizar `__post_init__`,
      `with_tags()` y properties.
- [x] `Chunk`: renombrar `chunk_id` → `id`, `position` → `index`;
      cambiar `strategy: str` → `strategy: ChunkStrategy`; añadir
      `heading: Optional[str] = None`; actualizar `__post_init__`.
- [x] `ChunkStrategy`: renombrar members a `FIXED_SIZE` / `MARKDOWN_HEADER` /
      `BACKLINK_AWARE` manteniendo los `.value` (`fixed`/`markdown`/`backlink`).
- [x] `ports.py`: renombrar `IVaultReader`→`NoteLoader`,
      `IVaultWriter`→`NoteWriter`, `IBaseChunker`→`BaseChunker`.
- [x] `NoteLoader`: `load()`→`load_by_id()`; añadir `exists()`; conservar
      `load_all()` y `load_by_tags()`.
- [x] `NoteWriter`: `create(title, content, tags)` y `update(note_id, content)`;
      omitir `delete()`.
- [x] `BaseChunker.chunk_many()`: sustituir `except: pass` por logging con
      `exc_info=True` + traducción a `ChunkingError`.

### 📥 ObsidianLoader (adaptador de ingesta)
- [x] `load_all()`: recorrido recursivo, parsing de frontmatter, `title`/`tags`/
      `note_type`/`created_at`/`updated_at`, backlinks con alias, `id` relativo,
      `path` absoluto, normalización de notas vacías + warning.
- [x] `load_by_id()`: resolución de ruta + `NoteNotFoundError` si no existe.
- [x] `exists()`: comprobación de existencia en disco.
- [x] `create()`: escritura en `00-inbox/` + `VaultWriteError` si ya existe.
- [x] `update()`: preserva frontmatter, reemplaza contenido.

### ✂️ Chunkers
- [x] Función de split compartida a nivel de módulo (reutilizable, no herencia).
- [x] `FixedSizeChunker`: split con solapamiento, descarte/fusión de fragmentos
      < 10 chars, metadata correcta, `strategy=FIXED_SIZE`.
- [x] `MarkdownHeaderChunker`: split por `##`/`###`, `heading`, texto pre-cabecera,
      fusión de secciones < 10 chars, `strategy=MARKDOWN_HEADER`.
- [x] `BacklinkAwareChunker`: inyección de `NoteLoader`, enriquecimiento 1 nivel
      (200 chars/backlink, corte en palabra), troceo > 2000 chars con la función
      compartida, `linked_notes` en metadata, `strategy=BACKLINK_AWARE`.
- [x] `src/adapters/chunkers/base.py`: re-exporta `BaseChunker` del dominio.

### 🧪 Tests
- [x] Reescribir `tests/conftest.py` y `tests/unit/test_models.py` a los nombres
      nuevos; ampliar `tmp_vault` (note_type, alias de backlinks, nota vacía).
- [x] `tests/unit/test_obsidian_loader.py` (14 tests de T2.5).
- [x] `tests/unit/test_chunkers.py` (16 tests de T2.6, `NoteLoader` mockeado con `spec=`).

### 📚 Documentación y sincronización
- [x] `docs/error-log.md`: entrada de la deriva spec ↔ dominio (con la alternativa
      descartada y por qué).
- [x] `tasks/fase-2-ingesta.md`: actualizar a lo realmente construido.
- [x] `CLAUDE.md`: actualizar nombres de puertos/entidades.

### ✅ Verificación final
- [x] `pytest tests/unit/ -v` en verde.
- [x] `ruff check src/` y `ruff format src/` limpios.
