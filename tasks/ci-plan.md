# Plan de implementación — CI/CD (GitHub Actions)

## Contexto

Este plan integra el pipeline de CI (lint, tests unitarios, arquitectura)
con el desarrollo del proyecto descrito en `tasks/`. No es una fase
numerada porque es transversal — se activa progresivamente a medida que
existe código que comprobar.

**Ficheros ya creados** (raíz del repo):
- `.github/workflows/lint.yml`
- `.github/workflows/test-unit.yml`
- `.github/workflows/architecture-check.yml`
- `scripts/check_architecture.py`
- `pyproject.toml`
- `requirements.txt`
- `requirements-dev.txt`

---

## Paso 1 — Integrar en la Fase 0 (entorno)

Al ejecutar `fase-0-entorno.md`, usar los `requirements.txt` /
`requirements-dev.txt` ya creados (no generar otros nuevos — estos ya
incluyen `ruff` para el lint).

```bash
pip install -r requirements-dev.txt
```

Verificación local de que el entorno coincide con el CI:

```bash
black --check src tests scripts evaluation
isort --check-only src tests scripts evaluation
ruff check src tests scripts evaluation
python scripts/check_architecture.py
```

En este punto, `src/` solo tiene `__init__.py` y los ficheros del dominio
(`models.py`, `ports.py`), así que estos comandos deberían pasar sin
problema — es la línea base.

**Commit de referencia**: `chore: setup CI pipeline (lint, tests, architecture check)`

---

## Paso 2 — Activar `architecture-check` desde la Fase 1

A partir de `fase-1-dominio.md`, cada `git push` ya dispara
`architecture-check.yml`. Como `domain/` no debe importar nada de `src.*`
ni de terceros, este es el primer workflow que tiene contenido real que
comprobar.

Acción concreta: después de cada fase (1 a 9), antes de hacer push,
ejecutar localmente:

```bash
python scripts/check_architecture.py
```

Si falla, **no hacer push** — corregir primero. Si el agente (OpenCode/
Claude Code) generó el código que falla, esto es candidato directo para
una entrada en `docs/error-log.md` (ver skill `error-log`).

---

## Paso 3 — Activar `test-unit` desde la Fase 1

`fase-1-dominio.md` ya incluye `tests/unit/test_models.py`. A partir de
aquí, `test-unit.yml` empieza a ejecutar tests reales.

**Importante — el umbral de cobertura**: `test-unit.yml` tiene
`--cov-fail-under=80`. En las primeras fases (1-2), la cobertura real de
`src/` será baja porque hay muchos ficheros `__init__.py` vacíos y módulos
todavía sin implementar contarán como 0% si `--cov=src` los incluye.

Dos opciones, elegir una:

- **Opción A (recomendada)**: bajar el umbral a `--cov-fail-under=0`
  durante las fases 1-3, y subirlo progresivamente (`40` tras fase 3,
  `60` tras fase 5, `80` tras fase 7) editando `test-unit.yml`.
- **Opción B**: dejar `--cov-fail-under=80` desde el principio, pero
  añadir `# pragma: no cover` a los módulos aún no implementados — más
  trabajo de mantenimiento, no recomendado para un proyecto que avanza
  fase a fase.

Acción concreta: al terminar la Fase 1, editar `test-unit.yml` y poner
`--cov-fail-under=0`. Documentar en un comentario del propio YAML el plan
de incremento:

```yaml
# Umbral de cobertura — incrementar según el plan en tasks/ci-plan.md:
#   Fase 1-3: 0   | Fase 4-5: 40   | Fase 6-7: 60   | Fase 8-9: 80
--cov-fail-under=0
```

---

## Paso 4 — Activar `lint` desde la Fase 1

`lint.yml` no depende de cobertura, así que puede estar activo desde el
primer commit con código en `src/`. Si OpenCode/Claude Code no respeta
`black`/`isort` automáticamente, ejecutar localmente antes de cada commit:

```bash
black src tests scripts evaluation
isort src tests scripts evaluation
ruff check --fix src tests scripts evaluation
```

Recomendación: añadir esto como un script de conveniencia
`scripts/format.sh`:

```bash
#!/usr/bin/env bash
set -e
black src tests scripts evaluation
isort src tests scripts evaluation
ruff check --fix src tests scripts evaluation
echo "Formatting complete."
```

---

## Paso 5 — Pre-commit hook (opcional pero recomendado)

Para evitar pushes que fallen el CI por algo tan simple como formato,
instalar un hook de Git que ejecute `scripts/format.sh` +
`check_architecture.py` antes de cada commit.

