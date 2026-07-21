"""Tests unitarios para funciones puras del entrypoint de Chainlit."""

from src.app import _build_sources_footer, _dedup_note_ids
from src.domain.models import SearchResult


def _make_search_result(note_id: str, rank: int = 1) -> SearchResult:
    return SearchResult(
        chunk_id=f"chunk-{rank}",
        note_id=note_id,
        content=f"Contenido del chunk {rank}",
        score=0.9 - rank * 0.05,
        rank=rank,
    )


class TestDedupNoteIds:
    def test_dedup_note_ids_empty_list_returns_empty_list(self):
        assert _dedup_note_ids([]) == []

    def test_dedup_note_ids_preserves_order_and_removes_duplicates(self):
        results = [
            _make_search_result("notas/a.md", rank=1),
            _make_search_result("notas/b.md", rank=2),
            _make_search_result("notas/a.md", rank=3),
        ]

        assert _dedup_note_ids(results) == ["notas/a.md", "notas/b.md"]


class TestBuildSourcesFooter:
    def test_build_sources_footer_empty_results_returns_empty_string(self):
        assert _build_sources_footer([]) == ""

    def test_build_sources_footer_includes_each_note_id_literally(self):
        """Chainlit solo renderiza el chip de una fuente con display="page"
        si el note_id aparece literalmente en el texto del mensaje; el pie
        debe garantizar esa coincidencia exacta."""
        results = [
            _make_search_result("00-inbox/cocción-de-huevos", rank=1),
            _make_search_result("02-areas/rag/chromadb", rank=2),
        ]

        footer = _build_sources_footer(results)

        assert "00-inbox/cocción-de-huevos" in footer
        assert "02-areas/rag/chromadb" in footer

    def test_build_sources_footer_deduplicates_by_note_id(self):
        results = [
            _make_search_result("notas/a.md", rank=1),
            _make_search_result("notas/a.md", rank=2),
        ]

        footer = _build_sources_footer(results)

        assert footer.count("notas/a.md") == 1
