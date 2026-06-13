"""Dominio del proyecto Second Brain.

Entidades, value objects y interfaces de dominio que definen
el nucleo de la aplicacion.

Modulos:
    models:  Datos, entidades y enumeraciones del dominio.
    ports:   Interfaces ABC para los adaptadores de infraestructura.
"""

from .models import (
    Chunk,
    ChunkStrategy,
    EvaluationResult,
    EvaluationSample,
    Note,
    NoteType,
    RetrievalQuery,
    SearchResult,
)
from .ports import (
    BaseChunker,
    ChunkingError,
    EmbeddingError,
    IEmbedder,
    IEvaluationRepo,
    ILLMChat,
    IVectorStore,
    NoteLoader,
    NoteNotFoundError,
    NoteWriter,
    ObsidianRagError,
    VaultWriteError,
    VectorStoreError,
)

__all__ = [
    "BaseChunker",
    "Chunk",
    "ChunkingError",
    "ChunkStrategy",
    "EmbeddingError",
    "EvaluationResult",
    "EvaluationSample",
    "IEmbedder",
    "IEvaluationRepo",
    "ILLMChat",
    "IVectorStore",
    "Note",
    "NoteLoader",
    "NoteNotFoundError",
    "NoteType",
    "NoteWriter",
    "ObsidianRagError",
    "RetrievalQuery",
    "SearchResult",
    "VaultWriteError",
    "VectorStoreError",
]
