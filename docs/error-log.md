# Error Log — Obsidian RAG Agent

Registro de errores de diseño/implementación detectados durante el
desarrollo asistido por IA, y cómo se corrigieron. Material de apoyo
para la sección de metodología del TFM.

---

## [2026-06-13] Deriva de nombres entre Fase 1 (dominio) y la spec de Fase 2

**Fase**: fase-2-ingesta.md
**Categoría**: arquitectura

### Qué se hizo mal

El dominio implementado en Fase 1 y mergeado en PR #1 y #2 usaba convenciones
de nombres distintas a las que la spec de Fase 2 (`tasks/fase-2-ingesta.md`)
consideraba canónicas:

| Entidad | Fase 1 (implementado) | Fase 2 (spec) |
|---|---|---|
| `Note.note_id` | `note_id: str` | `id: str` |
| `Note` | sin `path`, sin `note_type` | `path: str`, `note_type: NoteType` |
| `Chunk.chunk_id` | `chunk_id: str` | `id: str` |
| `Chunk.position` | `position: int` | `index: int` |
| `Chunk.strategy` | `strategy: str` | `strategy: ChunkStrategy` (enum) |
| `ChunkStrategy.FIXED` | `FIXED` | `FIXED_SIZE` |
| Puerto de lectura | `IVaultReader` | `NoteLoader` |
| Puerto de escritura | `IVaultWriter` | `NoteWriter` |
| Puerto de chunking | `IBaseChunker` | `BaseChunker` |

Además, `IVaultReader.load()` debía llamarse `load_by_id()` y faltaba el método
`exists()`. `IVaultWriter` tenía una firma distinta y un método `delete()` que
la spec no pedía.

### Por qué era un error

La divergencia entre spec y dominio impedía implementar Fase 2 directamente:
los adaptadores (`ObsidianLoader`, chunkers) habrían usado los nombres de la
spec mientras el dominio y los tests de Fase 1 seguían con los nombres viejos,
rompiendo la cohesión de la capa interna del hexágono y produciendo tests
inconsistentes.

### Cómo se corrigió

Se tomó la spec como fuente de verdad y se ejecutó un refactor completo del
dominio antes de empezar a implementar los adaptadores:

1. `Note`: `note_id` → `id`; campos `path: str = ""` y
   `note_type: NoteType = NoteType.OTHER` añadidos.
2. `Chunk`: `chunk_id` → `id`, `position` → `index`,
   `strategy: str` → `strategy: ChunkStrategy`, `heading: Optional[str]` añadido.
3. `ChunkStrategy`: `FIXED`→`FIXED_SIZE`, `MARKDOWN`→`MARKDOWN_HEADER`,
   `BACKLINK`→`BACKLINK_AWARE` (conservando los `.value` para no romper el `.env`).
4. `ports.py`: puertos renombrados; `load_by_id()` y `exists()` añadidos;
   `NoteWriter` con `create()`/`update()` retornando `Note`.
5. `src/domain/__init__.py` actualizado con los nuevos nombres.
6. `tests/conftest.py` y `tests/unit/test_models.py` reescritos a los nombres
   nuevos; `tmp_vault` ampliado con `type:`, alias de backlinks y nota vacía.

**Alternativa descartada**: mantener los nombres de Fase 1 en el dominio y
añadir mapeo en los adaptadores. Se descartó porque duplicaría conceptos en la
capa interna y haría los tests de integración más frágiles.

### Cómo evitarlo en el futuro

Antes de cerrar una fase, revisar la spec de la fase siguiente y verificar que
los nombres de entidades, ports y campos del dominio son consistentes. Si hay
divergencia, resolverla en el mismo PR de la fase anterior.

---

## [2026-06-13] Errores de lint (I001, F401) al resolver conflictos de merge

**Fase**: fase-2-ingesta.md
**Categoría**: otro

### Qué se hizo mal

Al resolver los conflictos del merge de `develop` en `feature/domain-refactor`,
el bloque de imports de `src/domain/models.py` quedó desordenado (regla `I001`
de ruff) y `ChunkStrategy` se importó en `ports.py` sin usarse (`F401`).

### Por qué era un error

El action de lint de CI falló al hacer push, bloqueando el pipeline y
requiriendo un commit adicional de corrección.

### Cómo se corrigió

```bash
ruff check src/ --fix   # corrige I001 y F401 automáticamente
ruff format src/
```

### Cómo evitarlo en el futuro

Tras cualquier resolución de conflictos, ejecutar `ruff check src/ --fix &&
ruff format src/` localmente antes de hacer push. Añadirlo como paso del
checklist de merge.

---

## [2026-06-15] Deriva de nombres entre Fase 2 (dominio) y la spec de Fase 3

**Fase**: fase-3-vectorstore-llm.md
**Categoría**: arquitectura (recurrencia del error de Fase 1→2)

### Qué se hizo mal

La spec `tasks/fase-3-vectorstore-llm.md` usaba nombres y firmas distintos a
los puertos ya implementados y mergeados en Fase 2:

| Spec Fase 3 | Dominio real (Fase 2) |
|---|---|
| `ChunkEmbedder` | `IEmbedder` |
| `VectorStore` | `IVectorStore` |
| `ConversationalLLM` | `ILLMChat` |
| `add_chunks(chunks, embedder)` | `add_chunks(chunks)` |
| `delete_by_note(id)` | `delete_by_note_id(id)` |
| `count()` | `get_note_ids()` |
| `generate(prompt, ctx)` | `respond(prompt, ctx)` |

Además, la spec pedía pasar el embedder como argumento de `add_chunks`/`search`,
lo que habría ensuciado el contrato del puerto `VectorStore`.

### Por qué era un error

Implementar directamente sobre la spec habría roto el dominio mergeado, los 44
tests existentes, y habría acoplado el puerto `VectorStore` a ChromaDB (al
exponer el embedder en la firma de métodos del puerto).

