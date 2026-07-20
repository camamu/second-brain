# Plan de Implementación — Reinterpretación del diseño "Second Brain Chat" en la UI Chainlit

> Plan guardado en git. Los planes de fases anteriores se conservan en el historial: `git log --oneline`.

## Adenda: logo real de marca (`Second Brain Logo.dc.html`)

Se importó un segundo fichero del mismo proyecto de diseño con el icono de marca
definitivo: una silueta de cerebro con "surcos" de circuito, en gradiente
rosa/magenta (`#ec4899`→`#f472b6` sobre fondo oscuro, `#db2777`→`#ec4899` sobre
fondo claro). Sustituye el placeholder de texto "sb" usado inicialmente en
`public/logo_dark.svg` / `public/logo_light.svg` / `public/favicon.svg`.

**Decisión confirmada con el usuario**: el acento de la UI (`--primary`/`--ring`/
`--accent` en `public/theme.json`) se mantiene en teal (`#14b8a6`), sin
recalcularlo al rosa/magenta del logo. El logo es una pieza de marca
independiente; el teal ya implementado no se toca.

Verificado sirviendo la app (`chainlit run app.py` + `curl /logo?theme=dark`,
`/logo?theme=light`, `/favicon` → 200, `image/svg+xml`).

## Contexto

Se importó un diseño desde claude.ai/design (`Second Brain Chat.dc.html`, proyecto
"Rediseño chatbot RAG") vía el MCP `claude_design`. Es un prototipo interactivo
(runtime propio con bindings `{{ }}` sobre React) que sirve como referencia visual,
no como código ejecutable. Define una identidad de marca "second-brain" (minúsculas,
logo "sb", acento teal `#14b8a6`, dos temas claro/oscuro) y patrones de interacción:
sidebar con historial de conversaciones, topbar con badge y selector de temas, chips
de "tool usado" expandibles, citas de fuentes en pill-chips que abren un panel
lateral, sugerencias de prompt antes del primer mensaje, y composer redondeado.

**Decisiones de alcance ya acordadas con el usuario:**
1. **Reinterpretación nativa Chainlit** (no fork del frontend, no frontend custom
   completo) — se usa el sistema de theming/CSS/config de Chainlit 2.x tal cual.
2. **Variante A** de citas/chips (pill redondeada) — es la que más se parece al
   comportamiento nativo de Chainlit al adjuntar `cl.Text(display="side")`.

**Corrección importante detectada durante la planificación:** el `.chainlit/config.toml`
actual fue generado por Chainlit 1.3.2. El entorno tiene instalado **Chainlit 2.11.1**
(verificado con `.venv/bin/python -c "import chainlit; print(chainlit.__version__)"`),
donde el modelo `UISettings` ya **no tiene** los campos `[UI.theme]` /
`[UI.theme.light]` / `[UI.theme.dark]` ni `default_collapse_content` — Pydantic los
ignora en silencio (no falla, pero tampoco hace nada). El theming de colores en 2.x
vive en un fichero nuevo **`public/theme.json`** (confirmado leyendo
`chainlit/server.py::get_html_template`, líneas ~367-418: si existe, inyecta
`window.theme = {...}` con variables CSS estilo shadcn/Tailwind, ej. `--background`,
`--primary`, `--card`, `--border`, en tripletes HSL sin `hsl()` ni comas).

**Gaps documentados, no implementados en esta fase** (por decisión de alcance):
- Sidebar de "Recientes" con historial real de conversaciones (requiere data layer + auth).
- Badge custom "RAG · Obsidian" en el topbar (no hay slot nativo para HTML arbitrario ahí).
- Selector de variantes A/B/C en vivo (solo se fija la variante A).

## Mapa de cambios

| Fichero | Acción | Qué cambia |
|---|---|---|
| `.chainlit/config.toml` | Modificar | `name="second-brain"`, `description`, `default_theme="dark"` (plano), `custom_css="/public/style.css"`; eliminar bloques `[UI.theme]`/`[UI.theme.light]`/`[UI.theme.dark]` y `default_collapse_content` (sin efecto real en 2.11.1); bump `generated_by = "2.11.1"` |
| `public/theme.json` | Crear | Variables CSS (HSL) de temas dark/light + acento teal + `custom_fonts` |
| `public/style.css` | Crear | Reglas puntuales ancladas en `data-step-type`/`id` reales del bundle (burbuja usuario, composer, panel de citas, paso de tool) |
| `public/logo_dark.svg`, `public/logo_light.svg` | Crear | Logo mark "sb" con gradiente teal |
| `public/favicon.svg` | Crear | Favicon derivado del logo |
| `chainlit.md` | Modificar | Rebranding "Obsidian RAG Agent" → "second-brain" |
| `src/agent/tools.py` | Modificar | `create_search_tool(..., last_results: list[SearchResult] \| None = None)` |
| `src/agent/agent.py` | Modificar | `create_agent(..., last_results: list[SearchResult] \| None = None)`, reenviado a la tool |
| `src/app/__init__.py` | Modificar | `@cl.set_starters`; crear `last_search_results` en `on_chat_start`; helper `_build_citation_elements`; adjuntar `elements` al `cl.Message` final en `on_message` |
| `tests/unit/test_tools.py` | Modificar | 3 casos nuevos reutilizando `_make_search_result` ya existente |
| `tests/unit/test_agent.py` | Modificar | 1 caso nuevo verificando el reenvío de `last_results` |

## Análisis previo: captura de `SearchResult` reales para citas nativas

