# Spec: clinical cases

A case is a fictional patient that the patient agent plays in an ECOE station. Each case is built **from one or more grillas** (official evaluation rubrics, in `data/ecoe/<materia>/grillas/`): everything the grilla expects the student to ask or examine must have an answer in the case.

File: `cases/<materia>/<id>.json`. Validation: `python cases/validate.py`.

## Principles

1. **The patient only answers what is asked** (see `data/ecoe/contexto-ecoe.md`). That's why the anamnesis (history) is a list of *revealable facts*, each with the answer in the patient's own words.
2. **Grilla coverage:** every gradable item in the case's grillas is covered by at least one fact, finding, or result. Items about the student's conduct (greeting, introducing themselves, asking permission, explaining, positioning the patient) and the overall performance item are exempt.
3. **Pertinent negatives:** if the grilla asks about something the patient does *not* have, there is still a fact with the negative answer ("No, palpitaciones no").
4. **Medical consistency:** the data (symptoms, values, findings) must be consistent with the diagnosis and with the subject's course notes (`data/ecoe/<materia>/clean/`). Sources used are cited.
5. **The patient doesn't know medicine:** answers use lay language ("me falta el aire cuando subo la escalera", not "disnea de esfuerzo clase II"). They may know the names of their conditions and medications, like any patient.
6. **The diagnosis is hidden:** it never appears in the patient's answers.
7. **Fictional:** made-up names and data. Uruguayan context (healthcare providers, neighborhoods, colloquialisms with voseo).

Case content (answers, findings, titles) is in Spanish, since that is what the student sees.

## Schema

```jsonc
{
  "id": "mpna-disnea-icc",                 // <materia>-<slug>, same as the file name
  "materia": "mpna",
  "titulo": "Disnea de esfuerzo progresiva",  // shown to the student (doesn't reveal the diagnosis)
  "grillas": ["02-disnea", "05-ex-fisico-cardiovascular"],
  "dificultad": "basico" | "intermedio" | "avanzado",

  "paciente": {                            // patient identification data (ficha patronímica)
    "nombre": "...", "edad": 67, "sexo": "masculino" | "femenino",
    "procedencia": "...", "domicilio": "...", "ocupacion": "...",
    "convivencia": "...", "escolaridad": "...", "estado_civil": "...",
    "prestador": "...", "medico_referencia": "..."
  },

  "personalidad": {
    "tipo": "nervioso" | "reservado" | "conversador" | "colaborador" | "demandante",
    "descripcion": "How they behave during the consultation",
    "forma_de_hablar": "Register, verbal tics, level of detail"
  },

  "motivo_consulta": {
    "frase_inicial": "What they say when asked what brings them in (with no further detail)"
  },

  // Facts the patient reveals ONLY when asked.
  "anamnesis": [
    {
      "id": "inicio",
      "tema": "Inicio y circunstancia de aparición de la disnea",
      "preguntas_ejemplo": ["¿Desde cuándo le pasa?", "¿Cómo empezó?"],
      "respuesta": "In the patient's words",
      "grilla_items": ["02-disnea::Pregunta inicio y circunstancia de aparición de la disnea"]
    }
  ],

  "signos_vitales": {
    "pa": "150/90 mmHg", "fc": "92 lpm", "fr": "20 rpm",
    "temperatura": "36,5 °C", "saturacion": "94 %", "peso": "...", "talla": "...", "imc": "..."
  },

  // What the examiner reports when the student performs (or mentions) the maneuver.
  "examen_fisico": [
    {
      "id": "choque-punta",
      "maniobra": "Palpación del choque de punta",
      "hallazgo": "Choque de punta en 6.º espacio intercostal, línea axilar anterior",
      "grilla_items": ["05-ex-fisico-cardiovascular::Busca choque de punta (LMC y 5to espacio intercostal a izq, descenso o lateralización)"]
    }
  ],

  // Paraclínica (lab and imaging studies): results handed over if the student orders them.
  "paraclinica": [
    {
      "estudio": "Tirilla reactiva de orina",
      "resultado": "...",
      "indicado": true,                    // true: indicated | false: not indicated | "opcional": reasonable, neither adds nor subtracts
      "justificacion": "Why it is or isn't indicated (for the feedback)",
      "grilla_items": []
    }
  ],

  // HIDDEN: used only by the feedback agent.
  "diagnostico": {
    "principal": "...",
    "diferenciales": ["..."],
    "fundamento": "Case data that leads to the diagnosis",
    "grilla_items": []                     // diagnostic reasoning items
  },
  // If the grilla grades management (treatment, warning signs, follow-up).
  "conducta_esperada": [
    { "accion": "Antibiótico empírico: ...", "grilla_items": ["..."] }
  ],

  "fuentes": [{ "archivo": "mpna-teorico.md", "seccion": "...", "pagina": 32 }]
}
```

### Grilla references

`grilla_items` uses the format `"<grilla_id>::<exact item text>"`, copied verbatim from the grilla JSON. This way the validator can check coverage and the feedback agent knows which fact maps to which item.