### Cómo se corrigió

Se detectó la divergencia antes de escribir código (lección del error-log de
Fase 2). Decisiones tomadas:

1. **La spec es la fuente de verdad** para nombres de puertos. Se refactorizó
   el dominio: `IEmbedder→ChunkEmbedder`, `IVectorStore→VectorStore`,
   `ILLMChat→ConversationalLLM`, `delete_by_note_id→delete_by_note`,
   `get_note_ids→count`, `respond→generate`.
2. **El embedder se inyecta en el constructor** de `ChromaVectorStore`, no por
   argumento de método. Mantiene los métodos del puerto limpios.
3. Se verificó que los tres puertos a renombrar no tenían usos fuera de
   `ports.py` y `__init__.py` antes de hacer el refactor.
4. Gate tras el refactor: `pytest tests/unit -q` → 44/44 verde.

**Alternativa descartada**: mantener los nombres de Fase 2 y adaptar la spec.
Se descartó para mantener la spec como referencia canónica del TFM.

### Cómo evitarlo en el futuro

Al cerrar cada fase, verificar que los nombres de puertos de la spec de la fase
siguiente coinciden con el dominio actual. Si divergen, refactorizar el dominio
en el mismo PR de cierre de fase (no dejarlo para la siguiente).

---

## [2026-06-18] Modelos incompatibles con el agente ReAct en operaciones de escritura

**Fase**: fase-6-chainlit.md
**Categoría**: compatibilidad de modelo

### Qué ocurre

Al usar `llama3.2` (3B parámetros) para operaciones de escritura (`edit_note`,
`create_note`), el agente falla con:

```
Parsing LLM output produced both a final answer and a parse-able action
[...]
Invalid or incomplete response
```

El LLM genera en el mismo turno un bloque `Action / Action Input` y un `Final Answer`,
mezclando ambos cuando el razonamiento se vuelve multi-paso. El parser ReAct de
LangChain no puede interpretar esa salida y devuelve el fallback
`Invalid or incomplete response` como respuesta al usuario.

El `handle_parsing_errors=True` del `AgentExecutor` atrapa el error pero no lo
corrige: el modelo sigue cometiendo el mismo fallo en iteraciones sucesivas hasta
alcanzar `max_iterations=5`.

### Por qué ocurre

ReAct exige que el LLM genere **exactamente uno** de los dos patrones por turno:
- `Action: X\nAction Input: Y` (usar herramienta), o bien
- `Final Answer: Z` (responder al usuario)

Los modelos de ≤3B parámetros tienden a "atajan" el razonamiento incluyendo
ambos en el mismo bloque, especialmente cuando el input de la herramienta
necesita un JSON con múltiples campos (como `note_id` + `content`).

Las búsquedas simples (`search_vault`) sí funcionan con modelos pequeños porque
el input de la herramienta es un string corto y el agente suele necesitar solo
un ciclo de razonamiento.

### Modelos probados

| Modelo | Backend | Búsqueda | Creación/edición | Notas |
|---|---|---|---|---|
| `llama3.2` (3B) | Ollama local | ✅ | ❌ | Falla al generar JSON multi-campo |
| `llama3.2:1b` | Ollama local | ⚠️ | ❌ | Peor aún; a veces falla también búsqueda |
| `gemma4:e2b-mlx` (2B) | Ollama local | ❌ | ❌ | 2B params; mismo fallo que llama3.2, probado |
| `mistral` (7B) | Ollama local | ✅ | ⚠️ | Entra en bucle de búsquedas en ediciones complejas |
| `gemma3:12b` (12B) | Ollama local | ✅ | ✅ | Recomendado; probado búsqueda + edición sin bucles |
| `qwen3.6:35b-a3b-coding-nvfp4` | Ollama local | ✅ | ✅ | Modelos coding son más robustos con JSON |
| `llama-3.2-90b-text-preview` | Groq API | ✅ | ✅ | 90B; sin problemas de formato |

### Recomendación para el TFM

- **Mínimo recomendado para Ollama**: `mistral` (7B) o cualquier modelo ≥7B
  que sea instruction-tuned. Configurar con `OLLAMA_LLM_MODEL=mistral` en `.env`.
- **Modelos pequeños (≤3B)**: válidos **solo para demo de búsqueda**. Documentar
  explícitamente esta limitación en la memoria del TFM si se usan en evaluación.
- **Groq**: cualquier modelo del tier gratuito de Groq (llama-3.1-8b-instant,
  llama-3.2-90b) funciona correctamente para las tres operaciones.
- La tabla de decisiones de `critical-task-planning.md` ya recoge el trade-off
  ReAct vs. tool-calling: tool-calling nativo (si el modelo lo soporta) sería
  más robusto, pero ReAct es más portable entre modelos.

### Cómo evitarlo en el futuro

- En los scripts de evaluación (Fase 8), usar un modelo ≥7B para las ejecuciones
  de referencia; anotar el modelo exacto junto a cada resultado de evaluación.
- Si se quiere conservar `llama3.2` para velocidad en demos, limitar el agente
  a operaciones de solo lectura (`search_vault`) en esa configuración.

---

## [2026-06-15] Deriva de firmas entre Fase 3 (puertos) y la spec de Fase 4

**Fase**: fase-4-casos-de-uso.md
**Categoría**: arquitectura (recurrencia: tercera vez consecutiva)

### Qué se hizo mal

La spec `tasks/fase-4-casos-de-uso.md` se escribió antes de que en Fase 3 se
decidiera inyectar el `ChunkEmbedder` en el constructor del `VectorStore`. Por
eso la spec pedía pasar el embedder como parámetro a los casos de uso y a los
métodos del puerto:

