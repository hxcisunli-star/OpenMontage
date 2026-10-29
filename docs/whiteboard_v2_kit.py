"""Building blocks of the new-series style guide (projects/visual-upgrade-lab/artifacts/style_guide.md): palette, rounded boxes, sticky notes, chat bubbles, bars,
highlighter.  Everything is made of the board's own `stroke` / `write` items plus the optional fields of WhiteboardScene.tsx (fill, path, shadow, rot, origin, move,
sy), so no new board kind exists.

The functions only call `b.stroke(shape, at, dur, color=, width=, until=, **fields)` and `b.write(text, x, y, at, size=, dur=, color=, align=, until=, font=, **fields)`
on the board object they are given, and pass times through unchanged: the board decides whether times are absolute (the lessons' Board) or relative (RawBoard below).
A board used with this kit must hand unknown keyword fields (fill, box, d, shadow, layer, move, rot, origin) on to the item, and convert the `at` of `move` keys the way
it converts every other time.
"""

import math

PAL = {
    "board": "#FBFBF8", "ink": "#111827", "red": "#DC2626", "green": "#15803D", "yellow": "#FACC15",
    "user": "#E3CA9B", "program": "#1C3653", "model": "#56CBFD", "ai_line": "#093344",
    "note_yellow": "#FFF3A8", "note_blue": "#CDEBFA", "note_pink": "#FAD3D9", "note_green": "#D4F0D2",
    "model_block": "#DAF8FC",   # the robot's body colour (measured): sky-blue notes show up on it, they would melt into a sky-blue block
}
# role -> (fill, text colour, outline colour or None): who says / does it
ROLE = {
    "user": (PAL["user"], PAL["ink"], None),
    "program": (PAL["program"], "#FFFFFF", None),
    "model": (PAL["model"], PAL["ink"], PAL["ai_line"]),
}


def rrect_path(x, y, w, h, r):
    """A closed rounded rectangle as an SVG path (true circular corners)."""
    r = min(r, w / 2, h / 2)
    return (f"M {x + r} {y} L {x + w - r} {y} A {r} {r} 0 0 1 {x + w} {y + r} L {x + w} {y + h - r} A {r} {r} 0 0 1 {x + w - r} {y + h} "
            f"L {x + r} {y + h} A {r} {r} 0 0 1 {x} {y + h - r} L {x} {y + r} A {r} {r} 0 0 1 {x + r} {y} Z")


# role -> (fill, label colour, outline) of a big block: the program (navy, white label) or the model (the robot's light body colour with the dark outline)
BLOCK = {"program": (PAL["program"], "#FFFFFF", None), "model": (PAL["model_block"], PAL["ink"], PAL["ai_line"])}


def _move_kw(rot, origin, move, layer):
    kw = {}
    if rot:
        kw["rot"] = rot
    if origin is not None:
        kw["origin"] = list(origin)
    if move:
        kw["move"] = move
    if layer:
        kw["layer"] = layer
    return kw


def sticky(b, x, y, w, h, fill, lines, at, *, rot=0, move=None, dur=0.5, until=None, layer=None):
    """A tilted pastel note with a soft shadow.  `lines` = [(text, font, size)], first line hand font, second usually mono.  The note and every line share the
    same origin (the note's centre), tilt and move keys, so they stay together when the note flies or pops."""
    origin = (x + w / 2, y + h / 2)
    kw = _move_kw(rot, origin, move, layer)
    b.stroke("path", at, dur, width=0, until=until, d=rrect_path(x, y, w, h, 5), box=[x, y, x + w, y + h], fill=fill, shadow=True, **kw)
    ty = y + 16
    for text, font, size in lines:
        b.write(text, x + 16, ty, at + dur, size=size, font=None if font == "hand" else font, until=until, **kw)
        ty += round(size * 1.25) + 6


