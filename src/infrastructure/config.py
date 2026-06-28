"""Composition root — único fichero que lee .env e instancia adaptadores.

Todas las llamadas a os.getenv() viven aquí. Los imports de adaptadores son
lazy (dentro de cada función) para que el proyecto arranque aunque falten
dependencias opcionales (ej: langchain_groq no instalado en entorno local).
"""

import logging
import os

from dotenv import load_dotenv

from src.domain.models import ChunkStrategy
from src.domain.ports import (
    BaseChunker,
    ChunkEmbedder,
    ConfigError,
    ConversationalLLM,
    IEvaluationRepo,
    NoteLoader,
    NoteWriter,
    VectorStore,
)

load_dotenv()

logger = logging.getLogger(__name__)


# ─── helpers ──────────────────────────────────────────────────────────────────


def _require(key: str) -> str:
    """Lee una variable de entorno obligatoria.

    Args:
        key: Nombre de la variable de entorno.

    Returns:
        Valor de la variable.

    Raises:
        ConfigError: Si la variable no está definida o está vacía.
    """
    value = os.getenv(key, "").strip()
    if not value:
        raise ConfigError(f"Variable de entorno requerida no definida: {key}")
    return value


def _get_bool(key: str, default: bool = True) -> bool:
    """Lee una variable de entorno como booleano.

    Args:
        key: Nombre de la variable de entorno.
        default: Valor por defecto si la variable no existe.

    Returns:
        True si el valor es "true" (case-insensitive), False en caso contrario.
    """
    raw = os.getenv(key, "").strip().lower()
    if not raw:
        return default
    return raw == "true"


# ─── factories ────────────────────────────────────────────────────────────────


def get_llm() -> ConversationalLLM:
    """Devuelve el adaptador LLM según USE_LOCAL.

    Returns:
        OllamaLLMAdapter si USE_LOCAL=true, GroqLLMAdapter si USE_LOCAL=false.

    Raises:
        ConfigError: Si USE_LOCAL=false y GROQ_API_KEY no está definida.
    """
    use_local = _get_bool("USE_LOCAL", default=True)
    if use_local:
        from src.adapters.llm.ollama_adapter import OllamaLLMAdapter

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_LLM_MODEL", "llama3.2")
        logger.info("LLM: OllamaLLMAdapter (model=%s)", model)
        return OllamaLLMAdapter(model=model, base_url=base_url)
    else:
        from src.adapters.llm.groq_adapter import GroqLLMAdapter

        api_key = _require("GROQ_API_KEY")
        model = os.getenv("GROQ_MODEL", "llama-3.2-90b-text-preview")
        logger.info("LLM: GroqLLMAdapter (model=%s)", model)
        return GroqLLMAdapter(api_key=api_key, model=model)


def get_langchain_llm():
    """Devuelve el LLM nativo de LangChain (OllamaLLM o ChatGroq) para el agente.

    Returns:
        BaseLanguageModel: Instancia lista para usar en create_react_agent.

    Raises:
        ConfigError: Si USE_LOCAL=false y GROQ_API_KEY no está definida.
    """
    llm = get_llm()
    return llm.as_langchain()  # type: ignore[attr-defined]


def get_embedder() -> ChunkEmbedder:
    """Devuelve el adaptador de embeddings según USE_LOCAL.

    Returns:
        OllamaEmbedderAdapter si USE_LOCAL=true,
        HuggingFaceEmbedderAdapter si USE_LOCAL=false.
    """
    use_local = _get_bool("USE_LOCAL", default=True)
    if use_local:
        from src.adapters.llm.ollama_adapter import OllamaEmbedderAdapter

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        logger.info("Embedder: OllamaEmbedderAdapter (model=%s)", model)
        return OllamaEmbedderAdapter(model=model, base_url=base_url)
    else:
        from src.adapters.llm.groq_adapter import HuggingFaceEmbedderAdapter

        model_name = os.getenv("HF_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1")
        logger.info("Embedder: HuggingFaceEmbedderAdapter (model=%s)", model_name)
        return HuggingFaceEmbedderAdapter(model_name=model_name)


