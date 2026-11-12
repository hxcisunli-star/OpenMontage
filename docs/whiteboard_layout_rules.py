"""Rules for the measured layout check (docs/whiteboard_layout_check.py).  Pure functions over the probe output, no browser, no I/O (glyph_findings only
reads font files through fc-query): easy to test.

Input  = {frame: payload} from remotion-composer/probe (real DOM boxes, CSS px in the 1920x1080 viewport), the lesson props, and a cut-of-frame function.
Output = findings [{severity, rule, cut, t0, t1, n, msg, frame, boxes}], merged over neighbouring sample frames.

What a box means: a text rect is the glyph advance box of ONE line (Range.getClientRects).  It includes the line's leading, so it is shrunk by 10 % top and
bottom before two texts are compared ("ink box").  Strokes are compared as points sampled along the drawn part of the path, never as bounding boxes (a
diagonal arrow's bounding box is a big empty rectangle).  Rules (ERROR stops the render, WARN only reports):
  text-overlap    two texts of DIFFERENT board items overlap (ERROR when the overlap is >= 40 % of the smaller text; only WARN when both are the same text, e.g. a note copy
                  sliding off its original)
  stroke-on-text  an open stroke (line, arrow shaft) runs through the middle of a text.  On purpose, so not reported: the pointer pen, arrows that start or
                  end on a label, underlines, short marks drawn on a text (the red cross-out of a value), crossed pairs (an X) and the emphasis frames other items
                  draw round a word.  Only finished strokes count.
  frame-fit       a frame of the SAME item does not hold its text (a memory cell whose value is wider than the cell)
  (both stroke rules need two neighbouring samples: a value that flies across a memory board crosses cell edges for under a second, and the first arm of a
  cross-out exists before the second one)
  off-board       text sticks out of the board rectangle (the board clips it: ERROR), or its ink sits closer than 8 px to the edge (WARN)
  under-overlay   text lies under the caption pill or the school logo (WARN; ERROR at >= 40 %)
  under-character text lies under a picture drawn in the top layer (a character standing in front of the board text).  The probe reports a 32x32 grid of the picture's opaque cells,
                  so the share of the text that is REALLY covered is measured (WARN from 3 %, ERROR from 15 %); without a grid the picture's box is used (an upper bound: WARN only).
                  The same grid measures how much of a filled note / bubble / block a character stands on (WARN from 10 %, ERROR from 25 %)
  (hidden)        two texts whose overlap lies completely inside an opaque filled shape of a layer in front of the lower text (a note copy sliding off its original) are not counted
                  in text-overlap
  (camera) while the board camera is zoomed in (the probe reports `zoom` > 1) content leaves the view on purpose, so `off-board` is not checked then
  wrap            a line broke where the source text has no line break (ERROR)
  glyph           a character that no font in the chain can draw (tofu, ERROR) or only the fallback font has (WARN)  -- from the props, no browser
"""
FPS = 30
MIN_OPACITY = 0.5      # fading in/out items are checked at the time they are fully there
SOLID = 0.99           # two texts only count as overlapping when both are fully opaque: anything in the middle of a fade or a value rewrite is a moment, not a layout
INK_PAD = 0.10         # share of the line height cut off top and bottom
TOL = 3.0              # px of overlap that is never reported
EDGE = 8.0             # px (ink box): closer than this to the board edge is a WARN; clipped text is an ERROR
CHAR_WARN, CHAR_ERROR = 0.03, 0.15   # share of a text's ink box covered by the opaque cells of a top-layer picture
BLOCK_WARN, BLOCK_ERROR = 0.10, 0.25  # the same for a filled note / bubble / block
ALPHA_GRID = 32
PEN_FILL = "rgb(245, 201, 166)"  # the pointer pen's circle in WhiteboardScene.Pointer: it points at things on purpose


def ink(r):
    h = r[3] - r[1]
    return [r[0] + 1.0, r[1] + INK_PAD * h, r[2] - 1.0, r[3] - INK_PAD * h]


def inter(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])), max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def area(r):
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def inside(r, big, pad=0.0):
    return r[0] >= big[0] - pad and r[1] >= big[1] - pad and r[2] <= big[2] + pad and r[3] <= big[3] + pad


