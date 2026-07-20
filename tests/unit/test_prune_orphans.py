"""Tests unitarios para PruneOrphans."""

from unittest.mock import MagicMock

import pytest

from src.application.prune_orphans import PruneOrphans
from src.domain.models import Note
from src.domain.ports import NoteLoader, VectorStore


@pytest.fixture
def mock_loader() -> MagicMock:
    return MagicMock(spec=NoteLoader)


@pytest.fixture
def mock_store() -> MagicMock:
    return MagicMock(spec=VectorStore)


@pytest.fixture
def use_case(mock_loader: MagicMock, mock_store: MagicMock) -> PruneOrphans:
    return PruneOrphans(loader=mock_loader, store=mock_store)


def _make_note(note_id: str) -> Note:
    return Note(id=note_id, title=note_id, content="Contenido.")


def test_prune_orphans_deletes_notes_not_in_vault(
    use_case: PruneOrphans,
    mock_loader: MagicMock,
    mock_store: MagicMock,
) -> None:
    # Arrange — el vault solo tiene "nota-viva"; el índice tiene 2 más
    mock_loader.load_all.return_value = [_make_note("nota-viva")]
    mock_store.list_note_ids.return_value = ["nota-viva", "huerfana-1", "huerfana-2"]

    # Act
    result = use_case.execute()

    # Assert
    assert result == ["huerfana-1", "huerfana-2"]
    assert mock_store.delete_by_note.call_count == 2
    mock_store.delete_by_note.assert_any_call("huerfana-1")
    mock_store.delete_by_note.assert_any_call("huerfana-2")


def test_prune_orphans_no_orphans_deletes_nothing(
    use_case: PruneOrphans,
    mock_loader: MagicMock,
    mock_store: MagicMock,
) -> None:
    # Arrange — vault e índice coinciden exactamente
    mock_loader.load_all.return_value = [_make_note("nota-viva")]
    mock_store.list_note_ids.return_value = ["nota-viva"]

    # Act
    result = use_case.execute()

    # Assert
    assert result == []
    mock_store.delete_by_note.assert_not_called()


def test_prune_orphans_empty_index_returns_empty(
    use_case: PruneOrphans,
    mock_loader: MagicMock,
    mock_store: MagicMock,
) -> None:
    # Arrange
    mock_loader.load_all.return_value = [_make_note("nota-viva")]
    mock_store.list_note_ids.return_value = []

    # Act
    result = use_case.execute()

    # Assert
    assert result == []
    mock_store.delete_by_note.assert_not_called()


def test_prune_orphans_find_orphans_does_not_delete(
    use_case: PruneOrphans,
    mock_loader: MagicMock,
    mock_store: MagicMock,
) -> None:
    # Arrange
    mock_loader.load_all.return_value = [_make_note("nota-viva")]
    mock_store.list_note_ids.return_value = ["nota-viva", "huerfana-1"]

    # Act
    result = use_case.find_orphans()

    # Assert — detección pura, sin efectos secundarios
    assert result == ["huerfana-1"]
    mock_store.delete_by_note.assert_not_called()


def test_prune_orphans_execute_with_precomputed_list_skips_detection(
    use_case: PruneOrphans,
    mock_loader: MagicMock,
    mock_store: MagicMock,
) -> None:
    # Act — se pasa la lista ya detectada; no debe consultar loader/store
    result = use_case.execute(orphans=["huerfana-1", "huerfana-2"])

    # Assert
    assert result == ["huerfana-1", "huerfana-2"]
    mock_loader.load_all.assert_not_called()
    mock_store.list_note_ids.assert_not_called()
    assert mock_store.delete_by_note.call_count == 2
