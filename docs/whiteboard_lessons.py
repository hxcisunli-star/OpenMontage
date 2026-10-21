"""Lesson index for the whiteboard series: project directory <-> lesson number <-> title, read from the LESSONS list of docs/whiteboard_cover_maker.py
(every lesson already has a row there, so there is no second table to keep in sync). Imported by the other whiteboard tools.

Series: lesson numbers count inside a series.  The project name decides the series: `agent-...-cn` is the agent-development series (智能体篇, lesson 1 is its
first lesson); everything else (`c-...-cn`, `bubble-sort-tutorial-cn`) is the C series, which is what the tools assumed before series existed."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ROW = re.compile(r'^\s*\("([^"]+)",\s*(\d+),\s*"([^"]*)"', re.M)
SERIES_ORDER = ["c", "agent"]


def series_of(project):
    """'agent' for agent-...-cn projects, 'c' for the rest."""
    return "agent" if Path(project).name.startswith("agent-") else "c"


def lesson_table():
    """{project_dir_name: (number, title)} in series order, then lesson order."""
    text = (ROOT / "docs" / "whiteboard_cover_maker.py").read_text(encoding="utf-8")
    rows = [(m.group(1), int(m.group(2)), m.group(3)) for m in _ROW.finditer(text)]
    return {p: (n, t) for p, n, t in sorted(rows, key=lambda r: (SERIES_ORDER.index(series_of(r[0])), r[1]))}


def project_of(number, series="c"):
    for p, (n, _) in lesson_table().items():
        if n == number and series_of(p) == series:
            return p
    return None


def number_of(project):
    return lesson_table().get(Path(project).name, (None, None))[0]


def title_of(project):
    return lesson_table().get(Path(project).name, (None, None))[1]


def load_terms(series="c"):
    """Hard words for the narration of one series: {term: {from: lesson, allow_in: [lessons]}}.  The C series keeps the top-level `terms:`; other series have
    their own list under `series_terms:` in docs/whiteboard/wordlist.yaml (lesson numbers are per series, so the lists must not be mixed)."""
    import yaml
    data = yaml.safe_load((ROOT / "docs" / "whiteboard" / "wordlist.yaml").read_text(encoding="utf-8"))
    if series == "c":
        return data["terms"]
    return (data.get("series_terms") or {}).get(series, {})
