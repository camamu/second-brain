---
title: "RAG - Recuperación Aumentada con Generación"
tags: [rag, llm, arquitectura, ia]
date: 2026-01-15
---

# RAG - Recuperación Aumentada con Generación

La **Recuperación Aumentada con Generación** (RAG, del inglés *Retrieval-Augmented Generation*) es una arquitectura de IA que combina la búsqueda semántica de documentos con la capacidad generativa de los [[Modelos de Lenguaje Grande (LLM)]].

## Problema que resuelve

Los LLMs tienen dos limitaciones fundamentales:
1. **Conocimiento estático**: su información está congelada en la fecha de entrenamiento.
2. **Alucinaciones**: pueden generar información plausible pero incorrecta.

RAG resuelve ambas al anclar las respuestas en documentos reales recuperados en tiempo de ejecución.

## Flujo de trabajo

```
Pregunta del usuario
       ↓
Embedding de la pregunta
       ↓
Búsqueda semántica en el [[ChromaDB - Vector Store]]
       ↓
Recuperación de los K chunks más relevantes
       ↓
Construcción del prompt: contexto + pregunta
       ↓
Generación de respuesta con el LLM
```

## Componentes clave

- **Embedder**: convierte texto en vectores numéricos. Ver [[Embeddings y Representación Vectorial]].
- **Vector Store**: almacén indexado de vectores para búsqueda eficiente.
- **Chunker**: divide los documentos fuente en fragmentos manejables. Ver [[Estrategias de Chunking]].
- **LLM**: genera la respuesta final a partir del contexto recuperado.

## Ventajas para el TFM

En este proyecto, RAG permite hacer preguntas en lenguaje natural sobre un vault de [[Obsidian - Gestión del Conocimiento]]. El sistema indexa las notas, las convierte en vectores y recupera los fragmentos más relevantes antes de generar la respuesta.

Ver también: [[Agente ReAct]], [[TFM - Objetivos y Alcance]].
