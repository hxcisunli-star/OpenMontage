"""Pre-render lint for whiteboard lessons: catch known board mistakes BEFORE a 45-minute render.

Run (OpenMontage root):  .venv/bin/python docs/whiteboard_lint.py projects/<lesson> [--props render_props.json]
Exit code 1 if any ERROR is found (WARN never fails).  whiteboard_render.py runs this automatically.

Checks (each one is a mistake we already paid for, see docs/whiteboard-course-playbook.zh-CN.md):
  ERROR  CJK / full-width characters in a monospace write or code line (the mono font has no CJK glyphs -> tofu squares)
  ERROR  digit 0 or a capital Latin letter in a hand-font write (hand font draws them as squares; write them in mono)
  ERROR  null value anywhere in a board item (`until: None` hides arrows / items)
  ERROR  vertical memory arrow between two cells with less than 88 px gap (short hand-drawn stroke arrows are fine)
  ERROR  a non-circle item starts inside a quiz silence (question_end+0.3 .. answer_not_before) -> answer shown too early
  WARN   other non-ASCII in mono text; non-ASCII memory-cell names; lowercase c/o in hand text; file-name / call / long Latin word mixed with Chinese in a hand-font write
  WARN   estimated text boxes that are visible at the same time and overlap (an ESTIMATE, only for `write` items: the measured check is docs/whiteboard_layout_check.py)
Reminders borrowed from huashu-art-motion (MIT, evaluated 2026-11-01; WARN only, the numbers are its author's measurements of other people's videos, not checked against our own cuts yet):
  WARN   a camera move (scale or centre differs from the previous key) without `kind` (缓推 / 拉远 / 横移 / 快推 / 砸入) or without `why` (what the viewer should look at now); a `kind` outside that list;
         a move whose length (this key's `at` minus the previous key's) is outside the range of its kind: 缓推 / 拉远 / 横移 0.6-1.5 s, 快推 0.25-0.35 s, 砸入 0.1-0.2 s
  WARN   hand-font writes longer than 8 characters (one WARN per cut): the board takes short words, long sentences belong to the narration and the subtitles
New optional fields (layer / move / rot / origin / fill / path / camera, see WhiteboardScene.tsx):
  ERROR  code `lang` other than "c" / "py"; layer other than "top"; a `move` key without a numeric `at`; a `path` stroke without a `d` string; a fill or fillOpacity that is not a colour string / a number
         in 0..1; a camera key with scale < 1 (the board edge would show) or without a numeric `at`
  WARN   a `path` stroke with a fill but no `box` (the tools cannot place it); a camera centre outside the canvas
  ERROR  a `move` key with a field the composer does not read (it reads at, dx, dy, scale, sy, rot; anything else, e.g. `sx`, is silently ignored: lesson 3's knob was squashed that way)
  ERROR  two or more pictures of the same character (layer "top", same name before the first "_": robot_, teacher_) visible together (opacity > 0.2) for more than 1.0 s (WARN from 0.4 s):
         a pose swap is a dissolve, longer means two poses stand on top of each other (lesson 3: an old pose whose `until` ran to the end of the board, 25 s; back-test 2026-11-05: lesson 1
         has a 2.8 s double teacher in K3).  An image always fades out over 0.4 s after its `until`, so end the old pose at least 0.2 s before the new one starts.
  WARN   text lying on a filled block whose contrast with the fill is too low (WCAG 4.5, 3.0 for text of 40 px and up; hex colours only; the topmost fill that is on the board at the same time counts)
"""
import json
import re
import sys
from pathlib import Path

