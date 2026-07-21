# Plan de implementación: Convenciones de Obsidian en la creación/edición de notas

> Plan guardado en git. Los planes de fases anteriores se conservan en el
> historial: `git log --oneline -- implementation-plan.md`.
>
> Generado como entregable obligatorio de la skill `critical-task-planning`
> para la tarea `tasks/tasks-obsidian-note-creation-conventions.md`.

## 1. Contexto y decisión de fondo

`tasks/tasks-obsidian-note-creation-conventions.md` pide formalizar las
convenciones de Obsidian (frontmatter YAML, tags, wikilinks, nombres de
fichero) en la creación/edición de notas del vault. El diagnóstico
obligatorio que pide el propio fichero de tarea se completó mediante dos
agentes Explore en paralelo más lectura directa de código.

**Hallazgo principal**: la funcionalidad de escritura ya existe y
funciona (`NoteWriter` / `ObsidianLoader.create()`/`update()`, tools
`create_note`/`edit_note` del agente, gate de `READONLY_MODE`). El
"diseño propuesto" original del fichero de tarea (crear `domain/note.py`,
un `NoteWriterPort` nuevo, etc.) está desactualizado respecto al código
real — esas piezas ya existen bajo otros nombres
(`src/domain/models.py::Note`, `src/domain/ports.py::NoteWriter`). Esto
es exactamente el tipo de "drift entre spec y dominio" que
`docs/error-log.md` pide vigilar.

**Gap real y acotado**: falta una función que construya wikilinks
(`build_wikilink`) y el saneamiento de nombre de fichero vive inline en
el adaptador en vez de como función pura de dominio testeable. Todo lo
demás (normalización de tags, generación de frontmatter YAML) ya está
resuelto por código/librerías existentes y correctamente probado
(`src/domain/tags.py`, librería `python-frontmatter`).

**No se toca**: `scripts/ingest.py`, chunkers, configuración de
Chainlit/Groq, ni el comportamiento de `READONLY_MODE` (confirmado
correcto vía gate en `create_agent()`).

## 2. Mapa de cambios

| Fichero | Acción |
|---|---|
| `implementation-plan.md` (este fichero) | Actualizar (reemplaza el plan de la fase anterior, conservado en git log) |
| `src/domain/obsidian_conventions.py` | Crear — `sanitize_filename`, `validate_tag`, `build_frontmatter`, `build_wikilink` |
| `tests/unit/test_obsidian_conventions.py` | Crear — 16 tests |
| `src/adapters/obsidian_loader.py` | Modificar: sustituir regex inline de slug por `sanitize_filename(title)` |
| `tests/unit/test_obsidian_loader.py` | Añadir 2 tests de regresión sobre `create()` |
| `tasks/tasks-obsidian-note-creation-conventions.md` | Marcar checklist, anotar decisión sobre `READONLY_MODE` |

No hay tabla "antes → después" de firmas porque no se renombra ni se
mueve ninguna función pública existente — solo se extrae lógica ya
existente (el regex de slug) a una nueva ubicación, preservando
comportamiento.

## 3. Especificación de componentes

### `src/domain/obsidian_conventions.py`

Cero dependencias externas; importa `normalize_tag` desde
`src.domain.tags` (domain→domain, permitido por
`scripts/check_architecture.py`).

```python
def sanitize_filename(title: str) -> str: ...
def validate_tag(tag: str) -> bool: ...
def build_frontmatter(tags: list[str], aliases: list[str] | None = None) -> str: ...
def build_wikilink(
    target: str,
    alias: str | None = None,
    heading: str | None = None,
    block_id: str | None = None,
    embed: bool = False,
) -> str: ...
```

Type hints completos, docstrings Google-style, 80 cols, `logging` no
`print()`.

### `src/adapters/obsidian_loader.py`

Sustituir el regex inline de `create()` (slug del título) por una
llamada a `sanitize_filename(title)`. Sin cambio de comportamiento
observable.

## 4. Análisis previo de los puntos críticos

### 4.1 `sanitize_filename` — extraer sin cambiar comportamiento

**Aspecto crítico**: el slug actual (`ObsidianLoader.create()`)
lowercasea y convierte espacios en guiones. La spec de la tarea sugiere
"nombre de archivo = título literal". Pero el agente ReAct ya construye
wikilinks usando `note_id` (el slug), no el título en lenguaje natural
(prompt "ENLAZAR NOTAS" en `src/agent/agent.py`). Cambiar el slugify
rompería esa consistencia y renombraría el esquema de notas ya creadas
en producción.

