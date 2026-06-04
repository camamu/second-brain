# AGENTS.md — Obsidian RAG Agent

## Descripción del proyecto

Sistema RAG (Retrieval-Augmented Generation) conversacional que permite "hablar" con un vault de Obsidian. El usuario puede hacer preguntas sobre sus notas, crear notas nuevas y editar las existentes desde una interfaz de chat.

Es un TFM académico con dos objetivos:

1. **Sistema funcional**: agente LangChain con herramientas que actúa sobre el vault.
2. **Aportación investigadora**: comparativa de tres estrategias de chunking medida con Precision@K y MRR.

---

## Stack técnico

| Componente | Tecnología |
|---|---|
| LLM local | Ollama + Llama 3.2 |
| LLM producción | Groq (llama-3.2) |
| Embeddings local | Ollama + nomic-embed-text |
| Embeddings producción | HuggingFace nomic-embed-text-v1 |
| Vector store | ChromaDB (persistido en `data/chroma_db/`) |
| Orquestador | LangChain |
| Interfaz | Chainlit |
| Lenguaje | Python 3.11+ |

---

## Arquitectura: Puertos y Adaptadores (Hexagonal)

```
domain/          → Entidades y puertos (interfaces abstractas). Sin dependencias externas.
application/     → Casos de uso. Solo depende de domain/.
adapters/        → Implementaciones concretas de los puertos.
agent/           → Agente LangChain y herramientas.
infrastructure/  → Configuración, variables de entorno, factories.
```

**Regla de dependencias**: las capas internas nunca importan de las externas.

- `domain` no importa nada del proyecto
- `application` solo importa de `domain`
- `adapters` implementa interfaces de `domain`
- `infrastructure` une todo mediante inyección de dependencias

---

## Convenciones de código

### General

- Python 3.11+, type hints en todas las funciones
- Docstrings en clases y métodos públicos (formato Google)
- Nombres en inglés para código, español solo en comentarios explicativos del TFM
- Máximo 80 caracteres por línea
- Sin `print()` en producción — usar `logging`

### Puertos (interfaces)

- Definidos en `src/domain/ports.py` como clases abstractas con `ABC`
- Nombres: `NounVerber` → ej. `NoteLoader`, `ChunkEmbedder`, `VectorStore`
- Todos los métodos abstractos llevan type hints completos

### Adaptadores

- Un fichero por adaptador
- El constructor recibe SOLO los parámetros que necesita (no el objeto config completo)
- Nunca llaman a `os.getenv()` directamente — reciben la config inyectada

### Casos de uso

- Una clase por caso de uso, un método público `execute()`
- Sin lógica de infraestructura (no instancian adaptadores, los reciben)

### Tests

- `tests/unit/` → sin I/O, sin red, sin ficheros reales
- `tests/integration/` → pueden usar ChromaDB en memoria y Ollama real
- Nombrado: `test_<módulo>_<comportamiento>_<resultado_esperado>`

---

## Variables de entorno

Ver `.env.example` para la lista completa. Las más importantes:

```
USE_LOCAL=true          # true=Ollama, false=Groq+HuggingFace
VAULT_PATH=             # Ruta absoluta al vault de Obsidian
OLLAMA_BASE_URL=http://localhost:11434
GROQ_API_KEY=           # Solo necesario si USE_LOCAL=false
```

---

## Chunkers (núcleo de la investigación)

Hay tres implementaciones en `src/adapters/chunkers/`, todas implementan `BaseChunker`:

| Chunker | Fichero | Descripción |
|---|---|---|
| Fixed size | `fixed_size.py` | Split por tokens con solapamiento configurable |
| Markdown header | `markdown_header.py` | Cada sección `##` es un chunk |
| Backlink-aware | `backlink_aware.py` | Nota + notas enlazadas como unidad semántica |

Para cambiar la estrategia activa: variable `CHUNKER_STRATEGY=fixed|markdown|backlink` en `.env`.

---

## Comandos útiles

```bash
# Activar entorno virtual
source .venv/bin/activate

# Indexar el vault (primera vez o tras cambios)
python scripts/ingest.py

# Arrancar la interfaz de chat
chainlit run app.py

# Ejecutar tests
pytest tests/unit/
pytest tests/integration/

# Verificar que Ollama responde
python scripts/test_ollama.py
```

---

## Flujo de datos

```
Vault .md files
    → ObsidianLoader        (lee frontmatter + contenido + backlinks)
    → BaseChunker           (divide en chunks según estrategia)
    → ChunkEmbedder         (genera vectores con nomic-embed-text)
    → VectorStore           (persiste en ChromaDB)

Query del usuario
    → Agent                 (LangChain con ReAct)
    → Tool: search_vault    (retrieval semántico en ChromaDB)
    → Tool: create_note     (escribe .md en el vault)
    → Tool: edit_note       (modifica .md existente)
    → LLM                   (genera respuesta con contexto recuperado)
    → Chainlit UI
```

---

## Estado del proyecto

- [ ] Entorno configurado
- [ ] Domain: modelos y puertos
- [ ] Adaptador: ObsidianLoader
- [ ] Adaptador: tres chunkers
- [ ] Adaptador: ChromaDB
- [ ] Adaptador: Ollama LLM
- [ ] Adaptador: Groq LLM
- [ ] Caso de uso: IngestVault
- [ ] Caso de uso: SearchNotes
- [ ] Agente con herramientas
- [ ] Interfaz Chainlit
- [ ] Evaluación: dataset + métricas
- [ ] Despliegue HuggingFace Spaces
