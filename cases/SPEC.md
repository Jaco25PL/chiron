# Spec: casos clínicos

Un caso es un paciente ficticio que el agente paciente interpreta en una estación del ECOE. Cada caso se arma **a partir de una o más grillas** (`data/ecoe/<materia>/grillas/`): todo lo que la grilla espera que el estudiante pregunte o examine tiene que tener una respuesta en el caso.

Archivo: `cases/<materia>/<id>.json`. Validación: `python cases/validate.py`.

## Principios

1. **El paciente solo responde lo que se le pregunta** (ver `data/ecoe/contexto-ecoe.md`). Por eso la anamnesis es una lista de *hechos revelables*, cada uno con la respuesta en palabras del paciente.
2. **Cobertura de la grilla:** cada ítem evaluable de las grillas del caso está cubierto por al menos un hecho, hallazgo o resultado. Quedan exentos los ítems de conducta del estudiante (saludar, presentarse, pedir permiso, explicar, posicionar) y el rendimiento global.
3. **Negativos pertinentes:** si la grilla pregunta por algo que el paciente *no* tiene, igual hay un hecho con la respuesta negativa ("No, palpitaciones no").
4. **Consistencia médica:** los datos (síntomas, valores, hallazgos) tienen que ser coherentes con el diagnóstico y con los apuntes de la materia (`data/ecoe/<materia>/clean/`). Se citan las fuentes usadas.
5. **El paciente no sabe medicina:** las respuestas usan lenguaje de paciente ("me falta el aire cuando subo la escalera", no "disnea de esfuerzo clase II"). Puede saber el nombre de sus enfermedades y medicamentos, como cualquier paciente.
6. **El diagnóstico está oculto:** nunca aparece en las respuestas del paciente.
7. **Ficticio:** nombres y datos inventados. Contexto uruguayo (prestadores, barrios, modismos con voseo).

## Esquema

```jsonc
{
  "id": "mpna-disnea-icc",                 // <materia>-<slug>, igual al nombre del archivo
  "materia": "mpna",
  "titulo": "Disnea de esfuerzo progresiva",  // visible para el estudiante (no revela el diagnóstico)
  "grillas": ["02-disnea", "05-ex-fisico-cardiovascular"],
  "dificultad": "basico" | "intermedio" | "avanzado",

  "paciente": {                            // ficha patronímica
    "nombre": "...", "edad": 67, "sexo": "masculino" | "femenino",
    "procedencia": "...", "domicilio": "...", "ocupacion": "...",
    "convivencia": "...", "escolaridad": "...", "estado_civil": "...",
    "prestador": "...", "medico_referencia": "..."
  },

  "personalidad": {
    "tipo": "nervioso" | "reservado" | "conversador" | "colaborador" | "demandante",
    "descripcion": "Cómo se comporta en la consulta",
    "forma_de_hablar": "Registro, muletillas, nivel de detalle"
  },

  "motivo_consulta": {
    "frase_inicial": "Lo que dice cuando le preguntan qué lo trae (sin dar más detalles)"
  },

  // Hechos que el paciente revela SOLO si se los preguntan.
  "anamnesis": [
    {
      "id": "inicio",
      "tema": "Inicio y circunstancia de aparición de la disnea",
      "preguntas_ejemplo": ["¿Desde cuándo le pasa?", "¿Cómo empezó?"],
      "respuesta": "En palabras del paciente",
      "grilla_items": ["02-disnea::Pregunta inicio y circunstancia de aparición de la disnea"]
    }
  ],

  "signos_vitales": {
    "pa": "150/90 mmHg", "fc": "92 lpm", "fr": "20 rpm",
    "temperatura": "36,5 °C", "saturacion": "94 %", "peso": "...", "talla": "...", "imc": "..."
  },

  // Lo que el docente informa cuando el estudiante hace (o menciona) la maniobra.
  "examen_fisico": [
    {
      "id": "choque-punta",
      "maniobra": "Palpación del choque de punta",
      "hallazgo": "Choque de punta en 6.º espacio intercostal, línea axilar anterior",
      "grilla_items": ["05-ex-fisico-cardiovascular::Busca choque de punta (LMC y 5to espacio intercostal a izq, descenso o lateralización)"]
    }
  ],

  // Resultados que se entregan si el estudiante los pide.
  "paraclinica": [
    {
      "estudio": "Tirilla reactiva de orina",
      "resultado": "...",
      "indicado": true,                    // true: corresponde | false: no corresponde | "opcional": razonable, no suma ni resta
      "justificacion": "Por qué corresponde o no (para el feedback)",
      "grilla_items": []
    }
  ],

  // OCULTO: solo lo usa el agente de feedback.
  "diagnostico": {
    "principal": "...",
    "diferenciales": ["..."],
    "fundamento": "Datos del caso que llevan al diagnóstico",
    "grilla_items": []                     // ítems de planteo diagnóstico
  },
  // Si la grilla evalúa la conducta (tratamiento, signos de alarma, control).
  "conducta_esperada": [
    { "accion": "Antibiótico empírico: ...", "grilla_items": ["..."] }
  ],

  "fuentes": [{ "archivo": "mpna-teorico.md", "seccion": "...", "pagina": 32 }]
}
```

### Referencias a la grilla

`grilla_items` usa el formato `"<grilla_id>::<texto exacto del ítem>"`, copiado literal del JSON de la grilla. Así el validador verifica la cobertura y el agente de feedback sabe qué hecho corresponde a qué ítem.
