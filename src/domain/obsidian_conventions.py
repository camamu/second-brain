"""Convenciones de Obsidian para la creación/edición de notas.

Funciones puras (sin I/O, sin dependencias externas) que formalizan el
saneamiento de nombres de fichero, la validación de tags ya normalizados
y la construcción de frontmatter/wikilinks compatibles con Obsidian.

IMPORTANTE: la ruta de producción real de escritura a disco
(`src/adapters/obsidian_loader.py`) sigue usando la librería
`python-frontmatter` como única fuente de verdad para serializar el
documento completo (título + contenido libre + frontmatter). El
`build_frontmatter` de este módulo es una utilidad pura de alcance
estrecho, limitada a listas ya normalizadas (`tags`/`aliases`), no
cableada a esa ruta — evita reinventar un serializador YAML genérico en
una capa de dominio sin dependencias externas.
"""

import logging
import re

from src.domain.tags import normalize_tag

logger = logging.getLogger(__name__)

_SLUG_STRIP_RE = re.compile(r"[^\w\s-]")
_SLUG_WHITESPACE_RE = re.compile(r"[\s_]+")

_STRUCTURAL_CHARS = ("[", "]", "|")
_BLOCK_ID_RE = re.compile(r"^[A-Za-z0-9-]+$")


def sanitize_filename(title: str) -> str:
    """Convierte un título de nota en un slug seguro para nombre de fichero.

    Elimina caracteres que rompen la sintaxis de enlaces de Obsidian
    (`# | ^ : %% [ ]`, entre otros no alfanuméricos) y colapsa espacios
    a guiones, en minúsculas.

    Args:
        title: Título de la nota tal como lo introduce el usuario o el LLM.

    Returns:
        Slug en minúsculas, con espacios colapsados a guiones y sin los
        caracteres reservados de la sintaxis de Obsidian.
    """
    slug = _SLUG_STRIP_RE.sub("", title.lower())
    return _SLUG_WHITESPACE_RE.sub("-", slug).strip("-")


def validate_tag(tag: str) -> bool:
    """Indica si `tag` ya está en su forma canónica de Obsidian.

    A diferencia de `normalize_tag` (que arregla lo recuperable),
    `validate_tag` es estricto: solo devuelve True si el tag no
    necesitaría ningún cambio para ser válido.

    Args:
        tag: Tag a comprobar.

    Returns:
        True si el tag ya está normalizado (minúsculas, sin espacios,
        no puramente numérico, namespaces con `/`).
    """
    normalized = normalize_tag(tag)
    return normalized is not None and normalized == tag


def build_frontmatter(tags: list[str], aliases: list[str] | None = None) -> str:
    """Construye el bloque de frontmatter YAML para `tags`/`aliases`.

    Alcance limitado a listas ya normalizadas (vía `normalize_tag`), sin
    caracteres que requieran comillas o escapado YAML. No serializa
    `title` ni contenido libre — ver nota del módulo.

    Args:
        tags: Tags ya normalizados a incluir como lista YAML.
        aliases: Alias opcionales a incluir como lista YAML.

    Returns:
        Bloque delimitado por `---`/`---` como primera línea absoluta
        del fichero, con `tags` (y `aliases` si se proporcionan) como
        listas YAML.
    """
    lines = ["---", "tags:"]
    lines.extend(f"  - {tag}" for tag in tags)
    if aliases:
        lines.append("aliases:")
        lines.extend(f"  - {alias}" for alias in aliases)
    lines.append("---")
    return "\n".join(lines) + "\n"


def build_wikilink(
    target: str,
    alias: str | None = None,
    heading: str | None = None,
    block_id: str | None = None,
    embed: bool = False,
) -> str:
    """Construye un wikilink de Obsidian con sintaxis válida.

    Args:
        target: Nota destino (título o note_id), sin `.md`.
        alias: Texto mostrado en lugar de `target`.
        heading: Encabezado dentro de `target` al que enlazar.
        block_id: Identificador de bloque (solo letras, números,
            guiones) dentro de `target` al que enlazar. Mutuamente
            excluyente con `heading`.
        embed: Si True, antepone `!` para transclusión.

    Returns:
        El wikilink formateado, ej. `[[Target#Heading|Alias]]`.

    Raises:
        ValueError: si `target` está vacío, si `target`/`alias`/
            `heading` contienen caracteres estructurales (`[`, `]`,
            `|`), si se combinan `heading` y `block_id`, si `heading`
            es una cadena vacía explícita, o si `block_id` no cumple
            `^[A-Za-z0-9-]+$`.
    """
    if not target.strip():
        raise ValueError("target no puede estar vacío")
    for name, value in (("target", target), ("alias", alias), ("heading", heading)):
        if value is not None and any(c in value for c in _STRUCTURAL_CHARS):
            raise ValueError(f"{name} no puede contener '[', ']' ni '|': {value!r}")
    if heading is not None and block_id is not None:
        raise ValueError("heading y block_id son mutuamente excluyentes")
    if heading is not None and heading == "":
        raise ValueError("heading no puede ser una cadena vacía")
    if block_id is not None and not _BLOCK_ID_RE.match(block_id):
        raise ValueError(
            f"block_id solo admite letras, números y guiones: {block_id!r}"
        )

    link = f"{target}#{heading}" if heading else target
    if block_id:
        link = f"{target}#^{block_id}"
    if alias:
        link = f"{link}|{alias}"

    prefix = "!" if embed else ""
    return f"{prefix}[[{link}]]"