**Aspecto crítico**: `create_search_tool` debe seguir devolviendo un string plano
para el LLM (contrato actual, usado en el prompt ReAct), pero `on_message` necesita
los objetos `SearchResult` reales (`note_id`, `score`, `content`) para adjuntarlos
como `cl.Text(display="side")`. Esos objetos solo existen dentro del closure
`_search` de `tools.py` y se pierden al formatear a string.

**Opciones consideradas**:
1. **Lista mutable inyectada por closure** — `create_search_tool` recibe
   `last_results: list[SearchResult] | None`; `_search` la vacía y rellena en cada
   llamada. `on_chat_start` la crea y la pasa a `create_agent`, guardándola también
   en `cl.user_session`; `on_message` la lee tras `ainvoke()`. Conserva los objetos
   tipados originales sin reparsear nada.
2. **Parsear `intermediate_steps`** (`AgentExecutor(return_intermediate_steps=True)`)
   con regex sobre el string ya formateado — reconstruye con regex un dato que ya
   teníamos tipado; frágil si cambia el formato (que también usa el LLM).
3. **Callback handler custom** (`on_tool_end`) — mismo problema: solo recibe el
   string, no los objetos.

**Decisión**: Opción 1. Es la única que preserva los `SearchResult` sin reparsear;
el coste es un parámetro opcional en dos factories y una lista de estado por sesión.

**Riesgo aceptado**: si el agente llamara a `search_vault` más de una vez en el mismo
turno, solo quedarían los resultados de la última llamada (se vacía en cada
invocación). El prompt ReAct ya prohíbe explícitamente repetir la misma búsqueda
("NUNCA repitas la misma consulta..."), así que es un caso ya mitigado por diseño.
Si en el futuro se permiten varias búsquedas por turno, cambiar a acumulador
deduplicado por `note_id`.

### Especificación

`src/agent/tools.py` — `create_search_tool`:
```python
def create_search_tool(
    search_use_case: SearchNotes,
    strategy: ChunkStrategy,
    last_results: list[SearchResult] | None = None,
) -> Tool:
    def _search(query: str) -> str:
        query = _unwrap_string_input(query)
        try:
            results = search_use_case.execute_text(query, strategy=strategy)
            if last_results is not None:
                last_results.clear()
                last_results.extend(results)
            ...  # resto sin cambios (formato de string al LLM intacto)
```

`src/agent/agent.py` — `create_agent` añade parámetro `last_results` y lo reenvía a
`create_search_tool(search_use_case, strategy, last_results)`.

`src/app/__init__.py`:
```python
# on_chat_start, tras montar search_uc:
last_search_results: list[SearchResult] = []
agent = create_agent(..., last_results=last_search_results)
cl.user_session.set("agent", agent)
cl.user_session.set("last_search_results", last_search_results)

# on_message, antes de ainvoke:
last_results = cl.user_session.get("last_search_results")
if last_results is not None:
    last_results.clear()
response = await agent.ainvoke(...)
elements = _build_citation_elements(last_results) if last_results else []
await cl.Message(content=response["output"], elements=elements).send()

def _build_citation_elements(results: list[SearchResult]) -> list[cl.Text]:
    """Convierte SearchResult reales en elementos de fuente nativos de Chainlit."""
    seen: set[str] = set()
    elements: list[cl.Text] = []
    for r in results:
        if r.note_id in seen:
            continue
        seen.add(r.note_id)
        elements.append(cl.Text(
            name=r.note_id,
            content=f"**Ruta:** `{r.note_id}`\n\n**Score:** {r.score:.2f}\n\n---\n\n{r.content}",
            display="side",
        ))
    return elements
```

Importar `SearchResult` desde `src.domain.models` en `src/app/__init__.py` es
coherente con el precedente ya existente (`ChunkStrategy`, `ObsidianRagError` ya se
importan ahí desde dominio) y respeta la regla hexagonal: el dominio es el centro,
capas externas pueden depender de él libremente.

## Análisis previo: alcance del CSS custom vs. riesgo entre versiones de Chainlit

**Aspecto crítico**: Chainlit 2.11.1 no expone `data-testid` (0 coincidencias en el
bundle compilado), pero sí expone `data-step-type="user_message"|"assistant_message"|"tool"`
y varios `id` fijos (`#chat-input`, `#chat-submit`, `#message-composer`, `#header`,
`#theme-toggle`, `#side-view-content`, `#starters`, `#welcome-screen`) — verificados
inspeccionando el bundle JS instalado. Ninguno es API pública documentada.

**Opciones consideradas**:
1. Solo `theme.json` (colores/`--radius` global) — cero selectores frágiles, pero no
   permite igualar detalles finos (radio asimétrico de burbujas, chip de tool).
2. `theme.json` + `public/style.css` con un número reducido de selectores anclados en
   `data-step-type`/`id` (más estables que clases Tailwind hasheadas, pero no oficiales).
3. Fork del frontend (`custom_build`) — descartado explícitamente por el usuario.

**Decisión**: Opción 2, con el CSS deliberadamente pequeño (4-5 reglas) para
minimizar superficie de rotura.

**Riesgo aceptado**: un `pip install -U chainlit` puede renombrar estos hooks sin
lanzar error (fallo silencioso, solo visual). Mitigación: comentario
`/* verificado con chainlit==2.11.1 */` en cada bloque de `style.css`; verificación
100% manual (no hay test automatizado posible para CSS/clases generadas).

## `public/theme.json` — contenido (HSL calculado exactamente, no aproximado)

