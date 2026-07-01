---
title: "Chainlit - Interfaz Conversacional"
tags: [chainlit, ui, chat, despliegue]
date: 2026-01-21
---

# Chainlit - Interfaz Conversacional

**Chainlit** es el framework de interfaz de usuario de este proyecto. Permite construir aplicaciones de chat web con integración nativa de LangChain y callbacks de streaming en tiempo real.

## ¿Por qué Chainlit?

- **Integración LangChain**: el callback `AsyncLangchainCallbackHandler` muestra el razonamiento del [[Agente ReAct]] en tiempo real (steps intermedios visibles).
- **Sin frontend custom**: la interfaz de chat está lista en minutos, sin HTML/JS/CSS.
- **Despliegue sencillo**: compatible con Docker y Hugging Face Spaces.

## Componentes usados

### `@cl.on_chat_start`
Se ejecuta al abrir una sesión. En este proyecto:
1. Muestra un selector de [[Estrategias de Chunking]] (`AskActionMessage`).
2. Inicializa todos los adaptadores (embedder, store, LLM).
3. Crea el agente ReAct y lo guarda en la sesión.

### `@cl.on_message`
Recibe cada mensaje del usuario y lo pasa al agente. La respuesta se devuelve como `cl.Message`.

### `cl.user_session`
Diccionario de sesión por usuario. El agente se guarda aquí para evitar re-inicializarlo en cada mensaje.

### `AsyncLangchainCallbackHandler`
Emite eventos en tiempo real: cada `Thought`, `Action` y `Observation` del bucle ReAct es visible en la UI durante la ejecución.

## Configuración

El fichero `.chainlit/config.toml` controla la apariencia (nombre del bot, tema, features habilitados). El fichero `chainlit.md` es la pantalla de bienvenida (Markdown).

## En producción

```bash
chainlit run app.py --host 0.0.0.0 --port 8000
```

En Hugging Face Spaces, el puerto 8000 está expuesto automáticamente. Ver [[TFM - Objetivos y Alcance]].

Ver también: [[LangChain - Framework de Orquestación]], [[RAG - Recuperación Aumentada con Generación]].
