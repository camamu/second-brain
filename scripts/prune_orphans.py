#!/usr/bin/env python
"""CLI para eliminar de ChromaDB los chunks de notas ya borradas del vault."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger(__name__)

    from src.application.prune_orphans import PruneOrphans
    from src.infrastructure.config import get_note_loader, get_vector_store

    try:
        loader = get_note_loader()
        store = get_vector_store()
    except Exception as exc:
        logger.error("Error al inicializar componentes: %s", exc)
        sys.exit(1)

    prune = PruneOrphans(loader=loader, store=store)

    logger.info("Buscando chunks huérfanos (notas borradas del vault)...")
    try:
        orphans = prune.execute()
    except Exception as exc:
        logger.error("Error durante la limpieza: %s", exc, exc_info=True)
        sys.exit(1)

    if orphans:
        logger.info(
            "Eliminados chunks de %d nota(s) huérfana(s): %s",
            len(orphans),
            ", ".join(orphans),
        )
    else:
        logger.info("No se encontraron chunks huérfanos.")


if __name__ == "__main__":
    main()
