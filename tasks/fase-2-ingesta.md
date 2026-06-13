# Fase 2 — Adaptadores de ingesta

> **Estado: COMPLETADA** (rama `feature/domain-refactor`).
> Incluye refactor del dominio de Fase 1 para alinear nombres con esta spec.
> Ver `docs/error-log.md` para la deriva detectada y cómo se resolvió.

## Contexto

Esta fase implementa la lectura del vault de Obsidian y las tres estrategias de chunking que se compararán en la evaluación del TFM.

**Ficheros a crear:**
- `src/adapters/obsidian_loader.py`
- `src/adapters/chunkers/base.py` (re-exporta BaseChunker del dominio)
- `src/adapters/chunkers/fixed_size.py`
- `src/adapters/chunkers/markdown_header.py`
- `src/adapters/chunkers/backlink_aware.py`
- `tests/unit/test_obsidian_loader.py`
- `tests/unit/test_chunkers.py`

**Dependencias de dominio:**
- `Note`, `Chunk`, `ChunkStrategy`, `NoteType` de `src.domain.models`
- `NoteLoader`, `NoteWriter`, `BaseChunker` de `src.domain.ports`
- `NoteNotFoundError`, `ChunkingError`, `VaultWriteError` de `src.domain.ports`

---

## Tareas

### T2.1 — Implementar `ObsidianLoader` (NoteLoader + NoteWriter)

Fichero: `src/adapters/obsidian_loader.py`

Implementa los puertos `NoteLoader` y `NoteWriter`. Recibe `vault_path: str` en el constructor.

**`load_all() -> list[Note]`**:
1. Recorre recursivamente `vault_path` buscando ficheros `*.md`.
2. Para cada fichero, usa `python-frontmatter` para separar YAML del contenido.
3. Extrae `title` del frontmatter o del nombre de fichero (sin extensión).
4. Extrae `tags` del frontmatter (campo `tags: [...]`).
5. Extrae `type` del frontmatter y mapea a `NoteType` enum.
6. Extrae `created` y `updated` del frontmatter como `datetime`.
7. Extrae backlinks con regex: busca todas las ocurrencias de `[[nombre]]` en el contenido y devuelve la lista de nombres. Los alias `[[nombre|alias]]` deben extraer solo `nombre`.
8. El `id` de cada nota es la ruta relativa desde `vault_path`, sin extensión `.md`. Ejemplo: `vault_path=/vault`, fichero `/vault/01-proyectos/tfm.md` → id = `01-proyectos/tfm`.
9. Notas vacías (content solo whitespace) se cargan pero con un `logger.warning`.

**`load_by_id(note_id: str) -> Note`**:
1. Calcula la ruta: `vault_path / note_id + ".md"`.
2. Si no existe, lanza `NoteNotFoundError(note_id)`.
3. Parsea igual que `load_all`.

**`exists(note_id: str) -> bool`**:
1. Comprueba si el fichero existe en disco.

**`create(title: str, content: str, tags: list[str]) -> Note`**:
1. Genera el path: `vault_path/00-inbox/{title_slug}.md`.
2. Escribe frontmatter YAML + contenido.
3. Si el fichero ya existe, lanza `VaultWriteError`.
4. Devuelve la Note creada.

**`update(note_id: str, content: str) -> Note`**:
1. Carga la nota actual con `load_by_id`.
2. Preserva el frontmatter original, reemplaza solo el contenido.
3. Escribe el fichero.
4. Devuelve la Note actualizada.

### T2.2 — Implementar `FixedSizeChunker`

Fichero: `src/adapters/chunkers/fixed_size.py`

Constructor: `chunk_size: int = 512`, `chunk_overlap: int = 50` (en caracteres).

**`chunk(note: Note) -> list[Chunk]`**:
1. Si el contenido está vacío, devuelve `[]`.
2. Divide `note.content` en fragmentos de `chunk_size` caracteres con solapamiento de `chunk_overlap`.
3. Cada chunk tiene:
   - `id`: `"{note.id}_{index}"`
   - `note_id`: `note.id`
   - `strategy`: `ChunkStrategy.FIXED_SIZE`
   - `index`: posición (0-based)
   - `metadata`: `{"tags": note.tags, "note_type": note.note_type.value, "path": note.path}`
