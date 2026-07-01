"""Tests de integración contra Ollama real (requiere servidor en localhost:11434)."""

import uuid

import chromadb
import pytest

from src.adapters.llm.ollama_adapter import OllamaEmbedderAdapter, OllamaLLMAdapter
from src.adapters.vector_stores.chroma_store import ChromaVectorStore
from src.domain.models import Chunk, ChunkStrategy, RetrievalQuery, SearchResult


@pytest.fixture
def embedder() -> OllamaEmbedderAdapter:
    return OllamaEmbedderAdapter(model="nomic-embed-text")


@pytest.fixture
def llm() -> OllamaLLMAdapter:
    return OllamaLLMAdapter(model="llama3.2")


@pytest.fixture
def store(embedder: OllamaEmbedderAdapter) -> ChromaVectorStore:
    client = chromadb.EphemeralClient()
    return ChromaVectorStore(
        persist_path="/tmp/integration_chroma",
        embedder=embedder,
        default_strategy=ChunkStrategy.FIXED_SIZE,
        collection_prefix=f"integ_{uuid.uuid4().hex[:8]}",
        client=client,
    )


@pytest.mark.integration
def test_ollama_embedder_returns_vector_of_expected_dimension(
    embedder: OllamaEmbedderAdapter,
) -> None:
    # Arrange
    text = "El aprendizaje profundo es una rama del machine learning."

    # Act
    vector = embedder.embed(text)

    # Assert — nomic-embed-text produce vectores de 768 dimensiones
    assert isinstance(vector, list)
    assert len(vector) > 0
    assert all(isinstance(v, float) for v in vector)


@pytest.mark.integration
def test_ollama_llm_generates_nonempty_response(llm: OllamaLLMAdapter) -> None:
    # Arrange
    context = [
        SearchResult(
            chunk_id="note-001_0",
            note_id="note-001",
            content="El aprendizaje profundo usa redes neuronales artificiales.",
            score=0.9,
            rank=1,
        )
    ]

    # Act
    response = llm.generate("¿Qué es el aprendizaje profundo?", context)

    # Assert
    assert isinstance(response, str)
    assert len(response.strip()) > 0


@pytest.mark.integration
def test_full_pipeline_ingest_and_search(
    store: ChromaVectorStore,
) -> None:
    # Arrange — un conjunto mínimo de chunks
    chunks = [
        Chunk(
            id="note-ml_0",
            note_id="note-ml",
            content="El machine learning permite a los ordenadores aprender de datos.",
            strategy=ChunkStrategy.FIXED_SIZE,
            index=0,
            token_count=12,
        ),
        Chunk(
            id="note-dl_0",
            note_id="note-dl",
            content="Las redes neuronales profundas son la base del deep learning.",
            strategy=ChunkStrategy.FIXED_SIZE,
            index=0,
            token_count=11,
        ),
        Chunk(
            id="note-cooking_0",
            note_id="note-cooking",
            content="La paella valenciana se prepara con arroz, pollo y verduras.",
            strategy=ChunkStrategy.FIXED_SIZE,
            index=0,
            token_count=9,
        ),
    ]

    # Act — ingesta y búsqueda
    store.add_chunks(chunks)
    query = RetrievalQuery(query="redes neuronales deep learning", top_k=2)
    results = store.search(query)

    # Assert
    assert len(results) >= 1
    assert results[0].rank == 1
    assert results[0].score >= 0.0
    # El chunk de cooking no debe ser el primer resultado
    top_note_ids = [r.note_id for r in results]
    assert "note-cooking" not in top_note_ids[:1]
