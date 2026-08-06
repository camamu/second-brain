# Plan de implementación: mover notas con confirmación del usuario

> Plan guardado en git. Los planes de fases anteriores se conservan en el
> historial: `git log --oneline -- implementation-plan.md`.
>
> Generado como entregable obligatorio de la skill `critical-task-planning`
> para la tarea `tasks/feature-move-note-suggestion.md`.

## 1. Contexto y decisión de fondo

`tasks/feature-move-note-suggestion.md` pide que el agente pueda proponer mover una nota
de `00-inbox/` a una carpeta más adecuada, ejecutando el movimiento sólo tras confirmación
explícita del usuario. Hoy no existe ninguna operación de movimiento: `note_id` **es** la
ruta relativa sin extensión (`obsidian_loader.py:259`), así que mover una nota cambia su
identidad y obliga a reindexar sus chunks.

La fase de diagnóstico obligatoria de la spec detectó **tres premisas que no se sostienen**
contra el código real. Las tres cambian el diseño.

### Contradicción 1 — los wikilinks NO resuelven por nombre de fichero

La spec (`tasks/feature-move-note-suggestion.md:45`) plantea que si Obsidian resuelve por
nombre, mover de carpeta no rompe backlinks. **En esta implementación es falso**:
`ObsidianLoader.exists()` hace `(self._vault / f"{note_id}.md").exists()`
(`obsidian_loader.py:85`) y `load_by_id` lo mismo (`obsidian_loader.py:71`). El texto dentro
de `[[...]]` se trata como **path relativo desde la raíz del vault**, no como stem.
`BacklinkAwareChunker` resuelve de forma perezosa contra el filesystem, sin índice ni grafo
(`backlink_aware.py:66-72`) — descartando en silencio lo que no resuelve.

> Dato del vault real: de 21 targets únicos de wikilink en `VAULT_PATH`, **16 ya están
> rotos hoy** por estar escritos con stem (`[[arquitectura-hexagonal]]` en vez de
> `[[02-areas/arquitectura/arquitectura-hexagonal]]`).

**Decisión (usuario):** al mover, **reescribir los enlaces entrantes** `[[old_id]]` →
`[[new_id]]` preservando alias, y reindexar las notas afectadas.

### Contradicción 2 — el vault demo no tiene «4 MOCs»

La spec (`:21-22`) describe «4 MOCs + notas atómicas». El vault real (`VAULT_PATH` →
`tfm/vault-demo`) tiene estructura **PARA**: `00-inbox/`, `01-proyectos/tfm/`,
`02-areas/{arquitectura,python,rag}/`, `03-recursos/`. No hay ninguna nota MOC, y los tres
valores de `type` del frontmatter (`concepto`, `recurso`, `proyecto`) no están en
`_NOTE_TYPE_MAP`, así que todas caen a `NoteType.OTHER`.

**Decisión (usuario):** las carpetas se descubren en runtime mediante una **tool aparte
`list_folders`**; el agente nunca inventa destinos.

### Contradicción 3 — el patrón de confirmación a reutilizar

La spec pide replicar `_confirm_and_prune` (`app/__init__.py:115`) y una tool
`suggest_move_note` que no mueve nada. Pero el repo ya tiene el patrón correcto para
escrituras del agente: `_confirm_write_action` (`app/__init__.py:96`) — el **mismo**
mecanismo `cl.AskActionMessage` (su propio docstring dice «Mismo patrón que
`_confirm_and_prune`») — inyectado como `ConfirmCallback` (`tools.py:22`) y llamado por
`create_note`/`edit_note` antes de escribir. La entrada #11 de `docs/error-log.md:549`
concluye que la garantía debe ser estructuralmente ineludible en la tool, no en el prompt.

**Decisión (usuario):** una única tool `move_note` que `await`ea `confirm_action(summary)`
antes de mover. Sigue cumpliendo «el agente sugiere, el usuario confirma»: sin pulsar el
botón no se mueve nada. Sin estado por closure entre turnos, sin UI nueva.

---

## 2. Mapa de cambios