LAYER_RANK = {"svg": 0, "html": 1, "svg-top": 2, "html-top": 3}   # back to front, as WhiteboardScene stacks them


def covers_of(p):
    """[(layer rank, box)] of the opaque filled shapes (fill alpha >= 0.95; not pictures: they have transparent corners): what hides the text of a layer behind it."""
    out = []
    for it in p.get("items", []):
        for s in it.get("shapes", []):
            if s.get("filled") and s["kind"] != "image" and s["opacity"] >= 0.99 and s.get("fillAlpha", 1) >= 0.95:   # a translucent block (the 45 % highlighter) hides nothing
                out.append((LAYER_RANK.get(it["layer"], 1), s["box"]))
    return out


def covered_share(alpha, box, rect, nx=24, ny=6):
    """Share of `rect` (a text's ink box) that lies on opaque cells of a picture: `alpha` = 32x32 string of 0/1 over `box`, sampled on an nx x ny grid of points."""
    bw, bh = box[2] - box[0], box[3] - box[1]
    if bw <= 0 or bh <= 0 or len(alpha) != ALPHA_GRID * ALPHA_GRID:
        return None
    hit = 0
    for i in range(nx):
        for j in range(ny):
            x = rect[0] + (rect[2] - rect[0]) * (i + 0.5) / nx
            y = rect[1] + (rect[3] - rect[1]) * (j + 0.5) / ny
            if box[0] <= x < box[2] and box[1] <= y < box[3]:
                cx = min(ALPHA_GRID - 1, int((x - box[0]) / bw * ALPHA_GRID))
                cy = min(ALPHA_GRID - 1, int((y - box[1]) / bh * ALPHA_GRID))
                hit += alpha[cy * ALPHA_GRID + cx] == "1"
    return hit / (nx * ny)


def visible_texts(p):
    """[(item key, text dict)] of the board's fully drawn, visible texts."""
    out = []
    for it in p.get("items", []):
        for t in it.get("texts", []):
            if t["opacity"] >= MIN_OPACITY and t["reveal"] >= 0.99 and t.get("rects"):
                out.append(((it["layer"], it["idx"]), t))
    return out


def visible_shapes(p):
    out = []
    for it in p.get("items", []):
        for s in it.get("shapes", []):
            if s["opacity"] >= MIN_OPACITY and s["reveal"] > 0.5:
                out.append(((it["layer"], it["idx"]), s))
    return out


def is_pen(s):
    return (s.get("fill") or "") == PEN_FILL


def _ccw(a, b, c):
    return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])