```json
{
  "custom_fonts": ["https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"],
  "variables": {
    "dark": {
      "--background": "240 14.3% 5.5%",
      "--foreground": "240 10.0% 96.1%",
      "--card": "240 8.8% 11.2%",
      "--card-foreground": "240 10.0% 96.1%",
      "--popover": "240 8.8% 13.3%",
      "--popover-foreground": "240 10.0% 96.1%",
      "--primary": "173.4 80.4% 40.0%",
      "--primary-foreground": "0 0% 100%",
      "--secondary": "240 7.3% 16.1%",
      "--secondary-foreground": "240 10.0% 96.1%",
      "--muted": "240 8.8% 13.3%",
      "--muted-foreground": "240 10.0% 68%",
      "--accent": "173.4 40% 20%",
      "--accent-foreground": "173.4 80.4% 70%",
      "--border": "240 8% 18%",
      "--input": "240 8.0% 9.8%",
      "--ring": "173.4 80.4% 40.0%",
      "--sidebar-background": "240 9.5% 8.2%",
      "--sidebar-foreground": "240 10.0% 96.1%",
      "--sidebar-primary": "173.4 80.4% 40.0%",
      "--sidebar-accent": "240 8.8% 13.3%",
      "--sidebar-border": "240 8% 18%",
      "--font-sans": "Inter, system-ui, sans-serif",
      "--radius": "0.75rem"
    },
    "light": {
      "--background": "40 15.8% 96.3%",
      "--foreground": "240 5.9% 10.0%",
      "--card": "0 0% 100%",
      "--card-foreground": "240 5.9% 10.0%",
      "--popover": "40 11.1% 94.7%",
      "--popover-foreground": "240 5.9% 10.0%",
      "--primary": "173.4 80.4% 40.0%",
      "--primary-foreground": "0 0% 100%",
      "--secondary": "30 10.5% 92.5%",
      "--secondary-foreground": "240 5.9% 10.0%",
      "--muted": "40 11.1% 94.7%",
      "--muted-foreground": "240 3% 44%",
      "--accent": "173.4 60% 92%",
      "--accent-foreground": "173.4 80.4% 25%",
      "--border": "0 0% 88%",
      "--input": "0 0% 100%",
      "--ring": "173.4 80.4% 40.0%",
      "--sidebar-background": "0 0% 100%",
      "--sidebar-foreground": "240 5.9% 10.0%",
      "--sidebar-primary": "173.4 80.4% 40.0%",
      "--sidebar-accent": "40 11.1% 94.7%",
      "--sidebar-border": "0 0% 88%",
      "--font-sans": "Inter, system-ui, sans-serif",
      "--radius": "0.75rem"
    }
  }
}
```

Nota: las variables HSL de shadcn no soportan directamente el canal alpha de
`rgba(255,255,255,0.08)` del diseño original; `--border`/`--accent` de arriba son
aproximaciones opacas de bajo contraste. Afinar visualmente tras el primer
`chainlit run` si se ve demasiado plano — ajustar solo con `rgba(...)` puntual en
`style.css`, no forzando el sistema de variables globales.

## `.chainlit/config.toml` — valores finales

```toml
[UI]
name = "second-brain"
description = "Tu segundo cerebro conversacional sobre Obsidian"
default_theme = "dark"
cot = "full"
custom_css = "/public/style.css"

[meta]
generated_by = "2.11.1"
```

Eliminar `default_collapse_content`, `[UI.theme]`, `[UI.theme.light]`,
`[UI.theme.dark]` (sin efecto real en 2.11.1). Mantener `[project]`/`[features]`
tal cual, no afectados por esta tarea.

## `public/style.css` — estructura

```css
/* second-brain custom theme — verificado con chainlit==2.11.1
   Selectores anclados en data-step-type/id reales del bundle compilado.
   Revisar tras cualquier `pip install -U chainlit`. */

[data-step-type="user_message"] .step {
  border-radius: 16px 16px 3px 16px;
}

[data-step-type="assistant_message"] {
  font-size: 15.5px;
  line-height: 1.6;
  animation: sb-fade-in 0.25s ease-out;
}

[data-step-type="tool"] {
  border-radius: 10px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--card));
}

#message-composer {
  border-radius: 18px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--input));
}
#chat-submit {
  border-radius: 9999px;
}

#side-view-content {
  animation: sb-slide-in 0.2s ease-out;
}

@keyframes sb-fade-in {
  from { opacity: 0; transform: translateY(2px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes sb-slide-in {
  from { transform: translateX(12px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
```

Punto de partida deliberadamente pequeño; afinar radios/bordes tras inspección
manual del DOM real en el primer `chainlit run`.

## Branding y logo

- `public/logo_dark.svg` / `public/logo_light.svg`: cuadrado 30×30, `rx="9"`,
  gradiente 135° de `#14b8a6` a `#14b8a6` (stop-opacity 0.6 en el segundo stop),
  texto "sb" centrado, blanco, monospace bold. Misma composición en ambos temas.
- `public/favicon.svg`: versión simplificada del mismo mark.
- `chainlit.md`: título `# second-brain`, mantener la lista de ejemplos
  Buscar/Crear/Editar ya existente, solo actualizar el nombre de marca.

## Starters

