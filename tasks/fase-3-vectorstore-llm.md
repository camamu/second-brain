# Fase 3 — Vector store y adaptadores LLM

## Contexto

Esta fase implementa la capa de persistencia vectorial (ChromaDB) y los adaptadores para los dos entornos de ejecución: local (Ollama) y producción (Groq + HuggingFace). También crea la factory en infrastructure que conecta todo.

**Ficheros a crear:**
- `src/adapters/vector_store/chroma_store.py`
- `src/adapters/llm/ollama_adapter.py`
- `src/adapters/llm/groq_adapter.py`
- `src/infrastructure/config.py`
- `tests/unit/test_chroma_store.py`
- `tests/unit/test_config.py`
- `tests/integration/test_ollama_integration.py`

**Dependencias de dominio:**
- `Chunk`, `SearchResult`, `RetrievalQuery`, `ChunkStrategy` de `src.domain.models`
- `ChunkEmbedder`, `VectorStore`, `ConversationalLLM` de `src.domain.ports`
- `VectorStoreError`, `EmbeddingError` de `src.domain.ports`

---

## Tareas

### T3.1 — Implementar `ChromaVectorStore`

Fichero: `src/adapters/vector_store/chroma_store.py`

Constructor: `persist_dir: str`, `collection_prefix: str = "obsidian_rag"`

El vector store usa una **colección por estrategia de chunking**. El nombre de la colección es `{collection_prefix}_{strategy.value}` (ej: `obsidian_rag_fixed`, `obsidian_rag_markdown`, `obsidian_rag_backlink`). Esto permite tener los tres índices en paralelo para la evaluación comparativa.

**`add_chunks(chunks: list[Chunk], embedder: ChunkEmbedder) -> None`**:
1. Agrupa los chunks por estrategia (todos deberían tener la misma, pero ser defensivo).
2. Para cada grupo, obtiene o crea la colección correspondiente.
3. Genera embeddings con `embedder.embed_many([c.content for c in chunks])`.
4. Llama a `collection.upsert(ids=..., embeddings=..., documents=..., metadatas=...)`.
5. Los metadatas deben incluir: `note_id`, `heading`, `strategy`, y todo lo que venga en `chunk.metadata`.
6. Envuelve errores de ChromaDB en `VectorStoreError`.

**`search(query: RetrievalQuery, embedder: ChunkEmbedder) -> list[SearchResult]`**:
1. Selecciona la colección según `query.strategy`.
2. Genera embedding de la query con `embedder.embed(query.text)`.
3. Llama a `collection.query(query_embeddings=[...], n_results=query.top_k)`.
4. Mapea los resultados a `list[SearchResult]` con score normalizado (ChromaDB devuelve distancias — convertir a similitud: `1 - distance` si usa cosine, o normalizar según la métrica configurada).
5. Reconstruye los objetos `Chunk` a partir de los documents y metadatas devueltos.
6. Ordena por score descendente y asigna `rank` (1-based).

**`delete_by_note(note_id: str) -> None`**:
1. Para cada colección existente, elimina los chunks donde `metadata["note_id"] == note_id`.

**`count() -> int`**:
1. Suma el count de todas las colecciones.

### T3.2 — Implementar `OllamaAdapter`

Fichero: `src/adapters/llm/ollama_adapter.py`

Contiene dos clases:

**`OllamaEmbedderAdapter(ChunkEmbedder)`**:
- Constructor: `model: str = "nomic-embed-text"`, `base_url: str = "http://localhost:11434"`
- Usa `langchain_ollama.OllamaEmbeddings` internamente.
- `embed(text)`: llama a `embeddings.embed_query(text)`.
- `embed_many(texts)`: llama a `embeddings.embed_documents(texts)`.
- Envuelve errores de conexión en `EmbeddingError`.

**`OllamaLLMAdapter(ConversationalLLM)`**:
- Constructor: `model: str = "llama3.2"`, `base_url: str = "http://localhost:11434"`
- Usa `langchain_ollama.OllamaLLM` internamente.
- `generate(prompt, context)`: construye el prompt completo con contexto RAG y llama a `llm.invoke()`.
- Prompt template sugerido:

```
Eres un asistente que responde preguntas basándose en las notas del usuario.
Usa el siguiente contexto recuperado de sus notas para responder.
Si no encuentras la respuesta en el contexto, di que no tienes información suficiente.

Contexto:
{context}

Pregunta: {prompt}

Respuesta:
```

### T3.3 — Implementar `GroqAdapter`

Fichero: `src/adapters/llm/groq_adapter.py`

