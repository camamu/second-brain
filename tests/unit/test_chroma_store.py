"""Tests unitarios para ChromaVectorStore usando ChromaDB in-memory."""

import random
from typing import List

import chromadb
import pytest

from src.adapters.vector_stores.chroma_store import ChromaVectorStore
from src.domain.models import Chunk, ChunkStrategy, RetrievalQuery
from src.domain.ports import ChunkEmbedder


class FakeEmbedder(ChunkEmbedder):
    """Embedder determinista para tests: usa hash del texto como seed."""

    DIM = 8

    def embed(self, text: str) -> List[float]:
        rng = random.Random(hash(text) & 0xFFFFFFFF)
        return [rng.uniform(-1.0, 1.0) for _ in range(self.DIM)]

    def embed_many(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


_TEST_PREFIX = "obsidian_rag"


@pytest.fixture
def store(embedder: FakeEmbedder) -> ChromaVectorStore:
    # EphemeralClient en ChromaDB v0.6 comparte estado global entre instancias.
    # Borramos las colecciones del prefijo antes de cada test para partir de cero.
    client = chromadb.EphemeralClient()
    for name in list(client.list_collections()):
        if name.startswith(_TEST_PREFIX + "_"):
            client.delete_collection(name)
    return ChromaVectorStore(
        persist_path="/tmp/test_chroma",
        embedder=embedder,
        default_strategy=ChunkStrategy.FIXED_SIZE,
        collection_prefix=_TEST_PREFIX,
        client=client,
    )


def _make_chunk(
    note_id: str,
    idx: int,
    content: str,
    strategy: ChunkStrategy = ChunkStrategy.FIXED_SIZE,
) -> Chunk:
    return Chunk(
        id=f"{note_id}_{idx}",
        note_id=note_id,
        content=content,
        strategy=strategy,
        index=idx,
        token_count=len(content.split()),
        metadata={"tags": ["test"], "path": f"/vault/{note_id}.md"},
    )


# ─── tests ────────────────────────────────────────────────────────────────────


def test_chroma_store_add_chunks_persists_documents(
    store: ChromaVectorStore,
) -> None:
    # Arrange
    chunks = [_make_chunk("note-001", 0, "El aprendizaje profundo es fascinante.")]

    # Act
    store.add_chunks(chunks)

    # Assert
    assert store.count() == 1


def test_chroma_store_add_chunks_upserts_duplicates(
    store: ChromaVectorStore,
) -> None:
    # Arrange
    chunk = _make_chunk("note-001", 0, "Contenido original del chunk.")

    # Act — insertar dos veces el mismo ID
    store.add_chunks([chunk])
    store.add_chunks([chunk])

    # Assert — upsert: sigue habiendo solo 1
    assert store.count() == 1


def test_chroma_store_search_returns_ranked_results(
    store: ChromaVectorStore,
) -> None:
    # Arrange
    chunks = [
        _make_chunk("note-001", 0, "Redes neuronales y backpropagation en Python."),
        _make_chunk("note-002", 0, "Recetas de cocina mediterránea con aceite."),
        _make_chunk("note-003", 0, "Gradient descent y optimización de modelos."),
    ]
    store.add_chunks(chunks)
    query = RetrievalQuery(query="Redes neuronales", top_k=3)

    # Act
    results = store.search(query)

    # Assert
    assert len(results) >= 1
    assert results[0].rank == 1
    # Los ranks son consecutivos
    for i, r in enumerate(results):
        assert r.rank == i + 1


def test_chroma_store_search_respects_top_k(
    store: ChromaVectorStore,
) -> None:
    # Arrange
    chunks = [
        _make_chunk("note-001", i, f"Contenido de prueba número {i}.") for i in range(5)
    ]
    store.add_chunks(chunks)
    query = RetrievalQuery(query="Contenido de prueba", top_k=2)

    # Act
    results = store.search(query)

    # Assert
    assert len(results) <= 2


def test_chroma_store_search_uses_correct_collection_per_strategy(
    store: ChromaVectorStore,
) -> None:
    # Arrange — un chunk en fixed y otro en markdown
    chunk_fixed = _make_chunk(
        "note-001", 0, "Estrategia fixed size para chunking.", ChunkStrategy.FIXED_SIZE
    )
    chunk_md = _make_chunk(
        "note-002",
        0,
        "Estrategia markdown header para chunking.",
        ChunkStrategy.MARKDOWN_HEADER,
    )
    store.add_chunks([chunk_fixed])
    store.add_chunks([chunk_md])

    # Act — buscar solo en markdown
    query = RetrievalQuery(query="markdown chunking", top_k=5, strategy="markdown")
    results = store.search(query)

    # Assert — solo el chunk de markdown está en esa colección
    assert len(results) == 1
    assert results[0].chunk_id == "note-002_0"


def test_chroma_store_delete_by_note_removes_all_chunks(
    store: ChromaVectorStore,
) -> None:
    # Arrange — nota con 2 chunks en fixed + 1 chunk de otra nota
    chunks = [
        _make_chunk("note-target", 0, "Primer chunk de la nota a borrar."),
        _make_chunk("note-target", 1, "Segundo chunk de la nota a borrar."),
        _make_chunk("note-other", 0, "Chunk de otra nota que debe sobrevivir."),
    ]
    store.add_chunks(chunks)
    assert store.count() == 3

    # Act
    store.delete_by_note("note-target")

    # Assert
    assert store.count() == 1


def test_chroma_store_count_returns_total_across_collections(
    store: ChromaVectorStore,
) -> None:
    # Arrange — 2 chunks en fixed, 1 chunk en markdown
    store.add_chunks(
        [
            _make_chunk(
                "note-001",
                0,
                "Fixed chunk uno para prueba de count.",
                ChunkStrategy.FIXED_SIZE,
            ),
            _make_chunk(
                "note-001",
                1,
                "Fixed chunk dos para prueba de count.",
                ChunkStrategy.FIXED_SIZE,
            ),
            _make_chunk(
                "note-002",
                0,
                "Markdown chunk para prueba de count.",
                ChunkStrategy.MARKDOWN_HEADER,
            ),
        ]
    )

    # Act
    total = store.count()

    # Assert
    assert total == 3