**Opciones consideradas**:
1. Preservar el título literal (interpretación literal de la spec) —
   requeriría cambiar `note_id` y el prompt del agente; alto riesgo,
   fuera de alcance.
2. Extraer el regex existente tal cual — cero riesgo nuevo, coherente
   con cómo ya funcionan los wikilinks.

**Decisión**: opción 2. Extraer el regex existente a
`sanitize_filename()`, sin cambiar comportamiento.

**Riesgo aceptado**: ninguno nuevo — comportamiento idéntico, solo
cambia de capa.

### 4.2 `validate_tag` — comprobación de forma canónica, no de recuperabilidad

**Aspecto crítico**: un wrapper ingenuo `normalize_tag(tag) is not None`
NO rechaza tags con espacios (`normalize_tag` los convierte a guiones y
los acepta), lo cual rompería el test obligatorio
`test_validate_tag_rejects_spaces`.

**Opciones consideradas**:
1. `return normalize_tag(tag) is not None` — simple pero incorrecto
   (acepta tags "arreglables", no solo los ya canónicos).
2. `return normalize_tag(tag) is not None and normalize_tag(tag) == tag`
   — valida que el tag YA esté en su forma canónica.

**Decisión**: opción 2. Delega 100% la regla en
`src/domain/tags.py::normalize_tag`, sin duplicar la regex.

**Riesgo aceptado**: ninguno — capa fina sobre código ya probado.

### 4.3 `build_frontmatter` — función pura de alcance estrecho, no cableada al adaptador

**Aspecto crítico**: la ruta de producción real ya genera frontmatter
correctamente vía `python-frontmatter`. Reimplementar un serializador
YAML a mano en el dominio para `title`/contenido arbitrario sería
reinventar YAML con riesgo de bugs de escapado.

**Opciones consideradas**:
1. No crear la función, cubrir el requisito solo con tests de adaptador
   sobre la salida real de `python-frontmatter` — se desvía
   completamente de la spec literal.
2. Crear `build_frontmatter` con alcance limitado a listas ya
   normalizadas (`tags`/`aliases`), sin serializar `title` ni contenido
   libre, como función pura no cableada al adaptador.

**Decisión**: opción 2. Cierra el requisito de la spec sin tocar la
ruta ya probada del adaptador.

**Riesgo aceptado**: código sin llamador en producción; mitigado porque
es puro, barato de mantener y con tests propios.

### 4.4 `build_wikilink` — única función realmente nueva

**Aspecto crítico**: no existe ningún equivalente previo; hay que
definir comportamiento en casos límite (alias/heading/block_id
combinados, caracteres inválidos).

**Opciones consideradas**:
1. Función permisiva que genera el mejor esfuerzo aunque los inputs
   sean ambiguos (ej. `heading` y `block_id` a la vez) — genera
   wikilinks potencialmente inválidos en Obsidian.
2. Función estricta que rechaza (`ValueError`) combinaciones inválidas
   según la sintaxis real de Obsidian.

**Decisión**: opción 2.
`build_wikilink(target, alias=None, heading=None, block_id=None, embed=False)`.
Reglas: `target` vacío → error; `target`/`alias`/`heading` con `[`, `]`
o `|` → error; `heading` y `block_id` simultáneos → error (mutuamente
excluyentes en Obsidian); `heading == ""` explícito → error; `block_id`
debe cumplir `^[A-Za-z0-9-]+$`.

**Riesgo aceptado**: ninguno — función nueva y aislada, cubierta por
tests.

### 4.5 `READONLY_MODE` — sin cambios, sin guard redundante en el puerto

**Aspecto crítico**: el checklist de la tarea pide un test
`test_note_writer_port_rejects_when_readonly_mode_enabled`, pero el
gate real vive en `create_agent()` (`src/agent/agent.py`), no en
`NoteWriter`/`ObsidianLoader`.

**Opciones consideradas**:
1. Añadir un guard de readonly dentro de `ObsidianLoader`/`NoteWriter`
   — defensa en profundidad, pero mete lógica de política de
   aplicación dentro de un adaptador de I/O puro, sin caso de uso real
   que lo requiera (nadie instancia `ObsidianLoader` fuera de la
   factory de infraestructura).
2. No tocar nada — el único punto de entrada a `NoteWriter` ya está
   gateado vía `ManageNotes`/agente.

**Decisión**: opción 2. Se retira el test de la lista (no aplica a la
arquitectura real), documentado aquí y en el checklist del fichero de
tarea.

