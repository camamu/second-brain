"""Tests unitarios para las herramientas del agente ReAct."""

import json
from unittest.mock import MagicMock

from src.agent.tools import create_edit_tool, create_note_tool, create_search_tool
from src.application.manage_notes import ManageNotes
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy, SearchResult
from src.domain.ports import NoteNotFoundError, VectorStoreError


def _make_search_result(rank: int = 1) -> SearchResult:
    return SearchResult(
        chunk_id=f"chunk-{rank}",
        note_id=f"notas/nota-{rank}.md",
        content=f"Contenido del chunk {rank}",
        score=0.9 - rank * 0.05,
        rank=rank,
    )


def _make_note(note_id: str = "notas/nueva.md") -> MagicMock:
    note = MagicMock()
    note.id = note_id
    return note


class TestSearchTool:
    def test_search_tool_calls_search_use_case_with_query(self):
        search_uc = MagicMock(spec=SearchNotes)
        search_uc.execute_text.return_value = []
        tool = create_search_tool(search_uc, ChunkStrategy.FIXED_SIZE)

        tool.func("python async")

        search_uc.execute_text.assert_called_once_with(
            "python async", strategy=ChunkStrategy.FIXED_SIZE
        )

    def test_search_tool_formats_results_as_readable_string(self):
        search_uc = MagicMock(spec=SearchNotes)
        search_uc.execute_text.return_value = [
            _make_search_result(1),
            _make_search_result(2),
        ]
        tool = create_search_tool(search_uc, ChunkStrategy.FIXED_SIZE)

        result = tool.func("query")

        assert "[1]" in result
        assert "[2]" in result
        assert "notas/nota-1.md" in result
        assert "Contenido del chunk 1" in result
        assert "score:" in result

    def test_search_tool_unwraps_json_wrapped_query(self):
        """Bug de producción (HF Spaces): Groq/Llama envía Action Input como
        JSON ('{"input": "arquitectura hexagonal"}') en lugar de texto
        plano. Sin desenvolver, ese JSON crudo se usaba como query,
        produciendo siempre el mismo resultado genérico y llevando al
        agente a repetir la búsqueda en bucle hasta agotar el rate limit.
        """
        search_uc = MagicMock(spec=SearchNotes)
        search_uc.execute_text.return_value = []
        tool = create_search_tool(search_uc, ChunkStrategy.FIXED_SIZE)

        tool.func('{"input": "arquitectura hexagonal"}')

        search_uc.execute_text.assert_called_once_with(
            "arquitectura hexagonal", strategy=ChunkStrategy.FIXED_SIZE
        )

    def test_search_tool_returns_friendly_message_on_error(self):
        search_uc = MagicMock(spec=SearchNotes)
        search_uc.execute_text.side_effect = VectorStoreError("conexión fallida")
        tool = create_search_tool(search_uc, ChunkStrategy.FIXED_SIZE)

        result = tool.func("query")

        assert "Error al buscar" in result
        assert "conexión fallida" in result

    def test_search_tool_populates_last_results_with_real_search_results(self):
        search_uc = MagicMock(spec=SearchNotes)
        results = [_make_search_result(1), _make_search_result(2)]
        search_uc.execute_text.return_value = results
        last_results: list[SearchResult] = []
        tool = create_search_tool(search_uc, ChunkStrategy.FIXED_SIZE, last_results)

        tool.func("query")

        assert last_results == results

    def test_search_tool_clears_last_results_before_new_search(self):
        search_uc = MagicMock(spec=SearchNotes)
        search_uc.execute_text.return_value = [_make_search_result(1)]
        last_results: list[SearchResult] = [_make_search_result(9)]
        tool = create_search_tool(search_uc, ChunkStrategy.FIXED_SIZE, last_results)

        tool.func("query")

        assert len(last_results) == 1
        assert last_results[0].note_id == "notas/nota-1.md"

    def test_search_tool_works_without_last_results_param(self):
        search_uc = MagicMock(spec=SearchNotes)
        search_uc.execute_text.return_value = []
        tool = create_search_tool(search_uc, ChunkStrategy.FIXED_SIZE)

        result = tool.func("query")

        assert "No se encontraron" in result


class TestCreateNoteTool:
    def test_create_note_tool_parses_json_and_creates_note(self):
        manage_uc = MagicMock(spec=ManageNotes)
        manage_uc.create.return_value = _make_note("notas/nueva.md")
        tool = create_note_tool(manage_uc)
        payload = json.dumps({"title": "Mi nota", "content": "Contenido"})

        result = tool.func(payload)

        manage_uc.create.assert_called_once_with("Mi nota", "Contenido", [])
        assert "notas/nueva.md" in result

    def test_create_note_tool_returns_error_on_invalid_json(self):
        manage_uc = MagicMock(spec=ManageNotes)
        tool = create_note_tool(manage_uc)

        result = tool.func("esto no es json")

        assert "Formato incorrecto" in result
        manage_uc.create.assert_not_called()


class TestEditNoteTool:
    def test_edit_note_tool_parses_json_and_updates_note(self):
        manage_uc = MagicMock(spec=ManageNotes)
        manage_uc.update.return_value = _make_note("notas/existente.md")
        tool = create_edit_tool(manage_uc)
        payload = json.dumps(
            {"note_id": "notas/existente.md", "content": "Nuevo contenido"}
        )

        result = tool.func(payload)

        # Sin tags en el payload, se propaga None (preserva tags actuales)
        manage_uc.update.assert_called_once_with(
            "notas/existente.md", "Nuevo contenido", None
        )
        assert "notas/existente.md" in result

    def test_edit_note_tool_with_tags_propagates_to_use_case(self):
        manage_uc = MagicMock(spec=ManageNotes)
        manage_uc.update.return_value = _make_note("notas/existente.md")
        tool = create_edit_tool(manage_uc)
        payload = json.dumps(
            {
                "note_id": "notas/existente.md",
                "content": "Nuevo contenido",
                "tags": ["nuevo-tag"],
            }
        )

        result = tool.func(payload)

        manage_uc.update.assert_called_once_with(
            "notas/existente.md", "Nuevo contenido", ["nuevo-tag"]
        )
        assert "notas/existente.md" in result

    def test_edit_note_tool_returns_error_when_note_not_found(self):
        manage_uc = MagicMock(spec=ManageNotes)
        manage_uc.update.side_effect = NoteNotFoundError("nota no existe")
        tool = create_edit_tool(manage_uc)
        payload = json.dumps({"note_id": "notas/fantasma.md", "content": "contenido"})

        result = tool.func(payload)

        assert "no existe" in result
        assert "search_vault" in result
