# Implementation Plan — Fase 3: Vector store y adaptadores LLM

> Documento de planificación previo a la implementación (skill
> `critical-task-planning`). Registro persistente y versionado del plan de la
> Fase 3. El tracking en vivo del harness, si se usa, es efímero; este fichero es
> la fuente de verdad del plan.

## 1. Contexto y decisión de fondo

La Fase 3 implementa la capa de persistencia vectorial (ChromaDB), los adaptadores
LLM/embedder para los dos entornos (local Ollama / producción Groq+HuggingFace) y la
factory (*composition root*) en `infrastructure`. Es lo que falta para poder ingestar
el vault y hacer retrieval (hoy `data/chroma_db/` está vacío).

### Deriva spec ↔ dominio (recurrencia del error-log)

La spec `tasks/fase-3-vectorstore-llm.md` usa nombres y firmas que **no coinciden** con
el dominio mergeado en Fase 2. Igual que ocurrió entre Fase 1→2, hay que resolver la
divergencia *antes* de implementar (lección de `docs/error-log.md`).

Divergencias detectadas:

| Spec Fase 3 | Dominio real (`ports.py` / `models.py`) |
|---|---|
| `ChunkEmbedder` | `IEmbedder` |
| `VectorStore` | `IVectorStore` |
| `ConversationalLLM` | `ILLMChat` |
| `add_chunks(chunks, embedder)` | `add_chunks(chunks)` — sin embedder |
| `search(query, embedder)` | `search(query)` — sin embedder |
| `delete_by_note(id)` | `delete_by_note_id(id)` |
| `count()` | `get_note_ids()` |
| `generate(prompt, ctx)` | `respond(prompt, ctx)` |
| ctor embedder `model, base_url` | `__init__(model_name)` |
| `query.text` | `RetrievalQuery.query` (el campo se llama `query`) |
| dir `vector_store/` | dir real `vector_stores/` (plural, ya existe) |

### Decisiones cerradas (con el usuario)

1. **Fuente de verdad → la spec.** Se refactoriza el dominio (puertos) a los nombres de
   la spec: `IEmbedder→ChunkEmbedder`, `IVectorStore→VectorStore`,
   `ILLMChat→ConversationalLLM`.
2. **Embeddings → inyección en constructor** (NO el `add_chunks(chunks, embedder)` de la
   spec). El `VectorStore` recibe el embedder en su `__init__`; `add_chunks`/`search`
   quedan sin parámetro embedder. Mantiene los métodos del puerto limpios y desacopla el
   puerto de ChromaDB.
3. **`search()` con `strategy=None` → estrategia por defecto del store**, inyectada en el
   constructor desde `CHUNKER_STRATEGY`.

Verificado: los tres puertos a renombrar solo aparecen en `src/domain/ports.py` y
`src/domain/__init__.py`; ningún adapter ni test los importa → refactor contenido y
seguro. Todas las dependencias ya están instaladas (`chromadb==0.6.3`,
`langchain-ollama`, `langchain-groq`, `huggingface_hub`, `python-dotenv`).

## 2. Mapa de cambios

### Refactor del dominio (`src/domain/ports.py` + `src/domain/__init__.py`)

| Antes (puerto actual) | Después (spec) |
|---|---|
| `class IEmbedder` | `class ChunkEmbedder` |
| `class IVectorStore` | `class VectorStore` |
| `class ILLMChat` | `class ConversationalLLM` |
| `IVectorStore.delete_by_note_id(id)` | `VectorStore.delete_by_note(id)` |
| `IVectorStore.get_note_ids() -> List[str]` | `VectorStore.count() -> int` |
| `ILLMChat.respond(prompt, context)` | `ConversationalLLM.generate(prompt, context)` |

- Quitar los `@abstractmethod __init__` de los tres puertos refactorizados: cada adapter
  tiene un constructor distinto (Ollama `model, base_url`; HF `model_name`; `VectorStore`
  `persist_path, embedder, default_strategy`). El puerto fija comportamiento, no constructor.
- `ChunkEmbedder`: `embed(text) -> list[float]`, `embed_many(texts) -> list[list[float]]`.
- `VectorStore`: `add_chunks(chunks) -> None`, `search(query) -> list[SearchResult]`,
  `delete_by_note(note_id) -> None`, `count() -> int`.
