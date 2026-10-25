# Hallazgos de ingeniería

Registro de lo que fui encontrando al construir Chiron: qué apareció, cómo lo detecté, qué hice y qué aprendí. Cada entrada sigue el mismo formato para poder contarla en una entrevista o en un post.

> Formato: **Contexto → Hallazgo → Cómo lo detecté → Qué hice → Resultado → Aprendizaje**

---

## 1. El eval mostró que el paciente revelaba dos hechos con una sola pregunta

- **Contexto:** en el ECOE el paciente solo responde lo que se le pregunta; la nota sale de que el estudiante *no se olvide de preguntar*. Si el paciente adelanta información, el simulador entrena mal.
- **Hallazgo:** a "¿Toma alguna medicación?", el paciente con angina respondió "no tomo nada… la pastilla del colesterol la dejé". Reveló dos hechos: la medicación actual y el abandono del tratamiento de la dislipemia, que es un ítem aparte de la grilla ("Profundiza sobre la dislipemia").
- **Cómo lo detecté:** con un eval en **LangSmith**. El modelo devuelve, además de la respuesta, los ids de los hechos del caso que usó, y un evaluador de código (`un_solo_hecho`) chequea que sea uno solo. Resultado: 19/20.
- **Qué hice:** *(pendiente)* ajustar el prompt y separar los hechos que se solapan en el caso.
- **Aprendizaje:** pedirle al modelo salida estructurada con *qué usó* además de *qué dijo* convierte un comportamiento difuso ("no adelanta información") en una métrica de código, sin necesidad de un juez LLM.

## 2. El eval encontró un riesgo de producción: cuota agotada sin reintento

- **Contexto:** uso el plan gratuito de Gemini con 3 API keys y rotación automática entre keys y modelos.
- **Hallazgo:** en la primera corrida del eval, 15 de 51 ejecuciones fallaron con `RESOURCE_EXHAUSTED`. Con varias llamadas en paralelo se agotaron las 3 keys en el mismo minuto, y la cadena de *fallbacks* no tenía a dónde ir.
- **Cómo lo detecté:** en LangSmith, los runs fallidos agrupados por mensaje de error. Todos eran el mismo.
- **Qué hice:** agregué `with_retry` con espera exponencial sobre la cadena de fallbacks de LangChain y bajé la concurrencia del eval.
- **Aprendizaje:** el eval no solo mide calidad; también es una prueba de carga barata. Lo que falló en el eval le iba a pasar a dos estudiantes usando la app a la vez.

## 3. El router confundía una pregunta al paciente con un planteo diagnóstico

- **Contexto:** un grafo de **LangGraph** decide en cada mensaje si el estudiante pregunta, examina, pide un estudio, plantea un diagnóstico o cierra.
- **Hallazgo:** "¿Qué cree usted que tiene?" se clasificaba como *diagnóstico*, así que el paciente nunca la contestaba.
- **Cómo lo detecté:** probando a mano una consulta completa y mirando la intención detectada en el panel de debug.
- **Qué hice:** precisé en el prompt que *diagnóstico* es cuando el estudiante **afirma** su planteo, no cuando le **pregunta** al paciente qué cree. Después armé un dataset de 25 mensajes para el router.
- **Resultado:** 25/25 en el eval del router.
- **Aprendizaje:** cada bug encontrado a mano se convierte en un ejemplo del dataset, para que no vuelva.

## 4. De 5 segundos a 1 por respuesta: el "thinking" del modelo

- **Contexto:** el objetivo final es una videollamada, así que la latencia del paciente es crítica.
- **Hallazgo:** el paciente tardaba unos 5 s por respuesta. El modelo razonaba ("thinking") por defecto antes de contestar algo tan simple como "hace cuatro meses".
- **Cómo lo detecté:** midiendo la misma pregunta con 3 modelos y 3 niveles de *thinking*:

  | Modelo | Por defecto | `thinking_level` bajo |
  |---|---|---|
  | gemini-3.5-flash | 3,0-3,7 s | 1,3-1,8 s |
  | gemini-3-flash-preview | 2,2-3,1 s | **1,0 s** |

- **Qué hice:** usé `gemini-3-flash-preview` con thinking bajo para el paciente y el modelo *lite* con thinking mínimo para el router.
- **Aprendizaje:** antes de cambiar de modelo, conviene revisar la configuración del que ya tenés. El modelo correcto mal configurado es más lento que uno "peor" bien configurado.

## 5. 45 segundos de arranque: 36 clientes creados de a uno

- **Hallazgo:** el primer mensaje de cada sesión tardaba 45 s.
- **Cómo lo detecté:** midiendo por separado import, creación de modelos y primera llamada: el 90 % estaba en *crear* los modelos, no en usarlos. La rotación armaba 4 cadenas × 3 keys × 3 modelos = 36 clientes de LangChain, y cada uno tarda ~1 s en inicializarse.
- **Qué hice:** compartí los clientes entre cadenas con caché y los precargo en segundo plano cuando arranca el servidor.
- **Resultado:** el arranque bajó de 41 s a 22 s y ya no lo paga el usuario.

## 6. Los agentes revisores encontraron fugas que el validador no veía