CJK = re.compile(r"[\u2e80-\u9fff\uff00-\uffef\u3000-\u303f]")
MONO_SAFE = "\u2192\u2018\u2019\u201c\u201d\u2026\u00b7\u00d7\u2190\u2191\u2193"  # glyphs the mono font really has (seen rendered)
MIN_VERTICAL_GAP = 88
CAMERA_KINDS = {"缓推": (0.6, 1.5), "拉远": (0.6, 1.5), "横移": (0.6, 1.5), "快推": (0.25, 0.35), "砸入": (0.1, 0.2)}   # seconds a move of that kind takes
MAX_HAND_CHARS = 8
MIXED_LATIN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9]+|[A-Za-z_][A-Za-z0-9_]*\(|[A-Za-z]{5,}")  # name.ext, call(, or a long Latin word


HEX = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def _rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(c):
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x / 255) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def fill_box(it):
    """Bounding box of a filled stroke item (None when the tools cannot tell)."""
    sh = it.get("shape")
    try:
        if sh == "rect":
            return (it["x"], it["y"], it["x"] + it["w"], it["y"] + it["h"])
        if sh == "circle":
            return (it["cx"] - it["r"], it["cy"] - it["r"], it["cx"] + it["r"], it["cy"] + it["r"])
        if sh == "path" and it.get("box"):
            return tuple(it["box"])
    except (KeyError, TypeError):
        return None
    return None


MOVE_FIELDS = {"at", "dx", "dy", "scale", "sy", "rot"}


def check_new_fields(cid, it, where, errors, warns):
    kind = it.get("kind")
    if kind == "code" and "lang" in it and it["lang"] not in ("c", "py"):
        errors.append(f"{where(it)}: code `lang` must be \"c\" or \"py\" (got {it['lang']!r})")
    if "layer" in it and it["layer"] != "top":
        errors.append(f"{where(it)}: layer must be \"top\" (got {it['layer']!r})")
    for k in it.get("move") or []:
        if not isinstance(k, dict) or not isinstance(k.get("at"), (int, float)):
            errors.append(f"{where(it)}: a `move` key needs a numeric `at`: {k!r}")
        elif set(k) - MOVE_FIELDS:
            errors.append(f"{where(it)}: a `move` key has fields the composer does not read: {sorted(set(k) - MOVE_FIELDS)} (it reads only {sorted(MOVE_FIELDS)}; e.g. use `scale`, not `sx`)")
    if kind == "stroke":
        if it.get("shape") == "path":
            if not isinstance(it.get("d"), str) or not it.get("d").strip():
                errors.append(f"{where(it)}: a `path` stroke needs a `d` string")
            elif it.get("fill") and not it.get("box"):
                warns.append(f"{where(it)}: a filled `path` stroke without `box` (the tools cannot place it for the contrast and layout checks)")
        if "fill" in it and not isinstance(it["fill"], str):
            errors.append(f"{where(it)}: fill must be a colour string")
        fo = it.get("fillOpacity")
        if fo is not None and not (isinstance(fo, (int, float)) and 0 <= fo <= 1):
            errors.append(f"{where(it)}: fillOpacity must be a number in 0..1 (got {fo!r})")


def check_characters(cid, wb, length, errors, warns):
    """Two pictures of one character on the board at once (see the docstring): scan the cut in 0.05 s steps with the composer's opacity rules (fade-in easeInOut over `dur` for
    reveal "fade", fade-out linear over 0.4 s after `until`)."""
    def ease(x):
        x = min(max(x, 0.0), 1.0)
        return 2 * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 2 / 2
    groups = {}
    for it in wb.get("items", []):
        if it.get("kind") == "image" and it.get("layer") == "top":
            name = str(it.get("src", "")).rsplit("/", 1)[-1]
            if "_" in name:
                groups.setdefault(name.split("_", 1)[0], []).append(it)
    for kind, its in groups.items():
        if len(its) < 2:
            continue
        run0, worst, worst_t = None, 0.0, 0.0
        t = 0.0
        while t <= length:
            n = 0
            for it in its:
                at = float(it.get("at", 0) or 0)
                if it.get("reveal") == "fade":
                    p = 1.0 if at < 0 else ease((t - at) / max(float(it.get("dur", 1.2) or 1.2), 1e-6))
                else:
                    p = 1.0 if t >= at else 0.0
                u = it.get("until")
                f = 1.0 if u is None else min(max(1 - (t - float(u)) / 0.4, 0.0), 1.0)
                if p * f > 0.2:
                    n += 1
            if n >= 2:
                run0 = t if run0 is None else run0
                if t - run0 > worst:
                    worst, worst_t = t - run0, run0
            else:
                run0 = None
            t = round(t + 0.05, 2)
        if worst > 1.0:
            errors.append(f"{cid} @{worst_t:.1f}s: two or more '{kind}_' pictures are visible together for {worst:.2f} s (a pose swap is a dissolve of 0.4 s; end the old pose 0.2 s before the new one starts)")
        elif worst > 0.4:
            warns.append(f"{cid} @{worst_t:.1f}s: two '{kind}_' pictures are visible together for {worst:.2f} s (a pose swap is a dissolve of about 0.2 s; a longer one shows two characters)")


