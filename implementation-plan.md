# Plan de implementación: Importar ficheros .md al vault persistente

> Plan guardado en git. Los planes de fases anteriores se conservan en el
> historial: `git log --oneline -- implementation-plan.md`.
>
> Generado como entregable obligatorio de la skill `critical-task-planning`
> para la tarea `tasks/feature-import-md-files.md`.

## 1. Contexto y decisión de fondo

Hoy el usuario no puede meter una nota externa en su segundo cerebro sin
copiarla a mano al vault y relanzar `scripts/ingest.py`. La única vía de
escritura desde el chat es que el **LLM redacte** la nota (`create_note`), lo
que no sirve para material que ya existe.

Esta feature añade una vía **determinista de UI**: adjuntar uno o varios `.md`
a un mensaje de Chainlit los escribe en el vault real e indexa en ChromaDB en
las tres estrategias de chunking. Sin LLM de por medio: adjuntar es la orden.

Especificación de origen: `tasks/feature-import-md-files.md`.

### Diagnóstico — hallazgos que cambian la spec

La spec pedía verificar cada premisa antes de implementar. Resultado:

| Premisa de la spec | Realidad verificada |
|---|---|
| `spontaneous_file_upload` desactivado | Cierto — `.chainlit/config.toml:37` `enabled = false` |
| `on_message` no lee `message.elements` | Cierto — cero ocurrencias de `message.elements` / `cl.File` en `src/`; los únicos `elements` eran de **salida** (`src/app/__init__.py:331`) |
| «`create_note`/`edit_note` ya siguen el patrón `READONLY_MODE`» | **Matiz crítico**: el único gate vivía en `create_agent()` (`src/agent/agent.py:175`), que simplemente no registra las tools. No hay guarda en `NoteWriter` ni en `ManageNotes`. Un handler de UI que llame a `ManageNotes` directamente se salta ese gate si no se replica explícitamente |
| Existe `tasks/obsidian-note-creation-conventions.md` | El fichero real es `tasks/tasks-obsidian-note-creation-conventions.md`; sí se ejecutó (commit `f8970a0`) |
| «reutilizar el validador de convenciones» | `src/domain/obsidian_conventions.py` existe, pero solo `sanitize_filename` está cableada a producción (`obsidian_loader.py:15`). `validate_tag`/`build_frontmatter` no están en ningún camino de escritura real; la normalización real es `normalize_tags` (`src/domain/tags.py:60`) |
| Existe `tasks/feature-hot-vault-upload.md` | No existe. No hay solapamiento que resolver |
| Indexar en todas las estrategias es trabajo nuevo | Ya resuelto: `IngestVault.execute_single` itera `all_chunkers` (`ingest_vault.py:86-91`) y el wiring de Chainlit ya lo inyecta (`src/app/__init__.py:199` en el estado previo). Se hereda gratis vía `ManageNotes` |
| Puede existir ya un límite de tamaño | No existía ninguno en `.env.example` ni en `src/`. Se definió `MAX_IMPORT_SIZE_MB=1` |

Chainlit instalado: 2.11.1. `SpontaneousFileUploadFeature` admite
`accept: Optional[Union[List[str], Dict[str, List[str]]]]`, así que se pudo
restringir a `.md` con `accept = { "text/markdown" = [".md"] }`.

## 2. Análisis previo (aspectos críticos)

### 2.1 Cómo escribir un `.md` importado sin perder datos

**Aspecto crítico**: `NoteWriter.create(title, content, tags)` reconstruye el
frontmatter desde cero (`frontmatter.Post(content, title=title, tags=...)`,
`obsidian_loader.py:126`) y nombra el fichero con `sanitize_filename(title)`.
Es un contrato pensado para que el LLM dicte una nota, no para preservar un
documento existente.

**Opciones consideradas**:
1. Reutilizar `ManageNotes.create()` parseando el `.md` → cero cambios en
   dominio/adaptador, pero descarta en silencio `aliases`, `type`,
   `created_at` y cualquier campo custom, y renombra el fichero según el
   `title:` del frontmatter en vez de según el fichero subido.
2. Añadir `create_raw(filename, raw_content, policy)` al puerto `NoteWriter`
   → escribe el documento preservando su frontmatter íntegro; el `note_id`
   deriva del nombre del fichero.

**Decisión**: Opción 2 (confirmada por el usuario). La pérdida silenciosa de
frontmatter es inaceptable en una feature cuyo objetivo literal es importar
notas ajenas. `NoteWriter` tiene una sola implementación (`ObsidianLoader`),
así que el coste real es bajo.

