"""Métricas de Information Retrieval para la evaluación comparativa.

Funciones puras sin estado ni I/O. Todas operan sobre SearchResult del dominio.
"""

from src.domain.models import SearchResult


def precision_at_k(
    results: list[SearchResult],
    relevant_note_ids: list[str],
    k: int,
) -> float:
    """Calcula Precision@K.

    Args:
        results: Resultados del retrieval, ordenados por score descendente.
        relevant_note_ids: IDs de notas que son ground truth relevantes.
        k: Número de resultados a considerar.

    Returns:
        Float entre 0.0 y 1.0. Cero si no hay resultados o k=0.
    """
    if k <= 0:
        return 0.0
    top_k = results[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for r in top_k if r.note_id in relevant_note_ids)
    return hits / k


def reciprocal_rank(
    results: list[SearchResult],
    relevant_note_ids: list[str],
) -> float:
    """Calcula el Reciprocal Rank para un solo query.

    Args:
        results: Resultados del retrieval, ordenados por score descendente.
        relevant_note_ids: IDs de notas que son ground truth relevantes.

    Returns:
        1/rank del primer resultado relevante, o 0.0 si no hay ninguno.
    """
    for i, r in enumerate(results, start=1):
        if r.note_id in relevant_note_ids:
            return 1.0 / i
    return 0.0


def recall_at_k(
    results: list[SearchResult],
    relevant_note_ids: list[str],
    k: int,
) -> float:
    """Calcula Recall@K.

    Args:
        results: Resultados del retrieval, ordenados por score descendente.
        relevant_note_ids: IDs de notas que son ground truth relevantes.
        k: Número de resultados a considerar.

    Returns:
        Fracción de notas relevantes encontradas en los top K resultados.
        Cero si relevant_note_ids está vacío.
    """
    if not relevant_note_ids:
        return 0.0
    top_k = results[:k]
    found = {r.note_id for r in top_k if r.note_id in relevant_note_ids}
    return len(found) / len(relevant_note_ids)
