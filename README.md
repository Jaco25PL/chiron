# Chiron — Product Brief

## Nombre

Chiron, por el centauro de la mitología griega que enseñó medicina a Asclepio, el dios de la medicina, y formó a otros grandes sanadores. Era el maestro de los médicos. Chiron no cura pacientes: forma a quienes los van a curar, igual que este producto.

## Problema

Los estudiantes de salud necesitan practicar entrevistas clínicas, pero practicar con pacientes reales o actores (pacientes estandarizados) es caro, limitado y depende de horarios. Muchos llegan a la práctica real con poca experiencia y sin feedback.

## Usuario

Estudiantes de medicina o enfermería que preparan entrevistas clínicas y exámenes prácticos.

## Solución

Un paciente virtual por videollamada al que el estudiante le hace la anamnesis y "examina", como en una consulta real. Al final recibe feedback sobre qué preguntó bien y qué se le pasó.

## Propuesta de valor

Practicar cuando quieras, las veces que quieras, con casos variados y feedback inmediato.

## Objetivos

- **Del producto:** que la práctica se sienta realista y el feedback sea útil.
- **Personal:** demostrar que sé construir y testear un sistema de AI de punta a punta.

## Alcance del MVP

- Videollamada con un paciente virtual
- 2–3 casos clínicos ficticios
- Examen físico simulado (presión, auscultación, laboratorio)
- Feedback final con rúbrica
- Evals de calidad del agente

## Arquitectura

Ver [ARCHITECTURE.md](ARCHITECTURE.md) (borrador tentativo).

## Hallazgos

Lo que fui encontrando al construirlo (evals, latencia, datos, bugs): [docs/HALLAZGOS.md](docs/HALLAZGOS.md).

## Decisiones de diseño

### Jev en español, sin traducción en tiempo real

[Jev](https://typesafe.ai/) (TypeSafe) es un modelo de decisiones tipadas con probabilidades calibradas, pensado para el router del grafo y para evaluar ítem por ítem la rúbrica. Su documentación indica que el inglés es el idioma donde rinde mejor, así que consideré traducir al inglés lo que dice el estudiante antes de pasárselo. **Lo descarté:**

- **Latencia:** suma una llamada extra (unos 0,7 s) en cada turno del router, y en una videollamada cada décima cuenta.
- **Errores:** la traducción puede deformar términos médicos, por ejemplo "disnea paroxística nocturna" o edemas "gravitacionales", justo lo que la rúbrica tiene que detectar.

En su lugar, las preguntas y criterios de Jev, que son fijos y los escribimos nosotros, pueden traducirse una sola vez, sin costo en tiempo real. La elección se decide con un eval que compara tres variantes contra Gemini como juez:

1. todo en español
2. criterios en inglés y transcripción en español
3. todo traducido