| Spec Fase 4 | Puerto real (Fase 3) |
|---|---|
| `IngestVault(loader, chunker, embedder, store)` | `IngestVault(loader, chunker, store)` |
| `store.add_chunks(chunks, embedder)` | `add_chunks(chunks)` — sin embedder |
| `store.search(query, embedder)` | `search(query)` — sin embedder |
| `SearchNotes(store, embedder)` | `SearchNotes(store)` |
| `execute_text(strategy: ChunkStrategy = FIXED_SIZE)` | `execute_text(strategy: ChunkStrategy \| None = None)` |

### Por qué era un error

Seguir la spec literal habría introducido parámetros muertos (`embedder`) en la
capa de aplicación y roto en runtime (el método `add_chunks` del puerto no
acepta 2º argumento). Habría acoplado la capa de aplicación a un detalle de
implementación que ya fue resuelto en el nivel del adaptador.

### Cómo se corrigió

Se detectó la divergencia en el análisis previo (antes de escribir código).
Decisión: el puerto refactorizado de Fase 3 es la fuente de verdad. Los casos
de uso no reciben ni manejan embedder; el `VectorStore` creado por la factory
ya lo encapsula. `execute_text` acepta `ChunkStrategy | None` y traduce a
`.value` al construir `RetrievalQuery` (cuyo campo es `Optional[str]`).

**Alternativa descartada**: incluir `embedder` como parámetro muerto para
respetar la firma de la spec. Se descartó porque crearía confusión en el lector
del TFM y viola el principio de no exponer detalles de implementación en los
puertos limpios.

### Cómo evitarlo en el futuro

Las specs de fases futuras deben revisarse contra el dominio **y** los puertos
implementados antes de empezar la fase. Cualquier decisión de diseño tomada
durante la implementación de una fase (como el patrón de inyección del embedder)
debe reflejarse en las specs de las fases siguientes antes de cerrar el PR.

---

## [2026-07-01] Corrección de bug sin tests de validación

**Fase**: fase-6-chainlit.md / fase-8-deploy.md
**Categoría**: testing

### Qué se hizo mal

Al corregir el crash del agente en producción (`ValueError: Got unsupported
early_stopping_method 'generate'` y el bucle `Action: None`), se modificó
`src/agent/agent.py` —dos cambios en `AgentExecutor`— sin escribir ningún test
que verificase el comportamiento corregido. Los tests se añadieron solo al ser
pedidos explícitamente por el usuario en el mensaje siguiente.

### Por qué era un error

Sin tests, el fix queda sin contrato: cualquier refactor futuro que revierta
`early_stopping_method` a `"generate"` o elimine `"Final Answer"` del mensaje
`handle_parsing_errors` pasaría desapercibido hasta el siguiente despliegue
fallido. Además, el bug ya existía en producción y se diagnosticó a partir de
logs, lo que hace que los tests de regresión tengan aún más valor: habrían
detectado el error antes de que llegara a HF Spaces.

### Cómo se corrigió

Se añadieron cinco tests en `tests/unit/test_agent.py` agrupados en dos clases:

- `TestCreateAgent` (configuración del executor):
  - `test_create_agent_uses_force_stopping_method` — verifica `early_stopping_method == "force"`
  - `test_create_agent_parsing_error_message_includes_final_answer` — verifica que el mensaje guía incluye `"Final Answer"`

- `TestAgentExecutorBehavior` (comportamiento con `FakeListLLM`):
  - `test_invoke_does_not_raise_when_llm_uses_action_none` — reproduce el bug exacto de producción
  - `test_invoke_does_not_raise_on_max_iterations_exceeded` — agente que agota `max_iterations=5` sin `ValueError`
  - `test_invoke_recovers_from_parsing_error_with_final_answer` — recuperación tras un error de formato

### Cómo evitarlo en el futuro

Antes de dar por terminado cualquier bug fix, escribir al menos un test de
regresión que falle con el código anterior y pase con el código corregido.
Si el bug se detectó en producción, el test debe reproducir el escenario
exacto de fallo (en este caso: `FakeListLLM` con `Action: None` en bucle).

---

## [2026-07-02] Hipótesis incorrecta sobre el texto que dispara el fallo de parseo ReAct

**Fase**: fase-6-chainlit.md
**Categoría**: testing

### Qué se hizo mal

Al diagnosticar en logs de producción el mensaje `handle_parsing_errors`
(`"Formato incorrecto. Cuando necesitas usar una herramienta..."`), se asumió
que el LLM había escrito un bloque `Action:` con texto libre **sin**
`Action Input:` junto a un `Final Answer:` en la misma respuesta. El primer
test de regresión escrito reprodujo exactamente esa forma:

```python
"Thought: ya tengo la información.\n"
"Action: No es necesario realizar ninguna acción adicional.\n\n"
"Thought: Tengo la respuesta final.\n"
"Final Answer: respuesta ignorada por formato mixto"
```

El test falló (la aserción, no una excepción): el `AgentExecutor` devolvió
directamente `"respuesta ignorada por formato mixto"` sin pasar por
`handle_parsing_errors`, es decir, el escenario "reproducido" ni siquiera
disparaba el bug.

### Por qué era un error

El log de Chainlit en modo `verbose=True` solo imprime el texto del LLM
cuando `ReActSingleInputOutputParser.parse()` tiene éxito (`on_agent_action`
/ `on_agent_finish`); cuando el parseo falla, el texto crudo que lo causó
nunca aparece en el log — solo se ve el mensaje de recuperación como
Observation. Se asumió una forma de fallo sin verificar la lógica real del
parser, lo que produjo un test verde que en realidad no ejercitaba el
código de recuperación: si el fix del prompt hubiera sido incorrecto, el
test no lo habría detectado.

Repasando la lógica de `ReActSingleInputOutputParser`: si el texto contiene
`Action:` pero **no** hace match con el regex `Action:.*Action Input:.*`, el
parser ignora esa línea y, si además hay `Final Answer:`, lo toma
directamente como `AgentFinish` — no lanza excepción. El error real
(`"Parsing LLM output produced both a final answer and a parse-able
action"`, ya documentado en la entrada `[2026-06-18]` de este mismo log)
solo ocurre cuando el texto tiene un bloque `Action:`/`Action Input:` que sí
matchea el regex **y además** un `Final Answer:`.

