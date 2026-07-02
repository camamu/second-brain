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
