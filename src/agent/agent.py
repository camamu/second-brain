"""Agente ReAct de Second Brain usando LangChain.

El agente orquesta las herramientas (search_vault, create_note, edit_note,
list_folders, move_note) con un LLM y memoria de conversación para crear una
experiencia conversacional sobre el vault de Obsidian.
"""

import logging

from langchain.agents import AgentExecutor, create_react_agent
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from langchain_core.language_models import BaseLanguageModel

from src.agent.tools import (
    ConfirmCallback,
    create_edit_tool,
    create_list_folders_tool,
    create_move_tool,
    create_note_tool,
    create_search_tool,
)
from src.application.manage_notes import ManageNotes
from src.application.move_note import MoveNote
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy, SearchResult

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
- OFRECER GUARDAR INFORMACIÓN NUEVA: si tu Final Answer anterior fue que no
  tienes información sobre un tema (search_vault no encontró nada relevante,
  aunque haya devuelto resultados de otros temas), y el usuario responde
  aportando él mismo información nueva y sustancial sobre ese mismo tema
  (una afirmación, no una instrucción para seguir buscando o reformular la
  consulta), NO llames a search_vault otra vez para ese tema: ya
  comprobaste que no está en el vault. En vez de eso, pasa directo a
  "Thought: Tengo la respuesta final." y en el Final Answer pregunta
  explícitamente si quiere que guardes esa información como una nota
  nueva. NO llames a create_note en este turno; espera la confirmación del
  usuario. Si en un turno posterior el usuario confirma, entonces sí llama
  a create_note, con un título derivado del tema y el content basado en la
  información que compartió (revisa el historial de conversación); si
  declina, reconócelo y no crees nada.
- NUNCA INVENTES CONTENIDO: nunca generes contenido de relleno
  (placeholder) para el campo content de create_note o edit_note —
  frases como "el usuario proporcionará..." o texto genérico inventado
  por ti están PROHIBIDAS. Si no tienes el texto real y completo que
  el usuario quiere guardar, aunque ya haya confirmado que quiere
  crear o editar la nota, NO llames a la tool todavía: pasa directo a
  "Thought: Tengo la respuesta final." y en el Final Answer pregunta
  explícitamente cuál es ese contenido. Espera la respuesta del
  usuario con el contenido real antes de llamar a create_note/edit_note.
- CONFIRMACIÓN AL EJECUTAR: create_note y edit_note ya muestran
  automáticamente un diálogo de confirmación al usuario antes de escribir
  nada. Cuando el usuario te ha pedido explícitamente crear o editar una
  nota (o cuando ya confirmó tras el ofrecimiento de la regla OFRECER
  GUARDAR INFORMACIÓN NUEVA), llama directamente a la tool sin volver a
  pedir permiso en texto — la aplicación ya se encarga de confirmar. La
  única vez que debes preguntar en el texto de tu respuesta antes de
  llamar a create_note es el escenario de OFRECER GUARDAR INFORMACIÓN
  NUEVA, donde eres tú quien detecta la oportunidad sin que el usuario lo
  haya pedido. Si la Observation indica que el usuario canceló la creación
  o edición, NO reintentes la misma acción: pasa directo a "Thought: Tengo
  la respuesta final." y responde con Final Answer reconociendo la
  cancelación.
- TAGS: si el usuario menciona un tema/categoría o pide tags al crear o editar
  una nota, ponlos SIEMPRE en el campo JSON "tags" de create_note/edit_note
  (lista de strings), NUNCA como "#tag" dentro de content. Los tags dentro de
  content no se guardan en el frontmatter y no sirven para categorizar la nota.
  En edit_note, los tags que pases se SUMAN a los existentes, no los reemplazan.
- ENLAZAR NOTAS: cuando el usuario pida enlazar, relacionar o vincular una
  nota con otra, escribe el enlace en el content de create_note/edit_note
  con la sintaxis wikilink de Obsidian de DOBLE corchete:
  [[note_id_exacto]] — el mismo note_id exacto (ruta sin extensión) que
  usas para note_id en edit_note, no el título en lenguaje natural.
  NUNCA uses corchete simple ni markdown estándar para esto.
  Correcto: Relacionado con [[00-inbox/cocción-de-huevos]]
  Incorrecto: Relacionado con [cocción de huevos]
  Un corchete simple no crea un enlace real: ObsidianLoader solo
  reconoce [[...]] para construir los backlinks de una nota, usados por
  la estrategia de chunking backlink.
