# Error Log — Obsidian RAG Agent

Registro de errores de diseño/implementación detectados durante el
desarrollo asistido por IA, y cómo se corrigieron. Material de apoyo
para la sección de metodología del TFM.

---

## [2026-06-13] Deriva de nombres entre Fase 1 (dominio) y la spec de Fase 2

**Fase**: fase-2-ingesta.md
**Categoría**: arquitectura

### Qué se hizo mal

El dominio implementado en Fase 1 y mergeado en PR #1 y #2 usaba convenciones
de nombres distintas a las que la spec de Fase 2 (`tasks/fase-2-ingesta.md`)
consideraba canónicas:

| Entidad | Fase 1 (implementado) | Fase 2 (spec) |
|---|---|---|
| `Note.note_id` | `note_id: str` | `id: str` |
| `Note` | sin `path`, sin `note_type` | `path: str`, `note_type: NoteType` |
| `Chunk.chunk_id` | `chunk_id: str` | `id: str` |
| `Chunk.position` | `position: int` | `index: int` |
| `Chunk.strategy` | `strategy: str` | `strategy: ChunkStrategy` (enum) |
| `ChunkStrategy.FIXED` | `FIXED` | `FIXED_SIZE` |
| Puerto de lectura | `IVaultReader` | `NoteLoader` |
| Puerto de escritura | `IVaultWriter` | `NoteWriter` |
| Puerto de chunking | `IBaseChunker` | `BaseChunker` |

Además, `IVaultReader.load()` debía llamarse `load_by_id()` y faltaba el método
`exists()`. `IVaultWriter` tenía una firma distinta y un método `delete()` que
la spec no pedía.

### Por qué era un error

La divergencia entre spec y dominio impedía implementar Fase 2 directamente:
los adaptadores (`ObsidianLoader`, chunkers) habrían usado los nombres de la
spec mientras el dominio y los tests de Fase 1 seguían con los nombres viejos,
rompiendo la cohesión de la capa interna del hexágono y produciendo tests
inconsistentes.

### Cómo se corrigió

Se tomó la spec como fuente de verdad y se ejecutó un refactor completo del
dominio antes de empezar a implementar los adaptadores:

1. `Note`: `note_id` → `id`; campos `path: str = ""` y
   `note_type: NoteType = NoteType.OTHER` añadidos.
2. `Chunk`: `chunk_id` → `id`, `position` → `index`,
   `strategy: str` → `strategy: ChunkStrategy`, `heading: Optional[str]` añadido.
3. `ChunkStrategy`: `FIXED`→`FIXED_SIZE`, `MARKDOWN`→`MARKDOWN_HEADER`,
   `BACKLINK`→`BACKLINK_AWARE` (conservando los `.value` para no romper el `.env`).
4. `ports.py`: puertos renombrados; `load_by_id()` y `exists()` añadidos;
   `NoteWriter` con `create()`/`update()` retornando `Note`.
5. `src/domain/__init__.py` actualizado con los nuevos nombres.
6. `tests/conftest.py` y `tests/unit/test_models.py` reescritos a los nombres
   nuevos; `tmp_vault` ampliado con `type:`, alias de backlinks y nota vacía.

**Alternativa descartada**: mantener los nombres de Fase 1 en el dominio y
añadir mapeo en los adaptadores. Se descartó porque duplicaría conceptos en la
capa interna y haría los tests de integración más frágiles.

### Cómo evitarlo en el futuro

Antes de cerrar una fase, revisar la spec de la fase siguiente y verificar que
los nombres de entidades, ports y campos del dominio son consistentes. Si hay
divergencia, resolverla en el mismo PR de la fase anterior.

---

## [2026-06-13] Errores de lint (I001, F401) al resolver conflictos de merge

**Fase**: fase-2-ingesta.md
**Categoría**: otro

### Qué se hizo mal

Al resolver los conflictos del merge de `develop` en `feature/domain-refactor`,
el bloque de imports de `src/domain/models.py` quedó desordenado (regla `I001`
de ruff) y `ChunkStrategy` se importó en `ports.py` sin usarse (`F401`).

### Por qué era un error

El action de lint de CI falló al hacer push, bloqueando el pipeline y
requiriendo un commit adicional de corrección.

### Cómo se corrigió

```bash
ruff check src/ --fix   # corrige I001 y F401 automáticamente
ruff format src/
```

### Cómo evitarlo en el futuro

Tras cualquier resolución de conflictos, ejecutar `ruff check src/ --fix &&
ruff format src/` localmente antes de hacer push. Añadirlo como paso del
checklist de merge.
