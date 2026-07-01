---
title: "Agente ReAct"
tags: [agente, react, langchain, razonamiento]
date: 2026-01-23
---

# Agente ReAct

El patrón **ReAct** (*Reasoning + Acting*) es la estrategia de agente elegida para este proyecto. El LLM alterna entre razonar sobre qué hacer (*Thought*) y ejecutar acciones concretas (*Action*) hasta llegar a una respuesta final.

## Ciclo de ejecución

```
Thought: necesito buscar información sobre X
Action: search_vault
Action Input: "X"
Observation: [resultado de la búsqueda]
Thought: ya tengo la información
Final Answer: La respuesta es...
```

Este ciclo puede repetirse hasta `max_iterations=10` veces si el agente necesita múltiples búsquedas.

## Herramientas disponibles

| Herramienta | Función | Input |
|---|---|---|
| `search_vault` | Búsqueda semántica en el vault | string con la consulta |
| `create_note` | Crea una nota nueva en Obsidian | JSON: `{title, content, tags?}` |
| `edit_note` | Edita el contenido de una nota | JSON: `{note_id, content}` |

En modo solo lectura (`READONLY_MODE=true`), solo `search_vault` está disponible.

## Limitaciones con modelos pequeños

Los modelos ≤3B parámetros (como `llama3.2`) tienen problemas para seguir el formato ReAct estrictamente cuando el `Action Input` requiere JSON multi-campo. El error típico es mezclar `Action` y `Final Answer` en el mismo bloque.

**Solución**: usar [[Modelos de Lenguaje Grande (LLM)]] de mayor tamaño. En producción se usa Groq con `llama-3.2-90b-text-preview` (90B parámetros).

## Implementación

El agente se construye en `src/agent/agent.py` con:
- `create_react_agent` de [[LangChain - Framework de Orquestación]]
- Prompt ReAct en español con `ConversationBufferWindowMemory(k=10)`
- `AgentExecutor(handle_parsing_errors=True, verbose=True)`

## Alternativa considerada: tool-calling

Los LLMs modernos soportan *tool calling* nativo (función estructurada). Es más robusto con JSON que ReAct, pero menos portable entre modelos. Se descartó para mantener compatibilidad con modelos locales de Ollama.

Ver también: [[RAG - Recuperación Aumentada con Generación]], [[Chainlit - Interfaz Conversacional]], [[TFM - Objetivos y Alcance]].