Añadir en `src/app/__init__.py`, junto a los demás handlers, antes de `on_chat_start`:
```python
@cl.set_starters
async def set_starters() -> list[cl.Starter]:
    return [
        cl.Starter(
            label="Resume mis notas de esta semana",
            message="Resume las notas que he creado o editado esta semana.",
        ),
        cl.Starter(
            label="¿Qué tareas tengo pendientes?",
            message="¿Qué tareas pendientes tengo apuntadas en mis notas?",
        ),
        cl.Starter(
            label="Busca menciones de un tema",
            message="Busca menciones de 'arquitectura hexagonal' en mis notas.",
        ),
    ]
```

## Tests

Todo lo de `tools.py`/`agent.py` es testeable con pytest (patrón AAA + `spec=` ya
usado). El theming (`config.toml`/`theme.json`/`style.css`) **no es testeable con
pytest** — verificación manual únicamente, tal como indica `CLAUDE.md` para cambios
de UI. Reutilizar el helper `_make_search_result` ya existente en
`tests/unit/test_tools.py` (no duplicarlo).

`tests/unit/test_tools.py` — nuevos casos en `TestSearchTool`:
```python
def test_search_tool_populates_last_results_with_real_search_results(self):
    search_uc = MagicMock(spec=SearchNotes)
    results = [_make_search_result(1), _make_search_result(2)]
    search_uc.execute_text.return_value = results
    last_results: list[SearchResult] = []
    tool = create_search_tool(search_uc, ChunkStrategy.FIXED_SIZE, last_results)

    tool.func("query")

    assert last_results == results

def test_search_tool_clears_last_results_before_new_search(self):
    search_uc = MagicMock(spec=SearchNotes)
    search_uc.execute_text.return_value = [_make_search_result(1)]
    last_results: list[SearchResult] = [_make_search_result(99)]
    tool = create_search_tool(search_uc, ChunkStrategy.FIXED_SIZE, last_results)

    tool.func("query")

    assert len(last_results) == 1
    assert last_results[0].note_id == "notas/nota-1.md"

def test_search_tool_works_without_last_results_param(self):
    search_uc = MagicMock(spec=SearchNotes)
    search_uc.execute_text.return_value = []
    tool = create_search_tool(search_uc, ChunkStrategy.FIXED_SIZE)

    result = tool.func("query")

    assert "No se encontraron" in result
```

`tests/unit/test_agent.py` — nuevo caso en `TestCreateAgent`:
```python
def test_create_agent_forwards_last_results_to_search_tool(self):
    search_uc = MagicMock(spec=SearchNotes)
    search_uc.execute_text.return_value = [_make_search_result(1)]
    last_results: list[SearchResult] = []

    executor = create_agent(
        llm=_make_fake_llm(),
        search_use_case=search_uc,
        manage_use_case=MagicMock(spec=ManageNotes),
        last_results=last_results,
    )
    search_tool = next(t for t in executor.tools if t.name == "search_vault")
    search_tool.func("query de prueba")

    assert len(last_results) == 1
```

(Usar los mocks/fixtures de `_make_fake_llm`/`_make_search_result` ya presentes en
cada fichero de test; no crear duplicados.)

## Orden de ejecución con gates

1. **Theming/branding** (bajo riesgo, sin tests): `public/theme.json`,
   `public/style.css`, `public/logo_*`, `public/favicon.svg`,
   `.chainlit/config.toml`, `chainlit.md`. Gate: `chainlit run app.py` +
   inspección visual manual (ver Verificación).
2. **Starters**: añadir `@cl.set_starters`. Gate: `ruff check src/app/__init__.py`,
   `ruff format --check`, arranque manual + click en un starter.
3. **Citas nativas** (el cambio delicado, de dentro hacia fuera):
   `src/agent/tools.py` → `src/agent/agent.py` → `src/app/__init__.py`.
   Gate tras cada fichero: `pytest tests/unit/test_tools.py`, luego
   `pytest tests/unit/test_agent.py`; al final `pytest tests/unit/` completo +
   `mypy src` + `ruff check src tests` + `ruff format --check`.
4. **Documentación**: marcar checkboxes en este fichero a medida que se completa
   cada grupo.

## Verificación end-to-end (manual, `chainlit run app.py`)

1. **Theming**: modo oscuro por defecto con fondo/tarjetas/texto correctos; click en
   el toggle de tema → modo claro usa la paleta `theme.json.variables.light`;
   acento teal visible en botón de enviar y elementos primarios.
2. **CSS**: burbuja de usuario con radio asimétrico; composer con radio 18px y
   borde sutil; una respuesta que dispare `search_vault` muestra el paso de tool
   (Chain-of-Thought) con fondo `--card`.
3. **Logo/branding**: favicon y logo en header/pantalla de bienvenida muestran "sb";
   título de página "second-brain".
4. **Starters**: aparecen los 3 chips en la pantalla de bienvenida; click envía el
   mensaje predefinido.
5. **Citas nativas**: preguntar algo que fuerce búsqueda en el vault (ej. "¿qué
   notas tengo sobre arquitectura hexagonal?"); comprobar chips de fuente (uno por
   `note_id` único) al pie del mensaje; click abre el panel lateral con ruta y
   contenido del chunk citado.

## Criterio de completado

- `pytest tests/unit/`, `mypy src`, `ruff check src tests`, `ruff format --check src tests`
  en verde.
- Los 5 puntos de la verificación manual anterior confirmados visualmente en el
  navegador.
- Este fichero actualizado con checkboxes marcados y la sección de gaps conocidos
  documentada.

## TODOs por funcionalidad

