"""Shared timing helpers for whiteboard lessons: when does every pen item of a board finish drawing, and how long before the board fades out?
Mirrors remotion-composer/src/components/WhiteboardScene.tsx (default durations, code lines, fade-out).
Used by whiteboard_last_item_check.py, whiteboard_thumb_check.py and whiteboard_last_item_report.py."""
import json
from pathlib import Path

PEN_KINDS = ("write", "stroke", "code", "image")  # what the teacher "writes"; memory cells are drawn boxes and only counted with include_memory
BOX = 0.5                                          # seconds a memory box takes to draw (WhiteboardScene.tsx)


def _f(v, default):
    return float(v) if v is not None else default


def item_span(it):
    """(start, end, label) of one board item in seconds relative to the cut start, or None for kinds that do not draw."""
    k = it.get("kind")
    at = _f(it.get("at"), 0.0)
    if k == "write":
        text = it.get("text", "")
        dur = _f(it.get("dur"), max(0.6, len(text) * 0.12))
        return at, at + dur, text
    if k == "stroke":
        return at, at + _f(it.get("dur"), 0.7), str(it.get("shape", "stroke"))
    if k == "image":
        return at, at + _f(it.get("dur"), 1.2), "image"
    if k == "code":
        lines = it.get("lines", [])
        line_dur = _f(it.get("lineDur"), 1.2)
        gap = _f(it.get("lineGap"), line_dur)
        starts = it.get("lineAts") or [at + i * gap for i in range(len(lines))]
        if not starts:
            return None
        i = max(range(len(starts)), key=lambda j: starts[j])
        return min(starts), max(starts) + line_dur, lines[i] if i < len(lines) else "code"
    if k == "memory":
        ends = [(c.get("at", 0) + BOX, c.get("name", "cell")) for c in it.get("cells", [])]
        ends += [(c.get("addrAt", c.get("at", 0) + BOX) + 0.5, c.get("name", "cell")) for c in it.get("cells", []) if c.get("addr")]
        ends += [(s["at"] + 0.5, c.get("name", "cell")) for c in it.get("cells", []) for s in c.get("sets", [])]
        ends += [(a.get("at", 0) + _f(a.get("dur"), 0.8), "arrow") for a in it.get("arrows", [])]
        if not ends:
            return None
        e = max(ends)
        return min(x[0] for x in ends) - 0.5, e[0], "memory:" + str(e[1])
    return None


def progress_at(it, t):
    """Fraction (0..1) of the item drawn at time t (relative to cut start). Code: the last line."""
    sp = item_span(it)
    if not sp:
        return 1.0
    s, e, _ = sp
    if it.get("kind") == "code":
        line_dur = _f(it.get("lineDur"), 1.2)
        s = e - line_dur
    return max(0.0, min(1.0, (t - s) / max(e - s, 1e-6)))


def load_project(proj):
    proj = Path(proj)
    scenes = json.loads((proj / "artifacts/whiteboard_scenes.json").read_text(encoding="utf-8"))
    ed = json.loads((proj / "artifacts/edit_decisions.json").read_text(encoding="utf-8"))
    return scenes, {c["id"]: c for c in ed["cuts"]}


def board_rows(proj, include_memory=False):
    """One row per board: id, in/out (absolute), length, fade start, last pen item (end, kind, text), margin, progress at fade start and at cut end."""
    scenes, cuts = load_project(proj)
    kinds = PEN_KINDS + (("memory",) if include_memory else ())
    rows = []
    for cid, board in scenes.items():
        cut = cuts[cid]
        length = cut["out_seconds"] - cut["in_seconds"]
        fade_len = _f(board.get("fadeOutSeconds"), 0.4)
        fade = length - fade_len
        spans = []
        for it in board["items"]:
            if it.get("kind") in kinds:
                sp = item_span(it)
                if sp:
                    spans.append((sp[1], it, sp[2]))
        if not spans:
            continue
        end, it, label = max(spans, key=lambda x: x[0])
        rows.append({"id": cid, "in": cut["in_seconds"], "out": cut["out_seconds"], "length": length, "fade_len": fade_len, "fade_start": fade,
                     "last_end": end, "last_kind": it["kind"], "last_text": str(label)[:40], "margin": fade - end,
                     "progress_at_fade": progress_at(it, fade), "progress_at_end": progress_at(it, length)})
    return rows
