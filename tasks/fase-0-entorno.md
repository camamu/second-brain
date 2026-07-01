# Fase 0 — Entorno y configuración

## Contexto del proyecto

Sistema RAG conversacional que permite interactuar con un vault de Obsidian. El usuario puede hacer preguntas sobre sus notas, crear notas nuevas y editar las existentes desde un chat.

**Stack**: Python 3.11+ | LangChain | Ollama (Llama 3.2 + nomic-embed-text) | ChromaDB | Chainlit
**Arquitectura**: Hexagonal (Puertos y Adaptadores)
**Despliegue dual**: local con Ollama / producción con Groq + HuggingFace Spaces

---

## Tareas

### T0.1 — Crear entorno virtual Python

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### T0.2 — Crear `requirements.txt`

```
langchain>=0.3.0
langchain-ollama>=0.2.0
langchain-chroma>=0.1.0
langchain-groq>=0.2.0
langchain-huggingface>=0.1.0
chromadb>=0.5.0
chainlit>=1.0.0
python-frontmatter>=1.1.0
python-dotenv>=1.0.0
```

### T0.3 — Crear `requirements-dev.txt`

```
-r requirements.txt
pytest>=8.0.0
pytest-cov>=5.0.0
black>=24.0.0
isort>=5.13.0
```

### T0.4 — Instalar dependencias

```bash
pip install -r requirements-dev.txt
```

### T0.5 — Descargar modelos Ollama

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

### T0.6 — Crear `.env.example`

```env
# Entorno: "true" = Ollama local, "false" = Groq + HuggingFace
USE_LOCAL=true

# Vault
VAULT_PATH=/ruta/absoluta/a/tu/vault

# Ollama (solo si USE_LOCAL=true)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_EMBED_MODEL=nomic-embed-text

# Groq (solo si USE_LOCAL=false)
GROQ_API_KEY=
GROQ_MODEL=llama-3.2-90b-text-preview

# ChromaDB
CHROMA_PERSIST_DIR=data/chroma_db

# Chunking
CHUNKER_STRATEGY=fixed
CHUNK_SIZE=512
CHUNK_OVERLAP=50

# Logging
LOG_LEVEL=INFO
```

### T0.7 — Crear `.gitignore`

Debe incluir al menos:
```
.venv/
.env
data/chroma_db/
__pycache__/
*.pyc
.pytest_cache/
.coverage
dist/
*.egg-info/
```

### T0.8 — Crear script de verificación `scripts/test_ollama.py`

Script que:
1. Importa `OllamaLLM` y `OllamaEmbeddings` de `langchain_ollama`.
2. Envía un prompt sencillo al LLM y comprueba que responde.
3. Genera un embedding de prueba y comprueba que devuelve un vector de dimensión 768.
4. Imprime los resultados con `print()` (es un script de verificación, no producción).

### T0.9 — Verificar estructura de carpetas

La estructura final del proyecto debe ser:

```
obsidian-rag/
├── .env.example
├── .gitignore
├── .opencode/skills/         # Ya creadas (no tocar)
├── AGENTS.md                 # Ya creado (no tocar)
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── src/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py         # Ya creado
│   │   └── ports.py          # Ya creado
│   ├── application/
│   │   └── __init__.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── chunkers/
│   │   │   └── __init__.py
│   │   ├── vector_store/
│   │   │   └── __init__.py
│   │   └── llm/
│   │       └── __init__.py
│   ├── agent/
│   │   └── __init__.py
│   └── infrastructure/
│       └── __init__.py
├── data/
│   └── chroma_db/
├── evaluation/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   └── __init__.py
│   └── integration/
│       └── __init__.py
├── scripts/
│   └── test_ollama.py
└── app.py
```

---

## Criterio de completado

- [x] `.venv` creado y activado
- [x] Dependencias instaladas sin errores — unificadas en un solo `requirements.txt` (se eliminó `requirements-dev.txt`)
- [ ] Ollama responde desde Python (LLM + embeddings) — pendiente: `scripts/test_ollama_chat.py` verifica el LLM pero no los embeddings; falta completar el script
- [ ] `.env` creado a partir de `.env.example` con rutas reales — acción manual del usuario
- [x] Estructura de carpetas verificada — creados `evaluation/`, `app.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`
- [ ] `git init` + primer commit con todo lo anterior — git inicializado, commit pendiente
