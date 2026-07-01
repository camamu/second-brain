# Fase 1 — Dominio: modelos y puertos

## Contexto

El dominio es el núcleo del sistema. No tiene dependencias externas — solo stdlib de Python. Define las entidades de datos (modelos) y los contratos que los adaptadores deben implementar (puertos).

**Ficheros a crear/modificar:**
- `src/domain/models.py` (ya existe — revisar y ajustar si es necesario)
- `src/domain/ports.py` (ya existe — revisar y ampliar la jerarquía de excepciones)
- `tests/conftest.py` (fixtures compartidos)
- `tests/unit/test_models.py`

---

## Tareas

### T1.1 — Revisar `src/domain/models.py`

El fichero ya contiene estas entidades. Verificar que todas tienen type hints completos y docstrings:

| Entidad | Propósito |
|---|---|
| `ChunkStrategy` | Enum: `FIXED_SIZE`, `MARKDOWN_HEADER`, `BACKLINK_AWARE` |
| `NoteType` | Enum: `NOTE`, `PROJECT`, `RESOURCE`, `CONCEPT`, `UNKNOWN` |
| `Note` | Nota de Obsidian con id, title, content, path, tags, backlinks, note_type, created_at, updated_at |
| `Chunk` | Fragmento de nota con id, note_id, content, strategy, index, heading, metadata |
| `SearchResult` | Resultado de búsqueda con chunk, score, rank |
| `RetrievalQuery` | Query encapsulada con text, top_k, strategy |
| `EvaluationSample` | Pregunta anotada con query y relevant_note_ids |
| `EvaluationResult` | Resultados de una estrategia con precision_at_k y mrr_scores |

Properties calculadas que deben existir:
- `Note.word_count` → len(content.split())
- `Note.has_frontmatter_metadata` → bool
- `Chunk.char_count` → len(content)
- `SearchResult.note_id` → chunk.note_id
- `SearchResult.is_relevant` → score >= 0.7
- `EvaluationResult.mean_precision` → media de precision_at_k
- `EvaluationResult.mean_mrr` → media de mrr_scores
- `EvaluationResult.summary()` → string formateado

### T1.2 — Revisar y ampliar `src/domain/ports.py`

El fichero ya contiene las interfaces base. Verificar que existen todos estos puertos:

| Puerto | Métodos abstractos |
|---|---|
| `NoteLoader` | `load_all()`, `load_by_id(note_id)`, `exists(note_id)` |
| `NoteWriter` | `create(title, content, tags)`, `update(note_id, content)` |
| `BaseChunker` | `strategy` (property), `chunk(note)`, `chunk_many(notes)` (concreto) |
| `ChunkEmbedder` | `embed(text)`, `embed_many(texts)` |
| `VectorStore` | `add_chunks(chunks, embedder)`, `search(query, embedder)`, `delete_by_note(note_id)`, `count()` |
| `ConversationalLLM` | `generate(prompt, context)` |
| `EvaluationRepository` | `load_samples()`, `save_result(result)`, `load_results()` |

Ampliar la jerarquía de excepciones con una clase base común:

```python
class ObsidianRagError(Exception):
    """Base para todas las excepciones del dominio."""

class NoteNotFoundError(ObsidianRagError): ...
class ChunkingError(ObsidianRagError): ...
class EmbeddingError(ObsidianRagError): ...
class VectorStoreError(ObsidianRagError): ...
class VaultWriteError(ObsidianRagError): ...
```

Cada excepción debe llevar contexto (qué nota, qué operación, por qué falló).

### T1.3 — Crear fixtures en `tests/conftest.py`

Fixtures reutilizables para todas las fases de testing:

- `sample_note` → una Note con frontmatter completo, tags y backlinks
- `sample_note_empty` → una Note con content vacío
- `sample_note_no_frontmatter` → una Note sin tags ni fechas
- `sample_chunk` → un Chunk vinculado a sample_note
- `sample_search_result` → un SearchResult con score alto
- `sample_evaluation_sample` → un EvaluationSample con query y note_ids
- `tmp_vault` → un directorio temporal con 3-4 ficheros .md de prueba (usar `tmp_path`)

### T1.4 — Crear `tests/unit/test_models.py`

Tests unitarios para los modelos del dominio:

- `test_note_word_count_returns_correct_count`
- `test_note_has_frontmatter_metadata_true_with_tags`
- `test_note_has_frontmatter_metadata_false_without_data`
- `test_chunk_char_count_returns_content_length`
- `test_search_result_is_relevant_above_threshold`
- `test_search_result_is_relevant_below_threshold`
- `test_evaluation_result_mean_precision_with_data`
- `test_evaluation_result_mean_precision_empty_returns_zero`
- `test_evaluation_result_mean_mrr_with_data`
- `test_evaluation_result_summary_format`
- `test_chunk_strategy_values_match_env_strings`

---

## Reglas de implementación

- Estos ficheros NO importan nada externo (ni langchain, ni chromadb, ni nada de `src.adapters`).
- Todo es `@dataclass` con type hints completos.
- Docstrings en formato Google en todas las clases y métodos públicos.
- Los tests siguen el patrón AAA (Arrange / Act / Assert).
- Nombrado de tests: `test_<clase>_<método>_<resultado_esperado>`.

---

## Criterio de completado

- [x] models.py tiene las 8 entidades con todos sus campos y properties — nota: enums con valores cortos (`FIXED/MARKDOWN/BACKLINK`, `DOC/TODO/…`) en lugar de los especificados; `SearchResult` aplanada en lugar de compuesta
- [x] ports.py tiene los 7 puertos y las 5 excepciones de dominio — puertos con prefijo `I` (`IVaultReader`, `IEmbedder`…) en lugar de los nombres de la spec; excepciones implementadas
- [x] conftest.py tiene los 7 fixtures
- [x] test_models.py pasa con todos los tests en verde — 14 tests (3 adicionales sobre los 11 especificados)
- [x] `pytest tests/unit/test_models.py -v` sin errores