| Fichero | Acción |
|---|---|
| `src/domain/models.py` | + `MoveResult` (frozen dataclass) |
| `src/domain/ports.py` | + `NoteWriter.move()` (abstracto) |
| `src/domain/obsidian_conventions.py` | + `rewrite_wikilink_target()` |
| `src/adapters/obsidian_loader.py` | + `move()` con validación anti path-traversal |
| `src/application/move_note.py` | **nuevo** — caso de uso `MoveNote` |
| `src/agent/tools.py` | + `create_move_tool()`, `create_list_folders_tool()` |
| `src/agent/agent.py` | registrar tools + bloque de prompt «MOVER NOTAS»; fix `01-inbox`→`00-inbox` |
| `src/app/__init__.py` | construir `MoveNote` y pasarlo a `create_agent` |
| `tests/unit/` | 4 ficheros (ver sección Tests) |
| `CLAUDE.md`, `docs/error-log.md`, `tasks/feature-move-note-suggestion.md` | sincronizar |

---

## 3. Análisis previo (bloques exigidos por `critical-task-planning`)

### Análisis previo: dónde vive el movimiento físico

**Aspecto crítico**: `NoteWriter` no tiene `move` ni `delete` (`ports.py:129-209`). Meter
el `rename` en el caso de uso violaría la regla hexagonal (application no toca `pathlib`).

**Opciones consideradas**:
1. `MoveNote` hace `Path.rename` directamente — rápido, pero mete I/O de filesystem en la
   capa de aplicación; rompe la testabilidad con mocks.
2. Ampliar el puerto `NoteWriter` con `move(note_id, target_folder) -> Note` — coherente
   con `create`/`update`/`create_raw`, testeable con `MagicMock(spec=NoteWriter)`.

**Decisión**: Opción 2. Es el mismo movimiento que ya se hizo al añadir `create_raw` para
la importación de `.md`, y mantiene `MoveNote` puramente orquestador.

**Riesgo aceptado**: ampliar un ABC obliga a que cualquier futuro `NoteWriter` implemente
`move`. Hoy sólo existe `ObsidianLoader`, que implementa ambos puertos, así que el coste
es cero.

### Análisis previo: orden de las operaciones de reindexado

**Aspecto crítico**: `IngestVault.execute_single(note_id)` ya hace
`store.delete_by_note(note_id)` + reindex en **todas** las estrategias
(`ingest_vault.py:84-91`). Pero borra por el id **nuevo**; los chunks bajo el id
**antiguo** quedarían huérfanos en las tres colecciones.

**Opciones consideradas**:
1. Confiar sólo en `execute_single(new_id)` — deja huérfanos silenciosos que sólo `/prune`
   limpiaría después.
2. `store.delete_by_note(old_id)` explícito + `ingest.execute_single(new_id)` — un delete
   extra, reutiliza el fan-out multi-estrategia ya existente sin duplicarlo.

**Decisión**: Opción 2. `ChromaVectorStore.delete_by_note` ya itera todas las colecciones
(`chroma_store.py:237-262`), así que cubre las tres estrategias con una sola llamada. Es
la misma lección de la entrada #16 del error-log (`:890`): lo escrito desde el chat debe
indexarse en todas las estrategias, no sólo en la activa.

**Riesgo aceptado**: si el proceso muere entre el `rename` y el `delete_by_note(old_id)`,
el índice queda con chunks del path antiguo. Mitigación: ya existe `/prune` para
detectarlos y limpiarlos (`PruneOrphans.find_orphans`, `prune_orphans.py:27`).

### Análisis previo: atomicidad del reenlazado

**Aspecto crítico**: reescribir `[[old_id]]` en N notas no es atómico. Un fallo a mitad
deja la nota movida y parte de los enlaces sin actualizar.

**Opciones consideradas**:
1. Todo-o-nada con rollback del `rename` — requiere deshacer escrituras ya hechas en N
   ficheros; complejidad desproporcionada para el alcance del TFM.
2. Best-effort por nota: capturar el error de cada reescritura, loguear con `exc_info`,
   continuar, y devolver en `MoveResult` la lista de las que fallaron para informar al
   usuario.

**Decisión**: Opción 2. El estado resultante nunca es peor que el actual (donde el 76% de
los wikilinks ya está roto), y el usuario recibe el detalle exacto de qué quedó pendiente.

**Riesgo aceptado**: enlaces parcialmente reescritos. Mitigación: mensaje explícito
listando las notas no reenlazadas para corrección manual.

---

## 4. Especificación

### 4.1 Dominio

`src/domain/models.py` — nuevo frozen dataclass, junto a las demás entidades:

