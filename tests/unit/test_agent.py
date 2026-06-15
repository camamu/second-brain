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
