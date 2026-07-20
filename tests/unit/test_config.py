"""Tests unitarios para la factory de infrastructure/config.py."""

from unittest.mock import patch

import pytest

import src.infrastructure.config as config_module
from src.adapters.chunkers.backlink_aware import BacklinkAwareChunker
from src.adapters.chunkers.fixed_size import FixedSizeChunker
from src.adapters.chunkers.markdown_header import MarkdownHeaderChunker
from src.adapters.llm.ollama_adapter import OllamaEmbedderAdapter, OllamaLLMAdapter
from src.domain.models import ChunkStrategy
from src.domain.ports import ConfigError


def test_get_llm_returns_ollama_when_local(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("USE_LOCAL", "true")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Act
    llm = config_module.get_llm()

    # Assert
    assert isinstance(llm, OllamaLLMAdapter)


def test_get_llm_returns_groq_when_not_local(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("USE_LOCAL", "false")
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")

    # Evitar instanciar ChatGroq real (haría llamada al API)
    with patch(
        "src.adapters.llm.groq_adapter.GroqLLMAdapter.__init__", return_value=None
    ):
        from src.adapters.llm.groq_adapter import GroqLLMAdapter

        # Act
        llm = config_module.get_llm()

    # Assert
    assert isinstance(llm, GroqLLMAdapter)


def test_get_embedder_returns_ollama_when_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("USE_LOCAL", "true")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Act
    embedder = config_module.get_embedder()

    # Assert
    assert isinstance(embedder, OllamaEmbedderAdapter)


def test_get_chunker_returns_correct_type_for_each_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Para BacklinkAwareChunker necesitamos VAULT_PATH
    monkeypatch.setenv("VAULT_PATH", "/tmp/fake-vault")

    # Arrange / Act / Assert — las tres estrategias
    fixed = config_module.get_chunker(ChunkStrategy.FIXED_SIZE)
    assert isinstance(fixed, FixedSizeChunker)

    markdown = config_module.get_chunker(ChunkStrategy.MARKDOWN_HEADER)
    assert isinstance(markdown, MarkdownHeaderChunker)

    backlink = config_module.get_chunker(ChunkStrategy.BACKLINK_AWARE)
    assert isinstance(backlink, BacklinkAwareChunker)


def test_get_chunker_from_env_raises_config_error_for_invalid_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("CHUNKER_STRATEGY", "unknown_strategy")

    # Act / Assert
    with pytest.raises(ConfigError, match="CHUNKER_STRATEGY inválida"):
        config_module.get_chunker_from_env()


def test_get_strategy_from_env_default_returns_fixed_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv("CHUNKER_STRATEGY", raising=False)

    # Act
    strategy = config_module.get_strategy_from_env()

    # Assert
    assert strategy == ChunkStrategy.FIXED_SIZE


def test_get_strategy_from_env_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("CHUNKER_STRATEGY", "markdown")

    # Act
    strategy = config_module.get_strategy_from_env()

    # Assert
    assert strategy == ChunkStrategy.MARKDOWN_HEADER


def test_get_strategy_from_env_invalid_value_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("CHUNKER_STRATEGY", "unknown_strategy")

    # Act / Assert
    with pytest.raises(ConfigError, match="CHUNKER_STRATEGY inválida"):
        config_module.get_strategy_from_env()


def test_require_raises_config_error_when_var_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — eliminar VAULT_PATH si existía
    monkeypatch.delenv("VAULT_PATH", raising=False)
    monkeypatch.setenv("USE_LOCAL", "true")

    # Act / Assert
    with pytest.raises(ConfigError, match="VAULT_PATH"):
        config_module.get_note_loader()