```python
@dataclass(frozen=True)
class MoveResult:
    """Resultado de mover una nota: nuevo estado + efectos colaterales."""
    note: Note                       # nota ya en su nueva ubicación
    old_id: str
    chunks_indexed: int              # chunks de la nota movida, todas las estrategias
    relinked_notes: list[str]        # notas cuyos [[...]] se reescribieron con éxito
    failed_relinks: list[str]        # notas que no se pudieron reenlazar
```

`src/domain/ports.py` — añadir a `NoteWriter` (misma convención de docstring que
`create_raw`):

```python
@abstractmethod
def move(self, note_id: str, target_folder: str) -> Note:
    """Mueve una nota a otra carpeta del vault, preservando su contenido.

    Raises:
        NoteNotFoundError: Si la nota origen no existe.
        VaultWriteError: Si la carpeta destino no existe, está fuera del
            vault, o ya hay un fichero con ese nombre en el destino.
    """
```

`src/domain/obsidian_conventions.py` — junto a `sanitize_filename`/`normalize_tags`:

```python
def rewrite_wikilink_target(content: str, old_target: str, new_target: str) -> str:
    """Sustituye [[old]] y [[old|alias]] por [[new]] / [[new|alias]]."""
```
Regex: `r"\[\[" + re.escape(old_target) + r"(\|[^\]]+)?\]\]"`, coherente con
`_BACKLINK_RE` (`obsidian_loader.py:21`).

### 4.2 Adaptador — `ObsidianLoader.move()`

Junto a `create_raw` (`obsidian_loader.py:155`):

1. `existing = self.load_by_id(note_id)` → propaga `NoteNotFoundError`.
2. `dest_dir = (self._vault / target_folder).resolve()`.
3. **Validación anti path-traversal**: `if not dest_dir.is_relative_to(self._vault.resolve())`
   → `VaultWriteError`. Hoy `load_by_id`/`update` no validan nada (`obsidian_loader.py:71`,
   `:145`) con `note_id` controlado por el LLM; no repetimos ese agujero en el código nuevo.
4. `if not dest_dir.is_dir()` → `VaultWriteError` (no se crean carpetas: el agente sólo
   mueve a destinos existentes).
5. `dest = dest_dir / Path(existing.path).name`; si `dest == src` → `VaultWriteError`
   («ya está en esa carpeta»); si `dest.exists()` → `VaultWriteError`.
6. `Path(existing.path).rename(dest)` y `return self._parse(dest)`.

Normalizar `target_folder` a separador `/` y hacer `strip("/")` antes de componer.

### 4.3 Aplicación — `src/application/move_note.py`

Precedente de clase con varios métodos públicos: `PruneOrphans`
(`find_orphans` + `execute`, `prune_orphans.py:27`).

```python
class MoveNote:
    def __init__(self, loader: NoteLoader, writer: NoteWriter,
                 store: VectorStore, ingest: IngestVault) -> None: ...

    def list_folders(self) -> list[str]:
        """Carpetas existentes en el vault, derivadas de los note_id."""
        # dirname de cada note.id de loader.load_all(), dedup + sorted.
        # Reutiliza load_all() igual que PruneOrphans.find_orphans().

    def find_inbound_links(self, note_id: str) -> list[str]:
        """note_id de las notas que contienen [[note_id]]."""
        # Usa note.backlinks, ya parseado por _parse (obsidian_loader.py:257).
        # Cero regex nueva aquí.

    def execute(self, note_id: str, target_folder: str) -> MoveResult: ...
```

`execute()` en orden estricto:
1. `inbound = self.find_inbound_links(note_id)` — **antes** de mover (después el id ya no existe).
2. `note = self._writer.move(note_id, target_folder)`.
3. `self._store.delete_by_note(note_id)` — limpia el id antiguo en las 3 colecciones.
4. `chunks = self._ingest.execute_single(note.id)` — reindexa en todas las estrategias.
5. Por cada `linker_id` de `inbound`, dentro de un `try/except ObsidianRagError`:
   `rewrite_wikilink_target` sobre el contenido → `self._writer.update(linker_id, nuevo)`
   (`tags=None` preserva frontmatter y tags) → `self._ingest.execute_single(linker_id)`.
   Éxito → `relinked`; fallo → `logger.error(..., exc_info=True)` + `failed_relinks`.
6. `return MoveResult(...)`.

### 4.4 Tools — `src/agent/tools.py`

Convención del repo: `langchain.tools.Tool` con **input string** y JSON parseado a mano con
`_safe_json_loads` (`tools.py:35`). **No** `StructuredTool`/`args_schema` — rompería el
prompt ReAct.

