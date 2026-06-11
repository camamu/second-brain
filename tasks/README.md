# Obsidian RAG Agent — Plan de tareas

## Título del TFM

> *"Diseño e implementación de un agente RAG conversacional sobre grafos de conocimiento personal: análisis comparativo de estrategias de chunking en vaults de Obsidian"*

## Stack

Python 3.11+ | LangChain | Ollama (local) / Groq (producción) | ChromaDB | Chainlit

## Fases

| Fase | Fichero | Descripción | Semana |
|---|---|---|---|
| 0 | `fase-0-entorno.md` | Entorno virtual, dependencias, Ollama, estructura de carpetas | 1 |
| 1 | `fase-1-dominio.md` | Entidades (Note, Chunk, etc.) y puertos (interfaces abstractas) | 1-2 |
| 2 | `fase-2-ingesta.md` | ObsidianLoader + tres chunkers (fixed, markdown, backlink) | 2 |
| 3 | `fase-3-vectorstore-llm.md` | ChromaDB, adaptadores Ollama/Groq, factory de configuración | 2-3 |
| 4 | `fase-4-casos-de-uso.md` | IngestVault, SearchNotes, ManageNotes + script CLI | 3 |
| 5 | `fase-5-agente.md` | Agente ReAct con tres herramientas (buscar, crear, editar) | 3-4 |
| 6 | `fase-6-chainlit.md` | Interfaz web de chat con selector de chunking | 4 |
| 7 | `fase-7-evaluacion.md` | Dataset anotado + Precision@K, MRR, Recall@K comparativa | 5-6 |
| 8 | `fase-8-despliegue.md` | Groq + HuggingFace Spaces (versión pública) | 6-7 |
| 9 | `fase-9-memoria-defensa.md` | Memoria técnica, presentación y demo en vivo | 7-8 |

## Cómo usar estos ficheros con Claude Code / OpenCode

Cada fichero de fase es autocontenido — incluye el contexto necesario, las tareas detalladas, los tests esperados y el criterio de completado. Pásalos uno a uno a Claude Code:

```
Implementa las tareas de este fichero: [pegar contenido de fase-X.md]
```

Antes de cada fase, verificar que la anterior está completada (tests en verde).

## Skills de OpenCode

Las convenciones de código están definidas en `.opencode/skills/`:

| Skill | Propósito |
|---|---|
| `hexagonal-architecture.md` | Reglas de dependencias entre capas |
| `python-clean-code.md` | Type hints, docstrings, naming, logging |
| `testing-strategy.md` | Unit vs integration, mocks, naming de tests |
| `error-handling.md` | Jerarquía de excepciones, traducción de errores |

## Ficheros ya creados

- `AGENTS.md` — contexto general del proyecto para OpenCode
- `src/domain/models.py` — entidades del dominio
- `src/domain/ports.py` — puertos (interfaces abstractas)
- Estructura de carpetas completa con `__init__.py`
