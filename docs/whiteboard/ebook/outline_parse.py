"""Parse the learning outline (projects/roadmap-agent-engineer/04-学习内容大纲/*.md) and its plain-language texts (review/plain/stages/*.json) into projects/_ebook/outline.json.
One record per unit (293 in outline v1.1): id, title, path, the outline fields (goal, points, prerequisites, skip, practice, check, sources, timeliness, whiteboard fit, job evidence) and the plain text.
The parser fails loudly (asserts) when a stage file does not have the unit count its own heading announces, or a unit has no plain text, so a silent gap cannot reach the ebook.
Run: .venv/bin/python docs/whiteboard/ebook/outline_parse.py"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTLINE = ROOT / "projects/roadmap-agent-engineer/04-学习内容大纲"
PLAIN = ROOT / "projects/roadmap-agent-engineer/review/plain/stages"
OUT = ROOT / "projects/_ebook/outline.json"
# stage file stem -> file of the plain texts
PLAIN_FILE = {"T1": "E", "T2": "P", "T3": "F", "T4": "M", "T5": "A"}
FIELD = re.compile(r"^- \*\*([^*]+)\*\*[：:]\s*(.*)$")
UNIT_ID = re.compile(r"\b([SEPFMA]\d*-[UX]\d+)\b")
SRC_ID = re.compile(r"\[(S-\d+)\]")
HEAD = re.compile(r"^#### ([SEPFMA]\d*-[UX]\d+)　(.+)$")


def parse_stage(path):
    stem = path.name.split("-")[0]
    lines = path.read_text(encoding="utf-8").splitlines()
    title_line = next(l for l in lines if l.startswith("# "))
    m = re.match(r"# (.+?)（(\d+) 个单元", title_line)
    assert m, f"{path.name}: the first heading must announce the unit count: {title_line!r}"
    stage = {"id": stem, "file": path.name, "title": m.group(1).strip(), "announced_units": int(m.group(2)), "notes": [], "units": []}
    cur, field = None, None
    for line in lines:
        h = HEAD.match(line)
        if h:
            cur = {"id": h.group(1), "title": h.group(2).strip(), "fields": {}}
            stage["units"].append(cur)
            field = None
            continue
        if cur is None:
            if line.startswith("> "):
                stage["notes"].append(line[2:].strip())
            continue
        f = FIELD.match(line)
        if f:
            field = f.group(1)
            cur["fields"][field] = f.group(2).strip()
        elif field and line.strip() and not line.startswith("#") and not line.startswith("---"):
            cur["fields"][field] += " " + line.strip()
    assert len(stage["units"]) == stage["announced_units"], f"{path.name}: heading says {stage['announced_units']} units, found {len(stage['units'])}"
    return stage


def shape(unit, plain):
    f = unit["fields"]
    wb = f.get("白板课", "")
    return {
        "id": unit["id"], "title": unit["title"], "path": f.get("路径", ""),
        "goal": f.get("目标", ""), "points": f.get("要点", ""), "prereq_raw": f.get("前置", ""), "prereq": UNIT_ID.findall(f.get("前置", "")),
        "skip": f.get("跳过", ""), "practice": f.get("实践", ""), "check": f.get("检验", ""), "sources_raw": f.get("资料", ""),
        "source_ids": SRC_ID.findall(f.get("资料", "")) , "timeliness": f.get("时效", ""), "whiteboard": wb, "whiteboard_fit": wb.split("｜")[0].strip(),
        "job_evidence": f.get("岗位证据", ""),
        "plain": {k: plain[k] for k in ("plain_title", "what", "why", "analogy", "terms") if k in plain},
    }


def main():
    stages = []
    for path in sorted(OUTLINE.glob("*.md")):
        if path.name.startswith("00-"):
            continue
        stage = parse_stage(path)
        plain_name = PLAIN_FILE.get(stage["id"], stage["id"])
        plain = {u["id"]: u for u in json.loads((PLAIN / f"{plain_name}.json").read_text(encoding="utf-8"))["units"]}
        units = []
        for u in stage["units"]:
            assert u["id"] in plain, f"no plain text for {u['id']}"
            units.append(shape(u, plain[u["id"]]))
        assert all(u["path"] for u in units), f"{stage['id']}: a unit has no 路径 field"
        stage["units"] = units
        del stage["announced_units"]
        stages.append(stage)
    ids = [u["id"] for s in stages for u in s["units"]]
    assert len(ids) == len(set(ids)), "duplicate unit ids"
    assert len(ids) == 293, f"the frozen outline v1.1 has 293 units, found {len(ids)}"
    out = {"outline_version": "v1.1 (frozen 2026-10-27)", "unit_count": len(ids), "stages": stages}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(stages)} stages, {len(ids)} units")
    return 0


if __name__ == "__main__":
    sys.exit(main())
