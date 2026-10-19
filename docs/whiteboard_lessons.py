"""Lesson index for the whiteboard series: project directory <-> lesson number <-> title, read from the LESSONS list of docs/whiteboard_cover_maker.py
(every lesson already has a row there, so there is no second table to keep in sync). Imported by the other whiteboard tools."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ROW = re.compile(r'^\s*\("([^"]+)",\s*(\d+),\s*"([^"]*)"', re.M)


def lesson_table():
    """{project_dir_name: (number, title)} in lesson order."""
    text = (ROOT / "docs" / "whiteboard_cover_maker.py").read_text(encoding="utf-8")
    rows = [(m.group(1), int(m.group(2)), m.group(3)) for m in _ROW.finditer(text)]
    return {p: (n, t) for p, n, t in sorted(rows, key=lambda r: r[1])}


def project_of(number):
    for p, (n, _) in lesson_table().items():
        if n == number:
            return p
    return None


def number_of(project):
    return lesson_table().get(Path(project).name, (None, None))[0]


def title_of(project):
    return lesson_table().get(Path(project).name, (None, None))[1]