def crosses(pa, pb, min_len=30.0):
    """Do two polylines properly cross (a touching end point does not count)?  Strokes shorter than min_len px are ignored."""
    def length(p):
        return sum(((p[i + 1][0] - p[i][0]) ** 2 + (p[i + 1][1] - p[i][1]) ** 2) ** 0.5 for i in range(len(p) - 1))
    if length(pa) < min_len or length(pb) < min_len:
        return False
    sa, sb = pa[:: max(1, len(pa) // 60)], pb[:: max(1, len(pb) // 60)]
    for i in range(len(sa) - 1):
        for j in range(len(sb) - 1):
            a, b, c, d = sa[i], sa[i + 1], sb[j], sb[j + 1]
            if _ccw(a, b, c) * _ccw(a, b, d) < 0 and _ccw(c, d, a) * _ccw(c, d, b) < 0:
                return True
    return False


def frame_findings(p):
    """Raw findings of one frame: [(rule, severity, key, msg, boxes)]; `key` identifies the offending pair so equal findings of neighbouring frames merge."""
    out = []
    board = p["board"]
    texts = visible_texts(p)
    shapes = visible_shapes(p)
    cov = covers_of(p)

    # -- off-board and wrap: per text ------------------------------------------------------------------------------------------------------------------
    zoomed = float(p.get("zoom", 1) or 1) > 1.001
    for k, t in texts:
        for r in t["rects"]:
            if zoomed:
                break
            worst = max(board[0] - r[0], board[1] - r[1], r[2] - board[2], r[3] - board[3])
            if worst > TOL:
                out.append(("off-board", "ERROR", ("off", t["text"]), f"text {t['text'][:30]!r} sticks out of the board by {worst:.0f}px (the board clips it)", [r]))
                break
            ib = ink(r)
            near = min(ib[0] - board[0], ib[1] - board[1], board[2] - ib[2], board[3] - ib[3])
            if near < EDGE:
                out.append(("off-board", "WARN", ("edge", t["text"]), f"text {t['text'][:30]!r} is {max(near, 0):.0f}px from the board edge (< {EDGE:.0f}px)", [r]))
                break
        expect = t["text"].count("\n") + 1
        if t["lines"] > expect:
            out.append(("wrap", "ERROR", ("wrap", t["text"]), f"text {t['text'][:30]!r} wrapped into {t['lines']} lines (source has {expect})", [t["box"]]))

    # -- text vs text across items ---------------------------------------------------------------------------------------------------------------------
    # Both texts must be (almost) fully opaque: in the middle of a fade or a value rewrite the old and the new text overlap for a moment on purpose.
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            (ka, a), (kb, b) = texts[i], texts[j]
            if ka == kb or min(a["opacity"], b["opacity"]) < SOLID:
                continue
            best = None
            for ra in a["rects"]:
                for rb in b["rects"]:
                    ox, oy = inter(ink(ra), ink(rb))
                    if ox > TOL and oy > TOL:
                        ratio = ox * oy / max(1.0, min(area(ink(ra)), area(ink(rb))))
                        if best is None or ratio > best[0]:
                            best = (ratio, ox, oy, ra, rb)
            if best:
                ia, ib = ink(best[3]), ink(best[4])
                region = [max(ia[0], ib[0]), max(ia[1], ib[1]), min(ia[2], ib[2]), min(ia[3], ib[3])]
                lo = min(LAYER_RANK.get(ka[0], 1), LAYER_RANK.get(kb[0], 1))
                if any(r > lo and inside(region, box, 1.0) for r, box in cov):
                    continue   # the overlap lies under an opaque block that is in front of the lower text: nobody sees the two words together (a note copy sliding off its original)
            if best and best[0] >= 0.05:
                pair = tuple(sorted([a["text"], b["text"]]))
                if a["text"] == b["text"] and best[0] >= 0.9:
                    out.append(("text-overlap", "WARN", ("tt",) + pair, f"{a['text'][:24]!r} is written twice at the same place (stacked, so it only looks bolder)", [best[3], best[4]]))
                    continue
                sev = "ERROR" if best[0] >= 0.40 and a["text"] != b["text"] else "WARN"   # the same text twice, shifted (a note copy sliding off its original) is not two words colliding
                out.append(("text-overlap", sev, ("tt",) + pair, f"{a['text'][:24]!r} / {b['text'][:24]!r} overlap {best[1]:.0f}x{best[2]:.0f}px ({best[0] * 100:.0f}% of the smaller)", [best[3], best[4]]))

    # -- strokes vs text ----------------------------------------------------------------------------------------------------------------------------------
    # What can be told from geometry alone (checked against the pictures of lesson 43): the pointer pen, arrows that start or end on a label, underlines, and
    # frames/ovals that a stroke item draws round a word (the frame cuts the line of text it marks) are all on purpose.  What is reported:
    #   * an OPEN stroke (line, arrow shaft) that passes through the middle of a text;
    #   * a closed frame that belongs to the SAME item as the text and does not hold it (a memory cell whose value is wider than the cell).
    # Not detectable here: a frame of another item that cuts through a word by mistake (it looks exactly like an emphasis frame).
    pen_items = {(it["layer"], it["idx"]) for it in p.get("items", []) for s in it.get("shapes", []) if is_pen(s)}
    open_strokes = [i for i, (ks, s) in enumerate(shapes) if ks not in pen_items and s.get("stroked", True) and len(s.get("pts") or []) > 2]

    def in_an_x(si):
        """Two strokes that cross each other are an X (a cross-out of a whole box or value): on purpose.  Only asked about a stroke that is about to be reported."""
        a = shapes[si][1]
        for bi in open_strokes:
            b = shapes[bi][1]
            if bi != si and inter(a["box"], b["box"])[0] > 0 and inter(a["box"], b["box"])[1] > 0 and crosses(a["pts"], b["pts"]):
                return True
        return False

    for si, (ks, s) in enumerate(shapes):
        if ks in pen_items or not s.get("stroked", True) or s["reveal"] < 0.99:
            continue  # a frame that is still being drawn is open until it is finished: judge it when it is complete
        pts = s.get("pts") or []
        subs = s.get("sub") or [0] * len(pts)
        closed = bool(s.get("closed")) or (len(pts) > 3 and ((pts[0][0] - pts[-1][0]) ** 2 + (pts[0][1] - pts[-1][1]) ** 2) ** 0.5 < 12)
        for kt, t in texts:
            for r in t["rects"]:
                bx = ink(r)
                hit = None
                if closed:
                    if ks != kt:
                        continue
                    ox, oy = inter(bx, s["box"])
                    frac = ox * oy / max(1.0, area(bx))
                    if frac >= 0.10 and not inside(bx, s["box"], 6.0):
                        hit = f"text {t['text'][:24]!r} does not fit inside its frame ({frac * 100:.0f}% of it inside)"
                elif len(pts) > 2:
                    sw, sh, tw, th = s["box"][2] - s["box"][0], s["box"][3] - s["box"][1], r[2] - r[0], r[3] - r[1]
                    cx, cy = (s["box"][0] + s["box"][2]) / 2, (s["box"][1] + s["box"][3]) / 2
                    if sw <= 1.4 * tw + 20 and sh <= 1.4 * th + 20 and r[0] - 6 <= cx <= r[2] + 6 and r[1] - 6 <= cy <= r[3] + 6:
                        continue  # a short mark drawn ON the text (a red cross-out of a value, a tick): the lessons do this on purpose; a long connector is another thing
                    pad = max(2.0, (s.get("width") or 0) / 2)
                    flags = [bx[0] - pad <= x <= bx[2] + pad and bx[1] - pad <= y <= bx[3] + pad for x, y in pts]
                    inn = [i for i, fl in enumerate(flags) if fl]
                    if len(inn) < 3:
                        continue
                    if len(inn) >= 0.6 * len(pts):
                        continue  # most of the stroke lies ON the text (a strike-through of a line of code): drawn on it, not across it
                    h = bx[3] - bx[1]
                    if all(pts[i][1] > bx[1] + 0.65 * h for i in inn):
                        continue  # an underline touching the bottom of its own text
                    last_sub = max(subs)
                    n0 = sum(1 for q in subs if q == 0)
                    if last_sub >= 1 and all(subs[i] == last_sub or (subs[i] == 0 and i >= 0.75 * n0) for i in inn):
                        continue  # the head of an arrow (and the last quarter of its shaft) pointing at the text
                    runs, i = [], 0
                    while i < len(flags):
                        if flags[i]:
                            j = i
                            while j + 1 < len(flags) and flags[j + 1]:
                                j += 1
                            runs.append((i, j)); i = j + 1
                        else:
                            i += 1
                    if all(a == 0 or b == len(flags) - 1 for a, b in runs):
                        continue  # the stroke starts or ends in the text (a label an arrow leaves from / a stroke that begins on a word)
                    hit = f"stroke runs through {t['text'][:24]!r} ({len(inn)} of {len(pts)} sample points inside it)"
                if hit and not (not closed and in_an_x(si)):
                    # both stroke findings must be seen in two neighbouring samples: a value that flies across a memory board is only there for a moment, and the
                    # first arm of a cross-out is drawn before the second one exists
                    out.append(("frame-fit" if closed else "stroke-on-text", "WARN", ("st", s["kind"], tuple(round(v / 10) for v in s["box"]), t["text"]), hit, [r, s["box"]], True))

    # -- text under a top-layer picture (a character in front of the board) ---------------------------------------------------------------------------------
    for it in p.get("items", []):
        if it.get("layer") != "html-top":
            continue
        for s in it.get("shapes", []):
            if s["kind"] != "image" or s["opacity"] < MIN_OPACITY:
                continue
            for kt, t in texts:
                for r in t["rects"]:
                    ox, oy = inter(ink(r), s["box"])
                    if ox > TOL and oy > TOL:
                        real = covered_share(s["alpha"], s["box"], ink(r)) if s.get("alpha") else None
                        if real is not None:
                            if real >= CHAR_WARN:
                                out.append(("under-character", "ERROR" if real >= CHAR_ERROR else "WARN", ("uc", t["text"], tuple(round(v / 10) for v in s["box"])),
                                            f"text {t['text'][:24]!r} is covered by a character picture ({real * 100:.0f}% of it is under opaque pixels)", [r, s["box"]]))
                                break
                            continue
                        ratio = ox * oy / max(1.0, area(ink(r)))
                        if ratio >= 0.05:
                            out.append(("under-character", "WARN", ("uc", t["text"], tuple(round(v / 10) for v in s["box"])),
                                        f"text {t['text'][:24]!r} lies under a character picture ({ratio * 100:.0f}% of it, from the picture's box)", [r, s["box"]]))
                            break

    # -- a character standing on a filled note / bubble / block ----------------------------------------------------------------------------------------------
    pics = [s for it in p.get("items", []) if it.get("layer") == "html-top" for s in it.get("shapes", []) if s["kind"] == "image" and s["opacity"] >= MIN_OPACITY and s.get("alpha")]
    if pics:
        for it in p.get("items", []):
            if it.get("layer") == "html-top":
                continue
            for sh in it.get("shapes", []):
                if not sh.get("filled") or sh["kind"] == "image" or sh["opacity"] < MIN_OPACITY or is_pen(sh) or area(sh["box"]) > 0.25 * 1920 * 1080:
                    continue
                for pic in pics:
                    share = covered_share(pic["alpha"], pic["box"], sh["box"], nx=24, ny=12)
                    if share is not None and share >= BLOCK_WARN:
                        out.append(("under-character", "ERROR" if share >= BLOCK_ERROR else "WARN", ("ucb", tuple(round(v / 10) for v in sh["box"])),
                                    f"a filled note/block at ({sh['box'][0]:.0f},{sh['box'][1]:.0f}) is {share * 100:.0f}% covered by a character picture", [sh["box"], pic["box"]]))
                        break

    # -- caption pill / logo ------------------------------------------------------------------------------------------------------------------------------
    for o in p.get("overlays", []):
        for s in o.get("shapes", []):
            if s["opacity"] < MIN_OPACITY or not (s.get("filled") or s["kind"] == "image"):
                continue
            region = s["box"]
            if area(region) > 0.25 * 1920 * 1080:
                continue  # a full-screen layer is not an obstacle
            for kt, t in texts:
                for r in t["rects"]:
                    ox, oy = inter(ink(r), region)
                    if ox > TOL and oy > TOL:
                        ratio = ox * oy / max(1.0, area(ink(r)))
                        if ratio >= 0.05:
                            what = "the caption pill" if region[1] > 700 else "the school logo"
                            out.append(("under-overlay", "ERROR" if ratio >= 0.40 else "WARN", ("ov", what, t["text"]), f"text {t['text'][:24]!r} lies under {what} ({ratio * 100:.0f}% of it)", [r, region]))
                            break
    return out


_CHARSETS = {}


def charset(font_file):
    """Code points a font file really has (fontconfig's fc-query, no extra dependency)."""
    import subprocess
    if font_file not in _CHARSETS:
        out = subprocess.run(["fc-query", "--format=%{charset}\\n", str(font_file)], capture_output=True, text=True).stdout.split()
        cps = set()
        for part in out:
            if "-" in part:
                a, b = part.split("-")
                cps.update(range(int(a, 16), int(b, 16) + 1))
            elif part:
                cps.add(int(part, 16))
        _CHARSETS[font_file] = cps
    return _CHARSETS[font_file]


def glyph_findings(props, hand_font, mono_font, fallback_font):
    """Characters that no font in the chain can draw (a tofu square, ERROR) or that only the fallback font has (it is drawn in another typeface, WARN).
    Chains as in WhiteboardScene: hand = ZCOOL KuaiLe -> sans-serif; mono = DejaVu Sans Mono -> any other font with the glyph (DejaVu Sans here, the only other
    one in the private fontconfig).  Works on the props only, so it needs no browser."""
    hand, mono, fb = charset(hand_font), charset(mono_font), charset(fallback_font)
    found = {}

    def check(cut, where, text, font):
        primary = hand if font == "hand" else mono
        for ch in sorted(set(text)):
            if ch.isspace() or ord(ch) < 0x20:
                continue
            cp = ord(ch)
            if cp in primary:
                continue
            sev, why = ("WARN", "only the fallback font has it, so it is drawn in another typeface") if cp in fb else ("ERROR", "no font can draw it: a tofu square")
            found.setdefault((cut, font, ch, sev), (where, why))

    for cut in props.get("cuts", []):
        wb = cut.get("whiteboard")
        if not wb:
            continue
        cid, base = cut.get("id", "?"), float(cut.get("in_seconds", 0))
        for it in wb.get("items", []):
            at = base + float(it.get("at", 0) or 0)
            if it.get("kind") == "write":
                check(cid, at, it.get("text", ""), "mono" if it.get("font") == "mono" else "hand")
            elif it.get("kind") == "code":
                for ln in it.get("lines", []):
                    check(cid, at, ln, "mono")
            elif it.get("kind") == "memory":
                for c in it.get("cells", []):  # MemoryBoard draws the name and the address in DejaVu Sans Mono, the value in the hand font
                    for fld, font in (("name", "mono"), ("value", "hand"), ("addr", "mono")):
                        check(cid, base + float(c.get("at", 0) or 0), str(c.get(fld, "") or ""), font)
    grouped = {}
    for (cid, font, ch, sev), (where, why) in found.items():
        grouped.setdefault((cid, round(where, 1), font, sev, why), []).append(ch)
    out = []
    for (cid, at, font, sev, why), chars in sorted(grouped.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2])):
        chars.sort()
        shown = " ".join(f"{c!r}" for c in chars[:8]) + (f" … ({len(chars)} characters)" if len(chars) > 8 else "")
        out.append({"severity": sev, "rule": "glyph", "cut": cid, "t0": at, "t1": at, "n": 1, "frame": None, "boxes": [],
                    "msg": f"{shown} in {font} text: {why}" if len(chars) > 1 else f"{chars[0]!r} (U+{ord(chars[0]):04X}) in {font} text: {why}"})
    return out


