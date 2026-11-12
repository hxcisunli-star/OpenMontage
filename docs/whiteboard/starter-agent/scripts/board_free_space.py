"""Where is the board occupied?  Read-only helper for the robot choreography (read-only).
usage as module: from board_free_space import occupied, free_spots"""
import json, os
from project_paths import P
D = json.loads((P / "artifacts/whiteboard_scenes.json").read_text(encoding="utf-8"))
CUTS = {c["id"]: (c["in_seconds"], c["out_seconds"]) for c in json.loads((P / "render_props.json").read_text(encoding="utf-8"))["cuts"]}


def tw(text, size):
    return sum(size * (1.0 if ord(ch) > 0x2E80 else 0.58) for ch in text)


def rect_of(it):
    k = it["kind"]
    if k == "write":
        w = tw(it["text"], it["size"]); h = it["size"] * 1.25; x = it["x"]
        al = it.get("align", "left")
        x0 = x if al == "left" else (x - w / 2 if al == "center" else x - w)
        return (x0, it["y"], x0 + w, it["y"] + h)
    if k == "image":
        return (it["x"], it["y"], it["x"] + it["w"], it["y"] + it["h"])
    if k == "stroke":
        s = it["shape"]
        if s == "path": return tuple(it["box"])
        if s == "rect": return (it["x"], it["y"], it["x"] + it["w"], it["y"] + it["h"])
        if s in ("line", "arrow"):
            p = it.get("width", 3) + 3
            return (min(it["x1"], it["x2"]) - p, min(it["y1"], it["y2"]) - p, max(it["x1"], it["x2"]) + p, max(it["y1"], it["y2"]) + p)
        if s == "circle": return (it["cx"] - it["r"], it["cy"] - it["r"], it["cx"] + it["r"], it["cy"] + it["r"])
        if s == "underline": return (it["x"], it["y"] - 6, it["x"] + it["w"], it["y"] + 6)
    return None


def occupied(cid, t0, t1):
    """rects of every non-character item visible at any moment in [t0,t1] (absolute video seconds); y<165 (title band) and y>895 (subtitle band) ignored"""
    cin, cout = CUTS[cid]; out = []
    for it in D[cid]["items"]:
        if it["kind"] == "image":
            n = os.path.basename(it["src"])
            if n.startswith(("teacher_", "robot_", "schoollogo")): continue
        r = rect_of(it)
        if r is None: continue
        a = it["at"] + cin
        u = (it["until"] if it.get("until") is not None else cout - cin) + cin
        if u <= t0 or a >= t1: continue
        if r[3] < 165 or r[1] > 895: continue
        out.append((r, it))
    return out


def free_spots(cid, t0, t1, w=190, h=310, xs=range(100, 1320, 20), bottoms=(760, 800, 840, 880), pad=14):
    """robot rects (w x h, feet at `bottom`) that touch no occupied rect during [t0,t1]"""
    occ = [r for r, _ in occupied(cid, t0, t1)]
    res = []
    for b in bottoms:
        for cx in xs:
            x0, x1, y0, y1 = cx - w / 2, cx + w / 2, b - h, b
            if all(x1 + pad <= r[0] or x0 - pad >= r[2] or y1 + pad <= r[1] or y0 - pad >= r[3] for r in occ):
                res.append((cx, b))
    return res


def runs(spots):
    """compress spots to x-ranges per bottom"""
    by = {}
    for cx, b in spots: by.setdefault(b, []).append(cx)
    out = {}
    for b, l in by.items():
        l.sort(); seg = [[l[0], l[0]]]
        for v in l[1:]:
            if v - seg[-1][1] <= 20: seg[-1][1] = v
            else: seg.append([v, v])
        out[b] = seg
    return out
