#!/usr/bin/env python3
"""Validate one section file of the scene plan.   usage: python3 validate_section.py <sid> <file.json> [script.json]
Exit code 1 on any ERROR; prints the estimated time of every event so you can see where the board is busy and where it is empty."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_common import ALLOWED_POSES, DEVICES, Timing, load_script, plain  # noqa: E402

from scene_common import _CFG
FORBID = _CFG["forbid_terms"]
MAX_GAP = 9.5   # seconds between neighbouring events of one section (the lint of the script allows 10 s between picture cues)
HEAD = re.compile(r"^\s*呈现手段：([^；。]*)")


def main(sid, path, script_path):
    err, warn = [], []
    script = load_script(script_path)
    T = Timing(script, sid)
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    for k in ("title", "layout", "phases", "events"):
        if k not in d:
            err.append(f"missing key {k}")
    if err:
        return err, warn
    if re.search(r"[A-Za-z0-9]", d["title"]):
        err.append("title must be Chinese only (no Latin letters or digits)")
    if len(d["title"]) > 14:
        warn.append("title longer than 14 characters")
    pids = [p["id"] for p in d["phases"]]
    if not (1 <= len(pids) <= 4) or pids != [f"p{i + 1}" for i in range(len(pids))]:
        err.append(f"phase ids must be p1..pN with 1 <= N <= 4, got {pids}")
    used_devices = set()
    for p in d["phases"]:
        m = HEAD.match(p.get("movement", ""))
        if not m:
            err.append(f"{p['id']}: movement must start with 呈现手段：手段一、手段二；")
            continue
        names = [x.strip() for x in re.split(r"[、,，]", m.group(1)) if x.strip()]
        bad = [x for x in names if x not in DEVICES]
        if bad or not names:
            err.append(f"{p['id']}: unknown device {bad} (allowed: {'、'.join(DEVICES)})")
        used_devices.update(names)
        if set(names) == {"纯板书"}:
            warn.append(f"{p['id']}: only 纯板书")
    pt, cursor, last_p, last_t = T.pt, 0, 0, -1.0
    rows, ev_phase_seen = [], []
    answer_needed = list(T.q_ends)
    cues = set()
    for k, e in enumerate(d["events"]):
        for key in ("cue", "phase", "action", "anchor"):
            if key not in e:
                err.append(f"event #{k}: missing {key}")
        if any(key not in e for key in ("cue", "phase", "action", "anchor")):
            continue
        if e["cue"] in cues:
            err.append(f"duplicate cue id {e['cue']}")
        cues.add(e["cue"])
        if not re.fullmatch(rf"{sid}-c\d\d", e["cue"]):
            err.append(f"{e['cue']}: cue id must look like {sid}-c01")
        if e["phase"] not in pids:
            err.append(f"{e['cue']}: phase {e['phase']} not in phases")
        else:
            pi = pids.index(e["phase"])
            if pi < last_p:
                err.append(f"{e['cue']}: phases must not go backwards")
            last_p = max(last_p, pi)
            ev_phase_seen.append(e["phase"])
        a = plain(e["anchor"])
        if not a or len(a) > 16:
            err.append(f"{e['cue']}: anchor must be 1..16 plain characters, got {len(a)}")
        p = pt.find(a, cursor)
        if p < 0:
            err.append(f"{e['cue']}: anchor {e['anchor']!r} not found in narration after position {cursor} (never loosen the search: change the plan)")
            continue
        cursor = p + len(a)
        t = T.start if k == 0 else max(T.est(p), last_t + 0.3)
        for f in e.get("follow_ups", []):
            fa = plain(f["anchor"])
            q = pt.find(fa, cursor)
            if q < 0:
                err.append(f"{e['cue']}: follow-up anchor {f['anchor']!r} not found after position {cursor}")
            else:
                cursor = q + len(fa)
        for qe in list(answer_needed):
            if p >= qe:
                is_last_q = T.q_ends.index(qe) == len(T.q_ends) - 1
                if "答案" not in e["action"] and not ("题卡" in e["action"] and not is_last_q):
                    err.append(f"{e['cue']}: the first event after a question must be the answer event and its action must contain 答案")
                answer_needed.remove(qe)
        text = e["action"]
        scrub = text
        for dv in DEVICES:
            scrub = scrub.replace(dv, "")
        bad = [w for w in FORBID if w in scrub]
        if bad:
            err.append(f"{e['cue']}: forbidden/old words in action: {bad}")
        if re.search(r"[①②③④⑤⑥⑦⑧⑨]", text):
            err.append(f"{e['cue']}: circled numerals are not in the handwriting font")
        for png in re.findall(r"[A-Za-z_]+\.png", text):
            if png not in ALLOWED_POSES:
                err.append(f"{e['cue']}: pose file {png} does not exist (allowed: {sorted(ALLOWED_POSES)})")
        last_t = t
        rows.append((e["cue"], round(t, 1), e["phase"], e["anchor"]))
    if answer_needed:
        err.append("a question has no answer event after it (the first event whose anchor starts after the question's last word)")
    first = d["events"][0] if d["events"] else None
    if first and plain(first["anchor"]) != pt[:len(plain(first["anchor"]))]:
        warn.append("the first event is not anchored at the very start of the section (it will be shown at the section start anyway)")
    for pid in pids:
        if pid not in ev_phase_seen:
            err.append(f"phase {pid} has no event")
    gaps = [round(b[1] - a[1], 1) for a, b in zip(rows, rows[1:])]
    tail = round(T.end - rows[-1][1], 1) if rows else None
    for a, b, g in zip(rows, rows[1:], gaps):
        if g > MAX_GAP:
            err.append(f"gap {g}s between {a[0]} and {b[0]} is longer than {MAX_GAP}s: add an event (a gag, a footnote, a small move) or move an anchor")
    if tail is not None and tail > 12:
        warn.append(f"the last event is {tail}s before the section ends")
    if len(used_devices - {"纯板书"}) < 2:
        warn.append("fewer than 2 presentation devices in this section")
    print(f"{sid}: {len(d['events'])} events, {len(pids)} phases, devices={sorted(used_devices)}, section {T.start:.1f}-{T.end:.1f}s, max gap {max(gaps) if gaps else None}s, tail {tail}s")
    for r in rows:
        print("  ", r)
    return err, warn


if __name__ == "__main__":
    sid, path = sys.argv[1], sys.argv[2]
    script_path = sys.argv[3] if len(sys.argv) > 3 else str(Path(__file__).resolve().parents[1] / "artifacts/script.json")
    e, w = main(sid, path, script_path)
    for x in w:
        print("WARN ", x)
    for x in e:
        print("ERROR", x)
    print(f"{sid}: {len(e)} error(s), {len(w)} warning(s)")
    sys.exit(1 if e else 0)
