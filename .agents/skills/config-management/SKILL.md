---
name: config-management
description: Use when reading environment variables, adding new .env settings, or wiring up src/infrastructure/config.py in the Obsidian RAG project. Defines the single-source-of-truth rule for os.getenv(), fail-fast validation with ConfigError, .env.example contract, lazy optional imports, and safe boolean/int parsing. Trigger for any config, settings, or factory-related change.
---

# Skill: Configuration & Secrets Management

---

## Single source of truth

All environment variables are read in **one place only**: `src/infrastructure/config.py`. No other module calls `os.getenv()` or `os.environ`.

```python
# src/infrastructure/config.py
import os
from dotenv import load_dotenv

load_dotenv()
```

If a new adapter needs a configuration value, add a getter here and pass the value into the adapter's constructor — never let the adapter read the environment itself.

---

## Fail fast on startup

Required configuration must be validated **before** any adapter is instantiated, with a clear error message naming the missing variable.

```python
# src/infrastructure/config.py

class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""

def _require(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise ConfigError(
            f"Missing required environment variable: '{var_name}'. "
            f"Check your .env file against .env.example."
        )
    return value

def get_vault_path() -> str:
    path = _require("VAULT_PATH")
    if not os.path.isdir(path):
        raise ConfigError(f"VAULT_PATH does not exist: '{path}'")
    return path
```

Rules:
- Required variables (no sensible default): `VAULT_PATH`, and `GROQ_API_KEY` when `USE_LOCAL=false`.
- Variables with sensible defaults (model names, ports, chunk sizes) use `os.getenv("VAR", "default")` — no validation needed.
- `ConfigError` is raised at factory-call time, not buried inside an adapter after several seconds of work.

---

## `.env.example` is the contract

Every variable used anywhere in `config.py` must appear in `.env.example` with a comment explaining it. If you add a new `os.getenv()` call, add the corresponding line to `.env.example` in the same change.

```env
# Required: absolute path to the Obsidian vault
VAULT_PATH=/ruta/absoluta/a/tu/vault

# Required only if USE_LOCAL=false
GROQ_API_KEY=
```

Never commit `.env` (already in `.gitignore`). Never put real secrets in `.env.example`.

---

## Conditional / optional dependencies

When `USE_LOCAL` toggles between Ollama and Groq, imports of the non-active provider must be **lazy** (inside the function), so the project still runs if an optional package isn't installed:

```python
def get_llm() -> ConversationalLLM:
    if os.getenv("USE_LOCAL", "true").lower() == "true":
        from src.adapters.llm.ollama_adapter import OllamaLLMAdapter
        return OllamaLLMAdapter(model=os.getenv("OLLAMA_MODEL", "llama3.2"))
    else:
        from src.adapters.llm.groq_adapter import GroqLLMAdapter
        return GroqLLMAdapter(api_key=_require("GROQ_API_KEY"))
```

---

## Boolean and numeric env vars

Always parse explicitly — never rely on truthiness of strings (`"false"` is truthy in Python).

```python
def _bool_env(var_name: str, default: bool) -> bool:
    value = os.getenv(var_name)
    if value is None:
        return default
    return value.strip().lower() in ("true", "1", "yes")

def _int_env(var_name: str, default: int) -> int:
    value = os.getenv(var_name)
    return int(value) if value else default
```

Use these helpers for `USE_LOCAL`, `READONLY_MODE`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, etc.

---

## Logging configuration at startup

Log the resolved (non-secret) configuration once at startup, so debugging a deployed instance doesn't require guessing what env vars were picked up:

```python
logger.info(
    "Config loaded: USE_LOCAL=%s, CHUNKER_STRATEGY=%s, VAULT_PATH=%s",
    use_local, chunker_strategy, vault_path,
)
```

Never log secret values (`GROQ_API_KEY`, etc.) — log only whether they are set:

```python
logger.info("GROQ_API_KEY configured: %s", bool(os.getenv("GROQ_API_KEY")))
```

---

## Quick checklist

- [ ] New env var added to `.env.example` with a comment
- [ ] Required vars validated via `_require()` at factory level, not inside adapters
- [ ] Booleans/ints parsed with helpers, not raw string checks
- [ ] No `os.getenv()` outside `src/infrastructure/config.py`
- [ ] No secret values written to logs