def check_camera(cid, wb, errors, warns):
    for k in wb.get("camera") or []:
        if not isinstance(k, dict) or not isinstance(k.get("at"), (int, float)):
            errors.append(f"{cid}: a camera key needs a numeric `at`: {k!r}")
            continue
        if k.get("scale") is not None and k["scale"] < 1:
            errors.append(f"{cid}: camera scale {k['scale']} < 1 would show the edge of the board")
        if (k.get("cx") is not None and not 0 <= k["cx"] <= 1920) or (k.get("cy") is not None and not 0 <= k["cy"] <= 1080):
            warns.append(f"{cid}: camera centre ({k.get('cx')}, {k.get('cy')}) is outside the canvas")
    keys = sorted((k for k in wb.get("camera") or [] if isinstance(k, dict) and isinstance(k.get("at"), (int, float))), key=lambda k: k["at"])
    untagged = []
    for prev, k in zip(keys, keys[1:]):
        kind = k.get("kind")
        if kind is not None and kind not in CAMERA_KINDS:
            warns.append(f"{cid} @{k['at']:.1f}s: camera kind {kind!r} is not one of {'／'.join(CAMERA_KINDS)}")
        same = lambda a, b: abs((a if a is not None else 1) - (b if b is not None else 1)) < 1e-6
        moved = not same(k.get("scale"), prev.get("scale")) or (k.get("cx") is not None and k.get("cx") != prev.get("cx")) or (k.get("cy") is not None and k.get("cy") != prev.get("cy"))
        if not moved:
            continue
        if not kind or not k.get("why"):
            untagged.append(f"@{k['at']:.1f}s")
        elif kind in CAMERA_KINDS:
            lo, hi = CAMERA_KINDS[kind]
            length = k["at"] - prev["at"]
            if not lo - 0.05 <= length <= hi + 0.05:
                warns.append(f"{cid} @{k['at']:.1f}s: {kind}用了 {length:.2f} 秒，常见范围是 {lo}-{hi} 秒（过渡用缓的，重音才用快的）")
    if untagged:
        warns.append(f"{cid}: {len(untagged)} 个镜头动作（{'、'.join(untagged)}）没写 kind（{'／'.join(CAMERA_KINDS)}）和 why（观众这一刻该看哪）：动镜头前先答“看哪、过渡还是重音、上一镜动作是什么”")


def _span(it):
    """(from, until) in cut seconds during which an item is on the board; a missing until means 'to the end', at < 0 means 'from the start'."""
    at = it.get("at", 0)
    return (-1e9 if at is None or at < 0 else float(at), float(it["until"]) if it.get("until") is not None else 1e9)


def _overlap(a, b):
    return min(a[1], b[1]) - max(a[0], b[0])