**Riesgo aceptado**: re-serializar con `frontmatter.dumps` puede reordenar
claves YAML. Mitigación implementada: si `normalize_tags(tags_originales) ==
tags_originales`, se escribe el contenido crudo byte a byte sin pasar por
`dumps`; solo se re-serializa cuando la normalización de tags obliga a ello
(`ObsidianLoader._normalize_raw_tags`).

### 2.2 Resolución de conflictos de `note_id`

**Aspecto crítico**: la app (capa externa) no debe consultar el filesystem
para decidir si hay conflicto — duplicaría la comprobación que ya hace el
adaptador y rompería la regla hexagonal.

**Opciones consideradas**:
1. El handler llama a `loader.exists(note_id)` antes de escribir → reimplementa
   en la app el cálculo de slug/carpeta destino, y hay TOCTOU.
2. Enum de dominio `ImportConflictPolicy` (`FAIL`/`OVERWRITE`/`COPY`) pasado al
   adaptador; el handler intenta con `FAIL`, y solo si captura
   `VaultWriteError` pregunta al usuario y reintenta con la política elegida.

**Decisión**: Opción 2. El adaptador sigue siendo el único que conoce rutas y
slugs; la app solo aporta la política elegida por el usuario.

**Riesgo aceptado**: dos intentos de escritura en el caso de conflicto. I/O
despreciable; `FAIL` aborta antes de escribir nada.

### 2.3 Gate de `READONLY_MODE` para una acción que no pasa por el agente

**Aspecto crítico**: el gate existente es «no registrar la tool en el
agente». `_handle_md_import` no es una tool del agente, así que ese gate no
la cubre por sí solo.

**Decisión**: replicar exactamente el patrón `prune_orphans`
(`src/app/__init__.py`): guardar en sesión `None if readonly else manage_uc`
bajo la clave `manage_notes`, y que `_handle_md_import` compruebe `is None`
al inicio, respondiendo con el mismo texto ya usado para `/prune`. Se
descartó meter la guarda dentro de `ObsidianLoader` por la misma razón ya
documentada para `create`/`update`: no mezclar política de aplicación con un
adaptador de I/O.

**Riesgo aceptado**: la guarda es por-sesión, no por-turno; si `READONLY_MODE`
cambia en caliente hace falta recargar. Idéntico al comportamiento ya
existente de `/prune`.

## 3. Decisiones cerradas con el usuario

| Decisión | Elección |
|---|---|
| Escritura | Preservar frontmatter íntegro vía `create_raw` |
| `note_id` | `sanitize_filename(Path(filename).stem)` → `00-inbox/<slug>` |
| Conflicto | `AskActionMessage`: Sobrescribir / Importar como copia (`-1`) / Cancelar |
| Confirmación previa | No — adjuntar ya es la orden explícita del usuario |

## 4. Mapa de cambios (implementado)

- `src/domain/models.py` — nuevo enum `ImportConflictPolicy` (`FAIL`,
  `OVERWRITE`, `COPY`).
- `src/domain/ports.py` — nuevo método abstracto `NoteWriter.create_raw()`.
- `src/adapters/obsidian_loader.py` — `create_raw()` (políticas FAIL/
  OVERWRITE/COPY, atajo byte a byte cuando los tags no cambian) +
  `_next_copy_path()` + `_normalize_raw_tags()`.
- `src/application/manage_notes.py` — `import_markdown()`: valida extensión
  `.md`, delega en `create_raw` y reindexa vía `execute_single` (fan-out a
  todas las estrategias, ya existente).
- `src/infrastructure/config.py` — `_get_int()` helper + `get_max_import_size_mb()`.
- `src/app/__init__.py` — `manage_notes` en sesión (guarda readonly),
  `_handle_md_import`, `_import_one_md`, `_ask_import_conflict`, hook en
  `on_message` tras el bloque de comandos `/reset`/`/prune`.
- `.chainlit/config.toml` — `spontaneous_file_upload` reactivado, restringido
  a `.md`, `max_size_mb = 1`.
- `.env.example` — `MAX_IMPORT_SIZE_MB=1`.
- `CLAUDE.md` — variable de entorno, `create_raw`/`import_markdown` en el
  inventario, `ImportConflictPolicy` en entidades de dominio.

## 5. Tests (implementados)

