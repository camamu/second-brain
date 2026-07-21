"""Tests unitarios para IngestVault."""

from unittest.mock import MagicMock

import pytest

from src.application.ingest_vault import IngestVault
from src.domain.models import Chunk, Note
from src.domain.ports import BaseChunker, NoteLoader, VectorStore


@pytest.fixture
def mock_loader() -> MagicMock:
    return MagicMock(spec=NoteLoader)


@pytest.fixture
def mock_chunker() -> MagicMock:
    return MagicMock(spec=BaseChunker)


@pytest.fixture
def mock_store() -> MagicMock:
    return MagicMock(spec=VectorStore)


@pytest.fixture
def notes(sample_note: Note) -> list[Note]:
    return [sample_note]


@pytest.fixture
def chunks(sample_chunk: Chunk) -> list[Chunk]:
    return [sample_chunk]


@pytest.fixture
def use_case(
    mock_loader: MagicMock,
    mock_chunker: MagicMock,
    mock_store: MagicMock,
) -> IngestVault:
    return IngestVault(loader=mock_loader, chunker=mock_chunker, store=mock_store)


# ─── execute() ────────────────────────────────────────────────────────────────


def test_ingest_vault_execute_loads_all_notes(
    use_case: IngestVault,
    mock_loader: MagicMock,
    mock_chunker: MagicMock,
    notes: list[Note],
    chunks: list[Chunk],
) -> None:
    # Arrange
    mock_loader.load_all.return_value = notes
    mock_chunker.chunk_many.return_value = chunks

    # Act
    use_case.execute()

    # Assert
    mock_loader.load_all.assert_called_once()


def test_ingest_vault_execute_chunks_all_notes(
    use_case: IngestVault,
    mock_loader: MagicMock,
    mock_chunker: MagicMock,
    notes: list[Note],
    chunks: list[Chunk],
) -> None:
    # Arrange
    mock_loader.load_all.return_value = notes
    mock_chunker.chunk_many.return_value = chunks

    # Act
    use_case.execute()

    # Assert
    mock_chunker.chunk_many.assert_called_once_with(notes)


def test_ingest_vault_execute_adds_chunks_to_store(
    use_case: IngestVault,
    mock_loader: MagicMock,
    mock_chunker: MagicMock,
    mock_store: MagicMock,
    notes: list[Note],
    chunks: list[Chunk],
) -> None:
    # Arrange
    mock_loader.load_all.return_value = notes
    mock_chunker.chunk_many.return_value = chunks

    # Act
    use_case.execute()

    # Assert
    mock_store.add_chunks.assert_called_once_with(chunks)


def test_ingest_vault_execute_returns_chunk_count(
    use_case: IngestVault,
    mock_loader: MagicMock,
    mock_chunker: MagicMock,
    notes: list[Note],
    chunks: list[Chunk],
) -> None:
    # Arrange
    mock_loader.load_all.return_value = notes
    mock_chunker.chunk_many.return_value = chunks

    # Act
    result = use_case.execute()

    # Assert
    assert result == len(chunks)


def test_ingest_vault_execute_empty_vault_returns_zero(
    use_case: IngestVault,
    mock_loader: MagicMock,
    mock_store: MagicMock,
) -> None:
    # Arrange
    mock_loader.load_all.return_value = []

    # Act
    result = use_case.execute()

    # Assert
    assert result == 0
    mock_store.add_chunks.assert_not_called()


def test_ingest_vault_execute_no_chunks_returns_zero(
    use_case: IngestVault,
    mock_loader: MagicMock,
    mock_chunker: MagicMock,
    mock_store: MagicMock,
    notes: list[Note],
) -> None:
    # Arrange
    mock_loader.load_all.return_value = notes
    mock_chunker.chunk_many.return_value = []

    # Act
    result = use_case.execute()

    # Assert
    assert result == 0
    mock_store.add_chunks.assert_not_called()


# ─── execute_single() ─────────────────────────────────────────────────────────


