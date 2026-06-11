# Fase 6 — Interfaz Chainlit

## Contexto

Chainlit proporciona una interfaz de chat web con muy poco código. Se conecta al agente LangChain y permite al usuario interactuar con el vault desde el navegador.

**Ficheros a crear/modificar:**
- `app.py` (punto de entrada)
- `.chainlit/config.toml` (se genera automáticamente, personalizar)
- `chainlit.md` (página de bienvenida)

**Dependencias:**
- `chainlit`
- `src.infrastructure.config` (factory)
- `src.application.*` (casos de uso)
- `src.agent.agent` (create_agent)

---

## Tareas

### T6.1 — Crear `app.py`

Este es el punto de entrada de la aplicación. Conecta la factory con el agente y Chainlit.

```python
"""Obsidian RAG Agent — Chainlit entry point."""

import logging
import chainlit as cl
from src.infrastructure.config import (
    get_llm, get_embedder, get_vector_store,
    get_note_loader, get_note_writer, get_chunker_from_env,
)
from src.application.ingest_vault import IngestVault
from src.application.search_notes import SearchNotes
from src.application.manage_notes import ManageNotes
from src.agent.agent import create_agent
from src.domain.models import ChunkStrategy

logging.basicConfig(level=logging.INFO)
```

**`@cl.on_chat_start`** — se ejecuta cuando un usuario abre el chat:
1. Instancia todos los adaptadores via factory.
2. Crea los casos de uso.
3. Crea el agente con `create_agent(...)`.
4. Guarda el agente en la sesión: `cl.user_session.set("agent", agent)`.
5. Envía mensaje de bienvenida al usuario.

**`@cl.on_message`** — se ejecuta por cada mensaje del usuario:
1. Recupera el agente de la sesión: `cl.user_session.get("agent")`.
2. Muestra un spinner/indicador de que está pensando.
3. Invoca el agente: `response = agent.invoke({"input": message.content})`.
4. Envía `response["output"]` como respuesta de Chainlit.
5. Si hay error, enviar un mensaje de error limpio al usuario.

### T6.2 — Crear selector de estrategia de chunking en la UI

Usar `@cl.on_chat_start` para presentar las opciones de chunking al usuario al inicio de la sesión. Chainlit soporta `cl.AskActionMessage` para esto:

```python
actions = [
    cl.Action(name="fixed", payload={"strategy": "fixed"}, label="Chunking por tamaño fijo"),
    cl.Action(name="markdown", payload={"strategy": "markdown"}, label="Chunking por cabeceras Markdown"),
    cl.Action(name="backlink", payload={"strategy": "backlink"}, label="Chunking por backlinks"),
]
res = await cl.AskActionMessage(
    content="¿Qué estrategia de chunking quieres usar?",
    actions=actions,
).send()
```

Según la selección, instanciar el chunker correspondiente y pasarlo al agente.

Si el usuario no selecciona nada (timeout), usar la estrategia por defecto del .env.

### T6.3 — Crear `chainlit.md`

Página de bienvenida que se muestra al abrir la app:

```markdown
# 🧠 Obsidian RAG Agent

Bienvenido a tu asistente conversacional para Obsidian.

## ¿Qué puedo hacer?

- **Buscar**: Pregúntame sobre el contenido de tus notas
- **Crear**: Pídeme que cree una nueva nota
- **Editar**: Pídeme que modifique una nota existente

## Ejemplos

- "¿Qué notas tengo sobre arquitectura hexagonal?"
- "Crea una nota sobre los patrones de diseño que hemos visto"
- "Actualiza la nota del TFM con los avances de esta semana"
```

### T6.4 — Personalizar configuración de Chainlit

Ejecutar `chainlit run app.py` una vez para que genere `.chainlit/config.toml`. Después modificar:

```toml
[project]
name = "Obsidian RAG Agent"
enable_telemetry = false

[UI]
name = "Obsidian RAG"
description = "Habla con tu vault de Obsidian"
default_theme = "dark"
```

---

## Tests

No se escriben tests unitarios para Chainlit (es UI/integración). Verificación manual:

- [ ] `chainlit run app.py` arranca sin errores
- [ ] El selector de chunking aparece al iniciar
- [ ] Una pregunta de búsqueda devuelve resultados del vault
- [ ] Se puede crear una nota y luego buscarla
- [ ] Se puede editar una nota existente
- [ ] Los errores se muestran al usuario de forma limpia (no stacktraces)

---

## Reglas de implementación

- `app.py` solo importa de `infrastructure` (factory) y `application` (casos de uso).
- Toda la lógica de negocio está en los casos de uso — `app.py` solo conecta piezas.
- El agente se crea una vez por sesión (en `on_chat_start`), no por mensaje.
- `async` en todos los handlers de Chainlit (es un framework async).

---

## Criterio de completado

- [ ] `chainlit run app.py` abre el chat en http://localhost:8000
- [ ] El usuario puede buscar, crear y editar notas desde el chat
- [ ] El selector de chunking funciona
- [ ] El sistema responde en menos de 30 segundos con Ollama local
