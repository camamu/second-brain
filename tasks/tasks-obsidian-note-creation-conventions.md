# Task: Convenciones de Obsidian en la creación/edición de notas

## Contexto

El agente necesita crear y/o editar notas `.md` dentro del vault de forma que
sean 100% compatibles con Obsidian: frontmatter YAML válido, tags bien
formados, y wikilinks que generen backlinks reales (de los que depende
`BacklinkAwareChunker`).

**Aviso importante detectado antes de este task**: el `README.md` actual del
repo indica que en la demo desplegada las herramientas de creación/edición de
notas están deshabilitadas (`READONLY_MODE=true`). Antes de implementar nada,
hay que confirmar el estado real de esto en el código (puede que el README
esté desactualizado, como ya sabemos que pasa con `CLAUDE.md`/`AGENTS.md`).

## Diagnóstico previo (obligatorio, no saltar)

Antes de escribir una sola línea de código, localizar y citar con `file:line`:

1. ¿Existe ya algún módulo que escriba archivos `.md` en el vault? Buscar por
   términos como `create_note`, `write_note`, `NoteWriter`, `save_note`,
   `frontmatter`, `yaml.dump`, `.md"` en `src/`.
2. ¿Dónde se define `READONLY_MODE` y qué condiciona exactamente? Buscar en
   `src/`, `.env.example`, y en la definición de tools del agente ReAct
   (carpeta `agent/` o donde estén registradas las tools de LangChain).
3. ¿Qué tools tiene actualmente registradas el agente? Listarlas todas
   (lectura y escritura) con su ubicación exacta.
4. ¿Existe ya `tasks/obsidian-tag-conventions.md` con reglas de tags? Si
   existe, leerlo entero y NO duplicar contenido — este task debe
   complementarlo (frontmatter completo + wikilinks), referenciándolo en vez
   de repetirlo.
5. Confirmar en qué capa de la arquitectura hexagonal debería vivir esto:
   la generación/validación de una nota es lógica de dominio (no depende de
   Chainlit, Groq ni ChromaDB), así que el candidato natural es `domain/`,
   con un puerto en `application/` y el adaptador de escritura a disco en
   `adapters/`. Confirmar que esta suposición encaja con la estructura real
   antes de crear archivos nuevos.

Si el diagnóstico revela que `READONLY_MODE=true` bloquea esto a propósito
para la demo pública, no lo desactives sin confirmar conmigo — puede ser
intencional para evitar que usuarios de la demo escriban en el vault de
producción.

## Resultados del diagnóstico

1. **Sí existe** un módulo completo que escribe `.md` en el vault:
   `src/adapters/obsidian_loader.py` — clase `ObsidianLoader` implementa
   `NoteWriter`. `create()` (líneas 102-128, antes del refactor de esta
   tarea) generaba frontmatter YAML vía la librería `python-frontmatter`
   y normalizaba tags vía `src/domain/tags.py::normalize_tags`.
   `update()` (líneas 130-153) preserva frontmatter y hace unión de
   tags. Ninguno de los dos construía ni validaba wikilinks al escribir
   (solo se extraen al leer, vía `_BACKLINK_RE`, línea 20).
2. `READONLY_MODE` se define en `src/infrastructure/config.py::is_readonly()`
   (lee `os.getenv("READONLY_MODE", ...)`, default `false` en
   `.env.example:20`). El bloqueo real no está en el puerto/adaptador:
   `src/agent/agent.py::create_agent()` (líneas 174-188) simplemente NO
   registra las tools `create_note`/`edit_note` en la lista `tools`
   cuando `readonly=True`. `README.md:41` documenta que la demo pública
   desplegada usa `READONLY_MODE=true` (config de despliegue, no
   contradice el default `false` de `.env.example`).
3. Tools registradas del agente ReAct (`src/agent/tools.py`,
   ensambladas en `src/agent/agent.py:174-188`): `search_vault`
   (siempre disponible), `create_note` y `edit_note` (solo si
   `readonly=False`, y solo con `confirm_action` obligatorio — ver
   `docs/error-log.md:549-611`).
