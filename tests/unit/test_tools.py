"""Tests unitarios para las herramientas del agente ReAct."""

import json
from unittest.mock import MagicMock

from src.agent.tools import (
    create_edit_tool,
    create_list_folders_tool,
    create_move_tool,
    create_note_tool,
    create_search_tool,
)
from src.application.manage_notes import ManageNotes
from src.application.move_note import MoveNote
from src.application.search_notes import SearchNotes
from src.domain.models import ChunkStrategy, MoveResult, SearchResult
from src.domain.ports import NoteNotFoundError, VaultWriteError, VectorStoreError


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


async def _approve(_summary: str) -> bool:
    return True


async def _reject(_summary: str) -> bool:
    return False


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
    async def test_create_note_tool_parses_json_and_creates_note(self):
        manage_uc = MagicMock(spec=ManageNotes)
        manage_uc.create.return_value = _make_note("notas/nueva.md")
        tool = create_note_tool(manage_uc, _approve)
        payload = json.dumps({"title": "Mi nota", "content": "Contenido"})

        result = await tool.coroutine(payload)

        manage_uc.create.assert_called_once_with("Mi nota", "Contenido", [])
        assert "notas/nueva.md" in result

    async def test_create_note_tool_returns_error_on_invalid_json(self):
        manage_uc = MagicMock(spec=ManageNotes)
        tool = create_note_tool(manage_uc, _approve)

        result = await tool.coroutine("esto no es json")

        assert "Formato incorrecto" in result
        manage_uc.create.assert_not_called()

    async def test_create_note_tool_skips_write_when_confirmation_rejected(self):
        manage_uc = MagicMock(spec=ManageNotes)
        tool = create_note_tool(manage_uc, _reject)
        payload = json.dumps({"title": "Mi nota", "content": "Contenido"})

        result = await tool.coroutine(payload)

        manage_uc.create.assert_not_called()
        assert "canceló" in result

    async def test_create_note_tool_asks_confirmation_with_note_summary(self):
        manage_uc = MagicMock(spec=ManageNotes)
        manage_uc.create.return_value = _make_note("notas/nueva.md")
        seen_summaries: list[str] = []

        async def _capture(summary: str) -> bool:
            seen_summaries.append(summary)
            return True

        tool = create_note_tool(manage_uc, _capture)
        payload = json.dumps({"title": "Mi nota", "content": "Contenido de prueba"})

        await tool.coroutine(payload)

        assert len(seen_summaries) == 1
        assert "Mi nota" in seen_summaries[0]
        assert "Contenido de prueba" in seen_summaries[0]


class TestEditNoteTool:
    async def test_edit_note_tool_parses_json_and_updates_note(self):
        manage_uc = MagicMock(spec=ManageNotes)
        manage_uc.update.return_value = _make_note("notas/existente.md")
        tool = create_edit_tool(manage_uc, _approve)
        payload = json.dumps(
            {"note_id": "notas/existente.md", "content": "Nuevo contenido"}
        )

        result = await tool.coroutine(payload)

        # Sin tags en el payload, se propaga None (preserva tags actuales)
        manage_uc.update.assert_called_once_with(
            "notas/existente.md", "Nuevo contenido", None
        )
        assert "notas/existente.md" in result

    async def test_edit_note_tool_with_tags_propagates_to_use_case(self):
        manage_uc = MagicMock(spec=ManageNotes)
        manage_uc.update.return_value = _make_note("notas/existente.md")
        tool = create_edit_tool(manage_uc, _approve)
        payload = json.dumps(
            {
                "note_id": "notas/existente.md",
                "content": "Nuevo contenido",
                "tags": ["nuevo-tag"],
            }
        )

        result = await tool.coroutine(payload)

        manage_uc.update.assert_called_once_with(
            "notas/existente.md", "Nuevo contenido", ["nuevo-tag"]
        )
        assert "notas/existente.md" in result

    async def test_edit_note_tool_returns_error_when_note_not_found(self):
        manage_uc = MagicMock(spec=ManageNotes)
        manage_uc.update.side_effect = NoteNotFoundError("nota no existe")
        tool = create_edit_tool(manage_uc, _approve)
        payload = json.dumps({"note_id": "notas/fantasma.md", "content": "contenido"})

        result = await tool.coroutine(payload)

        assert "no existe" in result
        assert "search_vault" in result

    async def test_edit_note_tool_skips_write_when_confirmation_rejected(self):
        manage_uc = MagicMock(spec=ManageNotes)
        tool = create_edit_tool(manage_uc, _reject)
        payload = json.dumps(
            {"note_id": "notas/existente.md", "content": "Nuevo contenido"}
        )

        result = await tool.coroutine(payload)

        manage_uc.update.assert_not_called()
        assert "canceló" in result