def test_ingest_vault_execute_single_reindexes_one_note(
    use_case: IngestVault,
    mock_loader: MagicMock,
    mock_chunker: MagicMock,
    mock_store: MagicMock,
    sample_note: Note,
    chunks: list[Chunk],
) -> None:
    # Arrange
    mock_loader.load_by_id.return_value = sample_note
    mock_chunker.chunk_many.return_value = chunks

    # Act
    result = use_case.execute_single(sample_note.id)

    # Assert
    mock_loader.load_by_id.assert_called_once_with(sample_note.id)
    mock_chunker.chunk_many.assert_called_once_with([sample_note])
    mock_store.add_chunks.assert_called_once_with(chunks)
    assert result == len(chunks)


def test_ingest_vault_execute_single_deletes_old_chunks_first(
    use_case: IngestVault,
    mock_loader: MagicMock,
    mock_chunker: MagicMock,
    mock_store: MagicMock,
    sample_note: Note,
    chunks: list[Chunk],
) -> None:
    """delete_by_note debe llamarse ANTES que add_chunks para evitar chunks huérfanos."""
    # Arrange
    mock_loader.load_by_id.return_value = sample_note
    mock_chunker.chunk_many.return_value = chunks
    call_order: list[str] = []
    mock_store.delete_by_note.side_effect = lambda *_: call_order.append("delete")
    mock_store.add_chunks.side_effect = lambda *_: call_order.append("add")

    # Act
    use_case.execute_single(sample_note.id)

    # Assert
    assert call_order == ["delete", "add"]


def test_ingest_vault_execute_single_uses_all_chunkers_when_provided(
    mock_loader: MagicMock,
    mock_store: MagicMock,
    sample_note: Note,
    chunks: list[Chunk],
) -> None:
    """Una nota debe reindexarse con cada chunker de all_chunkers, no solo
    con el de la estrategia activa, para quedar disponible al cambiar de
    estrategia."""
    # Arrange
    chunker_a = MagicMock(spec=BaseChunker)
    chunker_b = MagicMock(spec=BaseChunker)
    chunker_a.chunk_many.return_value = chunks
    chunker_b.chunk_many.return_value = chunks
    mock_loader.load_by_id.return_value = sample_note
    use_case = IngestVault(
        loader=mock_loader,
        chunker=chunker_a,
        store=mock_store,
        all_chunkers=[chunker_a, chunker_b],
    )

    # Act
    use_case.execute_single(sample_note.id)

    # Assert
    chunker_a.chunk_many.assert_called_once_with([sample_note])
    chunker_b.chunk_many.assert_called_once_with([sample_note])
    assert mock_store.add_chunks.call_count == 2


def test_ingest_vault_execute_single_deletes_note_only_once_with_multiple_chunkers(
    mock_loader: MagicMock,
    mock_store: MagicMock,
    sample_note: Note,
    chunks: list[Chunk],
) -> None:
    """delete_by_note debe llamarse una sola vez aunque haya varios chunkers:
    llamarlo por cada uno borraría en cada iteración lo que la anterior
    acababa de indexar (delete_by_note actúa sobre todas las colecciones)."""
    # Arrange
    chunker_a = MagicMock(spec=BaseChunker)
    chunker_b = MagicMock(spec=BaseChunker)
    chunker_a.chunk_many.return_value = chunks
    chunker_b.chunk_many.return_value = chunks
    mock_loader.load_by_id.return_value = sample_note
    use_case = IngestVault(
        loader=mock_loader,
        chunker=chunker_a,
        store=mock_store,
        all_chunkers=[chunker_a, chunker_b],
    )

    # Act
    use_case.execute_single(sample_note.id)

    # Assert
    mock_store.delete_by_note.assert_called_once_with(sample_note.id)


def test_ingest_vault_execute_single_sums_chunk_count_across_chunkers(
    mock_loader: MagicMock,
    mock_store: MagicMock,
    sample_note: Note,
    chunks: list[Chunk],
) -> None:
    # Arrange
    chunker_a = MagicMock(spec=BaseChunker)
    chunker_b = MagicMock(spec=BaseChunker)
    chunker_a.chunk_many.return_value = chunks
    chunker_b.chunk_many.return_value = chunks
    mock_loader.load_by_id.return_value = sample_note
    use_case = IngestVault(
        loader=mock_loader,
        chunker=chunker_a,
        store=mock_store,
        all_chunkers=[chunker_a, chunker_b],
    )

    # Act
    result = use_case.execute_single(sample_note.id)

    # Assert
    assert result == len(chunks) * 2