### 🎨 Theming
- [x] Crear `public/theme.json` con `variables.dark`/`variables.light`
- [x] Actualizar `.chainlit/config.toml`: `name`, `description`, `default_theme`,
      `custom_css`; eliminar bloques `[UI.theme]`/`default_collapse_content`
      obsoletos; bump `generated_by`

### 🏷️ Branding/Logo
- [x] Crear `public/logo_dark.svg` y `public/logo_light.svg` (mark "sb")
- [x] Crear `public/favicon.svg`
- [x] Actualizar `chainlit.md` a branding "second-brain"

### 🖌️ CSS
- [x] Crear `public/style.css` con selectores `data-step-type`/`id`
- [ ] Ajuste visual manual tras primer `chainlit run` (pendiente: requiere
      inspección en navegador real, no se pudo automatizar sin instalar
      Playwright — ver sección de verificación)

### 💬 Starters
- [x] Añadir `@cl.set_starters` en `src/app/__init__.py` (requirió aceptar
      `user: cl.User | None` en la firma para que mypy valide el tipo
      esperado por `cl.set_starters` en chainlit 2.11.1)

### 📎 Citas nativas
- [x] `src/agent/tools.py`: parámetro opcional `last_results` en `create_search_tool`
- [x] `src/agent/agent.py`: parámetro opcional `last_results` en `create_agent`
- [x] `src/app/__init__.py`: `last_search_results` en sesión, helper
      `_build_citation_elements`, adjuntar `elements` en `on_message`

### 🧪 Tests
- [x] `tests/unit/test_tools.py`: 3 casos nuevos
- [x] `tests/unit/test_agent.py`: 1 caso nuevo
- [x] `pytest tests/unit/` (127 passed), `mypy src` (sin errores),
      `ruff check` y `ruff format --check` (sin hallazgos) en verde

### 📚 Documentación y verificación final
- [x] Sección de gaps conocidos documentada en este fichero (arriba, ya incluida)
- [x] Verificación HTTP automatizada: servidor arrancado con
      `chainlit run app.py`, confirmado por `curl` que `/public/theme.json`,
      `/public/style.css`, `/public/logo_dark.svg`, `/public/favicon.svg`
      devuelven 200; `window.theme` inyectado en el HTML con los valores HSL
      esperados; `/project/settings` devuelve `name: "second-brain"`,
      `default_theme: "dark"` y los 3 starters con las labels correctas.
      Además, se ejecutó `create_search_tool` contra el ChromaDB real ya
      ingerido (`arquitectura hexagonal`) y se confirmó que `last_results`
      captura los `SearchResult` reales (5 resultados, note_id/score
      correctos) — la parte más delicada del cambio (Análisis previo §1)
      queda verificada con datos reales, no solo con mocks.
- [ ] Verificación visual interactiva pendiente (requiere navegador real):
      radio asimétrico de burbujas, apariencia del chip de tool/CoT, panel
      lateral de citas al hacer click, toggle de tema en vivo. No se pudo
      automatizar sin añadir Playwright como dependencia nueva (descartado
      por estar fuera del alcance acordado) — `chromium-cli` tampoco está
      disponible en este entorno. `cl.Text` no se puede instanciar fuera de
      una sesión Chainlit activa (`ChainlitContextException: Chainlit
      context not found`), así que el renderizado real de la cita solo se
      confirma con `chainlit run app.py` y una conversación real en el
      navegador.
- [x] Checkboxes marcados a medida que avanza el trabajo

---

# Plan de Implementación — Chunking a Settings, autocompletado de "/" y quitar subida de archivos

## Contexto

Tres cambios independientes en la UI de Chainlit (`src/app/__init__.py` y
`.chainlit/config.toml`), acordados tras iterar con el usuario:

1. **Chunking fuera de la pantalla inicial**: `on_chat_start`
   (`src/app/__init__.py`) bloqueaba el arranque del chat con un
   `cl.AskActionMessage` que obligaba a elegir estrategia de chunking antes
   de poder escribir. Se mueve al **panel de Settings** nativo (icono ⚙️,
   `cl.ChatSettings` + `@cl.on_settings_update`). Los botones de "Borrar
   historial" / "Limpiar huérfanos" **no se tocan** — siguen exactamente como
   estaban (adjuntos al mensaje de bienvenida vía `cl.Action` +
   `@cl.action_callback`); solo se les añade una segunda vía de acceso (ver
   punto 2).
2. **Autocompletado al escribir "/"**: Chainlit 2.x soporta comandos nativos
   vía `cl.context.emitter.set_commands([...])` (tipo `CommandDict`): al
   escribir "/" en el composer aparece un desplegable con los comandos
   registrados. Se registran `reset` y `prune`, que reutilizan
   `_reset_history`/`_confirm_and_prune` (las mismas funciones que ya usan
   los botones y los comandos de texto libre existentes
   `_RESET_COMMANDS`/`_PRUNE_COMMANDS`). Chainlit expone el comando elegido
   en `message.command` cuando el usuario lo selecciona del desplegable.
3. **Quitar la subida de archivos**: `.chainlit/config.toml` tenía
   `[features.spontaneous_file_upload]` con `enabled = true`, pero
   `on_message` nunca leía `message.elements` — no se procesaba nada de lo
   subido. Se desactiva con `enabled = false`.

No existe `tests/unit/test_app.py` ni test alguno sobre `on_chat_start`/
`on_message` — la capa `src/app/` es pura orquestación de Chainlit (I/O de
UI) y no se testea en este proyecto. Se mantiene esa convención: no se
añaden tests para los handlers, pero sí para el helper puro de config nuevo
(`get_strategy_from_env`), que sigue el patrón ya usado en
`tests/unit/test_config.py`.

