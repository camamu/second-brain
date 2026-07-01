---
title: "TFM - Objetivos y Alcance"
tags: [tfm, master, objetivos, alcance]
date: 2026-01-24
---

# TFM - Objetivos y Alcance

Este TFM (Trabajo de Fin de Máster) del **Máster en Desarrollo de Inteligencia Artificial** construye un agente conversacional RAG sobre un vault de [[Obsidian - Gestión del Conocimiento]] y evalúa tres estrategias de chunking.

## Objetivo principal

Demostrar que la elección de la estrategia de chunking tiene impacto medible en la calidad de recuperación de un sistema RAG sobre documentos con estructura de red (backlinks).

## Objetivos específicos

1. **Implementar** tres estrategias de chunking (fixed, markdown, backlink) bajo una arquitectura hexagonal limpia.
2. **Desplegar** un agente conversacional accesible por URL pública (Hugging Face Spaces).
3. **Evaluar** las estrategias usando métricas estándar de recuperación de información: Precision@K y MRR.
4. **Documentar** el proceso de desarrollo asistido por IA como metodología.

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| LLM (producción) | Groq API — [[Modelos de Lenguaje Grande (LLM)]] |
| LLM (local) | Ollama (llama3.2, mistral) |
| Embeddings | nomic-embed-text — [[Embeddings y Representación Vectorial]] |
| Vector store | [[ChromaDB - Vector Store]] |
| Orquestación | [[LangChain - Framework de Orquestación]] |
| UI | [[Chainlit - Interfaz Conversacional]] |
| Arquitectura | Hexagonal (ports & adapters) |

## Alcance del despliegue (Fase 8)

- El vault de demo incluye notas sobre los conceptos del TFM (IA, RAG, chunking).
- Las herramientas de escritura (`create_note`, `edit_note`) están deshabilitadas en la demo pública.
- El Space de Hugging Face permite acceder al sistema sin instalación local.

## Fases del proyecto

| Fase | Contenido |
|---|---|
| 1–2 | Dominio hexagonal + ingesta |
| 3–4 | Vectorstore, LLM, casos de uso |
| 5–6 | Agente ReAct + Chainlit |
| 7 | Evaluación comparativa |
| 8 | Despliegue en HF Spaces |

Ver también: [[TFM - Metodología de Evaluación]], [[TFM - Resultados Preliminares]], [[Estrategias de Chunking]].
