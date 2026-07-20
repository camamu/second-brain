FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descarga el modelo de embeddings para cachear esta capa de Docker
# (evita re-descargarlo durante la indexación del vault)
RUN python -c "\
from langchain_huggingface import HuggingFaceEmbeddings; \
HuggingFaceEmbeddings(\
    model_name='nomic-ai/nomic-embed-text-v1', \
    model_kwargs={'trust_remote_code': True}\
)"

COPY src/ src/
COPY scripts/ scripts/
COPY app.py .
COPY chainlit.md .
COPY .chainlit/ .chainlit/
COPY vault/ vault/
COPY pyproject.toml .

ENV USE_LOCAL=false
ENV VAULT_PATH=/app/vault
ENV CHROMA_PERSIST_DIR=/app/data/chroma_db
ENV CHUNKER_STRATEGY=fixed
ENV READONLY_MODE=true

EXPOSE 8000

CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]

# ---- valida que la ingesta funciona de verdad, con una sola estrategia ----
# Target usado por build-docker.yml en pull_request: confirma que
# scripts/ingest.py corre en la imagen sin pagar las 3 estrategias en
# cada PR (GROQ_API_KEY no se necesita aquí, solo usa embeddings HuggingFace).
FROM base AS ci
RUN python scripts/ingest.py --strategy fixed

# ---- imagen completa con las 3 estrategias (release / HF Spaces) ----
FROM ci AS indexed
RUN python scripts/ingest.py --strategy markdown \
    && python scripts/ingest.py --strategy backlink
