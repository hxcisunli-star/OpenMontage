"""Pre-render lint for whiteboard lessons: catch known board mistakes BEFORE a 45-minute render.

Run (OpenMontage root):  .venv/bin/python docs/whiteboard_lint.py projects/<lesson> [--props render_props.json]
Exit code 1 if any ERROR is found (WARN never fails).  whiteboard_render.py runs this automatically.

Checks (each one is a mistake we already paid for, see docs/whiteboard-course-playbook.zh-CN.md):
  ERROR  CJK / full-width characters in a monospace write or code line (the mono font has no CJK glyphs -> tofu squares)
  ERROR  digit 0 or a capital Latin letter in a hand-font write (hand font draws them as squares; write them in mono)
  ERROR  null value anywhere in a board item (`until: None` hides arrows / items)
  ERROR  vertical memory arrow between two cells with less than 88 px gap (short hand-drawn stroke arrows are fine)
  ERROR  a non-circle item starts inside a quiz silence (question_end+0.3 .. answer_not_before) -> answer shown too early
  WARN   other non-ASCII in mono text; non-ASCII memory-cell names; lowercase c/o in hand text
  WARN   estimated text boxes that are visible at the same time and overlap
"""
import json
import re
import sys
from pathlib import Path

CJK = re.compile(r"[\u2e80-\u9fff\uff00-\uffef\u3000-\u303f]")
MONO_SAFE = "\u2192\u2018\u2019\u201c\u201d\u2026\u00b7\u00d7\u2190\u2191\u2193"  # glyphs the mono font really has (seen rendered)
MIN_VERTICAL_GAP = 88


def est_w(text, size, mono=False):
    w = 0.0
    for ch in text:
        w += size * (1.0 if ord(ch) > 0x2E7F else (0.6 if mono else 0.52))
    return w


def lint_props(props, quiz=None):
    errors, warns = [], []
    for cut in props.get("cuts", []):
        wb = cut.get("whiteboard")
        if not wb:
            continue
        cid, base = cut.get("id", "?"), float(cut.get("in_seconds", 0))

        def where(it, at=None):
            t = base + float(at if at is not None else it.get("at", 0) or 0)
            return f"{cid} @{t:.1f}s"

        def walk_null(node, path):
            if isinstance(node, dict):
                for k, v in node.items():
                    if v is None:
                        errors.append(f"{cid}: null value at {path}.{k} (an `until: None` hides the item)")
                    else:
                        walk_null(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk_null(v, f"{path}[{i}]")

        walk_null(wb, "whiteboard")
        boxes = []  # (x0, y0, x1, y1, t0, t1, label)
        for it in wb.get("items", []):
            kind = it.get("kind")
            if kind == "write":
                text = it.get("text", "")
                mono = it.get("font") == "mono"
                if mono:
                    if CJK.search(text):
                        errors.append(f"{where(it)}: CJK/full-width text in MONOSPACE write -> tofu: {text!r}")
                    elif re.search(r"[^\x00-\x7f" + MONO_SAFE + "]", text):
                        warns.append(f"{where(it)}: non-ASCII in monospace write: {text!r}")
                else:
                    if re.search(r"[0０A-Z]", text):
                        bad = "".join(sorted(set(re.findall(r"[0０A-Z]", text))))
                        errors.append(f"{where(it)}: {bad!r} in HAND-font write (drawn as squares; write in mono): {text!r}")
                    elif re.search(r"[co]", text):
                        warns.append(f"{where(it)}: lowercase c/o in hand-font write (square glyphs?): {text!r}")
                size = float(it.get("size", 60))
                w = est_w(text, size, mono) * (1.1 if mono else 1.0)
                x0 = it["x"] - w / 2 if it.get("align") == "center" else it["x"]
                t1 = it.get("until", 1e9) if it.get("until") is not None else 1e9
                boxes.append((x0, it["y"], x0 + w, it["y"] + size * 1.15, it["at"], t1, text))
            elif kind == "code":
                for ln in it.get("lines", []):
                    if CJK.search(ln):
                        errors.append(f"{where(it)}: CJK/full-width text in code line -> tofu: {ln!r}")
            elif kind == "memory":
                cells = {c["id"]: c for c in it.get("cells", [])}
                for c in cells.values():
                    if re.search(r"[^\x00-\x7f]", c.get("name", "")):
                        warns.append(f"{where(c)}: non-ASCII memory-cell name {c.get('name')!r} (cell names should be Latin)")
                for a in it.get("arrows", []):
                    f, t = cells.get(a["from"]), cells.get(a["to"])
                    if not f or not t:
                        errors.append(f"{where(a)}: memory arrow {a.get('from')}->{a.get('to')} references an unknown cell")
                        continue
                    fx, fy = f["x"] + f.get("w", 170) / 2, f["y"] + f.get("h", 130) / 2
                    tx, ty = t["x"] + t.get("w", 170) / 2, t["y"] + t.get("h", 130) / 2
                    if abs(ty - fy) > abs(tx - fx):
                        gap = abs(ty - fy) - f.get("h", 130) / 2 - t.get("h", 130) / 2
                        if gap < MIN_VERTICAL_GAP:
                            errors.append(f"{where(a)}: vertical memory arrow {a['from']}->{a['to']} gap {gap:.0f}px (< {MIN_VERTICAL_GAP})")
        # simultaneous text overlap (estimates only)
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[4] < b[5] and b[4] < a[5]:  # visible at the same time
                    ox = min(a[2], b[2]) - max(a[0], b[0]); oy = min(a[3], b[3]) - max(a[1], b[1])
                    if ox > 12 and oy > 12:
                        warns.append(f"{cid} @{base + max(a[4], b[4]):.1f}s: text boxes overlap ({ox:.0f}x{oy:.0f}px): {a[6]!r} / {b[6]!r}")
        # quiz silence: nothing but countdown circles may start inside the silence
        for q in quiz or []:
            lo, hi = q["question_end"] + 0.3, q["answer_not_before"] - 0.05
            for it in wb.get("items", []):
                if it.get("kind") == "memory":
                    continue
                t = base + float(it.get("at", 0) or 0)
                if lo <= t < hi and not (it.get("kind") == "stroke" and it.get("shape") == "circle"):
                    errors.append(f"{where(it)}: starts inside the quiz silence {q['question_end']:.2f}-{q['answer_not_before']:.2f} (answer too early?)")
    return errors, warns


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return 2
    proj = Path(args[0])
    props_name = args[args.index("--props") + 1] if "--props" in args else "render_props.json"
    props = json.loads((proj / props_name).read_text(encoding="utf-8"))
    tl = proj / "assets/audio/narration_timeline.json"
    quiz = json.loads(tl.read_text(encoding="utf-8")).get("quiz", []) if tl.exists() else []
    errors, warns = lint_props(props, quiz)
    for w in warns:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"lint: {len(errors)} error(s), {len(warns)} warning(s), {len(props.get('cuts', []))} cuts, {len(quiz)} quiz marks")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
