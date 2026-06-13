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
    ChunkingError,
    EmbeddingError,
    IBaseChunker,
    IEmbedder,
    IEvaluationRepo,
    ILLMChat,
    IVaultReader,
    IVaultWriter,
    IVectorStore,
    NoteNotFoundError,
    ObsidianRagError,
    VaultWriteError,
    VectorStoreError,
)

__all__ = [
    "Chunk",
    "ChunkingError",
    "ChunkStrategy",
    "EmbeddingError",
    "EvaluationResult",
    "EvaluationSample",
    "IBaseChunker",
    "IEmbedder",
    "IEvaluationRepo",
    "ILLMChat",
    "IVectorStore",
    "IVaultReader",
    "IVaultWriter",
    "Note",
    "NoteNotFoundError",
    "NoteType",
    "ObsidianRagError",
    "RetrievalQuery",
    "SearchResult",
    "VaultWriteError",
    "VectorStoreError",
]
