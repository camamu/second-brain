"""Punto de entrada Chainlit — delega en src/app."""
# chainlit run app.py  ↔  chainlit run src/app/__init__.py
from src.app import *  # noqa: F401, F403
