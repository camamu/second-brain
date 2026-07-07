"""Normalización y validación de etiquetas (tags) de Obsidian.

Aplica una regla mínima equivalente a la sintaxis oficial de Obsidian:
sin espacios en blanco, caracteres Unicode (letras/números/_/-) más la
barra `/` para anidamiento, y prohibición de tags puramente numéricos.

IMPORTANTE: este módulo NO gestiona wikilinks `[[...]]`. El grafo de
backlinks que explota el BacklinkAwareChunker se construye solo a partir
de wikilinks (ver `_BACKLINK_RE` en el adaptador), no de tags.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Letras/números Unicode y `_` (vía \w con re.UNICODE), más `-` y `/`
# para tags anidados tipo `tipo/concepto`. Sin espacios permitidos.
_TAG_RE = re.compile(r"^[\w/-]+$", re.UNICODE)

# Espacios internos: se colapsan a un único guion medio (kebab-case).
_WHITESPACE_RE = re.compile(r"\s+")


def _is_numeric_only(tag: str) -> bool:
    """Indica si el tag es puramente numérico (Obsidian lo rechaza).

    Args:
        tag: Tag ya normalizado.

    Returns:
        True si, ignorando separadores, el tag solo contiene dígitos.
    """
    return tag.strip("-_/").isdigit()


def normalize_tag(tag: str) -> str | None:
    """Normaliza un único tag o lo descarta si es irrecuperable.

    Pasos: trim, quitar `#` inicial, colapsar espacios internos a `-`
    y pasar a minúsculas (Obsidian agrupa de forma case-insensitive).

    Args:
        tag: Tag crudo tal como aparece en el frontmatter o lo genera el LLM.

    Returns:
        El tag normalizado, o None si queda vacío, es puramente numérico
        o contiene caracteres no permitidos tras normalizar.
    """
    cleaned = _WHITESPACE_RE.sub("-", tag.strip().lstrip("#")).lower()
    if not cleaned:
        return None
    if _is_numeric_only(cleaned):
        return None
    if not _TAG_RE.match(cleaned):
        return None
    return cleaned


def normalize_tags(tags: list[str]) -> list[str]:
    """Normaliza una lista de tags, deduplicando y preservando el orden.

    Los tags que no se pueden normalizar se descartan con un warning,
    de modo que la ingesta de vaults reales nunca se rompe por un tag mal
    formado (política "normalizar y continuar").

    Args:
        tags: Lista de tags crudos.

    Returns:
        Lista de tags normalizados, sin duplicados, en orden de aparición.
    """
    result: list[str] = []
    for tag in tags:
        norm = normalize_tag(str(tag))
        if norm is None:
            logger.warning("Tag inválido descartado: %r", tag)
            continue
        if norm not in result:
            result.append(norm)
    return result
