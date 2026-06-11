"""Fixtures compartidos para todos los tests del proyecto."""

import pytest

from src.domain.models import (
    Chunk,
    ChunkStrategy,
    EvaluationSample,
    Note,
    SearchResult,
)


@pytest.fixture
def sample_note() -> Note:
    return Note(
        note_id="note-001",
        title="Aprendizaje profundo",
        content="El aprendizaje profundo es una rama del machine learning.",
        frontmatter={"author": "Carlos", "date": "2024-01-15"},
        tags=["ml", "deep-learning", "ia"],
        backlinks=["note-002", "note-003"],
        created_at="2024-01-15",
        updated_at="2024-06-01",
    )


@pytest.fixture
def sample_note_empty() -> Note:
    return Note(
        note_id="note-empty",
        title="Nota vacía",
        content="",
    )


@pytest.fixture
def sample_note_no_frontmatter() -> Note:
    return Note(
        note_id="note-plain",
        title="Nota sin metadatos",
        content="Contenido sin frontmatter ni tags.",
    )


@pytest.fixture
def sample_chunk(sample_note: Note) -> Chunk:
    return Chunk(
        chunk_id="note-001_chunk_0",
        note_id=sample_note.note_id,
        content="El aprendizaje profundo es una rama del machine learning.",
        strategy=ChunkStrategy.FIXED.value,
        position=0,
        token_count=12,
    )


@pytest.fixture
def sample_search_result() -> SearchResult:
    return SearchResult(
        chunk_id="note-001_chunk_0",
        note_id="note-001",
        content="El aprendizaje profundo es una rama del machine learning.",
        score=0.9,
        rank=1,
    )


@pytest.fixture
def sample_evaluation_sample() -> EvaluationSample:
    return EvaluationSample(
        sample_id="eval-001",
        query="¿Qué es el aprendizaje profundo?",
        expected_chunk_ids=["note-001_chunk_0"],
        expected_note_ids=["note-001"],
        difficulty="easy",
    )


@pytest.fixture
def tmp_vault(tmp_path):
    """Directorio temporal con 3 ficheros .md de prueba."""
    nota1 = tmp_path / "aprendizaje-profundo.md"
    nota1.write_text(
        "---\ntags: [ml, ia]\n---\n# Aprendizaje profundo\nContenido de prueba.",
        encoding="utf-8",
    )
    nota2 = tmp_path / "redes-neuronales.md"
    nota2.write_text(
        "# Redes neuronales\nSon la base del deep learning.",
        encoding="utf-8",
    )
    nota3 = tmp_path / "backpropagation.md"
    nota3.write_text(
        "# Backpropagation\nAlgoritmo de entrenamiento. [[aprendizaje-profundo]]",
        encoding="utf-8",
    )
    return tmp_path