- `tests/unit/test_models.py::test_import_conflict_policy_values`
- `tests/unit/test_obsidian_loader.py` — 6 tests de `create_raw` (preserva
  frontmatter, deriva note_id del filename, normaliza tags, FAIL/OVERWRITE/
  COPY)
- `tests/unit/test_manage_notes.py` — 5 tests de `import_markdown` (note_id
  esperado, rechaza extensión no-.md, propaga conflicto, fan-out de
  estrategias, devuelve nº de chunks)
- `tests/unit/test_config.py` — 3 tests de `get_max_import_size_mb`
- `tests/unit/test_app.py::TestHandleMdImport` — guarda de `READONLY_MODE`

## 6. Orden de ejecución con gates (seguido)

1. Dominio → `pytest tests/unit/test_models.py`
2. Adaptador → `pytest tests/unit/test_obsidian_loader.py`
3. Aplicación → `pytest tests/unit/test_manage_notes.py`
4. Infraestructura → `pytest tests/unit/test_config.py`
5. App → `pytest tests/unit/test_app.py`
6. Configuración y documentación
7. Gate final: `ruff format` + `ruff check` + `mypy src` +
   `check_architecture.py` + `pytest tests/unit/`

## 7. Criterio de completado

- Todos los gates incrementales en verde.
- `pytest tests/unit/` completo en verde, sin regresiones en los 168+ tests
  previos.
- `python scripts/check_architecture.py` sin violaciones.
- Verificación manual con `chainlit run app.py`: subir un `.md` con
  `aliases`/`type`/campo custom, confirmar que sobreviven en disco, que la
  nota es buscable vía `search_vault`, que un segundo intento del mismo
  fichero dispara el diálogo de conflicto, y que `READONLY_MODE=true` bloquea
  el import.

## 8. TODOs por funcionalidad

### 🧩 Dominio
- [x] `ImportConflictPolicy` en `src/domain/models.py`
- [x] `NoteWriter.create_raw()` abstracto en `src/domain/ports.py`
- [x] Test del enum en `tests/unit/test_models.py`

### 🔌 Adaptador
- [x] `ObsidianLoader.create_raw()` con las 3 políticas + normalización de tags
- [x] Atajo byte-a-byte cuando los tags ya están normalizados
- [x] 6 tests en `tests/unit/test_obsidian_loader.py`

### ⚙️ Aplicación
- [x] `ManageNotes.import_markdown()` con validación de extensión
- [x] 5 tests en `tests/unit/test_manage_notes.py`

### 🏗️ Infraestructura
- [x] `get_max_import_size_mb()` en `src/infrastructure/config.py`
- [x] Tests en `tests/unit/test_config.py`

### 💬 App / Chainlit
- [x] Guardar `manage_notes` en sesión con guarda de readonly
- [x] `_handle_md_import()` con `asyncio.to_thread`, límite de tamaño y `UnicodeDecodeError`
- [x] Diálogo de conflicto `AskActionMessage` (Sobrescribir / Copia / Cancelar)
- [x] Resumen en chat: `note_id` y chunks por fichero
- [x] Hook en `on_message` respetando la convivencia adjunto + texto
- [x] `test_import_md_blocked_when_readonly_mode_enabled` en `tests/unit/test_app.py`

### 📝 Configuración y documentación
- [x] `.chainlit/config.toml`: `enabled = true`, `accept` restringido a `.md`, `max_size_mb = 1`
- [x] `.env.example`: `MAX_IMPORT_SIZE_MB=1`
- [x] `CLAUDE.md`: variable de entorno + `create_raw` / `import_markdown` en el inventario
- [ ] Marcar el checklist de `tasks/feature-import-md-files.md`

### ✅ Verificación final
- [ ] `ruff format` + `ruff check` + `mypy src` + `check_architecture.py` + `pytest tests/unit/`
- [ ] Verificación manual con `chainlit run app.py`
- [ ] `docs/error-log.md` si aparece algún fallo no previsto

## 9. Desviación respecto al plan aprobado inicialmente

El plan aprobado mencionaba avisar en el chat de los tags descartados por
`normalize_tags` comparando el frontmatter original con `note.tags`. Se
decidió no implementarlo: exigiría re-parsear el frontmatter crudo en la capa
de app (duplicando lógica que ya vive en el adaptador) solo para un mensaje
informativo no cubierto por ninguno de los tests requeridos por la spec. El
descarte de tags inválidos ya queda registrado por el `logger.warning`
existente en `src/domain/tags.py:77`. Se prioriza no ampliar el alcance sobre
una funcionalidad de UI no solicitada explícitamente.
