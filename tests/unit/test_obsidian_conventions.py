"""Tests unitarios para las convenciones de Obsidian en dominio."""

import pytest

from src.domain.obsidian_conventions import (
    build_frontmatter,
    build_wikilink,
    sanitize_filename,
    validate_tag,
)


def test_sanitize_filename_strips_forbidden_characters() -> None:
    # Arrange
    title = "Cocción # de | huevos ^ y : otros %% [tips]"

    # Act
    result = sanitize_filename(title)

    # Assert
    for char in "# | ^ : %% [ ]".split():
        assert char not in result


def test_sanitize_filename_lowercases_and_hyphenates() -> None:
    # Arrange
    title = "Mi Nota Importante"

    # Act
    result = sanitize_filename(title)

    # Assert
    assert result == "mi-nota-importante"


def test_validate_tag_rejects_purely_numeric() -> None:
    # Arrange
    tag = "1984"

    # Act
    result = validate_tag(tag)

    # Assert
    assert result is False


def test_validate_tag_rejects_spaces() -> None:
    # Arrange
    tag = "tag con espacio"

    # Act
    result = validate_tag(tag)

    # Assert
    assert result is False


def test_validate_tag_accepts_nested_namespace() -> None:
    # Arrange
    tag = "tipo/concepto"

    # Act
    result = validate_tag(tag)

    # Assert
    assert result is True


def test_validate_tag_rejects_uppercase() -> None:
    # Arrange
    tag = "Distribuidos"

    # Act
    result = validate_tag(tag)

    # Assert
    assert result is False


def test_build_frontmatter_serializes_tags_as_yaml_list() -> None:
    # Arrange
    tags = ["tipo/concepto", "dominio/sistemas-distribuidos"]

    # Act
    result = build_frontmatter(tags)

    # Assert
    assert "tags:\n  - tipo/concepto\n  - dominio/sistemas-distribuidos" in result


def test_build_frontmatter_places_delimiters_at_file_start() -> None:
    # Arrange
    tags = ["recetas"]

    # Act
    result = build_frontmatter(tags)

    # Assert
    lines = result.splitlines()
    assert lines[0] == "---"
    assert "---" in lines[1:]


def test_build_frontmatter_omits_aliases_when_none() -> None:
    # Arrange
    tags = ["recetas"]

    # Act
    result = build_frontmatter(tags, aliases=None)

    # Assert
    assert "aliases:" not in result


def test_build_wikilink_simple() -> None:
    # Arrange
    target = "Nombre Nota"

    # Act
    result = build_wikilink(target)

    # Assert
    assert result == "[[Nombre Nota]]"


def test_build_wikilink_with_alias() -> None:
    # Arrange
    target = "Nombre Nota"
    alias = "Texto mostrado"

    # Act
    result = build_wikilink(target, alias=alias)

    # Assert
    assert result == "[[Nombre Nota|Texto mostrado]]"


def test_build_wikilink_with_heading() -> None:
    # Arrange
    target = "Nombre Nota"
    heading = "Encabezado"

    # Act
    result = build_wikilink(target, heading=heading)

    # Assert
    assert result == "[[Nombre Nota#Encabezado]]"


def test_build_wikilink_with_block_id() -> None:
    # Arrange
    target = "Nombre Nota"
    block_id = "block-id-123"

    # Act
    result = build_wikilink(target, block_id=block_id)

    # Assert
    assert result == "[[Nombre Nota#^block-id-123]]"


def test_build_wikilink_embed_prefixes_bang() -> None:
    # Arrange
    target = "Nombre Nota"

    # Act
    result = build_wikilink(target, embed=True)

    # Assert
    assert result == "![[Nombre Nota]]"


def test_build_wikilink_heading_and_block_id_raises_value_error() -> None:
    # Arrange
    target = "Nombre Nota"

    # Act / Assert
    with pytest.raises(ValueError):
        build_wikilink(target, heading="Encabezado", block_id="abc")


def test_build_wikilink_empty_target_raises_value_error() -> None:
    # Arrange
    target = "   "

    # Act / Assert
    with pytest.raises(ValueError):
        build_wikilink(target)


def test_build_wikilink_invalid_block_id_raises_value_error() -> None:
    # Arrange
    target = "Nombre Nota"

    # Act / Assert
    with pytest.raises(ValueError):
        build_wikilink(target, block_id="bloque con espacios")
