"""Caso de uso: eliminar del vector store chunks de notas ya borradas."""

import logging
from typing import List, Optional

from src.domain.ports import NoteLoader, VectorStore

logger = logging.getLogger(__name__)


class PruneOrphans:
    """Sincroniza el vector store con las notas que existen en el vault.

    ChromaDB persiste de forma independiente al filesystem del vault: borrar
    un fichero .md a mano no elimina sus chunks indexados. Esta use case
    detecta esos huérfanos comparando el vault actual contra el índice.

    Args:
        loader: Puerto para listar las notas actuales del vault.
        store: Puerto de persistencia y búsqueda vectorial.
    """

    def __init__(self, loader: NoteLoader, store: VectorStore) -> None:
        self._loader = loader
        self._store = store

    def find_orphans(self) -> List[str]:
        """Detecta notas indexadas que ya no existen en el vault (sin borrar).

        Returns:
            Lista de note_id presentes en el índice pero ausentes del vault.
        """
        vault_ids = {note.id for note in self._loader.load_all()}
        indexed_ids = set(self._store.list_note_ids())
        return sorted(indexed_ids - vault_ids)

    def execute(self, orphans: Optional[List[str]] = None) -> List[str]:
        """Borra del vector store los chunks de notas huérfanas.

        Args:
            orphans: Lista ya detectada de note_id a borrar. Si es None,
                se detecta primero con find_orphans() (uso en CLI).

        Returns:
            Lista de note_id eliminados del vector store.
        """
        if orphans is None:
            orphans = self.find_orphans()

        for note_id in orphans:
            self._store.delete_by_note(note_id)
            logger.info("Chunks huérfanos eliminados para nota '%s'.", note_id)

        return orphans
