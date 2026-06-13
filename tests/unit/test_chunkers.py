"""Tests unitarios para los tres chunkers de Fase 2."""

from unittest.mock import MagicMock

import pytest

from src.adapters.chunkers.backlink_aware import BacklinkAwareChunker
from src.adapters.chunkers.fixed_size import FixedSizeChunker
from src.adapters.chunkers.markdown_header import MarkdownHeaderChunker
from src.domain.models import ChunkStrategy, Note, NoteType
from src.domain.ports import NoteLoader


def _note(content: str, backlinks: list[str] | None = None) -> Note:
    return Note(
        id="test/nota",
        title="Nota de test",
        content=content,
        tags=["t1"],
        note_type=NoteType.DOC,
        path="/vault/test/nota.md",
        backlinks=backlinks or [],
    )


# ---------------------------------------------------------------------------
# FixedSizeChunker
# ---------------------------------------------------------------------------


def test_fixed_size_chunker_splits_long_content():
    # Arrange
    long = "a" * 600
    chunker = FixedSizeChunker(chunk_size=100, chunk_overlap=0)
    # Act
    chunks = chunker.chunk(_note(long))
    # Assert
    assert len(chunks) > 1


def test_fixed_size_chunker_single_chunk_for_short_content():
    # Arrange
    chunker = FixedSizeChunker(chunk_size=512, chunk_overlap=50)
    # Act
    chunks = chunker.chunk(_note("Contenido breve de la nota."))
    # Assert
    assert len(chunks) == 1


def test_fixed_size_chunker_empty_note_returns_empty_list():
    # Arrange
    chunker = FixedSizeChunker()
    # Act
    chunks = chunker.chunk(_note(""))
    # Assert
    assert chunks == []


def test_fixed_size_chunker_overlap_creates_overlapping_content():
    # Arrange
    text = "a" * 100
    chunker = FixedSizeChunker(chunk_size=60, chunk_overlap=20)
    # Act
    chunks = chunker.chunk(_note(text))
    # Assert — el segundo chunk empieza 40 chars después del primero
    assert chunks[0].content[:20] == chunks[1].content[:20]


def test_fixed_size_chunker_chunk_ids_are_sequential():
    # Arrange
    chunker = FixedSizeChunker(chunk_size=20, chunk_overlap=0)
    note = _note("x" * 100)
    # Act
    chunks = chunker.chunk(note)
    # Assert
    ids = [c.id for c in chunks]
    assert ids == [f"test/nota_{i}" for i in range(len(chunks))]


def test_fixed_size_chunker_metadata_includes_tags():
    # Arrange
    chunker = FixedSizeChunker()
    # Act
    chunks = chunker.chunk(_note("Contenido suficiente para el chunk."))
    # Assert
    assert chunks[0].metadata["tags"] == ["t1"]
    assert chunks[0].metadata["note_type"] == "doc"


# ---------------------------------------------------------------------------
# MarkdownHeaderChunker
# ---------------------------------------------------------------------------


def test_markdown_header_chunker_splits_by_headings():
    # Arrange
    content = "## Sección uno\nContenido de la primera sección.\n## Sección dos\nContenido de la segunda."
    chunker = MarkdownHeaderChunker()
    # Act
    chunks = chunker.chunk(_note(content))
    # Assert
    assert len(chunks) == 2


def test_markdown_header_chunker_preserves_heading_text():
    # Arrange
    content = "## Mi cabecera\nTexto de la sección con suficiente contenido."
    chunker = MarkdownHeaderChunker()
    # Act
    chunks = chunker.chunk(_note(content))
    # Assert
    assert chunks[0].heading == "Mi cabecera"


def test_markdown_header_chunker_no_headings_returns_single_chunk():
    # Arrange
    content = "Texto sin ninguna cabecera markdown en absoluto."
    chunker = MarkdownHeaderChunker()
    # Act
    chunks = chunker.chunk(_note(content))
    # Assert
    assert len(chunks) == 1
    assert chunks[0].heading is None


