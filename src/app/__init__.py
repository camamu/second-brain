"""Chainlit entrypoint — Obsidian RAG Agent."""

import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path

import chainlit as cl
from chainlit.element import Element
from chainlit.input_widget import InputWidget, Select
from langchain.agents import AgentExecutor

from src.agent.agent import create_agent
from src.application.ingest_vault import IngestVault
from src.application.manage_notes import ManageNotes
from src.application.prune_orphans import PruneOrphans
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy, ImportConflictPolicy, SearchResult
from src.domain.ports import ObsidianRagError, VaultWriteError
from src.infrastructure.config import (
    get_chunker,
    get_langchain_llm,
    get_max_import_size_mb,
    get_note_loader,
    get_note_writer,
    get_strategy_from_env,
    get_vector_store,
    is_readonly,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_RESET_COMMANDS = {"/reset", "/clear", "/borrar historial"}
_PRUNE_COMMANDS = {"/prune", "/limpiar huerfanos", "/limpiar huérfanos"}


def _dedup_note_ids(results: list[SearchResult]) -> list[str]:
    """Devuelve los note_id únicos de los resultados, en orden de aparición."""
    seen: set[str] = set()
    ids: list[str] = []
    for r in results:
        if r.note_id not in seen:
            seen.add(r.note_id)
            ids.append(r.note_id)
    return ids


def _build_citation_elements(results: list[SearchResult]) -> list[cl.Text]:
    """Convierte SearchResult reales en elementos de fuente nativos de Chainlit.

    Deduplica por note_id: si varios chunks citados pertenecen a la misma
    nota, solo se adjunta un elemento por nota.
    """
    by_note_id = {r.note_id: r for r in results}
    elements: list[cl.Text] = []
    for note_id in _dedup_note_ids(results):
        r = by_note_id[note_id]
        elements.append(
            cl.Text(
                name=r.note_id,
                content=(
                    f"**Ruta:** `{r.note_id}`\n\n"
                    f"**Score:** {r.score:.2f}\n\n---\n\n{r.content}"
                ),
                display="page",
            )
        )
    return elements


def _build_sources_footer(results: list[SearchResult]) -> str:
    """Genera un pie de mensaje con los note_id exactos de las fuentes.

    Chainlit solo renderiza un elemento con display="page" como chip
    clicable si su `name` (el note_id) aparece literalmente en el
    contenido del mensaje; el texto libre generado por el LLM casi nunca
    lo incluye, así que este pie garantiza esa coincidencia de forma
    determinista.
    """
    note_ids = _dedup_note_ids(results)
    if not note_ids:
        return ""
    return "\n\n**Fuentes:** " + " ".join(note_ids)


async def _reset_history(agent: AgentExecutor) -> None:
    """Borra la memoria de conversación del agente y confirma al usuario."""
    if agent.memory is not None:
        agent.memory.clear()
    await cl.Message(
        content="Historial de conversación borrado. Puedes empezar de nuevo."
    ).send()


async def _confirm_write_action(summary: str) -> bool:
    """Pide confirmación al usuario antes de que el agente cree o edite una nota.

    Inyectada en `create_agent` como `confirm_action`; la llaman las tools
    create_note/edit_note (`src/agent/tools.py`) antes de escribir en el
    vault. Mismo patrón que `_confirm_and_prune`.
    """
    res = await cl.AskActionMessage(
        content=f"{summary}\n\n¿Confirmas esta acción?",
        actions=[
            cl.Action(name="confirm", payload={"confirm": True}, label="Confirmar"),
            cl.Action(name="cancel", payload={"confirm": False}, label="Cancelar"),
        ],
        timeout=60,
    ).send()

    return res is not None and bool(res["payload"].get("confirm"))


async def _confirm_and_prune(prune: PruneOrphans) -> None:
    """Detecta chunks huérfanos, pide confirmación y los borra si se acepta."""
    orphans = prune.find_orphans()
    if not orphans:
        await cl.Message(
            content="No se encontraron notas huérfanas en el índice."
        ).send()
        return

    listing = "\n".join(f"- {note_id}" for note_id in orphans)
    res = await cl.AskActionMessage(
        content=(
            f"Se encontraron {len(orphans)} nota(s) huérfana(s) en el índice "
            f"(ya no existen en el vault):\n{listing}\n\n¿Confirmas el borrado?"
        ),
        actions=[
            cl.Action(
                name="confirm", payload={"confirm": True}, label="Confirmar borrado"
            ),
            cl.Action(name="cancel", payload={"confirm": False}, label="Cancelar"),
        ],
        timeout=60,
    ).send()

    if res is None or not res["payload"].get("confirm"):
        await cl.Message(content="Borrado cancelado.").send()
        return

    deleted = prune.execute(orphans)
    await cl.Message(
        content=(
            f"Eliminados chunks de {len(deleted)} nota(s) huérfana(s): "
            f"{', '.join(deleted)}"
        )
    ).send()


async def _ask_import_conflict(filename: str) -> ImportConflictPolicy | None:
    """Pregunta cómo resolver un note_id ya existente al importar `filename`.

    Returns:
        La política elegida, o None si el usuario cancela.
    """
    res = await cl.AskActionMessage(
        content=f"Ya existe una nota para **{filename}**. ¿Qué quieres hacer?",
        actions=[
            cl.Action(
                name="overwrite",
                payload={"resolution": "overwrite"},
                label="Sobrescribir",
            ),
            cl.Action(
                name="copy", payload={"resolution": "copy"}, label="Importar como copia"
            ),
            cl.Action(
                name="cancel", payload={"resolution": "cancel"}, label="Cancelar"
            ),
        ],
        timeout=60,
    ).send()

    if res is None:
        return None
    resolution = res["payload"].get("resolution")
    if resolution == "overwrite":
        return ImportConflictPolicy.OVERWRITE
    if resolution == "copy":
        return ImportConflictPolicy.COPY
    return None


async def _import_one_md(manage_notes: ManageNotes, filename: str, raw: str) -> str:
    """Importa un único .md, resolviendo el conflicto de note_id si aplica.

    Reintenta con la política elegida por el usuario cuando `import_markdown`
    señala un conflicto (VaultWriteError con policy=FAIL, el valor por defecto).
    """
    policy = ImportConflictPolicy.FAIL
    while True:
        try:
            note, chunks = await asyncio.to_thread(
                manage_notes.import_markdown, filename, raw, policy
            )
            return f"- **{filename}** → `{note.id}` ({chunks} chunks indexados)."
        except VaultWriteError:
            resolution = await _ask_import_conflict(filename)
            if resolution is None:
                return f"- **{filename}**: importación cancelada (ya existía)."
            policy = resolution


async def _handle_md_import(
    manage_notes: ManageNotes | None, elements: Sequence[Element]
) -> None:
    """Importa los .md adjuntos a un mensaje al vault persistente.

    Respeta la misma guarda de solo lectura que `/prune`: si `manage_notes`
    es None (READONLY_MODE=true), informa y no procesa nada.
    """
    if manage_notes is None:
        await cl.Message(
            content="Esta acción no está disponible en modo solo lectura."
        ).send()
        return

    md_elements = [el for el in elements if (el.name or "").lower().endswith(".md")]
    if not md_elements:
        return

    max_bytes = get_max_import_size_mb() * 1024 * 1024
    summaries: list[str] = []
    for element in md_elements:
        path = Path(element.path) if element.path else None
        if path is None or not path.exists():
            summaries.append(
                f"- **{element.name}**: no se pudo leer el fichero adjunto."
            )
            continue

        if path.stat().st_size > max_bytes:
            summaries.append(
                f"- **{element.name}**: supera el límite de "
                f"{get_max_import_size_mb()} MB, no se importó."
            )
            continue

        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            summaries.append(f"- **{element.name}**: no es texto UTF-8 válido.")
            continue

        summaries.append(await _import_one_md(manage_notes, element.name, raw))

    await cl.Message(content="\n".join(summaries)).send()


@cl.set_starters
async def set_starters(user: cl.User | None = None) -> list[cl.Starter]:
    """Sugerencias de prompt mostradas antes del primer mensaje."""
    return [
        cl.Starter(
            label="Resume mis notas de esta semana",
            message="Resume las notas que he creado o editado esta semana.",
        ),
        cl.Starter(
            label="¿Qué tareas tengo pendientes?",
            message="¿Qué tareas pendientes tengo apuntadas en mis notas?",
        ),
        cl.Starter(
            label="Busca menciones de un tema",
            message="Busca menciones de 'arquitectura hexagonal' en mis notas.",
        ),
    ]


async def _init_agent_session(
    strategy: ChunkStrategy, *, changed: bool = False
) -> None:
    """Construye chunker/store/agente para `strategy` y los guarda en la sesión.

    Reutilizada tanto por `on_chat_start` (arranque) como por
    `on_settings_update` (cambio de estrategia en caliente). `changed`
    controla el texto de los mensajes, ya que un cambio en caliente reinicia
    la memoria de conversación del agente (ver `create_agent`).

    Chainlit oculta la pantalla de bienvenida/starters en cuanto la sesión
    recibe su primer mensaje real (lista de mensajes no vacía en el
    frontend); no depende de ningún evento especial. Por eso el mensaje de
    carga se envía como primera acción de esta función, sin pasos previos
    que retrasen su llegada.
    """
    loading = cl.Message(
        content=(
            f"Cambiando a estrategia **{strategy.label}**..."
            if changed
            else f"Cargando estrategia **{strategy.label}**..."
        )
    )
    await loading.send()

    await cl.context.emitter.task_start()
    try:
        chunker = get_chunker(strategy)
        store = get_vector_store(strategy)
        loader = get_note_loader()
        writer = get_note_writer()
        # all_chunkers: las notas creadas/editadas desde el chat deben quedar
        # disponibles sin importar qué estrategia esté activa después.
        all_chunkers = [get_chunker(s) for s in ChunkStrategy]
        ingest_uc = IngestVault(
            loader=loader, chunker=chunker, store=store, all_chunkers=all_chunkers
        )
        search_uc = SearchNotes(store=store)
        manage_uc = ManageNotes(loader=loader, writer=writer, ingest=ingest_uc)
        llm = get_langchain_llm()
        readonly = is_readonly()
        last_search_results: list[SearchResult] = []
        agent = create_agent(
            llm=llm,
            search_use_case=search_uc,
            manage_use_case=manage_uc,
            strategy=strategy,
            readonly=readonly,
            last_results=last_search_results,
            confirm_action=None if readonly else _confirm_write_action,
        )
        cl.user_session.set("agent", agent)
        cl.user_session.set("last_search_results", last_search_results)
        cl.user_session.set("strategy", strategy)
        # Limpiar huérfanos borra datos indexados: no disponible en modo solo lectura.
        cl.user_session.set(
            "prune_orphans",
            None if readonly else PruneOrphans(loader=loader, store=store),
        )
        # Importar .md escribe en el vault: no disponible en modo solo lectura.
        cl.user_session.set("manage_notes", None if readonly else manage_uc)

        loading.content = (
            f"Estrategia actualizada a **{strategy.label}** "
            "(se reinició el historial de conversación)."
            if changed
            else f"Agente listo con estrategia **{strategy.label}**. "
            "¿En qué puedo ayudarte?"
        )
        await loading.update()
    except ObsidianRagError as e:
        logger.error("Error inicializando el agente: %s", e, exc_info=True)
        loading.content = f"Error al inicializar el agente: {e}"
        await loading.update()
    finally:
        await cl.context.emitter.task_end()


@cl.on_chat_start
async def on_chat_start() -> None:
    """Inicializa el agente al abrir una sesión de chat.

    La estrategia de chunking se toma de CHUNKER_STRATEGY (sin bloquear el
    arranque con una pregunta). Se entra directamente en la vista de chat
    (se salta la pantalla de bienvenida/starters, ver `_init_agent_session`)
    mostrando el mensaje de carga; la estrategia puede cambiarse luego desde
    el panel de Settings (⚙️).
    """
    strategy = get_strategy_from_env()
    await _init_agent_session(strategy)

    settings_widgets: list[InputWidget] = [
        Select(
            id="chunk_strategy",
            label="Estrategia de chunking",
            items={s.label: s.value for s in ChunkStrategy},
            initial_value=strategy.value,
        )
    ]
    await cl.ChatSettings(settings_widgets).send()

    await cl.context.emitter.set_commands(
        [
            {
                "id": "reset",
                "description": "Borra el historial de esta conversación",
                "icon": "history",
                "button": False,
                "persistent": False,
                "selected": False,
            },
            {
                "id": "prune",
                "description": (
                    "Elimina del índice las notas que ya no existen en el vault"
                ),
                "icon": "sparkles",
                "button": False,
                "persistent": False,
                "selected": False,
            },
        ]
    )


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """Reconstruye el agente si el usuario cambia la estrategia de chunking."""
    new_strategy = ChunkStrategy(settings["chunk_strategy"])
    if new_strategy != cl.user_session.get("strategy"):
        await _init_agent_session(new_strategy, changed=True)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Procesa un mensaje del usuario y devuelve la respuesta del agente."""
    agent = cl.user_session.get("agent")
    if agent is None:
        await cl.Message(
            content="La sesión no está inicializada. Por favor, recarga la página."
        ).send()
        return

    content = message.content.strip().lower()
    if message.command == "reset" or content in _RESET_COMMANDS:
        await _reset_history(agent)
        return

    if message.command == "prune" or content in _PRUNE_COMMANDS:
        prune = cl.user_session.get("prune_orphans")
        if prune is None:
            await cl.Message(
                content="Esta acción no está disponible en modo solo lectura."
            ).send()
            return
        await _confirm_and_prune(prune)
        return

    if message.elements:
        await _handle_md_import(cl.user_session.get("manage_notes"), message.elements)
        if not message.content.strip():
            return

    try:
        last_results = cl.user_session.get("last_search_results")
        if last_results is not None:
            last_results.clear()
        cb = cl.AsyncLangchainCallbackHandler()
        response = await agent.ainvoke(
            {"input": message.content},
            config={"callbacks": [cb]},
        )
        elements = _build_citation_elements(last_results) if last_results else []
        content = response["output"] + _build_sources_footer(last_results or [])
        await cl.Message(content=content, elements=elements).send()
    except ObsidianRagError as e:
        logger.error("Error del agente: %s", e, exc_info=True)
        await cl.Message(content=f"Error: {e}").send()
    except Exception as e:
        logger.error("Error inesperado: %s", e, exc_info=True)
        await cl.Message(
            content="Ocurrió un error inesperado. Consulta los logs para más detalles."
        ).send()
