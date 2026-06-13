"""Chunker de tamaño fijo con solapamiento."""

import logging
from typing import List

from src.domain.models import Chunk, ChunkStrategy, Note
from src.domain.ports import BaseChunker

logger = logging.getLogger(__name__)


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Divide un texto en fragmentos de tamaño fijo con solapamiento.

    Función de módulo reutilizable por BacklinkAwareChunker.

    Args:
        text: Texto a dividir.
        chunk_size: Número máximo de caracteres por fragmento.
        chunk_overlap: Número de caracteres de solapamiento entre fragmentos.

    Returns:
        Lista de fragmentos de texto.
    """
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    fragments: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        fragments.append(text[start:end])
        start += chunk_size - chunk_overlap
    return fragments


class FixedSizeChunker(BaseChunker):
    """Divide notas en fragmentos de tamaño fijo con solapamiento.

    Attributes:
        chunk_size: Número máximo de caracteres por chunk.
        chunk_overlap: Solapamiento en caracteres entre chunks consecutivos.
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50) -> None:
        """Inicializa el chunker con los parámetros de tamaño.

        Args:
            chunk_size: Tamaño máximo de cada chunk en caracteres.
            chunk_overlap: Solapamiento entre chunks consecutivos.
        """
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def chunk(self, note: Note) -> List[Chunk]:
        """Divide una nota en chunks de tamaño fijo.

        Args:
            note: Nota a dividir.

        Returns:
            Lista de Chunk; vacía si la nota no tiene contenido.
        """
        if not note.content:
            return []

        fragments = split_text(note.content, self._chunk_size, self._chunk_overlap)
        metadata = {
            "tags": note.tags,
            "note_type": note.note_type.value,
            "path": note.path,
        }

        chunks: List[Chunk] = []
        idx = 0
        for fragment in fragments:
            if len(fragment.strip()) < 10:
                logger.debug(
                    "Fragmento %d de '%s' descartado por ser < 10 chars",
                    idx,
                    note.id,
                )
                continue
            chunks.append(
                Chunk(
                    id=f"{note.id}_{idx}",
                    note_id=note.id,
                    content=fragment,
                    strategy=ChunkStrategy.FIXED_SIZE,
                    index=idx,
                    heading=None,
                    metadata=metadata,
                )
            )
            idx += 1
        return chunks
