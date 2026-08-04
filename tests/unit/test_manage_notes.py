"""Tests unitarios para ManageNotes."""

from unittest.mock import MagicMock

import pytest

from src.application.ingest_vault import IngestVault
from src.application.manage_notes import ManageNotes
from src.domain.models import ImportConflictPolicy, Note
from src.domain.ports import NoteLoader, NoteWriter, VaultWriteError


@pytest.fixture
def mock_loader() -> MagicMock:
    return MagicMock(spec=NoteLoader)


@pytest.fixture
def mock_writer() -> MagicMock:
    return MagicMock(spec=NoteWriter)


@pytest.fixture
def mock_ingest() -> MagicMock:
    return MagicMock(spec=IngestVault)


@pytest.fixture
def use_case(
    mock_loader: MagicMock,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
) -> ManageNotes:
    return ManageNotes(loader=mock_loader, writer=mock_writer, ingest=mock_ingest)


def test_manage_notes_create_writes_and_reindexes(
    use_case: ManageNotes,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
    sample_note: Note,
) -> None:
    # Arrange
    mock_writer.create.return_value = sample_note

    # Act
    result = use_case.create(
        title=sample_note.title,
        content=sample_note.content,
        tags=sample_note.tags,
    )

    # Assert
    mock_writer.create.assert_called_once_with(
        sample_note.title, sample_note.content, sample_note.tags
    )
    mock_ingest.execute_single.assert_called_once_with(sample_note.id)
    assert result == sample_note


def test_manage_notes_update_writes_and_reindexes(
    use_case: ManageNotes,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
    sample_note: Note,
) -> None:
    # Arrange
    new_content = "Contenido actualizado."
    mock_writer.update.return_value = sample_note

    # Act
    result = use_case.update(note_id=sample_note.id, content=new_content)

    # Assert — sin tags explícitos, se propaga None (preserva tags actuales)
    mock_writer.update.assert_called_once_with(sample_note.id, new_content, None)
    mock_ingest.execute_single.assert_called_once_with(sample_note.id)
    assert result == sample_note


def test_manage_notes_update_with_tags_propagates_to_writer(
    use_case: ManageNotes,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
    sample_note: Note,
) -> None:
    # Arrange
    new_content = "Contenido actualizado."
    new_tags = ["nuevo-tag"]
    mock_writer.update.return_value = sample_note

    # Act
    result = use_case.update(note_id=sample_note.id, content=new_content, tags=new_tags)

    # Assert
    mock_writer.update.assert_called_once_with(sample_note.id, new_content, new_tags)
    mock_ingest.execute_single.assert_called_once_with(sample_note.id)
    assert result == sample_note


def test_import_md_creates_note_with_expected_note_id(
    use_case: ManageNotes,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
    sample_note: Note,
) -> None:
    # Arrange
    mock_writer.create_raw.return_value = sample_note
    mock_ingest.execute_single.return_value = 3
    raw = "---\ntags: []\n---\nContenido.\n"

    # Act
    note, chunks = use_case.import_markdown("importada.md", raw)

    # Assert
    mock_writer.create_raw.assert_called_once_with(
        "importada.md", raw, ImportConflictPolicy.FAIL
    )
    assert note == sample_note
    assert chunks == 3


def test_import_md_rejects_non_md_extension(
    use_case: ManageNotes,
    mock_writer: MagicMock,
) -> None:
    # Act / Assert
    with pytest.raises(VaultWriteError):
        use_case.import_markdown("importada.txt", "contenido")
    mock_writer.create_raw.assert_not_called()


def test_import_md_rejects_when_note_id_already_exists(
    use_case: ManageNotes,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
) -> None:
    # Arrange — el adaptador propaga VaultWriteError si la política es FAIL
    mock_writer.create_raw.side_effect = VaultWriteError("Ya existe una nota")

    # Act / Assert
    with pytest.raises(VaultWriteError):
        use_case.import_markdown("duplicada.md", "contenido")
    mock_ingest.execute_single.assert_not_called()


def test_import_md_indexes_into_all_chunking_strategies(
    use_case: ManageNotes,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
    sample_note: Note,
) -> None:
    # Arrange — execute_single es quien hace el fan-out a all_chunkers
    mock_writer.create_raw.return_value = sample_note
    mock_ingest.execute_single.return_value = 6

    # Act
    use_case.import_markdown("importada.md", "contenido")

    # Assert
    mock_ingest.execute_single.assert_called_once_with(sample_note.id)


def test_import_md_returns_chunk_count_from_ingest(
    use_case: ManageNotes,
    mock_writer: MagicMock,
    mock_ingest: MagicMock,
    sample_note: Note,
) -> None:
    # Arrange
    mock_writer.create_raw.return_value = sample_note
    mock_ingest.execute_single.return_value = 9

    # Act
    _, chunks = use_case.import_markdown("importada.md", "contenido")

    # Assert
    assert chunks == 9


def test_manage_notes_get_delegates_to_loader(
    use_case: ManageNotes,
    mock_loader: MagicMock,
    sample_note: Note,
) -> None:
    # Arrange
    mock_loader.load_by_id.return_value = sample_note

    # Act
    result = use_case.get(sample_note.id)

    # Assert
    mock_loader.load_by_id.assert_called_once_with(sample_note.id)
    assert result == sample_note
