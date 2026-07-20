"""Tests unitarios para la normalización de tags de Obsidian."""

from src.domain.tags import normalize_tag, normalize_tags


def test_normalize_tag_internal_space_returns_kebab_case() -> None:
    # Arrange
    raw = "personajes públicos"

    # Act
    result = normalize_tag(raw)

    # Assert
    assert result == "personajes-públicos"


def test_normalize_tag_uppercase_returns_lowercase() -> None:
    # Arrange
    raw = "Distribuidos"

    # Act
    result = normalize_tag(raw)

    # Assert
    assert result == "distribuidos"


def test_normalize_tag_numeric_only_returns_none() -> None:
    # Arrange
    raw = "1984"

    # Act
    result = normalize_tag(raw)

    # Assert
    assert result is None


def test_normalize_tag_alphanumeric_returns_valid() -> None:
    # Arrange
    raw = "y1984"

    # Act
    result = normalize_tag(raw)

    # Assert
    assert result == "y1984"


def test_normalize_tag_nested_returns_preserved() -> None:
    # Arrange
    raw = "tipo/concepto"

    # Act
    result = normalize_tag(raw)

    # Assert
    assert result == "tipo/concepto"


def test_normalize_tag_accent_returns_preserved() -> None:
    # Arrange
    raw = "diseño"

    # Act
    result = normalize_tag(raw)

    # Assert
    assert result == "diseño"


def test_normalize_tag_leading_hash_returns_stripped() -> None:
    # Arrange
    raw = "#reunion"

    # Act
    result = normalize_tag(raw)

    # Assert
    assert result == "reunion"


def test_normalize_tag_empty_returns_none() -> None:
    # Arrange
    raw = "   "

    # Act
    result = normalize_tag(raw)

    # Assert
    assert result is None


def test_normalize_tags_dedups_and_preserves_order() -> None:
    # Arrange
    raw = ["Beta", "alpha", "beta", "1984", "gamma nested"]

    # Act
    result = normalize_tags(raw)

    # Assert
    assert result == ["beta", "alpha", "gamma-nested"]


def test_normalize_tags_empty_list_returns_empty() -> None:
    # Arrange
    raw: list[str] = []

    # Act
    result = normalize_tags(raw)

    # Assert
    assert result == []
