#!/usr/bin/env python3
"""Create the project skeleton of a new whiteboard lesson (run it only AFTER the user said "计划确认").
Run (repo root):  .venv/bin/python docs/whiteboard_new_lesson.py --pid c-xxx-cn --n 44 --title "课名" [--from c-clinic-cn] [--dry-run] [--projects-dir projects]
It replaces the hand-run steps "init_project, mkdir -p ..., cp the previous lesson's scripts, sed the project name" (which left a stale name in 41-43's render_stills.py,
a missing assets/captions, and a copied finish_compose.py that overwrote another lesson's files once):
  1. lib.checkpoint.init_project + code validation scripts assets/images assets/captions review references artifacts exports
  2. the series' cast pictures: from its cast library when docs/whiteboard/series.yaml gives one (cast_dir: teacher + AI partner poses, school logo, reference pictures for new poses),
     otherwise (the C series) the doctor images and the school logo of the source lesson
  3. the never-changing scripts from docs/whiteboard/starter/scripts (placeholders __PID__ / __N__ replaced; rebuild_edit.sh already runs last_item_check)
  4. the lesson-specific scripts (plan_stage, build_script, build_scene_plan, _body_boards, _build_tail, sample_voice, finish_assets, publish_prep, make_exercises, run_*.sh) copied from the
     source lesson with its project name / lesson number replaced; build_script.py reads the hard words from docs/whiteboard/wordlist.yaml (NEW_TERMS = this lesson's new terms);
     publish_prep.py refuses a thumbnail time that is not fully drawn (docs/whiteboard_thumb_check.py)
  5. experiment labels: a template lesson that is an experiment (EXPERIMENT.md: "试验品 / 技术测试 / 不属于课程") has those words in its publish scripts, exercises and title. A copied script that
     carries them gets a guard as its first statement that stops it until it is rewritten for the new lesson - otherwise the first real lesson of a series would be published labelled as an experiment
  6. scan: any OTHER lesson's project name or the source lesson number left in the new scripts is listed (content to rewrite or a stale copy), and every .py must still compile.
Nothing is rendered, generated or run."""
import argparse
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from whiteboard_lessons import lesson_table, series_config, series_of  # noqa: E402

STARTER = ROOT / "docs/whiteboard/starter/scripts"
SPECIFIC = ["plan_stage.py", "build_script.py", "build_scene_plan.py", "_body_boards.py", "_build_tail.py", "sample_voice.py", "finish_assets.py", "publish_prep.py",
            "make_exercises.py", "run_exercises.sh", "run_validation.sh"]
LEGACY_ASSETS = ["assets/images/doctor_holding_note.png", "assets/images/doctor_pointing.png", "assets/images/schoollogo.png", "references/ref_doctor.png"]   # the C series: copied from the source lesson
ASSETS = LEGACY_ASSETS
DIRS = ["code", "validation", "scripts", "assets/images", "assets/captions", "review", "references", "artifacts", "exports"]
D = "零一二三四五六七八九"


