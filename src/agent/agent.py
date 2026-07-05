"""Agente ReAct de Second Brain usando LangChain.

El agente orquesta las tres herramientas (search_vault, create_note, edit_note)
con un LLM y memoria de conversación para crear una experiencia conversacional
sobre el vault de Obsidian.
"""

import logging
from typing import Callable

from langchain.agents import AgentExecutor, create_react_agent
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseLanguageModel

from src.agent.tools import create_edit_tool, create_note_tool, create_search_tool
from src.application.manage_notes import ManageNotes
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy

logger = logging.getLogger(__name__)

_REACT_PROMPT_TEMPLATE = """\
Eres un asistente de segundo cerebro que ayuda a gestionar un vault de Obsidian.
Puedes buscar notas, crear nuevas notas y editar notas existentes.

Reglas:
- Usa search_vault ANTES de responder preguntas sobre el contenido del vault.
- El Action Input de search_vault debe ser SOLO el texto de la consulta en
  lenguaje natural, sin JSON, sin comillas ni llaves.
  Correcto: Action Input: arquitectura hexagonal
  Incorrecto: Action Input: {{"input": "arquitectura hexagonal"}}
- NUNCA repitas la misma consulta de búsqueda dos veces. Si ya llamaste a
  search_vault y tienes una Observation, responde con Final Answer usando
  esa información aunque no sea perfecta; no vuelvas a buscar lo mismo.
- FLUJO OBLIGATORIO PARA EDITAR: (1) llama search_vault UNA sola vez,
  (2) toma el note_id exacto del primer resultado: el valor entre "nota: " y ",",
  (3) llama edit_note INMEDIATAMENTE con ese note_id. No vuelvas a buscar.
- El campo content de edit_note debe contener SOLO el texto limpio de la nota.
  Nunca incluyas marcadores de búsqueda como "(nota: X, score: Y)" en el content.
- Responde en el idioma del usuario.
- Sé conciso y cita la nota fuente cuando sea relevante.
- Si ya tienes la respuesta y no necesitas otra herramienta, NO escribas la
  línea "Action:". Ve directo a "Thought: Tengo la respuesta final." seguido
  de "Final Answer:".
- Action debe ser SIEMPRE uno de los nombres exactos de {tool_names}. Nunca
  escribas una Action como "No se requiere ninguna acción" ni ninguna frase
  que no sea un nombre de herramienta.
- Las líneas "Observation" son mensajes internos de depuración, incluidos los
  que empiezan por "Formato incorrecto": NUNCA copies su contenido literal
  en tu Final Answer. Tu Final Answer siempre es una respuesta natural
  dirigida al usuario, jamás un mensaje de error ni instrucciones de formato.

Herramientas disponibles:
{tools}

Formato de respuesta OBLIGATORIO:

Thought: razona sobre qué acción tomar
Action: <nombre exacto de la herramienta, una de: {tool_names}>
Action Input: <input para la herramienta>
Observation: <resultado de la herramienta>
... (repite Thought/Action/Action Input/Observation si es necesario)
Thought: Tengo la respuesta final
Final Answer: <respuesta para el usuario>

Historial de conversación:
{chat_history}

Pregunta del usuario: {input}
{agent_scratchpad}"""

_REACT_PROMPT = PromptTemplate(
    input_variables=[
        "tools",
        "tool_names",
        "input",
        "agent_scratchpad",
        "chat_history",
    ],
    template=_REACT_PROMPT_TEMPLATE,
)

_PARSING_ERROR_TEMPLATE = (
    "[Mensaje interno para el agente, no es la respuesta al usuario]\n"
    "Cuando necesitas usar una herramienta:\n"
    "Thought: <razonamiento>\n"
    "Action: <una de estas herramientas: {tool_names}>\n"
    "Action Input: <texto de entrada>\n\n"
    "Cuando ya tienes la respuesta final:\n"
    "Thought: Tengo la respuesta final.\n"
    "Final Answer: <tu respuesta real al usuario; nunca copies este mensaje>"
)


def _build_parsing_error_handler(
    tool_names: list[str],
) -> Callable[[OutputParserException], str]:
    """Crea el manejador de errores de parseo del ReAct output parser.

    El mensaje generado incluye los nombres reales de las herramientas
    disponibles y advierte explícitamente al LLM de que no debe copiar este
    texto de corrección como si fuera su respuesta final al usuario.

    Args:
        tool_names: Nombres de las herramientas disponibles para el agente.

    Returns:
        Función que LangChain invoca con la excepción de parseo y devuelve
        el texto de la Observation.
    """
    message = _PARSING_ERROR_TEMPLATE.format(tool_names=", ".join(tool_names))

    def _handle_parsing_error(error: OutputParserException) -> str:  # noqa: ARG001
        return message

    return _handle_parsing_error


def create_agent(
    llm: BaseLanguageModel,
    search_use_case: SearchNotes,
    manage_use_case: ManageNotes,
    strategy: ChunkStrategy = ChunkStrategy.FIXED_SIZE,
    readonly: bool = False,
) -> AgentExecutor:
    """Construye el agente ReAct con las herramientas del vault.

    Args:
        llm: Modelo de lenguaje de LangChain (OllamaLLM o ChatGroq).
        search_use_case: Caso de uso de búsqueda semántica.
        manage_use_case: Caso de uso de gestión de notas.
        strategy: Estrategia de chunking para search_vault.
        readonly: Si True, solo incluye search_vault (sin create/edit).

    Returns:
        AgentExecutor listo para recibir preguntas del usuario.
    """
    search_tool = create_search_tool(search_use_case, strategy)
    if readonly:
        tools = [search_tool]
    else:
        tools = [
            search_tool,
            create_note_tool(manage_use_case),
            create_edit_tool(manage_use_case),
        ]

    memory = ConversationBufferWindowMemory(
        k=10,
        memory_key="chat_history",
        input_key="input",
    )

    agent = create_react_agent(llm=llm, tools=tools, prompt=_REACT_PROMPT)

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        handle_parsing_errors=_build_parsing_error_handler(
            [tool.name for tool in tools]
        ),
        max_iterations=10,
        early_stopping_method="force",
    )

    logger.info(
        "Agente ReAct creado: %d herramientas, estrategia=%s, readonly=%s",
        len(tools),
        strategy.value,
        readonly,
    )
    return executor
