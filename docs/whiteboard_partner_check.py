#!/usr/bin/env python3
"""Partner check for lessons whose AI partner speaks with its own voice (script.metadata.partner_lines; lesson 3 onwards).  Reads the built boards (render_props.json), the real
narration timeline and the script, and checks what lint, the layout check and the last-item check cannot:

  1  every real partner clip (narration_timeline.json, speaker "partner") lies inside a stretch where a robot_ picture is on stage, arriving at least 0.5 s before the clip starts and
     staying at least 0.25 s after it ends (a line of 1 s is over before a robot that starts to walk in at the first word has arrived)
  2  every partner line appears word for word as a bubble: consecutive `write` items whose texts join to the line (a bubble may break only at punctuation), starting between 2.5 s before
     and 0.8 s after the clip starts and staying on the board until the clip ends
  3  every robot interval contains a partner clip (the partner is on stage only around its own lines)
  4  the partner's pictures are listed before the teacher's (drawn behind her), see Board._stage_robot in the starter head

Usage:  .venv/bin/python docs/whiteboard_partner_check.py projects/<lesson>      (exit 1 on any FAIL; rebuild_edit.sh of the agent starter runs it when the script has partner_lines)
Why it exists: lesson 3's first sample had the partner's wave pose and point pose both on stage for 25 s (two robots on top of each other) and a 1.1 s line whose robot walked in during the
line; the first version of these checks lived in projects/agent-sampling-temp-cn/code/check_boards.py (E117, E118)."""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    P = Path(sys.argv[1])
    props = json.loads((P / "render_props.json").read_text(encoding="utf-8"))
    tl = json.loads((P / "assets/audio/narration_timeline.json").read_text(encoding="utf-8"))
    script = json.loads((P / "artifacts/script.json").read_text(encoding="utf-8"))
    lines_by_sec = script.get("metadata", {}).get("partner_lines", {})
    fail = []
    cuts = {c["id"]: c for c in props["cuts"]}
    secs = tl["sections"]
    for i, sec in enumerate(secs):
        cid = f"K{i + 1}"
        c = cuts.get(cid)
        if c is None:      # a partial build
            continue
        t0 = float(c["in_seconds"])
        items = c["whiteboard"]["items"]

        def span(it):
            a = it["at"]
            u = it.get("until")
            return (t0 + a if a >= 0 else t0 - 10), (t0 + u if u is not None else float(c["out_seconds"]))
        robots = sorted(span(it) + (it["src"].rsplit("/", 1)[-1],) for it in items if it["kind"] == "image" and "/robot_" in it["src"])
        merged = []
        for a, u, n in robots:
            if merged and a <= merged[-1][1] + 0.25:
                merged[-1][1] = max(merged[-1][1], u)
            else:
                merged.append([a, u, n])
        clips = [x for x in sec["clips"] if x["speaker"] == "partner"]
        expected = lines_by_sec.get(sec["id"], [])
        if sorted(x["text"] for x in clips) != sorted(expected):
            fail.append(f"{cid}: partner clips of the timeline {[x['text'] for x in clips]} differ from script.metadata.partner_lines {expected}")
        for cl in clips:
            if not any(a <= cl["start"] - 0.5 and u >= cl["end"] + 0.25 for a, u, _ in merged):
                fail.append(f"{cid}: partner clip {cl['start']:.2f}-{cl['end']:.2f} {cl['text']!r} is not covered by a robot on stage (arrive >= 0.5 s before, stay >= 0.25 s after)")
        for a, u, n in merged:
            if not any(a <= cl["start"] and cl["end"] <= u for cl in clips):
                fail.append(f"{cid}: robot on stage {a:.2f}-{u:.2f} contains no partner clip")
        writes = sorted(((span(it)[0], span(it)[1], it["text"]) for it in items if it["kind"] == "write"), key=lambda w: w[0])
        for cl in clips:
            line, found = cl["text"], None
            for i0 in range(len(writes)):
                acc = ""
                for j in range(i0, min(i0 + 5, len(writes))):
                    acc += writes[j][2].strip()
                    if acc == line:
                        found = (writes[i0][0], min(w[1] for w in writes[i0:j + 1]))
                        break
                    if not line.startswith(acc):
                        break
                if found:
                    break
            if not found:
                fail.append(f"{cid}: no bubble reads {line!r} word for word")
                continue
            if not (cl["start"] - 2.5 <= found[0] <= cl["start"] + 0.8):
                fail.append(f"{cid}: bubble for {line!r} starts at {found[0]:.2f}, the clip at {cl['start']:.2f} (expected -2.5 .. +0.8 s)")
            if found[1] < cl["end"] - 0.01:
                fail.append(f"{cid}: bubble for {line!r} leaves at {found[1]:.2f}, before the clip ends at {cl['end']:.2f}")
        order = [it["src"].rsplit("/", 1)[-1] for it in items if it["kind"] == "image" and it.get("layer") == "top"]
        ft = min((k for k, n in enumerate(order) if n.startswith("teacher_")), default=None)
        lr = max((k for k, n in enumerate(order) if n.startswith("robot_")), default=None)
        if ft is not None and lr is not None and lr > ft:
            fail.append(f"{cid}: a partner picture is listed after a teacher picture (it would be drawn in front of her)")
        print(f"{cid}: robot on stage {[(round(a, 2), round(u, 2)) for a, u, _ in merged]}; partner clips {[(x['start'], x['end']) for x in clips]}")
    for f in fail:
        print("FAIL", f)
    print(f"partner check: {len(fail)} failure(s)")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