- **Contexto:** los casos clínicos los escribe un agente y los revisa otro con contexto limpio, mientras un validador automático chequea que cada ítem de la grilla tenga respuesta.
- **Hallazgo:** casos que pasaban el validador igual tenían fugas sutiles:
  - el paciente decía "una **opresión**", la palabra exacta que la grilla espera que el estudiante pregunte ("Pregunta TIPO: opresivo");
  - respuestas que adelantaban otro ítem: a "¿cuánto le duele?" contestaba "…me obliga a pararme", revelando que el dolor es de esfuerzo.
- **Aprendizaje:** el validador garantiza *cobertura*; la revisión independiente garantiza *calidad*. Son controles distintos, y hacen falta los dos.

## 7. Dos fuentes de la cátedra se contradecían

- **Hallazgo:** el revisor del caso de pielonefritis quitó "la diabetes hace complicada la ITU" porque los apuntes no lo decían. Al sumar otra clase de la cátedra (Infecciones urinarias 2026), esa clase **sí** lo dice explícitamente.
- **Qué hice:** corregí el caso y cité la fuente con página.
- **Aprendizaje:** un sistema de IA médica tiene que poder citar de dónde saca cada dato. Por eso cada chunk del RAG guarda fuente y número de página, y cada caso lista sus fuentes.

## 8. La limpieza de PDFs borraba contenido real

- **Contexto:** decidí limpiar los PDFs sin LLM (con reglas), para no arriesgar que un modelo reescriba contenido médico.
- **Hallazgo:** el filtro que descartaba "restos de diagramas" también borraba líneas cortas reales, como `DI → 0°` o `100–125 mg/dL`.
- **Cómo lo detecté:** comparando el conteo de palabras entre el PDF original y el Markdown limpio. Ahí aparecieron listas enteras faltantes.
- **Qué hice:** el filtro pasó a descartar solo líneas sin palabras ni números. Pérdida final: menos del 0,1 % de las palabras, todas etiquetas de diagramas.
- **Aprendizaje:** toda transformación de datos necesita una métrica de "qué se perdió". Mirar un ejemplo a ojo no alcanza.

## 9. PDFs con trampas: viñetas Wingdings y texto a dos columnas

- **Hallazgos:**
  - en las diapositivas, cada viñeta salía como la letra `n` seguida de un carácter invisible (U+F06E, de la fuente Wingdings);
  - las guías del MSP están a dos columnas, y la extracción "con layout" mezclaba las columnas y generaba títulos falsos.
- **Qué hice:** normalicé los caracteres de uso privado a viñetas y, para los PDFs a dos columnas, extraigo en orden de lectura. Cada fuente declara su modo en un manifiesto (`sources.json`).

## 10. Una guía de 2,3 millones de caracteres habría tapado todo el material

- **Hallazgo:** entre el material del curso estaba la guía ADA 2025 (en inglés): sola serían ~1.500 chunks, más del doble de todo el índice.
- **Decisión:** dejarla afuera. El ECOE se evalúa con lo que enseña la cátedra; una guía enorme y genérica dominaría cada búsqueda por volumen, no por relevancia. Además etiqueté cada fuente por tipo (`apunte`, `clase`, `guia`) para poder priorizar.
- **Aprendizaje:** en RAG, más datos no siempre es mejor. Lo que entra al índice es una decisión de diseño.

## 11. Un error envuelto rompía la rotación de keys

- **Hallazgo:** la rotación de keys no se activó la primera vez que se agotó la cuota de embeddings.
- **Causa:** LangChain envuelve el error 429 de Google en su propia excepción, y mi código solo atrapaba la excepción original.
- **Qué hice:** detectar el error por su contenido (`RESOURCE_EXHAUSTED`) y no por su tipo.

## 12. Decisión de diseño: no traducir en tiempo real para Jev

- **Contexto:** Jev (TypeSafe) da decisiones tipadas con probabilidades calibradas, ideal para el router y la rúbrica, pero rinde mejor en inglés.
- **Decisión:** no traducir lo que dice el estudiante, porque sumaría ~0,7 s por turno y puede deformar términos médicos. Las preguntas fijas de Jev, en cambio, se traducen una sola vez. La variante final se elige con un eval contra Gemini como juez.

---

## Versión corta para LinkedIn

> Estoy construyendo **Chiron**, un simulador de pacientes con IA para que estudiantes de medicina practiquen el ECOE (el examen clínico práctico). Lo más interesante no fue hacer hablar al paciente, sino **medir que se comporte como debe**.
>
> Con evals en LangSmith encontré que, ante "¿toma alguna medicación?", el paciente contestaba también que había dejado el tratamiento del colesterol: justo un ítem que el estudiante tiene que saber preguntar. La clave fue pedirle al modelo que devuelva qué hechos del caso usó, no solo qué dijo. Eso convirtió "no adelantes información" en una métrica que se chequea con código.
>
> El mismo eval, corriendo en paralelo, agotó las 3 API keys en el mismo minuto: una prueba de carga gratis que reveló un bug de producción antes que cualquier usuario.
>
> Stack: Python, LangGraph, LangChain, Gemini, Chroma, LangSmith.
