"""Herramientas LangChain para el agente ReAct de Second Brain.

Cada tool es una factory function que recibe un caso de uso del dominio
y devuelve un Tool de LangChain listo para usar en el agente.
"""

import json
import logging
from collections.abc import Awaitable, Callable

from langchain.tools import Tool

from src.application.manage_notes import ManageNotes
from src.application.move_note import MoveNote
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy, SearchResult
from src.domain.ports import NoteNotFoundError, VaultWriteError, VectorStoreError

logger = logging.getLogger(__name__)

_CONTENT_PREVIEW_LIMIT = 800

ConfirmCallback = Callable[[str], Awaitable[bool]]
"""Callback inyectado que muestra al usuario un resumen de una escritura
propuesta (crear/editar nota) y devuelve True si la aprueba, False si la
cancela. Mantiene `tools.py` independiente del framework de UI (Chainlit)."""


def _truncate(content: str) -> str:
    """Recorta contenido largo para no saturar el diálogo de confirmación."""
    if len(content) <= _CONTENT_PREVIEW_LIMIT:
        return content
    return content[:_CONTENT_PREVIEW_LIMIT] + "\n[...contenido truncado...]"


def _safe_json_loads(s: str) -> dict:
    """json.loads tolerante a saltos de línea literales dentro de strings.

    Los LLMs generan frecuentemente JSON con \\n reales dentro de valores
    de string en lugar de la secuencia de escape \\\\n, lo que rompe el
    parser estándar.
    """
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Reescribir carácter a carácter escapando \\n dentro de strings JSON
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in s:
        if escaped:
            out.append(ch)
            escaped = False
        elif ch == "\\":
            out.append(ch)
            escaped = True
        elif ch == '"':
            out.append(ch)
            in_string = not in_string
        elif ch == "\n" and in_string:
            out.append("\\n")
        else:
            out.append(ch)
    return json.loads("".join(out))


def _unwrap_string_input(raw: str) -> str:
    """Extrae el valor si el LLM envuelve el input en JSON de un solo campo.

    Algunos LLMs entrenados con tool-calling nativo (p. ej. Groq/Llama)
    generan Action Input como '{"input": "texto"}' aunque la herramienta
    espera un string plano. Sin este desenvolvimiento, ese JSON crudo se
    usaría como query de búsqueda, produciendo siempre el mismo resultado
    genérico y llevando al agente a repetir la misma búsqueda en bucle.
    """
    stripped = raw.strip()
    if not stripped.startswith("{"):
        return raw
    try:
        data = _safe_json_loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return raw
    if isinstance(data, dict) and len(data) == 1:
        value = next(iter(data.values()))
        if isinstance(value, str):
            return value
    return raw


def create_search_tool(
    search_use_case: SearchNotes,
    strategy: ChunkStrategy,
    last_results: list[SearchResult] | None = None,
) -> Tool:
    """Crea la herramienta search_vault para el agente ReAct.

    Args:
        search_use_case: Caso de uso de búsqueda semántica.
        strategy: Estrategia de chunking activa.
        last_results: lista mutable donde se guardan (sustituyendo el
            contenido anterior) los SearchResult de la última búsqueda,
            para que la capa de presentación (Chainlit) pueda adjuntarlos
            como citas sin cambiar el contrato de retorno de esta tool.

    Returns:
        Tool de LangChain que busca en el vault de Obsidian.
    """

    def _search(query: str) -> str:
        query = _unwrap_string_input(query)
        try:
            results = search_use_case.execute_text(query, strategy=strategy)
            if last_results is not None:
                last_results.clear()
                last_results.extend(results)
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


