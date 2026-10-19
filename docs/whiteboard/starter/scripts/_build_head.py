"""Build edit_decisions, whiteboard scene data and render_props for __PID__ (lesson __N__).

All times come from assets/audio/narration_timeline.json (real TTS durations) and the
estimated caption timing in assets/captions/captions.json (phrase anchoring via Finder).
One whiteboard cut per script section (the board is cleared between sections).
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path("/home/MyProject/OpenMontage")
PID = "__PID__"
PROJ = ROOT / "projects" / PID
ART = PROJ / "artifacts"
AUD = PROJ / "assets" / "audio"
IMG = PROJ / "assets" / "images"
CAP = PROJ / "assets" / "captions" / "captions.json"

caps = json.loads(CAP.read_text(encoding="utf-8"))
tl = json.loads((AUD / "narration_timeline.json").read_text(encoding="utf-8"))
sec_tl = {s["id"]: s for s in tl["sections"]}
TOTAL = tl["total_seconds"]

PUNCT = "，。？！：；、,.?!:;"
LATIN_CAPS_FONT = "'DejaVu Sans', WBHand, 'Noto Sans SC', sans-serif"
INK, RED, GREEN, GREY = "#111827", "#DC2626", "#15803D", "#64748B"

# Single uppercase Latin letters are square glyphs in the handwriting font; use a Latin font.
for _c in caps:
    _w = "".join(ch for ch in _c["word"] if ch not in PUNCT and not ch.isspace())
    if re.fullmatch(r"[A-Zco]", _w):
        _c["fontFamily"] = LATIN_CAPS_FONT

# ---- caption paging: break at punctuation, split long clauses at natural word endings
_SENT_END, _SOFT, _SAFE_END = "。？！：；", "，、", "的了和把是就在让会它我你们"


def _repage(tokens):
    for t in tokens:
        t.pop("pageBreakAfter", None)
    seg, segs = [], []
    for i, t in enumerate(tokens):
        seg.append(i)
        w = t["word"].rstrip()
        if w and w[-1] in _SENT_END:
            segs.append(seg); seg = []
        elif w and w[-1] in _SOFT and len(seg) >= 5:
            segs.append(seg); seg = []
    if seg:
        segs.append(seg)

    def split(idx, limit=14):
        if len(idx) <= limit:
            return [idx]
        L = len(idx)
        lo, hi = int(L * 0.35), int(L * 0.65)
        cands = [k for k in range(max(lo, 3), min(hi, L - 3)) if tokens[idx[k]]["word"].rstrip()[-1:] in _SAFE_END]
        k = min(cands, key=lambda c: abs(c - L / 2)) if cands else L // 2
        return split(idx[:k + 1], limit) + split(idx[k + 1:], limit)

    for sg in segs:
        for part in split(sg):
            tokens[part[-1]]["pageBreakAfter"] = True
    return tokens


caps = _repage(caps)
CAP.write_text(json.dumps(caps, ensure_ascii=False), encoding="utf-8")


# ----------------------------------------------------------------- anchors from caption timing
class Finder:
    def __init__(self, sid):
        s = sec_tl[sid]
        lo, hi = (s["start"] - 0.05) * 1000, (s["end"] + 0.05) * 1000
        self.toks = [c for c in caps if lo <= c["startMs"] <= hi]
        self.plain, self.idx = "", []
        for i, t in enumerate(self.toks):
            w = "".join(ch for ch in t["word"] if ch not in PUNCT and not ch.isspace())
            self.plain += w
            self.idx += [i] * len(w)
        self.cur = 0
        self.sid = sid

    def at(self, phrase, end=False):
        p = self.plain.find(phrase, self.cur)
        if p < 0:
            raise SystemExit(f"anchor not found in {self.sid}: {phrase!r} (after {self.cur})")
        i0, i1 = self.idx[p], self.idx[p + len(phrase) - 1]
        self.cur = p + len(phrase)
        return self.toks[i1]["endMs"] / 1000 if end else self.toks[i0]["startMs"] / 1000


def est_w(text, size):
    return sum(size * (0.55 if ord(c) < 128 else 1.0) for c in text.split("\n")[0])


# ----------------------------------------------------------------- board builder
class Board:
    def __init__(self, cid, cin, cout):
        self.cid, self.cin, self.cout = cid, cin, cout
        self.items, self.keys = [], []

    def r(self, t):
        return round(max(t - self.cin, 0.3), 2)

    def key(self, t, x, y):
        self.keys.append((self.r(t), round(x), round(y)))

    def write(self, text, x, y, at, size=60, dur=None, color=None, align="left", until=None, font=None):
        chars = len(text.replace("\n", ""))
        d = dur if dur is not None else max(0.6, chars * 0.11)
        it = {"kind": "write", "text": text, "x": x, "y": y, "at": self.r(at), "dur": round(d, 2), "size": size, "align": align}
        if color:
            it["color"] = color
        if until is not None:
            it["until"] = self.r(until)
        if font:
            it["font"] = font
        self.items.append(it)
        w = est_w(text, size) * (1.1 if font == "mono" else 1.0)
        x0 = x - w / 2 if align == "center" else x
        self.key(at, x0, y + size * 0.8)
        self.key(at + d, x0 + w, y + size * 0.8)

    def stroke(self, shape, at, dur=0.7, color=None, width=6, until=None, **kw):
        it = {"kind": "stroke", "shape": shape, "at": self.r(at), "dur": dur, "width": width, **kw}
        if color:
            it["color"] = color
        if until is not None:
            it["until"] = self.r(until)
        self.items.append(it)
        if shape in ("line", "arrow"):
            self.key(at, kw["x1"], kw["y1"]); self.key(at + dur, kw["x2"], kw["y2"])
        elif shape == "rect":
            self.key(at, kw["x"], kw["y"]); self.key(at + dur, kw["x"] + kw["w"], kw["y"] + kw["h"])
        elif shape == "circle":
            self.key(at, kw["cx"] - kw["r"], kw["cy"]); self.key(at + dur, kw["cx"], kw["cy"] - kw["r"])
        elif shape == "underline":
            self.key(at, kw["x"], kw["y"]); self.key(at + dur, kw["x"] + kw["w"], kw["y"])

    def image(self, name, cx, top, h, at, dur=1.0, reveal="down", until=None):
        path = IMG / f"{name}.png"
        im = Image.open(path)
        w = round(im.width * h / im.height)
        x = round(cx - w / 2)
        it = {"kind": "image", "src": str(path), "x": x, "y": round(top), "w": w, "h": round(h),
              "at": self.r(at), "dur": dur, "reveal": reveal}
        if until is not None:
            it["until"] = self.r(until)
        self.items.append(it)
        self.key(at, cx, top); self.key(at + dur, cx, top + h)

    def code(self, lines, x, y, line_ats, highlights, size=33, line_dur=0.9):
        lat = [self.r(t) for t in line_ats]
        hl = [{**h, "at": self.r(h["at"])} for h in highlights]
        self.items.append({"kind": "code", "lines": lines, "x": x, "y": y, "at": min(lat), "lineAts": lat,
                           "lineDur": line_dur, "size": size, "highlights": hl})
        lh = size * 1.5
        for i, t in sorted(enumerate(line_ats), key=lambda p: p[1]):
            self.key(t, x, y + i * lh + size)
            self.key(t + line_dur, x + len(lines[i]) * size * 0.6, y + i * lh + size)

    def mem(self, cells, arrows=()):
        cs = []
        for c in cells:
            d = dict(c)
            d["at"] = self.r(d["at"])
            if "addrAt" in d:
                d["addrAt"] = self.r(d["addrAt"])
            for k in ("dimAt", "until"):
                if d.get(k) is not None:
                    d[k] = self.r(d[k])
            if d.get("sets"):
                d["sets"] = [{"at": self.r(s["at"]), "value": s["value"]} for s in d["sets"]]
            cs.append(d)
            self.key(c["at"], c["x"] + c.get("w", 190) / 2, c["y"] - 10)
        ar = []
        for a in arrows:
            d = dict(a)
            d["at"] = self.r(d["at"])
            if d.get("until") is not None:
                d["until"] = self.r(d["until"])
            ar.append(d)
        self.items.append({"kind": "memory", "cells": cs, "arrows": ar})

    def check(self, cx, cy, at, color=GREEN):
        self.stroke("line", at, 0.25, color=color, width=9, x1=cx - 26, y1=cy, x2=cx - 6, y2=cy + 24)
        self.stroke("line", at + 0.25, 0.35, color=color, width=9, x1=cx - 6, y1=cy + 24, x2=cx + 34, y2=cy - 26)

    def cross(self, cx, cy, at, color=RED):
        self.stroke("line", at, 0.25, color=color, width=9, x1=cx - 24, y1=cy - 24, x2=cx + 24, y2=cy + 24)
        self.stroke("line", at + 0.25, 0.25, color=color, width=9, x1=cx + 24, y1=cy - 24, x2=cx - 24, y2=cy + 24)

    def data(self):
        out, last = [], -1
        for at, x, y in sorted(self.keys):
            if at <= last:
                at = round(last + 0.02, 2)
            out.append({"at": at, "x": x, "y": y})
            last = at
        return {"items": self.items, "pointer": out, "inkColor": INK, "accentColor": RED, "fadeOutSeconds": 0.4}


def A(sid, phrase, after=None, end=False):
    """Time of a phrase in a section (independent cursor, optional `after` anchor)."""
    f = Finder(sid)
    if after:
        f.at(after)
    return f.at(phrase, end=end)


