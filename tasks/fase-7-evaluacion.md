# Fase 7 — Evaluación comparativa (aportación investigadora)

## Contexto

Esta es la fase más importante desde el punto de vista académico. La comparativa de las tres estrategias de chunking es la aportación diferenciadora del TFM. Necesitas resultados cuantitativos con métricas estándar de Information Retrieval.

**Ficheros a crear:**
- `evaluation/dataset.json`
- `evaluation/metrics.py`
- `evaluation/run_evaluation.py`
- `evaluation/results/` (directorio para resultados)
- `tests/unit/test_metrics.py`

**Dependencias de dominio:**
- `EvaluationSample`, `EvaluationResult`, `ChunkStrategy`, `RetrievalQuery` de `src.domain.models`
- `EvaluationRepository` de `src.domain.ports`

---

## Tareas

### T7.1 — Crear `evaluation/dataset.json`

Dataset de preguntas anotadas sobre el vault. Mínimo 20, ideal 30 preguntas.

Estructura:

```json
{
  "metadata": {
    "vault_name": "mi-vault",
    "created_at": "2025-XX-XX",
    "total_samples": 25,
    "annotator": "autor del TFM"
  },
  "samples": [
    {
      "id": "q01",
      "query": "¿Qué es la arquitectura hexagonal?",
      "relevant_note_ids": [
        "02-areas/arquitectura/hexagonal",
        "02-areas/arquitectura/puertos-adaptadores"
      ],
      "difficulty": "easy",
      "notes": "Dos notas tratan este tema directamente"
    },
    {
      "id": "q02",
      "query": "¿Cómo se relaciona el patrón Saga con la consistencia eventual?",
      "relevant_note_ids": [
        "02-areas/distribuidos/saga-pattern",
        "02-areas/distribuidos/consistencia-eventual"
      ],
      "difficulty": "hard",
      "notes": "Requiere conectar conceptos de dos notas enlazadas"
    }
  ]
}
```

Cada sample tiene:
- `id`: identificador único
- `query`: pregunta en lenguaje natural
- `relevant_note_ids`: IDs de las notas que contienen la respuesta correcta (ground truth)
- `difficulty`: `easy` (respuesta en una nota obvia), `medium` (requiere contexto), `hard` (requiere conectar varias notas)
- `notes`: anotación opcional del evaluador

**Importante**: las preguntas deben cubrir diferentes tipos:
- Preguntas directas sobre una nota específica (easy)
- Preguntas que requieren información de varias notas (medium)
- Preguntas que solo se responden bien si el chunker preserva relaciones entre notas (hard) — aquí el BacklinkAwareChunker debería brillar
- Preguntas donde no hay respuesta en el vault (para medir falsos positivos)

### T7.2 — Implementar métricas en `evaluation/metrics.py`

**Precision@K**:

```
Precision@K = (número de chunks relevantes en los top K resultados) / K
```

Un chunk es relevante si su `note_id` está en `relevant_note_ids` del sample.

```python
def precision_at_k(
    results: list[SearchResult],
    relevant_note_ids: list[str],
    k: int,
) -> float:
    """
    Calcula Precision@K.

    Args:
        results: Resultados del retrieval, ordenados por score descendente.
        relevant_note_ids: IDs de notas que son ground truth relevantes.
        k: Número de resultados a considerar.

    Returns:
        Float entre 0.0 y 1.0.
    """
```

**MRR (Mean Reciprocal Rank)**:

```
RR = 1 / posición del primer resultado relevante
MRR = media de todos los RR del dataset
```

```python
def reciprocal_rank(
    results: list[SearchResult],
    relevant_note_ids: list[str],
) -> float:
    """
    Calcula el Reciprocal Rank para un solo query.

    Returns:
        1/rank del primer resultado relevante, o 0.0 si no hay ninguno.
    """
```

**Recall@K** (métrica adicional recomendada):

```
Recall@K = (número de notas relevantes encontradas en top K) / (total de notas relevantes)
```

### T7.3 — Implementar `EvaluationRepository` (adaptador)

Fichero sugerido: `src/adapters/evaluation_repo.py`

Implementa el puerto `EvaluationRepository`:
- `load_samples()`: lee `evaluation/dataset.json` y devuelve `list[EvaluationSample]`.
- `save_result(result)`: escribe a `evaluation/results/{strategy}_{timestamp}.json`.
- `load_results()`: lee todos los ficheros de resultados.

### T7.4 — Implementar `evaluation/run_evaluation.py`

Script que ejecuta la evaluación completa:

```python
"""
Ejecuta la evaluación comparativa de las tres estrategias de chunking.

Para cada estrategia:
1. Ingesta el vault con esa estrategia
2. Para cada pregunta del dataset:
   a. Ejecuta retrieval
   b. Calcula Precision@K y RR
3. Calcula las medias
4. Guarda los resultados

Al final, imprime una tabla comparativa.
"""
```

Flujo:
1. Cargar el dataset.
2. Para cada `ChunkStrategy`:
   a. Limpiar y reindestar el vault con esa estrategia.
   b. Para cada sample del dataset, hacer la query y calcular métricas.
   c. Almacenar `EvaluationResult`.
3. Imprimir tabla resumen:

```
┌──────────────────┬──────────────┬─────────┬────────────┐
│ Estrategia       │ Precision@5  │  MRR    │  Recall@5  │
├──────────────────┼──────────────┼─────────┼────────────┤
│ Fixed size       │    0.620     │  0.750  │   0.580    │
│ Markdown header  │    0.680     │  0.810  │   0.640    │
│ Backlink-aware   │    0.740     │  0.870  │   0.720    │
└──────────────────┴──────────────┴─────────┴────────────┘
```

4. Guardar también un desglose por dificultad (easy/medium/hard) — aquí es donde se verá la diferencia del BacklinkAwareChunker en preguntas que requieren conectar varias notas.

Ejecutar con:
```bash
python evaluation/run_evaluation.py
```

---

## Tests

### T7.5 — `tests/unit/test_metrics.py`

Tests con datos controlados (no necesitan ChromaDB ni Ollama):

- `test_precision_at_k_all_relevant_returns_one`
- `test_precision_at_k_none_relevant_returns_zero`
- `test_precision_at_k_partial_relevant_returns_correct_ratio`
- `test_precision_at_k_respects_k_limit`
- `test_reciprocal_rank_first_result_relevant_returns_one`
- `test_reciprocal_rank_third_result_relevant_returns_one_third`
- `test_reciprocal_rank_no_relevant_returns_zero`
- `test_recall_at_k_all_found_returns_one`
- `test_recall_at_k_partial_found_returns_correct_ratio`

---

## Reglas de implementación

- Las métricas son funciones puras (sin estado, sin I/O) — fáciles de testear.
- El script de evaluación importa de infrastructure (factory) — es un punto de entrada.
- No hardcodear el path del dataset — leerlo de config o argumento CLI.
- Logging de cada step de la evaluación para poder diagnosticar problemas.

---

## Criterio de completado

- [ ] Dataset con al menos 20 preguntas anotadas
- [ ] Precision@K, MRR y Recall@K implementados y testeados
- [ ] `python evaluation/run_evaluation.py` ejecuta la evaluación completa
- [ ] Tabla comparativa generada con resultados de las tres estrategias
- [ ] Resultados guardados en `evaluation/results/`
- [ ] Tests: `pytest tests/unit/test_metrics.py -v`
