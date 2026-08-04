"""Interfaces de dominio (ports) para el proyecto Second Brain.

Define los contratos ABC que los adaptadores deben implementar.
La capa de dominio no depende de ninguna tecnologa externa.

Adaptadores:
    Document loaders     -> NoteLoader, NoteWriter
    Chunkers             -> BaseChunker
    Embedders            -> ChunkEmbedder
    Vector store         -> VectorStore
    LLM chat             -> ConversationalLLM
    Evaluation repo      -> IEvaluationRepo
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from .models import (
    Chunk,
    EvaluationResult,
    EvaluationSample,
    ImportConflictPolicy,
    Note,
    RetrievalQuery,
    SearchResult,
)

logger = logging.getLogger(__name__)


# =================== EXCEPCIONES ===================


class ObsidianRagError(Exception):
    """Base para todas las excepciones del dominio."""


class NoteNotFoundError(ObsidianRagError):
    """Se lanza cuando una nota no existe en el vault."""


class ChunkingError(ObsidianRagError):
    """Se lanza cuando falla la division de una nota en chunks."""


class EmbeddingError(ObsidianRagError):
    """Se lanza cuando falla la generacion de embeddings."""


class VectorStoreError(ObsidianRagError):
    """Se lanza cuando falla una operacion en el vector store."""


class VaultWriteError(ObsidianRagError):
    """Se lanza cuando falla la escritura de una nota en el vault."""


class ConfigError(ObsidianRagError):
    """Se lanza cuando falta o es inválida una variable de configuración."""


class NoteLoader(ABC):
    """Interface para cargar notas del vault de Obsidian.

    Abstrae la lectura de archivos markdown desde el vault,
    incluyendo parsing de frontmatter, extraccion de tags
    y calculo de backlinks.
    """

    @abstractmethod
    def __init__(self, vault_path: str) -> None:
        """Inicializa el lector con la ruta del vault.

        Args:
            vault_path: Ruta absoluta al vault de Obsidian.
        """
        ...

    @abstractmethod
    def load_by_id(self, note_id: str) -> Note:
        """Carga una nota por su identificador.

        Args:
            note_id: Identificador unico de la nota a cargar.

        Returns:
            La nota con frontmatter, tags y backlinks parseados.

        Raises:
            NoteNotFoundError: Si note_id no existe en el vault.
        """
        ...

    @abstractmethod
    def exists(self, note_id: str) -> bool:
        """Comprueba si una nota existe en el vault.

        Args:
            note_id: Identificador unico de la nota.

        Returns:
            True si la nota existe en disco, False en caso contrario.
        """
        ...

    @abstractmethod
    def load_all(self) -> List[Note]:
        """Carga todas las notas del vault.

        Returns:
            Lista de todas las notas del vault con sus metadatos.
        """
        ...

    @abstractmethod
    def load_by_tags(self, tags: List[str]) -> List[Note]:
        """Filtra notas por tags especificados.

        Args:
            tags: Lista de tags a filtrar (OR logic).

        Returns:
            Notas que coinciden con al menos uno de los tags.
        """
        ...


class NoteWriter(ABC):
    """Interface para escribir notas en el vault de Obsidian.

    Abstrae la escritura de archivos markdown con frontmatter
    YAML en el filesystem del vault.
    """

    @abstractmethod
    def __init__(self, vault_path: str) -> None:
        """Inicializa el escritor con la ruta del vault.

        Args:
            vault_path: Ruta absoluta al vault de Obsidian.
        """
        ...

    @abstractmethod
    def create(self, title: str, content: str, tags: List[str]) -> Note:
        """Crea una nueva nota en el vault.

        Args:
            title: Titulo de la nota.
            content: Contenido markdown de la nota.
            tags: Lista de tags a incluir en el frontmatter.

        Returns:
            La nota recien creada.

        Raises:
            VaultWriteError: Si ya existe una nota con ese titulo.
        """
        ...

    @abstractmethod
    def update(
        self, note_id: str, content: str, tags: Optional[List[str]] = None
    ) -> Note:
        """Actualiza el contenido de una nota existente.

        Args:
            note_id: Identificador de la nota a actualizar.
            content: Nuevo contenido markdown (preserva el resto del frontmatter).
            tags: Tags a añadir a los existentes (union, sin eliminarlos).
                None preserva los tags actuales sin cambios.

        Returns:
            La nota con el contenido actualizado.

        Raises:
            NoteNotFoundError: Si note_id no existe en el vault.
        """
        ...

    @abstractmethod
    def create_raw(
        self,
        filename: str,
        raw_content: str,
        policy: ImportConflictPolicy = ImportConflictPolicy.FAIL,
    ) -> Note:
        """Escribe un documento .md preservando su frontmatter original.

        A diferencia de `create`, no reconstruye el frontmatter: el
        contenido crudo (incluido su YAML) se escribe tal cual, salvo que
        la normalizacion de tags obligue a reserializarlo. Pensado para
        importar notas ya existentes, no para que el LLM redacte una nueva.

        Args:
            filename: Nombre de fichero original (con o sin extension
                .md); el note_id se deriva de su slug.
            raw_content: Contenido completo del documento, incluido su
                frontmatter YAML si lo tiene.
            policy: Que hacer si el note_id resultante ya existe.

        Returns:
            La nota recien escrita.

        Raises:
            VaultWriteError: Si el note_id ya existe y policy es FAIL.
        """
        ...


class BaseChunker(ABC):
    """Contrato base comun para los tres chunkers.

    Define el metodo abstracto chunk() que cada strategy
    debe implementar de forma distinta. Tiene el metodo
    concreto chunk_many() que permite shared logic como
    tracking de tokens, manejo de errores y logging.
    """

    @abstractmethod
    def chunk(self, note: Note) -> List[Chunk]:
        """Divide una nota en fragmentos (chunks).

        Args:
            note: La nota a dividir en chunks.

        Returns:
            Lista de Chunk objects con el contenido dividido.
        """
        ...

    def chunk_many(self, notes: List[Note]) -> List[Chunk]:
        """Divide varias notas en chunks, acumulando resultados.

        Args:
            notes: Lista de notas a dividir.

        Returns:
            Lista plana de todos los chunks de todas las notas.

        Raises:
            ChunkingError: Si falla el chunking de alguna nota.
        """
        result: List[Chunk] = []
        for note in notes:
            try:
                result.extend(self.chunk(note))
            except ChunkingError:
                raise
            except Exception as exc:
                logger.error(
                    "Error al chunkear nota '%s': %s",
                    note.id,
                    exc,
                    exc_info=True,
                )
                raise ChunkingError(str(exc)) from exc
        return result


class ChunkEmbedder(ABC):
    """Interface para generar vectores de embeddings.

    Abstrace llamados a Ollama o HuggingFace para generar
    embeddings vectoriales a partir de textos cortos.
    """

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Genera el vector de embedding de un texto.

        Args:
            text: Texto para generar el embedding.

        Returns:
            Lista de floats que representan el vector.
        """
        ...

    @abstractmethod
    def embed_many(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings para una lista de textos.

        Args:
            texts: Lista de textos a incrustar.

        Returns:
            Lista de vectores (uno por texto).
        """
        ...


class VectorStore(ABC):
    """Interface para persistencia y busqueda vectorial.

    Abstrace ChromaDB para almacenar chunks con sus
    embeddings y buscarlos semanticamente.
    """

    @abstractmethod
    def add_chunks(self, chunks: List[Chunk]) -> None:
        """Persiste chunks con sus embeddings.

        Args:
            chunks: Chunks a almacenar en el vector store.
        """
        ...

    @abstractmethod
    def search(self, query: RetrievalQuery) -> List[SearchResult]:
        """Busca resultados semanticamente relevantes.

        Args:
            query: Parametros de busqueda del usuario.

        Returns:
            Lista ordenada de resultados con scores.
        """
        ...

    @abstractmethod
    def delete_by_note(self, note_id: str) -> None:
        """Elimina todos los chunks de una nota.

        Args:
            note_id: Identificador de la nota a eliminar.
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Devuelve el total de chunks indexados.

        Returns:
            Numero de chunks en el vector store.
        """
        ...

    @abstractmethod
    def list_note_ids(self) -> List[str]:
        """Devuelve los IDs de todas las notas con chunks indexados.

        Recorre todas las colecciones (todas las estrategias) para permitir
        detectar notas huerfanas (borradas del vault pero aun indexadas).

        Returns:
            Lista de note_id unicos presentes en el vector store.
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Elimina todos los chunks de la colección activa.

        Útil para reindexar el vault con una estrategia diferente
        durante la evaluación comparativa.

        Raises:
            VectorStoreError: Si falla la operación de borrado.
        """
        ...


class ConversationalLLM(ABC):
    """Interface para generar respuestas con un LLM.

    Abstrace llamados a Ollama (llama3.2, qwen3.6)
    o Groq (Gemma, Llama) para generar respuestas
    naturales a partir de contexto de retrieval.
    """

    @abstractmethod
    def generate(self, prompt: str, context: List[SearchResult]) -> str:
        """Genera respuesta natural a partir de contexto.

        Args:
            prompt: Pregunta o instruccion del usuario.
            context: Resultados de retrieval como contexto.

        Returns:
            Respuesta generada por el modelo de lenguaje.
        """
        ...


class IEvaluationRepo(ABC):
    """Interface para persistir dataset de evaluacion y resultados.

    Abstrace carga/guardado de EvaluationSample y
    EvaluationResult en un formato persistente (JSON/CSV).
    """

    @abstractmethod
    def load_sample(self, sample_id: str) -> EvaluationSample:
        """Carga una muestra de evaluacion por su ID.

        Args:
            sample_id: Identificador de la muestra.

        Returns:
            La muestra de evaluacion cargada.
        """
        ...

    @abstractmethod
    def save_result(self, result: EvaluationResult) -> None:
        """Guarda el resultado de una evaluacion.

        Args:
            result: Resultado de precision@K / MRR a guardar.
        """
        ...

    @abstractmethod
    def list_samples(self) -> List[EvaluationSample]:
        """Devuelve todas las muestras de evaluacion.

        Returns:
            Lista de todas las muestras del dataset.
        """
        ...
