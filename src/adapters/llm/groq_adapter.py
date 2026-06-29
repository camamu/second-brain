"""Adaptadores Groq y HuggingFace para embeddings y generación de texto."""

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


class HuggingFaceEmbedderAdapter(ChunkEmbedder):
    """Genera embeddings usando HuggingFace vía LangChain.

    Attributes:
        _model_name: Nombre del modelo de HuggingFace Hub.
        _embeddings: Instancia de HuggingFaceEmbeddings de LangChain.
    """

    def __init__(
        self,
        model_name: str = "nomic-ai/nomic-embed-text-v1",
    ) -> None:
        """Inicializa el embedder con el modelo de HuggingFace.

        Args:
            model_name: Nombre del modelo en HuggingFace Hub.
        """
        from langchain_huggingface import HuggingFaceEmbeddings

        self._model_name = model_name
        self._embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"trust_remote_code": True},
        )

    def embed(self, text: str) -> List[float]:
        """Genera el vector de embedding de un texto.

        Args:
            text: Texto a vectorizar.

        Returns:
            Lista de floats que representan el vector.

        Raises:
            EmbeddingError: Si falla la llamada al modelo.
        """
        try:
            return self._embeddings.embed_query(text)
        except Exception as exc:
            logger.error(
                "Error al generar embedding HuggingFace: %s", exc, exc_info=True
            )
            raise EmbeddingError(str(exc)) from exc

    def embed_many(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings para una lista de textos.

        Args:
            texts: Lista de textos a vectorizar.

        Returns:
            Lista de vectores (uno por texto).

        Raises:
            EmbeddingError: Si falla la llamada al modelo.
        """
        try:
            return self._embeddings.embed_documents(texts)
        except Exception as exc:
            logger.error(
                "Error al generar embeddings batch HuggingFace: %s", exc, exc_info=True
            )
            raise EmbeddingError(str(exc)) from exc


class GroqLLMAdapter(ConversationalLLM):
    """Genera respuestas usando Groq (ChatGroq) vía LangChain.

    Attributes:
        _model: Nombre del modelo en Groq.
        _llm: Instancia de ChatGroq de LangChain.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
    ) -> None:
        """Inicializa el adaptador LLM con la API key de Groq.

        Args:
            api_key: API key de Groq.
            model: Nombre del modelo a usar en Groq.
        """
        from langchain_groq import ChatGroq
        from pydantic import SecretStr

        self._model = model
        self._llm = ChatGroq(api_key=SecretStr(api_key), model=model)

    def as_langchain(self):
        """Devuelve el objeto LangChain subyacente para uso en el agente ReAct."""
        return self._llm

    def generate(self, prompt: str, context: List[SearchResult]) -> str:
        """Genera respuesta en lenguaje natural a partir de contexto RAG.

        Args:
            prompt: Pregunta o instrucción del usuario.
            context: Chunks recuperados del vault como contexto.

        Returns:
            Respuesta generada por el modelo de Groq.

        Raises:
            EmbeddingError: Si falla la generación.
        """
        full_prompt = _RAG_TEMPLATE.format(
            context=_format_context(context),
            prompt=prompt,
        )
        try:
            response = self._llm.invoke(full_prompt)
            return str(response.content)
        except Exception as exc:
            logger.error("Error al generar respuesta Groq: %s", exc, exc_info=True)
            raise EmbeddingError(str(exc)) from exc