class TestListFoldersTool:
    def test_list_folders_tool_returns_existing_folders(self):
        move_uc = MagicMock(spec=MoveNote)
        move_uc.list_folders.return_value = ["00-inbox", "02-areas/rag"]
        tool = create_list_folders_tool(move_uc)

        result = tool.func("")

        assert "00-inbox" in result
        assert "02-areas/rag" in result

    def test_list_folders_tool_reports_empty_vault(self):
        move_uc = MagicMock(spec=MoveNote)
        move_uc.list_folders.return_value = []
        tool = create_list_folders_tool(move_uc)

        result = tool.func("")

        assert "no tiene ninguna subcarpeta" in result


class TestMoveNoteTool:
    def _result(self, note_id: str = "02-areas/rag/chunking") -> MoveResult:
        note = MagicMock()
        note.id = note_id
        return MoveResult(note=note, old_id="00-inbox/chunking", chunks_indexed=3)

    async def test_move_tool_moves_when_user_approves(self):
        move_uc = MagicMock(spec=MoveNote)
        move_uc.list_folders.return_value = ["02-areas/rag"]
        move_uc.find_inbound_links.return_value = []
        move_uc.execute.return_value = self._result()
        tool = create_move_tool(move_uc, _approve)
        payload = json.dumps(
            {"note_id": "00-inbox/chunking", "target_folder": "02-areas/rag"}
        )

        result = await tool.coroutine(payload)

        move_uc.execute.assert_called_once_with("00-inbox/chunking", "02-areas/rag")
        assert "02-areas/rag/chunking" in result

    async def test_move_tool_does_not_move_when_user_rejects(self):
        move_uc = MagicMock(spec=MoveNote)
        move_uc.list_folders.return_value = ["02-areas/rag"]
        move_uc.find_inbound_links.return_value = []
        tool = create_move_tool(move_uc, _reject)
        payload = json.dumps(
            {"note_id": "00-inbox/chunking", "target_folder": "02-areas/rag"}
        )

        result = await tool.coroutine(payload)

        move_uc.execute.assert_not_called()
        assert "canceló" in result

    async def test_move_tool_rejects_unknown_target_folder(self):
        move_uc = MagicMock(spec=MoveNote)
        move_uc.list_folders.return_value = ["00-inbox"]
        tool = create_move_tool(move_uc, _approve)
        payload = json.dumps(
            {"note_id": "00-inbox/chunking", "target_folder": "99-inventada"}
        )

        result = await tool.coroutine(payload)

        move_uc.execute.assert_not_called()
        assert "no es una carpeta existente" in result

    async def test_move_tool_returns_error_when_note_not_found(self):
        move_uc = MagicMock(spec=MoveNote)
        move_uc.list_folders.return_value = ["02-areas/rag"]
        move_uc.find_inbound_links.return_value = []
        move_uc.execute.side_effect = NoteNotFoundError("no existe")
        tool = create_move_tool(move_uc, _approve)
        payload = json.dumps(
            {"note_id": "00-inbox/fantasma", "target_folder": "02-areas/rag"}
        )

        result = await tool.coroutine(payload)

        assert "no existe" in result
        assert "search_vault" in result

    async def test_move_tool_returns_error_on_vault_write_error(self):
        move_uc = MagicMock(spec=MoveNote)
        move_uc.list_folders.return_value = ["02-areas/rag"]
        move_uc.find_inbound_links.return_value = []
        move_uc.execute.side_effect = VaultWriteError("ya existe")
        tool = create_move_tool(move_uc, _approve)
        payload = json.dumps(
            {"note_id": "00-inbox/chunking", "target_folder": "02-areas/rag"}
        )

        result = await tool.coroutine(payload)

        assert "Error al mover la nota" in result

    async def test_move_tool_summary_mentions_notes_to_relink(self):
        move_uc = MagicMock(spec=MoveNote)
        move_uc.list_folders.return_value = ["02-areas/rag"]
        move_uc.find_inbound_links.return_value = ["01-proyectos/tfm"]
        move_uc.execute.return_value = self._result()
        seen_summaries: list[str] = []

        async def _capture(summary: str) -> bool:
            seen_summaries.append(summary)
            return True

        tool = create_move_tool(move_uc, _capture)
        payload = json.dumps(
            {"note_id": "00-inbox/chunking", "target_folder": "02-areas/rag"}
        )

        await tool.coroutine(payload)

        assert len(seen_summaries) == 1
        assert "01-proyectos/tfm" in seen_summaries[0]
