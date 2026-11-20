"""rag/chunk.py structure_guide: MSP guideline headings from their real structure, no text lost."""

from rag.chunk import structure_guide

GUIDE = """### Edulcorante

INGESTA DIARIA ACEPTABLE

- ¿Cuál es el tratamiento farmacológico inicial en los pacientes con DM2?........ 47

- ¿Cuál es el tratamiento farmacológico inicial en los pacientes con DM2?

**Metformina**

Es el fármaco recomendado como primera elección.

**Recomendaciones**

Iniciar con 500 mg.

**Aspecto general Piel y mucosas**

**Bucofaringe Linfoganglionar y cuello**

Inspección.

- ¿Tiene DM?
"""


def test_table_headers_stop_being_headings_and_questions_and_subtitles_become_them():
    out = structure_guide(GUIDE).split("\n")
    assert "Edulcorante" in out and "### Edulcorante" not in out  # a table column header
    assert "## ¿Cuál es el tratamiento farmacológico inicial en los pacientes con DM2?" in out
    assert any(line.endswith("........ 47") and not line.startswith("#") for line in out)  # the index stays text
    assert "### Metformina" in out
    assert "**Recomendaciones**" in out  # generic label: not a section of its own
    assert "- ¿Tiene DM?" in out  # a short flowchart question isn't a section


def test_a_title_with_nothing_under_it_stays_text():
    """Stacked table headers: the splitter would drop an empty section together with its title."""
    out = structure_guide(GUIDE).split("\n")
    assert "**Aspecto general Piel y mucosas**" in out
    assert "### Bucofaringe Linfoganglionar y cuello" in out


def test_only_line_roles_change():
    # a promoted question drops its list dash ("- ¿...?" -> "## ¿...?"); nothing else may differ
    strip = lambda t: [l.lstrip("#").strip().strip("*").removeprefix("- ") for l in t.split("\n")]  # noqa: E731
    assert strip(structure_guide(GUIDE)) == strip(GUIDE)
