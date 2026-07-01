# Plan de Implementación — Fase 5: Agente LangChain ReAct

> Plan guardado en git. El plan de la Fase 4 se conserva en el historial: `git log --oneline`.

## Contexto

Las fases 1–4 están completas (73 tests unitarios). La Fase 5 construye la capa `src/agent/`
con un agente ReAct de LangChain que expone tres herramientas sobre el vault de Obsidian:
búsqueda semántica, creación y edición de notas. Esta capa es el núcleo de la UX antes
de conectar Chainlit (Fase 6).

## Decisiones clave

| Decisión | Elegida | Motivo |
|---|---|---|
| `as_langchain()` en puerto vs. adaptadores | Solo en adaptadores | Preserva "zero external deps" del dominio |
| `create_agent()` acepta `BaseLanguageModel` | Sí | Mantiene el dominio limpio; la capa agent puede depender de LangChain |
| ReAct vs. tool-calling | ReAct primero | Más universal con modelos locales (ver tabla critical-task-planning) |
| Prompt — hub.pull vs. inline | Inline | Sin deps de red ni API key de LangChain Hub |
| Tool vs. StructuredTool para create/edit | Tool + JSON string | ReAct pasa action input como único string |

## Mapa de cambios (completo)

### Ficheros nuevos
- `src/agent/tools.py` — `create_search_tool`, `create_note_tool`, `create_edit_tool`
- `src/agent/agent.py` — `create_agent() -> AgentExecutor`
- `tests/unit/test_tools.py` — 7 tests
- `tests/unit/test_agent.py` — 3 tests

### Ficheros modificados
- `src/adapters/llm/ollama_adapter.py` — `OllamaLLMAdapter.as_langchain()`
- `src/adapters/llm/groq_adapter.py` — `GroqLLMAdapter.as_langchain()`
- `src/infrastructure/config.py` — `get_langchain_llm()` factory

### Ficheros sin cambios
- `src/domain/ports.py` — sigue sin imports externos
- Todos los chunkers, embedders, vector store, casos de uso

## Estado final

- [x] `OllamaLLMAdapter` y `GroqLLMAdapter` tienen `as_langchain()`
- [x] `config.py` expone `get_langchain_llm()`
- [x] `src/agent/tools.py` con las tres tool factories
- [x] `src/agent/agent.py` con `create_agent()`
- [x] `pytest tests/unit/ -q` → 83 tests en verde (73 previos + 7 tools + 3 agent)
- [x] `ruff check src/ tests/` → sin errores

## TODOs por funcionalidad

### 🔧 Adaptadores LLM
- [x] `OllamaLLMAdapter.as_langchain()` en `src/adapters/llm/ollama_adapter.py`
- [x] `GroqLLMAdapter.as_langchain()` en `src/adapters/llm/groq_adapter.py`
- [x] `get_langchain_llm()` en `src/infrastructure/config.py`

### 🧩 Herramientas del agente (`src/agent/tools.py`)
- [x] `create_search_tool()` con formato numerado y manejo de `VectorStoreError`
- [x] `create_note_tool()` con parseo JSON y manejo de `VaultWriteError`
- [x] `create_edit_tool()` con parseo JSON y manejo de `NoteNotFoundError`

### 🤖 Agente ReAct (`src/agent/agent.py`)
- [x] Prompt ReAct inline con instrucciones en español
- [x] `ConversationBufferWindowMemory(k=10)`
- [x] `create_react_agent` + `AgentExecutor(handle_parsing_errors=True, max_iterations=5)`
- [x] `create_agent(llm, search_use_case, manage_use_case, strategy) -> AgentExecutor`

### 🧪 Tests
- [x] 7 tests en `test_tools.py` (mocks con `spec=`)
- [x] 3 tests en `test_agent.py` (FakeListLLM de langchain_community)

### ✅ Verificación final
- [x] `pytest tests/unit/ -q` → 83 tests en verde
- [x] `ruff check src/ tests/` → sin errores
