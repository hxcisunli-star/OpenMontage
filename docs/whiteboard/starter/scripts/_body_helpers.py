SIDS = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]
B = [0.0] + [round(sec_tl[s]["start"] - 0.35, 2) for s in SIDS[1:]] + [round(TOTAL + 0.4, 2)]
K = {f"K{i+1}": (B[i], B[i + 1]) for i in range(8)}
cuts = {}
GOLD = "#D9A400"


def title(b, text, at):
    b.write(text, 420, 46, at, size=62, dur=1.4)
    b.stroke("line", at + 0.7, 0.7, color="#CBD5E1", width=3, x1=80, y1=160, x2=1840, y2=160)


def cell(cid, x, y, value, at, w=170, h=130, name="", **kw):
    """Memory cell (hand font). Values never contain a zero: numbers with zeros go through mono() instead."""
    assert str(value) != "0"
    d = {"id": cid, "name": name, "value": str(value), "x": x, "y": y, "w": w, "h": h, "at": at}
    d.update({k: v for k, v in kw.items() if v is not None})
    return d


def setv(cells, cid, at, value):
    for c in cells:
        if c["id"] == cid:
            c.setdefault("sets", []).append({"at": round(at, 2), "value": str(value)}); return
    raise KeyError(cid)


def dim(cells, cid, dim_at, until=None):
    for c in cells:
        if c["id"] == cid:
            c["dimAt"] = dim_at
            if until is not None:
                c["until"] = until
            return
    raise KeyError(cid)


def mono(b, text, x, y, at, size=36, dur=None, indent=0, **kw):
    """Code is always written in the monospace font; indentation is a shift in x (leading spaces are collapsed by SVG)."""
    d = dur if dur is not None else max(0.8, 0.05 * len(text))
    b.write(text, x + indent * 4 * size * 0.6, y, at, size=size, dur=d, font="mono", **kw)


def hand_mono(b, hand, mono_t, x, y, at, size=34, color=None, dur=1.6, until=None, mcolor=None):
    """A line mixing hand-written Chinese and a monospace word."""
    b.write(hand, x, y, at, size=size, dur=dur, color=color, until=until)
    mono(b, mono_t, x + est_w(hand, size) + 10, y + 2, at + dur, size=size, dur=0.6, color=mcolor or color, until=until)


def code(b, lines, x, y, ats, size=34, lh=None, until=None, colors=None):
    """Write code lines (list of (text, indent_level)); ats[i] is None to skip a line (its height is kept)."""
    lh = lh or size * 1.45
    for i, (ln, ind) in enumerate(lines):
        if ats[i] is None:
            continue
        mono(b, ln, x, y + i * lh, ats[i], size=size, indent=ind, until=until, color=(colors or {}).get(i))


def ring(b, c, at, until, r=82, color=GOLD):
    b.stroke("circle", at, 0.6, color=color, width=7, cx=c["x"] + c["w"] / 2, cy=c["y"] + c["h"] / 2, r=r, until=until)


def under(b, x, y, w, at, until, color=GOLD):
    b.stroke("underline", at, 0.45, color=color, width=7, x=x, y=y, w=w, until=until)


def box(b, x, y, w, h, at, until=None, color=GOLD, width=6):
    b.stroke("rect", at, 0.6, color=color, width=width, x=x, y=y, w=w, h=h, until=until)


def slash(b, c, at, until=None):
    """The empty slip: a red diagonal across the cell."""
    b.stroke("line", at, 0.4, color=RED, width=7, x1=c["x"] + 22, y1=c["y"] + c["h"] - 10, x2=c["x"] + c["w"] - 22, y2=c["y"] + 10, until=until)


def zone(b, x, y, w, h, label, at, until=None, size=30, color=GREY, lx=None):
    """A labelled frame: 'function' (the function's own slips), 'hospital' (cards that stay) or 'main'. lx moves the label."""
    b.stroke("rect", at, 0.8, width=5, x=x, y=y, w=w, h=h, until=until)
    b.write(label, x + 14 if lx is None else lx, y + 6, at + 0.5, size=size, dur=0.9, color=color, until=until)


def beds(cells, prefix, x0, y, vals, at, n=3, w=170, h=100, gap=60, until=None, **kw):
    """A row of beds; vals is a list of strings ('' for an empty bed)."""
    out = []
    for j in range(n):
        out.append(cell(f"{prefix}{j}", x0 + (w + gap) * j, y, vals[j], at + 0.25 * j, w=w, h=h, until=until, **kw))
    cells.extend(out)
    return out