def create_note_tool(
    manage_use_case: ManageNotes, confirm_action: ConfirmCallback
) -> Tool:
    """Crea la herramienta create_note para el agente ReAct.

    Args:
        manage_use_case: Caso de uso de gestión de notas.
        confirm_action: Callback que pide confirmación al usuario antes de
            escribir la nota. Obligatorio: crear notas sin pedir permiso es
            precisamente el comportamiento que esta tool debe evitar.

    Returns:
        Tool de LangChain (solo async) que crea notas nuevas en el vault.
    """

    async def _create(tool_input: str) -> str:
        try:
            data = _safe_json_loads(tool_input)
            title = data["title"]
            content = data["content"]
            tags = data.get("tags", [])
        except (json.JSONDecodeError, KeyError):
            return "Formato incorrecto. Usa JSON con campos: title, content, tags (opcional)"

        summary = (
            f"Crear nota nueva:\n\n"
            f"**Título:** {title}\n"
            f"**Tags:** {', '.join(tags) if tags else '(ninguno)'}\n\n"
            f"**Contenido:**\n{_truncate(content)}"
        )
        if not await confirm_action(summary):
            logger.info("create_note: creación cancelada por el usuario ('%s')", title)
            return "El usuario canceló la creación de la nota."

        try:
            note = manage_use_case.create(title, content, tags)
            logger.info("create_note: nota creada '%s'", note.id)
            return f"Nota creada: {note.id}"
        except VaultWriteError as exc:
            logger.error("create_note error: %s", exc, exc_info=True)
            return f"Error al crear la nota: {exc}"

    return Tool(
        name="create_note",
        func=None,
        coroutine=_create,
        description=(
            "Crea una nueva nota en el vault de Obsidian. "
            "El input debe ser un JSON con campos: "
            "title (str, requerido), content (str, requerido), "
            "tags (lista de strings, opcional). "
            "IMPORTANTE sobre tags: siempre que el usuario mencione un tema, "
            "categoría o pida explícitamente tags, inclúyelos en el campo "
            'JSON \'tags\' (ej. "tags": ["arquitectura", "microservicios"]). '
            "NUNCA escribas '#tag' dentro de content: los tags fuera del "
            "campo 'tags' no se guardan en el frontmatter y no son "
            "recuperables por categoría."
        ),
    )


def create_edit_tool(
    manage_use_case: ManageNotes, confirm_action: ConfirmCallback
) -> Tool:
    """Crea la herramienta edit_note para el agente ReAct.

    Args:
        manage_use_case: Caso de uso de gestión de notas.
        confirm_action: Callback que pide confirmación al usuario antes de
            escribir la edición. Obligatorio: editar notas sin pedir permiso
            es precisamente el comportamiento que esta tool debe evitar.

    Returns:
        Tool de LangChain (solo async) que edita notas existentes en el vault.
    """

    async def _edit(tool_input: str) -> str:
        try:
            data = _safe_json_loads(tool_input)
            note_id = data["note_id"]
            content = data["content"]
            tags = data.get("tags")
        except (json.JSONDecodeError, KeyError):
            return "Formato incorrecto. Usa JSON con campos: note_id, content, tags (opcional)"

        summary = (
            f"Editar nota existente:\n\n"
            f"**Nota:** {note_id}\n"
            f"**Tags a añadir:** {', '.join(tags) if tags else '(ninguno)'}\n\n"
            f"**Nuevo contenido:**\n{_truncate(content)}"
        )
        if not await confirm_action(summary):
            logger.info("edit_note: edición cancelada por el usuario ('%s')", note_id)
            return "El usuario canceló la edición de la nota."

        try:
            note = manage_use_case.update(note_id, content, tags)
            logger.info("edit_note: nota actualizada '%s'", note.id)
            return f"Nota actualizada: {note.id}"
        except NoteNotFoundError:
            return (
                f"La nota '{note_id}' no existe. "
                "Usa search_vault para encontrarla primero."
            )

    return Tool(
        name="edit_note",
        func=None,
        coroutine=_edit,
        description=(
            "Edita el contenido de una nota existente en el vault de Obsidian. "
            "IMPORTANTE: note_id debe ser el identificador exacto que aparece como "
            "'(nota: X)' en los resultados de search_vault, "
            "por ejemplo '01-proyectos/tfm/resumen'. "
            "Nunca uses el título en lenguaje natural como note_id. "
            "El input debe ser un JSON con campos: "
            "note_id (str, ruta exacta obtenida de search_vault), "
            "content (str, nuevo contenido completo de la nota — "
            "NO incluyas marcadores de búsqueda como '(nota: X, score: Y)'), "
            "tags (lista de strings, opcional). "
            "IMPORTANTE sobre tags: si el usuario pide añadir tags a esta "
            "nota, inclúyelos en el campo JSON 'tags' — se SUMAN a los tags "
            "que ya tiene la nota, no los reemplazan. "
            "NUNCA escribas '#tag' dentro de content."
        ),
    )