def slip(b, x, y, w, h, speaker, text, at, *, size=22, dur=0.4, until=None, rot=0, origin=None, move=None, layer=None, role_w=None, instant=False):
    """One message of a list as a role-coloured note: the speaker ('user' / 'assistant') and what was said, both monospace on ONE row.  The user's notes are the user colour, the
    assistant's the model colour (with its dark outline).  All parts share the note's tilt, origin and move keys, so a note can fly as one piece.
    `instant`: the text is there at once instead of being written (a copy that must look exactly like its original from the first frame)."""
    fill, _, outline = ROLE["user" if speaker == "user" else "model"]
    kw = _move_kw(rot, origin or (x + w / 2, y + h / 2), move, layer)
    b.stroke("path", at, dur, color=outline, width=3 if outline else 0, until=until, d=rrect_path(x, y, w, h, 6), box=[x, y, x + w, y + h], fill=fill, shadow=True, **kw)
    ty = y + (h - size * 1.25) / 2 - 1
    rw = role_w if role_w is not None else round(size * 0.602 * 9 + 22)
    if speaker:
        b.write(speaker, x + 16, ty, at + dur, size=size, dur=0.05 if instant else 0.5, font="mono", until=until, **kw)
    if text:
        b.write(text, x + 16 + rw, ty, at + dur + (0.0 if instant else 0.3), size=size, dur=0.05 if instant else max(0.6, 0.045 * len(text)), font="mono", until=until, **kw)


def bubble(b, x, y, w, h, role, lines, at, *, font="hand", size=38, dur=0.5, until=None, layer=None, **kw0):
    """A chat bubble in the colour of its role (see ROLE).  Chinese text in the hand font, English/code in mono (the mono font has no Chinese)."""
    fill, text_col, outline = ROLE[role]
    kw = _move_kw(kw0.get("rot"), kw0.get("origin") or (x + w / 2, y + h / 2), kw0.get("move"), layer)
    b.stroke("path", at, dur, color=outline, width=4 if outline else 0, until=until, d=rrect_path(x, y, w, h, 26), box=[x, y, x + w, y + h], fill=fill, **kw)
    for i, line in enumerate(lines):
        b.write(line, x + 26, y + 18 + i * round(size * 1.25), at + dur, size=size, color=text_col, font=None if font == "hand" else font, until=until, **kw)


def bar(b, x, base_y, w, h, fill, at, *, grow=1.0, outline=None, until=None, layer=None):
    """A filled bar that grows up from its base line (vertical stretch about the base)."""
    origin = (x + w / 2, base_y)
    move = [{"at": at, "sy": 0.02}, {"at": at + grow, "sy": 1}]
    kw = _move_kw(0, origin, move, layer)
    b.stroke("path", at, 0.2, color=outline, width=4 if outline else 0, until=until, d=rrect_path(x, base_y - h, w, h, 6), box=[x, base_y - h, x + w, base_y], fill=fill, **kw)


def highlight(b, x, y, w, h, at, *, dur=0.4, until=None):
    """Highlighter under a text (yellow at 45 %): draw it BEFORE the text so it sits behind it."""
    b.stroke("path", at, dur, width=0, until=until, d=rrect_path(x, y, w, h, 8), box=[x, y, x + w, y + h], fill=PAL["yellow"], fillOpacity=0.45)


def block(b, x, y, w, h, role, label, at, *, until=None, lx=None, size=36):
    """A big role-coloured block with its label inside at the top (the program, the model)."""
    fill, tcol, outline = BLOCK[role]
    b.stroke("path", at, 0.6, color=outline, width=4 if outline else 0, until=until, d=rrect_path(x, y, w, h, 22), box=[x, y, x + w, y + h], fill=fill)
    b.write(label, (x + 24) if lx is None else lx, y + 12, at + 0.5, size=size, dur=0.9, color=tcol, until=until)


def idle_keys(t0, t1, *, amp=5.0, period=2.6, sway=0.0):
    """`move` keys for a standing character that is not frozen: a slow breathing bob of `amp` px (and a sway of +-`sway` degrees about the feet) from t0 to t1.  The composer eases between keys,
    so alternating rest / raised keys read as one smooth bob."""
    keys, t, i = [], t0, 0
    while t < t1:
        raised = i % 2 == 1
        k = {"at": round(t, 2), "dy": -amp if raised else 0.0}
        if sway:
            k["rot"] = sway if raised else -sway
        keys.append(k)
        t += period / 2
        i += 1
    return keys


def char(b, name, cx, bottom, h, at, *, until=None, dur=0.6, idle=None):
    """A character standing on a line: top layer (in front of everything), the pen does not go to it.  KEEP IT OFF THE CONTENT: the layout check measures how much of a text or a note
    the character's opaque pixels cover (rule under-character, an ERROR from 15 % of a text / 25 % of a note); a character in front of a note hides it, so let notes land BESIDE it."""
    kw = {}
    if idle:   # True or {amp, period, sway}: breathing bob about the feet, until `until` (a minute when the character stays to the end)
        cfg = {} if idle is True else dict(idle)
        kw = {"move": idle_keys(at, until if until is not None else at + 60.0, **cfg), "origin": [cx, bottom]}
    b.image(name, cx, bottom - h, h, at, dur=dur, reveal="fade", until=until, pen=False, layer="top", **kw)