4. `tasks/obsidian-tag-conventions.md` **no existe** en el repo (se
   comprobó con `find`). No hay nada que evitar duplicar en ese frente.
5. La entidad `Note` ya existe en `src/domain/models.py:85-162` y el
   puerto `NoteWriter` ya existe en `src/domain/ports.py:128-179`,
   ambos implementados — el "Diseño propuesto" de más abajo (crear
   `domain/note.py`, un `NoteWriterPort` nuevo) está desactualizado
   respecto al código real. Ver `implementation-plan.md` (raíz del
   repo) para el diseño final aplicado, que reutiliza estas piezas
   existentes en vez de recrearlas.

**Decisión sobre `READONLY_MODE`**: no requiere ningún cambio. El gate
en `create_agent()` ya es correcto y suficiente (único punto de entrada
a `NoteWriter` es vía `ManageNotes`/agente, ya gateados). Añadir un
guard adicional dentro de `ObsidianLoader`/`NoteWriter` metería lógica
de política de aplicación en un adaptador de I/O puro sin caso de uso
real que lo requiera. Esta es una confirmación de diseño correcto, no
una corrección de un error — no se registra en `docs/error-log.md` (ver
`implementation-plan.md`, Análisis previo 4.5, para el detalle
completo).

## Especificación funcional: convenciones de Obsidian a implementar

### Frontmatter (YAML)
- Debe ser la primera línea absoluta del archivo, delimitado por `---` /
  `---`, sin líneas en blanco antes.
- Claves reservadas a soportar: `tags` (lista), `aliases` (lista),
  `cssclasses` (lista, opcional, no crítico para el TFM).
- Serialización de `tags` siempre como lista YAML, nunca como string:
  ```yaml
  tags:
    - tipo/concepto
    - dominio/sistemas-distribuidos
  ```
- Tipos de propiedad a validar si se exponen campos custom: `text`, `list`,
  `number`, `checkbox`, `date` (`YYYY-MM-DD`), `datetime` (ISO 8601).

### Tags
- Prefijo `#` solo aplica a tags inline en el cuerpo; en frontmatter van sin
  `#`, como strings de la lista.
- Sin espacios.
- Al menos un carácter no numérico (`1984` inválido, `y1984` válido).
- Anidación con `/` (namespace): `tipo/concepto`, `tipo/moc`, `dominio/<area>`.
- Case-insensitive a efectos de Obsidian, pero generar siempre en minúsculas
  para consistencia interna del vault.

### Wikilinks (lo que alimenta el backlink chunker)
- Enlace simple: `[[Nombre Nota]]`
- Con alias: `[[Nombre Nota|Texto mostrado]]`
- A un encabezado: `[[Nombre Nota#Encabezado]]`
- A un bloque: `[[Nombre Nota#^block-id]]` (block-id: solo letras, números,
  guiones)
- Embebido (transclusión): `![[Nombre Nota]]` o `![[Nombre Nota#Sección]]`
- **Regla de negocio clave**: toda relación semántica entre conceptos que
  quede reflejada como backlink debe crearse como `[[wikilink]]` en el
  cuerpo, nunca como tag. Los tags no generan aristas en el grafo.

### Nombres de archivo
- El nombre de archivo = título de la nota (sin `.md` en el wikilink).
- Sanear/rechazar estos caracteres antes de crear el archivo, porque rompen
  la sintaxis de enlaces: `# | ^ : %% [ ]`

## Diseño propuesto (validar contra el diagnóstico antes de aplicar)

- `domain/note.py` (o donde vivan las entidades de dominio ya existentes):
  entidad `Note` con `title`, `frontmatter: dict`, `body: str`, `tags: list[str]`,
  `links: list[str]`.
