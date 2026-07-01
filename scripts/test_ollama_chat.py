"""Test LangChain + Ollama."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.adapters.llm import OllamaChat


def main() -> None:
    chat = OllamaChat(model="qwen3.6:35b-a3b", base_url="http://localhost:11434")

    questions = [
        "¿Qué es el RAG en procesamiento de lenguaje natural?",
        "Resume en una frase tus respuestas anteriores.",
    ]

    print(f"Modelo: {chat.model}\n")
    for q in questions:
        print("Pregunta:", q)
        response = chat.send(q)
        print("Respuesta:", response[:500])
        print("-" * 60)


if __name__ == "__main__":
    main()
