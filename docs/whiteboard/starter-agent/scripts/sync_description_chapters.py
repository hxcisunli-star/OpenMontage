"""E105: after docs/whiteboard_prepend_cover.py the chapter lines at the end of exports/metadata/description.txt are the old (not shifted) times, while chapters.txt and metadata.json carry the shifted ones.
Rewrite the part after "章节时间轴：" from chapters.txt and assert that the three files agree.  Idempotent.  Run (repo root): .venv/bin/python projects/<lesson>/scripts/sync_description_chapters.py"""
import json
from pathlib import Path

M = Path(__file__).resolve().parents[1] / "exports/metadata"
ch = [l for l in (M / "chapters.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
assert ch, "chapters.txt is empty"
d = (M / "description.txt").read_text(encoding="utf-8")
key = "章节时间轴：\n\n"
assert d.count(key) == 1
d = d.split(key)[0] + key + "\n".join(ch) + "\n"
(M / "description.txt").write_text(d, encoding="utf-8")
meta = json.loads((M / "metadata.json").read_text(encoding="utf-8"))
fmt = lambda s: f"{int(s) // 60}:{int(s) % 60:02d}"
assert ch == [f"{fmt(c['start_seconds'])} - {c['title']}" for c in meta["chapters"]], "chapters.txt and metadata.json disagree"
assert meta["description"].split("章节时间轴：")[0] == d.split("章节时间轴：")[0], "description text differs between description.txt and metadata.json"
print("description.txt chapter lines now match chapters.txt and metadata.json:", ch)
