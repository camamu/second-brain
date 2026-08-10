"""Tests unitarios para MoveNote."""

from unittest.mock import MagicMock

import pytest

from src.application.ingest_vault import IngestVault
from src.application.move_note import MoveNote
from src.domain.models import Note
from src.domain.ports import NoteLoader, NoteNotFoundError, NoteWriter, VectorStore


@pytest.fixture
def mock_loader() -> MagicMock:
    return MagicMock(spec=NoteLoader)


@pytest.fixture
def mock_writer() -> MagicMock:
    return MagicMock(spec=NoteWriter)


@pytest.fixture
def mock_store() -> MagicMock:
    return MagicMock(spec=VectorStore)


@pytest.fixture
def mock_ingest() -> MagicMock:
    return MagicMock(spec=IngestVault)


@pytest.fixture
def use_case(
    mock_loader: MagicMock,
    mock_writer: MagicMock,
    mock_store: MagicMock,
    mock_ingest: MagicMock,
) -> MoveNote:
    return MoveNote(
        loader=mock_loader, writer=mock_writer, store=mock_store, ingest=mock_ingest
    )


def _note(
    note_id: str, content: str = "Contenido.", backlinks: list[str] | None = None
) -> Note:
    return Note(id=note_id, title=note_id, content=content, backlinks=backlinks or [])


def test_move_note_use_case_moves_file_and_reindexes_under_new_path(
    use_case: MoveNote,
    mock_loader: MagicMock,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
) -> None:
    # Arrange — sin notas entrantes, movimiento simple
    mock_loader.load_all.return_value = []
    moved = _note("02-areas/rag/chunking")
    mock_writer.move.return_value = moved
    mock_ingest.execute_single.return_value = 4

    # Act
    result = use_case.execute("00-inbox/chunking", "02-areas/rag")

    # Assert
    mock_writer.move.assert_called_once_with("00-inbox/chunking", "02-areas/rag")
    mock_ingest.execute_single.assert_called_once_with("02-areas/rag/chunking")
    assert result.note == moved
    assert result.old_id == "00-inbox/chunking"
    assert result.chunks_indexed == 4


def test_move_note_use_case_removes_old_chunks_across_all_strategies(
    use_case: MoveNote,
    mock_loader: MagicMock,
    mock_writer: MagicMock,
    mock_store: MagicMock,
    mock_ingest: MagicMock,
) -> None:
    # Arrange
    mock_loader.load_all.return_value = []
    mock_writer.move.return_value = _note("02-areas/chunking")
    mock_ingest.execute_single.return_value = 2

    # Act
    use_case.execute("00-inbox/chunking", "02-areas")

    # Assert — delete_by_note del vector store itera todas las colecciones
    mock_store.delete_by_note.assert_called_once_with("00-inbox/chunking")


def test_move_note_use_case_rewrites_inbound_wikilinks(
    use_case: MoveNote,
    mock_loader: MagicMock,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
) -> None:
    # Arrange — "01-proyectos/tfm" enlaza a la nota que se va a mover
    linker = _note(
        "01-proyectos/tfm",
        content="Ver [[00-inbox/chunking|chunking]] para detalles.",
        backlinks=["00-inbox/chunking"],
    )
    mock_loader.load_all.return_value = [linker]
    mock_loader.load_by_id.return_value = linker
    mock_writer.move.return_value = _note("02-areas/chunking")
    mock_ingest.execute_single.return_value = 3

    # Act
    result = use_case.execute("00-inbox/chunking", "02-areas")

    # Assert
    mock_writer.update.assert_called_once_with(
        "01-proyectos/tfm",
        "Ver [[02-areas/chunking|chunking]] para detalles.",
        tags=None,
    )
    assert result.relinked_notes == ["01-proyectos/tfm"]
    assert result.failed_relinks == []
    # execute_single: una vez por la nota movida, otra por la reenlazada
    assert mock_ingest.execute_single.call_count == 2


def test_move_note_use_case_reports_failed_relinks_without_aborting(
    use_case: MoveNote,
    mock_loader: MagicMock,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
) -> None:
    # Arrange — la nota entrante desapareció entre la detección y el reenlazado
    mock_loader.load_all.return_value = [
        _note("01-proyectos/tfm", backlinks=["00-inbox/chunking"])
    ]
    mock_loader.load_by_id.side_effect = NoteNotFoundError("borrada")
    mock_writer.move.return_value = _note("02-areas/chunking")
    mock_ingest.execute_single.return_value = 1

    # Act — no debe propagar la excepción
    result = use_case.execute("00-inbox/chunking", "02-areas")

    # Assert
    assert result.relinked_notes == []
    assert result.failed_relinks == ["01-proyectos/tfm"]
    mock_writer.update.assert_not_called()


def test_move_note_use_case_lists_existing_folders_from_vault(
    use_case: MoveNote,
    mock_loader: MagicMock,
) -> None:
    # Arrange
    mock_loader.load_all.return_value = [
        _note("00-inbox/a"),
        _note("00-inbox/b"),
        _note("02-areas/rag/c"),
        _note("nota-en-la-raiz"),
    ]

    # Act
    folders = use_case.list_folders()

    # Assert — sin duplicados, ordenadas, la nota de raíz no aporta carpeta
    assert folders == ["00-inbox", "02-areas/rag"]


def test_move_note_use_case_raises_when_note_not_found(
    use_case: MoveNote,
    mock_loader: MagicMock,
    mock_writer: MagicMock,
    mock_store: MagicMock,
) -> None:
    # Arrange
    mock_loader.load_all.return_value = []
    mock_writer.move.side_effect = NoteNotFoundError("no existe")

    # Act / Assert
    with pytest.raises(NoteNotFoundError):
        use_case.execute("no-existe", "02-areas")
    mock_store.delete_by_note.assert_not_called()