def fly(b, x, y, w, h, speaker, text, t_go, dx, dy=0, *, dur_fly=1.3, until=None, size=22):
    """A copy of a message note, placed exactly over its original, that leaves at t_go and glides (dx, dy) away.  The copy is in the top layer with its text there at once and exists from
    0.1 s before take-off, so at take-off only ONE text is seen (a copy in the normal layers lets the original's text show through its fill, a copy whose text is written lets the original's
    text vanish under its fill)."""
    mv = [{"at": t_go, "dx": 0, "dy": 0}, {"at": t_go + dur_fly, "dx": dx, "dy": dy}]
    slip(b, x, y, w, h, speaker, text, t_go - 0.1, size=size, dur=0.05, until=until, move=mv, layer="top", instant=True)


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
# devices of the second round (docs/whiteboard/style-guide-agent.zh-CN.md section "第二轮手段"): result panel, countdown ring, quiz card, right/wrong panels, token meter, lanes, curve
PANEL = {"fill": "#EEF2F7", "line": "#94A3B8", "title": "#475569", "cmd": "#0A645D", "good": "#166534", "bad": "#B91C1C"}   # line colours of a result panel (all >= 4.5:1 on the panel)


def result_panel(b, x, y, w, h, lines, at, *, title="运行结果", size=28, per_line=0.55, until=None):
    """The result of running the code, beside it: a pale panel with a small hand-written title and monospace lines.  A line is a string (an output) or (text, kind): "cmd" the typed command, "good" / "bad" a right / wrong result.
    The monospace font has no Chinese: lines are English/digits/symbols only."""
    b.stroke("path", at, 0.6, color=PANEL["line"], width=3, until=until, d=rrect_path(x, y, w, h, 16), box=[x, y, x + w, y + h], fill=PANEL["fill"])
    b.write(title, x + 20, y + 8, at + 0.4, size=26, dur=0.7, color=PANEL["title"], until=until)
    lh = round(size * 1.35)
    for i, ln in enumerate(lines):
        text, kind = (ln, "out") if isinstance(ln, str) else ln
        b.write(text, x + 22, y + 52 + i * lh, at + 0.9 + i * per_line, size=size, dur=max(0.5, 0.04 * len(text)), font="mono", color=PANEL.get(kind) if kind != "out" else None, until=until)


def _arc(cx, cy, r, a0, a1):
    x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
    return f"M {x0:.1f} {y0:.1f} A {r} {r} 0 0 1 {x1:.1f} {y1:.1f}"


def ring(b, cx, cy, r, q_end, ans_at, *, color=None, width=9, segments=3):
    """Countdown ring for the 3 s silence after a question: the arcs appear together just after the question (before the quiz silence starts, so the lint's silence rule is happy) and vanish one
    after the other, clockwise from the top; the last one is gone when the answer is due, so the ring 'closes in' on the silence."""
    color = color or PAL["red"]
    span, gap, t0 = 360.0 / segments, 10.0, q_end + 0.3
    for k in range(segments):
        until = t0 + (ans_at - 0.4 - t0) * (k + 1) / segments
        b.stroke("path", q_end + 0.1, 0.35, color=color, width=width, until=until, d=_arc(cx, cy, r, -90 + k * span + gap / 2, -90 + (k + 1) * span - gap / 2), box=[cx - r, cy - r, cx + r, cy + r])


def _chip(b, x, y, w, h, fill, text, at, *, size=30, until=None):
    b.stroke("path", at, 0.3, width=0, until=until, d=rrect_path(x, y, w, h, h / 2), box=[x, y, x + w, y + h], fill=fill)
    b.write(text, x + w / 2, y + (h - size * 1.25) / 2, at + 0.3, size=size, dur=0.5, color="#FFFFFF", align="center", until=until)