### Cómo se corrigió

Se reescribió el test con un bloque `Action`/`Action Input` completo y
parseable junto al `Final Answer`:

```python
"Thought: ya tengo la información pero seré explícito.\n"
"Action: search_vault\n"
"Action Input: no hace falta\n"
"Thought: Tengo la respuesta final.\n"
"Final Answer: respuesta ignorada por formato mixto"
```

Con este texto el test sí reproduce el `OutputParserException` real y
verifica la recuperación en el turno siguiente.

### Cómo evitarlo en el futuro

Cuando se diagnostica un bug a partir de logs sin la traza cruda exacta
(porque la librería no la loguea en el caso de fallo), verificar la
hipótesis contra el código fuente de la librería o contra una entrada
previa de `docs/error-log.md` antes de escribir el test de regresión —  y
confirmar en rojo-verde (el test falla con el código anterior, pasa con el
corregido) en vez de asumir que un test que pasa a la primera reproduce el
bug real.

---

## [2026-07-02] CLAUDE.md desactualizado respecto al código real

**Fase**: transversal (detectado durante fase-6-chainlit.md / hotfix del agente)
**Categoría**: documentación

### Qué se hizo mal

`CLAUDE.md` no se había actualizado desde (aproximadamente) el cierre de la
Fase 4. Seguía describiendo el estado del proyecto como si `src/agent/`,
`src/app/`, `app.py`, `src/adapters/evaluation_repo.py` y los workflows de
CI no existieran o estuvieran "sin implementar". Ejemplos concretos:

- Comando documentado: `chainlit run src/app/__init__.py` (marcado "not yet
  implemented"). Comando real: `chainlit run app.py`.
- Variables de entorno documentadas (`OLLAMA_LLM_MODEL`, ausencia de
  `READONLY_MODE`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `LOG_LEVEL`) no coincidían
  con `.env.example`, la fuente real.
- Sección "Current state" listaba 73 tests y omitía `src/agent/`,
  `tests/unit/test_agent.py`, `test_tools.py`, `test_metrics.py`,
  `scripts/check_architecture.py`, `scripts/format.sh` y los workflows de
  `.github/workflows/`.
- No mencionaba las lecciones ya registradas en este mismo `docs/error-log.md`
  (p. ej. la entrada `[2026-06-18]` sobre modelos ReAct incompatibles).

### Por qué era un error

`CLAUDE.md` es la primera fuente que se lee al empezar cualquier sesión en
este repo — es la razón de ser del fichero. Si describe un estado pasado del
proyecto, induce a error en cascada: se referencian comandos que ya no
existen, se ignoran adaptadores/tests reales, y las "Current lessons" no
reflejan los aprendizajes más recientes que sí están en `docs/error-log.md`.
El propio `CLAUDE.md` instruye "Read it at the start of each phase" sobre el
error-log, pero nadie aplicó la misma disciplina al propio `CLAUDE.md`: no
hay ningún paso del flujo de trabajo que lo mantenga sincronizado con el
código después de cada fase.

### Cómo se corrigió

Se revisó `CLAUDE.md` contra el estado real del repo (`find src -name
"*.py"`, `.env.example`, `tests/unit/`, `.github/workflows/`,
`docs/error-log.md`) y se corrigieron las secciones "Commands", "Architecture"
(añadidas `Agent` y `App`), "Environment variables", "Current state" y
"Error log" para que coincidan con el código real en lugar de con el estado
de hace varias fases.

### Cómo evitarlo en el futuro

Al cerrar cada fase (`tasks/fase-N-*.md`) o cualquier PR que añada un
adaptador, script, comando o variable de entorno nuevos, actualizar
`CLAUDE.md` en el mismo cambio — no como tarea aparte. Antes de dar por
cerrada una fase, comparar explícitamente `CLAUDE.md` contra
`find src -name "*.py" ! -name "__init__.py"`, `.env.example` y el número
de tests (`pytest tests/unit/ -q`) para detectar drift antes de mergear.

---

## [2026-07-02] "Lint limpio" verificado solo a medias (ruff check sin ruff format)

**Fase**: fase-6-chainlit.md (hotfix del agente)
**Categoría**: testing

### Qué se hizo mal

Tras aplicar los fixes del bucle de `search_vault`, se afirmó que "ruff y
mypy están limpios" habiendo ejecutado solo `ruff check src/ tests/`. Nunca
se corrió `ruff format --check`. El commit se subió a la rama remota con
`tests/unit/test_agent.py` sin formatear (una línea que ruff format habría
partido en varias). El usuario lo detectó por el CI (`Would reformat:
tests/unit/test_agent.py`), no el agente.

### Por qué era un error

`ruff check` (linter) y `ruff format` (formateador) son herramientas
distintas que comprueban cosas distintas: una detecta errores/convenciones
de código, la otra el formato exacto (line-wrapping, comillas, etc.). Pasar
una no garantiza pasar la otra. El propio `CLAUDE.md` ya documentaba en la
entrada "Lint after merges" que hay que correr ambas, pero esa lección
estaba redactada solo para el caso de resolución de conflictos de merge, no
como regla general antes de cualquier commit — por eso no se activó aquí.

### Cómo se corrigió

```bash
ruff format src/ tests/   # reformatea
ruff check src/ tests/    # lint
pytest tests/unit/ -q     # confirma que el reformateo no rompe nada
```

Se creó un commit de estilo (`ef10b74`) separado del fix funcional y se
volvió a subir.

### Cómo evitarlo en el futuro

Antes de dar por cerrado cualquier cambio de código (no solo tras merges),
correr siempre `ruff format <paths> && ruff check <paths>` — nunca uno sin
el otro — igual que ya hace `scripts/format.sh`. Preferir invocar ese script
directamente en vez de recordar los dos comandos por separado.

---

## [2026-07-09] `await` suprimido por analogía en vez de verificar el método concreto

**Fase**: refactor de `src/app/__init__.py` (chunking a Settings + comandos "/")
**Categoría**: diseño / verificación

### Qué se hizo mal

Al llamar a `cl.context.emitter.set_commands([...])`, `mypy` marcó
`Coroutine[...] must be used` (el stub de `BaseChainlitEmitter` declara el
método `async def`). En vez de comprobar la implementación concreta que se
ejecuta en runtime (`ChainlitEmitter.set_commands`), se resolvió por
analogía con otra llamada cercana en el mismo fichero de Chainlit
(`chat_settings.py` invoca `context.emitter.set_chat_settings(...)` sin
`await`) y se silenció el error con `# type: ignore[unused-coroutine]`. La
prueba manual (`chainlit run app.py`) reveló el fallo real: sin `await`,
Python emite `RuntimeWarning: coroutine 'AsyncServer.emit' was never
awaited` y el panel de comandos nunca llega al cliente — un fallo
completamente silencioso (ni excepción ni test unitario lo detecta).

### Por qué era un error

Dos métodos que se ven parecidos (`set_chat_settings` y `set_commands`) en
la misma clase pueden tener implementaciones completamente distintas:
`set_chat_settings` solo hace una asignación local síncrona
(`self.session.chat_settings = settings`), mientras que `set_commands`
delega en `self.emit(...)`, que en tiempo de ejecución es el `emit` async de
`python-socketio`. La analogía por "se ve igual" sin leer el cuerpo del
método concreto llevó a la conclusión contraria a la correcta. Además, este
tipo de bug (falta de `await` en una llamada fire-and-forget) no lo detecta
ni `pytest` ni `mypy` una vez suprimido con `type: ignore` — solo una
ejecución real del servidor con una advertencia de runtime.

### Cómo se corrigió

Se leyó el cuerpo real de `ChainlitEmitter.set_commands` (delega en
`self.emit`) frente a `set_chat_settings` (asignación directa), se confirmó
con `chainlit run app.py` que sin `await` aparecía el `RuntimeWarning`, y se
añadió el `await` (quitando el `type: ignore`).

### Cómo evitarlo en el futuro

Cuando `mypy` señale una discrepancia entre lo que "parece" el patrón
establecido en el código y lo que el stub declara, no resolver por analogía
con una llamada vecina sin leer el cuerpo del método concreto que se
ejecuta. Y, en general: un `# type: ignore` sobre un error de
`unused-coroutine`/`await` faltante es una señal de alarma — antes de
silenciarlo, verificar con una ejecución real (no solo tests), porque un
`await` faltante en una llamada fire-and-forget no lanza excepción, solo dejar
de funcionar en silencio.

---

## [2026-07-20] create_note/edit_note escribían en el vault sin confirmación del usuario

**Fase**: fase-6-chainlit.md
**Categoría**: diseño

### Qué se hizo mal

El agente ReAct podía crear y editar notas en el vault sin pedir ninguna
confirmación al usuario. La única "protección" existente era una
instrucción en el prompt del agente (`_REACT_PROMPT_TEMPLATE` en
`src/agent/agent.py`), que además iba en la dirección contraria: la regla
"FLUJO OBLIGATORIO PARA EDITAR" instruía explícitamente al LLM a llamar
`edit_note` **INMEDIATAMENTE** tras una búsqueda, sin ningún paso
intermedio de confirmación, y no había ninguna regla equivalente para
`create_note`. Las funciones de las tools (`src/agent/tools.py`) llamaban
directamente a `ManageNotes.create()`/`.update()` en cuanto recibían el
Action Input, sin ningún punto de pausa.

### Por qué era un error

Delegar una garantía de comportamiento (nunca escribir sin permiso
explícito) únicamente a una instrucción de prompt es frágil por
construcción: depende de que el LLM la respete en cada turno, y los LLMs
—especialmente los modelos pequeños usados en este proyecto (ver tabla de
compatibilidad más abajo en este archivo)— no lo garantizan de forma
consistente. El resultado observado fue exactamente ese: el agente creaba
notas nuevas sin que el usuario lo hubiera aprobado.

### Cómo se corrigió

Se movió la garantía de la capa de prompt (donde es solo una sugerencia) a
la capa de código (donde es obligatoria):

1. `create_note_tool`/`create_edit_tool` (`src/agent/tools.py`) pasan a
   requerir un parámetro `confirm_action: ConfirmCallback` (callback
   `async` inyectado, sin default inseguro) y se convierten en tools solo
   async (`func=None`, `coroutine=...`). Antes de escribir, construyen un
   resumen de la acción propuesta y hacen
   `approved = await confirm_action(summary)`; si no se aprueba, no se
   llama a `ManageNotes.create()`/`.update()`.
2. `create_agent()` (`src/agent/agent.py`) lanza `ValueError` en
   construcción si `readonly=False` y no se pasa `confirm_action` —
   imposible desplegar un agente con escritura habilitada y sin mecanismo
   de confirmación por un olvido.
3. `src/app/__init__.py` implementa `_confirm_write_action()` reutilizando
   el mismo patrón de `cl.AskActionMessage` (confirmar/cancelar,
   `timeout=60`) que ya existía para `/prune` (`_confirm_and_prune`), y lo
   inyecta en `create_agent(...)`.
4. Se mantiene `tools.py` libre de dependencias de Chainlit (regla de
   arquitectura hexagonal): el callback es un `Callable[[str],
   Awaitable[bool]]` genérico, no una llamada directa a `cl.AskActionMessage`.

### Cómo evitarlo en el futuro

Cuando una acción es irreversible o modifica estado del usuario (crear,
editar, borrar), no confiar en que el prompt del LLM baste para exigir
confirmación: la garantía debe imponerse en la capa de código que ejecuta
la acción (la tool o el caso de uso), de forma que sea estructuralmente
imposible de saltarse, y no solo una convención que el modelo puede
ignorar. El precedente correcto ya existía en este mismo proyecto
(`_confirm_and_prune` para `/prune`) y no se había generalizado a
`create_note`/`edit_note` cuando se implementaron.

---

## [2026-07-20] El agente ignoraba información nueva aportada tras un "no tengo información"

**Fase**: fase-6-chainlit.md
**Categoría**: diseño

### Qué se hizo mal

Log de producción (Groq): el usuario preguntó por "Manolo el del Bombo",
`search_vault` no encontró nada relevante y el agente respondió
correctamente "no tengo información sobre eso". El usuario respondió
aportando él mismo un dato ("es hincha de la selección española") — no
una instrucción para seguir buscando, sino información nueva que el
agente no tenía. En vez de reconocer la oportunidad de guardarla, el
agente volvió a llamar `search_vault` dos veces más con variaciones de la
consulta, sin encontrar nada, y repitió el mismo "no tengo información",
ignorando por completo el dato que el usuario acababa de darle.

### Por qué era un error

El prompt del agente (`_REACT_PROMPT_TEMPLATE`) solo cubría el flujo de
"el usuario pide crear/editar explícitamente" (ver entrada anterior), pero
no contemplaba el caso más común en una conversación real: el usuario
completa una laguna de conocimiento del vault de forma incidental, sin
pedir explícitamente que se guarde nada. Sin una regla que reconociera
este patrón, el agente desperdiciaba turnos repitiendo búsquedas que ya
sabía que no darían resultado, en vez de ofrecer la acción obviamente útil
(guardar la información como nota nueva).

### Cómo se corrigió

Se añadió la regla "OFRECER GUARDAR INFORMACIÓN NUEVA" al prompt: si el
Final Answer anterior fue "no tengo información" sobre un tema y el
usuario responde con una afirmación (no una instrucción de búsqueda) sobre
ese mismo tema, el agente no debe volver a llamar `search_vault`; debe
preguntar en el propio Final Answer si quiere que lo guarde como nota, y
solo llamar a `create_note` (que ya exige confirmación de escritura desde
la entrada anterior de este log) cuando el usuario confirme en un turno
posterior. Es, por naturaleza, una regla de prompt — a diferencia de la
garantía de "nunca escribir sin confirmar" (que se impuso en código), aquí
no hay forma de codificar de forma fiable "esto es información nueva y no
una instrucción de búsqueda": es un juicio semántico que depende del LLM.

### Cómo evitarlo en el futuro

Al diseñar reglas de prompt para un agente conversacional con memoria,
pensar en los turnos siguientes al caso feliz/triste inmediato: un "no
encontré nada" no es un callejón sin salida conversacional, es el punto de
partida más probable para que el usuario aporte la información que
faltaba. Diseñar explícitamente ese segundo turno, no solo el primero.

---

## [2026-07-20] Panel lateral de referencias se abría solo, y luego dejó de aparecer

**Fase**: fase-6-chainlit.md
**Categoría**: diseño / UI

### Qué se hizo mal

`_build_citation_elements` (`src/app/__init__.py`) adjuntaba los
resultados de `search_vault` como `cl.Text(..., display="side")` a cada
respuesta del agente. El supuesto de diseño (documentado en
`implementation-plan.md`) era que el panel lateral de Chainlit solo se
abre cuando el usuario hace click en una referencia mencionada en el
chat — pero esa verificación visual en navegador quedó pendiente y nunca
se completó. En producción, el panel se abría automáticamente en cuanto
llegaba cualquier respuesta con resultados de búsqueda, sin interacción
del usuario.

Al corregirlo cambiando `display="side"` por `display="page"` (para que
el click navegase a una página dedicada en vez de abrir un panel), el
síntoma cambió mal: dejaron de aparecer chips de referencia clicables
por completo.

### Por qué era un error

Ambos supuestos se basaban en la documentación superficial de Chainlit,
no en el comportamiento real del frontend. Leyendo el bundle JS
instalado (`chainlit==2.11.1`, `.venv/.../chainlit/frontend/dist/`) se
confirmó que hay dos mecanismos independientes:

1. Un `useEffect` que filtra **todos** los elementos adjuntos al hilo
   con `display==="side"` y abre el panel lateral automáticamente en
   cuanto la lista cambia — sin importar el texto del mensaje ni ningún
   click. De ahí el primer bug.
2. Para cualquier `display` que no sea `"inline"` (incluido `"page"`),
   el chip clicable **solo se renderiza si el `name` del elemento
   aparece literalmente como substring dentro del `content` del
   mensaje** (la función que arma el contenido hace un
   `content.replaceAll(regex_de_los_names, ...)`). El `content` de la
   respuesta es texto libre generado por el LLM, que casi nunca
   reproduce el `note_id` exacto (ruta de archivo) — de ahí el segundo
   bug: el elemento queda adjunto pero invisible.

En ambos casos, confiar en la documentación o en la analogía ("`side`
abre panel, `page` abre página, ambos con el mismo mecanismo de
disparo") sin leer el bundle real llevó a una hipótesis incorrecta.

### Cómo se corrigió

1. Cambiar `display="side"` → `display="page"` en
   `_build_citation_elements` (evita la auto-apertura, punto 1).
2. Añadir `_build_sources_footer()` en `src/app/__init__.py`, que
   construye de forma **determinista** (no dependiente del LLM) un pie
   de mensaje con los `note_id` exactos de las fuentes citadas, y se
   concatena siempre a `response["output"]` antes de enviar el
   `cl.Message`. Esto garantiza la coincidencia textual que Chainlit
   exige para renderizar el chip (punto 2), sin depender de que el
   prompt del LLM cite la ruta exacta de la nota.
3. Se extrajo `_dedup_note_ids()` como función pura compartida entre
   `_build_citation_elements` y `_build_sources_footer`, lo que además
   la hizo testeable sin necesitar un contexto real de Chainlit
   (`cl.Text` no se puede instanciar fuera de una sesión activa —
   lanza `ChainlitContextException`).

### Cómo evitarlo en el futuro

Para cualquier comportamiento de Chainlit que dependa de cómo el
frontend interpreta los `elements` adjuntos a un mensaje (paneles,
chips, auto-apertura), no asumir el comportamiento a partir del nombre
del parámetro (`display="side"` vs `"page"`) ni de la documentación de
alto nivel: leer el bundle JS instalado en `.venv` cuando el
comportamiento observado no cuadre con lo esperado, como ya se hizo
aquí. Y, como en la entrada anterior sobre confirmación de escritura:
si una garantía de UI depende de que el LLM reproduzca un dato exacto
(aquí, el `note_id`) en texto libre, no confiar en el prompt —
construir ese dato de forma determinista en código.

---

## [2026-07-20] El agente seguía inventando contenido e ignorando sus propias preguntas de seguimiento

**Fase**: fase-6-chainlit.md
**Categoría**: diseño

### Qué se hizo mal

Log de producción (Groq): tras la regla "OFRECER GUARDAR INFORMACIÓN
NUEVA" (entrada anterior de este log), el agente sí preguntaba
correctamente "¿quieres que guarde esto como nota nueva?" cuando no
encontraba información. Pero cuando el usuario respondía solo "sí"
(confirmando la acción sin aportar el contenido real), el agente
llamaba a `create_note` con contenido inventado por él mismo
(`"El usuario proporcionará la información sobre cómo cocinar un
huevo"`, y en el turno siguiente `"Para cocinar un huevo, se
necesitan..."`), en vez de preguntar cuál era el contenido real.
Además, cuando el propio agente preguntó "¿quieres agregar tags como
'recetas' o 'cocina'?" y el usuario respondió con la palabra "recetas",
el turno siguiente del agente ignoró por completo esa respuesta y
disparó una nueva búsqueda `search_vault` con "recetas" como si fuera
una pregunta nueva sobre el vault, en vez de interpretarla como el tag
a añadir con `edit_note`.

### Por qué era un error

La regla "OFRECER GUARDAR INFORMACIÓN NUEVA" ya existente asumía
implícitamente que, en el turno de confirmación, el usuario "aporta él
mismo información nueva y sustancial" — pero no cubría el caso, más
común en la práctica, de que el usuario solo confirme ("sí") sin dar
contenido. Ante ese vacío de instrucción, el LLM rellenaba el campo
`content` con texto plausible pero inventado, y ese contenido pasaba
sin fricción por el único guardarraíl real del sistema
(`_confirm_write_action`, ver entrada de confirmación de escritura),
que solo pregunta "¿confirmas esta acción?" sobre el contenido que el
LLM ya decidió — no valida si ese contenido es real.

Por separado, el prompt tampoco tenía ninguna regla de continuidad
conversacional: nada le decía al LLM que debía correlacionar la
respuesta corta del usuario con la pregunta de seguimiento que él mismo
acababa de formular. La regla genérica "Usa search_vault ANTES de
responder preguntas sobre el contenido del vault" ganaba por defecto
ante la ausencia de una regla más específica, y el LLM trataba "recetas"
como una nueva consulta.

Se confirmó además, investigando `ObsidianLoader.update()`
(`src/adapters/obsidian_loader.py`), que el manejo de tags al editar
**no tenía ningún bug**: la unión `existing.tags + tags` con
`tags=[]` preserva los tags existentes. El síntoma observado era
puramente de prompt (el agente nunca llegó a intentar añadir el tag),
no de pérdida de datos en el adaptador.

### Cómo se corrigió

Se añadieron dos reglas nuevas a `_REACT_PROMPT_TEMPLATE`
(`src/agent/agent.py`), en el mismo estilo que las reglas existentes:

1. **NUNCA INVENTES CONTENIDO**: prohíbe explícitamente generar
   contenido de relleno en `create_note`/`edit_note`; si no se tiene el
   texto real, instruye a preguntarlo explícitamente en el `Final
   Answer` y esperar la respuesta antes de llamar a la tool.
2. **CONTINUIDAD DE PREGUNTAS PROPIAS**: instruye a interpretar el
   siguiente mensaje del usuario como respuesta a la pregunta de
   seguimiento del turno anterior (revisando `chat_history`) antes de
   decidir si hace falta otra herramienta, con el ejemplo explícito de
   tags → `edit_note`, no `search_vault`.

Se añadieron tests de regresión en `tests/unit/test_agent.py`
(`test_react_prompt_forbids_placeholder_content`,
`test_react_prompt_includes_follow_up_continuity_rule`) que verifican
la presencia de ambas reglas en el prompt, siguiendo el patrón ya
usado por `test_react_prompt_includes_offer_to_save_new_information_rule`.

### Cómo evitarlo en el futuro

Como ya señala la entrada anterior de este log: al añadir una regla de
prompt para cubrir un escenario conversacional, pensar explícitamente
en los casos degenerados de ese mismo escenario (aquí: "el usuario
confirma sin dar contenido" era el caso degenerado de "el usuario
aporta información nueva", y no se cubrió la primera vez). Y, en
general, cualquier regla de "pregúntale al usuario X" necesita una
regla hermana de "cuando el usuario responda, trátalo como respuesta a
X" — sin esta segunda mitad, el prompt sabe preguntar pero no sabe
escuchar.

---

## [2026-07-21] El mecanismo para saltar la pantalla de bienvenida no era el correcto

**Fase**: fase-6-chainlit.md
**Categoría**: diseño

### Qué se hizo mal

La iteración 5 de `implementation-plan.md` (arranque directo en la vista
de chat) añadió en `_init_agent_session` (`src/app/__init__.py`) un hack
que fijaba `cl.context.session.has_first_interaction = True` y llamaba a
`cl.context.emitter.init_thread(interaction="chunking_init")`, basándose
en la lectura de `chainlit/socket.py`/`chainlit/emitter.py`: la pantalla
de bienvenida se oculta cuando el cliente recibe el evento de socket
`"first_interaction"`, así que se decidió disparar ese mismo evento a
mano. El usuario probó en el navegador y siguió viendo el flash de la
pantalla de bienvenida antes de pasar al chat.

### Por qué era un error

Investigar el bundle JS compilado del frontend (no solo el backend) reveló
que la premisa era incorrecta: el componente que renderiza
`#welcome-screen` decide mostrarse u ocultarse según `Nie(messages)` —
si la lista de `messages` de la sesión está vacía o no — y **no** según el
evento `first_interaction`. Ese evento solo sirve para otra cosa (nombrar
el thread vía `data_layer.update_thread`, que este proyecto ni siquiera
configura, por lo que `flush_thread_queues` es un no-op salvo por el
`emit`). El hack no solo no cumplía su propósito: añadía un `await` de red
completo (`init_thread`) antes de enviar el primer `cl.Message` de carga,
alargando exactamente el flash que pretendía evitar.

La lección de fondo: `chainlit/emitter.py` y `chainlit/socket.py`
(backend) explican *cuándo* se emite un evento, pero no *qué hace* ese
evento en el cliente. Verificar solo el lado del servidor llevó a una
solución que "debería funcionar" según la lectura del backend pero que no
tenía ningún efecto observable en el frontend real.

### Cómo se corrigió

Se eliminó el bloque `has_first_interaction`/`init_thread` de
`_init_agent_session`. El mensaje de carga (`cl.Message(...).send()`)
vuelve a ser la primera acción de la función, sin ningún paso previo que
retrase su llegada — dado que Chainlit oculta la bienvenida en cuanto
llega el primer mensaje real, minimizar la latencia hasta ese envío es la
única palanca real disponible. Se corrigió también el docstring de la
función para describir el mecanismo verificado (`Nie(messages)`) en vez
del incorrecto.

### Cómo evitarlo en el futuro

Cuando una hipótesis sobre comportamiento de UI se basa en leer solo el
código Python del backend de un framework con frontend compilado
(Chainlit, y en general cualquier SPA), verificar también el bundle JS
servido realmente antes de implementar — el backend puede emitir eventos
cuyo efecto en el cliente es distinto (o nulo) al que su nombre sugiere.
Cuando el usuario reporta que un fix "no funcionó" tras una verificación
manual, no reforzar el mismo mecanismo: cuestionar la hipótesis de
partida y volver a leer el código real, tal como se hizo aquí.

---

## [2026-07-21] Notas creadas/editadas por el agente solo se indexaban en la estrategia activa

**Fase**: fase-6-chainlit.md
**Categoría**: arquitectura

### Qué se hizo mal

El usuario reportó: crear una nota con la estrategia de chunking `fixed`
activa y luego cambiar a `markdown` o `backlink` desde el panel de
Settings hacía que la búsqueda no encontrara esa nota, como si no
existiera.

### Por qué era un error

`ChromaVectorStore` mantiene una colección por estrategia (diseño
intencional para comparar Precision@K/MRR). `_init_agent_session`
(`src/app/__init__.py`) construye, para la estrategia activa, un único
`chunker` y un único `IngestVault(loader, chunker, store)`, inyectado en
`ManageNotes`. `ManageNotes.create()`/`update()` llaman
`ingest.execute_single(note.id)`, que chunkeaba la nota con ese único
chunker y llamaba `store.add_chunks(chunks)`. Como cada chunker marca sus
chunks con su propio `Chunk.strategy` fijo por clase, y
`ChromaVectorStore.add_chunks()` enruta cada chunk a la colección de su
`strategy`, la nota solo terminaba indexada en la colección de la
estrategia activa en el momento de crearla — nunca en las otras dos. El
diseño de "una colección por estrategia" es correcto para la ingesta
masiva del vault (`scripts/ingest.py --strategy X`, pensada para producir
resultados de evaluación aislados y comparables), pero no tenía sentido
aplicado a la escritura interactiva desde el chat: el usuario no está
"evaluando una estrategia" al crear una nota, espera poder usarla después
sin importar cuál esté activa.

### Cómo se corrigió

`IngestVault` ganó un parámetro opcional `all_chunkers: list[BaseChunker]
| None`, usado únicamente por `execute_single()`: hace un solo
`delete_by_note()` (ya opera sobre todas las colecciones) y luego un
`chunk_many()` + `add_chunks()` por cada chunker de la lista, sumando el
total de chunks. `execute()` (la ingesta masiva del CLI) no cambia — sigue
usando un único `chunker`. `_init_agent_session` construye
`all_chunkers = [get_chunker(s) for s in ChunkStrategy]` y lo pasa al
`IngestVault` de `ManageNotes`.

Se descartó llamar `execute_single()` tres veces (una por estrategia, con
un `IngestVault` distinto cada vez) porque cada llamada habría borrado la
nota de **todas** las colecciones antes de reindexar solo en la suya — la
segunda y tercera llamada habrían borrado lo que la anterior acababa de
indexar, sobreviviendo solo la última estrategia procesada. Se documentó
como test de regresión explícito
(`test_ingest_vault_execute_single_deletes_note_only_once_with_multiple_chunkers`).

### Cómo evitarlo en el futuro

Cuando un mismo caso de uso (`IngestVault`) sirve a dos flujos con
requisitos distintos — ingesta masiva por estrategia para evaluación
comparativa, y escritura interactiva que debe funcionar sin importar la
estrategia activa — no asumir que ambos deben compartir exactamente la
misma configuración (un chunker). Preguntar explícitamente "¿este
componente se usa igual en los dos flujos, o uno de ellos tiene una
necesidad distinta que el diseño actual no contempla?" antes de dar por
buena una única estrategia activa como suficiente para todo.