## Análisis previo: reconstrucción del agente al cambiar de estrategia

**Aspecto crítico**: `create_agent` crea siempre una
`ConversationBufferWindowMemory` nueva y no admite inyectar memoria
existente. Cambiar de estrategia desde el panel de Settings a media
conversación obliga a reconstruir el agente completo → se pierde el
historial.

**Opciones consideradas**:
1. Reconstruir todo en cada `on_settings_update`, sin comparar el valor
   anterior.
2. Comparar contra `cl.user_session.get("strategy")`; si es igual, no-op;
   si cambia, reconstruir y avisar explícitamente del reinicio de historial.

**Decisión**: Opción 2 — evita trabajo innecesario y permite un mensaje claro
solo cuando de verdad hay pérdida de historial.

**Riesgo aceptado**: sigue sin preservarse el historial al cambiar de
estrategia (limitación de `create_agent`, fuera de alcance). Mitigación:
mensaje explícito al usuario en el momento del cambio.

## Análisis previo: comandos nativos "/" vs comandos de texto libre existentes

**Aspecto crítico**: ya existían `_RESET_COMMANDS`/`_PRUNE_COMMANDS`
(coincidencia de texto libre en `on_message`). Había que decidir cómo
convive el nuevo mecanismo nativo (`message.command`) con el existente, sin
duplicar lógica de negocio.

**Opciones consideradas**:
1. Sustituir el texto libre por el comando nativo.
2. Mantener ambos: registrar `set_commands` para el desplegable y seguir
   comprobando `message.command` **además** de la coincidencia de texto ya
   existente, ambos llamando a las mismas funciones.

**Decisión**: Opción 2 — no se pidió quitar el modo texto libre; no hay
lógica duplicada porque ambas rutas llaman a las mismas funciones.

**Riesgo aceptado**: dos puntos de entrada para el mismo efecto, mitigado
porque delegan en las mismas funciones ya existentes.

## Detalle de implementación no previsto en el análisis inicial

`mypy` marcó `cl.context.emitter.set_commands(...)` como
`Coroutine[...] must be used` (stub `async def` en `BaseChainlitEmitter`).
Inicialmente se descartó el `await` razonando por analogía con
`chat_settings.py` (que llama a `set_chat_settings` sin `await`), pero la
prueba manual (`chainlit run app.py`) reveló el error real: sin `await`,
Python emite `RuntimeWarning: coroutine 'AsyncServer.emit' was never
awaited` y el comando nunca llega al cliente. La diferencia: `set_chat_settings`
solo hace una asignación local síncrona (`self.session.chat_settings = settings`),
mientras que `set_commands` sí delega en `self.emit(...)`, que en tiempo de
ejecución es el `emit` async de `python-socketio` — por tanto **sí** requiere
`await`, tal como declara el stub. Corregido añadiendo el `await`. Lección:
un fallo de tipado "silencioso" (sin excepción, solo un warning) solo se
detecta con una ejecución real, no con mypy/tests — de ahí que la
verificación manual con `chainlit run app.py` sea un gate obligatorio y no
opcional en este tipo de cambios. También hubo que anotar la lista de
widgets como `list[InputWidget]` (invariancia de `list` en mypy) y añadir la
clave `"selected"` a cada `CommandDict` (el `TypedDict` la exige aunque sea
`Optional`).

## TODOs por funcionalidad

### 🔧 Config (`src/infrastructure/config.py`)
- [x] Añadir `get_strategy_from_env() -> ChunkStrategy`.
- [x] Refactorizar `get_chunker_from_env()` para usarla.
- [x] Refactorizar `get_vector_store()` para usarla.

### ⚙️ Chainlit config (`.chainlit/config.toml`)
- [x] `spontaneous_file_upload.enabled = false`.

### 🧩 App (`src/app/__init__.py`)
- [x] Extraer `_init_agent_session(strategy, *, changed)`.
- [x] Simplificar `on_chat_start` (quitar `AskActionMessage` de chunking;
      usar `get_strategy_from_env` + `_init_agent_session`; enviar
      `ChatSettings`; registrar `set_commands`).
- [x] Añadir `@cl.on_settings_update` → `on_settings_update`.
- [x] Ampliar `on_message` para comprobar `message.command` además del
      texto libre existente.

### 🧪 Tests
- [x] `test_get_strategy_from_env_default_returns_fixed_size`.
- [x] `test_get_strategy_from_env_reads_env_var`.
- [x] `test_get_strategy_from_env_invalid_value_raises_config_error`.

### ✅ Verificación final
- [x] `ruff check src/ tests/ --fix && ruff format src/ tests/` (sin
      hallazgos).
- [x] `mypy src` (sin errores, tras resolver la discrepancia de tipado
      descrita arriba).
- [x] `pytest tests/unit/` (130 passed).
- [x] Prueba manual con `chainlit run app.py`: arranca sin `AskActionMessage`
      de chunking, sin errores de import ni excepciones; se detectó y
      corrigió en esta verificación el bug del `await` faltante en
      `set_commands` (ver "Detalle de implementación" arriba y la entrada
      de `docs/error-log.md` del 2026-07-09). Tras el fix, el arranque no
      deja ningún `RuntimeWarning`. No se pudo verificar visualmente en
      navegador (interacción con el desplegable de "/", el panel ⚙️ y los
      switches) en este entorno sin sesión de navegador real — pendiente de
      que el usuario lo confirme en `chainlit run app.py` local.