def check_contrast(cid, wb, base, warns):
    """Text whose estimated box lies on a filled block: ink on the (blended) fill must stay readable."""
    board = wb.get("boardColor") or "#FBFBF8"
    ink = wb.get("inkColor") or "#111827"
    if not HEX.match(board):
        return
    fills = []
    for it in wb.get("items", []):
        if it.get("kind") == "stroke" and it.get("fill") and HEX.match(it["fill"]) and fill_box(it):
            b = _rgb(board); f = _rgb(it["fill"]); a = float(it.get("fillOpacity", 1))
            fills.append((fill_box(it), tuple(round(a * f[i] + (1 - a) * b[i]) for i in range(3)), _span(it)))
    for it in wb.get("items", []):
        if it.get("kind") != "write" or not fills:
            continue
        text = it.get("text", "")
        size = float(it.get("size", 60)); mono = it.get("font") == "mono"
        w = est_w(text, size, mono)
        x0 = it["x"] - w / 2 if it.get("align") == "center" else it["x"]
        cx, cy = x0 + w / 2, it["y"] + size * 0.6
        col = it.get("color") or ink
        if not HEX.match(col):
            continue
        for (bx0, by0, bx1, by1), blended, fspan in reversed(fills):   # the topmost fill under the text counts (a note lying on a big block)
            if bx0 <= cx <= bx1 and by0 <= cy <= by1 and _overlap(fspan, _span(it)) > 0.3:   # ... that is there at the same time as the text
                ratio = contrast(_rgb(col), blended)
                need = 3.0 if size >= 40 else 4.5
                if ratio < need:
                    warns.append(f"{cid} @{base + float(it.get('at', 0) or 0):.1f}s: text {text[:20]!r} ({col}) on a fill of {'#%02X%02X%02X' % blended} has contrast {ratio:.1f} (< {need})")
                break


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
        check_camera(cid, wb, errors, warns)
        check_characters(cid, wb, float(cut.get("out_seconds", 0) or 0) - base, errors, warns)
        check_contrast(cid, wb, base, warns)
        boxes = []  # (x0, y0, x1, y1, t0, t1, label)
        long_hand = []
        for it in wb.get("items", []):
            kind = it.get("kind")
            check_new_fields(cid, it, where, errors, warns)
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
                    if len(text.replace(" ", "")) > MAX_HAND_CHARS:
                        long_hand.append(text)
                    if CJK.search(text) and MIXED_LATIN.search(text):  # lesson 40: `list.txt` written in the hand font next to Chinese looked wrong; split into hand + mono
                        warns.append(f"{where(it)}: file name / call / code-like Latin mixed into a CJK hand-font write; split it into hand text + a mono write: {text!r}")
                size = float(it.get("size", 60))
                w = est_w(text, size, mono) * (1.1 if mono else 1.0)
                x0 = it["x"] - w / 2 if it.get("align") == "center" else it["x"]
                t1 = it.get("until", 1e9) if it.get("until") is not None else 1e9
                if not it.get("move"):   # an item that moves has no fixed place to estimate: the measured layout check sees where it really is
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
        if long_hand:
            longest = max(long_hand, key=len)
            warns.append(f"{cid}: {len(long_hand)} 条手写文字超过 {MAX_HAND_CHARS} 字（最长 {len(longest.replace(' ', ''))} 字：{longest[:16]!r}）。板上写短词，长句交给旁白和字幕；确有必要就留着（这只是提醒）")
        # simultaneous text overlap (estimates only)
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[4] < b[5] and b[4] < a[5]:  # visible at the same time
                    ox = min(a[2], b[2]) - max(a[0], b[0]); oy = min(a[3], b[3]) - max(a[1], b[1])
                    if ox > 12 and oy > 12:
                        warns.append(f"{cid} @{base + max(a[4], b[4]):.1f}s: text boxes overlap ({ox:.0f}x{oy:.0f}px): {a[6]!r} / {b[6]!r} (ESTIMATED from character counts; docs/whiteboard_layout_check.py measures the real boxes)")
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
