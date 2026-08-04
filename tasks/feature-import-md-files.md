# Feature: Importar archivos .md al vault persistente

## Objetivo

Permitir que el usuario adjunte uno o varios ficheros `.md` en el chat (Chainlit)
y que se añadan como notas reales al vault persistente, indexadas en ChromaDB —
no a una colección efímera de sesión.

## Contexto (verificar cada dato antes de asumirlo, no copiar tal cual)

- `.chainlit/config.toml` tenía `[features.spontaneous_file_upload]` activo en
  algún momento y se desactivó (`enabled = false`) porque `on_message` nunca leía
  `message.elements` — no se procesaba nada de lo subido. Confirmar que sigue
  desactivado antes de tocar nada.
- `READONLY_MODE=true` deshabilita creación/edición de notas en el demo
  desplegado. `create_note`/`edit_note` ya siguen ese patrón — el import debe
  seguir exactamente la misma guarda, no inventar una nueva.
- Existe `tasks/obsidian-note-creation-conventions.md` con las convenciones de
  creación de notas (tags controlados `tipo/concepto`, `tipo/moc`,
  `dominio/<área>`, sin espacios, no puramente numéricos, `tags:` siempre como
  lista YAML). Si ya está ejecutado, el import debe validar contra ese mismo
  validador. Si no, aplicar como mínimo esas reglas de tags.
- Existe `tasks/feature-hot-vault-upload.md` (subida efímera de vault completo
  por sesión, colecciones ChromaDB por sesión, para testers). **Esta feature es
  distinta**: añade notas al vault persistente real. No reutilizar el mecanismo
  de sesión efímera; sí reutilizar parsing/validación de `.md` si hay código
  compartible.
- `note_id` es el path relativo dentro del vault. Un fichero importado con un
  nombre que ya existe es un conflicto — nunca sobrescribir en silencio.

## Fase de diagnóstico (obligatoria antes de escribir código)

Leer y citar `file:line` de cada uno de estos puntos antes de proponer el plan
definitivo:

1. `.chainlit/config.toml` completo — estado actual de `spontaneous_file_upload`
   y qué opciones admite esa sección (p. ej. `accept`, límite de tamaño) en la
   versión de Chainlit instalada (`.venv/bin/python -c "import chainlit; print(chainlit.__version__)"`).
2. `on_message` en `src/app/__init__.py` — grep de `message.elements` / `cl.File`
   para confirmar que hoy no se procesa nada.
3. Interfaz completa de `ManageNotes` en `src/application/` — firma exacta de
   `create_note`, validaciones, efectos secundarios (¿indexa ya en las 3
   estrategias o solo en la activa?).
4. Adapter(s) de indexación en `src/adapters/` que insertan en ChromaDB —
   confirmar si hay ya un método reutilizable para indexar contenido nuevo sin
   pasar por el flujo completo de `create_note`.
5. Entidad `Note` y validaciones existentes en `src/domain/` (posiblemente
   `src/domain/models.py`).
6. Guarda de `READONLY_MODE` alrededor de `create_note`/`edit_note` en
   `src/app/__init__.py` — replicar el mismo patrón exacto para el import.
7. Si `tasks/obsidian-note-creation-conventions.md` ya se ejecutó, localizar el
   validador de convenciones resultante y reutilizarlo.

## Spec funcional

- El usuario adjunta uno o varios `.md` a un mensaje, sin comando especial.
- Por cada fichero:
  - Validar extensión `.md` y un tamaño máximo razonable (confirmar en
    diagnóstico si ya existe un límite establecido en otra parte del proyecto;
    si no, definir uno explícito, p. ej. 1 MB).
  - Validar frontmatter/tags según las convenciones existentes.
  - Destino por defecto: `inbox/`, igual que las notas creadas por el agente
    hoy. La reubicación es responsabilidad de la feature de mover notas — no
    mezclar alcance aquí.
  - Si ya existe una nota con ese `note_id`: no sobrescribir. Informar el
    conflicto en el chat y pedir renombrar o confirmar sobrescritura explícita.
  - Escribir el fichero en el vault real e indexarlo reutilizando el mismo
    pipeline que usa `create_note`, en todas las estrategias de chunking
    activas (no solo la seleccionada en la sesión de chat).
  - Confirmar en el chat con el `note_id` asignado y, si es sencillo de
    obtener, el número de chunks generados por estrategia.
- Respetar `READONLY_MODE=true`: si está activo, no procesar el adjunto y
  explicarlo igual que ya se hace para `create_note`/`edit_note`.
- Reactivar `spontaneous_file_upload`, restringido a `.md` si la versión de
  Chainlit lo permite.

## Plan de implementación (ajustar tras diagnóstico)

- `src/app/__init__.py`: en `on_message`, si `message.elements` contiene
  ficheros `.md`, desviar a un handler nuevo `_handle_md_import(elements)`
  antes de pasar el turno al agente (decidir en diagnóstico si conviven
  adjunto + texto libre en el mismo turno, y qué pasa si ambos aparecen).
- `src/application/`: extender `ManageNotes` (o nuevo caso de uso) con una
  operación de importación que reciba path + contenido crudo y reutilice la
  misma ruta de indexación que `create_note`, sin pasar por el LLM — es una
  acción determinista de UI, no una decisión del agente.
- Tests del nuevo caso de uso mockeando repositorio/indexador, sin depender de
  Chainlit real, igual que el resto de `src/application`.

## Tests (patrón AAA + `spec=` ya usado en el proyecto)

- `test_import_md_creates_note_with_expected_note_id`
- `test_import_md_rejects_non_md_extension`
- `test_import_md_rejects_when_note_id_already_exists`
- `test_import_md_indexes_into_all_chunking_strategies`
- `test_import_md_blocked_when_readonly_mode_enabled`

## Checklist de completitud

- [x] Diagnóstico completado con citas `file:line`
- [x] `spontaneous_file_upload` reactivado y limitado a `.md`
- [x] Caso de uso de importación con tests unitarios en verde
- [x] Guardas de `READONLY_MODE` verificadas
- [x] `ruff check`/`format`, `mypy src`, `pytest tests/unit/` en verde
- [x] Verificación manual con `chainlit run app.py`: subir un `.md`, confirmar
      nota creada y buscable con `search_vault` (ver nota sobre el método de
      verificación en `docs/error-log.md`)
- [x] `docs/error-log.md` actualizado si aparece algún fallo no previsto