## Iteración 2: no abandonar la pantalla de bienvenida + quitar botones redundantes

Feedback del usuario tras probar en vivo: (1) el mensaje "Agente listo con
estrategia **Fixed**..." enviado en `on_chat_start` hacía que Chainlit
abandonara la pantalla de bienvenida (`chainlit.md`) nada más arrancar, aun
seleccionando la estrategia por defecto en segundo plano; (2) los botones
"🗑️ Borrar historial" / "🧹 Limpiar huérfanos" quedaban redundantes una vez
añadidos los comandos nativos `/reset` y `/prune`.

**Cambios**:
- `_init_agent_session` gana el parámetro `announce: bool = True`. Con
  `announce=False` construye agente/chunker/store/sesión igual que antes
  pero no envía ningún `cl.Message`, así que Chainlit no abandona la
  pantalla de bienvenida. Los errores de inicialización (`ObsidianRagError`)
  siguen mostrándose siempre, incluso con `announce=False` — un fallo de
  configuración debe ser visible aunque rompa la pantalla de bienvenida,
  es preferible a fallar en silencio.
- `on_chat_start` llama a `_init_agent_session(strategy, announce=False)`.
  `on_settings_update` seguía sin tocar (usa `changed=True`, `announce`
  por defecto `True`) — un cambio de estrategia a media conversación sí debe
  confirmarse, porque el usuario ya está en la vista de chat interactuando
  con el panel de Settings.
- Se eliminaron `@cl.action_callback("reset_history")` /
  `on_reset_history_action`, `@cl.action_callback("prune_orphans")` /
  `on_prune_orphans_action`, y la construcción de `welcome_actions` dentro
  de `_init_agent_session`. `cl.user_session["prune_orphans"]` se sigue
  fijando siempre (objeto o `None` en modo readonly) porque `on_message`
  todavía lo necesita para el comando `/prune`; solo se quitó la exposición
  como botón.
- Gates repetidos: `ruff check --fix` + `ruff format`, `mypy src`,
  `pytest tests/unit/` (130 passed) y `chainlit run app.py` — arranca sin
  warnings ni excepciones nuevas.

### TODOs iteración 2
- [x] `_init_agent_session(strategy, *, changed=False, announce=True)`.
- [x] `on_chat_start` con `announce=False`.
- [x] Quitar `on_reset_history_action`/`on_prune_orphans_action` y
      `welcome_actions`.
- [x] `ruff check`/`format`, `mypy src`, `pytest tests/unit/` en verde.
- [x] `chainlit run app.py` sin warnings/excepciones nuevas.
- [ ] Verificación visual en navegador (pantalla de bienvenida se mantiene
      al arrancar; `/reset` y `/prune` siguen funcionando sin los botones)
      pendiente de confirmación del usuario — este entorno no tiene sesión
      de navegador real.

## Iteración 3: indicador de carga + decisión sobre persistencia de estrategia

Dos preguntas del usuario tras la iteración 2:

1. ¿Se puede indicar visualmente que se está construyendo/cambiando el
   agente (tanto en el arranque silencioso como al cambiar de estrategia
   desde Settings), ya que ahora no hay ningún mensaje ni feedback visible?
2. ¿Tiene sentido que cada chat nuevo tenga que reseleccionar la estrategia,
   ya que siempre arranca desde `CHUNKER_STRATEGY` del `.env`?

**Pregunta 1 — indicador de carga**: se investigó el bundle del frontend de
Chainlit (`chainlit/frontend/dist/assets/index-*.js`) y se confirmó que los
eventos `task_start`/`task_end` del emitter (`cl.context.emitter.task_start()`
/`task_end()`) activan un indicador de carga nativo global, independiente de
la lista de mensajes/steps del hilo — no reintroduce el problema de
abandonar la pantalla de bienvenida (a diferencia de `cl.Message`/`cl.Step`,
que sí forman parte del hilo). `_init_agent_session` ahora envuelve toda la
construcción en `await task_start()` / `await task_end()` (en un
`try/finally`, así se apaga el indicador también si falla con
`ObsidianRagError`). Igual que con `set_commands` (iteración 1), estos
métodos delegan en `self.emit(...)` (el `emit` async de `python-socketio`)
así que requieren `await`; se verificó con `chainlit run app.py` que no
aparece el `RuntimeWarning` de corrutina no esperada.

**Pregunta 2 — persistencia entre sesiones**: se preguntó al usuario si
prefería que la última estrategia elegida en Settings persistiera entre
chats nuevos (requeriría un fichero local de estado, fuera del alcance
actual) o mantener el diseño actual (cada chat nuevo usa el default de
`CHUNKER_STRATEGY`, que ya es la única fuente de verdad de configuración del
proyecto — ver skill `config-management`). **Decisión confirmada por el
usuario**: mantener el comportamiento actual, sin cambios de código. Si en
el futuro se quiere otro default permanente, basta con editar
`CHUNKER_STRATEGY` en `.env`.

### TODOs iteración 3
- [x] `task_start`/`task_end` en `_init_agent_session` (try/finally).
- [x] `ruff check`/`format`, `mypy src`, `pytest tests/unit/` (130 passed)
      en verde.
- [x] `chainlit run app.py` sin `RuntimeWarning` ni excepciones nuevas.
- [x] Pregunta de persistencia resuelta con el usuario: sin cambios de
      código (se mantiene `CHUNKER_STRATEGY` del `.env` como único default).