- `ConversationalLLM`: `generate(prompt: str, context: List[SearchResult]) -> str`.
- Añadir excepción `ConfigError(ObsidianRagError)` (skill `config-management`).
- Actualizar imports/`__all__` en `src/domain/__init__.py` y docstring de cabecera de `ports.py`.

### Ficheros nuevos

| Fichero | Contenido |
|---|---|
| `src/adapters/vector_stores/chroma_store.py` | `ChromaVectorStore(VectorStore)` |
| `src/adapters/llm/ollama_adapter.py` | `OllamaEmbedderAdapter(ChunkEmbedder)` + `OllamaLLMAdapter(ConversationalLLM)` |
| `src/adapters/llm/groq_adapter.py` | `HuggingFaceEmbedderAdapter(ChunkEmbedder)` + `GroqLLMAdapter(ConversationalLLM)` |
| `src/infrastructure/config.py` | factory / composition root |
| `tests/unit/test_chroma_store.py` | tests unitarios con `FakeEmbedder` |
| `tests/unit/test_config.py` | tests de la factory (mock de env) |
| `tests/integration/test_ollama_integration.py` | tests `@pytest.mark.integration` |

> Se usa el directorio existente `src/adapters/vector_stores/` (plural, ya creado y
> documentado en CLAUDE.md), no el `vector_store/` singular de la spec. Embedders y LLM se
> agrupan por proveedor en `llm/` según la spec; el dir vacío `embedders/` queda sin usar
> (limpieza fuera de alcance).

## 3. Especificación de componentes

### `ChromaVectorStore(VectorStore)`

- `__init__(self, persist_path: str, embedder: ChunkEmbedder, default_strategy: ChunkStrategy, collection_prefix: str = "obsidian_rag", client=None)`.
  - `client` opcional para tests (in-memory). Default: `chromadb.PersistentClient(path=persist_path)`.
- Colección por estrategia: nombre `f"{collection_prefix}_{strategy.value}"`. Crear/obtener
  con `metadata={"hnsw:space": "cosine"}`.
- `add_chunks(chunks)`:
  1. Agrupar por `chunk.strategy` (defensivo).
  2. Por grupo: `get_or_create_collection`, `embedder.embed_many([c.content ...])`.
  3. `collection.upsert(ids, embeddings, documents, metadatas)`.
  4. metadatas: `note_id`, `heading` (o `""`), `strategy` (=`.value`), `index`,
     `token_count` + aplanar `chunk.metadata` (ChromaDB solo acepta str/int/float/bool;
     listas como `tags` → join por comas). Fallos → `VectorStoreError`.
- `search(query)`:
  1. Resolver estrategia: `query.strategy` (str) → `ChunkStrategy(query.strategy)`; si
     `None` → `self._default_strategy`. Valor inválido → `VectorStoreError`.
  2. `embedder.embed(query.query)` → `collection.query(query_embeddings=[v], n_results=query.top_k)`.
  3. Mapear a `SearchResult`: `score = max(0.0, min(1.0, 1 - distance))`, filtrar por
     `query.min_score`, ordenar desc, `rank` 1-based.
  4. Colección inexistente / vacía → devolver `[]` (no error).
- `delete_by_note(note_id)`: en cada colección existente, `collection.delete(where={"note_id": note_id})`.
- `count()`: suma de `collection.count()` de todas las colecciones del prefijo.

### `ollama_adapter.py`

- `OllamaEmbedderAdapter`: ctor `model="nomic-embed-text", base_url="http://localhost:11434"`;
  envuelve `langchain_ollama.OllamaEmbeddings`. `embed`→`embed_query`, `embed_many`→`embed_documents`.
  Errores → `EmbeddingError`.
- `OllamaLLMAdapter`: ctor `model="llama3.2", base_url=...`; envuelve `langchain_ollama.OllamaLLM`.
  `generate` formatea el prompt RAG (template de la spec) con `context` (lista de
  `SearchResult` → texto con `[note_id]` para citación) y llama a `llm.invoke`.

### `groq_adapter.py`

- `HuggingFaceEmbedderAdapter`: ctor `model_name="nomic-ai/nomic-embed-text-v1"`;
  envuelve `langchain_huggingface.HuggingFaceEmbeddings`. Misma interfaz.
- `GroqLLMAdapter`: ctor `api_key: str, model="llama-3.2-90b-text-preview"`;
  envuelve `langchain_groq.ChatGroq`. Mismo template que Ollama.

### `infrastructure/config.py` (composition root)

