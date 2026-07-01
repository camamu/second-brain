---
title: "LangChain - Framework de Orquestación"
tags: [langchain, framework, agente, ia]
date: 2026-01-20
---

# LangChain - Framework de Orquestación

**LangChain** es el framework de orquestación central de este proyecto. Proporciona abstracciones para conectar LLMs, herramientas, memoria conversacional y cadenas de procesamiento.

## Componentes utilizados

### AgentExecutor
Ejecuta el bucle ReAct: razona sobre qué herramienta usar, la invoca, observa el resultado y repite hasta generar la respuesta final. Ver [[Agente ReAct]].

### ConversationBufferWindowMemory
Mantiene las últimas `k=10` interacciones en memoria para que el agente tenga contexto histórico de la conversación.

### PromptTemplate
Define la plantilla del prompt ReAct en español, con variables `{tools}`, `{tool_names}`, `{input}`, `{agent_scratchpad}` y `{chat_history}`.

### Tool
Abstracción para las herramientas del agente (`search_vault`, `create_note`, `edit_note`). Cada `Tool` tiene nombre, descripción y función callable.

## Adaptadores LangChain en este proyecto

Los adaptadores de la capa hexagonal exponen un método `as_langchain()` que devuelve el objeto nativo de LangChain:

- `OllamaLLMAdapter.as_langchain()` → `OllamaLLM`
- `GroqLLMAdapter.as_langchain()` → `ChatGroq`

Esto mantiene el dominio limpio de dependencias externas: solo los adaptadores conocen LangChain.

## Versiones

```
langchain>=0.2
langchain-core>=0.2
langchain-community>=0.2
langchain-groq>=0.1
langchain-huggingface>=0.0.3
langchain-ollama>=0.1
```

## Relación con la arquitectura hexagonal

LangChain vive exclusivamente en la capa `src/agent/` y en los adaptadores `src/adapters/llm/`. Las capas `src/domain/` y `src/application/` no importan nada de LangChain.

Ver también: [[RAG - Recuperación Aumentada con Generación]], [[Chainlit - Interfaz Conversacional]], [[Modelos de Lenguaje Grande (LLM)]].
