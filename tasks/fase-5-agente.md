# Fase 5 — Agente LangChain

## Contexto

El agente es la pieza central de la experiencia de usuario. Es un agente ReAct de LangChain que decide qué herramienta usar según la pregunta del usuario. Tiene tres herramientas: buscar en el vault, crear notas y editar notas.

**Ficheros a crear:**
- `src/agent/tools.py`
- `src/agent/agent.py`
- `tests/unit/test_tools.py`
- `tests/unit/test_agent.py`

**Dependencias:**
- `src.domain.*` (models y ports)
- `src.application.*` (casos de uso)
- `langchain` (para Tool, AgentExecutor, prompts)

---

## Tareas

### T5.1 — Definir herramienta `search_vault`

Fichero: `src/agent/tools.py`

Usa `langchain.tools.tool` decorator o `StructuredTool.from_function`.

```python
def create_search_tool(search_use_case: SearchNotes, strategy: ChunkStrategy) -> Tool:
```

- **name**: `"search_vault"`
- **description**: `"Busca información relevante en las notas del vault de Obsidian. Usa esta herramienta cuando el usuario haga una pregunta sobre el contenido de sus notas. Input: la pregunta o términos de búsqueda."`
- **Función interna**: llama a `search_use_case.execute_text(query, strategy=strategy)` y formatea los resultados como string legible.
- Formato de respuesta sugerido:

```
Encontrados 3 resultados:

[1] (nota: 01-proyectos/tfm, score: 0.85)
Contenido del chunk relevante...

[2] (nota: 02-areas/python, score: 0.72)
Contenido del chunk relevante...
```

- En caso de error (VectorStoreError), devolver un mensaje de error user-friendly sin stacktrace.

### T5.2 — Definir herramienta `create_note`

```python
def create_note_tool(manage_use_case: ManageNotes) -> Tool:
```

- **name**: `"create_note"`
- **description**: `"Crea una nota nueva en el vault de Obsidian. Usa esta herramienta cuando el usuario quiera guardar información nueva. Input: un JSON con los campos 'title' (obligatorio), 'content' (obligatorio) y 'tags' (lista opcional)."`
- **Función interna**: parsea el input como JSON, llama a `manage_use_case.create(...)`, devuelve confirmación con el ID de la nota creada.
- Validar que el input sea JSON válido. Si no, devolver mensaje de error pidiéndolo en el formato correcto.

### T5.3 — Definir herramienta `edit_note`

```python
def create_edit_tool(manage_use_case: ManageNotes) -> Tool:
```

- **name**: `"edit_note"`
- **description**: `"Edita una nota existente en el vault. Usa esta herramienta cuando el usuario quiera modificar el contenido de una nota. Input: un JSON con los campos 'note_id' (obligatorio) y 'content' (nuevo contenido completo)."`
- **Función interna**: parsea JSON, llama a `manage_use_case.update(...)`, devuelve confirmación.
- Si NoteNotFoundError, devolver mensaje diciendo que la nota no existe y sugerir buscarla primero.

### T5.4 — Montar el agente ReAct

Fichero: `src/agent/agent.py`

```python
def create_agent(
    llm: ConversationalLLM,
    search_use_case: SearchNotes,
    manage_use_case: ManageNotes,
    strategy: ChunkStrategy = ChunkStrategy.FIXED_SIZE,
) -> AgentExecutor:
```

Componentes:
1. **Tools**: las tres herramientas de T5.1-T5.3.
2. **System prompt**:

```
Eres un asistente conversacional que ayuda al usuario a interactuar con su vault de Obsidian (su "segundo cerebro").

Tus capacidades:
- Buscar información en las notas del usuario usando search_vault.
- Crear nuevas notas con create_note.
- Editar notas existentes con edit_note.

Reglas:
- Siempre busca en el vault antes de responder preguntas sobre el contenido de las notas.
- Responde en el mismo idioma que el usuario.
- Si no encuentras información relevante, dilo claramente.
- Cuando crees o edites notas, confirma la acción al usuario.
- Sé conciso pero útil.
```

3. **Memoria de conversación**: usar `ConversationBufferWindowMemory` con `k=10` (últimos 10 intercambios). Esto permite seguimiento de contexto en la conversación sin llenar la ventana de contexto.

4. **Agent type**: usar `create_react_agent` con el prompt de ReAct. Si el LLM local (Llama 3.2) tiene problemas con ReAct, considerar `create_tool_calling_agent` como alternativa.

5. **AgentExecutor config**:
   - `verbose=True` para desarrollo (cambiar a False en producción)
   - `handle_parsing_errors=True` (para cuando el LLM genera output malformado)
   - `max_iterations=5` (evitar bucles infinitos)

**Nota sobre la integración con LangChain**: el puerto `ConversationalLLM` es nuestra abstracción, pero LangChain espera sus propios tipos (`BaseLLM` o `BaseChatModel`). Hay dos opciones:
1. Que los adaptadores (OllamaLLMAdapter, GroqLLMAdapter) expongan el objeto interno de LangChain via un método `as_langchain() -> BaseLLM`.
2. Que `create_agent` reciba directamente el objeto LangChain en vez del puerto.

La opción 1 es más limpia arquitectónicamente. Implementar un método `as_langchain()` en el puerto `ConversationalLLM` y en ambos adaptadores.

---

## Tests

### T5.5 — `tests/unit/test_tools.py`

Mockear los casos de uso (SearchNotes, ManageNotes):

- `test_search_tool_calls_search_use_case_with_query`
- `test_search_tool_formats_results_as_readable_string`
- `test_search_tool_returns_friendly_message_on_error`
- `test_create_note_tool_parses_json_and_creates_note`
- `test_create_note_tool_returns_error_on_invalid_json`
- `test_edit_note_tool_parses_json_and_updates_note`
- `test_edit_note_tool_returns_error_when_note_not_found`

### T5.6 — `tests/unit/test_agent.py`

Test más ligero — verificar que el agente se crea correctamente:

- `test_create_agent_returns_agent_executor`
- `test_create_agent_has_three_tools`
- `test_create_agent_tools_have_correct_names`

---

## Reglas de implementación

- `tools.py` importa de `src.application` y `src.domain` — nunca de adapters.
- `agent.py` importa de `langchain` + `src.domain` + `src.application` — nunca de adapters.
- Las herramientas capturan excepciones de dominio y devuelven strings user-friendly.
- No hay lógica de negocio en las herramientas — solo formateo y delegación a casos de uso.
- Logging en cada herramienta: qué se pidió, qué se devolvió.

---

## Criterio de completado

- [ ] Las tres herramientas funcionan correctamente en aislamiento
- [ ] El agente se instancia y puede responder preguntas básicas
- [ ] El agente busca en el vault antes de responder (verificar con verbose=True)
- [ ] El agente crea y edita notas cuando se le pide
- [ ] Tests pasan: `pytest tests/unit/test_tools.py tests/unit/test_agent.py -v`
