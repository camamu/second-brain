---
title: "Estrategias de Chunking"
tags: [chunking, rag, evaluacion, tfm]
date: 2026-01-18
---

# Estrategias de Chunking

El **chunking** es el proceso de dividir documentos largos en fragmentos (*chunks*) más pequeños para indexarlos en el [[ChromaDB - Vector Store]]. La estrategia de chunking es la principal variable de investigación de este TFM.

## ¿Por qué importa?

Un chunk demasiado grande captura mucho contexto pero incluye ruido irrelevante. Uno demasiado pequeño pierde contexto. La estrategia óptima depende del tipo de documento y la consulta.

## Estrategias implementadas

### 1. Fixed-Size (`fixed`)
Divide el texto en ventanas de tamaño fijo (512 tokens) con solapamiento (50 tokens).

- **Ventaja**: simple, predecible, sin dependencias del contenido.
- **Desventaja**: puede cortar frases o secciones a la mitad.
- **Implementación**: `FixedSizeChunker` en `src/adapters/chunkers/fixed_size.py`.

### 2. Markdown Header (`markdown`)
Divide el documento por cabeceras Markdown (`#`, `##`, `###`). Cada sección es un chunk.

- **Ventaja**: respeta la estructura semántica de las notas.
- **Desventaja**: chunks de tamaño muy variable; secciones muy largas no se dividen.
- **Implementación**: `MarkdownHeaderChunker` en `src/adapters/chunkers/markdown_header.py`.

### 3. Backlink-Aware (`backlink`)
Expande cada nota con el contenido de las notas enlazadas mediante `[[backlinks]]` de Obsidian antes de chunkear.

- **Ventaja**: incluye contexto relacionado; ideal para vaults con estructura de red.
- **Desventaja**: chunks más grandes; puede duplicar contenido.
- **Implementación**: `BacklinkAwareChunker` en `src/adapters/chunkers/backlink_aware.py`.

## Comparativa en la evaluación

La hipótesis del TFM es que `backlink` obtiene mejor Precision@K en vaults con alta densidad de backlinks. Ver [[TFM - Metodología de Evaluación]] y [[TFM - Resultados Preliminares]].

## Relación con la arquitectura

Todos los chunkers implementan el puerto `BaseChunker` del dominio (arquitectura hexagonal). El sistema permite cambiar de estrategia sin modificar la capa de aplicación.

Ver también: [[RAG - Recuperación Aumentada con Generación]], [[Embeddings y Representación Vectorial]].
