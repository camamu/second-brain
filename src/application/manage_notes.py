"""Caso de uso: crear, actualizar y obtener notas del vault."""

import logging

from src.application.ingest_vault import IngestVault
from src.domain.models import ImportConflictPolicy, Note
from src.domain.ports import NoteLoader, NoteWriter, VaultWriteError

logger = logging.getLogger(__name__)


class ManageNotes:
    """Orquesta la escritura de notas y su reindexación automática.

    Args:
        loader: Puerto para leer notas del vault.
        writer: Puerto para escribir notas en el vault.
        ingest: Caso de uso de ingesta para reindexar tras cada escritura.
    """

    def __init__(
        self,
        loader: NoteLoader,
        writer: NoteWriter,
        ingest: IngestVault,
    ) -> None:
        self._loader = loader
        self._writer = writer
        self._ingest = ingest

    def create(self, title: str, content: str, tags: list[str]) -> Note:
        """Crea una nueva nota y la indexa en el vector store.

        Args:
            title: Título de la nota.
            content: Contenido markdown.
            tags: Lista de tags para el frontmatter.

        Returns:
            La nota recién creada.
        """
        note = self._writer.create(title, content, tags)
        self._ingest.execute_single(note.id)
        logger.info("Nota '%s' creada y reindexada.", note.id)
        return note

    def update(self, note_id: str, content: str, tags: list[str] | None = None) -> Note:
        """Actualiza el contenido de una nota y la reindexar.

        Args:
            note_id: Identificador de la nota a actualizar.
            content: Nuevo contenido markdown.
            tags: Tags a añadir a los existentes (union, sin eliminarlos).
                None preserva los tags actuales sin cambios.

        Returns:
            La nota actualizada.
        """
        note = self._writer.update(note_id, content, tags)
        self._ingest.execute_single(note.id)
        logger.info("Nota '%s' actualizada y reindexada.", note.id)
        return note

    def import_markdown(
        self,
        filename: str,
        raw_content: str,
        policy: ImportConflictPolicy = ImportConflictPolicy.FAIL,
    ) -> tuple[Note, int]:
        """Importa un fichero .md existente al vault y lo indexa.

        A diferencia de `create`, es una acción determinista de UI (no
        pasa por el LLM) y preserva el frontmatter original del fichero
        en vez de reconstruirlo.

        Args:
            filename: Nombre de fichero original, tal como lo subió el
                usuario (debe terminar en .md).
            raw_content: Contenido completo del fichero, incluido su
                frontmatter YAML si lo tiene.
            policy: Qué hacer si ya existe una nota con el note_id
                resultante.

        Returns:
            Tupla (nota creada, número de chunks indexados en todas las
            estrategias de chunking).

        Raises:
            VaultWriteError: Si `filename` no termina en .md, o si el
                note_id ya existe y policy es FAIL.
        """
        if not filename.lower().endswith(".md"):
            raise VaultWriteError(f"Solo se admiten ficheros .md: '{filename}'")
        note = self._writer.create_raw(filename, raw_content, policy)
        chunks = self._ingest.execute_single(note.id)
        logger.info("Nota '%s' importada y reindexada (%d chunks).", note.id, chunks)
        return note, chunks

    def get(self, note_id: str) -> Note:
        """Obtiene una nota por su identificador.

        Args:
            note_id: Identificador de la nota.

        Returns:
            La nota cargada del vault.
        """
        return self._loader.load_by_id(note_id)
