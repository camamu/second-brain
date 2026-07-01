---
title: "TFM - Metodología de Evaluación"
tags: [tfm, evaluacion, metricas, precision, mrr]
date: 2026-01-25
---

# TFM - Metodología de Evaluación

La evaluación compara las tres [[Estrategias de Chunking]] usando métricas estándar de recuperación de información.

## Métricas

### Precision@K
Mide la fracción de los K chunks recuperados que son relevantes para la consulta.

```
Precision@K = (chunks relevantes en top K) / K
```

Valores típicos: K=1, K=3, K=5.

### MRR (Mean Reciprocal Rank)
Mide en qué posición aparece el primer chunk relevante en el ranking.

```
MRR = (1/N) * Σ (1/rank_i)
```

Donde `rank_i` es la posición del primer resultado relevante para la consulta `i`.

## Dataset de evaluación

Un conjunto de pares `(pregunta, nota_relevante)` creados manualmente a partir del vault. Cada pregunta tiene al menos un `note_id` de referencia (ground truth).

Formato (`evaluation/dataset.json`):
```json
[
  {
    "query": "¿Qué es RAG?",
    "relevant_note_ids": ["rag-recuperacion-aumentada"]
  }
]
```

## Protocolo

1. Indexar el vault con cada estrategia por separado.
2. Para cada consulta del dataset, recuperar los top-5 chunks.
3. Comparar los `note_id` recuperados con el ground truth.
4. Calcular Precision@1, Precision@3, Precision@5 y MRR para cada estrategia.
5. Repetir 3 veces y promediar para reducir varianza.

## Hipótesis

La estrategia **backlink** obtendrá la mayor Precision@K en vaults con alta densidad de backlinks porque expande el contexto de cada nota con información relacionada, capturando mejor la semántica de red del vault.

## Relación con el [[Agente ReAct]]

La evaluación se realiza directamente sobre el vector store (sin pasar por el agente), para medir la calidad de la recuperación de forma aislada. El agente añade una capa de razonamiento sobre los resultados.

Ver también: [[TFM - Objetivos y Alcance]], [[TFM - Resultados Preliminares]], [[ChromaDB - Vector Store]].
