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
    ChunkEmbedder,
    ChunkingError,
    ConfigError,
    ConversationalLLM,
    EmbeddingError,
    IEvaluationRepo,
    NoteLoader,
    NoteNotFoundError,
    NoteWriter,
    ObsidianRagError,
    VaultWriteError,
    VectorStore,
    VectorStoreError,
)

__all__ = [
    "BaseChunker",
    "Chunk",
    "ChunkEmbedder",
    "ChunkingError",
    "ChunkStrategy",
    "ConfigError",
    "ConversationalLLM",
    "EmbeddingError",
    "EvaluationResult",
    "EvaluationSample",
    "IEvaluationRepo",
    "Note",
    "NoteLoader",
    "NoteNotFoundError",
    "NoteType",
    "NoteWriter",
    "ObsidianRagError",
    "RetrievalQuery",
    "SearchResult",
    "VaultWriteError",
    "VectorStore",
    "VectorStoreError",
]