- [ ] Verificación visual en navegador de que el indicador de carga se ve
      (arranque y cambio de estrategia) — pendiente, este entorno no tiene
      sesión de navegador real.

## Iteración 4: `task_start`/`task_end` no bastan — indicador real por mensaje

El usuario probó en el navegador y reportó que no se ve ningún indicador de
carga. Se investigó más a fondo el bundle del frontend (siguiendo el atom de
Recoil `boe` = `Loading`, consumido en el hook `cd()`) y se confirmó la causa
real: el único efecto visual de `task_start`/`task_end` es cambiar el icono
de "enviar" por uno de "detener" en el composer, **y solo si
`firstInteraction` ya es `true`** (es decir, después de que el usuario haya
enviado su primer mensaje). En el arranque (`on_chat_start`), antes de
cualquier interacción, esa condición nunca se cumple, así que no hay ningún
indicador visible ahí — la suposición de la iteración 3 (que `task_start`
mostraba un spinner genérico) era incorrecta.

Como Chainlit no ofrece ningún indicador de carga visible antes del primer
mensaje que no pase por el hilo de mensajes, se preguntó al usuario cómo
resolver el conflicto con la decisión de la iteración 2 (no abandonar la
pantalla de bienvenida). **Decisión confirmada por el usuario**: aceptar que
el arranque vuelva a abandonar la pantalla de bienvenida a cambio de tener
feedback visual real.

**Cambio**: `_init_agent_session` ya no tiene parámetro `announce`. Ahora
siempre:
1. Envía un mensaje inicial ("Cargando estrategia **X**..." en el arranque,
   "Cambiando a estrategia **X**..." en un cambio desde Settings).
2. Construye chunker/store/agente (con `task_start`/`task_end` alrededor,
   que se conserva porque igualmente deshabilita el composer mientras se
   reconstruye, aunque no muestre icono visible en el arranque).
3. Actualiza ese mismo mensaje in-place (`cl.Message.update()`, no un
   segundo mensaje) con el resultado final o el error.

`on_chat_start` y `on_settings_update` llaman a `_init_agent_session` igual
que antes, solo que ahora sin el argumento `announce`.

### TODOs iteración 4
- [x] Quitar el parámetro `announce`; `_init_agent_session` siempre envía
      un mensaje de carga y lo actualiza con `Message.update()`.
- [x] `on_chat_start` sin `announce=False`.
- [x] `ruff check`/`format`, `mypy src`, `pytest tests/unit/` (130 passed)
      en verde.
- [x] `chainlit run app.py` sin warnings ni excepciones nuevas.
- [ ] Verificación visual en navegador de que el mensaje de carga aparece y
      se actualiza correctamente (arranque y cambio de estrategia) —
      pendiente de confirmación del usuario.

## Iteración 5: forzar la transición a la vista de chat en el arranque

El usuario probó la iteración 4 en el navegador real y reportó que el chat
se quedaba en la pantalla principal (bienvenida/starters), sin mostrar el
mensaje de carga — contradiciendo la lectura inicial del código del
frontend (que sugería que el mensaje debía bastar para ocultar esa
pantalla). Se investigó más a fondo `chainlit/socket.py` y
`chainlit/emitter.py`: la pantalla de bienvenida solo se oculta cuando el
cliente recibe el evento de socket `"first_interaction"`, que Chainlit solo
emite tras (a) un mensaje real del usuario (`process_message`) o (b) la
respuesta a un `Ask*` prompt — nunca por el simple hecho de que el servidor
envíe un `cl.Message` durante `on_chat_start`.

Se preguntó al usuario cómo resolver el conflicto (silencio total en el
arranque vs. mensaje de carga oculto tras la pantalla de bienvenida).
**Decisión del usuario**: una tercera opción no ofrecida en las alternativas
— saltarse la pantalla de bienvenida por completo y arrancar directamente en
la vista de chat, conservando el mensaje "Cargando estrategia...".

**Cambio**: al principio de `_init_agent_session`, si
`cl.context.session.has_first_interaction` es `False` (arranque, nunca lo
será `True` en el cambio de estrategia vía Settings porque ahí ya hubo una
interacción real previa), se fija a `True` y se llama a
`cl.context.emitter.init_thread(interaction="chunking_init")` — el mismo
mecanismo interno que Chainlit dispara tras la primera interacción real del
usuario. Esto **no es una API pública documentada**: es alcanzar
directamente atributos/métodos internos de `session`/`emitter`. Se dejó un
comentario en el código señalando dónde revisar (`chainlit/emitter.py`
→ `init_thread`, `chainlit/session.py` → `has_first_interaction`) si una
futura versión de Chainlit cambia este comportamiento.

### TODOs iteración 5
- [x] `cl.context.session.has_first_interaction` + `emitter.init_thread(...)`
      al principio de `_init_agent_session`, guardado por el propio flag
      para no repetirlo en cambios de estrategia posteriores.
- [x] `ruff check`/`format`, `mypy src`, `pytest tests/unit/` (130 passed)
      en verde.
- [x] `chainlit run app.py` sin warnings ni excepciones nuevas.
- [ ] Verificación visual en navegador de que el chat arranca directamente
      en la vista de conversación (sin pantalla de bienvenida) mostrando
      "Cargando estrategia..." actualizado a "Agente listo..." — pendiente
      de confirmación del usuario. Es la parte con más incertidumbre de
      toda la funcionalidad (mecanismo interno no documentado), así que
      conviene confirmarla explícitamente antes de dar la tarea por
      cerrada.
