---
title: "TFM - Resultados Preliminares"
tags: [tfm, resultados, evaluacion, metricas]
date: 2026-01-26
---

# TFM - Resultados Preliminares

Resultados de la evaluación comparativa de las tres [[Estrategias de Chunking]] sobre el vault del máster.

## Configuración del experimento

- **Vault**: notas del Máster en Desarrollo de IA (~200 notas, ~150k palabras)
- **Dataset**: 30 pares (pregunta, nota relevante) anotados manualmente
- **Embedder**: `nomic-ai/nomic-embed-text-v1` — [[Embeddings y Representación Vectorial]]
- **Vector store**: [[ChromaDB - Vector Store]] (distancia coseno)

## Resultados (preliminares)

| Estrategia | Precision@1 | Precision@3 | Precision@5 | MRR |
|---|---|---|---|---|
| Fixed (512 tokens) | 0.63 | 0.71 | 0.74 | 0.68 |
| Markdown header | 0.70 | 0.76 | 0.78 | 0.73 |
| Backlink-aware | **0.77** | **0.82** | **0.84** | **0.79** |

## Análisis preliminar

La estrategia **backlink** supera a las otras en todas las métricas, consistente con la hipótesis del TFM. La expansión con el contenido de notas enlazadas provee contexto adicional que mejora la similitud semántica con las consultas.

La estrategia **markdown** supera a **fixed** porque respeta los límites semánticos del documento (secciones), evitando cortar conceptos a mitad.

## Limitaciones

- Muestra de 30 consultas puede no ser suficiente para resultados estadísticamente significativos.
- El dataset está sesgado hacia el tipo de preguntas que el autor conoce de antemano.
- Los resultados pueden variar con otros vaults y otros modelos de embedding.

## Próximos pasos

1. Ampliar el dataset a 100 consultas.
2. Evaluar con diferentes modelos de embedding.
3. Analizar el impacto del tamaño del vault.

Ver también: [[TFM - Metodología de Evaluación]], [[TFM - Objetivos y Alcance]], [[Modelos de Lenguaje Grande (LLM)]].
