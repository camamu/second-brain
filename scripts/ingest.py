#!/usr/bin/env python
"""CLI para indexar el vault de Obsidian completo en el vector store."""

import argparse
import logging
import os
import sys

VALID_STRATEGIES = ("fixed", "markdown", "backlink")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Indexa el vault de Obsidian en ChromaDB."
    )
    parser.add_argument(
        "--strategy",
        choices=VALID_STRATEGIES,
        default=None,
        help=(
            "Estrategia de chunking (fixed|markdown|backlink). "
            "Si se omite, usa CHUNKER_STRATEGY del .env."
        ),
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger(__name__)

    args = _parse_args()

    # Si --strategy se pasa explícitamente, sobreescribir el env antes de que
    # la factory lo lea, para que chunker y store usen la misma estrategia.
    if args.strategy:
        os.environ["CHUNKER_STRATEGY"] = args.strategy
        logger.info("Estrategia forzada vía CLI: %s", args.strategy)

    from src.application.ingest_vault import IngestVault
    from src.infrastructure.config import (
        get_chunker_from_env,
        get_note_loader,
        get_vector_store,
    )

    try:
        loader = get_note_loader()
        chunker = get_chunker_from_env()
        store = get_vector_store()
    except Exception as exc:
        logger.error("Error al inicializar componentes: %s", exc)
        sys.exit(1)

    ingest = IngestVault(loader=loader, chunker=chunker, store=store)

    logger.info("Iniciando ingesta del vault...")
    try:
        count = ingest.execute()
    except Exception as exc:
        logger.error("Error durante la ingesta: %s", exc, exc_info=True)
        sys.exit(1)

    logger.info("Ingesta completada: %d chunks indexados.", count)


if __name__ == "__main__":
    main()
