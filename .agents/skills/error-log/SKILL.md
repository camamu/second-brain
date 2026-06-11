---
name: error-log
description: Use whenever the user corrects, rejects, or fixes something the agent proposed or implemented (architecture violations, design bugs, wrong approaches discovered after completion). Defines the docs/error-log.md format for documenting what went wrong, why, how it was fixed, and how to avoid it — material for the TFM methodology section. Trigger after any user correction of agent output, and at the start of each phase to review prior entries.
---

# Skill: Error Log & Corrections

## Propósito

Cada vez que el modelo comete un error que el usuario detecta y corrige (un bug, una violación de arquitectura, un test mal diseñado, una mala decisión técnica), debe quedar registrado en `docs/error-log.md`. Esto tiene dos beneficios:

1. **Para el TFM**: es material directo para la sección de "lecciones aprendidas" / metodología de desarrollo asistido por IA — uno de los focos del máster.
2. **Para el propio desarrollo**: evita repetir el mismo error dos veces — el agente debe revisar este fichero al empezar una sesión sobre un módulo donde ya hubo errores previos.

---

## Cuándo registrar una entrada

Registrar SIEMPRE que ocurra alguno de estos casos:

- El usuario corrige código generado porque viola una regla de arquitectura (capas mezcladas, import incorrecto).
- Un test falla y la causa era un error de diseño, no un detalle menor.
- El usuario rechaza un enfoque y pide uno alternativo.
- Se descubre un bug después de haber dado por completada una tarea.
- Una decisión técnica tomada anteriormente resulta ser incorrecta o subóptima y se cambia.

NO registrar:
- Errores tipográficos triviales (nombre de variable mal escrito) sin impacto en el diseño.
- Iteraciones normales de desarrollo (afinar un prompt, ajustar un mensaje de log).

---

## Formato de entrada

Fichero: `docs/error-log.md`. Cada entrada sigue esta plantilla:

```markdown
## [YYYY-MM-DD] Título corto del error

**Fase**: fase-X-nombre.md
**Categoría**: arquitectura | testing | lógica | configuración | dependencias | otro

### Qué se hizo mal
Descripción concreta y objetiva de lo que el código/diseño hacía incorrectamente.
Incluir fragmento de código si ayuda a entenderlo.

### Por qué era un error
Explicación de la consecuencia: qué regla violaba, qué bug producía, o qué
problema generaría a futuro si no se corrige.

### Cómo se corrigió
Descripción del cambio aplicado. Incluir fragmento de código del "antes" y
"después" si el cambio es ilustrativo.

### Cómo evitarlo en el futuro
Una frase accionable. Ej: "Antes de implementar un adaptador, revisar
hexagonal-architecture.md para confirmar qué puerto implementa."
```

---

## Ejemplo de entrada completa

```markdown
## [2025-03-12] BacklinkAwareChunker importaba ObsidianLoader directamente

**Fase**: fase-2-ingesta.md
**Categoría**: arquitectura

### Qué se hizo mal
`BacklinkAwareChunker.__init__` instanciaba `ObsidianLoader` internamente:

```python
class BacklinkAwareChunker(BaseChunker):
    def __init__(self, vault_path: str):
        self._loader = ObsidianLoader(vault_path)  # acoplamiento directo
```

### Por qué era un error
Viola la regla de dependencias de hexagonal-architecture.md: un adaptador
no debe instanciar otro adaptador. Además hacía imposible testear el chunker
sin un vault real en disco, y acoplaba el chunker a una implementación
concreta de NoteLoader en vez de al puerto.

### Cómo se corrigió
El chunker recibe un `NoteLoader` (puerto) por constructor:

```python
class BacklinkAwareChunker(BaseChunker):
    def __init__(self, loader: NoteLoader):
        self._loader = loader  # inyección de dependencia
```

La factory en `infrastructure/config.py` es quien construye
`BacklinkAwareChunker(get_note_loader())`.

### Cómo evitarlo en el futuro
Antes de escribir `__init__`, listar las dependencias del adaptador y
comprobar que todas son tipos de `domain/ports.py`, nunca clases de
`adapters/`.
```

---

## Revisión al inicio de cada fase

Antes de empezar una fase nueva, el agente debe:

1. Leer `docs/error-log.md` (si existe).
2. Si hay entradas relacionadas con la fase actual o con módulos de los que depende, mencionarlas brevemente y aplicar la lección antes de escribir código nuevo.

Si `docs/error-log.md` no existe todavía, crearlo con un encabezado:

```markdown
# Error Log — Obsidian RAG Agent

Registro de errores de diseño/implementación detectados durante el
desarrollo asistido por IA, y cómo se corrigieron. Material de apoyo
para la sección de metodología del TFM.
```

---

## Quick checklist

- [ ] ¿El usuario acaba de corregir algo que el agente propuso o implementó?
- [ ] ¿La corrección revela una regla, patrón o decisión que conviene no olvidar?
- [ ] Si sí a ambas → añadir entrada a `docs/error-log.md` con la plantilla anterior.
