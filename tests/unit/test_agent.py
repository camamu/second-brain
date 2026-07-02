"""Tests unitarios para la factory del agente ReAct."""

from unittest.mock import MagicMock

from langchain.agents import AgentExecutor
from langchain_community.llms.fake import FakeListLLM

from src.agent.agent import create_agent
from src.application.manage_notes import ManageNotes
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy


def _make_fake_llm() -> FakeListLLM:
    return FakeListLLM(responses=["Final Answer: respuesta de prueba"])


class TestCreateAgent:
    def test_create_agent_returns_agent_executor(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
        )

        assert isinstance(executor, AgentExecutor)

    def test_create_agent_has_three_tools(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
        )

        assert len(executor.tools) == 3

    def test_create_agent_tools_have_correct_names(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
            strategy=ChunkStrategy.MARKDOWN_HEADER,
        )

        tool_names = [t.name for t in executor.tools]
        assert tool_names == ["search_vault", "create_note", "edit_note"]

    def test_create_agent_uses_force_stopping_method(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
        )

        assert executor.early_stopping_method == "force"

    def test_create_agent_parsing_error_message_includes_final_answer(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
        )

        assert isinstance(executor.handle_parsing_errors, str)
        assert "Final Answer" in executor.handle_parsing_errors


class TestAgentExecutorBehavior:
    """Tests de comportamiento que ejecutan el AgentExecutor con FakeListLLM."""

    def test_invoke_does_not_raise_when_llm_uses_action_none(self):
        """Bug de producción: LLM devuelve 'Action: None' en bucle.

        Con early_stopping_method='generate' esto terminaba en ValueError.
        Con 'force' el executor devuelve output sin explotar.
        """
        llm = FakeListLLM(
            responses=["Thought: tengo info.\nAction: None\nAction Input: None"]
        )

        executor = create_agent(
            llm=llm,
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
        )

        result = executor.invoke({"input": "¿qué es la arquitectura hexagonal?"})

        assert "output" in result

    def test_invoke_does_not_raise_on_max_iterations_exceeded(self):
        """El agente que siempre llama una herramienta agota max_iterations=5
        y debe retornar graciosamente en lugar de lanzar ValueError.
        """
        search_mock = MagicMock(spec=SearchNotes)
        search_mock.execute_text.return_value = []
        llm = FakeListLLM(
            responses=[
                "Thought: Necesito buscar.\nAction: search_vault\nAction Input: test"
            ]
        )

        executor = create_agent(
            llm=llm,
            search_use_case=search_mock,
            manage_use_case=MagicMock(spec=ManageNotes),
        )

        result = executor.invoke({"input": "¿qué es RAG?"})

        assert "output" in result

    def test_invoke_search_vault_receives_clean_query_despite_json_wrapped_input(
        self,
    ):
        """Bug de producción (HF Spaces): el LLM envía Action Input como
        JSON ('{"input": "arquitectura hexagonal"}') en lugar de texto
        plano, lo que hacía que search_vault buscara con el JSON crudo,
        obteniendo siempre el mismo resultado genérico y llevando al
        agente a repetir search_vault → ChatGroq → search_vault sin llegar
        a Final Answer, agotando el rate limit de Groq. El desenvolvimiento
        de JSON en la tool debe evitar que la query llegue sucia al caso de
        uso de búsqueda, incluso si el LLM sigue insistiendo con el mismo
        formato incorrecto en cada iteración.
        """
        search_mock = MagicMock(spec=SearchNotes)
        search_mock.execute_text.return_value = []
        llm = FakeListLLM(
            responses=[
                "Thought: necesito buscar.\n"
                "Action: search_vault\n"
                'Action Input: {"input": "arquitectura hexagonal"}'
            ]
        )

        executor = create_agent(
            llm=llm,
            search_use_case=search_mock,
            manage_use_case=MagicMock(spec=ManageNotes),
        )

        result = executor.invoke(
            {"input": "¿Qué es la arquitectura hexagonal?"}
        )

        assert "output" in result
        for call in search_mock.execute_text.call_args_list:
            assert call.args[0] == "arquitectura hexagonal"

    def test_invoke_recovers_from_mixed_action_and_final_answer(self):
        """Bug de producción: el LLM incluye un 'Action:'/'Action Input:'
        parseable Y un 'Final Answer:' en la misma respuesta (típico cuando
        ya tiene la información pero sigue redactando tras la observación).
        LangChain lanza OutputParserException ("produced both a final
        answer and a parse-able action"); el agente debe recuperarse en el
        siguiente turno usando la guía de handle_parsing_errors.
        """
        responses = [
            "Thought: ya tengo la información pero seré explícito.\n"
            "Action: search_vault\n"
            "Action Input: no hace falta\n"
            "Thought: Tengo la respuesta final.\n"
            "Final Answer: respuesta ignorada por formato mixto",
            "Thought: Tengo la respuesta final.\nFinal Answer: respuesta correcta",
        ]
        llm = FakeListLLM(responses=responses)

        executor = create_agent(
            llm=llm,
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
        )

        result = executor.invoke({"input": "¿qué es la arquitectura hexagonal?"})

        assert result["output"] == "respuesta correcta"

    def test_invoke_recovers_from_parsing_error_with_final_answer(self):
        """Tras un error de formato, el LLM recibe el mensaje de guía actualizado
        (que ahora incluye 'Final Answer:') y puede completar en el siguiente turno.
        """
        responses = [
            "solo texto sin formato correcto",
            "Thought: Tengo la respuesta.\nFinal Answer: respuesta correcta",
        ]
        llm = FakeListLLM(responses=responses)

        executor = create_agent(
            llm=llm,
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
        )

        result = executor.invoke({"input": "test"})

        assert result["output"] == "respuesta correcta"
