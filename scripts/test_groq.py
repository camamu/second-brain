"""Smoke test de conectividad con Groq + HuggingFace embeddings.

Ejecutar con USE_LOCAL=false configurado en .env:
    python scripts/test_groq.py
"""

import logging
import time

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)


def main() -> None:
    from src.infrastructure.config import get_embedder, get_llm

    print("=== Test HuggingFace Embeddings ===")
    t0 = time.perf_counter()
    embedder = get_embedder()
    vector = embedder.embed("¿Qué es la recuperación aumentada con generación?")
    elapsed = time.perf_counter() - t0
    print(f"  Dimensión del vector: {len(vector)}")
    print(f"  Primeros 5 valores: {[round(v, 4) for v in vector[:5]]}")
    print(f"  Tiempo: {elapsed:.2f}s")

    print("\n=== Test Groq LLM ===")
    t0 = time.perf_counter()
    llm_adapter = get_llm()
    llm = llm_adapter.as_langchain()  # type: ignore[attr-defined]
    response = llm.invoke("Di 'Hola, sistema RAG operativo' y nada más.")
    elapsed = time.perf_counter() - t0
    print(f"  Respuesta: {response.content}")
    print(f"  Tiempo: {elapsed:.2f}s")

    print("\n✓ Groq + HuggingFace listos para despliegue.")


if __name__ == "__main__":
    main()
