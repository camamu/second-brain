"""Tests unitarios para ObsidianLoader."""

import pytest

from src.adapters.obsidian_loader import ObsidianLoader
from src.domain.models import NoteType
from src.domain.ports import NoteNotFoundError, VaultWriteError

# ---------------------------------------------------------------------------
# load_all
# ---------------------------------------------------------------------------


def test_obsidian_loader_load_all_returns_all_notes_in_vault(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    notes = loader.load_all()
    # Assert — fixture crea 4 ficheros .md
    assert len(notes) == 4


def test_obsidian_loader_load_all_parses_frontmatter_correctly(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    notes = {n.id: n for n in loader.load_all()}
    note = notes["aprendizaje-profundo"]
    # Assert
    assert note.title == "aprendizaje-profundo"  # frontmatter no tiene title
    assert set(note.tags) == {"ml", "ia"}
    assert note.note_type == NoteType.DOC


def test_obsidian_loader_load_all_normalizes_malformed_tags(tmp_vault):
    # Arrange — nota con un tag con espacio+mayúsculas y otro válido
    (tmp_vault / "roto.md").write_text(
        '---\ntags: ["Personajes Públicos", castores]\n---\nCuerpo.',
        encoding="utf-8",
    )
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    notes = {n.id: n for n in loader.load_all()}
    note = notes["roto"]
    # Assert — el espacio pasa a guion y todo a minúsculas
    assert note.tags == ["personajes-públicos", "castores"]


def test_obsidian_loader_load_all_extracts_backlinks(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    notes = {n.id: n for n in loader.load_all()}
    note = notes["backpropagation"]
    # Assert
    assert "aprendizaje-profundo" in note.backlinks


def test_obsidian_loader_load_all_extracts_aliased_backlinks(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    notes = {n.id: n for n in loader.load_all()}
    note = notes["backpropagation"]
    # Assert — [[redes-neuronales|Redes]] debe extraer solo el nombre
    assert "redes-neuronales" in note.backlinks
    assert "Redes" not in note.backlinks


def test_obsidian_loader_load_all_skips_non_md_files(tmp_vault):
    # Arrange
    (tmp_vault / "notas.txt").write_text("texto plano", encoding="utf-8")
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    notes = loader.load_all()
    # Assert — el .txt no aparece
    assert all(n.id != "notas" for n in notes)
    assert len(notes) == 4


def test_obsidian_loader_load_all_handles_empty_note(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    notes = {n.id: n for n in loader.load_all()}
    empty = notes["nota-vacia"]
    # Assert — contenido normalizado a "" (no se lanza excepción)
    assert empty.content == ""
    assert empty.title == "Nota vacía"


# ---------------------------------------------------------------------------
# load_by_id
# ---------------------------------------------------------------------------


def test_obsidian_loader_load_by_id_returns_correct_note(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    note = loader.load_by_id("redes-neuronales")
    # Assert
    assert note.id == "redes-neuronales"
    assert "deep learning" in note.content


def test_obsidian_loader_load_by_id_nonexistent_raises_not_found(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act / Assert
    with pytest.raises(NoteNotFoundError):
        loader.load_by_id("no-existe")


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


def test_obsidian_loader_exists_returns_true_for_existing_note(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act / Assert
    assert loader.exists("aprendizaje-profundo") is True


def test_obsidian_loader_exists_returns_false_for_missing_note(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act / Assert
    assert loader.exists("no-existe") is False


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_obsidian_loader_create_writes_file_with_frontmatter(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    note = loader.create(
        title="Nueva nota",
        content="Contenido de la nota nueva.",
        tags=["test", "nuevo"],
    )
    # Assert
    assert note.title == "Nueva nota"
    assert set(note.tags) == {"test", "nuevo"}
    assert (tmp_vault / "00-inbox" / "nueva-nota.md").exists()


def test_obsidian_loader_create_normalizes_tags_as_yaml_list(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act — tag con espacio se normaliza antes de escribir el frontmatter
    loader.create(
        title="Con tags raros",
        content="Contenido.",
        tags=["Foo Bar", "baz"],
    )
    # Assert — al releer, los tags están normalizados y como lista YAML
    reloaded = loader.load_by_id("00-inbox/con-tags-raros")
    assert reloaded.tags == ["foo-bar", "baz"]
    raw = (tmp_vault / "00-inbox" / "con-tags-raros.md").read_text(encoding="utf-8")
    assert "- foo-bar" in raw


def test_obsidian_loader_create_existing_file_raises_write_error(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    loader.create(title="Duplicada", content="Primera vez.", tags=[])
    # Act / Assert
    with pytest.raises(VaultWriteError):
        loader.create(title="Duplicada", content="Segunda vez.", tags=[])


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def test_obsidian_loader_update_preserves_frontmatter(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    original = loader.load_by_id("aprendizaje-profundo")
    # Act
    updated = loader.update("aprendizaje-profundo", "Nuevo contenido.")
    # Assert — contenido cambia, tags y note_type se conservan
    assert updated.content == "Nuevo contenido."
    assert updated.tags == original.tags
    assert updated.note_type == original.note_type


def test_obsidian_loader_update_with_tags_merges_with_existing(tmp_vault):
    # Arrange — "aprendizaje-profundo" ya tiene tags {"ml", "ia"} (ver fixture)
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    updated = loader.update(
        "aprendizaje-profundo", "Nuevo contenido.", tags=["Nuevo Tag"]
    )
    # Assert — se suma el nuevo tag normalizado, sin perder los existentes
    assert set(updated.tags) == {"ml", "ia", "nuevo-tag"}


def test_obsidian_loader_update_without_tags_preserves_existing(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    original = loader.load_by_id("aprendizaje-profundo")
    # Act — tags=None (default) no debe tocar los tags actuales
    updated = loader.update("aprendizaje-profundo", "Nuevo contenido.")
    # Assert
    assert updated.tags == original.tags


def test_obsidian_loader_update_nonexistent_raises_not_found(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act / Assert
    with pytest.raises(NoteNotFoundError):
        loader.update("no-existe", "contenido")