- `load_dotenv()` a nivel de módulo; único fichero con `os.getenv()`.
- Imports de adaptadores **lazy** (dentro de cada función) para no exigir Groq en local.
- Helpers seguros `_get_bool`, `_require` (lanza `ConfigError` si falta var obligatoria).
- Factories: `get_llm()`, `get_embedder()`, `get_vector_store()` (inyecta `get_embedder()` +
  estrategia de `CHUNKER_STRATEGY`), `get_note_loader()`, `get_note_writer()`,
  `get_chunker(strategy)`, `get_chunker_from_env()`.
- `BacklinkAwareChunker` recibe `get_note_loader()`.
- Mapeo `CHUNKER_STRATEGY` → `ChunkStrategy(value)` (valores `fixed|markdown|backlink`).
- Env: `USE_LOCAL`, `VAULT_PATH`, `OLLAMA_BASE_URL`, `GROQ_API_KEY`, `CHUNKER_STRATEGY`,
  `CHROMA_PERSIST_DIR` (default `data/chroma_db`).

## 4. Tests

### `tests/unit/test_chroma_store.py`
- `FakeEmbedder(ChunkEmbedder)`: vector determinista por `hash(text)` con `random.seed`
  fijo, dimensión fija (p.ej. 8). Sin red.
- Inyectar `client=chromadb.Client()` (in-memory) en el constructor.
- Tests: `test_chroma_store_add_chunks_persists_documents`,
  `test_chroma_store_add_chunks_upserts_duplicates`,
  `test_chroma_store_search_returns_ranked_results`,
  `test_chroma_store_search_respects_top_k`,
  `test_chroma_store_search_uses_correct_collection_per_strategy`,
  `test_chroma_store_delete_by_note_removes_all_chunks`,
  `test_chroma_store_count_returns_total_across_collections`.

### `tests/unit/test_config.py`
- `monkeypatch.setenv` para `USE_LOCAL`; verificar tipos con `isinstance`:
  `test_get_llm_returns_ollama_when_local`, `test_get_llm_returns_groq_when_not_local`,
  `test_get_embedder_returns_ollama_when_local`,
  `test_get_chunker_returns_correct_type_for_each_strategy`.
- Groq: mock de la clase para no instanciar cliente real / pedir API key.

### `tests/integration/test_ollama_integration.py` (`@pytest.mark.integration`)
- `test_ollama_embedder_returns_vector_of_expected_dimension`,
  `test_ollama_llm_generates_nonempty_response`,
  `test_full_pipeline_ingest_and_search` (nota → chunk → embed → store → search).

Naming `test_<class>_<method>_<expected>`, patrón AAA, mockear puertos con `spec=`
(skill `testing-strategy`).

## 5. Bloques "Análisis previo" (puntos arriesgados)

### Análisis previo: normalización de score ChromaDB → SearchResult
**Aspecto crítico**: `SearchResult.__post_init__` exige `0.0 ≤ score ≤ 1.0`; ChromaDB
devuelve *distancias* y con la métrica por defecto (L2) el rango no está acotado a [0,1].
**Opciones consideradas**:
1. Métrica por defecto + normalización ad-hoc — frágil, puede salirse de [0,1].
2. Crear colecciones con `hnsw:space=cosine` → distancia coseno ∈ [0,2], `score = 1 - distance`
   con clamp a [0,1].
**Decisión**: Opción 2 — el clamp evita romper la validación por redondeo y el coseno es el
estándar para embeddings de texto.
**Riesgo aceptado**: si una colección se creó con otra métrica, el espacio no cambia.
Mitigación: prefijo de colección fijo; borrar `data/chroma_db/` si se cambia la métrica.

### Análisis previo: inyección del embedder en el VectorStore
**Aspecto crítico**: el puerto no pasa embedder y `Chunk` no tiene campo embedding.
**Opciones consideradas**:
1. Pasar embedder por método (`add_chunks(chunks, embedder)`) — sigue la spec pero ensucia
   el puerto y obliga al llamador a tener el embedder.
2. Inyección en constructor — el `VectorStore` posee el embedder; métodos limpios.
**Decisión**: Opción 2 (acordada con el usuario) — desacopla el puerto de ChromaDB.
**Riesgo aceptado**: una instancia de store queda atada a un embedder/estrategia; aceptable
para el alcance del TFM (una instancia por colección/modelo).

