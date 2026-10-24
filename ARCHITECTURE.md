# Chiron — Arquitectura técnica

> **Borrador tentativo.** Esta arquitectura es una propuesta inicial y puede cambiar a medida que avance el proyecto.

## Stack

- **Lenguaje:** Python (backend y agentes)
- **Orquestación:** LangGraph + LangChain
- **Modelos:** Gemini API, rotando entre modelos según la tarea y los rate limits
- **Voz y video:** Gemini Live API para conversación en tiempo real + avatar animado sincronizado con el audio
- **RAG:** vector store (Chroma o FAISS) con embeddings de Gemini
- **Herramientas:** servidor MCP (FastMCP) con las herramientas de examen físico
- **Backend:** FastAPI con WebSockets
- **Frontend:** web con cámara y micrófono del estudiante
- **Observabilidad y evals:** LangSmith (tracing + datasets + evaluadores)
- **Testing:** pytest para la lógica, Playwright para el flujo E2E
- **Desarrollo:** Claude Code

## El grafo (LangGraph)

```
inicio (carga el caso)
   ↓
paciente ←──────────┐   responde con RAG sobre su caso
   ↓                │
router ─────────────┤   ¿pregunta? → paciente
   │                │   ¿examen?  → herramienta MCP
   │   examen (MCP) ┘
   ↓   ¿terminó / dio diagnóstico?
feedback                LLM-as-a-judge con rúbrica
   ↓
fin
```

## Estado de la sesión

Caso activo, transcripción, información ya revelada, exámenes realizados y diagnóstico propuesto por el estudiante.

## Caso clínico (estructura)

Datos del paciente, motivo de consulta, historia de la enfermedad, antecedentes, medicación, alergias, personalidad (nervioso, reservado, conversador), hallazgos del examen, laboratorio, diagnóstico oculto y preguntas clave para la rúbrica.

## Uso del dataset de preguntas y respuestas

- Few-shot en el prompt, para que el paciente responda natural
- Dataset de evals en LangSmith
- Base de la rúbrica del feedback

## Evals (el diferencial)

| Eval | Qué mide |
|---|---|
| No revela el diagnóstico | El paciente nunca dice qué tiene |
| Consistencia | No se contradice con su caso |
| Sin alucinaciones | No inventa síntomas que no están en el caso |
| En personaje | Habla como paciente, no como médico ni como AI |
| Calidad del feedback | La rúbrica detecta las preguntas clave que faltaron |
| Latencia | La respuesta es lo bastante rápida para una videollamada |

## Estructura del repo (propuesta)

```
chiron/
├── cases/          casos clínicos ficticios (JSON)
├── data/           dataset de preguntas y respuestas
├── agents/         grafo, nodos y prompts
├── rag/            indexado y retrieval
├── mcp_server/     herramientas de examen físico
├── api/            FastAPI + WebSockets
├── frontend/       UI de videollamada
├── evals/          datasets y evaluadores de LangSmith
├── tests/          pytest + Playwright
└── README.md
```

## Pasos (en orden, sin fecha)

1. Casos clínicos ficticios + dataset de preguntas y respuestas
2. Agente paciente en LangGraph, por chat (prompt + RAG del caso)
3. Servidor MCP con las herramientas de examen físico
4. Agente de feedback con rúbrica (LLM-as-a-judge)
5. Evals en LangSmith
6. Capa de voz con Gemini Live
7. Videollamada con avatar
8. README, video demo y post de LinkedIn

Cada paso deja algo que funciona: si la videollamada se complica, igual hay producto por chat.

## Métricas de éxito

- El paciente no revela el diagnóstico ni se contradice (evals).
- Una estudiante real lo usa y le sirve para practicar.
- El feedback detecta las preguntas clave que faltaron.

## Riesgos y supuestos

- Latencia en la videollamada que rompa la experiencia.
- El paciente alucina síntomas que no están en el caso.
- Límites de las APIs gratuitas.
- **Supuesto:** con buen contexto y casos bien armados, un modelo gratuito alcanza para un paciente creíble.

## Diferencial

No es "un chatbot de salud": es un simulador evaluado, con métricas que prueban que el paciente se comporta como debe.