def quiz_card(b, x, y, w, h, lines, at, *, size=40, tag="想一想", until=None):
    """A prediction question on a coloured card with a red tag: the question is the only thing on the board that is NOT an answer, so it gets the loudest colour block."""
    b.stroke("path", at, 0.5, width=0, until=until, d=rrect_path(x, y, w, h, 22), box=[x, y, x + w, y + h], fill=PAL["note_blue"], shadow=True)
    _chip(b, x + 24, y - 24, 150, 48, PAL["red"], tag, at + 0.2, until=until)
    for i, ln in enumerate(lines):
        b.write(ln, x + 36, y + 36 + i * round(size * 1.3), at + 0.7 + 0.5 * i, size=size, dur=max(0.6, 0.12 * len(ln)), until=until)


def mark_ok(b, cx, cy, at, *, color=None, until=None):
    color = color or PAL["green"]
    b.stroke("line", at, 0.25, color=color, width=9, until=until, x1=cx - 26, y1=cy, x2=cx - 6, y2=cy + 24)
    b.stroke("line", at + 0.25, 0.35, color=color, width=9, until=until, x1=cx - 6, y1=cy + 24, x2=cx + 34, y2=cy - 26)


def mark_bad(b, cx, cy, at, *, color=None, until=None):
    color = color or PAL["red"]
    b.stroke("line", at, 0.25, color=color, width=9, until=until, x1=cx - 24, y1=cy - 24, x2=cx + 24, y2=cy + 24)
    b.stroke("line", at + 0.25, 0.25, color=color, width=9, until=until, x1=cx + 24, y1=cy - 24, x2=cx - 24, y2=cy + 24)


def split_panels(b, x, y, w, h, at, *, gap=40, labels=("对", "错"), until=None):
    """Right / wrong side by side: a green panel and a pink one with a tag each.  Returns the two panels as (x, y, w, h) for the caller to fill; mark_ok / mark_bad draw the tick and the cross."""
    pw = (w - gap) / 2
    boxes = []
    for i, (fill, line, chip) in enumerate(((PAL["note_green"], PAL["green"], PAL["green"]), (PAL["note_pink"], PAL["red"], PAL["red"]))):
        px = x + i * (pw + gap)
        b.stroke("path", at + 0.2 * i, 0.5, color=line, width=4, until=until, d=rrect_path(px, y, pw, h, 20), box=[px, y, px + pw, y + h], fill=fill)
        _chip(b, px + 24, y - 24, 90, 48, chip, labels[i], at + 0.2 * i + 0.2, until=until)
        boxes.append((px, y, pw, h))
    return boxes


def token_meter(b, x, base_y, w, limit_h, notes, at, *, gap=8, until=None):
    """A context window as a tall frame with a red limit line.  `notes` = [(speaker, height, t_in)], oldest first, heights in px: they are stacked from the bottom; when the stack would get
    higher than the limit the OLDEST notes slide out to the left and fade, the rest settle down.  Nothing here claims a number: it shows 'the stack grows and the oldest falls out'.
    Returns [(speaker, y_top_when_placed, t_drop or None)]."""
    top = base_y - limit_h
    b.stroke("path", at, 0.8, color=PAL["ink"], width=5, until=until, d=rrect_path(x, top - 30, w, limit_h + 44, 14), box=[x, top - 30, x + w, base_y + 14])
    b.stroke("line", at + 0.6, 0.5, color=PAL["red"], width=6, until=until, x1=x - 18, y1=top, x2=x + w + 18, y2=top)
    active, drops, placed = [], [], []   # active = indexes of the notes in the frame, drops = (t_drop, height shift)
    for i, (spk, h, t_in) in enumerate(notes):
        stack = sum(notes[j][1] + gap for j in active)
        y = base_y - stack - h
        placed.append([spk, y, None])
        active.append(i)
        while sum(notes[j][1] + gap for j in active) > limit_h and len(active) > 1:
            old = active.pop(0)
            t_drop = t_in + 0.9
            placed[old][2] = t_drop
            drops.append((t_drop, notes[old][1] + gap, old, set(active)))
    for i, (spk, h, t_in) in enumerate(notes):
        keys, dy = [], 0.0
        for t_drop, shift, old, stay in sorted(drops, key=lambda d: d[0]):
            if i == old:
                keys += [{"at": t_drop, "dx": 0, "dy": 0}, {"at": t_drop + 0.6, "dx": -(w + 70), "dy": 0}]
                break
            if i in stay and t_drop > t_in:
                keys += [{"at": t_drop + 0.3, "dy": dy}, {"at": t_drop + 0.9, "dy": dy + shift}]
                dy += shift
        slip(b, x + 12, placed[i][1], w - 24, h, spk, "", t_in, size=22, dur=0.3, move=keys or None, until=(placed[i][2] + 0.5) if placed[i][2] else until, role_w=0)
    return [tuple(p) for p in placed]


