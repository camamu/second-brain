---
title: "Embeddings y Representación Vectorial"
tags: [embeddings, nlp, vectores, ia]
date: 2026-01-16
---

# Embeddings y Representación Vectorial

Un **embedding** es una representación numérica densa de texto en un espacio vectorial de alta dimensión. Palabras, frases o documentos semánticamente similares se mapean a vectores cercanos en ese espacio.

## ¿Por qué son esenciales en RAG?

Sin embeddings no existe [[RAG - Recuperación Aumentada con Generación]]: la búsqueda semántica depende de comparar el vector de la pregunta con los vectores de los chunks indexados. La similitud del coseno entre vectores determina la relevancia.

## Modelos de embedding

### nomic-embed-text (local con Ollama)
- Dimensión: 768
- Especialmente diseñado para búsqueda de documentos
- Rápido y eficiente en CPU

### nomic-ai/nomic-embed-text-v1 (HuggingFace)
- El mismo modelo, ejecutado localmente vía `sentence-transformers`
- Usado en producción en este proyecto (sin API externa)
- Requiere `trust_remote_code=True` por su arquitectura personalizada

### text-embedding-ada-002 (OpenAI)
- 1536 dimensiones
- Alta calidad, pero coste por llamada de API

## Propiedades importantes

| Propiedad | Descripción |
|---|---|
| Dimensionalidad | Número de componentes del vector (768, 1536, etc.) |
| Normalización | Vectores unitarios facilitan la similitud coseno |
| Contexto | Los modelos modernos son context-aware (bidireccionales) |

## En este proyecto

El adaptador `HuggingFaceEmbedderAdapter` envuelve `langchain-huggingface` para generar embeddings en el propio servidor, sin depender de APIs externas de pago. Ver [[ChromaDB - Vector Store]] para cómo se indexan.

Ver también: [[Estrategias de Chunking]], [[LangChain - Framework de Orquestación]].
