"""Adaptador de ingesta para vaults de Obsidian.

Implementa NoteLoader y NoteWriter usando el sistema de ficheros
y python-frontmatter para parsear/serializar el YAML frontmatter.
"""

import logging
import re
from pathlib import Path
from typing import List

import frontmatter

from src.domain.models import ImportConflictPolicy, Note, NoteType
from src.domain.obsidian_conventions import sanitize_filename
from src.domain.ports import NoteLoader, NoteNotFoundError, NoteWriter, VaultWriteError
from src.domain.tags import normalize_tags

logger = logging.getLogger(__name__)

_BACKLINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

_NOTE_TYPE_MAP: dict[str, NoteType] = {
    "doc": NoteType.DOC,
    "todo": NoteType.TODO,
    "meeting": NoteType.MEETING,
    "mindmap": NoteType.MINDMAP,
    "snippet": NoteType.SNIPPET,
}


class ObsidianLoader(NoteLoader, NoteWriter):
    """Lee y escribe notas Markdown de un vault de Obsidian.

    Attributes:
        vault_path: Ruta absoluta al directorio raíz del vault.
    """

    def __init__(self, vault_path: str) -> None:
        """Inicializa el loader con la ruta del vault.

        Args:
            vault_path: Ruta absoluta al vault de Obsidian.
        """
        self._vault = Path(vault_path)

    # ------------------------------------------------------------------
    # NoteLoader
    # ------------------------------------------------------------------

    def load_all(self) -> List[Note]:
        """Carga todas las notas .md del vault de forma recursiva.

        Returns:
            Lista de notas con frontmatter, tags y backlinks parseados.
        """
        return [self._parse(p) for p in sorted(self._vault.rglob("*.md"))]

    def load_by_id(self, note_id: str) -> Note:
        """Carga una nota por su ID (ruta relativa sin .md).

        Args:
            note_id: Ruta relativa desde el vault sin extensión.

        Returns:
            La nota parseada.

        Raises:
            NoteNotFoundError: Si el fichero no existe en el vault.
        """
        path = self._vault / f"{note_id}.md"
        if not path.exists():
            raise NoteNotFoundError(note_id)
        return self._parse(path)

    def exists(self, note_id: str) -> bool:
        """Comprueba si una nota existe en el vault.

        Args:
            note_id: Ruta relativa desde el vault sin extensión.

        Returns:
            True si el fichero .md existe en disco.
        """
        return (self._vault / f"{note_id}.md").exists()

    def load_by_tags(self, tags: List[str]) -> List[Note]:
        """Filtra notas por tags (OR logic).

        Args:
            tags: Lista de tags a filtrar.

        Returns:
            Notas que contienen al menos uno de los tags dados.
        """
        tag_set = set(tags)
        return [n for n in self.load_all() if tag_set & set(n.tags)]

    # ------------------------------------------------------------------
    # NoteWriter
    # ------------------------------------------------------------------

    def create(self, title: str, content: str, tags: List[str]) -> Note:
        """Crea una nueva nota en 00-inbox/.

        Args:
            title: Título de la nota (usado también para el slug del fichero).
            content: Contenido markdown de la nota.
            tags: Lista de tags a incluir en el frontmatter.

        Returns:
            La nota recién creada.

        Raises:
            VaultWriteError: Si ya existe un fichero con ese slug.
        """
        inbox = self._vault / "00-inbox"
        inbox.mkdir(parents=True, exist_ok=True)

        slug = sanitize_filename(title)
        path = inbox / f"{slug}.md"

        if path.exists():
            raise VaultWriteError(f"Ya existe una nota en '{path}'")

        post = frontmatter.Post(content, title=title, tags=normalize_tags(tags))
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
        return self._parse(path)

    def update(self, note_id: str, content: str, tags: List[str] | None = None) -> Note:
        """Actualiza el contenido de una nota preservando su frontmatter.

        Args:
            note_id: ID de la nota a actualizar.
            content: Nuevo contenido markdown.
            tags: Tags a añadir a los existentes (union, sin eliminarlos).
                None preserva los tags actuales sin cambios.

        Returns:
            La nota con el contenido actualizado.

        Raises:
            NoteNotFoundError: Si la nota no existe.
        """
        existing = self.load_by_id(note_id)
        path = Path(existing.path)
        raw = path.read_text(encoding="utf-8")
        post = frontmatter.loads(raw)
        post.content = content
        if tags is not None:
            post["tags"] = normalize_tags(existing.tags + tags)
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
        return self._parse(path)

    def create_raw(
        self,
        filename: str,
        raw_content: str,
        policy: ImportConflictPolicy = ImportConflictPolicy.FAIL,
    ) -> Note:
        """Escribe un documento .md preservando su frontmatter original.

        Args:
            filename: Nombre de fichero original; el note_id se deriva
                de su slug (misma función que usa `create`).
            raw_content: Contenido completo del documento, incluido su
                frontmatter YAML si lo tiene.
            policy: Qué hacer si el note_id resultante ya existe.

        Returns:
            La nota recién escrita.

        Raises:
            VaultWriteError: Si ya existe un fichero con ese slug y
                policy es FAIL.
        """
        inbox = self._vault / "00-inbox"
        inbox.mkdir(parents=True, exist_ok=True)

        slug = sanitize_filename(Path(filename).stem)
        path = inbox / f"{slug}.md"

        if path.exists():
            if policy == ImportConflictPolicy.FAIL:
                raise VaultWriteError(f"Ya existe una nota en '{path}'")
            if policy == ImportConflictPolicy.COPY:
                path = self._next_copy_path(inbox, slug)

        path.write_text(self._normalize_raw_tags(raw_content), encoding="utf-8")
        return self._parse(path)

    def move(self, note_id: str, target_folder: str) -> Note:
        """Mueve una nota a otra carpeta del vault, preservando su contenido.

        Args:
            note_id: Identificador de la nota a mover.
            target_folder: Carpeta destino, relativa a la raiz del vault
                (p. ej. "02-areas/rag"). Debe existir ya en el vault.

        Returns:
            La nota con su nuevo id y path, tras el movimiento.

        Raises:
            NoteNotFoundError: Si note_id no existe en el vault.
            VaultWriteError: Si target_folder no existe, queda fuera del
                vault, o ya hay un fichero con ese nombre en el destino.
        """
        existing = self.load_by_id(note_id)
        vault_root = self._vault.resolve()

        clean_folder = target_folder.strip("/")
        dest_dir = (self._vault / clean_folder).resolve()
        if not dest_dir.is_relative_to(vault_root):
            raise VaultWriteError(
                f"La carpeta destino '{target_folder}' está fuera del vault"
            )
        if not dest_dir.is_dir():
            raise VaultWriteError(f"La carpeta destino '{target_folder}' no existe")

        src = Path(existing.path)
        dest = dest_dir / src.name
        if dest == src:
            raise VaultWriteError(f"La nota '{note_id}' ya está en '{target_folder}'")
        if dest.exists():
            raise VaultWriteError(f"Ya existe una nota en '{dest}'")

        src.rename(dest)
        return self._parse(dest)

    # ------------------------------------------------------------------
    # Privado
    # ------------------------------------------------------------------

    @staticmethod
    def _next_copy_path(inbox: Path, slug: str) -> Path:
        """Encuentra el primer nombre libre `<slug>-N.md` en `inbox`."""
        n = 1
        while True:
            candidate = inbox / f"{slug}-{n}.md"
            if not candidate.exists():
                return candidate
            n += 1

    @staticmethod
    def _normalize_raw_tags(raw_content: str) -> str:
        """Normaliza los tags del frontmatter sin tocar el resto del documento.

        Si los tags ya están normalizados (o no hay tags), devuelve
        `raw_content` sin modificar para preservar el documento original
        byte a byte.
        """
        post = frontmatter.loads(raw_content)
        fm = dict(post.metadata)
        tags_raw = fm.get("tags", [])
        raw_list = list(tags_raw) if isinstance(tags_raw, list) else [str(tags_raw)]
        normalized = normalize_tags(raw_list)
        if normalized == raw_list:
            return raw_content
        post["tags"] = normalized
        return frontmatter.dumps(post)

    def _parse(self, path: Path) -> Note:
        """Parsea un fichero .md y devuelve una Note del dominio.

        Args:
            path: Ruta absoluta al fichero markdown.

        Returns:
            Note con todos los campos del dominio populados.
        """
        raw = path.read_text(encoding="utf-8")
        post = frontmatter.loads(raw)
        fm = dict(post.metadata)
        content = post.content

        if content and not content.strip():
            logger.warning(
                "Nota '%s' tiene contenido solo con espacios; normalizado a ''",
                path,
            )
            content = ""

        title: str = str(fm.get("title") or path.stem)

        tags_raw = fm.get("tags", [])
        raw_list = list(tags_raw) if isinstance(tags_raw, list) else [str(tags_raw)]
        tags: List[str] = normalize_tags(raw_list)

        type_str = str(fm.get("type", "")).lower()
        note_type = _NOTE_TYPE_MAP.get(type_str, NoteType.OTHER)

        created_at = str(fm["created_at"]) if "created_at" in fm else None
        updated_at = str(fm["updated_at"]) if "updated_at" in fm else None

        backlinks: List[str] = _BACKLINK_RE.findall(content)

        note_id = str(path.relative_to(self._vault).with_suffix(""))

        return Note(
            id=note_id,
            title=title,
            content=content,
            frontmatter=fm,
            tags=tags,
            backlinks=backlinks,
            note_type=note_type,
            path=str(path),
            created_at=created_at,
            updated_at=updated_at,
        )