### Colección por estrategia
Decisión ya registrada en `critical-task-planning.md`: *"Estrategia de chunking activa →
una colección ChromaDB por estrategia (elegido)"*. Permite los 3 índices en paralelo para
la evaluación comparativa de Fase 7.

## 6. Orden de ejecución (con gates)

1. (Hecho) Crear este `implementation-plan.md`.
2. Refactor dominio (`ports.py` + `__init__.py`) → **gate**: `pytest tests/unit -q` (44 verdes).
3. `ChromaVectorStore` + `test_chroma_store.py` → **gate**: `pytest tests/unit/test_chroma_store.py -v`.
4. `ollama_adapter.py` y `groq_adapter.py`.
5. `config.py` + `test_config.py` → **gate**: `pytest tests/unit/test_config.py -v`.
6. `test_ollama_integration.py` → **gate** (requiere Ollama): `pytest tests/integration -v -m integration`.
7. **gate final**: `ruff check src/ tests/ --fix && ruff format src/ tests/` y `pytest tests/unit -q`.
8. Sincronizar docs: `CLAUDE.md` (estado/adapters Fase 3), `CHROMA_PERSIST_DIR`,
   criterios en `tasks/fase-3-vectorstore-llm.md`, y entrada en `docs/error-log.md` por la
   recurrencia de la deriva spec↔dominio (Fase 2→3) y la decisión de refactorizar a la spec.

## 7. Criterio de completado

- [x] Dominio refactorizado; los 44 tests previos siguen verdes.
- [x] ChromaDB persiste y recupera chunks (colección por estrategia, score normalizado).
- [x] Los dos adaptadores LLM/embedder implementan los puertos y traducen excepciones.
- [x] La factory devuelve el adapter correcto según `USE_LOCAL` (imports lazy).
- [x] `pytest tests/unit/test_chroma_store.py tests/unit/test_config.py -v` pasa.
- [ ] `pytest tests/integration/ -v -m integration` pasa (con Ollama arriba).
- [x] `ruff check` y `ruff format` limpios; docs sincronizadas.

## 8. TODOs por funcionalidad

### 🧩 Dominio (refactor a la spec)
- [x] Renombrar puertos `IEmbedder→ChunkEmbedder`, `IVectorStore→VectorStore`, `ILLMChat→ConversationalLLM`.
- [x] Renombrar métodos `delete_by_note_id→delete_by_note`, `get_note_ids→count`, `respond→generate`; quitar `__init__` abstractos.
- [x] Añadir `ConfigError(ObsidianRagError)`.
- [x] Actualizar `src/domain/__init__.py` (imports/`__all__`) y docstring de `ports.py`.
- [x] Gate: `pytest tests/unit -q` verde.

### 🗄️ Vector store (ChromaDB)
- [x] `ChromaVectorStore` con colección por estrategia (`hnsw:space=cosine`), embedder inyectado, `client` opcional.
- [x] `add_chunks` (group + upsert + metadatas saneados).
- [x] `search` (default_strategy, score clamp, filtro min_score, rank).
- [x] `delete_by_note` y `count`.

### 🔌 Adaptadores LLM/Embedder
- [x] `OllamaEmbedderAdapter` + `OllamaLLMAdapter` en `ollama_adapter.py`.
- [x] `HuggingFaceEmbedderAdapter` + `GroqLLMAdapter` en `groq_adapter.py`.
- [x] Template RAG compartido + traducción de excepciones (`EmbeddingError`).

### 🏭 Factory (infrastructure)
- [x] `config.py` con `load_dotenv`, helpers seguros, `ConfigError`, imports lazy.
- [x] Las 7 factories, inyección de embedder/estrategia/loader.

### 🧪 Tests
- [x] `FakeEmbedder` + `test_chroma_store.py` (7 tests).
- [x] `test_config.py` (6 tests, mock env).
- [ ] `test_ollama_integration.py` (3 tests `@integration`, requiere Ollama).

### 📚 Documentación y sincronización
- [ ] Actualizar `CLAUDE.md` (adapters/estado Fase 3) y doc de `CHROMA_PERSIST_DIR`.
- [ ] Marcar criterios en `tasks/fase-3-vectorstore-llm.md`.
- [x] Entrada en `docs/error-log.md` (recurrencia deriva spec↔dominio).

### ✅ Verificación final
- [x] `ruff check src/ tests/ --fix && ruff format src/ tests/`.
- [x] `pytest tests/unit -q` (57/57).
- [ ] `pytest tests/integration/ -v -m integration` (requiere Ollama).