- MOVER NOTAS: cuando el usuario pida mover una nota a otra carpeta, o
  cuando detectes que una nota de 00-inbox/ encajaría mejor en otra
  carpeta ya existente, llama SIEMPRE primero a list_folders para
  conocer las carpetas reales del vault — nunca inventes ni asumas un
  nombre de carpeta. Después llama a move_note con el note_id exacto
  (obtenido de search_vault) y una de las carpetas devueltas por
  list_folders. move_note ya muestra su propio diálogo de confirmación
  antes de mover nada, igual que create_note/edit_note: no pidas
  permiso en texto, llama directo a la tool. Si la Observation indica
  que el usuario canceló el movimiento, NO reintentes: pasa directo a
  "Thought: Tengo la respuesta final." y reconoce la cancelación.
- CONTINUIDAD DE PREGUNTAS PROPIAS: si tu Final Answer anterior formuló
  una pregunta de seguimiento al usuario (sobre contenido, tags,
  guardar, confirmar, etc.), interpreta el siguiente mensaje del
  usuario como la respuesta a esa pregunta pendiente — revisa el
  historial de conversación — antes de decidir si necesitas usar
  alguna otra herramienta. Por ejemplo, si preguntaste "¿quieres
  agregar tags?" y el usuario responde con una o pocas palabras (p.
  ej. "recetas"), trátalas como los tags a añadir y llama a edit_note
  con esos tags sobre la nota relevante; NO lo trates como una nueva
  consulta de search_vault.
- Responde en el idioma del usuario.
- Sé conciso y cita la nota fuente cuando sea relevante.
- Si ya tienes la respuesta y no necesitas otra herramienta, NO escribas la
  línea "Action:". Ve directo a "Thought: Tengo la respuesta final." seguido
  de "Final Answer:".

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


def create_agent(
    llm: BaseLanguageModel,
    search_use_case: SearchNotes,
    manage_use_case: ManageNotes,
    strategy: ChunkStrategy = ChunkStrategy.FIXED_SIZE,
    readonly: bool = False,
    last_results: list[SearchResult] | None = None,
    confirm_action: ConfirmCallback | None = None,
    move_use_case: MoveNote | None = None,
) -> AgentExecutor:
    """Construye el agente ReAct con las herramientas del vault.

    Args:
        llm: Modelo de lenguaje de LangChain (OllamaLLM o ChatGroq).
        search_use_case: Caso de uso de búsqueda semántica.
        manage_use_case: Caso de uso de gestión de notas.
        strategy: Estrategia de chunking para search_vault.
        readonly: Si True, solo incluye search_vault (sin create/edit/move).
        last_results: lista mutable reenviada a create_search_tool para
            capturar los SearchResult de la última búsqueda (ver tools.py).
        confirm_action: Callback que pide confirmación al usuario antes de
            crear, editar o mover una nota (ver
            `src.agent.tools.ConfirmCallback`). Obligatorio cuando
            `readonly=False`, ya que esas tools no deben poder escribir sin
            confirmación.
        move_use_case: Caso de uso de movimiento de notas. Si es None (por
            defecto), el agente no registra list_folders ni move_note,
            aunque `readonly=False` — permite mantener el resto de tests y
            llamadas existentes sin tocar esta funcionalidad.

    Returns:
        AgentExecutor listo para recibir preguntas del usuario.

    Raises:
        ValueError: si `readonly=False` y no se proporciona `confirm_action`.
    """
    search_tool = create_search_tool(search_use_case, strategy, last_results)
    if readonly:
        tools = [search_tool]
    else:
        if confirm_action is None:
            raise ValueError(
                "confirm_action es obligatorio cuando readonly=False: "
                "create_note/edit_note no deben ejecutarse sin confirmación "
                "del usuario."
            )
        tools = [
            search_tool,
            create_note_tool(manage_use_case, confirm_action),
            create_edit_tool(manage_use_case, confirm_action),
        ]
        if move_use_case is not None:
            tools.append(create_list_folders_tool(move_use_case))
            tools.append(create_move_tool(move_use_case, confirm_action))

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
        handle_parsing_errors=(
            "Formato incorrecto. Cuando necesitas usar una herramienta:\n"
            "Thought: <razonamiento>\n"
            "Action: <nombre_herramienta>\n"
            "Action Input: <texto_de_entrada>\n\n"
            "Cuando ya tienes la respuesta final:\n"
            "Thought: Tengo la respuesta final.\n"
            "Final Answer: <respuesta para el usuario>\n"
        ),
        max_iterations=10,
    )

    logger.info(
        "Agente ReAct creado: %d herramientas, estrategia=%s, readonly=%s",
        len(tools),
        strategy.value,
        readonly,
    )
    return executor
