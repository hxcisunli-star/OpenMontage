SIDS = [s["id"] for s in tl["sections"]]
if not SIDS:
    raise SystemExit("旁白时间线没有 sections，无法建立板书时间窗")
B = [0.0] + [round(sec_tl[s]["start"] - 0.35, 2) for s in SIDS[1:]] + [round(TOTAL + 0.4, 2)]
K = {f"K{i+1}": (B[i], B[i + 1]) for i in range(len(SIDS))}     # cut windows: one board per script section, each starts 0.35 s before its first word (the fade-in)
cuts = {}
GOLD = "#D9A400"
PAL = V2.PAL
BLUE_LINE = PAL["ai_line"]
POSE = json.loads((IMG / "pose_metrics.json").read_text(encoding="utf-8"))["poses"]   # per pose: h_at_std = the display height that gives the standard body size (see scripts/pose_metrics.py)
TEACHER_X, TEACHER_BOTTOM = 1680, 1030                  # the teacher stands at the lower right
ROBOT_X, ROBOT_BOTTOM = 1450, 890                      # the partner stands to her left (feet y 890: the same baseline for every pose, so a swap never makes it jump)
QZ = tl["quiz"]                                        # [{section_id, question_end, answer_not_before, answer}] in lesson order (real times from the audio)


def quiz_of(sid):
    """(question_end, answer_not_before) of every quiz question of a section, in order."""
    return [(q["question_end"], q["answer_not_before"]) for q in QZ if q["section_id"] == sid]


def title(b, text, at):
    b.write(text, 420, 46, at, size=62, dur=1.4)
    b.stroke("line", at + 0.7, 0.7, color="#CBD5E1", width=3, x1=80, y1=160, x2=1840, y2=160)


def mono(b, text, x, y, at, size=36, dur=None, indent=0, **kw):
    """Code, digits and Latin text are ALWAYS written in the monospace font (the hand font draws 0, o, c and capitals as squares); the mono font has no Chinese."""
    d = dur if dur is not None else max(0.8, 0.05 * len(text))
    b.write(text, x + indent * 4 * size * 0.6, y, at, size=size, dur=d, font="mono", **kw)


def foot(b, runs, x, y, at, size=24, color=GREY, until=None, per=0.5):
    """One line that mixes hand-written Chinese ('h') and monospace Latin/digits ('m'): runs = [("h", "判分："), ("m", "3+2=5"), ...].  Each run is written after the previous one,
    placed at the measured end of the previous run (est_w), so labels and numbers never share one write (the lint forbids that)."""
    cx, t = x, at
    for kind, text in runs:
        w = est_w(text, size) * (1.1 if kind == "m" else 1.0)
        if kind == "m":
            b.write(text, cx, y + 2, t, size=size, dur=max(0.5, 0.04 * len(text)), font="mono", color=color, until=until)
        else:
            b.write(text, cx, y, t, size=size, dur=max(0.5, 0.09 * len(text)), color=color, until=until)
        cx += w + 8
        t += per
    return cx


def char(b, name, cx, bottom, at, *, until=None, dur=0.45, idle=True, h=None):
    """A character pose standing on `bottom`, at the display height that gives the standard body size (POSE[name]['h_at_std']); top layer, the pen does not go to it.
    A swap = two calls: the old pose with until=t_swap + 0.15, the new one with at=t_swap (a short cross-fade).  Keep characters off the content (layout rule under-character)."""
    V2.char(b, name, cx, bottom, h or POSE[name]["h_at_std"], at, until=until, dur=dur, idle=True if idle else None)


def pose_seq(b, cx, bottom, seq, *, end=None, dur=0.4, idle=True):
    """Pose changes of one character: seq = [(time, pose name), ...] ascending; each pose stays until the next one starts (0.15 s overlap = a quick cross-fade); the last one until `end` (None = to the end of the cut)."""
    for i, (t, name) in enumerate(seq):
        nxt = seq[i + 1][0] + 0.15 if i + 1 < len(seq) else end
        char(b, name, cx, bottom, t, until=nxt, dur=dur if i else 0.6, idle=idle)


