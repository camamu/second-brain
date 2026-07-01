"""Caso de uso: indexar el vault completo o una nota individual."""

import logging
from typing import List

from src.domain.models import Chunk, Note
from src.domain.ports import BaseChunker, NoteLoader, VectorStore

logger = logging.getLogger(__name__)


class IngestVault:
    """Orquesta la ingesta del vault: carga notas, las chunkea y las indexa.

    Args:
        loader: Puerto para cargar notas del vault.
        chunker: Puerto para dividir notas en chunks.
        store: Puerto para persistir y buscar chunks vectorialmente.
    """

    def __init__(
        self,
        loader: NoteLoader,
        chunker: BaseChunker,
        store: VectorStore,
    ) -> None:
        self._loader = loader
        self._chunker = chunker
        self._store = store

    def execute(self) -> int:
        """Indexa todas las notas del vault.

        Returns:
            Número de chunks indexados. 0 si el vault está vacío.
        """
        notes: List[Note] = self._loader.load_all()
        if not notes:
            logger.warning("El vault no contiene notas; no se indexó nada.")
            return 0

        chunks: List[Chunk] = self._chunker.chunk_many(notes)
        if not chunks:
            logger.warning("El chunker no produjo chunks; no se indexó nada.")
            return 0

        self._store.add_chunks(chunks)
        logger.info(
            "Ingesta completa: %d notas -> %d chunks indexados.",
            len(notes),
            len(chunks),
        )
        return len(chunks)

    def execute_single(self, note_id: str) -> int:
        """Reindexar una sola nota (borra chunks anteriores primero).

        Args:
            note_id: Identificador de la nota a reindexar.

        Returns:
            Número de chunks indexados para esa nota.

        Raises:
            NoteNotFoundError: Si note_id no existe en el vault.
        """
        note: Note = self._loader.load_by_id(note_id)
        self._store.delete_by_note(note_id)
        chunks: List[Chunk] = self._chunker.chunk_many([note])
        self._store.add_chunks(chunks)
        logger.info(
            "Reindexación de '%s': %d chunks indexados.",
            note_id,
            len(chunks),
        )
        return len(chunks)
