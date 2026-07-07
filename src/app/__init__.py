"""Chainlit entrypoint — Obsidian RAG Agent."""

import logging

import chainlit as cl
from langchain.agents import AgentExecutor

from src.agent.agent import create_agent
from src.application.ingest_vault import IngestVault
from src.application.manage_notes import ManageNotes
from src.application.prune_orphans import PruneOrphans
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy
from src.domain.ports import ObsidianRagError
from src.infrastructure.config import (
    get_chunker,
    get_langchain_llm,
    get_note_loader,
    get_note_writer,
    get_vector_store,
    is_readonly,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_RESET_COMMANDS = {"/reset", "/clear", "/borrar historial"}
_PRUNE_COMMANDS = {"/prune", "/limpiar huerfanos", "/limpiar huérfanos"}


async def _reset_history(agent: AgentExecutor) -> None:
    """Borra la memoria de conversación del agente y confirma al usuario."""
    if agent.memory is not None:
        agent.memory.clear()
    await cl.Message(
        content="Historial de conversación borrado. Puedes empezar de nuevo."
    ).send()


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


@cl.action_callback("reset_history")
async def on_reset_history_action(action: cl.Action) -> None:
    """Maneja el clic en el botón de borrar historial."""
    agent = cl.user_session.get("agent")
    if agent is None:
        await cl.Message(
            content="La sesión no está inicializada. Por favor, recarga la página."
        ).send()
        return
    await _reset_history(agent)


@cl.action_callback("prune_orphans")
async def on_prune_orphans_action(action: cl.Action) -> None:
    """Maneja el clic en el botón de limpiar huérfanos."""
    prune = cl.user_session.get("prune_orphans")
    if prune is None:
        await cl.Message(
            content="Esta acción no está disponible en modo solo lectura."
        ).send()
        return
    await _confirm_and_prune(prune)


@cl.on_chat_start
async def on_chat_start() -> None:
    """Inicializa el agente al abrir una sesión de chat."""
    actions = [
        cl.Action(
            name="fixed",
            payload={"strategy": "fixed"},
            label="Chunking por tamaño fijo",
        ),
        cl.Action(
            name="markdown",
            payload={"strategy": "markdown"},
            label="Chunking por cabeceras Markdown",
        ),
        cl.Action(
            name="backlink",
            payload={"strategy": "backlink"},
            label="Chunking por backlinks",
        ),
    ]
    res = await cl.AskActionMessage(
        content="¿Qué estrategia de chunking quieres usar?",
        actions=actions,
        timeout=30,
    ).send()

    if res is None:
        strategy = ChunkStrategy.FIXED_SIZE
    else:
        strategy = ChunkStrategy(res["payload"]["strategy"])

    try:
        chunker = get_chunker(strategy)
        store = get_vector_store(strategy)
        loader = get_note_loader()
        writer = get_note_writer()
        ingest_uc = IngestVault(loader=loader, chunker=chunker, store=store)
        search_uc = SearchNotes(store=store)
        manage_uc = ManageNotes(loader=loader, writer=writer, ingest=ingest_uc)
        llm = get_langchain_llm()
        readonly = is_readonly()
        agent = create_agent(
            llm=llm,
            search_use_case=search_uc,
            manage_use_case=manage_uc,
            strategy=strategy,
            readonly=readonly,
        )
        cl.user_session.set("agent", agent)

        welcome_actions = [
            cl.Action(
                name="reset_history",
                payload={},
                label="🗑️ Borrar historial",
            )
        ]
        # Limpiar huérfanos borra datos indexados: se oculta en modo solo lectura.
        if not readonly:
            cl.user_session.set(
                "prune_orphans", PruneOrphans(loader=loader, store=store)
            )
            welcome_actions.append(
                cl.Action(
                    name="prune_orphans",
                    payload={},
                    label="🧹 Limpiar huérfanos",
                )
            )

        await cl.Message(
            content=f"Agente listo con estrategia **{strategy.label}**. ¿En qué puedo ayudarte?",
            actions=welcome_actions,
        ).send()
    except ObsidianRagError as e:
        logger.error("Error inicializando el agente: %s", e, exc_info=True)
        await cl.Message(content=f"Error al inicializar el agente: {e}").send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Procesa un mensaje del usuario y devuelve la respuesta del agente."""
    agent = cl.user_session.get("agent")
    if agent is None:
        await cl.Message(
            content="La sesión no está inicializada. Por favor, recarga la página."
        ).send()
        return

    if message.content.strip().lower() in _RESET_COMMANDS:
        await _reset_history(agent)
        return

    if message.content.strip().lower() in _PRUNE_COMMANDS:
        prune = cl.user_session.get("prune_orphans")
        if prune is None:
            await cl.Message(
                content="Esta acción no está disponible en modo solo lectura."
            ).send()
            return
        await _confirm_and_prune(prune)
        return

    try:
        cb = cl.AsyncLangchainCallbackHandler()
        response = await agent.ainvoke(
            {"input": message.content},
            config={"callbacks": [cb]},
        )
        await cl.Message(content=response["output"]).send()
    except ObsidianRagError as e:
        logger.error("Error del agente: %s", e, exc_info=True)
        await cl.Message(content=f"Error: {e}").send()
    except Exception as e:
        logger.error("Error inesperado: %s", e, exc_info=True)
        await cl.Message(
            content="Ocurrió un error inesperado. Consulta los logs para más detalles."
        ).send()
