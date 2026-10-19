#!/usr/bin/env python3
"""Create the project skeleton of a new whiteboard lesson (run it only AFTER the user said "计划确认").
Run (repo root):  .venv/bin/python docs/whiteboard_new_lesson.py --pid c-xxx-cn --n 44 --title "课名" [--from c-clinic-cn] [--dry-run] [--projects-dir projects]
It replaces the hand-run steps "init_project, mkdir -p ..., cp the previous lesson's scripts, sed the project name" (which left a stale name in 41-43's render_stills.py,
a missing assets/captions, and a copied finish_compose.py that overwrote another lesson's files once):
  1. lib.checkpoint.init_project + code validation scripts assets/images assets/captions review references artifacts exports
  2. doctor images, school logo, hand font from the source lesson
  3. the never-changing scripts from docs/whiteboard/starter/scripts (placeholders __PID__ / __N__ replaced; rebuild_edit.sh already runs last_item_check)
  4. the lesson-specific scripts (plan_stage, build_script, build_scene_plan, _body_boards, _build_tail, sample_voice, finish_assets, publish_prep, make_exercises, run_*.sh) copied from the
     source lesson with its project name / lesson number replaced; build_script.py reads the hard words from docs/whiteboard/wordlist.yaml (NEW_TERMS = this lesson's new terms);
     publish_prep.py refuses a thumbnail time that is not fully drawn (docs/whiteboard_thumb_check.py)
  5. scan: any OTHER lesson's project name or the source lesson number left in the new scripts is listed (content to rewrite or a stale copy), and every .py must still compile.
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
from whiteboard_lessons import lesson_table  # noqa: E402

STARTER = ROOT / "docs/whiteboard/starter/scripts"
SPECIFIC = ["plan_stage.py", "build_script.py", "build_scene_plan.py", "_body_boards.py", "_build_tail.py", "sample_voice.py", "finish_assets.py", "publish_prep.py",
            "make_exercises.py", "run_exercises.sh", "run_validation.sh"]
ASSETS = ["assets/images/doctor_holding_note.png", "assets/images/doctor_pointing.png", "assets/images/schoollogo.png", "references/ref_doctor.png"]
DIRS = ["code", "validation", "scripts", "assets/images", "assets/captions", "review", "references", "artifacts", "exports"]
D = "零一二三四五六七八九"


def cn(n):
    if n < 10:
        return D[n]
    if n < 20:
        return "十" + (D[n % 10] if n % 10 else "")
    return D[n // 10] + "十" + (D[n % 10] if n % 10 else "")


def patch_build_script(text, n):
    forb = re.compile(r"^FORB = \[.*?\]\s*$", re.M | re.S)
    jarg = re.compile(r"^JARGON = \[.*?\]\s*$", re.M | re.S)
    if not (forb.search(text) and jarg.search(text)):
        return text, False
    block = (f"LESSON = {n}\n"
             "NEW_TERMS = []   # 本课要教的新词：写在这里就不算难词（旁白里点名一次并配大白话）；复盘时把本课号加进 docs/whiteboard/wordlist.yaml 的 allow_in\n"
             "import yaml as _yaml\n"
             "_WL = _yaml.safe_load((ROOT / \"docs/whiteboard/wordlist.yaml\").read_text(encoding=\"utf-8\"))[\"terms\"]\n"
             "FORB = [w for w, s in _WL.items() if LESSON >= s.get(\"from\", 11) and LESSON not in (s.get(\"allow_in\") or []) and w not in NEW_TERMS]  # 难词与禁词只存一份：docs/whiteboard/wordlist.yaml")
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
    if not re.fullmatch(r"c-[a-z0-9]+(-[a-z0-9]+)*-cn", a.pid):
        sys.exit("--pid must look like c-xxx-cn (kebab-case)")
    table = lesson_table()
    src = a.src or max(table, key=lambda p: table[p][0])
    pdir = Path(a.projects_dir)
    srcdir, dst = pdir / src, pdir / a.pid
    if not (srcdir / "scripts").is_dir():
        sys.exit(f"source lesson {srcdir} has no scripts/")
    if dst.exists():
        sys.exit(f"{dst} already exists - refusing to touch it")
    if a.pid in table or any(v[0] == a.n for v in table.values()):
        print(f"note: docs/whiteboard_cover_maker.py already has a row for {a.pid} or lesson {a.n}")
    src_n = table.get(src, (None,))[0]
    plan = [f"project {a.pid} (lesson {a.n}, {a.title!r}) from {src} (lesson {src_n})", f"dirs: {DIRS}", f"starter scripts: {sorted(p.name for p in STARTER.iterdir())}",
            f"lesson-specific scripts: {[f for f in SPECIFIC if (srcdir / 'scripts' / f).exists()]}"]
    print("\n".join(plan))
    if a.dry_run:
        print("dry-run: nothing written")
        return 0
    os.chdir(ROOT)
    from lib.checkpoint import init_project
    init_project(a.pid, title=a.title, pipeline_type="animated-explainer", pipeline_dir=pdir, style_playbook="clean-professional")
    for d in DIRS:
        (dst / d).mkdir(parents=True, exist_ok=True)
    for rel in ASSETS:
        if (srcdir / rel).exists():
            shutil.copy2(srcdir / rel, dst / rel)
        else:
            print("warning: source has no", rel)
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
            text, ok = patch_build_script(text, a.n)
            notes.append(("build_script.py wordlist", ok))
        if f == "publish_prep.py":
            text, ok = patch_publish_prep(text)
            notes.append(("publish_prep.py thumbnail guard", ok))
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
    print("leftovers (other lessons' project names / the source lesson number) - rewrite or confirm each is intended:")
    for name, o, nn in left:
        print(f"  {name}: other project names {o or '-'}; source-lesson number mentions {nn}")
    print(f"created {dst}")
    print("next: read docs/whiteboard/checklists/01-plan.md; fill plan_stage.py (research + proposal), then stop at the proposal gate. Add the cover row (docs/whiteboard_cover_maker.py LESSONS) at the publish stage.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
