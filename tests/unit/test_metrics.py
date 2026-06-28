"""Tests unitarios para evaluation/metrics.py.

Las funciones de métricas son puras (sin I/O, sin estado) — los tests
operan directamente sobre SearchResult del dominio, sin mocks.
"""

import pytest

from evaluation.metrics import precision_at_k, recall_at_k, reciprocal_rank
from src.domain.models import SearchResult


def _make_result(note_id: str, rank: int = 1, score: float = 0.9) -> SearchResult:
    return SearchResult(
        chunk_id=f"chunk_{note_id}_{rank}",
        note_id=note_id,
        content="contenido de ejemplo",
        score=score,
        rank=rank,
    )


# ─── precision_at_k ───────────────────────────────────────────────────────────


def test_precision_at_k_all_relevant_returns_one() -> None:
    # Arrange
    results = [_make_result("nota_a", 1), _make_result("nota_b", 2)]
    relevant = ["nota_a", "nota_b"]

    # Act
    score = precision_at_k(results, relevant, k=2)

    # Assert
    assert score == pytest.approx(1.0)


def test_precision_at_k_none_relevant_returns_zero() -> None:
    results = [_make_result("nota_x", 1), _make_result("nota_y", 2)]
    relevant = ["nota_z"]

    score = precision_at_k(results, relevant, k=2)

    assert score == pytest.approx(0.0)


def test_precision_at_k_partial_relevant_returns_correct_ratio() -> None:
    # 2 de 4 resultados relevantes → P@4 = 0.5
    results = [
        _make_result("nota_a", 1),
        _make_result("nota_b", 2),
        _make_result("nota_c", 3),
        _make_result("nota_d", 4),
    ]
    relevant = ["nota_a", "nota_c"]

    score = precision_at_k(results, relevant, k=4)

    assert score == pytest.approx(0.5)


def test_precision_at_k_respects_k_limit() -> None:
    # Solo el primer resultado es relevante; k=1 → P@1=1.0, k=3 → P@3=0.333
    results = [
        _make_result("nota_a", 1),
        _make_result("nota_b", 2),
        _make_result("nota_c", 3),
    ]
    relevant = ["nota_a"]

    assert precision_at_k(results, relevant, k=1) == pytest.approx(1.0)
    assert precision_at_k(results, relevant, k=3) == pytest.approx(1 / 3)


# ─── reciprocal_rank ──────────────────────────────────────────────────────────


def test_reciprocal_rank_first_result_relevant_returns_one() -> None:
    results = [_make_result("nota_a", 1), _make_result("nota_b", 2)]
    relevant = ["nota_a"]

    rr = reciprocal_rank(results, relevant)

    assert rr == pytest.approx(1.0)


def test_reciprocal_rank_third_result_relevant_returns_one_third() -> None:
    results = [
        _make_result("nota_x", 1),
        _make_result("nota_y", 2),
        _make_result("nota_a", 3),
    ]
    relevant = ["nota_a"]

    rr = reciprocal_rank(results, relevant)

    assert rr == pytest.approx(1 / 3)


def test_reciprocal_rank_no_relevant_returns_zero() -> None:
    results = [_make_result("nota_x", 1), _make_result("nota_y", 2)]
    relevant = ["nota_z"]

    rr = reciprocal_rank(results, relevant)

    assert rr == pytest.approx(0.0)


# ─── recall_at_k ──────────────────────────────────────────────────────────────


def test_recall_at_k_all_found_returns_one() -> None:
    results = [_make_result("nota_a", 1), _make_result("nota_b", 2)]
    relevant = ["nota_a", "nota_b"]

    score = recall_at_k(results, relevant, k=2)

    assert score == pytest.approx(1.0)


def test_recall_at_k_partial_found_returns_correct_ratio() -> None:
    # Solo nota_a aparece en top 2; nota_b y nota_c no → Recall@2 = 1/3
    results = [
        _make_result("nota_a", 1),
        _make_result("nota_x", 2),
        _make_result("nota_b", 3),
    ]
    relevant = ["nota_a", "nota_b", "nota_c"]

    score = recall_at_k(results, relevant, k=2)

    assert score == pytest.approx(1 / 3)
