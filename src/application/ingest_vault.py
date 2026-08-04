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
        chunker: Puerto para dividir notas en chunks. Usado por `execute()`
            (ingesta completa de una sola estrategia) y como fallback de
            `execute_single()` si no se proporciona `all_chunkers`.
        store: Puerto para persistir y buscar chunks vectorialmente.
        all_chunkers: Chunkers de todas las estrategias, usados solo por
            `execute_single()` para que una nota creada o editada
            interactivamente quede indexada en todas las colecciones,
            sin importar cuál esté activa en la UI. Si es None,
            `execute_single()` usa únicamente `chunker`.
    """

    def __init__(
        self,
        loader: NoteLoader,
        chunker: BaseChunker,
        store: VectorStore,
        all_chunkers: List[BaseChunker] | None = None,
    ) -> None:
        self._loader = loader
        self._chunker = chunker
        self._store = store
        self._all_chunkers = all_chunkers

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
        """Reindexar una nota en todas las estrategias de chunking disponibles.

        Borra los chunks anteriores de la nota en todas las colecciones
        (una sola vez) y luego la reindexa con cada chunker de
        `all_chunkers` (o solo con `chunker` si no se proporcionó ninguno),
        para que quede disponible sin importar qué estrategia esté activa
        en la UI.

        Args:
            note_id: Identificador de la nota a reindexar.

        Returns:
            Número total de chunks indexados para esa nota, sumando todas
            las estrategias.

        Raises:
            NoteNotFoundError: Si note_id no existe en el vault.
        """
        note: Note = self._loader.load_by_id(note_id)
        self._store.delete_by_note(note_id)

        chunkers = self._all_chunkers or [self._chunker]
        total = 0
        for chunker in chunkers:
            chunks: List[Chunk] = chunker.chunk_many([note])
            self._store.add_chunks(chunks)
            total += len(chunks)

        logger.info(
            "Reindexación de '%s': %d chunks indexados en %d estrategia(s).",
            note_id,
            total,
            len(chunkers),
        )
        return total
