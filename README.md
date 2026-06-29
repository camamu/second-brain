---
title: Obsidian RAG Agent
emoji: 🧠
colorFrom: purple
colorTo: teal
sdk: docker
app_port: 8000
---

# Obsidian RAG Agent

Agente conversacional RAG sobre un vault de Obsidian. TFM del Máster en Desarrollo de IA.

El sistema indexa notas Markdown con tres estrategias de chunking distintas y permite hacer preguntas en lenguaje natural sobre el contenido del vault.

## Tecnologías

- **LangChain** — orquestación del agente ReAct
- **Groq** (`llama-3.2-90b-text-preview`) — LLM de generación
- **HuggingFace Embeddings** (`nomic-ai/nomic-embed-text-v1`) — embeddings locales
- **ChromaDB** — vector store con colecciones por estrategia
- **Chainlit** — interfaz de chat web

## Estrategias de chunking

| Estrategia | Descripción |
|---|---|
| `fixed` | Ventanas de 512 tokens con solapamiento de 50 |
| `markdown` | División por cabeceras Markdown (`#`, `##`, `###`) |
| `backlink` | Expansión con el contenido de notas enlazadas (`[[backlinks]]`) |

## Uso

Selecciona una estrategia de chunking al abrir el chat y haz preguntas sobre el vault.

En esta demo las herramientas de creación y edición de notas están deshabilitadas (`READONLY_MODE=true`).

## Despliegue local

```bash
git clone <repo>
cd second-brain
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configurar .env (ver .env.example)
# Con USE_LOCAL=false y GROQ_API_KEY=<tu_key>

python scripts/ingest.py
chainlit run app.py
```

## Secrets requeridos (Hugging Face Spaces)

Configura `GROQ_API_KEY` en los secrets del Space.
