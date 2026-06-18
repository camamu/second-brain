"""Chainlit entrypoint — Obsidian RAG Agent."""

import logging

import chainlit as cl

from src.agent.agent import create_agent
from src.application.ingest_vault import IngestVault
from src.application.manage_notes import ManageNotes
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy
from src.domain.ports import ObsidianRagError
from src.infrastructure.config import (
    get_chunker,
    get_langchain_llm,
    get_note_loader,
    get_note_writer,
    get_vector_store,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        agent = create_agent(
            llm=llm,
            search_use_case=search_uc,
            manage_use_case=manage_uc,
            strategy=strategy,
        )
        cl.user_session.set("agent", agent)
        await cl.Message(
            content=f"Agente listo con estrategia **{strategy.label}**. ¿En qué puedo ayudarte?"
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