**`create_list_folders_tool(move_use_case: MoveNote) -> Tool`** — síncrona (`func=_list`),
ignora el input, devuelve las carpetas una por línea o un mensaje si el vault es plano.

**`create_move_tool(move_use_case: MoveNote, confirm_action: ConfirmCallback) -> Tool`** —
**async** (`func=None, coroutine=_move`), igual que `create_note`/`edit_note`
(`tools.py:181`):

- Parsea `{"note_id", "target_folder", "reason"}`; `JSONDecodeError`/`KeyError` → string de
  ayuda de formato, nunca excepción.
- Valida `target_folder` contra `move_use_case.list_folders()`; si no existe, devuelve al
  agente las válidas para que reintente (nunca inventa carpetas).
- Calcula `inbound = move_use_case.find_inbound_links(note_id)` y construye el `summary`:
  nota, `origen → destino`, `reason` del agente y **cuántas notas se reenlazarán**. El
  usuario confirma también esa reescritura, no sólo el `rename`.
- `if not await confirm_action(summary): return "El usuario canceló el movimiento de la nota."`
- Ejecuta y devuelve un resumen con `new_id`, chunks indexados, notas reenlazadas y, si
  las hay, las fallidas.
- Captura `NoteNotFoundError` y `VaultWriteError` → string de error (no re-lanza).

### 4.5 Agente — `src/agent/agent.py`

`create_agent(...)` recibe `move_use_case: MoveNote | None = None` (**opcional con default
`None`** para no romper las llamadas existentes de `tests/unit/test_agent.py`). En la rama
no-readonly (`agent.py:184-188`), si `move_use_case is not None` añadir
`create_list_folders_tool(...)` y `create_move_tool(..., confirm_action)`. En readonly la
lista sigue siendo `[search_tool]`.

Nuevo bloque en `_REACT_PROMPT_TEMPLATE`, **MOVER NOTAS**:
- Llamar `list_folders` **antes** de `move_note`; nunca inventar una carpeta.
- Sugerir mover sólo notas que estén en `00-inbox/`.
- `move_note` ya muestra diálogo de confirmación — no pedir permiso en texto (coherente con
  el bloque «CONFIRMACIÓN AL EJECUTAR», `agent.py:68-80`).
- Si la Observation dice que el usuario canceló, no reintentar.

**Fix incluido**: el ejemplo de wikilink de `agent.py:92` usa `[[01-inbox/...]]` cuando la
carpeta real es `00-inbox` (`obsidian_loader.py:117`) — genera enlaces rotos.

### 4.6 UI — `src/app/__init__.py`

En `_init_agent_session` (`app/__init__.py:298-321`), tras construir `ingest_uc`:

```python
move_uc = MoveNote(loader=loader, writer=writer, store=store, ingest=ingest_uc)
```
y pasar `move_use_case=None if readonly else move_uc` a `create_agent`. Guarda de readonly
por señal nula, igual que `prune_orphans` y `manage_notes` (`app/__init__.py:326-331`).

No hace falta tocar `on_message`: la confirmación viaja por `_confirm_write_action`, ya
inyectado. **Cero UI nueva.**

---

## 5. Tests

`tests/unit/test_move_note.py` (nuevo) — `MagicMock(spec=...)` de cada puerto, AAA explícito:
- `test_move_note_use_case_moves_file_and_reindexes_under_new_path`
- `test_move_note_use_case_removes_old_chunks_across_all_strategies` — asserta
  `store.delete_by_note.assert_called_once_with(old_id)`
- `test_move_note_use_case_rewrites_inbound_wikilinks`
- `test_move_note_use_case_reports_failed_relinks_without_aborting`
- `test_move_note_use_case_lists_existing_folders_from_vault`
- `test_move_note_use_case_raises_when_note_not_found`

`tests/unit/test_obsidian_loader.py` (ampliar, con la fixture `tmp_vault` de
`tests/conftest.py:83`) — hoy el vault de test es **plano**, por eso nunca se detectó el
problema path-vs-stem; estos tests introducen subcarpetas:
- `test_obsidian_loader_move_relocates_note_and_updates_id`
- `test_obsidian_loader_move_rejects_target_outside_vault` (`../../`)
- `test_obsidian_loader_move_rejects_missing_target_folder`
- `test_obsidian_loader_move_rejects_existing_destination_file`

