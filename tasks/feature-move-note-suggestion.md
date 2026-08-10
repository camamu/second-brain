# Feature: Sugerencia de mover notas (con confirmación del usuario)

## Objetivo

Que el agente pueda proponer mover una nota de `inbox/` a una carpeta más
adecuada, y que el movimiento (con reindexación) solo se ejecute si el usuario
lo confirma explícitamente. El agente nunca mueve nada por su cuenta.

## Contexto (verificar cada dato antes de asumirlo, no copiar tal cual)

- Hoy no existe `move_note`. `note_id` es el path relativo — mover una nota
  implica cambiar su identificador y reindexar sus chunks en las estrategias
  de chunking activas, no solo renombrar el fichero en disco.
- Ya existe en el proyecto un patrón de confirmación previo a una acción
  irreversible: `_confirm_and_prune` (usado en el comando `/prune`). Reutilizar
  ese mismo mecanismo de confirmación en vez de crear uno nuevo, por
  consistencia de UX y para no duplicar lógica.
- Decisión de producto ya tomada con el usuario: **el agente sugiere, el
  usuario confirma antes de mover.** No implementar un modo autónomo.
- Las notas creadas por el agente vía chat caen hoy todas en `inbox/`; el
  vault demo tiene una estructura de carpetas por dominio (4 MOCs + notas
  atómicas). La sugerencia de destino debe basarse en esa estructura
  existente, no inventar carpetas nuevas sin justificación.

## Fase de diagnóstico (obligatoria antes de escribir código)

Leer y citar `file:line` de cada uno de estos puntos antes de proponer el plan
definitivo:

1. `_confirm_and_prune` completo en `src/app/__init__.py`: firma, qué
   componente de Chainlit dispara la confirmación (`cl.AskActionMessage`,
   `cl.Action`, comando de texto libre...). Replicar exactamente ese mecanismo,
   no otro.
2. `src/agent/tools.py` y `src/agent/agent.py` completos: convención de
   definición/registro de tools (`create_note`, `edit_note`, `search_vault`)
   para seguir el mismo patrón de firma.
3. Interfaz de `ManageNotes` en `src/application/`: ¿ya expone algo
   reutilizable para reindexar por `note_id`, o hay que añadirlo?
4. Adapter de ChromaDB en `src/adapters/`: cómo se borran/reinsertan chunks
   por `note_id` hoy (¿`edit_note` ya hace un delete-and-reinsert reutilizable
   para el path antiguo tras un movimiento?).
5. Estructura real de carpetas del vault demo (vault versionado o
   `vault-demo-tfm.zip`) para confirmar los nombres de carpeta/dominio que el
   agente podría sugerir como destino.
6. Confirmar si los `[[wikilinks]]` de Obsidian resuelven por nombre de
   fichero o por path completo. Si resuelven por nombre, mover de carpeta no
   rompe backlinks. Si el `BacklinkAwareChunker` usa el path completo como
   clave del grafo, documentar si hace falta actualizar algo interno tras el
   movimiento, antes de implementar.

## Spec funcional

- Nueva tool del agente (nombre provisional `suggest_move_note(note_id,
  target_folder, reason)`) que el LLM invoca cuando detecta que una nota en
  `inbox/` encajaría mejor en otra carpeta existente (p. ej. tras crearla, o
  si el usuario pregunta explícitamente).
- La tool **no mueve nada**: solo devuelve una propuesta (carpeta sugerida +
  motivo) que el agente incluye en su respuesta.
- Tras la respuesta del agente, disparar una confirmación reutilizando el
  mecanismo de `_confirm_and_prune` (botón/acción Confirmar / Cancelar).
- Si el usuario confirma: ejecutar el movimiento real — mover el fichero en el
  vault, borrar los chunks bajo el `note_id` antiguo y reindexar bajo el nuevo
  path, en todas las estrategias de chunking activas.
- Si el usuario cancela o no responde: no se ejecuta ningún cambio.
- Respetar `READONLY_MODE=true` igual que el resto de operaciones de
  escritura.

## Plan de implementación (ajustar tras diagnóstico)

- `src/agent/tools.py`: nueva factory `create_suggest_move_tool(...)`, misma
  convención que las tools existentes.