```bash
# .git/hooks/pre-commit
#!/usr/bin/env bash
set -e
./scripts/format.sh
python scripts/check_architecture.py
```

```bash
chmod +x .git/hooks/pre-commit
```

No versionar `.git/hooks/` (no se puede). Documentar este paso en el
`README.md` del proyecto como parte del setup de Fase 0, para que sea
reproducible si se clona el repo de nuevo.

---

## Paso 6 — Subir umbral de cobertura (Fase 4 y Fase 7)

| Tras completar | `--cov-fail-under` |
|---|---|
| Fase 3 (vector store + LLM adapters) | `40` |
| Fase 5 (agente) | `60` |
| Fase 7 (evaluación) | `80` |

Editar `test-unit.yml` en cada hito. Si el CI falla tras subir el umbral,
es señal de que faltan tests de esa fase — revisar el criterio de
completado del fichero de fase correspondiente antes de continuar.

---

## Paso 7 — Tests de integración (opcional, fuera del CI estándar)

`tests/integration/` requiere Ollama corriendo — GitHub Actions no tiene
Ollama por defecto y montar un runner con el modelo descargado es lento
(varios GB) y consume minutos de CI gratuitos.

**Recomendación para el TFM**: no automatizar esto en GitHub Actions.
Documentar en el README que los tests de integración se ejecutan
manualmente en local:

```bash
pytest tests/integration/ -v -m integration
```

Si en algún momento se quiere automatizar, la opción más ligera es un
workflow `workflow_dispatch` (manual, solo cuando se lance a mano) que
instale Ollama y descargue `llama3.2:1b` (la versión más pequeña) — pero
esto es trabajo adicional no crítico para el TFM. Mencionarlo como
"trabajo futuro" en la memoria si no se implementa.

---

## Paso 8 — `build-docker` (Fase 8, despliegue)

Cuando se llegue a `fase-8-despliegue.md` y exista el `Dockerfile`, añadir:

```yaml
# .github/workflows/build-docker.yml
name: Build Docker Image

on:
  pull_request:
    branches: ["main"]
    paths:
      - "Dockerfile"
      - "src/**"
      - "app.py"
      - "requirements.txt"

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t obsidian-rag:ci .
```

Esto verifica que la imagen de producción construye correctamente antes de
mergear a `main`, sin desplegar nada todavía. No crear este fichero hasta
llegar a la Fase 8 — no tiene sentido antes de que exista el `Dockerfile`.

---

## Paso 9 — `deploy-hf-spaces` (Fase 8, despliegue) — opcional

Automatizar el push a Hugging Face Spaces al mergear a `main` es posible
pero añade complejidad (gestión de credenciales `HF_TOKEN` como secret de
GitHub, sincronización de `data/chroma_db/` pre-indexado). Para el alcance
del TFM, **se recomienda el despliegue manual** descrito en
`fase-8-despliegue.md` (T8.5), y dejar la automatización como mejora futura
documentada en la memoria.

Si se decide automatizar más adelante, el esqueleto sería:

```yaml
# .github/workflows/deploy-hf-spaces.yml
name: Deploy to Hugging Face Spaces

on:
  push:
    branches: ["main"]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Push to HF Spaces
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          git remote add space https://user:${HF_TOKEN}@huggingface.co/spaces/tu-usuario/obsidian-rag
          git push space main
```

---

## Resumen — qué hacer y cuándo

| Cuándo | Acción |
|---|---|
| Fase 0 | Instalar `requirements-dev.txt`, verificar comandos de lint/arquitectura en local, primer commit con CI |
| Fase 0 | Crear `scripts/format.sh` y el pre-commit hook |
| Fase 1 | `architecture-check` y `test-unit` empiezan a tener contenido real; poner `--cov-fail-under=0` |
| Fase 3 | Subir `--cov-fail-under` a `40` |
| Fase 5 | Subir `--cov-fail-under` a `60` |
| Fase 7 | Subir `--cov-fail-under` a `80` |
| Fase 8 | Añadir `build-docker.yml`; valorar `deploy-hf-spaces.yml` (opcional) |
| Continuo | Si `architecture-check` falla por código generado por el agente IA → entrada en `docs/error-log.md` |

---

## Criterio de completado

- [ ] `requirements.txt` / `requirements-dev.txt` / `pyproject.toml` en la raíz
- [ ] Los 3 workflows pasan en verde con el código de Fase 1
- [ ] `scripts/format.sh` creado y ejecutable
- [ ] Pre-commit hook configurado en local (no versionado, documentado en README)
- [ ] Umbral de cobertura actualizado según el calendario de la tabla resumen
- [ ] `build-docker.yml` añadido al llegar a la Fase 8
