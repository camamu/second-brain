"""Tests unitarios para la factory del agente ReAct."""

from unittest.mock import MagicMock

import pytest
from langchain.agents import AgentExecutor
from langchain_community.llms.fake import FakeListLLM

from src.agent.agent import _REACT_PROMPT_TEMPLATE, create_agent
from src.application.manage_notes import ManageNotes
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy, SearchResult


def _make_fake_llm() -> FakeListLLM:
    return FakeListLLM(responses=["Final Answer: respuesta de prueba"])


async def _auto_confirm(_summary: str) -> bool:
    return True


def _make_search_result(rank: int = 1) -> SearchResult:
    return SearchResult(
        chunk_id=f"chunk-{rank}",
        note_id=f"notas/nota-{rank}.md",
        content=f"Contenido del chunk {rank}",
        score=0.9 - rank * 0.05,
        rank=rank,
    )


class TestCreateAgent:
    def test_create_agent_returns_agent_executor(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
            confirm_action=_auto_confirm,
        )

        assert isinstance(executor, AgentExecutor)

    def test_create_agent_has_three_tools(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
            confirm_action=_auto_confirm,
        )

        assert len(executor.tools) == 3

    def test_create_agent_tools_have_correct_names(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
            confirm_action=_auto_confirm,
            strategy=ChunkStrategy.MARKDOWN_HEADER,
        )

        tool_names = [t.name for t in executor.tools]
        assert tool_names == ["search_vault", "create_note", "edit_note"]

    def test_create_agent_uses_force_stopping_method(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
            confirm_action=_auto_confirm,
        )

        assert executor.early_stopping_method == "force"

    def test_create_agent_parsing_error_message_includes_final_answer(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
            confirm_action=_auto_confirm,
        )

        assert isinstance(executor.handle_parsing_errors, str)
        assert "Final Answer" in executor.handle_parsing_errors

    def test_react_prompt_includes_offer_to_save_new_information_rule(self):
        """El prompt debe instruir al agente a ofrecer guardar información
        que el usuario aporta tras un 'no tengo información', en vez de
        repetir la búsqueda con variaciones (bug de producción: el agente
        ignoraba el dato nuevo y volvía a llamar a search_vault)."""
        assert "OFRECER GUARDAR INFORMACIÓN NUEVA" in _REACT_PROMPT_TEMPLATE
        assert "NO llames a create_note en este turno" in _REACT_PROMPT_TEMPLATE

    def test_react_prompt_forbids_placeholder_content(self):
        """El prompt debe prohibir inventar contenido de relleno al crear o
        editar notas (bug de producción: el agente escribía placeholders
        tipo "el usuario proporcionará..." en vez de pedir el contenido
        real al usuario)."""
        assert "NUNCA INVENTES CONTENIDO" in _REACT_PROMPT_TEMPLATE
        assert "PROHIBIDAS" in _REACT_PROMPT_TEMPLATE

    def test_react_prompt_includes_follow_up_continuity_rule(self):
        """El prompt debe instruir al agente a interpretar la respuesta del
        usuario como continuación de su propia pregunta de seguimiento
        (bug de producción: tras preguntar por tags, el agente ignoraba la
        respuesta del usuario y disparaba una nueva search_vault)."""
        assert "CONTINUIDAD DE PREGUNTAS PROPIAS" in _REACT_PROMPT_TEMPLATE
        assert "NO lo trates como una nueva" in _REACT_PROMPT_TEMPLATE
        assert "consulta de search_vault" in _REACT_PROMPT_TEMPLATE

    def test_react_prompt_requires_double_bracket_wikilinks_for_note_links(self):
        """El prompt debe exigir la sintaxis wikilink [[note_id]] de Obsidian
        al enlazar notas, no corchete simple (bug de producción: el agente
        escribía [nota] en vez de [[nota]], por lo que ObsidianLoader nunca
        detectaba el backlink)."""
        assert "ENLAZAR NOTAS" in _REACT_PROMPT_TEMPLATE
        assert "[[note_id_exacto]]" in _REACT_PROMPT_TEMPLATE
        assert "NUNCA uses corchete simple" in _REACT_PROMPT_TEMPLATE

    def test_create_agent_forwards_last_results_to_search_tool(self):
        search_uc = MagicMock(spec=SearchNotes)
        search_uc.execute_text.return_value = [_make_search_result(1)]
        last_results: list[SearchResult] = []

        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=search_uc,
            manage_use_case=MagicMock(spec=ManageNotes),
            confirm_action=_auto_confirm,
            last_results=last_results,
        )
        search_tool = next(t for t in executor.tools if t.name == "search_vault")
        search_tool.func("query de prueba")

        assert len(last_results) == 1

    def test_create_agent_requires_confirm_action_when_not_readonly(self):
        """create_note/edit_note no deben poder existir sin un mecanismo de
        confirmación: omitir confirm_action debe ser un error, no un bypass
        silencioso."""
        with pytest.raises(ValueError):
            create_agent(
                llm=_make_fake_llm(),
                search_use_case=MagicMock(spec=SearchNotes),
                manage_use_case=MagicMock(spec=ManageNotes),
                confirm_action=None,
            )

    def test_create_agent_readonly_does_not_require_confirm_action(self):
        executor = create_agent(
            llm=_make_fake_llm(),
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=MagicMock(spec=ManageNotes),
            readonly=True,
        )

        assert len(executor.tools) == 1


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
            confirm_action=_auto_confirm,
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
            confirm_action=_auto_confirm,
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
            confirm_action=_auto_confirm,
        )

        result = executor.invoke({"input": "¿Qué es la arquitectura hexagonal?"})

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
            confirm_action=_auto_confirm,
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
            confirm_action=_auto_confirm,
        )

        result = executor.invoke({"input": "test"})

        assert result["output"] == "respuesta correcta"

    async def test_ainvoke_create_note_cancelled_does_not_write_and_stops(self):
        """Si el usuario cancela la confirmación de create_note, el agente
        no debe escribir la nota ni reintentar la misma acción: debe cerrar
        el turno con Final Answer reconociendo la cancelación."""
        manage_mock = MagicMock(spec=ManageNotes)
        llm = FakeListLLM(
            responses=[
                "Thought: voy a crear la nota.\n"
                "Action: create_note\n"
                'Action Input: {"title": "Nota nueva", "content": "contenido"}',
                "Thought: Tengo la respuesta final.\n"
                "Final Answer: entendido, no se creó la nota",
            ]
        )

        async def _reject(_summary: str) -> bool:
            return False

        executor = create_agent(
            llm=llm,
            search_use_case=MagicMock(spec=SearchNotes),
            manage_use_case=manage_mock,
            confirm_action=_reject,
        )

        result = await executor.ainvoke({"input": "crea una nota sobre X"})

        manage_mock.create.assert_not_called()
        assert result["output"] == "entendido, no se creó la nota"

    async def test_ainvoke_offers_to_save_info_user_provides_after_failed_search(
        self,
    ):
        """Reproduce el bug de producción: tras un 'no tengo información',
        si el usuario aporta un dato nuevo, el agente debe ofrecer guardarlo
        (sin llamar a search_vault ni create_note en ese turno) y solo crear
        la nota cuando el usuario confirma en un turno posterior. Ejercita
        el AgentExecutor real con memoria compartida entre tres turnos
        (search_vault -> ofrecimiento -> confirmación), verificando que la
        mecánica del agente soporta el flujo aunque el cumplimiento de la
        regla del prompt dependa del LLM real."""
        search_mock = MagicMock(spec=SearchNotes)
        search_mock.execute_text.return_value = []
        manage_mock = MagicMock(spec=ManageNotes)
        manage_mock.create.return_value = MagicMock(id="notas/manolo.md")

        llm = FakeListLLM(
            responses=[
                "Thought: necesito buscar.\n"
                "Action: search_vault\n"
                "Action Input: Manolo el del Bombo",
                "Thought: no hay resultados.\n"
                "Final Answer: Lo siento, no tengo información sobre eso.",
                "Thought: el usuario aportó un dato nuevo, no vuelvo a buscar.\n"
                "Final Answer: ¿Quieres que guarde esta información en una nota nueva?",
                "Thought: el usuario confirmó, creo la nota.\n"
                "Action: create_note\n"
                'Action Input: {"title": "Manolo el del Bombo", '
                '"content": "Es hincha de la selección española"}',
                "Thought: Tengo la respuesta final.\n"
                "Final Answer: Nota creada correctamente.",
            ]
        )

        executor = create_agent(
            llm=llm,
            search_use_case=search_mock,
            manage_use_case=manage_mock,
            confirm_action=_auto_confirm,
        )

        result1 = await executor.ainvoke({"input": "¿Quién es Manolo el del Bombo?"})
        assert "no tengo información" in result1["output"]
        search_mock.execute_text.assert_called_once()

        result2 = await executor.ainvoke(
            {"input": "Es un hincha de la selección española"}
        )
        assert "¿Quieres que guarde" in result2["output"]
        search_mock.execute_text.assert_called_once()  # no repitió la búsqueda
        manage_mock.create.assert_not_called()  # no creó nada todavía

        result3 = await executor.ainvoke({"input": "sí, guárdalo"})
        manage_mock.create.assert_called_once_with(
            "Manolo el del Bombo", "Es hincha de la selección española", []
        )
        assert result3["output"] == "Nota creada correctamente."
