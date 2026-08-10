"""Tests unitarios para ObsidianLoader."""

import pytest

from src.adapters.obsidian_loader import ObsidianLoader
from src.domain.models import ImportConflictPolicy, NoteType
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


def test_obsidian_loader_create_writes_delimiters_at_file_start(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    loader.create(title="Delimitadores", content="Cuerpo.", tags=["test"])
    # Assert — el fichero empieza en la primera línea absoluta con "---"
    raw = (tmp_vault / "00-inbox" / "delimitadores.md").read_text(encoding="utf-8")
    lines = raw.splitlines()
    assert lines[0] == "---"
    assert "---" in lines[1:]


def test_obsidian_loader_create_serializes_tags_as_yaml_list(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    loader.create(title="Tags lista", content="Cuerpo.", tags=["alpha", "beta"])
    # Assert — tags serializados como lista YAML, nunca como string
    raw = (tmp_vault / "00-inbox" / "tags-lista.md").read_text(encoding="utf-8")
    assert "tags:" in raw
    assert "- alpha" in raw
    assert "- beta" in raw


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


# ---------------------------------------------------------------------------
# create_raw
# ---------------------------------------------------------------------------


def test_create_raw_preserves_original_frontmatter_fields(tmp_vault):
    # Arrange — aliases, type y un campo custom que create() no soporta
    raw = (
        "---\n"
        "title: Importada\n"
        "tags:\n"
        "  - ia\n"
        "aliases:\n"
        "  - Alias Uno\n"
        "type: doc\n"
        "custom_field: valor-custom\n"
        "---\n"
        "Cuerpo de la nota importada.\n"
    )
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    note = loader.create_raw("Importada.md", raw)
    # Assert — todos los campos sobreviven, no solo title/content/tags
    assert note.frontmatter["aliases"] == ["Alias Uno"]
    assert note.frontmatter["custom_field"] == "valor-custom"
    assert note.note_type == NoteType.DOC


def test_create_raw_derives_note_id_from_filename_slug(tmp_vault):
    # Arrange
    raw = "---\ntags: []\n---\nContenido.\n"
    loader = ObsidianLoader(str(tmp_vault))
    # Act — el título del frontmatter difiere del nombre de fichero
    note = loader.create_raw("Mi Fichero Original.md", raw)
    # Assert — el note_id sale del slug del filename, no del title
    assert note.id == "00-inbox/mi-fichero-original"


def test_create_raw_normalizes_invalid_tags(tmp_vault):
    # Arrange
    raw = '---\ntags: ["Foo Bar", "123"]\n---\nContenido.\n'
    loader = ObsidianLoader(str(tmp_vault))
    # Act — "Foo Bar" se normaliza, "123" se descarta por ser numérico puro
    note = loader.create_raw("con-tags.md", raw)
    # Assert
    assert note.tags == ["foo-bar"]


def test_create_raw_raises_when_path_exists_and_policy_is_fail(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    loader.create_raw("duplicada.md", "---\ntags: []\n---\nPrimera.\n")
    # Act / Assert — FAIL es la política por defecto
    with pytest.raises(VaultWriteError):
        loader.create_raw("duplicada.md", "---\ntags: []\n---\nSegunda.\n")


def test_create_raw_overwrites_when_policy_is_overwrite(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    loader.create_raw("duplicada.md", "---\ntags: []\n---\nPrimera.\n")
    # Act
    note = loader.create_raw(
        "duplicada.md",
        "---\ntags: []\n---\nSegunda.\n",
        policy=ImportConflictPolicy.OVERWRITE,
    )
    # Assert — mismo note_id, contenido reemplazado
    assert note.id == "00-inbox/duplicada"
    assert note.content == "Segunda."


def test_create_raw_adds_numeric_suffix_when_policy_is_copy(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    loader.create_raw("duplicada.md", "---\ntags: []\n---\nPrimera.\n")
    # Act
    note = loader.create_raw(
        "duplicada.md",
        "---\ntags: []\n---\nSegunda.\n",
        policy=ImportConflictPolicy.COPY,
    )
    # Assert — el original se conserva, la copia recibe el sufijo -1
    assert note.id == "00-inbox/duplicada-1"
    original = loader.load_by_id("00-inbox/duplicada")
    assert original.content == "Primera."


# ---------------------------------------------------------------------------
# move
# ---------------------------------------------------------------------------


def test_obsidian_loader_move_relocates_note_and_updates_id(tmp_vault):
    # Arrange
    (tmp_vault / "02-areas").mkdir()
    loader = ObsidianLoader(str(tmp_vault))
    # Act
    moved = loader.move("aprendizaje-profundo", "02-areas")
    # Assert — nuevo id/path, contenido preservado, fichero antiguo ya no existe
    assert moved.id == "02-areas/aprendizaje-profundo"
    assert (tmp_vault / "02-areas" / "aprendizaje-profundo.md").exists()
    assert not (tmp_vault / "aprendizaje-profundo.md").exists()
    with pytest.raises(NoteNotFoundError):
        loader.load_by_id("aprendizaje-profundo")


def test_obsidian_loader_move_rejects_target_outside_vault(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act / Assert — target_folder intenta escapar del vault
    with pytest.raises(VaultWriteError):
        loader.move("aprendizaje-profundo", "../../etc")


def test_obsidian_loader_move_rejects_missing_target_folder(tmp_vault):
    # Arrange
    loader = ObsidianLoader(str(tmp_vault))
    # Act / Assert — la carpeta destino no existe, move() no crea carpetas
    with pytest.raises(VaultWriteError):
        loader.move("aprendizaje-profundo", "02-areas/no-existe")


def test_obsidian_loader_move_rejects_existing_destination_file(tmp_vault):
    # Arrange — ya hay un fichero con el mismo nombre en el destino
    dest_dir = tmp_vault / "02-areas"
    dest_dir.mkdir()
    (dest_dir / "aprendizaje-profundo.md").write_text("Cuerpo.", encoding="utf-8")
    loader = ObsidianLoader(str(tmp_vault))
    # Act / Assert
    with pytest.raises(VaultWriteError):
        loader.move("aprendizaje-profundo", "02-areas")
