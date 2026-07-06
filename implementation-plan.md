# Plan de Implementación — Normalización y validación de tags de Obsidian

> Plan guardado en git. Los planes de fases anteriores se conservan en el historial: `git log --oneline`.

## Contexto

El proyecto no tenía **ninguna** lógica de validación ni normalización de tags: los
tags fluían sin transformar desde el LLM → `create_note` → frontmatter YAML, y al leer
se copiaban tal cual de la clave `tags:` (`obsidian_loader.py`). Esto ya produjo un tag
mal formado en el vault de demo (`personajes públicos`, con espacio interior y tilde).
Obsidian trata un espacio como separador, así que ese tag queda partido/roto.

El documento de convenciones (spec de esta tarea) exige una regla mínima equivalente a
Obsidian: sin espacios, sin tags puramente numéricos, serialización siempre como lista
YAML, y **sin mezclar** la lógica de tags con el `BacklinkAwareChunker` (que depende solo
de `[[wikilinks]]`, `_BACKLINK_RE` en `obsidian_loader.py:19`).

## Decisiones clave

| Decisión | Elegida | Motivo |
|---|---|---|
| Política ante tag inválido (escritura) | Normalizar y continuar | Nunca romper al agente en `create_note` |
| Saneado en lectura | Sí, tolerante | Coherente con "no romper vaults reales"; corrige el tag roto en runtime |
| Punto de enforcement | Función de dominio + boundaries del adaptador | No romper la ingesta; ver "Análisis previo" |
| ¿Validar en `Note.__post_init__`? | No | Frozen + raise rompería la ingesta de vaults reales |
| Alcance | Solo código + tests | No se edita ningún `.md` de vault |

Como las políticas de lectura y escritura convergen (ambas "normalizar y continuar"),
**una sola función** `normalize_tags()` sirve para los dos caminos.

### Análisis previo: dónde vive la validación de tags

**Aspecto crítico**: elegir el punto de enforcement sin romper la regla hexagonal ni la
ingesta de vaults reales.

**Opciones consideradas**:
1. Validar en `Note.__post_init__` — centraliza, pero al ser frozen y lanzar rompería la
   ingesta de cualquier vault real con un tag raro (contradice "no romper vaults reales").
2. Función de dominio pura cableada en los dos boundaries del adaptador (`_parse` para
   leer, `create` para escribir) — el modelo sigue permisivo; normalización localizada.

**Decisión**: Opción 2. `src/domain/tags.py` es dominio puro (importable por el adaptador
sin violar la dirección de dependencias) y el adaptador es el único sitio que toca
frontmatter, así que cubre ambos caminos con un solo cableado por lado.

**Riesgo aceptado**: `\w` Unicode preserva tildes, que la convención recomienda evitar; no
es un error (Obsidian las acepta) y evita normalización destructiva de acentos. Forzar
ASCII sería una extensión posterior documentada, no parte de esta regla.

## Mapa de cambios

### Ficheros nuevos
- `src/domain/tags.py` — `normalize_tag()`, `normalize_tags()`, `_TAG_RE` (solo stdlib).
- `tests/unit/test_tags.py` — 10 tests de la función pura.

### Ficheros modificados
- `src/adapters/obsidian_loader.py` — importa `normalize_tags`; lo cablea en `_parse`
  (lectura) y en `create` (escritura, antes de `frontmatter.Post`).
- `tests/unit/test_obsidian_loader.py` — 2 tests nuevos (lectura + create normalizan).

### Ficheros sin cambios
- `src/domain/models.py` (`Note` sigue permisivo), `src/agent/tools.py`,
  `src/application/manage_notes.py`, `backlink_aware.py` y `_BACKLINK_RE`.
- Ningún `.md` de vault.

## Especificación de `src/domain/tags.py`

- `_TAG_RE = re.compile(r"^[\w/-]+$", re.UNICODE)` — letras/números Unicode, `_`, `-`, `/`.
- `normalize_tag(tag)`: trim → quitar `#` inicial → espacios internos a `-` → `lower()`;
  devuelve `None` si queda vacío, es puramente numérico (`strip("-_/").isdigit()`) o no
  casa `_TAG_RE`. Preserva tildes y anidamiento `tipo/concepto`.
- `normalize_tags(tags)`: aplica `normalize_tag`, descarta `None` con warning, deduplica
  preservando orden.

Ejemplos: `personajes públicos`→`personajes-públicos`; `Distribuidos`→`distribuidos`;
`tipo/concepto`→`tipo/concepto`; `1984`→descartado; `y1984`→`y1984`.

## Estado final

- **112 tests unitarios en verde** (102 previos + 10 de tags; +2 de loader ya contados).
- `ruff check` + `ruff format`, `mypy src` y `check_architecture.py`: todos en verde.
- Lectura y escritura de tags pasan por `normalize_tags`; frontmatter `tags:` se serializa
  como lista YAML (verificado releyendo el `.md`).
