"""Adaptador JSON para persistir dataset de evaluación y resultados."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from src.domain.models import EvaluationResult, EvaluationSample
from src.domain.ports import IEvaluationRepo, NoteNotFoundError, ObsidianRagError

logger = logging.getLogger(__name__)


class EvaluationRepo(IEvaluationRepo):
    """Repositorio de evaluación basado en ficheros JSON.

    Carga el dataset desde un fichero JSON anotado y persiste los resultados
    de cada estrategia en ficheros individuales con timestamp.

    Attributes:
        _dataset_path: Ruta al fichero dataset.json.
        _results_dir: Directorio donde se guardan los resultados.
    """

    def __init__(self, dataset_path: str, results_dir: str) -> None:
        """Inicializa el repositorio con las rutas de datos.

        Args:
            dataset_path: Ruta al fichero evaluation/dataset.json.
            results_dir: Ruta al directorio evaluation/results/.
        """
        self._dataset_path = Path(dataset_path)
        self._results_dir = Path(results_dir)

    def list_samples(self) -> List[EvaluationSample]:
        """Lee el dataset JSON y devuelve todos los samples anotados.

        Returns:
            Lista de EvaluationSample del dataset.

        Raises:
            ObsidianRagError: Si el fichero no existe o tiene formato inválido.
        """
        if not self._dataset_path.exists():
            raise ObsidianRagError(
                f"Dataset no encontrado: {self._dataset_path}. "
                "Crea evaluation/dataset.json antes de evaluar."
            )
        try:
            data = json.loads(self._dataset_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ObsidianRagError(
                f"Dataset JSON inválido: {self._dataset_path}"
            ) from exc

        samples: List[EvaluationSample] = []
        for raw in data.get("samples", []):
            samples.append(
                EvaluationSample(
                    sample_id=raw["id"],
                    query=raw["query"],
                    expected_note_ids=raw.get("relevant_note_ids", []),
                    expected_chunk_ids=[],
                    difficulty=raw.get("difficulty", "medium"),
                )
            )
        logger.info(
            "Dataset cargado: %d samples desde %s", len(samples), self._dataset_path
        )
        return samples

    def load_sample(self, sample_id: str) -> EvaluationSample:
        """Carga una muestra de evaluación por su ID.

        Args:
            sample_id: Identificador de la muestra.

        Returns:
            La muestra de evaluación correspondiente.

        Raises:
            NoteNotFoundError: Si sample_id no existe en el dataset.
        """
        for sample in self.list_samples():
            if sample.sample_id == sample_id:
                return sample
        raise NoteNotFoundError(f"Sample '{sample_id}' no encontrado en el dataset")

    def save_result(self, result: EvaluationResult) -> None:
        """Persiste el resultado de una estrategia en un fichero JSON con timestamp.

        Args:
            result: Resultado de Precision@K / MRR / Recall@K a guardar.
        """
        self._results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self._results_dir / f"{result.strategy}_{timestamp}.json"

        payload = {
            "strategy": result.strategy,
            "total_samples": result.total_samples,
            "mrr": result.mrr,
            "average_precision": result.average_precision,
            "precision_at_k": {str(k): v for k, v in result.precision_at_k.items()},
            "recall_at_k": {str(k): v for k, v in result.recall_at_k.items()},
            "mrr_per_sample": result.mrr_per_sample,
            "summary": result.summary(),
        }
        filename.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Resultado guardado en %s", filename)