- `src/agent/agent.py`: registrar la tool nueva en `create_agent`.
- `src/application/`: nuevo método `move_note(note_id, target_path)` en
  `ManageNotes` (o caso de uso dedicado) que hace el movimiento físico +
  reindexación, reutilizando el borrado/reinserción ya existente en
  `edit_note` si es posible en vez de duplicar lógica.
- `src/app/__init__.py`: capturar la propuesta de movimiento — revisar si
  aplica el mismo patrón de lista mutable por closure ya usado para
  `last_search_results` — y disparar la confirmación reutilizando
  `_confirm_and_prune`.

## Tests

- `test_suggest_move_tool_returns_proposal_without_moving_note`
- `test_move_note_use_case_moves_file_and_reindexes_under_new_path`
- `test_move_note_use_case_removes_old_chunks_across_all_strategies`
- `test_move_note_blocked_when_readonly_mode_enabled`
- Flujo de confirmación en sí: si no es testeable con pytest (igual que la UI
  de citas nativas no lo es), documentarlo como verificación manual explícita
  en vez de omitirlo.

## Diagnóstico y desviaciones respecto a esta spec

El diagnóstico obligatorio (ver `implementation-plan.md` en la raíz del repo,
sección "Contexto") encontró que tres afirmaciones de este fichero no se
sostenían contra el código/vault reales, y cambió el plan en consecuencia:

1. **Wikilinks por nombre (línea 45-49, falso)**: `ObsidianLoader.exists()`
   trata `[[...]]` como path relativo al vault, no como stem — verificado en
   `obsidian_loader.py:71,85`. Mover SÍ rompe backlinks. 16/21 wikilinks del
   vault real ya estaban rotos por esta razón antes de tocar nada. Decisión:
   `MoveNote.execute()` reescribe los `[[old_id]]` entrantes en modo
   best-effort (ver `docs/error-log.md`, entrada `[2026-08-04]` sobre esta
   spec).
2. **«4 MOCs + notas atómicas» (línea 21-22, falso)**: el vault real
   (`VAULT_PATH`) tiene estructura PARA, sin MOCs. Decisión: tool
   `list_folders` descubre las carpetas reales en runtime; el agente nunca
   inventa un destino.
3. **Patrón de confirmación (línea 14-17, 53-60)**: no se reutilizó
   `_confirm_and_prune` ni se implementó `suggest_move_note` como tool
   separada de solo-propuesta. Se reutilizó `_confirm_write_action`
   (`src/app/__init__.py:96`) — el mismo mecanismo `cl.AskActionMessage` que
   ya usan `create_note`/`edit_note` — inyectado como `ConfirmCallback` en
   una única tool `move_note` que `await`ea la confirmación antes de mover.
   Sigue cumpliendo "el agente sugiere, el usuario confirma": sin pulsar el
   botón no se mueve nada, sin estado por closure entre turnos, sin UI nueva.

## Checklist de completitud

- [x] Diagnóstico completado con citas `file:line`, incluida la verificación
      de wikilinks por nombre vs. path
- [x] Tool `move_note` (con `ConfirmCallback`, no `suggest_move_note` — ver
      desviación 3 arriba) registrada y testeada
- [x] Caso de uso `MoveNote` con reindexación completa, tests en verde
- [x] Confirmación reutiliza el patrón `_confirm_write_action`/
      `_confirm_and_prune` existente (mismo mecanismo `cl.AskActionMessage`,
      sin UI nueva — ver desviación 3 arriba)
- [x] Guardas de `READONLY_MODE` verificadas
- [x] `ruff check`/`format`, `mypy src`, `pytest tests/unit/` en verde
- [x] Verificación manual con `chainlit run app.py` (LLM Groq real): pedida
      sugerencia sobre `00-inbox/patron-circuit-breaker`, el agente llamó
      `list_folders` y propuso `02-areas/arquitectura` (carpeta real);
      confirmado el movimiento, `search_vault` la encontró bajo el nuevo
      `note_id` y no bajo el antiguo. Repetido con `00-inbox/teresa-de-calcuta`
      pulsando **Cancelar**: el fichero no se movió. Vault del usuario
      restaurado a su estado original al terminar (ver
      `implementation-plan.md`, sección "Verificación final")
- [x] `docs/error-log.md` actualizado (entrada `[2026-08-04]` sobre las
      premisas no verificadas de esta spec)