- El backlink chunker no se ha tocado; ningún `.md` de vault modificado.

## TODOs por funcionalidad

### 🧩 Dominio
- [x] Crear `src/domain/tags.py` con `_TAG_RE`, `normalize_tag`, `normalize_tags`.

### 🔌 Adaptador (ObsidianLoader)
- [x] Cablear `normalize_tags` en `_parse` (lectura).
- [x] Cablear `normalize_tags` en `create` antes de `frontmatter.Post`.

### 🧪 Tests
- [x] Crear `tests/unit/test_tags.py` (10 casos de la spec).
- [x] Extender `tests/unit/test_obsidian_loader.py` (lectura + create normalizan).

### 📄 Documentación y verificación final
- [x] Actualizar `implementation-plan.md` en la raíz.
- [x] Gates: `pytest tests/unit/`, `ruff`, `mypy src`, `check_architecture.py` en verde.
- [x] Confirmar que no se ha tocado el backlink chunker ni ningún `.md` de vault.

---

## Follow-up: el agente no fijaba tags al crear/editar notas

**Síntoma reportado por el usuario**: al crear notas, el agente no genera tags; y
al pedirle explícitamente que añada tags, los escribe como `#tag` dentro del
`content` en vez de en el frontmatter.

**Diagnóstico** — dos causas distintas:
1. **Creación**: el pipeline de tags ya funcionaba (`create_note` → `ManageNotes.create`
   → `ObsidianLoader.create` → `normalize_tags` → frontmatter), pero el tool y el prompt
   ReAct no insistían en usarlo; modelos pequeños omiten campos "opcionales" bajo presión
   de generar JSON válido (ver `docs/error-log.md`).
2. **Edición**: `NoteWriter.update(note_id, content)` no aceptaba `tags` en absoluto — no
   existía ningún código para modificar tags de una nota existente. El LLM no tenía otra
   opción que inlinear `#tag` en `content`.

### Análisis previo: extender `NoteWriter.update` para tags

**Aspecto crítico**: el agente nunca ve los tags actuales de una nota (los resultados de
`search_vault` no los exponen), así que un reemplazo total de tags al editar podría
borrar tags existentes sin que el LLM lo sepa.

**Opciones consideradas**:
1. `update(note_id, content, tags: List[str])` obligatorio con reemplazo total — rompe
   llamadas existentes y es peligroso sin visibilidad de los tags actuales.
2. `update(note_id, content, tags: Optional[List[str]] = None)` — `None` preserva tags
   actuales (compatible con llamadas existentes); una lista se **fusiona** (unión vía
   `normalize_tags`) con los tags existentes, nunca los borra.

**Decisión**: Opción 2 (merge aditivo). Compatible hacia atrás y evita que el LLM borre
tags por accidente al no tener visibilidad de los actuales.

**Riesgo aceptado**: no permite *eliminar* un tag vía chat, solo añadir. Fuera del
alcance pedido; sería una extensión futura documentada.

### Mapa de cambios

- `src/domain/ports.py` — `NoteWriter.update` gana `tags: Optional[List[str]] = None`.
- `src/adapters/obsidian_loader.py` — `update()` fusiona `existing.tags + tags` vía
  `normalize_tags` cuando `tags is not None`.
- `src/application/manage_notes.py` — `ManageNotes.update` gana el mismo parámetro y lo
  propaga.
- `src/agent/tools.py` — `create_note`/`edit_note`: descripciones reforzadas explicando
  que los tags van en el campo JSON `tags` (nunca `#tag` en `content`), y que en
  `edit_note` los tags se suman a los existentes.
- `src/agent/agent.py` — nueva regla en el prompt ReAct sobre el uso de tags.
- Tests actualizados/nuevos en `test_manage_notes.py`, `test_tools.py` y
  `test_obsidian_loader.py` (merge de tags, preservación con `tags=None`).

### Estado final

- **116 tests unitarios en verde**; `ruff`, `mypy` y `check_architecture.py` en verde.
- Verificado manualmente sobre una copia del vault externo real: `update(..., tags=[...])`
  añade el tag normalizado preservando los existentes (incluido el previamente roto
  `personajes-públicos`, ya corregido en lectura).

### TODOs

- [x] Extender `NoteWriter.update` (puerto) con `tags: Optional[List[str]] = None`.
- [x] Implementar merge en `ObsidianLoader.update`.
- [x] Propagar en `ManageNotes.update`.
- [x] Reforzar descripciones de `create_note`/`edit_note` en `tools.py`.
- [x] Añadir regla de tags al prompt ReAct en `agent.py`.
- [x] Tests: merge de tags, `tags=None` preserva, propagación en las 3 capas.
- [x] Gates: `pytest tests/unit/`, `ruff`, `mypy src`, `check_architecture.py` en verde.
