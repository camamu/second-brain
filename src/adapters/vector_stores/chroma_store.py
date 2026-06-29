"""Adaptador ChromaDB para persistencia y búsqueda vectorial."""

import logging
from typing import Any, Dict, List, Optional

import chromadb

from src.domain.models import Chunk, ChunkStrategy, RetrievalQuery, SearchResult
from src.domain.ports import ChunkEmbedder, VectorStore, VectorStoreError

logger = logging.getLogger(__name__)


def _sanitize_metadata(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convierte metadatos a tipos aceptados por ChromaDB (str/int/float/bool).

    Args:
        raw: Diccionario de metadatos sin filtrar.

    Returns:
        Diccionario con todos los valores convertidos a tipos escalares.
    """
    result: Dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, (str, int, float, bool)):
            result[key] = value
        elif isinstance(value, list):
            result[key] = ", ".join(str(v) for v in value)
        elif value is None:
            result[key] = ""
        else:
            result[key] = str(value)
    return result


class ChromaVectorStore(VectorStore):
    """Persistencia y búsqueda vectorial con ChromaDB.

    Mantiene una colección por estrategia de chunking para permitir
    la evaluación comparativa de Precision@K y MRR entre estrategias.

    Attributes:
        _embedder: Adapter de embeddings inyectado en el constructor.
        _default_strategy: Estrategia usada cuando query.strategy es None.
        _collection_prefix: Prefijo de nombre de colección.
        _client: Cliente ChromaDB (PersistentClient o in-memory para tests).
    """

    def __init__(
        self,
        persist_path: str,
        embedder: ChunkEmbedder,
        default_strategy: ChunkStrategy,
        collection_prefix: str = "obsidian_rag",
        client: Optional[chromadb.ClientAPI] = None,
    ) -> None:
        """Inicializa el store con el embedder y la estrategia por defecto.

        Args:
            persist_path: Ruta donde ChromaDB persiste los datos.
            embedder: Adapter de embeddings para vectorizar chunks y queries.
            default_strategy: Estrategia usada si query.strategy es None.
            collection_prefix: Prefijo de nombre para las colecciones.
            client: Cliente ChromaDB. Si None, crea PersistentClient en persist_path.
        """
        self._embedder = embedder
        self._default_strategy = default_strategy
        self._collection_prefix = collection_prefix
        self._client = client or chromadb.PersistentClient(path=persist_path)

    def _collection_name(self, strategy: ChunkStrategy) -> str:
        return f"{self._collection_prefix}_{strategy.value}"

    def _get_or_create_collection(self, strategy: ChunkStrategy) -> chromadb.Collection:
        return self._client.get_or_create_collection(
            name=self._collection_name(strategy),
            metadata={"hnsw:space": "cosine"},
        )

    def _existing_collections(self) -> List[chromadb.Collection]:
        """Devuelve solo las colecciones del prefijo de este store.

        ChromaDB v0.6 list_collections() devuelve strings (nombres), no objetos.
        """
        prefix = self._collection_prefix + "_"
        return [
            self._client.get_collection(name)
            for name in self._client.list_collections()
            if name.startswith(prefix)
        ]

    def add_chunks(self, chunks: List[Chunk]) -> None:
        """Persiste chunks con sus embeddings, agrupados por estrategia.

        Args:
            chunks: Chunks a almacenar. Todos deben tener el mismo strategy
                (se agrupan defensivamente por si llegan mezclados).

        Raises:
            VectorStoreError: Si falla cualquier operación de ChromaDB o embedding.
        """
        if not chunks:
            return

        # Agrupar por estrategia (defensivo)
        groups: Dict[ChunkStrategy, List[Chunk]] = {}
        for chunk in chunks:
            groups.setdefault(chunk.strategy, []).append(chunk)

        for strategy, group in groups.items():
            try:
                collection = self._get_or_create_collection(strategy)
                texts = [c.content for c in group]
                embeddings = self._embedder.embed_many(texts)

                ids = [c.id for c in group]
                documents = texts
                metadatas = []
                for c in group:
                    meta: Dict[str, Any] = {
                        "note_id": c.note_id,
                        "heading": c.heading or "",
                        "strategy": c.strategy.value,
                        "index": c.index,
                        "token_count": c.token_count,
                    }
                    meta.update(_sanitize_metadata(c.metadata))
                    metadatas.append(meta)

                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,  # type: ignore[arg-type]
                    documents=documents,
                    metadatas=metadatas,  # type: ignore[arg-type]
                )
                logger.info(
                    "Upserted %d chunks en colección '%s'",
                    len(group),
                    self._collection_name(strategy),
                )
            except Exception as exc:
                logger.error(
                    "Error al añadir chunks a '%s': %s",
                    self._collection_name(strategy),
                    exc,
                    exc_info=True,
                )
                raise VectorStoreError(str(exc)) from exc

    def search(self, query: RetrievalQuery) -> List[SearchResult]:
        """Busca chunks semánticamente relevantes para la query.

        Args:
            query: Parámetros de búsqueda. query.strategy (str o None) selecciona
                la colección; None usa la estrategia por defecto del store.

        Returns:
            Lista de SearchResult ordenada por score descendente (rank 1-based).
            Lista vacía si la colección no existe o está vacía.

        Raises:
            VectorStoreError: Si query.strategy tiene un valor desconocido.
        """
        # Resolver estrategia
        if query.strategy is None:
            strategy = self._default_strategy
        else:
            try:
                strategy = ChunkStrategy(query.strategy)
            except ValueError as exc:
                raise VectorStoreError(
                    f"Estrategia de chunking desconocida: '{query.strategy}'"
                ) from exc

        collection_name = self._collection_name(strategy)

        # Si la colección no existe, devolver vacío
        # ChromaDB v0.6: list_collections() devuelve strings
        existing = list(self._client.list_collections())
        if collection_name not in existing:
            logger.debug(
                "Colección '%s' no existe; search devuelve []", collection_name
            )
            return []

        try:
            collection = self._client.get_collection(collection_name)
            if collection.count() == 0:
                return []

            query_vector = self._embedder.embed(query.query)
            results = collection.query(
                query_embeddings=[query_vector],  # type: ignore[arg-type]
                n_results=min(query.top_k, collection.count()),
            )
        except Exception as exc:
            logger.error("Error en search: %s", exc, exc_info=True)
            raise VectorStoreError(str(exc)) from exc

        raw_ids = results["ids"]
        raw_documents = results["documents"]
        raw_distances = results["distances"]
        raw_metadatas = results["metadatas"]
        if not raw_ids or raw_documents is None or raw_distances is None or raw_metadatas is None:
            return []

        ids = raw_ids[0]
        documents = raw_documents[0]
        distances = raw_distances[0]
        metadatas = raw_metadatas[0]

        # Acumular tuplas (chunk_id, note_id, content, score) antes de asignar rank
        candidates = []
        for chunk_id, doc, distance, meta in zip(ids, documents, distances, metadatas):
            score = max(0.0, min(1.0, 1.0 - distance))
            if score < query.min_score:
                continue
            candidates.append((chunk_id, str(meta.get("note_id", "")), doc, score))

        candidates.sort(key=lambda t: t[3], reverse=True)
        return [
            SearchResult(
                chunk_id=chunk_id,
                note_id=note_id,
                content=content,
                score=score,
                rank=i + 1,
            )
            for i, (chunk_id, note_id, content, score) in enumerate(candidates)
        ]

    def delete_by_note(self, note_id: str) -> None:
        """Elimina todos los chunks de una nota de todas las colecciones.

        Args:
            note_id: Identificador de la nota cuyos chunks se eliminan.

        Raises:
            VectorStoreError: Si falla la operación de borrado.
        """
        for collection in self._existing_collections():
            try:
                collection.delete(where={"note_id": note_id})
                logger.debug(
                    "Eliminados chunks de nota '%s' en colección '%s'",
                    note_id,
                    collection.name,
                )
            except Exception as exc:
                logger.error(
                    "Error al borrar nota '%s' de '%s': %s",
                    note_id,
                    collection.name,
                    exc,
                    exc_info=True,
                )
                raise VectorStoreError(str(exc)) from exc

    def count(self) -> int:
        """Devuelve el total de chunks indexados en todas las colecciones.

        Returns:
            Suma de chunks en todas las colecciones del prefijo.
        """
        return sum(c.count() for c in self._existing_collections())

    def clear(self) -> None:
        """Elimina y recrea la colección de la estrategia por defecto.

        Raises:
            VectorStoreError: Si falla la operación de borrado en ChromaDB.
        """
        collection_name = self._collection_name(self._default_strategy)
        try:
            existing = list(self._client.list_collections())
            if collection_name in existing:
                self._client.delete_collection(collection_name)
                logger.info("Colección '%s' eliminada", collection_name)
            self._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Colección '%s' recreada vacía", collection_name)
        except Exception as exc:
            logger.error(
                "Error al limpiar colección '%s': %s",
                collection_name,
                exc,
                exc_info=True,
            )
            raise VectorStoreError(str(exc)) from exc
