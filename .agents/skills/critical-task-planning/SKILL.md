---
name: critical-task-planning
description: Use before implementing any non-trivial design decision in the Obsidian RAG project — new ports/interfaces, choices between multiple valid implementations, or hard-to-reverse decisions (ID schemes, vector store schema, agent tool contracts). Defines a short pre-coding "Análisis previo" format identifying the critical aspect, alternatives considered, and the decision rationale, plus a reference table of recurring project decisions. Trigger before coding original/research-relevant components like the chunkers.
---

# Skill: Critical Task Planning

## Propósito

Antes de implementar cualquier tarea no trivial (una nueva clase, un cambio de diseño, una decisión de librería), el agente debe hacer un breve ejercicio de planificación crítica: identificar el aspecto más arriesgado de la tarea, considerar al menos una alternativa, y justificar la elección. Esto evita que el desarrollo asistido por IA avance "en piloto automático" tomando siempre la primera solución que se le ocurre.

Esta skill no sustituye a `hexagonal-architecture.md` ni a las demás — es una capa de **reflexión previa** que se aplica antes de escribir código.

---

## Cuándo aplicar esta skill

Aplicar el análisis crítico cuando la tarea implica:

- Diseñar una nueva interfaz/puerto o cambiar una existente.
- Elegir entre dos o más formas razonables de implementar algo (estructura de datos, algoritmo, librería).
- Una decisión que será costosa de revertir más adelante (formato de IDs, esquema de la base vectorial, contrato de una herramienta del agente).
- Cualquier tarea marcada como "aportación original" en los ficheros de fase (ej. el `BacklinkAwareChunker`).

NO es necesario aplicarla para:
- Tareas mecánicas con especificación completa (ej. "añade este campo al dataclass").
- Fixes triviales o renombrados.
- Tareas donde el fichero de fase ya especifica la decisión de forma inequívoca.

---

## Formato del análisis (antes de codificar)

Cuando aplique, el agente debe escribir un bloque corto **antes** de generar el código, con esta estructura:

```markdown
### Análisis previo: [nombre de la tarea]

**Aspecto crítico**: [la decisión de diseño que más impacto tiene / más riesgo de tener que rehacerse]

**Opciones consideradas**:
1. [Opción A] — ventajas / inconvenientes
2. [Opción B] — ventajas / inconvenientes

**Decisión**: [Opción elegida] porque [justificación en 1-2 frases,
relacionada con los objetivos del TFM, la arquitectura o el tiempo disponible]

**Riesgo aceptado**: [qué podría salir mal con esta elección y cómo se mitigaría]
```

Este bloque debe ser breve — 5-8 líneas en total. No es un ensayo, es una checkpoint de criterio.

---

## Ejemplo aplicado

```markdown
### Análisis previo: formato de ID de los Chunks

**Aspecto crítico**: el ID de un Chunk debe ser estable entre reindexaciones
(para que `upsert` en ChromaDB sustituya en vez de duplicar) pero también
único si una nota cambia de número de chunks.

**Opciones consideradas**:
1. `f"{note_id}_{index}"` — simple, pero si una nota pasa de 3 a 2 chunks
   tras una edición, el chunk `_2` antiguo queda huérfano en ChromaDB.
2. `f"{note_id}_{index}"` + borrar todos los chunks de la nota antes de
   reindexar (`delete_by_note` en `execute_single`).

**Decisión**: Opción 2. Es ligeramente más trabajo (un delete extra) pero
elimina el problema de chunks huérfanos sin necesitar hashes de contenido,
que añadirían complejidad innecesaria para el alcance del TFM.

**Riesgo aceptado**: si `delete_by_note` falla a mitad de operación podría
quedar el índice inconsistente. Mitigación: loguear el error y no continuar
con el `add_chunks` si el delete falla (ya cubierto por VectorStoreError).
```

---

## Alternativas para decisiones recurrentes del proyecto

Tabla de referencia rápida — decisiones que probablemente reaparezcan, con el aspecto crítico ya identificado para no repetir el análisis desde cero:

| Decisión | Aspecto crítico | Alternativas típicas |
|---|---|---|
| Estrategia de chunking activa | Reproducibilidad de la evaluación | Una colección ChromaDB por estrategia (elegido) vs. reindexar cada vez que se cambia |
| Formato de respuesta de `search_vault` | Que el LLM pueda citar la fuente | Texto plano con `[note_id]` (elegido) vs. JSON estructurado (más robusto pero el LLM local puede no parsearlo bien) |
| Agente ReAct vs. tool-calling | Compatibilidad con Llama 3.2 local | ReAct (más universal, peor parsing) vs. tool-calling nativo (mejor con Groq, puede fallar con modelos pequeños locales) |
| Manejo de notas sin frontmatter | No romper la ingesta con vaults reales | Asignar `NoteType.UNKNOWN` y continuar (elegido) vs. lanzar error y detener la ingesta |
| Persistencia de resultados de evaluación | Poder comparar ejecuciones a lo largo del tiempo | Un fichero por ejecución con timestamp (elegido) vs. sobrescribir un único fichero |

Si una tarea coincide con una fila de esta tabla, el agente puede referenciarla en vez de repetir el análisis completo, pero debe indicar explícitamente "Decisión ya registrada en critical-task-planning.md: [fila]".

---

## Entregable obligatorio: `implementation-plan.md`

Siempre que se planifique una fase o cualquier tarea no trivial (las del apartado
"Cuándo aplicar esta skill"), el agente **debe crear o actualizar un fichero
`implementation-plan.md`** en la raíz del repo **antes de escribir código**. No
basta con razonar en el chat: el plan se deja por escrito para que sea revisable,
versionable y sirva de material para la memoria del TFM.

El `implementation-plan.md` debe contener, como mínimo:

1. **Contexto y decisión de fondo** — qué se va a construir y las decisiones clave
   ya cerradas (incluyendo contradicciones detectadas entre la spec, el código y
   `CLAUDE.md`, y cómo se resuelven).
2. **Mapa de cambios** — qué ficheros se crean/modifican y, si hay refactor,
   tablas "antes → después" de nombres/firmas.
3. **Especificación** de los componentes a implementar (paso a paso).
4. **Tests** a escribir.
5. **Los bloques "Análisis previo"** de los puntos arriesgados (sección anterior).
6. **Orden de ejecución con *gates*** de verificación (`pytest`/`ruff`).
7. **Criterio de completado.**
8. **Lista de TODOs por funcionalidad** (ver abajo).

---

## Entregable obligatorio: lista de TODOs por funcionalidad

Dentro del `implementation-plan.md` (sección final) el agente **debe incluir
siempre una lista de TODOs agrupada por funcionalidad**, no una lista plana. El
objetivo es que cada grupo sea una unidad de trabajo independiente, abordable y
*commiteable* por separado.

Reglas:

- Agrupar por **funcionalidad/capa**, no por orden cronológico. Ejemplos de grupos
  típicos en este proyecto: `Setup y dependencias`, `Dominio`, `Adaptador X`,
  `Chunkers`, `Tests`, `Documentación y sincronización`, `Verificación final`.
- Cada TODO es una casilla markdown (`- [ ]`) concreta y verificable.
- El **orden de ejecución** entre grupos vive en la sección "Orden de ejecución",
  no mezclado con los TODOs.
- A medida que se completa el trabajo, marcar las casillas (`- [x]`) en el fichero.

Formato de referencia:

```markdown
## TODOs por funcionalidad

### 🔧 Setup y dependencias
- [ ] ...

### 🧩 Dominio
- [ ] ...

### 🧪 Tests
- [ ] ...
```

> Estos TODOs por escrito son **independientes** del tracking de tareas en vivo
> del harness (TaskCreate/TaskUpdate): el `implementation-plan.md` es el registro
> persistente y versionado; el tracking en vivo, si se usa, es efímero.

---

## Relación con error-log.md

Si, tras aplicar esta skill, la decisión tomada resulta ser incorrecta más adelante (se detecta un bug o el usuario la corrige), la entrada correspondiente en `docs/error-log.md` debe referenciar qué alternativa se descartó entonces y por qué esa alternativa habría sido mejor. Esto cierra el ciclo: planificación crítica → implementación → si falla, error log con la alternativa correcta para la próxima vez.

---

## Quick checklist

- [ ] ¿La tarea implica una decisión de diseño no especificada al 100% en el fichero de fase?
- [ ] ¿Existe más de una forma razonable de resolverla?
- [ ] Si sí a ambas → escribir el bloque "Análisis previo" antes de codificar.
- [ ] ¿La decisión coincide con la tabla de decisiones recurrentes? → referenciarla en vez de repetir el análisis.
- [ ] ¿He creado/actualizado `implementation-plan.md` con el plan completo antes de codificar?
- [ ] ¿El `implementation-plan.md` incluye la lista de TODOs **agrupada por funcionalidad**?
