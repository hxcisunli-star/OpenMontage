"""Safety net for every change to the whiteboard composer (remotion-composer/src): render the same fixed still frames of published lessons before and after and compare the PNG bytes.

  .venv/bin/python docs/whiteboard_whiteboard_baseline_stills.py render <tag>        render into projects/_baseline/<tag>/<lesson>/  (mirror projects: nothing is written into the lessons)
  .venv/bin/python docs/whiteboard_whiteboard_baseline_stills.py compare <a> <b>     byte-compare two tags, print a table, exit 1 on any difference

The reference set is projects/_baseline/ref (226 stills of 5 lessons, made 2026-10-21 BEFORE the colour/animation upgrade of the composer; after the upgrade the final code still reproduced it
byte for byte, and two runs of unchanged code are byte-identical, so a difference means the change, not the renderer).  Workflow: change the composer, `render new`, `compare ref new`; a
deliberate change of how old boards look means making a new reference (render it from the OLD code first - stash the change) and saying so in the registry.
The times are the whiteboard_render.key_times of every whiteboard cut thinned to at most PER_LESSON per lesson, plus every board's first and last frames (enter spring, exit fade) and the
middle of a write / stroke / image reveal, an array swap and a memory copy (the pen moves in all of them), so the in-between maths is covered, not only finished states.  Lessons: write, stroke,
image, array, code, memory items and a picture-sequence cut.  Only cuts with a whiteboard are sampled (the picture-sequence cut itself is not, only its edges)."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/MyProject/OpenMontage")
sys.path.insert(0, str(ROOT / "docs")); sys.path.insert(0, str(ROOT))
BASE = ROOT / "projects/_baseline"
LESSONS = ["bubble-sort-tutorial-cn", "c-stack-cn", "c-clinic-cn", "c-pointer-basics-cn", "agent-messages-cn"]
PER_LESSON = 9
MID_PER_KIND = 4


def thin(seq, n):
    seq = sorted(seq)
    if len(seq) <= n:
        return seq
    step = (len(seq) - 1) / (n - 1)
    return sorted({seq[round(i * step)] for i in range(n)})


def times_for(lesson):
    """Completed states (key_times) + the in-between frames the burst logic never samples: each board's first frames (enter spring) and last frames (exit fade),
    and the middle of a write / stroke / image reveal, an array swap and a memory copy (the pen moves in all of them)."""
    import whiteboard_render as wr          # chdirs to ROOT on import
    props = json.loads((ROOT / "projects" / lesson / "render_props.json").read_text(encoding="utf-8"))
    tl = ROOT / "projects" / lesson / "assets/audio/narration_timeline.json"
    quiz = json.loads(tl.read_text(encoding="utf-8")).get("quiz", []) if tl.exists() else []
    cuts = [c for c in props["cuts"] if c.get("whiteboard")]
    done = thin({t for c in cuts for t in wr.key_times(c, quiz)}, PER_LESSON)
    edge = []
    for c in cuts:
        edge += [float(c["in_seconds"]) + 0.15, float(c["in_seconds"]) + 0.45, float(c["out_seconds"]) - 0.2]
    mids = {"write": [], "stroke": [], "image": [], "swap": [], "copy": []}
    for c in cuts:
        base = float(c["in_seconds"])
        for it in c["whiteboard"].get("items", []):
            k, at = it.get("kind"), it.get("at", 0) or 0
            if k in ("write", "stroke", "image") and at >= 0:
                chars = len(it.get("text", "")) if k == "write" else 0
                dur = it.get("dur") or (max(0.6, chars * 0.12) if k == "write" else (0.7 if k == "stroke" else 1.2))
                mids[k].append(base + at + dur / 2)
            elif k == "array":
                for op in it.get("ops", []):
                    if op.get("type") == "swap":
                        mids["swap"].append(base + op["at"] + op.get("dur", 0.9) / 2)
            elif k == "memory":
                for cell in it.get("cells", []):
                    if cell.get("from"):
                        mids["copy"].append(base + cell["at"] + 0.5 + cell.get("copyDur", 1.0) / 2)
    mid = [t for v in mids.values() for t in thin(v, MID_PER_KIND)] if any(mids.values()) else []
    return sorted({round(t, 1) for t in done + edge + mid})


def render(tag):
    out = BASE / tag
    shutil.rmtree(out, ignore_errors=True)
    for lesson in LESSONS:
        mirror = BASE / f"_mirror_{lesson}"
        (mirror).mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "projects" / lesson / "render_props.json", mirror / "render_props.json")
        tl = ROOT / "projects" / lesson / "assets/audio/narration_timeline.json"
        if tl.exists():
            (mirror / "assets/audio").mkdir(parents=True, exist_ok=True); shutil.copy(tl, mirror / "assets/audio/narration_timeline.json")
        ts = times_for(lesson)
        (out / lesson).mkdir(parents=True)
        (out / lesson / "times.json").write_text(json.dumps(ts), encoding="utf-8")
        cmd = [str(ROOT / ".venv/bin/python"), str(ROOT / "docs/whiteboard_render.py"), str(mirror), "--local", "--no-lint", "--stills"] + [str(t) for t in ts]
        print(lesson, len(ts), "stills", flush=True)
        subprocess.run(cmd, check=True, cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": "."})
        for p in (mirror / "renders/stills").glob("*.png"):
            shutil.move(str(p), out / lesson / p.name)
        shutil.rmtree(mirror / "renders", ignore_errors=True)
    print("rendered into", out)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def compare(a, b):
    bad = total = 0
    for lesson in LESSONS:
        fa = {p.name: sha(p) for p in (BASE / a / lesson).glob("*.png")}
        fb = {p.name: sha(p) for p in (BASE / b / lesson).glob("*.png")}
        diff = [n for n in sorted(set(fa) | set(fb)) if fa.get(n) != fb.get(n)]
        total += len(fa); bad += len(diff)
        print(f"{lesson}: {len(fa)} stills before, {len(fb)} after, {len(diff)} differ {diff[:6]}")
    print(f"TOTAL {total} stills, {bad} differ")
    return 1 if bad or not total else 0


if __name__ == "__main__":
    if sys.argv[1] == "render":
        render(sys.argv[2])
    else:
        sys.exit(compare(sys.argv[2], sys.argv[3]))
