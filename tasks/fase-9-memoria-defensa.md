# Fase 9 — Memoria del TFM y defensa

## Contexto

La memoria es el entregable académico. Debe justificar las decisiones técnicas, presentar la evaluación comparativa y demostrar rigor. La defensa es una presentación de 15-20 minutos + preguntas.

**Ficheros a crear:**
- `docs/memoria.md` (borrador en Markdown, después convertir a PDF/Word según normativa)
- `docs/presentacion.md` (guión de la presentación)
- `docs/demo-script.md` (guión de la demo en vivo)

---

## Tareas

### T9.1 — Escribir la memoria técnica

Estructura sugerida (adaptar a la normativa del máster):

**1. Introducción** (~2-3 páginas)
- Motivación: por qué un asistente RAG sobre notas personales
- Problema: las herramientas de búsqueda en Obsidian son limitadas (solo keyword match), no entienden semántica ni relaciones entre notas
- Objetivo: construir un agente conversacional RAG que explote la estructura de un vault de Obsidian
- Contribución: comparativa de estrategias de chunking específicas para vaults de conocimiento personal

**2. Estado del arte** (~3-4 páginas)
- RAG (Retrieval-Augmented Generation): concepto, arquitectura, ventajas vs fine-tuning
- Estrategias de chunking existentes: fixed size, semantic, recursive character, document-based
- Herramientas similares: Obsidian Copilot, Khoj, Quivr — qué hacen y qué les falta
- Graph RAG y enfoques que explotan relaciones entre documentos
- LLMs locales: estado actual (Llama, Mistral), viabilidad para uso personal

**3. Arquitectura del sistema** (~4-5 páginas)
- Arquitectura hexagonal: justificación, diagrama de capas
- Diagrama de componentes del sistema completo
- Modelos del dominio: Note, Chunk, SearchResult, etc.
- Puertos y adaptadores: qué abstrae cada uno y por qué
- Flujo de datos: ingesta (vault → chunks → embeddings → ChromaDB) y consulta (query → retrieval → LLM → respuesta)
- Decisiones de diseño: por qué Ollama, por qué ChromaDB, por qué LangChain
- Portabilidad: cómo el mismo sistema corre local (Ollama) y en producción (Groq)

**4. Implementación** (~5-6 páginas)
- Stack tecnológico: tabla con cada componente y su rol
- Módulo de ingesta: ObsidianLoader y cómo se parsean las notas
- Estrategias de chunking — esta es la sección clave:
  - Fixed size: cómo funciona, parámetros (chunk_size, overlap), limitaciones
  - Markdown header: cómo respeta la estructura semántica del documento
  - Backlink-aware: cómo explota el grafo de conocimiento de Obsidian, por qué es original
  - Diagrama visual comparando cómo cada estrategia divide la misma nota
- Vector store: ChromaDB, colecciones por estrategia, persistencia
- Agente LangChain: herramientas, prompt de sistema, memoria conversacional
- Interfaz: Chainlit, selector de estrategia

**5. Evaluación** (~4-5 páginas)
- Metodología: dataset anotado, métricas seleccionadas, proceso de evaluación
- Métricas: Precision@K, MRR, Recall@K — definición formal y justificación
- Dataset: cómo se construyó, distribución por dificultad, ejemplos
- Resultados:
  - Tabla comparativa global (las tres estrategias × tres métricas)
  - Tabla desglosada por dificultad (easy/medium/hard)
  - Gráficos de barras comparando las tres estrategias
- Análisis:
  - ¿Qué estrategia gana globalmente?
  - ¿En qué tipo de preguntas destaca cada una?
  - ¿El BacklinkAwareChunker mejora en preguntas "hard" que requieren conectar notas?
  - Limitaciones: tamaño del dataset, vault personal (no generalizable)

**6. Despliegue** (~1-2 páginas)
- Arquitectura local vs. producción
- Groq como alternativa gratuita a Ollama en cloud
- Hugging Face Spaces como plataforma de despliegue
- Consideraciones: modo readonly, vault estático, embeddings locales vs. API

**7. Conclusiones y trabajo futuro** (~1-2 páginas)
- Resumen de contribuciones
- Conclusiones de la evaluación
- Trabajo futuro:
  - Chunking híbrido (combinar estrategias)
  - Reranking con cross-encoder
  - Soporte para imágenes y PDFs en el vault
  - Sincronización en tiempo real con el vault (file watcher)
  - Evaluación con vaults de otros usuarios

**8. Referencias** (~1-2 páginas)

**Anexos**
- Instrucciones de instalación y uso
- Código fuente relevante (solo fragmentos clave, no todo)
- Dataset completo de evaluación
- Resultados detallados de la evaluación

### T9.2 — Generar gráficos para la memoria

Scripts o notebooks para generar las visualizaciones de la sección de evaluación:

- Gráfico de barras: Precision@K por estrategia
- Gráfico de barras: MRR por estrategia
- Gráfico de barras agrupado: métricas × dificultad × estrategia
- Diagrama: cómo cada chunker divide una misma nota de ejemplo
- Diagrama: arquitectura del sistema (el que ya tenemos de la conversación)

Herramientas sugeridas: `matplotlib` o `plotly` para gráficos. Exportar como PNG para incluir en la memoria.

### T9.3 — Preparar la demo en vivo

Guión de demostración para la defensa (5-7 minutos):

```
1. Mostrar el vault en Obsidian (la herramienta original del usuario)
2. Abrir el terminal: ejecutar scripts/ingest.py para indexar
3. Abrir Chainlit: chainlit run app.py
4. Demo de búsqueda:
   - Pregunta fácil: "¿Qué es la arquitectura hexagonal?"
   - Pregunta que conecta notas: "¿Cómo se relaciona el patrón Saga con CQRS?"
   - Pregunta sin respuesta en el vault: "¿Cuál es el PIB de España?"
5. Demo de creación de nota:
   - "Crea una nota sobre los resultados de la evaluación del TFM"
   - Mostrar que la nota aparece en el vault de Obsidian
6. Cambiar estrategia de chunking en la UI
7. Mostrar la versión desplegada en HuggingFace (URL pública)
```

### T9.4 — Preparar presentación para la defensa

Estructura (15-20 diapositivas):

1. Portada
2. Motivación y problema
3. Objetivo del TFM
4. Estado del arte (resumido)
5. Arquitectura del sistema (diagrama)
6. Stack tecnológico
7. Las tres estrategias de chunking (diagrama visual)
8. Agente y herramientas
9. Metodología de evaluación
10. Resultados (tabla + gráficos)
11. Análisis de resultados
12. Demo en vivo (cambiar a la app)
13. Despliegue
14. Conclusiones
15. Trabajo futuro
16. Preguntas

---

## Reglas generales

- Usar un estilo académico pero accesible — evitar jerga innecesaria.
- Todas las figuras y tablas deben tener pie de figura/tabla numerado.
- Las citas al estado del arte deben ser a papers o documentación oficial (no blogs genéricos).
- Incluir el enlace al repositorio de GitHub y al HuggingFace Space.

---

## Criterio de completado

- [ ] Memoria escrita y revisada (sin faltas ortográficas)
- [ ] Gráficos generados e incluidos en la memoria
- [ ] Presentación con 15-20 diapositivas
- [ ] Demo ensayada al menos 2 veces
- [ ] Todo subido al repositorio (memoria en PDF, presentación)