def cn(n):
    if n < 10:
        return D[n]
    if n < 20:
        return "十" + (D[n % 10] if n % 10 else "")
    return D[n // 10] + "十" + (D[n % 10] if n % 10 else "")


def cast_plan(cfg, srcdir):
    """[(source file, destination relative to the project)] of the cast pictures: the series' cast library when it has one, else the C series' doctor images from the source lesson."""
    if cfg["cast_dir"]:
        cd = ROOT / cfg["cast_dir"]
        plan = [(cd / f, f"assets/images/{f}") for f in cfg["cast_assets"]]
        plan += [(cd / rel, f"references/{dst}") for dst, rel in (cfg.get("cast_references") or {}).items()]
        return plan
    return [(srcdir / rel, rel) for rel in LEGACY_ASSETS]


EXP_LABELS = re.compile(r"试验品|技术测试|不属于课程|EXPERIMENT")
EXP_CONTENT = re.compile(r"HyperFrames|hyperframes|frame_seq|\bK4b\b|Clip\(")   # content of the experiment lesson's boards (a picture-sequence clip), not a label: to be rewritten


def guard(name, text):
    """A copied script that still carries experiment labels stops until it is rewritten.  Returns the guarded text (or the text unchanged when it carries none)."""
    if not EXP_LABELS.search(text):
        return text, False
    msg = (f"{name} was copied from an EXPERIMENT (试验品 / 技术测试 / 不属于课程) and still carries its labels, title, description or tags: rewrite it for THIS lesson, then delete this guard line")
    if name.endswith(".sh"):
        lines = text.split("\n")
        at = 1 if lines and lines[0].startswith("#!") else 0
        lines.insert(at, f"echo {msg!r} >&2; exit 1   # NEW-LESSON GUARD")
        return "\n".join(lines), True
    return f"raise SystemExit({msg!r})   # NEW-LESSON GUARD\n" + text, True


def patch_build_script(text, n, series="c"):
    # the C series keeps the top-level `terms:`; lesson numbers count from 1 inside each series, so every other series has its own list under `series_terms:`
    terms = '["terms"]' if series == "c" else f'.get("series_terms", {{}}).get("{series}", {{}})'
    default_from = 11 if series == "c" else 1
    forb = re.compile(r"^FORB = \[.*?\]\s*$", re.M | re.S)
    jarg = re.compile(r"^JARGON = \[.*?\]\s*$", re.M | re.S)
    if not (forb.search(text) and jarg.search(text)):
        return text, False
    block = (f"LESSON = {n}\n"
             "NEW_TERMS = []   # 本课要教的新词：写在这里就不算难词（旁白里点名一次并配大白话）；复盘时把本课号加进 docs/whiteboard/wordlist.yaml 的 allow_in\n"
             "import yaml as _yaml\n"
             f"_WL = _yaml.safe_load((ROOT / \"docs/whiteboard/wordlist.yaml\").read_text(encoding=\"utf-8\")){terms}\n"
             f"FORB = [w for w, s in _WL.items() if LESSON >= s.get(\"from\", {default_from}) and LESSON not in (s.get(\"allow_in\") or []) and w not in NEW_TERMS]  # 难词与禁词只存一份：docs/whiteboard/wordlist.yaml")
    text = forb.sub(lambda m: block, text, count=1)
    text = jarg.sub(lambda m: "JARGON = []   # 并入上面的 FORB（单一词表）", text, count=1)
    return text, True


def patch_publish_prep(text):
    rx = re.compile(r"^(THUMB_T = float\(os\.environ\.get\(\"THUMB_T\".*\)\)\s*)$", re.M)
    if not rx.search(text):
        return text, False
    guard = ("\nif subprocess.call([sys.executable, str(ROOT / \"docs/whiteboard_thumb_check.py\"), str(PROJ), str(THUMB_T)]):  # the frame must be fully drawn and not yet fading\n"
             "    sys.exit(\"pick THUMB_T from: python3 docs/whiteboard_thumb_check.py projects/<lesson> --list  (and still LOOK at the exported image)\")")
    return rx.sub(lambda m: m.group(1) + guard, text, count=1), True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pid", required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--from", dest="src")
    ap.add_argument("--projects-dir", default=str(ROOT / "projects"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not re.fullmatch(r"(c|agent)-[a-z0-9]+(-[a-z0-9]+)*-cn", a.pid):
        sys.exit("--pid must look like c-xxx-cn (C series) or agent-xxx-cn (agent series), kebab-case")
    series = series_of(a.pid)
    table = lesson_table()
    same = {p: v for p, v in table.items() if series_of(p) == series}   # lesson numbers count inside a series
    cfg = series_config(series)
    src = a.src or cfg["template_lesson"] or max(same or table, key=lambda p: (same or table)[p][0])   # a series names its template lesson in series.yaml; otherwise the latest lesson of its own series, else of the C series
    pdir = Path(a.projects_dir)
    srcdir, dst = pdir / src, pdir / a.pid
    if not (srcdir / "scripts").is_dir():
        sys.exit(f"source lesson {srcdir} has no scripts/")
    if dst.exists():
        sys.exit(f"{dst} already exists - refusing to touch it")
    if a.pid in table or any(v[0] == a.n for p, v in table.items() if series_of(p) == series):
        print(f"note: docs/whiteboard_cover_maker.py already has a row for {a.pid} or lesson {a.n} of the {series} series")
    src_n = table.get(src, (None,))[0]
    casts = cast_plan(cfg, srcdir)
    plan = [f"project {a.pid} (lesson {a.n}, {a.title!r}, {series} series) from {src} (lesson {src_n})", f"dirs: {DIRS}", f"cast pictures: {[d for _, d in casts]}",
            f"starter scripts: {sorted(p.name for p in STARTER.iterdir())}", f"lesson-specific scripts: {[f for f in SPECIFIC if (srcdir / 'scripts' / f).exists()]}"]
    if not cfg["name"]:
        plan.append(f"note: the {series} series has no name yet (docs/whiteboard/series.yaml name): covers and the release pack refuse to run until the user has chosen one")
    print("\n".join(plan))
    if a.dry_run:
        print("dry-run: nothing written")
        return 0
    os.chdir(ROOT)
    from lib.checkpoint import init_project
    init_project(a.pid, title=a.title, pipeline_type="animated-explainer", pipeline_dir=pdir, style_playbook="clean-professional")
    for d in DIRS:
        (dst / d).mkdir(parents=True, exist_ok=True)
    for from_, rel in casts:
        if from_.exists():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(from_, dst / rel)
        else:
            print("warning: no", from_)
    sc = dst / "scripts"
    for f in sorted(STARTER.iterdir()):
        text = f.read_text(encoding="utf-8").replace("__PID__", a.pid).replace("__N__", str(a.n))
        (sc / f.name).write_text(text, encoding="utf-8")
        if f.suffix == ".sh":
            (sc / f.name).chmod(0o755)
    notes = []
    for f in SPECIFIC:
        p = srcdir / "scripts" / f
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8").replace(src, a.pid)
        if src_n is not None:
            text = re.sub(rf"\b(Lesson|lesson) {src_n}\b", rf"\1 {a.n}", text)
        if f == "build_script.py":
            text, ok = patch_build_script(text, a.n, series)
            notes.append(("build_script.py wordlist", ok))
        if f == "publish_prep.py":
            text, ok = patch_publish_prep(text)
            notes.append(("publish_prep.py thumbnail guard", ok))
        text, guarded = guard(f, text)
        if guarded:
            notes.append((f"{f}: experiment labels -> GUARD at the top (rewrite for this lesson, then delete the guard line)", True))
        (sc / f).write_text(text, encoding="utf-8")
        if f.endswith(".sh"):
            (sc / f).chmod(0o755)
    for name, ok in notes:
        print(f"patch {name}: {'applied' if ok else 'NOT applied (pattern not found - do it by hand)'}")
    # scan
    other = [p for p in table if p != a.pid]
    rx_other = re.compile("|".join(re.escape(p) for p in sorted(other, key=len, reverse=True)))
    rx_num = re.compile(rf"第 ?{src_n} ?课|第{cn(src_n)}课|[Ll]esson {src_n}\b") if src_n else None
    bad, left = 0, []
    for f in sorted(sc.iterdir()):
        if f.suffix not in (".py", ".sh"):
            continue
        t = f.read_text(encoding="utf-8")
        o = rx_other.findall(t)
        nn = rx_num.findall(t) if rx_num else []
        if o or nn:
            left.append((f.name, sorted(set(o)), len(nn)))
        if f.suffix == ".py":
            try:
                compile(t, str(f), "exec")
            except SyntaxError as e:
                bad += 1
                print("SYNTAX ERROR in", f.name, e)
    for f in sorted(sc.iterdir()):
        if f.suffix == ".py" and EXP_CONTENT.search(f.read_text(encoding="utf-8")):
            print(f"  note: {f.name} still has the experiment lesson's picture-sequence clip (K4b / frame_seq / HyperFrames): content to rewrite, or delete if this lesson has no clip")
    if cfg["cast_dir"]:   # the template lesson's boards were drawn with another cast: its picture names are content to rewrite
        rx_cast = re.compile(r"doctor_\w+|ref_doctor")
        for f in sorted(sc.iterdir()):
            if f.suffix == ".py" and rx_cast.search(f.read_text(encoding="utf-8")):
                print(f"  note: {f.name} still names the C series' doctor pictures ({sorted(set(rx_cast.findall(f.read_text(encoding='utf-8'))))}): redraw with this series' cast ({[d for _, d in casts if d.startswith('assets/images/')][:4]} ...)")
    print("leftovers (other lessons' project names / the source lesson number) - rewrite or confirm each is intended:")
    for name, o, nn in left:
        print(f"  {name}: other project names {o or '-'}; source-lesson number mentions {nn}")
    print(f"created {dst}")
    print("next: read docs/whiteboard/checklists/01-plan.md; fill plan_stage.py (research + proposal), then stop at the proposal gate. Add the cover row (docs/whiteboard_cover_maker.py LESSONS) at the publish stage.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
