---
title: "Obsidian - Gestión del Conocimiento"
tags: [obsidian, pkm, vault, notas]
date: 2026-01-22
---

# Obsidian - Gestión del Conocimiento

**Obsidian** es una aplicación de gestión del conocimiento personal (PKM) que almacena las notas como ficheros Markdown locales. Su característica más potente son los **backlinks**: enlaces bidireccionales entre notas que forman una red de conocimiento (*second brain*).

## Estructura de un vault

Un **vault** es la carpeta raíz donde Obsidian almacena todas las notas. Cada nota es un fichero `.md` con:

- **Frontmatter YAML**: metadatos (`title`, `tags`, `date`, `aliases`, etc.)
- **Cuerpo Markdown**: el contenido de la nota
- **Backlinks**: referencias a otras notas con la sintaxis `[[Nombre de la nota]]`

## Por qué Obsidian como fuente de datos

Los vaults de Obsidian son ideales para un sistema [[RAG - Recuperación Aumentada con Generación]] por varias razones:

1. **Formato abierto**: ficheros `.md` legibles por cualquier herramienta.
2. **Red de conocimiento**: los `[[backlinks]]` crean relaciones explícitas entre conceptos.
3. **Metadatos ricos**: el frontmatter permite filtrar por etiquetas, fecha, tipo.
4. **Uso real**: el vault del TFM es el cuaderno de estudio del máster — contenido real, no sintético.

## El adaptador ObsidianLoader

En este proyecto, `ObsidianLoader` (`src/adapters/obsidian_loader.py`) implementa los puertos `NoteLoader` y `NoteWriter`. Lee el frontmatter con `python-frontmatter` y construye objetos `Note` del dominio.

Funciones clave:
- `load_all()` → lista todas las notas del vault
- `load_by_id(note_id)` → carga una nota por su identificador
- `create(title, content, tags)` → escribe una nota nueva al disco
- `update(note_id, content)` → actualiza el contenido de una nota existente

## Estrategia backlink

La estrategia `backlink` de [[Estrategias de Chunking]] aprovecha la red de Obsidian: expande cada nota con el contenido de sus notas enlazadas para crear chunks más ricos en contexto.

Ver también: [[TFM - Objetivos y Alcance]], [[ChromaDB - Vector Store]].
