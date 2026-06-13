"""Chunker que enriquece el contenido con notas enlazadas (backlinks)."""

import logging
from typing import List

from src.domain.models import Chunk, ChunkStrategy, Note
from src.domain.ports import BaseChunker, NoteLoader

from .fixed_size import split_text

logger = logging.getLogger(__name__)

_MAX_CHARS = 2000
_LINKED_PREVIEW = 200


def _cut_at_word(text: str, limit: int) -> str:
    """Trunca el texto en el límite de palabra más cercano a `limit`.

    Args:
        text: Texto a truncar.
        limit: Número máximo de caracteres.

    Returns:
        Texto truncado sin cortar palabras a medias.
    """
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(None, 1)[0]
    return cut


class BacklinkAwareChunker(BaseChunker):
    """Enriquece el contenido de una nota con fragmentos de sus backlinks.

    Recibe un NoteLoader por inyección de dependencia: nunca instancia
    ObsidianLoader directamente, manteniendo el hexágono limpio.

    Attributes:
        loader: Puerto NoteLoader para cargar notas enlazadas.
    """

    def __init__(self, loader: NoteLoader) -> None:
        """Inicializa el chunker con un loader inyectado.

        Args:
            loader: Implementación de NoteLoader para resolver backlinks.
        """
        self._loader = loader

    def chunk(self, note: Note) -> List[Chunk]:
        """Genera un chunk enriquecido con contexto de notas enlazadas.

        Args:
            note: Nota a chunkear.

        Returns:
            Lista de Chunk; vacía si la nota no tiene contenido.
        """
        if not note.content:
            return []

        enriched = note.content
        linked_ids: List[str] = []

        for backlink_id in note.backlinks:
            if not self._loader.exists(backlink_id):
                continue
            linked = self._loader.load_by_id(backlink_id)
            preview = _cut_at_word(linked.content, _LINKED_PREVIEW)
            enriched += f"\n\n--- Nota enlazada: {linked.title} ---\n{preview}"
            linked_ids.append(backlink_id)

        metadata = {
            "tags": note.tags,
            "note_type": note.note_type.value,
            "path": note.path,
            "linked_notes": linked_ids,
        }

        if len(enriched) <= _MAX_CHARS:
            return [
                Chunk(
                    id=f"{note.id}_0",
                    note_id=note.id,
                    content=enriched,
                    strategy=ChunkStrategy.BACKLINK_AWARE,
                    index=0,
                    heading=None,
                    metadata=metadata,
                )
            ]

        # Texto enriquecido supera el límite: trocear con split compartido
        fragments = split_text(enriched, _MAX_CHARS, 0)
        chunks: List[Chunk] = []
        idx = 0
        for fragment in fragments:
            if len(fragment.strip()) < 10:
                continue
            chunks.append(
                Chunk(
                    id=f"{note.id}_{idx}",
                    note_id=note.id,
                    content=fragment,
                    strategy=ChunkStrategy.BACKLINK_AWARE,
                    index=idx,
                    heading=None,
                    metadata=metadata,
                )
            )
            idx += 1
        return chunks
