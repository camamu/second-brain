"""Evaluación comparativa de las tres estrategias de chunking.

Para cada estrategia (fixed, markdown, backlink):
1. Limpia la colección ChromaDB y reindexa el vault (salvo --skip-ingest).
2. Para cada pregunta del dataset: ejecuta retrieval y calcula métricas.
3. Calcula Precision@K, MRR y Recall@K globales y por dificultad.
4. Guarda los resultados en evaluation/results/.
5. Imprime una tabla comparativa con rich.

Uso:
    python evaluation/run_evaluation.py
    python evaluation/run_evaluation.py --k 10 --skip-ingest
    python evaluation/run_evaluation.py --dataset path/to/dataset.json
"""

import argparse
import logging
import sys
from pathlib import Path

# Añadir la raíz del proyecto al path para importar desde src.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich import box
from rich.console import Console
from rich.table import Table

from evaluation.metrics import precision_at_k, recall_at_k, reciprocal_rank
from src.application.ingest_vault import IngestVault
from src.application.search_notes import SearchNotes
from src.domain.models import (
    ChunkStrategy,
    EvaluationResult,
    EvaluationSample,
    RetrievalQuery,
)
from src.infrastructure.config import (
    get_chunker,
    get_evaluation_repo,
    get_note_loader,
    get_vector_store,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
console = Console()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluación comparativa de estrategias de chunking"
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Número de resultados top-K a evaluar (default: 5)",
    )
    parser.add_argument(
        "--dataset",
        default="evaluation/dataset.json",
        help="Ruta al fichero dataset.json (default: evaluation/dataset.json)",
    )
    parser.add_argument(
        "--results-dir",
        default="evaluation/results",
        help="Directorio donde guardar los resultados (default: evaluation/results)",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Omitir la reindexación del vault (usa colecciones existentes)",
    )
    return parser.parse_args()


def _evaluate_strategy(
    strategy: ChunkStrategy,
    samples: list[EvaluationSample],
    k: int,
    skip_ingest: bool,
) -> EvaluationResult:
    """Evalúa una estrategia de chunking sobre todos los samples.

    Args:
        strategy: Estrategia a evaluar.
        samples: Lista de muestras anotadas del dataset.
        k: Top-K para las métricas.
        skip_ingest: Si True, omite la ingesta y usa la colección existente.

    Returns:
        EvaluationResult con las métricas calculadas.
    """
    console.rule(f"[bold cyan]Estrategia: {strategy.value}")

    store = get_vector_store(strategy=strategy)

    if not skip_ingest:
        logger.info("[%s] Limpiando colección ChromaDB...", strategy.value)
        store.clear()

        loader = get_note_loader()
        chunker = get_chunker(strategy)
        logger.info("[%s] Reindexando vault...", strategy.value)
        n_chunks = IngestVault(loader=loader, chunker=chunker, store=store).execute()
        logger.info("[%s] %d chunks indexados.", strategy.value, n_chunks)
    else:
        logger.info(
            "[%s] --skip-ingest activo; usando colección existente.", strategy.value
        )

    searcher = SearchNotes(store=store)
    precision_scores: list[float] = []
    rr_scores: list[float] = []
    recall_scores: list[float] = []
    mrr_per_sample: dict[str, float] = {}

    for sample in samples:
        logger.debug(
            "[%s] Evaluando sample '%s': %s",
            strategy.value,
            sample.sample_id,
            sample.query,
        )
        query = RetrievalQuery(query=sample.query, top_k=k)
        results = searcher.execute(query)

        p = precision_at_k(results, sample.expected_note_ids, k)
        rr = reciprocal_rank(results, sample.expected_note_ids)
        r = recall_at_k(results, sample.expected_note_ids, k)

        precision_scores.append(p)
        rr_scores.append(rr)
        recall_scores.append(r)
        mrr_per_sample[sample.sample_id] = rr

    n = len(samples)
    avg_precision = sum(precision_scores) / n if n else 0.0
    avg_mrr = sum(rr_scores) / n if n else 0.0
    avg_recall = sum(recall_scores) / n if n else 0.0

    return EvaluationResult(
        strategy=strategy.value,
        total_samples=n,
        precision_at_k={k: avg_precision},
        mrr=avg_mrr,
        mrr_per_sample=mrr_per_sample,
        average_precision=avg_precision,
        recall_at_k={k: avg_recall},
    )