def create_list_folders_tool(move_use_case: MoveNote) -> Tool:
    """Crea la herramienta list_folders para el agente ReAct.

    Args:
        move_use_case: Caso de uso de movimiento de notas.

    Returns:
        Tool de LangChain (síncrona) que lista las carpetas existentes
        del vault, para que el agente nunca invente un destino en
        move_note.
    """

    def _list(_tool_input: str = "") -> str:
        folders = move_use_case.list_folders()
        if not folders:
            return "El vault no tiene ninguna subcarpeta todavía."
        return "\n".join(f"- {folder}" for folder in folders)

    return Tool(
        name="list_folders",
        func=_list,
        description=(
            "Lista las carpetas que ya existen en el vault. Llama a esta "
            "herramienta ANTES de move_note para saber qué destinos son "
            "válidos: move_note rechaza cualquier carpeta que no aparezca "
            "aquí. El input se ignora."
        ),
    )


def create_move_tool(move_use_case: MoveNote, confirm_action: ConfirmCallback) -> Tool:
    """Crea la herramienta move_note para el agente ReAct.

    Args:
        move_use_case: Caso de uso de movimiento de notas.
        confirm_action: Callback que pide confirmación al usuario antes de
            mover la nota. Obligatorio: mover notas sin pedir permiso es
            precisamente el comportamiento que esta tool debe evitar.

    Returns:
        Tool de LangChain (solo async) que mueve una nota a otra carpeta
        del vault, reindexándola y reenlazando sus backlinks entrantes.
    """

    async def _move(tool_input: str) -> str:
        try:
            data = _safe_json_loads(tool_input)
            note_id = data["note_id"]
            target_folder = data["target_folder"]
            reason = data.get("reason", "")
        except (json.JSONDecodeError, KeyError):
            return (
                "Formato incorrecto. Usa JSON con campos: "
                "note_id, target_folder, reason (opcional)"
            )

        valid_folders = move_use_case.list_folders()
        if target_folder.strip("/") not in valid_folders:
            return (
                f"'{target_folder}' no es una carpeta existente del vault. "
                f"Usa list_folders para ver las carpetas válidas: "
                f"{', '.join(valid_folders) if valid_folders else '(ninguna)'}"
            )

        inbound = move_use_case.find_inbound_links(note_id)
        relink_note = (
            f"Se reescribirán los enlaces [[...]] de {len(inbound)} nota(s): "
            f"{', '.join(inbound)}"
            if inbound
            else "Ninguna otra nota enlaza a esta."
        )
        summary = (
            f"Mover nota:\n\n"
            f"**Nota:** {note_id}\n"
            f"**Carpeta destino:** {target_folder}\n"
            f"**Motivo:** {reason or '(sin especificar)'}\n\n"
            f"{relink_note}"
        )
        if not await confirm_action(summary):
            logger.info(
                "move_note: movimiento cancelado por el usuario ('%s')", note_id
            )
            return "El usuario canceló el movimiento de la nota."

        try:
            result = move_use_case.execute(note_id, target_folder)
            logger.info("move_note: nota movida '%s' -> '%s'", note_id, result.note.id)
            summary_parts = [
                f"Nota movida: {result.old_id} -> {result.note.id} "
                f"({result.chunks_indexed} chunks indexados)."
            ]
            if result.relinked_notes:
                summary_parts.append(
                    f"Enlaces actualizados en: {', '.join(result.relinked_notes)}."
                )
            if result.failed_relinks:
                summary_parts.append(
                    f"No se pudieron actualizar los enlaces en: "
                    f"{', '.join(result.failed_relinks)}."
                )
            return " ".join(summary_parts)
        except NoteNotFoundError:
            return (
                f"La nota '{note_id}' no existe. "
                "Usa search_vault para encontrarla primero."
            )
        except VaultWriteError as exc:
            logger.error("move_note error: %s", exc, exc_info=True)
            return f"Error al mover la nota: {exc}"

    return Tool(
        name="move_note",
        func=None,
        coroutine=_move,
        description=(
            "Mueve una nota existente a otra carpeta del vault. Llama "
            "primero a list_folders para conocer los destinos válidos: "
            "esta herramienta rechaza cualquier carpeta que no exista ya. "
            "El input debe ser un JSON con campos: "
            "note_id (str, ruta exacta obtenida de search_vault), "
            "target_folder (str, una de las carpetas de list_folders), "
            "reason (str, opcional, por qué encaja mejor en esa carpeta). "
            "Muestra un diálogo de confirmación al usuario antes de mover "
            "nada; si lo cancela, no reintentes en el mismo turno."
        ),
    )