4. Si la nota completa cabe en un solo chunk, devuelve un único Chunk.

### T2.3 — Implementar `MarkdownHeaderChunker`

Fichero: `src/adapters/chunkers/markdown_header.py`

Constructor: sin parámetros.

**`chunk(note: Note) -> list[Chunk]`**:
1. Si el contenido está vacío, devuelve `[]`.
2. Divide el contenido por cabeceras Markdown (`##`, `###`). Usa regex para detectar líneas que empiezan con `## ` o `### `.
3. El texto antes de la primera cabecera (si existe) es un chunk con `heading=None`.
4. Cada sección bajo una cabecera es un chunk con `heading` = texto de la cabecera (sin los `#`).
5. Misma estructura de `id`, `note_id`, `strategy`, `metadata` que el FixedSizeChunker.
6. Si la nota no tiene cabeceras, devuelve un único chunk con toda la nota.

### T2.4 — Implementar `BacklinkAwareChunker`

Fichero: `src/adapters/chunkers/backlink_aware.py`

Constructor: `loader: NoteLoader` (necesita acceso al vault para resolver backlinks).

**`chunk(note: Note) -> list[Chunk]`**:
1. Si el contenido está vacío, devuelve `[]`.
2. Comienza con el contenido de la nota principal.
3. Para cada backlink en `note.backlinks`:
   - Si el `loader.exists(backlink_id)` es True, carga la nota enlazada.
   - Añade un resumen de la nota enlazada al contenido del chunk: `"\n\n--- Nota enlazada: {linked.title} ---\n{linked.content[:200]}"` (primeros 200 caracteres como contexto).
4. El resultado es un único chunk enriquecido con contexto de las notas relacionadas.
5. Si el chunk resultante excede 2000 caracteres, dividirlo con la misma lógica de FixedSizeChunker (reutilizar lógica, no herencia).
6. `metadata` incluye: tags, note_type, path, y `linked_notes: [ids de notas enlazadas]`.

Este chunker es **la aportación original del TFM** — explota la estructura de grafo de Obsidian que los otros chunkers ignoran.

---

## Tests

### T2.5 — `tests/unit/test_obsidian_loader.py`

Usa la fixture `tmp_vault` (directorio temporal con ficheros .md de prueba).

Tests obligatorios:
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

### T2.6 — `tests/unit/test_chunkers.py`

Tests obligatorios:
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

Para el BacklinkAwareChunker, mockear el `NoteLoader` (no acceso real a ficheros).

---

## Reglas de implementación

- ObsidianLoader importa `frontmatter` (python-frontmatter) — es su única dependencia externa.
- Los chunkers solo importan de `src.domain.*`.
- BacklinkAwareChunker recibe un `NoteLoader` por constructor (inyección de dependencia), nunca instancia ObsidianLoader directamente.
- Todas las excepciones externas (FileNotFoundError, etc.) se traducen a excepciones de dominio.
- Logging con `logger = logging.getLogger(__name__)` en cada módulo.

---

## Criterio de completado

- [x] ObsidianLoader carga un vault real correctamente
- [x] Los tres chunkers producen Chunks con IDs únicos y metadata correcta
- [x] Todos los tests pasan: `pytest tests/unit/test_obsidian_loader.py tests/unit/test_chunkers.py -v`
- [x] Sin imports cruzados entre adaptadores

## Notas de implementación (desviaciones respecto a la spec)

- El dominio de Fase 1 requirió un refactor previo para alinear nombres
  (`note_id`→`id`, `chunk_id`→`id`, `IVaultReader`→`NoteLoader`, etc.).
- `Note` recibió dos campos nuevos: `path: str = ""` y `note_type: NoteType = NoteType.OTHER`.
- `NoteLoader` recibió el método abstracto `exists(note_id: str) -> bool`.
- La función `split_text()` en `fixed_size.py` es reutilizada por `BacklinkAwareChunker`
  (no herencia, importación directa de módulo).
- 44 tests unitarios en total (14 modelos + 14 loader + 16 chunkers), todos en verde.
- `ruff check` y `ruff format` limpios.