def get_vector_store(strategy: ChunkStrategy | None = None) -> VectorStore:
    """Devuelve el ChromaVectorStore con embedder y estrategia.

    Args:
        strategy: Estrategia de chunking que determina la colección ChromaDB.
            Si es None, lee CHUNKER_STRATEGY del entorno (default "fixed").

    Returns:
        ChromaVectorStore configurado con el embedder y la estrategia activa.

    Raises:
        ConfigError: Si CHUNKER_STRATEGY tiene un valor desconocido.
    """
    from src.adapters.vector_stores.chroma_store import ChromaVectorStore

    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db")
    resolved = (
        strategy
        if strategy is not None
        else _parse_strategy(os.getenv("CHUNKER_STRATEGY", "fixed"))
    )
    embedder = get_embedder()
    logger.info(
        "VectorStore: ChromaVectorStore (persist_dir=%s, strategy=%s)",
        persist_dir,
        resolved,
    )
    return ChromaVectorStore(
        persist_path=persist_dir,
        embedder=embedder,
        default_strategy=resolved,
    )


def get_note_loader() -> NoteLoader:
    """Devuelve el ObsidianLoader para el vault configurado.

    Returns:
        ObsidianLoader apuntando a VAULT_PATH.

    Raises:
        ConfigError: Si VAULT_PATH no está definida.
    """
    from src.adapters.obsidian_loader import ObsidianLoader

    vault_path = _require("VAULT_PATH")
    return ObsidianLoader(vault_path=vault_path)


def get_note_writer() -> NoteWriter:
    """Devuelve el ObsidianLoader como escritor del vault.

    Returns:
        ObsidianLoader (implementa NoteWriter) apuntando a VAULT_PATH.

    Raises:
        ConfigError: Si VAULT_PATH no está definida.
    """
    from src.adapters.obsidian_loader import ObsidianLoader

    vault_path = _require("VAULT_PATH")
    return ObsidianLoader(vault_path=vault_path)


def get_chunker(strategy: ChunkStrategy) -> BaseChunker:
    """Devuelve el chunker correspondiente a la estrategia dada.

    Args:
        strategy: Estrategia de chunking a instanciar.

    Returns:
        La instancia del chunker correspondiente.
    """
    if strategy == ChunkStrategy.FIXED_SIZE:
        from src.adapters.chunkers.fixed_size import FixedSizeChunker

        return FixedSizeChunker()
    elif strategy == ChunkStrategy.MARKDOWN_HEADER:
        from src.adapters.chunkers.markdown_header import MarkdownHeaderChunker

        return MarkdownHeaderChunker()
    else:
        from src.adapters.chunkers.backlink_aware import BacklinkAwareChunker

        loader = get_note_loader()
        return BacklinkAwareChunker(loader=loader)


def get_chunker_from_env() -> BaseChunker:
    """Devuelve el chunker indicado por CHUNKER_STRATEGY del entorno.

    Returns:
        El chunker correspondiente a la variable CHUNKER_STRATEGY.

    Raises:
        ConfigError: Si CHUNKER_STRATEGY tiene un valor desconocido.
    """
    strategy = _parse_strategy(os.getenv("CHUNKER_STRATEGY", "fixed"))
    return get_chunker(strategy)


def is_readonly() -> bool:
    """Indica si el sistema está en modo solo lectura (sin escritura al vault).

    Returns:
        True si READONLY_MODE=true, False en caso contrario.
    """
    return _get_bool("READONLY_MODE", default=False)


def get_evaluation_repo(
    dataset_path: str = "evaluation/dataset.json",
    results_dir: str = "evaluation/results",
) -> IEvaluationRepo:
    """Devuelve el adaptador de repositorio de evaluación.

    Args:
        dataset_path: Ruta al fichero dataset.json de preguntas anotadas.
        results_dir: Directorio donde se guardan los resultados JSON.

    Returns:
        EvaluationRepo configurado con las rutas indicadas.
    """
    from src.adapters.evaluation_repo import EvaluationRepo

    return EvaluationRepo(dataset_path=dataset_path, results_dir=results_dir)


def _parse_strategy(value: str) -> ChunkStrategy:
    """Convierte un string de estrategia a ChunkStrategy.

    Args:
        value: Valor de la variable CHUNKER_STRATEGY (fixed|markdown|backlink).

    Returns:
        El ChunkStrategy correspondiente.

    Raises:
        ConfigError: Si el valor no corresponde a ninguna estrategia conocida.
    """
    try:
        return ChunkStrategy(value.strip().lower())
    except ValueError:
        valid = [s.value for s in ChunkStrategy]
        raise ConfigError(
            f"CHUNKER_STRATEGY inválida: '{value}'. Valores válidos: {valid}"
        )