Contiene dos clases:

**`HuggingFaceEmbedderAdapter(ChunkEmbedder)`**:
- Constructor: `model_name: str = "nomic-ai/nomic-embed-text-v1"`
- Usa `langchain_huggingface.HuggingFaceEmbeddings` internamente.
- Misma interfaz que OllamaEmbedderAdapter.

**`GroqLLMAdapter(ConversationalLLM)`**:
- Constructor: `api_key: str`, `model: str = "llama-3.2-90b-text-preview"`
- Usa `langchain_groq.ChatGroq` internamente.
- `generate(prompt, context)`: mismo prompt template que Ollama.

### T3.4 — Implementar factory en `src/infrastructure/config.py`

Este es el **composition root** — el único fichero que lee `.env` y decide qué adaptador instanciar.

```python
import os
from dotenv import load_dotenv

load_dotenv()
```

Funciones factory:
- `get_llm() -> ConversationalLLM` — devuelve OllamaLLMAdapter o GroqLLMAdapter según `USE_LOCAL`.
- `get_embedder() -> ChunkEmbedder` — devuelve OllamaEmbedderAdapter o HuggingFaceEmbedderAdapter.
- `get_vector_store() -> VectorStore` — devuelve ChromaVectorStore con `CHROMA_PERSIST_DIR`.
- `get_note_loader() -> NoteLoader` — devuelve ObsidianLoader con `VAULT_PATH`.
- `get_note_writer() -> NoteWriter` — devuelve ObsidianLoader (implementa ambos puertos).
- `get_chunker(strategy: ChunkStrategy) -> BaseChunker` — devuelve el chunker adecuado. `BacklinkAwareChunker` recibe `get_note_loader()` como dependencia.
- `get_chunker_from_env() -> BaseChunker` — lee `CHUNKER_STRATEGY` del .env y llama a `get_chunker`.

Regla: los imports de adaptadores son **lazy** (dentro de la función, no a nivel de módulo), para que no falle si faltan dependencias opcionales (ej: si Groq no está instalado en local).

---

## Tests

### T3.5 — `tests/unit/test_chroma_store.py`

ChromaDB puede funcionar in-memory (sin disco), así que los tests unitarios son factibles:

```python
import chromadb
client = chromadb.Client()  # in-memory
```

Tests obligatorios:
- `test_chroma_store_add_chunks_persists_documents`
- `test_chroma_store_add_chunks_upserts_duplicates`
- `test_chroma_store_search_returns_ranked_results`
- `test_chroma_store_search_respects_top_k`
- `test_chroma_store_search_uses_correct_collection_per_strategy`
- `test_chroma_store_delete_by_note_removes_all_chunks`
- `test_chroma_store_count_returns_total_across_collections`

Para los tests, crear un `FakeEmbedder(ChunkEmbedder)` que devuelva vectores aleatorios pero deterministas (usando un seed fijo). No llamar a Ollama en tests unitarios.

### T3.6 — `tests/unit/test_config.py`

Tests de la factory. Mockear `os.environ` para verificar:

- `test_get_llm_returns_ollama_when_local`
- `test_get_llm_returns_groq_when_not_local`
- `test_get_embedder_returns_ollama_when_local`
- `test_get_chunker_returns_correct_type_for_each_strategy`

### T3.7 — `tests/integration/test_ollama_integration.py`

Tests marcados con `@pytest.mark.integration`:

- `test_ollama_embedder_returns_vector_of_expected_dimension`
- `test_ollama_llm_generates_nonempty_response`
- `test_full_pipeline_ingest_and_search` (carga nota → chunk → embed → store → search)

---

## Reglas de implementación

- `chroma_store.py` importa `chromadb` — es su única dependencia externa.
- `ollama_adapter.py` importa `langchain_ollama` — su única dependencia externa.
- `groq_adapter.py` importa `langchain_groq` y `langchain_huggingface`.
- `config.py` es el único fichero que llama a `os.getenv()`.
- Todos los adaptadores traducen excepciones externas a excepciones de dominio.

---

## Criterio de completado

- [ ] ChromaDB persiste chunks y los recupera correctamente
- [ ] Los dos adaptadores LLM generan respuestas (Ollama probado, Groq verificable cambiando USE_LOCAL)
- [ ] La factory devuelve el adaptador correcto según el entorno
- [ ] Tests unitarios pasan: `pytest tests/unit/test_chroma_store.py tests/unit/test_config.py -v`
- [ ] Test de integración pasa: `pytest tests/integration/ -v -m integration`
