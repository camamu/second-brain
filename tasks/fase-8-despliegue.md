# Fase 8 — Despliegue (Groq + Hugging Face Spaces)

## Contexto

Desplegar una versión del sistema accesible por URL. En producción, el LLM se ejecuta en Groq (API gratuita) y los embeddings con HuggingFace (local en el Space). ChromaDB sigue siendo local (in-memory o persistido en el Space).

El vault se incluye como parte del despliegue (un snapshot estático). Las funciones de crear/editar notas quedan deshabilitadas en producción (el Space no tiene disco persistente fiable).

**Ficheros a crear/modificar:**
- `Dockerfile` (o `requirements.txt` adaptado para HF Spaces)
- `README.md` del Space (formato HF)
- Configuración de secrets en HF

---

## Tareas

### T8.1 — Crear cuenta en Groq y obtener API key

1. Ir a https://console.groq.com
2. Crear cuenta (gratis).
3. Generar una API key.
4. Guardarla en `.env` local como `GROQ_API_KEY=gsk_...`.
5. Verificar que funciona:

```bash
# Cambiar en .env
USE_LOCAL=false
GROQ_API_KEY=gsk_tu_key

# Ejecutar
python scripts/test_ollama.py   # (renombrar o crear un test_groq.py equivalente)
```

### T8.2 — Verificar el sistema completo con Groq

1. Cambiar `USE_LOCAL=false` en `.env`.
2. Ejecutar `python scripts/ingest.py` — debe funcionar con HuggingFace embeddings.
3. Ejecutar `chainlit run app.py` — debe responder preguntas usando Groq como LLM.
4. Verificar tiempos de respuesta (Groq es significativamente más rápido que Ollama local).

### T8.3 — Preparar el repositorio para Hugging Face Spaces

HF Spaces con Chainlit usa Docker o un SDK estándar. Opción recomendada: SDK Docker.

Crear `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copiar requirements y instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY src/ src/
COPY app.py .
COPY chainlit.md .
COPY .chainlit/ .chainlit/

# Copiar el vault (snapshot estático para la demo)
COPY vault/ vault/

# Copiar ChromaDB pre-indexado (opcional, evita re-indexar en cada reinicio)
COPY data/chroma_db/ data/chroma_db/

# Puerto de Chainlit
EXPOSE 8000

# Variables de entorno por defecto (sobreescritas por secrets de HF)
ENV USE_LOCAL=false
ENV VAULT_PATH=/app/vault
ENV CHROMA_PERSIST_DIR=/app/data/chroma_db
ENV CHUNKER_STRATEGY=fixed

CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
```

### T8.4 — Crear README.md para HF Spaces

HF Spaces lee el header YAML del README:

```markdown
---
title: Obsidian RAG Agent
emoji: 🧠
colorFrom: purple
colorTo: teal
sdk: docker
app_port: 8000
---

# Obsidian RAG Agent

Sistema RAG conversacional que permite interactuar con un vault de Obsidian.

## Tecnologías
- LangChain + Groq (Llama 3.2)
- ChromaDB (vector store)
- Chainlit (interfaz de chat)

## Uso
Escribe una pregunta sobre el contenido del vault y el agente buscará la información relevante.
```

### T8.5 — Subir a Hugging Face Spaces

1. Crear cuenta en https://huggingface.co (gratis).
2. Crear un nuevo Space: `Settings > New Space > Docker`.
3. Configurar secrets en el Space:
   - `GROQ_API_KEY`: tu API key de Groq
4. Subir el código:

```bash
# Instalar CLI de HF
pip install huggingface_hub

# Login
huggingface-cli login

# Clonar el Space (o crear desde la web)
git clone https://huggingface.co/spaces/tu-usuario/obsidian-rag
cd obsidian-rag

# Copiar todos los ficheros del proyecto
# Hacer commit y push
git add .
git commit -m "Deploy Obsidian RAG Agent"
git push
```

5. Esperar a que el Space se construya (puede tardar 5-10 minutos la primera vez).
6. Verificar en `https://tu-usuario-obsidian-rag.hf.space`.

### T8.6 — Deshabilitar funciones de escritura en producción

En producción (HF Spaces), las herramientas de `create_note` y `edit_note` deben estar deshabilitadas o devolver un mensaje explicativo, porque el filesystem del Space no es persistente.

Opción: añadir variable de entorno `READONLY_MODE=true` y condicionar en `create_agent`:

```python
if os.getenv("READONLY_MODE", "false") == "true":
    tools = [search_tool]  # solo búsqueda
else:
    tools = [search_tool, create_tool, edit_tool]
```

---

## Consideraciones

- **Vault estático**: el vault se copia al Docker image como snapshot. Cambios en el vault original no se reflejan automáticamente en la demo.
- **ChromaDB pre-indexado**: para evitar que el Space tenga que indexar el vault en cada reinicio, copiar `data/chroma_db/` ya indexado al Docker image. Alternativa: indexar en el startup con un script.
- **Costes**: Groq tier gratuito tiene 30 req/min. Para una demo con pocas personas, es más que suficiente.
- **Embeddings**: HuggingFace embeddings corren localmente en el Space (sin API externa), así que no hay coste adicional.

---

## Criterio de completado

- [ ] El sistema funciona completamente con `USE_LOCAL=false` (Groq)
- [ ] Dockerfile creado y probado localmente (`docker build && docker run`)
- [ ] Space publicado en HuggingFace y accesible por URL
- [ ] El chat responde preguntas sobre el vault desplegado
- [ ] Las herramientas de escritura están deshabilitadas en producción
