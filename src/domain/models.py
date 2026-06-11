"""Entidades principales del dominio Second Brain.

Contiene Note, Chunk, SearchResult, RetrievalQuery, EvaluationSample,
EvaluationResult y los enums ChunkStrategy y NoteType: la base sobre
la cual se construye toda la logica de recuperacion y evaluacion del
proyecto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Note:
    """Entidad que representa una nota completa del vault de Obsidian.

    Incluye frontmatter, tags y backlinks calculados para permitir
    que el sistema de recuperacion aproveche metadatos ricos.

    Attributes:
        note_id: Identificador unico de la nota (slug o filename).
        title: Titulo de la nota, extraido del frontmatter o primer heading.
        content: Contenido markdown de la nota (sin frontmatter).
        frontmatter: Dict con las claves/values del YAML frontmatter.
        tags: Lista de tags extraidos del frontmatter o wikilinks.
        backlinks: IDs de notas que referencian esta nota mediante wikilinks.
        created_at: Fecha de creacion (None si no esta disponible).
        updated_at: Fecha de ultima modificacion (None si no esta disponible).
    """

    note_id: str
    title: str
    content: str
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    backlinks: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.note_id:
            raise ValueError("note_id no puede estar vacio")
        if not self.title:
            raise ValueError("title no puede estar vacio")
        if self.content and not self.content.strip():
            raise ValueError("content no puede ser solo espacios en blanco")

    @property
    def tag_string(self) -> str:
        """Devuelve los tags como string separado por espacios."""
        return " ".join(self.tags) if self.tags else ""

    @property
    def backlink_string(self) -> str:
        """Devuelve los backlinks como string separado por comas."""
        return ", ".join(self.backlinks) if self.backlinks else ""

    @property
    def word_count(self) -> int:
        """Devuelve el número de palabras del contenido."""
        return len(self.content.split()) if self.content else 0

    @property
    def has_frontmatter_metadata(self) -> bool:
        """Devuelve True si la nota tiene frontmatter o tags."""
        return bool(self.frontmatter or self.tags)

    @property
    def is_empty(self) -> bool:
        """Verifica si la nota no tiene contenido ni metadatos relevantes."""
        return not self.content and not self.frontmatter

    def with_tags(self, tags: List[str]) -> Note:
        """Devuelve una copia de la nota con los tags dados."""
        return Note(
            note_id=self.note_id,
            title=self.title,
            content=self.content,
            frontmatter=self.frontmatter,
            tags=tags,
            backlinks=self.backlinks,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


@dataclass(frozen=True)
class Chunk:
    """Fragmento de una nota, preparado para ser almacenado en ChromaDB.

    Cada chunk se genera mediante alguna estrategia (fixed, markdown,
    backlink) y se indexa con su embedding y metadatos para permitir
    busqueda semantica y evaluacion de precision@K / MRR.

    Attributes:
        chunk_id: Identificador unico (note_id + indice posicion).
        note_id: ID de la nota madre que contiene este fragmento.
        content: Texto del fragmento sin frontmatter (markdown).
        strategy: estrategia de chunking usada ("fixed", "markdown", "backlink").
        position: Posicion ordinal del fragmento dentro de la nota padre.
        token_count: Estimacion del numero de tokens del contenido.
        metadata: Dict con metadatos adicionales para ChromaDB.
    """

    chunk_id: str
    note_id: str
    content: str
    strategy: str
    position: int = 0
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.chunk_id:
            raise ValueError("chunk_id no puede estar vacio")
        if not self.note_id:
            raise ValueError("note_id no puede estar vacio")
        if self.content and len(self.content) < 10:
            raise ValueError("el contenido del chunk debe tener >= 10 caracteres")

    @property
    def char_count(self) -> int:
        """Devuelve el número de caracteres del contenido."""
        return len(self.content)


@dataclass(frozen=True)
class SearchResult:
    """Resultado individual devuelto por el vector store.

    Representa un chunk que se considero relevante para la query
    del usuario, junto con su score de similitud y ranking.

    Attributes:
        chunk_id: ID del chunk que coincide con la query.
        note_id: ID de la nota madre del chunk.
        content: Fragmento de texto relevante como snippet.
        score: Score de similitud (0.0 a 1.0).
        rank: Posicion en el ranking (1-based).
    """

    chunk_id: str
    note_id: str
    content: str
    score: float
    rank: int = 1

    def __post_init__(self) -> None:
        if self.score < 0.0 or self.score > 1.0:
            raise ValueError("score debe estar entre 0.0 y 1.0")
        if self.rank < 1:
            raise ValueError("rank debe ser >= 1")

    @property
    def is_relevant(self) -> bool:
        """Devuelve True si el score supera el umbral de relevancia (0.7)."""
        return self.score >= 0.7


@dataclass(frozen=True)
class RetrievalQuery:
    """Consulta de recuperacion encapsulada con sus parametros.

    Define la query del usuario y los hiperparametros que controlan
    como se ejecuta la busqueda en el vector store.

    Attributes:
        query: Texto de la query del usuario.
        top_k: Numero maximo de resultados a devolver.
        min_score: Score minimo de similitud para incluir resultados.
        strategy: Estrategia de chunking a filtrar, o None para todas.
    """

    query: str
    top_k: int = 5
    min_score: float = 0.0
    strategy: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query no puede estar vacio")
        if self.top_k < 1:
            raise ValueError("top_k debe ser >= 1")
        if self.min_score < 0.0 or self.min_score > 1.0:
            raise ValueError("min_score debe estar entre 0.0 y 1.0")


@dataclass(frozen=True)
class EvaluationSample:
    """Muestra anotada de un dataset de evaluacion.

    Un sample es un par (query, ground_truth) que se usa para
    evaluar la calidad de la recuperacion vs una respuesta
    referencia conocida.

    Attributes:
        sample_id: Identificador unico de la muestra.
        query: Pregunta o consulta del usuario.
        expected_chunk_ids: IDs de chunks que DEBEN estar en top-K.
        expected_note_ids:IDs de notas consideradas relevantes.
        difficulty: Nivel de dificultad ("easy", "medium", "hard").
    """

    sample_id: str
    query: str
    expected_chunk_ids: List[str] = field(default_factory=list)
    expected_note_ids: List[str] = field(default_factory=list)
    difficulty: str = "medium"

    def __post_init__(self) -> None:
        if not self.sample_id:
            raise ValueError("sample_id no puede estar vacio")
        if not self.query.strip():
            raise ValueError("query no puede estar vacio")
        if self.difficulty not in ("easy", "medium", "hard"):
            raise ValueError(f"difficulty invalida: {self.difficulty}")
        if not self.expected_chunk_ids and not self.expected_note_ids:
            raise ValueError(
                "al menos one de expected_chunk_ids y expected_note_ids debe tener valores"
            )


@dataclass(frozen=True)
class EvaluationResult:
    """Resultados de una estrategia de retrieval sobre un dataset.

    Calcula métricas de Precision@K y Mean Reciprocal Rank (MRR)
    sobre los resultados de una estrategia de chunking.

    Attributes:
        strategy: Nombre de la estrategia evaluada.
        precision_at_k: Dict precision@K por cada K evaluado.
            Ej: {3: 0.667, 5: 0.8, 10: 0.7}
        mrr: Mean Reciprocal Rank global (0.0 a 1.0).
        mrr_per_sample: MRR detallado por cada sample.
        total_samples: Numero total de samples evaluados.
        average_precision: Precision promedio por sample.
    """

    strategy: str
    total_samples: int
    precision_at_k: Dict[int, float] = field(default_factory=dict)
    mrr: float = 0.0
    mrr_per_sample: Dict[str, float] = field(default_factory=dict)
    average_precision: float = 0.0

    def __post_init__(self) -> None:
        if not self.strategy:
            raise ValueError("strategy no puede estar vacio")
        if self.mrr < 0.0 or self.mrr > 1.0:
            raise ValueError("mrr debe estar entre 0.0 y 1.0")
        if (
            self.average_precision < 0.0
            or self.average_precision > 1.0
        ):
            raise ValueError(
                "average_precision debe estar entre 0.0 y 1.0"
            )
        if self.total_samples < 0:
            raise ValueError("total_samples no puede ser negativo")

    @property
    def mean_precision(self) -> float:
        """Devuelve la precisión media sobre todos los K evaluados."""
        values = list(self.precision_at_k.values())
        return sum(values) / len(values) if values else 0.0

    @property
    def mean_mrr(self) -> float:
        """Devuelve el MRR medio calculado sobre los samples individuales."""
        values = list(self.mrr_per_sample.values())
        return sum(values) / len(values) if values else 0.0

    def summary(self) -> str:
        """Devuelve un resumen formateado de los resultados de evaluación."""
        p_str = ", ".join(
            f"P@{k}={v:.3f}" for k, v in sorted(self.precision_at_k.items())
        )
        return (
            f"Strategy={self.strategy} | Samples={self.total_samples} | "
            f"MRR={self.mrr:.3f} | {p_str}"
        )


# =================== ENUMS ===================


class ChunkStrategy(Enum):
    """Estrategias de chunking para dividir el contenido de notas.

    Cada estrategia produce distinta fragmentacion del contenido
    y afecta la precision@K y MRR en la recuperacion.

    Attributes:
        FIXED: chunking por tamano fijo de tokens.
        MARKDOWN: chunking por cabeceras markdown (#, ##, ###).
        BACKLINK: chunking basado en relaciones de backlinks.
    """

    FIXED = "fixed"
    MARKDOWN = "markdown"
    BACKLINK = "backlink"

    def __init__(self, value: str) -> None:
        self._label: str = value.replace("_", " ").title()

    @property
    def label(self) -> str:
        """Devuelve una etiqueta legible para logs y UI."""
        return self._label


class NoteType(Enum):
    """Tipos de nota que se pueden encontrar en un vault de Obsidian.

    Ayuda a categorizar el contenido y aplicar estrategias
    de chunking diferentes segun el tipo.

    Attributes:
        DOC: Nota tipo documento o pagina wiki.
        TODO: Lista de tareas pendientes.
        MEETING: Nota de reunion con estructura de asistencia.
        MINDMAP: Mapa mental o estructura jerarquica.
        SNIPPET: Fragmento de codigo o referencia rapida.
        OTHER: Cualquier otro tipo de nota no clasificada.
    """

    DOC = "doc"
    TODO = "todo"
    MEETING = "meeting"
    MINDMAP = "mindmap"
    SNIPPET = "snippet"
    OTHER = "other"

    def __init__(self, value: str) -> None:
        labels = {
            "doc": "Documento",
            "todo": "Lista de tareas",
            "meeting": "Reunion",
            "mindmap": "Mapa mental",
            "snippet": "Snippet de codigo",
            "other": "Otro",
        }
        self._label: str = labels.get(value, value.title())

    @property
    def label(self) -> str:
        """Devuelve una etiqueta legible para logs y UI."""
        return self._label
