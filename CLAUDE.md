# Chiron

Simulador de pacientes virtuales para que estudiantes de medicina practiquen el ECOE: anamnesis y examen físico frente a un paciente con IA, y después feedback contra la grilla oficial. Ver [README.md](README.md) (producto) y [ARCHITECTURE.md](ARCHITECTURE.md) (arquitectura tentativa).

## Dominio: el ECOE

Ver el detalle en [data/ecoe/contexto-ecoe.md](data/ecoe/contexto-ecoe.md). Lo esencial:

- **ECOE** = Evaluación Clínica Objetiva Estructurada, examen práctico por estaciones.
- **Estación clínica (~7 min):** anamnesis **o** examen físico con un actor o paciente real.
- **Paraclínica e imagenología:** interpretar estudios y saber cuándo pedirlos y cuándo no.
- **Evaluación:** el docente puntúa cada ítem de una **grilla** como Excelente / Bien / Regular / No realizado. También cuentan las formalidades (saludar, presentarse, ficha patronímica).
- **El paciente solo responde lo que se le pregunta.** No se adelanta, no ayuda y no revela el diagnóstico. El examen mide que el estudiante no se olvide de preguntar.

Materias: **MPNA** (Medicina en el Primer Nivel de Atención, adultos) por ahora; después **Pediatría**. El estudiante elige para qué materia practica.

## Datos

```
data/ecoe/
├── contexto-ecoe.md          qué es el ECOE (común a todas las materias)
├── audios/                   audios originales + transcripciones.md
└── <materia>/                p. ej. mpna/
    ├── raw/                  PDFs originales (no se tocan, no se versionan)
    │   └── slides/           presentaciones escaneadas; su contenido ya está en los apuntes
    ├── clean/                apuntes limpios en Markdown (con marcas <!-- p. N --> de página)
    ├── grillas/              una grilla de evaluación por JSON + index.json
    └── chunks.jsonl          chunks para el RAG (generado)
```

- Solo se versiona lo procesado. `raw/` y los `.ogg` están en `.gitignore`: los PDFs y audios originales viven solo en local.
- Las **grillas** son la fuente de verdad de la rúbrica. Su texto es literal del PDF: no parafrasearlo.
- El contenido médico no se reescribe con LLM. La limpieza de PDFs es determinística (`rag/clean_pdfs.py`).

## Casos clínicos

- Spec en [cases/SPEC.md](cases/SPEC.md); casos en `cases/<materia>/<id>.json`, cada uno armado a partir de una o más grillas.
- Cada ítem evaluable de la grilla tiene que estar cubierto (`grilla_items: ["<grilla_id>::<texto literal>"]`), incluidos los negativos pertinentes.
- Las respuestas del paciente revelan un solo hecho por pregunta, en lenguaje de paciente, sin nombrar el diagnóstico.
- Flujo para casos nuevos: un agente escribe el caso, otro con contexto limpio lo revisa contra los apuntes, y `python cases/validate.py` + `pytest` tienen que pasar.

## Tests

`python -m pytest` (config en `pytest.ini`). TDD para lo determinístico; el comportamiento del LLM se mide con evals.

## Gemini

- Keys en `.env` como `GOOGLE_API_KEY_1`, `_2`, `_3` (cuentas distintas). `llm/gemini.py` rota de key ante 429 y espera si todas llegaron al límite por minuto.
- `MODELS` en `llm/gemini.py` define qué modelo usa cada tarea (`patient`, `router`, `judge`, `live`, `embedding`), con alternativas de respaldo.
- Los modelos cambian seguido: `python llm/probe_models.py` prueba cuáles andan con cada key y cuánto tardan.
- En el plan gratuito los modelos "pro" tienen cuota 0, y el límite de embeddings es de 100 por minuto por key.

## Observabilidad (LangSmith)

- Con `LANGSMITH_TRACING=true` y `LANGSMITH_API_KEY` en `.env`, cada turno del grafo se traza solo en el proyecto `chiron` de smith.langchain.com.
- Cada traza se llama `turno N`, lleva el `case_id` como tag y `case_id` + `session_id` en la metadata. Dentro se ven el router, el nodo y el prompt y la respuesta exactos de Gemini.

## RAG

Entorno: `python -m venv .venv` + `.venv/Scripts/pip install -r requirements.txt`.

```
python rag/clean_pdfs.py mpna   # raw/*.pdf -> clean/*.md (requiere pdftotext)
python rag/chunk.py mpna        # clean + grillas + contexto -> chunks.jsonl
python rag/ingest.py mpna       # chunks -> Chroma (.chroma/), embeddings de Gemini
python rag/query.py mpna "¿qué preguntar ante disnea?"
```

- Una colección de Chroma por materia: `ecoe_<materia>`.
- Metadata de cada chunk: `materia`, `fuente`, `tipo` (`apunte` | `grilla` | `contexto_ecoe`), `seccion`, `pagina`.
- Chunking con LangChain (`MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter`).

## Convenciones

- Contenido, prompts y documentación en español. Código en inglés o español, siguiendo lo que ya haya en el archivo.
- Python 3.11. Dependencias en `requirements.txt`.