def _difficulty_breakdown(
    strategy: ChunkStrategy,
    samples: list[EvaluationSample],
    k: int,
    skip_ingest: bool,
) -> dict[str, dict[str, float]]:
    """Calcula métricas agrupadas por dificultad para una estrategia.

    Args:
        strategy: Estrategia evaluada.
        samples: Todos los samples.
        k: Top-K.
        skip_ingest: Si True, omite la ingesta.

    Returns:
        Dict {difficulty: {metric: value}}.
    """
    store = get_vector_store(strategy=strategy)
    searcher = SearchNotes(store=store)

    by_difficulty: dict[str, list[EvaluationSample]] = {}
    for sample in samples:
        by_difficulty.setdefault(sample.difficulty, []).append(sample)

    breakdown: dict[str, dict[str, float]] = {}
    for difficulty, group in by_difficulty.items():
        p_scores, rr_scores, r_scores = [], [], []
        for sample in group:
            query = RetrievalQuery(query=sample.query, top_k=k)
            results = searcher.execute(query)
            p_scores.append(precision_at_k(results, sample.expected_note_ids, k))
            rr_scores.append(reciprocal_rank(results, sample.expected_note_ids))
            r_scores.append(recall_at_k(results, sample.expected_note_ids, k))
        n = len(group)
        breakdown[difficulty] = {
            "precision": sum(p_scores) / n,
            "mrr": sum(rr_scores) / n,
            "recall": sum(r_scores) / n,
            "count": n,
        }
    return breakdown


def _print_summary_table(results: list[EvaluationResult], k: int) -> None:
    """Imprime la tabla comparativa de resultados con rich."""
    table = Table(
        title=f"Evaluación comparativa — top-{k}",
        box=box.SQUARE,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Estrategia", style="cyan", min_width=18)
    table.add_column(f"Precision@{k}", justify="center", min_width=12)
    table.add_column("MRR", justify="center", min_width=9)
    table.add_column(f"Recall@{k}", justify="center", min_width=10)
    table.add_column("Samples", justify="center", min_width=8)

    for result in results:
        p = result.precision_at_k.get(k, 0.0)
        r = result.recall_at_k.get(k, 0.0)
        table.add_row(
            result.strategy,
            f"{p:.3f}",
            f"{result.mrr:.3f}",
            f"{r:.3f}",
            str(result.total_samples),
        )
    console.print(table)


def _print_difficulty_table(
    strategy_breakdowns: dict[str, dict[str, dict[str, float]]],
    k: int,
) -> None:
    """Imprime el desglose de métricas por dificultad."""
    console.rule("[bold yellow]Desglose por dificultad")
    for difficulty in ("easy", "medium", "hard"):
        table = Table(
            title=f"Dificultad: {difficulty}",
            box=box.SIMPLE_HEAD,
            header_style="bold yellow",
        )
        table.add_column("Estrategia", style="cyan", min_width=18)
        table.add_column(f"Precision@{k}", justify="center")
        table.add_column("MRR", justify="center")
        table.add_column(f"Recall@{k}", justify="center")
        table.add_column("N", justify="center")

        for strategy_value, breakdown in strategy_breakdowns.items():
            if difficulty not in breakdown:
                continue
            m = breakdown[difficulty]
            table.add_row(
                strategy_value,
                f"{m['precision']:.3f}",
                f"{m['mrr']:.3f}",
                f"{m['recall']:.3f}",
                str(int(m["count"])),
            )
        console.print(table)


def main() -> None:
    args = _parse_args()
    k: int = args.k

    console.rule("[bold green]Evaluación comparativa de estrategias de chunking")

    repo = get_evaluation_repo(dataset_path=args.dataset, results_dir=args.results_dir)
    samples = repo.list_samples()
    logger.info("Dataset cargado: %d samples.", len(samples))

    strategies = [
        ChunkStrategy.FIXED_SIZE,
        ChunkStrategy.MARKDOWN_HEADER,
        ChunkStrategy.BACKLINK_AWARE,
    ]

    all_results: list[EvaluationResult] = []
    for strategy in strategies:
        result = _evaluate_strategy(strategy, samples, k, args.skip_ingest)
        repo.save_result(result)
        all_results.append(result)
        console.print(
            f"[green]✓[/green] {strategy.value}: P@{k}={result.precision_at_k[k]:.3f} | MRR={result.mrr:.3f} | R@{k}={result.recall_at_k[k]:.3f}"
        )

    console.print()
    _print_summary_table(all_results, k)

    # Desglose por dificultad (reutiliza colecciones ya indexadas)
    strategy_breakdowns: dict[str, dict[str, dict[str, float]]] = {}
    for strategy in strategies:
        strategy_breakdowns[strategy.value] = _difficulty_breakdown(
            strategy, samples, k, skip_ingest=True
        )
    _print_difficulty_table(strategy_breakdowns, k)

    console.rule("[bold green]Evaluación completada")
    console.print(f"Resultados guardados en: [italic]{args.results_dir}[/italic]")


if __name__ == "__main__":
    main()
