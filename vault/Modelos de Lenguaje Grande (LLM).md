---
title: "Modelos de Lenguaje Grande (LLM)"
tags: [llm, ia, generacion, transformers]
date: 2026-01-17
---

# Modelos de Lenguaje Grande (LLM)

Los **Modelos de Lenguaje Grande** (LLM) son redes neuronales entrenadas sobre enormes corpus de texto. Su arquitectura Transformer les permite generar texto coherente y seguir instrucciones en lenguaje natural.

## Modelos usados en este proyecto

### Llama 3.2 (Meta)
- Familia de modelos de 1B, 3B y 90B parámetros
- Open-source bajo licencia permisiva
- Versión local (Ollama): `llama3.2` (3B) — rápido, requiere solo 4 GB de RAM
- Versión en Groq: `llama-3.2-90b-text-preview` — 90B parámetros, alta calidad

### Limitación con modelos pequeños
Los modelos ≤3B parámetros tienen dificultades con el formato ReAct: mezclan `Action` y `Final Answer` en el mismo turno, confundiendo al parser. Ver [[Agente ReAct]] para más detalle.

**Recomendación**: usar Groq (90B) en producción para operaciones de escritura; Llama 3.2 local solo para búsquedas simples.

## Groq API

Groq proporciona acceso a modelos de gran escala con latencia extremadamente baja gracias a su hardware LPU (*Language Processing Unit*). El tier gratuito incluye 30 peticiones/minuto.

En este proyecto, `GroqLLMAdapter` envuelve `ChatGroq` de LangChain. Ver [[LangChain - Framework de Orquestación]].

## Temperatura y parámetros

| Parámetro | Efecto | Valor típico en RAG |
|---|---|---|
| temperature | Aleatoriedad de la respuesta | 0.0–0.3 (factual) |
| max_tokens | Longitud máxima de respuesta | 512–2048 |
| top_p | Nucleus sampling | 0.9 |

## Relación con RAG

En [[RAG - Recuperación Aumentada con Generación]], el LLM es el componente final: recibe el contexto recuperado y genera la respuesta. No necesita "saber" la información de antemano — la lee del contexto en cada llamada.

Ver también: [[TFM - Metodología de Evaluación]], [[TFM - Resultados Preliminares]].
