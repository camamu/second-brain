---
title: "ChromaDB - Vector Store"
tags: [chromadb, vectorstore, base-de-datos, rag]
date: 2026-01-19
---

# ChromaDB - Vector Store

**ChromaDB** es una base de datos vectorial open-source diseñada específicamente para aplicaciones de IA. Almacena vectores de [[Embeddings y Representación Vectorial]] junto con metadatos y permite búsquedas por similitud semántica en milisegundos.

## ¿Por qué ChromaDB?

| Criterio | ChromaDB | Pinecone | Weaviate |
|---|---|---|---|
| Coste | Gratuito (local) | Pago | Pago/Self-hosted |
| Setup | Zero config | Cloud | Docker |
| Persistencia | SQLite local | Cloud | Cloud/local |
| Ideal para | TFM / prototipo | Producción | Producción |

Para este TFM, ChromaDB local elimina dependencias externas y costes de cloud.

## Colecciones por estrategia

Cada [[Estrategias de Chunking]] usa una colección separada en ChromaDB. Esto permite evaluar las tres estrategias sobre el mismo conjunto de documentos sin interferencia:

- `chunks_fixed` — chunks de tamaño fijo
- `chunks_markdown` — chunks por cabeceras Markdown
- `chunks_backlink` — chunks con contexto de backlinks

## API principal

```python
store.add_chunks(chunks)           # indexar una lista de Chunk
store.search(query, k=5)           # búsqueda semántica top-K
store.delete_by_note(note_id)      # eliminar chunks de una nota
store.count()                      # número total de chunks indexados
```

## Similaridad coseno

ChromaDB usa distancia coseno como métrica de similitud. Dos vectores paralelos tienen similitud 1; dos vectores ortogonales tienen similitud 0. Los resultados de búsqueda se ordenan de mayor a menor similitud.

## En este proyecto

El adaptador `ChromaVectorStore` en `src/adapters/vector_stores/chroma_store.py` implementa el puerto `VectorStore` del dominio. Los datos se persisten en `data/chroma_db/` (SQLite + índices HNSW).

Ver también: [[RAG - Recuperación Aumentada con Generación]], [[LangChain - Framework de Orquestación]].
