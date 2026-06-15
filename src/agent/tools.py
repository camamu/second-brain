"""Herramientas LangChain para el agente ReAct de Second Brain.

Cada tool es una factory function que recibe un caso de uso del dominio
y devuelve un Tool de LangChain listo para usar en el agente.
"""

import json
import logging

from langchain.tools import Tool

from src.application.manage_notes import ManageNotes
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy
from src.domain.ports import NoteNotFoundError, VaultWriteError, VectorStoreError

logger = logging.getLogger(__name__)


def create_search_tool(
    search_use_case: SearchNotes,
    strategy: ChunkStrategy,
) -> Tool:
    """Crea la herramienta search_vault para el agente ReAct.

    Args:
        search_use_case: Caso de uso de búsqueda semántica.
        strategy: Estrategia de chunking activa.

    Returns:
        Tool de LangChain que busca en el vault de Obsidian.
    """

    def _search(query: str) -> str:
        try:
            results = search_use_case.execute_text(query, strategy=strategy)
            logger.info("search_vault: query='%s', resultados=%d", query, len(results))
            if not results:
                return "No se encontraron resultados para la consulta."
            lines = []
            for i, r in enumerate(results, 1):
                lines.append(f"[{i}] (nota: {r.note_id}, score: {r.score:.2f})")
                lines.append(r.content)
            return "\n".join(lines)
        except VectorStoreError as exc:
            logger.error("search_vault error: %s", exc, exc_info=True)
            return f"Error al buscar en el vault: {exc}"

    return Tool(
        name="search_vault",
        func=_search,
        description=(
            "Busca notas en el vault de Obsidian usando búsqueda semántica. "
            "Úsala cuando el usuario haga preguntas sobre el contenido de sus notas. "
            "El input es la consulta en lenguaje natural."
        ),
    )


def create_note_tool(manage_use_case: ManageNotes) -> Tool:
    """Crea la herramienta create_note para el agente ReAct.

    Args:
        manage_use_case: Caso de uso de gestión de notas.

    Returns:
        Tool de LangChain que crea notas nuevas en el vault.
    """

    def _create(tool_input: str) -> str:
        try:
            data = json.loads(tool_input)
            title = data["title"]
            content = data["content"]
            tags = data.get("tags", [])
        except (json.JSONDecodeError, KeyError):
            return "Formato incorrecto. Usa JSON con campos: title, content, tags (opcional)"
        try:
            note = manage_use_case.create(title, content, tags)
            logger.info("create_note: nota creada '%s'", note.id)
            return f"Nota creada: {note.id}"
        except VaultWriteError as exc:
            logger.error("create_note error: %s", exc, exc_info=True)
            return f"Error al crear la nota: {exc}"

    return Tool(
        name="create_note",
        func=_create,
        description=(
            "Crea una nueva nota en el vault de Obsidian. "
            "El input debe ser un JSON con campos: "
            "title (str, requerido), content (str, requerido), tags (lista, opcional)."
        ),
    )


def create_edit_tool(manage_use_case: ManageNotes) -> Tool:
    """Crea la herramienta edit_note para el agente ReAct.

    Args:
        manage_use_case: Caso de uso de gestión de notas.

    Returns:
        Tool de LangChain que edita notas existentes en el vault.
    """

    def _edit(tool_input: str) -> str:
        try:
            data = json.loads(tool_input)
            note_id = data["note_id"]
            content = data["content"]
        except (json.JSONDecodeError, KeyError):
            return "Formato incorrecto. Usa JSON con campos: note_id, content"
        try:
            note = manage_use_case.update(note_id, content)
            logger.info("edit_note: nota actualizada '%s'", note.id)
            return f"Nota actualizada: {note.id}"
        except NoteNotFoundError:
            return (
                f"La nota '{note_id}' no existe. "
                "Usa search_vault para encontrarla primero."
            )

    return Tool(
        name="edit_note",
        func=_edit,
        description=(
            "Edita el contenido de una nota existente en el vault de Obsidian. "
            "El input debe ser un JSON con campos: "
            "note_id (str, ruta de la nota), content (str, nuevo contenido completo)."
        ),
    )
