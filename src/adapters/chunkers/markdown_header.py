"""Chunker basado en cabeceras markdown (## y ###)."""

import logging
import re
from typing import List, Optional, Tuple

from src.domain.models import Chunk, ChunkStrategy, Note
from src.domain.ports import BaseChunker

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)


def _split_by_headings(text: str) -> List[Tuple[Optional[str], str]]:
    """Divide el texto en secciones por cabeceras ## / ###.

    Args:
        text: Contenido markdown a dividir.

    Returns:
        Lista de tuplas (heading_text | None, section_content).
    """
    sections: List[Tuple[Optional[str], str]] = []
    last_end = 0
    current_heading: Optional[str] = None

    for match in _HEADING_RE.finditer(text):
        section_text = text[last_end : match.start()].strip()
        if section_text or current_heading is not None:
            sections.append((current_heading, section_text))
        current_heading = match.group(2).strip()
        last_end = match.end()

    tail = text[last_end:].strip()
    if tail or current_heading is not None:
        sections.append((current_heading, tail))

    return sections


class MarkdownHeaderChunker(BaseChunker):
    """Divide notas por cabeceras markdown de nivel ## y ###.

    Secciones con contenido menor a 10 caracteres se fusionan con
    la sección siguiente para respetar la invariante del dominio.
    """

    def chunk(self, note: Note) -> List[Chunk]:
        """Divide una nota por cabeceras markdown.

        Args:
            note: Nota a dividir.

        Returns:
            Lista de Chunk; vacía si la nota no tiene contenido.
        """
        if not note.content:
            return []

        sections = _split_by_headings(note.content)

        if not sections:
            sections = [(None, note.content)]

        metadata = {
            "tags": note.tags,
            "note_type": note.note_type.value,
            "path": note.path,
        }

        # Fusionar secciones con contenido < 10 chars con la siguiente
        merged: List[Tuple[Optional[str], str]] = []
        pending_heading: Optional[str] = None
        pending_content = ""

        for heading, content in sections:
            combined_heading = pending_heading if pending_content else heading
            combined_content = (
                (pending_content + "\n" + content).strip()
                if pending_content
                else content
            )

            if len(combined_content.strip()) < 10:
                logger.debug(
                    "Sección '%s' de '%s' con < 10 chars; fusionando con la siguiente",
                    heading,
                    note.id,
                )
                pending_heading = combined_heading
                pending_content = combined_content
            else:
                merged.append((combined_heading, combined_content))
                pending_heading = None
                pending_content = ""

        # Si queda pendiente, añadirlo al último chunk o como chunk propio
        if pending_content:
            if merged:
                last_heading, last_content = merged[-1]
                merged[-1] = (
                    last_heading,
                    (last_content + "\n" + pending_content).strip(),
                )
            else:
                merged.append((pending_heading, pending_content))

        chunks: List[Chunk] = []
        for idx, (heading, content) in enumerate(merged):
            if len(content.strip()) < 10:
                continue
            chunks.append(
                Chunk(
                    id=f"{note.id}_{idx}",
                    note_id=note.id,
                    content=content,
                    strategy=ChunkStrategy.MARKDOWN_HEADER,
                    index=idx,
                    heading=heading,
                    metadata=metadata,
                )
            )
        return chunks
