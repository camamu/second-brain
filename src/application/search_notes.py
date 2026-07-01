"""Caso de uso: buscar notas semánticamente en el vector store."""

import logging
from typing import Optional

from src.domain.models import ChunkStrategy, RetrievalQuery, SearchResult
from src.domain.ports import VectorStore

logger = logging.getLogger(__name__)


class SearchNotes:
    """Orquesta la búsqueda semántica sobre el vault indexado.

    Args:
        store: Puerto de persistencia vectorial que ya contiene el embedder.
    """

    def __init__(self, store: VectorStore) -> None:
        self._store = store

    def execute(self, query: RetrievalQuery) -> list[SearchResult]:
        """Busca chunks relevantes para una query estructurada.

        Args:
            query: Parámetros de búsqueda (texto, top_k, estrategia, score mínimo).

        Returns:
            Lista ordenada de resultados con scores.
        """
        results = self._store.search(query)
        logger.info(
            "Búsqueda '%s' -> %d resultados.",
            query.query,
            len(results),
        )
        return results

    def execute_text(
        self,
        text: str,
        top_k: int = 5,
        strategy: Optional[ChunkStrategy] = None,
    ) -> list[SearchResult]:
        """Método de conveniencia para el agente: acepta texto y enum de estrategia.

        Args:
            text: Texto de la query del usuario.
            top_k: Número máximo de resultados.
            strategy: Estrategia de chunking a filtrar, o None para la por defecto.

        Returns:
            Lista ordenada de resultados con scores.
        """
        strategy_value = strategy.value if strategy is not None else None
        query = RetrievalQuery(query=text, top_k=top_k, strategy=strategy_value)
        return self.execute(query)
