"""Caso de uso: mover una nota a otra carpeta del vault y reindexarla."""

import logging
from typing import List

from src.application.ingest_vault import IngestVault
from src.domain.models import MoveResult
from src.domain.obsidian_conventions import rewrite_wikilink_target
from src.domain.ports import NoteLoader, NoteWriter, ObsidianRagError, VectorStore

logger = logging.getLogger(__name__)


class MoveNote:
    """Mueve una nota entre carpetas, reindexando y reenlazando backlinks.

    Args:
        loader: Puerto para leer notas del vault.
        writer: Puerto para escribir/mover notas en el vault.
        store: Puerto de persistencia y búsqueda vectorial.
        ingest: Caso de uso de ingesta para reindexar tras el movimiento.
    """

    def __init__(
        self,
        loader: NoteLoader,
        writer: NoteWriter,
        store: VectorStore,
        ingest: IngestVault,
    ) -> None:
        self._loader = loader
        self._writer = writer
        self._store = store
        self._ingest = ingest

    def list_folders(self) -> List[str]:
        """Carpetas existentes en el vault, derivadas de los note_id actuales.

        No inventa carpetas: solo devuelve las que ya contienen al menos
        una nota, para que la tool del agente valide destinos contra algo
        real en vez de estructuras hardcodeadas.

        Returns:
            Carpetas únicas, ordenadas alfabéticamente. Las notas en la
            raíz del vault (sin carpeta) no aportan ninguna entrada.
        """
        folders = {
            note.id.rsplit("/", 1)[0]
            for note in self._loader.load_all()
            if "/" in note.id
        }
        return sorted(folders)

    def find_inbound_links(self, note_id: str) -> List[str]:
        """note_id de las notas que enlazan a `note_id` mediante [[wikilink]].

        Args:
            note_id: Identificador de la nota destino de los enlaces.

        Returns:
            note_id de las notas cuyo contenido contiene [[note_id]].
        """
        return [
            note.id for note in self._loader.load_all() if note_id in note.backlinks
        ]

    def execute(self, note_id: str, target_folder: str) -> MoveResult:
        """Mueve una nota, reindexa sus chunks y reescribe enlaces entrantes.

        Orden de operaciones (ver `implementation-plan.md`, sección 4.3):
        1. Detecta las notas que enlazan a `note_id` ANTES de moverla,
           porque tras el movimiento ese id deja de existir.
        2. Mueve el fichero físico (cambia el note_id).
        3. Borra del vector store los chunks bajo el note_id antiguo, en
           todas las estrategias de chunking.
        4. Reindexa la nota bajo su nuevo note_id, en todas las estrategias.
        5. Reescribe [[note_id]] -> [[nuevo_id]] en cada nota entrante,
           en modo best-effort: un fallo en una no aborta las demás.

        Args:
            note_id: Identificador de la nota a mover.
            target_folder: Carpeta destino, relativa a la raíz del vault.

        Returns:
            El resultado del movimiento con sus efectos colaterales.

        Raises:
            NoteNotFoundError: Si note_id no existe en el vault.
            VaultWriteError: Si target_folder no existe, queda fuera del
                vault, o ya hay un fichero con ese nombre en el destino.
        """
        inbound = self.find_inbound_links(note_id)

        note = self._writer.move(note_id, target_folder)
        self._store.delete_by_note(note_id)
        chunks_indexed = self._ingest.execute_single(note.id)

        relinked: List[str] = []
        failed: List[str] = []
        for linker_id in inbound:
            try:
                linker = self._loader.load_by_id(linker_id)
                new_content = rewrite_wikilink_target(linker.content, note_id, note.id)
                self._writer.update(linker_id, new_content, tags=None)
                self._ingest.execute_single(linker_id)
                relinked.append(linker_id)
            except ObsidianRagError:
                logger.error(
                    "No se pudo reenlazar '%s' tras mover '%s' a '%s'.",
                    linker_id,
                    note_id,
                    note.id,
                    exc_info=True,
                )
                failed.append(linker_id)

        logger.info(
            "Nota '%s' movida a '%s' (%d chunks, %d reenlazadas, %d fallidas).",
            note_id,
            note.id,
            chunks_indexed,
            len(relinked),
            len(failed),
        )
        return MoveResult(
            note=note,
            old_id=note_id,
            chunks_indexed=chunks_indexed,
            relinked_notes=relinked,
            failed_relinks=failed,
        )
