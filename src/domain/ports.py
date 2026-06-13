"""Interfaces de dominio (ports) para el proyecto Second Brain.

Define los contratos ABC que los adaptadores deben implementar.
La capa de dominio no depende de ninguna tecnologa externa.

Adaptadores:
    Document loaders     -> IVaultReader, IVaultWriter
    Chunkers             -> IBaseChunker
    Embedders            -> IEmbedder
    Vector store         -> IVectorStore
    LLM chat             -> ILLMChat
    Evaluation repo      -> IEvaluationRepo
"""

from abc import ABC, abstractmethod
from typing import List

from .models import (
    Chunk,
    EvaluationResult,
    EvaluationSample,
    Note,
    RetrievalQuery,
    SearchResult,
)

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


class IVaultReader(ABC):
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
    def load(self, note_id: str) -> Note:
        """Carga una nota por su identificador.

        Args:
            note_id: Identificador unico de la nota a cargar.

        Returns:
            La nota con frontmatter, tags y backlinks parseados.

        Raises:
            ValueError: Si note_id no existe en el vault.
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


class IVaultWriter(ABC):
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
    def write(self, note: Note) -> None:
        """Crea una nueva nota en el vault.

        Args:
            note: La nota a crear con su contenido y metadatos.

        Raises:
            ValueError: Si note_id ya existe en el vault.
        """
        ...

    @abstractmethod
    def update(self, note_id: str, note: Note) -> None:
        """Actualiza una nota existente en el vault.

        Args:
            note_id: Identificador de la nota a actualizar.
            note: La nota con los valores actualizados.

        Raises:
            ValueError: Si note_id no existe en el vault.
        """
        ...

    @abstractmethod
    def delete(self, note_id: str) -> None:
        """Elimina una nota del vault.

        Args:
            note_id: Identificador de la nota a eliminar.
        """
        ...


class IBaseChunker(ABC):
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

        Este es el unico metodo con implementacion concreta
        que puede ser util en un puerto. Permite tracking
        de tokens, error handling y logging compartido.

        Args:
            notes: Lista de notas a dividir.

        Returns:
            Lista plana de todos los chunks de todas las notas.
        """
        all: List[Chunk] = []
        for note in notes:
            try:
                all.extend(self.chunk(note))
            except Exception:
                pass
        return all


class IEmbedder(ABC):
    """Interface para generar vectores de embeddings.

    Abstrace llamados a Ollama o HuggingFace para generar
    embeddings vectoriales a partir de textos cortos.
    """

    @abstractmethod
    def __init__(self, model_name: str) -> None:
        """Inicializa el embedder con el modelo a usar.

        Args:
            model_name: Nombre del modelo de embedding.
        """
        ...

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


class IVectorStore(ABC):
    """Interface para persistencia y busqueda vectorial.

    Abstrace ChromaDB para almacenar chunks con sus
    embeddings y buscarlos semanticamente.
    """

    @abstractmethod
    def __init__(self, persist_path: str) -> None:
        """Inicializa el vector store en la ruta dada.

        Args:
            persist_path: Ruta para persistir ChromaDB.
        """
        ...

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
    def delete_by_note_id(self, note_id: str) -> None:
        """Elimina todos los chunks de una nota.

        Args:
            note_id: Identificador de la nota a eliminar.
        """
        ...

    @abstractmethod
    def get_note_ids(self) -> List[str]:
        """Devuelve los IDs de notas indexadas.

        Returns:
            Lista de IDs de notas indexadas actualmente.
        """
        ...


class ILLMChat(ABC):
    """Interface para generar respuestas con un LLM.

    Abstrace llamados a Ollama (llama3.2, qwen3.6)
    o Groq (Gemma, Llama) para generar respuestas
    naturales a partir de contexto de retrieval.
    """

    @abstractmethod
    def __init__(self, model_name: str) -> None:
        """Inicializa el LLM con el modelo a usar.

        Args:
            model_name: Nombre del modelo de language model.
        """
        ...

    @abstractmethod
    def respond(self, prompt: str, context: List[SearchResult]) -> str:
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
