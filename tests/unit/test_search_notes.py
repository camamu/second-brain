"""Tests unitarios para SearchNotes."""

from unittest.mock import MagicMock

import pytest

from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy, RetrievalQuery, SearchResult
from src.domain.ports import VectorStore


@pytest.fixture
def mock_store() -> MagicMock:
    return MagicMock(spec=VectorStore)


@pytest.fixture
def use_case(mock_store: MagicMock) -> SearchNotes:
    return SearchNotes(store=mock_store)


# ─── execute() ────────────────────────────────────────────────────────────────


def test_search_notes_execute_delegates_to_store(
    use_case: SearchNotes,
    mock_store: MagicMock,
    sample_search_result: SearchResult,
) -> None:
    # Arrange
    query = RetrievalQuery(query="deep learning", top_k=3)
    mock_store.search.return_value = [sample_search_result]

    # Act
    use_case.execute(query)

    # Assert
    mock_store.search.assert_called_once_with(query)


def test_search_notes_execute_returns_store_results(
    use_case: SearchNotes,
    mock_store: MagicMock,
    sample_search_result: SearchResult,
) -> None:
    # Arrange
    query = RetrievalQuery(query="redes neuronales")
    mock_store.search.return_value = [sample_search_result]

    # Act
    results = use_case.execute(query)

    # Assert
    assert results == [sample_search_result]


# ─── execute_text() ───────────────────────────────────────────────────────────


def test_search_notes_execute_text_builds_query_correctly(
    use_case: SearchNotes,
    mock_store: MagicMock,
) -> None:
    # Arrange
    mock_store.search.return_value = []

    # Act
    use_case.execute_text("machine learning", top_k=7)

    # Assert
    called_query: RetrievalQuery = mock_store.search.call_args[0][0]
    assert called_query.query == "machine learning"
    assert called_query.top_k == 7


def test_search_notes_execute_text_translates_strategy_to_value(
    use_case: SearchNotes,
    mock_store: MagicMock,
) -> None:
    # Arrange
    mock_store.search.return_value = []

    # Act
    use_case.execute_text("backlinks", strategy=ChunkStrategy.MARKDOWN_HEADER)

    # Assert
    called_query: RetrievalQuery = mock_store.search.call_args[0][0]
    assert called_query.strategy == "markdown"


def test_search_notes_execute_text_none_strategy_passes_none(
    use_case: SearchNotes,
    mock_store: MagicMock,
) -> None:
    # Arrange
    mock_store.search.return_value = []

    # Act
    use_case.execute_text("cualquier cosa", strategy=None)

    # Assert
    called_query: RetrievalQuery = mock_store.search.call_args[0][0]
    assert called_query.strategy is None