`tests/unit/test_tools.py` (ampliar `TestMoveNoteTool`, con `_approve`/`_reject` de
`test_tools.py:29-34`):
- `test_move_tool_does_not_move_when_user_rejects` — asserta
  `move_use_case.execute.assert_not_called()`. Sustituye al
  `test_suggest_move_tool_returns_proposal_without_moving_note` de la spec: la tool ya no
  es «suggest», la garantía es el `ConfirmCallback`.
- `test_move_tool_moves_when_user_approves`
- `test_move_tool_rejects_unknown_target_folder`
- `test_list_folders_tool_returns_existing_folders`

`tests/unit/test_agent.py` (ampliar):
- `test_create_agent_readonly_excludes_move_tools` — cubre
  `test_move_note_blocked_when_readonly_mode_enabled` de la spec, en el punto donde vive
  realmente la guarda (`agent.py:174-186`).
- `test_create_agent_registers_move_tools_when_move_use_case_provided`
- `test_react_prompt_contains_move_notes_rules` — patrón ya usado en `test_agent.py:112-119`

`tests/unit/test_obsidian_conventions.py` — `rewrite_wikilink_target` preserva el alias y no
toca targets parcialmente coincidentes.

**Verificación manual** (el flujo `AskActionMessage` no es testeable con pytest, igual que
la UI de citas — error-log #17, `:952`): documentar explícitamente aquí, no omitir.

---

## 6. Orden de ejecución con gates

0. `git checkout -b feature/move-note-suggestion` (desde `feature/manage-md-files`) — HECHO.
   Crear `implementation-plan.md` en la raíz — este fichero.
1. Dominio (`models.py`, `ports.py`, `obsidian_conventions.py`) → **gate**:
   `pytest tests/unit/ && python scripts/check_architecture.py`
2. Adaptador `ObsidianLoader.move` + sus tests → **gate**: `pytest tests/unit/test_obsidian_loader.py -v`
3. Caso de uso `MoveNote` + `test_move_note.py` → **gate**: `pytest tests/unit/test_move_note.py -v`
4. Tools + tests → **gate**: `pytest tests/unit/test_tools.py -v`
5. Agente (registro + prompt + fix `00-inbox`) + tests → **gate**: `pytest tests/unit/test_agent.py -v`
6. Wiring en `src/app/__init__.py` → **gate**: `pytest tests/unit/ && mypy src`
7. Docs: `CLAUDE.md`, `docs/error-log.md`, `tasks/feature-move-note-suggestion.md`
8. **Gate final**: `scripts/format.sh && ruff check src/ tests/ && mypy src && pytest tests/unit/`
   (error-log #9, `:453`: `check` **y** `format`, nunca uno solo)
9. Verificación manual con `chainlit run app.py`.

---

## 7. Criterio de completado

1. El agente nunca mueve una nota sin que el usuario pulse «Confirmar»; la garantía es el
   `await confirm_action(...)` dentro de la tool, no una instrucción del prompt.
2. Tras un movimiento no quedan chunks bajo el `note_id` antiguo en ninguna de las tres
   colecciones de ChromaDB, y la nota está indexada bajo el nuevo id en las tres.
3. Los `[[old_id]]` de otras notas apuntan al nuevo id, con alias preservado, y esas notas
   están reindexadas.
4. `READONLY_MODE=true` deja al agente sin `move_note` ni `list_folders`.
5. Lint, tipos y tests unitarios en verde; `CLAUDE.md` y `docs/error-log.md` sincronizados.

## 8. Fuera de alcance (explícito)

- **No** se arreglan los 16 wikilinks ya rotos del vault demo ni se cambia la resolución
  path→stem de `ObsidianLoader.exists()`. Es un problema preexistente e independiente que
  merece su propia tarea; se documentará en `docs/error-log.md`.
- **No** se crean carpetas nuevas: `move_note` sólo acepta destinos existentes.
- **No** se añade `delete` al puerto `NoteWriter`.

---

## 9. TODOs por funcionalidad

### 🔧 Setup
- [x] `git checkout -b feature/move-note-suggestion`
- [x] Crear `implementation-plan.md` en la raíz

### 🧩 Dominio
- [x] `MoveResult` en `src/domain/models.py`
- [x] `NoteWriter.move()` abstracto en `src/domain/ports.py`
- [x] `rewrite_wikilink_target()` en `src/domain/obsidian_conventions.py`

### 🔌 Adaptador
- [x] `ObsidianLoader.move()` con validación anti path-traversal y colisión de destino

### ⚙️ Aplicación
- [x] `src/application/move_note.py`: `MoveNote` con `list_folders`, `find_inbound_links`, `execute`
- [x] Reindexado: `delete_by_note(old_id)` + `execute_single(new_id)` + reindex de reenlazadas
- [x] Reenlazado best-effort con `failed_relinks`

### 🤖 Agente
- [x] `create_list_folders_tool` y `create_move_tool` en `src/agent/tools.py`
- [x] Registro condicional en `create_agent` respetando `readonly`
- [x] Bloque «MOVER NOTAS» en `_REACT_PROMPT_TEMPLATE`
- [x] Fix del ejemplo `01-inbox` → `00-inbox` en `agent.py:92`

### 🖥️ UI
- [x] Construir `MoveNote` en `_init_agent_session` y pasarlo con guarda de readonly

### 🧪 Tests
- [x] `tests/unit/test_move_note.py` (6 tests)
- [x] `move` en `tests/unit/test_obsidian_loader.py` (4 tests, con subcarpetas)
- [x] `TestMoveNoteTool` en `tests/unit/test_tools.py` (4 tests)
- [x] Readonly + prompt en `tests/unit/test_agent.py` (3 tests)
- [x] `rewrite_wikilink_target` en `tests/unit/test_obsidian_conventions.py` (5 tests)

### 📚 Documentación
- [x] `CLAUDE.md`: `NoteWriter.move`, `MoveResult`, `MoveNote`, tools nuevas, nº de tests
- [x] `docs/error-log.md`: entrada `[2026-08-04]` — la spec asumió resolución de wikilinks
      por stem cuando el código resuelve por path; premisa del vault («4 MOCs») no verificada
- [x] `tasks/feature-move-note-suggestion.md`: registrado el diagnóstico y las 3 desviaciones

### ✅ Verificación final
- [x] `scripts/format.sh` (ruff format + check), `mypy src`, `pytest tests/unit/` en verde
      (211 tests)
- [x] Manual: `chainlit run app.py` (puerto 8126, LLM Groq real) → pedida sugerencia de
      mover `00-inbox/patron-circuit-breaker` → el agente llamó `list_folders` y propuso
      `02-areas/arquitectura` (carpeta real, no inventada) → **Confirmar** → fichero movido
      en disco (verificado con `ls`, contenido/frontmatter intactos), `search_vault` lo
      encontró bajo `02-areas/arquitectura/patron-circuit-breaker` y ya no bajo el id
      antiguo. Esta nota no tenía enlaces entrantes reales en el vault (`grep` confirmó 0
      referencias), así que el reenlazado no se ejercitó en este pase manual — cubierto por
      `test_move_note_use_case_rewrites_inbound_wikilinks` y
      `test_move_note_use_case_reports_failed_relinks_without_aborting`.
- [x] Manual: repetido con `00-inbox/teresa-de-calcuta` → 03-recursos, pulsando
      **Cancelar** → `ls` confirmó que el fichero no se movió; el agente reconoció la
      cancelación sin reintentar.
- [x] Manual: vault del usuario restaurado a su estado original (nota devuelta a
      `00-inbox/` vía el propio flujo de la app, contenido verificado byte a byte) para no
      dejar datos de prueba en su segundo cerebro real.
- [x] `READONLY_MODE=true`: verificado con
      `test_create_agent_readonly_excludes_move_tools` (asserta que `move_note`/
      `list_folders` no aparecen en `executor.tools` cuando `readonly=True`, aunque se pase
      `move_use_case`). No repetido como arranque manual aparte — el dev server de este
      entorno no sobrevive a cortes de sesión del harness (tres intentos, ver nota abajo),
      y el test cubre exactamente la rama de código que decide el registro de tools.

### 🩹 Fuera de esta rama (seguimiento acordado con el usuario)
- [x] `docs/error-log.md`: entrada `[2026-08-04]` sobre la pérdida de contenido en
      `edit_note` al vincular notas (bug distinto, detectado durante esta rama)
- [x] `spawn_task` con el fix (chip `task_0e0f1ca3`, pendiente de que el usuario lo
      inicie): tool `get_note` de solo lectura + refuerzo de `edit_note`/prompt +
      confirmación con diff/aviso de contenido drásticamente más corto