def robot_on(b, name, cx, at, until, *, bottom=ROBOT_BOTTOM, from_x=None, from_bottom=None, walk=0.8, to_x=None, to_at=None, slide=0.8, hops=(), leave_x=None, breathe=True, h=None, dur=0.45):
    """The partner on stage as ONE picture (pose `name`) from `at` to `until`, standing at cx with its feet on `bottom` (ROBOT_CHOREO.md).
    from_x / from_bottom: it walks in from there during `walk` s (a small step bob while it moves; the picture fades in over `dur`).  to_x/to_at/slide: it slides on to to_x between to_at and
    to_at+slide (the next pose is then placed at to_x).  hops: [(time, px)] jumps in place, one per counted step.  leave_x: during the last 0.5 s it drifts to leave_x while it fades out.
    h: display height when it must differ from the standard one.  breathe=False: no breathing bob (a hand that holds a prop drawn on the board must not move).  Keys are relative to where the picture is drawn (cx, bottom)."""
    h = h or POSE[name]["h_at_std"]
    keys, dx_now, t0 = [], 0.0, at

    def bob(t_from, t_to, d_from, d_to, y_from=0.0, y_to=0.0, step=0.3, up=12):
        n = max(2, round((t_to - t_from) / step))
        n += n % 2                                           # an even number of keys, so the last one rests on the ground
        out = []
        for i in range(1, n + 1):
            f = i / n
            out.append({"at": round(t_from + (t_to - t_from) * f, 2), "dx": round(d_from + (d_to - d_from) * f, 1), "dy": round(y_from + (y_to - y_from) * f - (up if i % 2 == 1 and i < n else 0), 1)})
        return out
    if from_x is not None or from_bottom is not None:
        d0 = (from_x if from_x is not None else cx) - cx
        y0 = (from_bottom - bottom) if from_bottom is not None else 0.0
        keys.append({"at": round(at, 2), "dx": round(d0, 1), "dy": round(y0, 1)})
        keys += bob(at, at + walk, d0, 0.0, y0, 0.0)
        t0 = at + walk
    slide_end = None
    if to_x is not None:
        d1 = to_x - cx
        keys += bob(to_at, to_at + slide, 0.0, d1)
        dx_now, slide_end = d1, to_at + slide
    busy = [(to_at - 0.05, slide_end + 0.05)] if slide_end else []
    for th, px in hops:
        busy.append((th - 0.05, th + 0.4))
        keys += [{"at": round(th, 2), "dy": 0.0}, {"at": round(th + 0.12, 2), "dy": -px}, {"at": round(th + 0.28, 2), "dy": 0.0}]
    t_end = until - 0.5 if leave_x is not None else until
    if breathe:
        for k in V2.idle_keys(t0, t_end):
            if not any(a <= k["at"] <= z for a, z in busy):
                keys.append({"at": k["at"], "dy": k["dy"]})
    if leave_x is not None:
        keys += [{"at": round(until - 0.5, 2), "dx": round(dx_now, 1)}, {"at": round(until, 2), "dx": round(leave_x - cx, 1), "dy": 0.0}]
    keys.sort(key=lambda k: k["at"])
    kw = {"move": keys, "origin": [cx, bottom]} if keys else {}
    b.image(name, cx, bottom - h, h, at, dur=dur, reveal="fade", until=until, pen=False, layer="top", **kw)


def pic(b, name, cx, top, h, at, *, card=False, until=None, dur=0.9, reveal=None, layer=None, **kw):
    """A generated picture from assets/images.  card=True: an opaque scene card (rounded corners 18, 4 px ink border, soft shadow, drawn in by a downward wipe); otherwise a keyed transparent
    prop (fades in).  The pen does not follow it.  `h` is the display height in px; the width follows the picture's aspect."""
    if card:
        kw.setdefault("radius", 18); kw.setdefault("border", {"width": 4, "color": INK}); kw.setdefault("shadow", True)
    if layer:
        kw["layer"] = layer
    b.image(name, cx, top, h, at, dur=dur, reveal=reveal or ("down" if card else "fade"), until=until, pen=False, **kw)


def pic_w(name, h):
    """Display width of a picture shown at height h (to place it by its left edge or to check that it fits)."""
    im = Image.open(IMG / f"{name}.png")
    return round(im.width * h / im.height)


def ring(b, c, at, until, r=82, color=GOLD):
    b.stroke("circle", at, 0.6, color=color, width=7, cx=c["x"] + c["w"] / 2, cy=c["y"] + c["h"] / 2, r=r, until=until)