def test_markdown_header_chunker_text_before_first_heading():
    # Arrange
    content = "Intro antes de cabecera.\n## Primera sección\nContenido de la sección."
    chunker = MarkdownHeaderChunker()
    # Act
    chunks = chunker.chunk(_note(content))
    # Assert — primer chunk tiene heading=None (texto pre-cabecera)
    assert chunks[0].heading is None
    assert "Intro" in chunks[0].content


def test_markdown_header_chunker_empty_note_returns_empty_list():
    # Arrange
    chunker = MarkdownHeaderChunker()
    # Act
    chunks = chunker.chunk(_note(""))
    # Assert
    assert chunks == []


# ---------------------------------------------------------------------------
# BacklinkAwareChunker
# ---------------------------------------------------------------------------


def test_backlink_aware_chunker_enriches_with_linked_notes():
    # Arrange
    linked = _note("Contenido de la nota enlazada con suficiente texto.")
    loader = MagicMock(spec=NoteLoader)
    loader.exists.return_value = True
    loader.load_by_id.return_value = linked
    note = _note("Contenido principal.", backlinks=["otra/nota"])
    chunker = BacklinkAwareChunker(loader)
    # Act
    chunks = chunker.chunk(note)
    # Assert
    assert len(chunks) >= 1
    assert "Nota enlazada" in chunks[0].content


def test_backlink_aware_chunker_ignores_missing_backlinks():
    # Arrange
    loader = MagicMock(spec=NoteLoader)
    loader.exists.return_value = False
    note = _note("Contenido principal sin backlinks resueltos.", backlinks=["no/existe"])
    chunker = BacklinkAwareChunker(loader)
    # Act
    chunks = chunker.chunk(note)
    # Assert — se genera un chunk solo con el contenido principal
    assert len(chunks) == 1
    assert "Nota enlazada" not in chunks[0].content


def test_backlink_aware_chunker_empty_note_returns_empty_list():
    # Arrange
    loader = MagicMock(spec=NoteLoader)
    chunker = BacklinkAwareChunker(loader)
    # Act
    chunks = chunker.chunk(_note(""))
    # Assert
    assert chunks == []


def test_backlink_aware_chunker_long_result_is_split():
    # Arrange
    linked = _note("z" * 200)
    loader = MagicMock(spec=NoteLoader)
    loader.exists.return_value = True
    loader.load_by_id.return_value = linked
    # Nota con contenido largo + backlinks que supere 2000 chars
    note = _note("a" * 1900, backlinks=["otra/nota"])
    chunker = BacklinkAwareChunker(loader)
    # Act
    chunks = chunker.chunk(note)
    # Assert — el resultado enriquecido supera 2000 chars y se trocea
    assert len(chunks) > 1


# ---------------------------------------------------------------------------
# Estrategia correcta en todos los chunkers
# ---------------------------------------------------------------------------


def test_all_chunkers_set_correct_strategy_enum():
    # Arrange
    content = "## Sección\nContenido de prueba suficientemente largo para el chunk."
    loader = MagicMock(spec=NoteLoader)
    loader.exists.return_value = False
    note = _note(content)

    fixed = FixedSizeChunker()
    markdown = MarkdownHeaderChunker()
    backlink = BacklinkAwareChunker(loader)

    # Act
    fixed_chunks = fixed.chunk(note)
    markdown_chunks = markdown.chunk(note)
    backlink_chunks = backlink.chunk(note)

    # Assert
    assert all(c.strategy == ChunkStrategy.FIXED_SIZE for c in fixed_chunks)
    assert all(c.strategy == ChunkStrategy.MARKDOWN_HEADER for c in markdown_chunks)
    assert all(c.strategy == ChunkStrategy.BACKLINK_AWARE for c in backlink_chunks)