- `domain/obsidian_conventions.py`: funciones puras de validación/formateo,
  sin dependencias externas:
  - `validate_tag(tag: str) -> bool`
  - `sanitize_filename(title: str) -> str`
  - `build_frontmatter(tags: list[str], aliases: list[str] | None = None) -> str`
  - `build_wikilink(target: str, alias: str | None = None, heading: str | None = None) -> str`
- `application/`: puerto `NoteWriterPort` (interfaz) si no existe ya un
  concepto equivalente.
- `adapters/`: implementación concreta que escribe a disco (o al vault
  configurado), usando las funciones de dominio para construir el contenido
  antes de persistir.

**No tocar**: ingestión (`scripts/ingest.py`), chunkers existentes, ni la
configuración de Chainlit/Groq. Este task es exclusivamente sobre la
creación/formateo de notas nuevas.

## Tests requeridos

- `test_validate_tag_rejects_purely_numeric`
- `test_validate_tag_rejects_spaces`
- `test_validate_tag_accepts_nested_namespace`
- `test_sanitize_filename_strips_forbidden_characters`
- `test_build_frontmatter_serializes_tags_as_yaml_list`
- `test_build_frontmatter_places_delimiters_at_file_start`
- `test_build_wikilink_simple`
- `test_build_wikilink_with_alias`
- `test_build_wikilink_with_heading`
- `test_build_wikilink_with_block_id`
- ~~`test_note_writer_port_rejects_when_readonly_mode_enabled`~~ —
  **retirado**: el diagnóstico confirmó que `READONLY_MODE` se aplica a
  nivel de registro de tools en `create_agent()`, no dentro del puerto
  `NoteWriter`; un guard ahí sería redundante y violaría separación de
  responsabilidades. Ver "Decisión sobre `READONLY_MODE`" arriba y
  `implementation-plan.md` (Análisis previo 4.5).

Tests adicionales implementados, no listados en la spec original (ver
`implementation-plan.md` sección 5 para la justificación completa):
`test_sanitize_filename_lowercases_and_hyphenates`,
`test_validate_tag_rejects_uppercase`,
`test_build_frontmatter_omits_aliases_when_none`,
`test_build_wikilink_embed_prefixes_bang`,
`test_build_wikilink_heading_and_block_id_raises_value_error`,
`test_build_wikilink_empty_target_raises_value_error`,
`test_build_wikilink_invalid_block_id_raises_value_error`, más 2 tests
de regresión en `tests/unit/test_obsidian_loader.py` que verifican que
la ruta real de escritura (vía `python-frontmatter`) cumple las mismas
propiedades que valida `build_frontmatter` de forma aislada.

## Checklist de completitud

- [x] Diagnóstico documentado con `file:line` de los 5 puntos de arriba
      (ver "Resultados del diagnóstico")
- [x] Confirmado si `tasks/obsidian-tag-conventions.md` existe y contenido
      cruzado sin duplicar (no existe)
- [x] Decisión explícita sobre `READONLY_MODE` (mantener/ajustar) documentada
      en `docs/error-log.md` si aplica (no aplica — confirmación de diseño
      correcto, no un error; documentado arriba e `implementation-plan.md`)
- [x] Funciones de dominio implementadas y puras (sin I/O) —
      `src/domain/obsidian_conventions.py`
- [x] Tests listados arriba pasando (16 en
      `tests/unit/test_obsidian_conventions.py` + 2 de regresión en
      `tests/unit/test_obsidian_loader.py`, 168 tests totales en verde)
- [x] Lint/typecheck/ruff/mypy en verde
- [x] Boundary check de arquitectura hexagonal en verde (dominio no importa
      de adapters/infrastructure) — `python scripts/check_architecture.py`
- [x] README actualizado si el comportamiento de creación de notas cambia
      respecto a lo que dice hoy — no requiere cambios: el refactor es
      behavior-preserving (mismo slug, mismo frontmatter), sin cambio de
      comportamiento observable para el usuario