**Riesgo aceptado**: ninguno — el único punto de entrada a `NoteWriter`
en el proyecto ya está gateado.

## 5. Tests

`tests/unit/test_obsidian_conventions.py` (patrón AAA, naming
`test_<function>_<condition>_<expected>` como en `tests/unit/test_tags.py`):

- `test_sanitize_filename_strips_forbidden_characters`
- `test_sanitize_filename_lowercases_and_hyphenates`
- `test_validate_tag_rejects_purely_numeric`
- `test_validate_tag_rejects_spaces`
- `test_validate_tag_accepts_nested_namespace`
- `test_validate_tag_rejects_uppercase`
- `test_build_frontmatter_serializes_tags_as_yaml_list`
- `test_build_frontmatter_places_delimiters_at_file_start`
- `test_build_frontmatter_omits_aliases_when_none`
- `test_build_wikilink_simple`
- `test_build_wikilink_with_alias`
- `test_build_wikilink_with_heading`
- `test_build_wikilink_with_block_id`
- `test_build_wikilink_embed_prefixes_bang`
- `test_build_wikilink_heading_and_block_id_raises_value_error`
- `test_build_wikilink_empty_target_raises_value_error`
- `test_build_wikilink_invalid_block_id_raises_value_error`

`tests/unit/test_obsidian_loader.py` (regresión de la ruta real):
- `test_obsidian_loader_create_writes_delimiters_at_file_start`
- `test_obsidian_loader_create_serializes_tags_as_yaml_list`

**Test retirado de la spec original** (documentado, no implementado):
`test_note_writer_port_rejects_when_readonly_mode_enabled` — ver
Análisis previo 4.5.

## 6. Orden de ejecución con gates

1. Crear/actualizar `implementation-plan.md` (este fichero). ✅
2. Crear `src/domain/obsidian_conventions.py` con las 4 funciones.
3. Crear `tests/unit/test_obsidian_conventions.py` (16 tests).
   Gate: `pytest tests/unit/test_obsidian_conventions.py -v`.
4. Modificar `src/adapters/obsidian_loader.py` para usar
   `sanitize_filename`. Gate: `pytest tests/unit/test_obsidian_loader.py -v`
   (regresión cero).
5. Añadir los 2 tests de adaptador. Mismo gate.
6. Suite completa: `pytest tests/unit/`.
7. `ruff check src/ tests/ --fix && ruff format src/ tests/`.
8. `mypy src`.
9. `python scripts/check_architecture.py`.
10. Marcar checklist en `tasks/tasks-obsidian-note-creation-conventions.md`.

## 7. Criterio de completado

- Los 16+2 tests nuevos pasan; `tests/unit/test_obsidian_loader.py`
  sigue en verde sin modificar su lógica de aserciones existentes.
- `ruff`/`mypy`/`check_architecture.py` en verde.
- Checklist de `tasks/tasks-obsidian-note-creation-conventions.md`
  actualizado, incluyendo la justificación de las desviaciones respecto
  al diseño original.

## 8. TODOs por funcionalidad

### 🧩 Dominio
- [x] Crear `src/domain/obsidian_conventions.py`
- [x] Implementar `sanitize_filename(title: str) -> str`
- [x] Implementar `validate_tag(tag: str) -> bool`
- [x] Implementar `build_frontmatter(tags, aliases=None) -> str`
- [x] Implementar `build_wikilink(target, alias=None, heading=None, block_id=None, embed=False) -> str`

### 🔌 Adaptador
- [x] Sustituir el regex inline de slug en `ObsidianLoader.create()` por
      `sanitize_filename(title)`
- [x] Verificar que `tests/unit/test_obsidian_loader.py` sigue en verde
      sin modificaciones

### 🧪 Tests
- [x] Crear `tests/unit/test_obsidian_conventions.py` con los 16 tests
- [x] Añadir 2 tests de regresión a `tests/unit/test_obsidian_loader.py`
- [x] Ejecutar suite completa `pytest tests/unit/` (168 passed)

### 🧹 Verificación final
- [x] `ruff check src/ tests/ --fix && ruff format src/ tests/`
- [x] `mypy src`
- [x] `python scripts/check_architecture.py`

### 📄 Documentación y sincronización
- [x] Marcar checklist de `tasks/tasks-obsidian-note-creation-conventions.md`
- [x] Anotar en el checklist la decisión sobre `READONLY_MODE` (sin
      guard en el puerto, test retirado)
- [x] Confirmar que `README.md` no requiere cambios (sin cambio de
      comportamiento observable)
