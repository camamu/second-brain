"""Adaptadores Ollama para embeddings y generación de texto."""

import logging
from typing import List

from src.domain.models import SearchResult
from src.domain.ports import ChunkEmbedder, ConversationalLLM, EmbeddingError

logger = logging.getLogger(__name__)

_RAG_TEMPLATE = """\
Eres un asistente que responde preguntas basándose en las notas del usuario.
Usa el siguiente contexto recuperado de sus notas para responder.
Si no encuentras la respuesta en el contexto, di que no tienes información suficiente.

Contexto:
{context}

Pregunta: {prompt}

Respuesta:"""


def _format_context(context: List[SearchResult]) -> str:
    parts = [f"[{r.note_id}] {r.content}" for r in context]
    return "\n\n".join(parts)


class OllamaEmbedderAdapter(ChunkEmbedder):
    """Genera embeddings usando Ollama vía LangChain.

    Attributes:
        _model: Nombre del modelo de embedding en Ollama.
        _embeddings: Instancia de OllamaEmbeddings de LangChain.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
    ) -> None:
        """Inicializa el embedder apuntando al servidor Ollama.

        Args:
            model: Nombre del modelo de embedding a usar.
            base_url: URL base del servidor Ollama.
        """
        from langchain_ollama import OllamaEmbeddings

        self._model = model
        self._embeddings = OllamaEmbeddings(model=model, base_url=base_url)

    def embed(self, text: str) -> List[float]:
        """Genera el vector de embedding de un texto.

        Args:
            text: Texto a vectorizar.

        Returns:
            Lista de floats que representan el vector.

        Raises:
            EmbeddingError: Si Ollama no está disponible o falla la llamada.
        """
        try:
            return self._embeddings.embed_query(text)
        except Exception as exc:
            logger.error("Error al generar embedding: %s", exc, exc_info=True)
            raise EmbeddingError(str(exc)) from exc

    def embed_many(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings para una lista de textos.

        Args:
            texts: Lista de textos a vectorizar.

        Returns:
            Lista de vectores (uno por texto).

        Raises:
            EmbeddingError: Si Ollama no está disponible o falla la llamada.
        """
        try:
            return self._embeddings.embed_documents(texts)
        except Exception as exc:
            logger.error("Error al generar embeddings batch: %s", exc, exc_info=True)
            raise EmbeddingError(str(exc)) from exc


class OllamaLLMAdapter(ConversationalLLM):
    """Genera respuestas usando Ollama vía LangChain.

    Attributes:
        _model: Nombre del modelo LLM en Ollama.
        _llm: Instancia de OllamaLLM de LangChain.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
    ) -> None:
        """Inicializa el adaptador LLM apuntando al servidor Ollama.

        Args:
            model: Nombre del modelo LLM a usar.
            base_url: URL base del servidor Ollama.
        """
        from langchain_ollama import OllamaLLM

        self._model = model
        self._llm = OllamaLLM(model=model, base_url=base_url)

    def as_langchain(self):
        """Devuelve el objeto LangChain subyacente para uso en el agente ReAct."""
        return self._llm

    def generate(self, prompt: str, context: List[SearchResult]) -> str:
        """Genera respuesta en lenguaje natural a partir de contexto RAG.

        Args:
            prompt: Pregunta o instrucción del usuario.
            context: Chunks recuperados del vault como contexto.

        Returns:
            Respuesta generada por el modelo.

        Raises:
            EmbeddingError: Si Ollama no está disponible o falla la generación.
        """
        full_prompt = _RAG_TEMPLATE.format(
            context=_format_context(context),
            prompt=prompt,
        )
        try:
            response = self._llm.invoke(full_prompt)
            return str(response)
        except Exception as exc:
            logger.error("Error al generar respuesta LLM: %s", exc, exc_info=True)
            raise EmbeddingError(str(exc)) from exc