def lanes(b, x, y, w, h, specs, at, *, until=None):
    """Three (or n) columns for a sequence of messages: a role-coloured header chip and a thin lifeline each.  specs = [(name, role)], role in user / program / model.  Returns the lanes' x."""
    n = len(specs)
    xs = [x + w * (i + 0.5) / n for i in range(n)]
    for i, (name, role) in enumerate(specs):
        fill, tcol, outline = BLOCK[role] if role in BLOCK else ROLE[role]
        b.stroke("path", at + 0.2 * i, 0.4, color=outline, width=3 if outline else 0, until=until, d=rrect_path(xs[i] - 100, y, 200, 56, 14), box=[xs[i] - 100, y, xs[i] + 100, y + 56], fill=fill)
        b.write(name, xs[i], y + 8, at + 0.2 * i + 0.3, size=32, dur=0.6, color=tcol, align="center", until=until)
        b.stroke("line", at + 0.5 + 0.2 * i, 0.7, color="#94A3B8", width=4, until=until, x1=xs[i], y1=y + 66, x2=xs[i], y2=y + h)
    return xs


def lane_msg(b, xs, src, dst, y, label, at, *, size=26, font="mono", color=None, until=None):
    """One message between two lanes: an arrow with its label above the middle (monospace for code and replies, hand font for Chinese)."""
    x1, x2 = xs[src], xs[dst]
    d = 1 if x2 > x1 else -1
    b.stroke("arrow", at, 0.5, color=color or PAL["ink"], width=6, until=until, x1=x1 + 10 * d, y1=y, x2=x2 - 14 * d, y2=y)
    b.write(label, (x1 + x2) / 2, y - size * 1.45, at + 0.3, size=size, dur=max(0.5, 0.04 * len(label)), font=None if font == "hand" else font, align="center", color=color, until=until)


def _smooth(pts):
    """A cubic Bezier path through the points (Catmull-Rom)."""
    d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d


def curve(b, x, y, w, h, pts, at, *, dur=1.8, color=None, width=8, until=None):
    """A line chart drawn as ONE stroke that is drawn along its length (no numbers claimed: pts are fractions 0..1 of the plot box, origin at the bottom left).  Two arrows are the axes, a dot
    marks each point as the line reaches it."""
    color = color or PAL["red"]
    b.stroke("arrow", at, 0.5, color=PAL["ink"], width=5, until=until, x1=x, y1=y + h, x2=x, y2=y - 10)
    b.stroke("arrow", at + 0.2, 0.5, color=PAL["ink"], width=5, until=until, x1=x, y1=y + h, x2=x + w + 10, y2=y + h)
    xy = [(x + px * w, y + h - py * h) for px, py in pts]
    b.stroke("path", at + 0.6, dur, color=color, width=width, until=until, d=_smooth(xy), box=[x, y, x + w, y + h])
    for i, (px, py) in enumerate(xy):
        b.stroke("circle", at + 0.6 + dur * i / max(len(xy) - 1, 1), 0.3, color=color, width=5, until=until, fill=color, cx=px, cy=py, r=8)


class RawBoard:
    """The smallest board that can use the kit: it keeps the items exactly as given (times as given, no pen).  For tests and fixtures."""
    def __init__(self):
        self.items = []

    def stroke(self, shape, at, dur=0.7, color=None, width=6, until=None, **kw):
        it = {"kind": "stroke", "shape": shape, "at": at, "dur": dur, "width": width, **kw}
        if color:
            it["color"] = color
        if until is not None:
            it["until"] = until
        self.items.append(it)

    def write(self, text, x, y, at, size=60, dur=None, color=None, align="left", until=None, font=None, **kw):
        it = {"kind": "write", "text": text, "x": x, "y": y, "at": at, "size": size, "align": align, **kw}
        if dur is not None:
            it["dur"] = dur
        if color:
            it["color"] = color
        if until is not None:
            it["until"] = until
        if font:
            it["font"] = font
        self.items.append(it)

    def image(self, src, x, y, w, h, at, dur=1.0, reveal="fade", until=None, **kw):
        it = {"kind": "image", "src": src, "x": x, "y": y, "w": w, "h": h, "at": at, "dur": dur, "reveal": reveal, **kw}
        if until is not None:
            it["until"] = until
        self.items.append(it)