def collect(per_frame, cut_of):
    """per_frame = {frame: [raw findings]} -> merged findings.  The same (rule, key) in two CONSECUTIVE sample frames of one cut is one event with a time range
    (samples can be seconds apart, so frame distance says nothing; a finding that vanishes from a sample and comes back is a new event)."""
    finished, open_runs = [], {}
    prev = None
    for frame in sorted(per_frame):
        cut = cut_of(frame)
        for rule, sev, key, msg, boxes, *rest in per_frame[frame]:
            k = (rule, key)
            run = open_runs.get(k)
            if run and run["last"] == prev and run["cut"] == cut:
                run["last"] = frame; run["n"] += 1
                if sev == "ERROR" and run["sev"] != "ERROR":
                    run["sev"], run["msg"], run["boxes"], run["frame"] = sev, msg, boxes, frame
            else:
                if run:
                    finished.append(run)
                open_runs[k] = {"rule": rule, "sev": sev, "msg": msg, "first": frame, "last": frame, "n": 1, "cut": cut, "boxes": boxes, "frame": frame, "persist": bool(rest and rest[0])}
        prev = frame
    finished.extend(open_runs.values())
    finished = [r for r in finished if not (r["persist"] and r["n"] < 2)]  # a one-sample finding on a memory board is most likely a value in flight
    return [{"severity": r["sev"], "rule": r["rule"], "cut": r["cut"], "t0": round(r["first"] / FPS, 1), "t1": round(r["last"] / FPS, 1), "n": r["n"], "msg": r["msg"],
             "frame": r["frame"], "boxes": r["boxes"]} for r in sorted(finished, key=lambda r: (r["first"], r["rule"]))]


def analyze(frames, cut_of):
    per = {}
    for f, p in frames.items():
        if p.get("scene") == "whiteboard":
            per[int(f)] = frame_findings(p)
    return collect(per, cut_of)


def format_finding(f):
    when = f"@{f['t0']:.1f}s" if f["t0"] == f["t1"] else f"@{f['t0']:.1f}-{f['t1']:.1f}s"
    return f"{f['severity']:<5} {f['cut']} {when} [{f['rule']}] {f['msg']}" + (f" (seen in {f['n']} samples)" if f["n"] > 1 else "")
