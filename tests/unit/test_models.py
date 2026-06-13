"""Tests unitarios para los modelos del dominio."""

import pytest

from src.domain.models import (
    Chunk,
    ChunkStrategy,
    EvaluationResult,
    Note,
    SearchResult,
)


def test_note_word_count_returns_correct_count():
    note = Note(id="n1", title="T", content="uno dos tres cuatro")
    assert note.word_count == 4


def test_note_word_count_empty_content_returns_zero():
    note = Note(id="n1", title="T", content="")
    assert note.word_count == 0


def test_note_has_frontmatter_metadata_true_with_tags():
    note = Note(id="n1", title="T", content="x", tags=["ia"])
    assert note.has_frontmatter_metadata is True


def test_note_has_frontmatter_metadata_true_with_frontmatter():
    note = Note(id="n1", title="T", content="x", frontmatter={"date": "2024"})
    assert note.has_frontmatter_metadata is True


def test_note_has_frontmatter_metadata_false_without_data():
    note = Note(id="n1", title="T", content="x")
    assert note.has_frontmatter_metadata is False


def test_chunk_char_count_returns_content_length():
    chunk = Chunk(
        id="c1",
        note_id="n1",
        content="Texto de ejemplo para test.",
        strategy=ChunkStrategy.FIXED_SIZE,
    )
    assert chunk.char_count == len("Texto de ejemplo para test.")


def test_search_result_is_relevant_above_threshold():
    result = SearchResult(chunk_id="c1", note_id="n1", content="x" * 10, score=0.85, rank=1)
    assert result.is_relevant is True


def test_search_result_is_relevant_at_threshold():
    result = SearchResult(chunk_id="c1", note_id="n1", content="x" * 10, score=0.7, rank=1)
    assert result.is_relevant is True


def test_search_result_is_relevant_below_threshold():
    result = SearchResult(chunk_id="c1", note_id="n1", content="x" * 10, score=0.5, rank=1)
    assert result.is_relevant is False


def test_evaluation_result_mean_precision_with_data():
    result = EvaluationResult(
        strategy="fixed",
        total_samples=10,
        precision_at_k={3: 0.6, 5: 0.8, 10: 0.7},
    )
    assert result.mean_precision == pytest.approx((0.6 + 0.8 + 0.7) / 3)


def test_evaluation_result_mean_precision_empty_returns_zero():
    result = EvaluationResult(strategy="fixed", total_samples=0)
    assert result.mean_precision == 0.0


def test_evaluation_result_mean_mrr_with_data():
    result = EvaluationResult(
        strategy="markdown",
        total_samples=3,
        mrr_per_sample={"eval-1": 1.0, "eval-2": 0.5, "eval-3": 0.33},
    )
    assert result.mean_mrr == pytest.approx((1.0 + 0.5 + 0.33) / 3)


def test_evaluation_result_summary_format():
    result = EvaluationResult(
        strategy="fixed",
        total_samples=5,
        mrr=0.75,
        precision_at_k={3: 0.6, 5: 0.8},
    )
    summary = result.summary()
    assert "Strategy=fixed" in summary
    assert "Samples=5" in summary
    assert "MRR=0.750" in summary
    assert "P@3=0.600" in summary
    assert "P@5=0.800" in summary


def test_chunk_strategy_values_match_env_strings():
    assert ChunkStrategy.FIXED_SIZE.value == "fixed"
    assert ChunkStrategy.MARKDOWN_HEADER.value == "markdown"
    assert ChunkStrategy.BACKLINK_AWARE.value == "backlink"
