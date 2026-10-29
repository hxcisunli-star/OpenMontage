#!/usr/bin/env python3
"""Sound-effect cues for a whiteboard lesson: derived from the board data, mixed into the narration BEFORE rendering (the composer plays one narration track).

  cues  <project> [--cues PROFILE] [--timeline T.json] [--out cues.json]    list the cues the boards ask for (and the ones the quiz-silence rule drops)
  mix   <project> --narration N.wav --out OUT.wav [--cues PROFILE] [--timeline T.json] [--props render_props.json]
                                                            narration + cues -> a 48 kHz mono wav (the final mux upsamples the narration to 48 kHz anyway)
  check <narration.wav> <mixed.wav>                          loudness (integrated, LRA, true peak) and the silences of both; the silences must be identical
  apply <project> [--cues PROFILE] [--undo]                  the lesson-facing command: cues -> mix -> assets/audio/narration_sfx.wav -> check (silences identical, loudness within 0.3 LU,
                                                            else nothing is changed) -> render_props.json `audio.narration.src` points to the mix (the plain path is kept in `src_plain`;
                                                            `--undo` puts it back).  The chunk fingerprints ignore `audio`, so no board is re-rendered; run it after every build of the props
                                                            and before the render, so the sample and the final both carry it.

PROFILE (--cues): `light` (the default, a decision of 2026-10-21) = the answer chime plus the cues a board asks for by name (`sfx` field); `all` = also pop and whoosh; `none` = only the
named ones; or a comma list of cue names (plus the named ones).  Why light: the narration is the main channel and the board has text, so sounds that carry no information (a pop for every
note) are extraneous material (the coherence principle of multimedia learning); the chime has a job: it marks "the silence is over, the answer comes".  `all` was the first version and is
kept for lessons where the author hears that it helps.

Cues, from the items of every whiteboard cut (absolute time = cut start + item time; items with at < 0 are already drawn and make no sound):
  pop            a note / bubble / block fades in (a filled `path` stroke with `shadow` or a role outline that is not a top-layer copy)
  whoosh-short   something flies: an item whose `move` keys travel >= 150 px (one whoosh per cluster of flights within 0.6 s), 15 ms BEFORE the motion starts
  chime          an answer is revealed: narration_timeline.json `quiz[].answer_not_before` + 0.3 s
  any sample     an item with the optional field `sfx: "<name>"` (the composer ignores the field): the cue goes at the item's `at`
The level is RELATIVE to the narration: every sample is scaled so that its own RMS sits `gain_db` below the narration's speech RMS (-18 dB for pop and whoosh, -16 dB for the chime; the
sound-design guide says -18..-12 dB).  QUIZ SILENCE: the 3 s after a prediction question are real silence (the verifier looks for them with silencedetect), so no cue may start in
[question_end, answer_not_before) and a cue that would run into it is cut and faded out before it.  Background music stays off (a user decision); this is sound effects only.
Files: docs/whiteboard/sfx/*.mp3 (Pixabay Content License, no attribution; see CREDITS.md and manifest.json)."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SFX_DIR = ROOT / "docs" / "whiteboard" / "sfx"
SR = 48000
FLIGHT_PX, CLUSTER_S, PRE_ROLL_S, MERGE_S = 150.0, 0.6, 0.015, 0.08
LEVELS = {"pop": -18.0, "whoosh-short": -18.0, "chime": -16.0}
DEFAULT_LEVEL = -18.0
PEAK_LIMIT = 10 ** (-1.0 / 20)   # -1 dBFS


def decode(path, sr=SR):
    """Any audio file -> mono float32 at `sr`."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
    if r.returncode:
        sys.exit(f"ffmpeg could not read {path}: {r.stderr.decode()[-200:]}")
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def rms_db(x, floor=1e-4):
    x = x[np.abs(x) > floor] if np.any(np.abs(x) > floor) else x
    return 20 * np.log10(max(float(np.sqrt(np.mean(x ** 2))), 1e-9))


def speech_rms_db(narr):
    """RMS of the narration over its speech (frames above -45 dBFS), in dBFS."""
    frame = SR // 20
    n = len(narr) // frame
    if not n:
        return rms_db(narr)
    fr = narr[: n * frame].reshape(n, frame)
    rms = np.sqrt((fr ** 2).mean(axis=1))
    voiced = fr[rms > 10 ** (-45 / 20)]
    return rms_db(voiced.reshape(-1)) if voiced.size else rms_db(narr)


def select_cues(cues, which="all"):
    """The profile filter (see the module doc): cues a board asks for by name (`explicit`) are always kept."""
    which = (which or "all").strip()
    if which == "all":
        return cues
    names = {"light": {"chime"}, "none": set()}.get(which) if which in ("light", "none") else {x.strip() for x in which.split(",") if x.strip()}
    return [c for c in cues if c.get("explicit") or c["name"] in names]


def derive_cues(props, quiz=(), which="all"):
    """[{t, name, gain_db, why}] sorted by time, before the quiz-silence rule; `which` is the profile (default: everything the boards could ask for)."""
    cues, flights = [], []
    for cut in props.get("cuts", []):
        wb = cut.get("whiteboard")
        if not wb:
            continue
        base = float(cut.get("in_seconds", 0))
        end = float(cut.get("out_seconds", 1e9))
        for it in wb.get("items", []):
            at = it.get("at", 0)
            if at is None or at < 0:
                continue   # already drawn (relist) or no time: no sound
            t = base + float(at)
            if t >= end:
                continue   # the cut ends before it starts (a board cut short for a video clip): nothing of it is seen
            mv = sorted(it.get("move") or [], key=lambda k: k.get("at", 0))
            if it.get("sfx"):
                cues.append({"t": t, "name": it["sfx"], "why": f"item field sfx ({it.get('kind')})", "explicit": True})
            elif (it.get("kind") == "stroke" and it.get("shape") == "path" and it.get("fill") and (it.get("fillOpacity") is None or it["fillOpacity"] >= 0.9)
                  and it.get("layer") != "top" and not mv):
                cues.append({"t": t + 0.05, "name": "pop", "why": "a note / bubble / block appears"})
            if len(mv) >= 2 and it.get("kind") in ("stroke", "write", "image") and mv[0].get("at", -1) >= 0:
                travel = max(abs(mv[-1].get("dx", 0) - mv[0].get("dx", 0)), abs(mv[-1].get("dy", 0) - mv[0].get("dy", 0)))
                if travel >= FLIGHT_PX and base + float(mv[0]["at"]) < end:
                    flights.append(base + float(mv[0]["at"]))
    last = None
    for t in sorted(flights):
        if last is None or t - last >= CLUSTER_S:   # one whoosh per cluster of flights
            cues.append({"t": t - PRE_ROLL_S, "name": "whoosh-short", "why": "something flies"})
            last = t
    for q in quiz:
        cues.append({"t": float(q["answer_not_before"]) + 0.3, "name": "chime", "why": f"answer revealed ({q.get('section_id', '?')})"})
    cues = select_cues(cues, which)
    cues.sort(key=lambda c: c["t"])
    merged = []
    for c in cues:   # two items appearing in the same instant are one sound, not a doubled one
        if merged and merged[-1]["name"] == c["name"] and c["t"] - merged[-1]["t"] < MERGE_S:
            continue
        merged.append(c)
    for c in merged:
        c["gain_db"] = LEVELS.get(c["name"], DEFAULT_LEVEL)
    return merged


def apply_quiz_rule(cues, quiz, lengths):
    """Drop cues that start in a quiz silence; mark cues that run into one for a cut at the silence start.  Returns (kept, dropped)."""
    kept, dropped = [], []
    for c in cues:
        n = lengths.get(c["name"], 1.0)
        hit = None
        for q in quiz:
            a, z = float(q["question_end"]), float(q["answer_not_before"])
            if a - 0.01 <= c["t"] < z:
                hit = ("starts inside the quiz silence", None)
                break
            if c["t"] < a < c["t"] + n:
                hit = ("runs into the quiz silence", a)
        if hit and hit[1] is None:
            dropped.append({**c, "dropped": hit[0]})
        else:
            kept.append({**c, "cut_at": hit[1] if hit else None})
    return kept, dropped


def mix(narr, cues, library=None):
    """Narration + cues -> float32 mono at SR (same length as the narration)."""
    library = library or {}
    speech = speech_rms_db(narr)
    out = narr.copy()
    for c in cues:
        if c["name"] not in library:
            library[c["name"]] = decode(SFX_DIR / f"{c['name']}.mp3")
        s = library[c["name"]].copy()
        s *= 10 ** ((speech + c["gain_db"] - rms_db(s)) / 20)
        i0 = max(0, int(round(c["t"] * SR)))
        n = min(len(s), len(out) - i0)
        if c.get("cut_at") is not None:
            n = min(n, max(0, int((c["cut_at"] - 0.05 - c["t"]) * SR)))
            fade = min(n, int(0.04 * SR))
            if fade:
                s[n - fade:n] *= np.linspace(1, 0, fade)
        if n > 0 and i0 < len(out):
            seg = s[:n]
            base = out[i0:i0 + n]
            if np.max(np.abs(base + seg)) > PEAK_LIMIT:   # a cue on top of a narration peak backs off, so the mix stays under -1 dBFS (AAC overshoots)
                lo, hi = 0.0, 1.0
                for _ in range(14):
                    k = (lo + hi) / 2
                    lo, hi = (k, hi) if np.max(np.abs(base + k * seg)) <= PEAK_LIMIT else (lo, k)
                seg = seg * lo
                c["limited_to"] = round(float(lo), 3)
            out[i0:i0 + n] += seg
    return out


def write_wav(path, x):
    import wave
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


def measure(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true,silencedetect=n=-40dB:d=1.3", "-f", "null", "-"], capture_output=True, text=True).stderr
    last = r[r.rfind("Summary:"):]
    g = lambda pat: float(re.search(pat, last).group(1)) if re.search(pat, last) else None
    sil = [(round(float(a), 2), round(float(b), 2)) for a, b in zip(re.findall(r"silence_start: ([\d.]+)", r), re.findall(r"silence_end: ([\d.]+)", r))]
    return {"I": g(r"I:\s+(-?[\d.]+) LUFS"), "LRA": g(r"LRA:\s+([\d.]+) LU"), "peak": g(r"Peak:\s+(-?[\d.]+) dBFS"), "silences": sil}


def load_props(proj, props_name):
    return json.loads((Path(proj) / props_name).read_text(encoding="utf-8"))


def load_quiz(proj, timeline):
    p = Path(timeline) if timeline else Path(proj) / "assets/audio/narration_timeline.json"
    return json.loads(p.read_text(encoding="utf-8")).get("quiz", []) if p.exists() else []


def lengths():
    m = json.loads((SFX_DIR / "manifest.json").read_text(encoding="utf-8"))
    return {k: v["duration"] for k, v in m.items()}


def apply(proj, which="light", timeline=None, props_name="render_props.json", narration=None, out=None, undo=False, max_change=0.3):
    """The lesson-facing step: mix the cues of `which` into the narration, check it, and point the props' narration at the mix.  Returns the exit code."""
    proj = Path(proj)
    pp = proj / props_name
    props = json.loads(pp.read_text(encoding="utf-8"))
    nar = (props.get("audio") or {}).get("narration")
    if not nar or not nar.get("src"):
        sys.exit(f"{pp}: no audio.narration.src")
    if undo:
        if "src_plain" not in nar:
            print("nothing to undo: the props do not point to a mixed narration")
            return 0
        nar["src"] = nar.pop("src_plain")
        pp.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
        print(f"props narration is back at {nar['src']}")
        return 0
    src = narration or nar.get("src_plain") or nar["src"]   # a second run starts again from the plain narration, never from a mix
    quiz = load_quiz(proj, timeline)
    kept, dropped = apply_quiz_rule(derive_cues(props, quiz, which), quiz, lengths())
    if not kept:
        print(f"profile {which!r}: no cues in this lesson, the props are left as they are")
        return 0
    narr = decode(src)
    mixed = mix(narr, kept)
    out = Path(out) if out else proj / "assets/audio/narration_sfx.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_wav(out, mixed)
    m0, m1 = measure(src), measure(out)
    change = None if m0["I"] is None or m1["I"] is None else round(m1["I"] - m0["I"], 2)
    problems = []
    if m0["silences"] != m1["silences"]:
        problems.append(f"the silences differ: {m0['silences']} -> {m1['silences']}")
    if change is None or abs(change) > max_change:
        problems.append(f"the loudness changed by {change} LU (more than {max_change})")
    if problems:
        print("NOT applied (the props are untouched): " + "; ".join(problems))
        return 1
    nar["src_plain"] = src
    nar["src"] = str(out)
    pp.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    by = {}
    for c in kept:
        by[c["name"]] = by.get(c["name"], 0) + 1
    peak = float(np.max(np.abs(mixed)))
    print(f"applied profile {which!r}: {len(kept)} cues {by}, {len(dropped)} dropped by the quiz-silence rule; silences identical, loudness {change:+} LU, peak {20 * np.log10(max(peak, 1e-9)):.1f} dBFS")
    print(f"props narration -> {out} (plain narration kept in audio.narration.src_plain; `apply --undo` puts it back)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("cues", "mix"):
        p = sub.add_parser(name)
        p.add_argument("proj"); p.add_argument("--timeline"); p.add_argument("--props", default="render_props.json"); p.add_argument("--out"); p.add_argument("--cues", default="light")
        if name == "mix":
            p.add_argument("--narration", required=True)
    p = sub.add_parser("apply")
    p.add_argument("proj"); p.add_argument("--cues", default="light"); p.add_argument("--timeline"); p.add_argument("--props", default="render_props.json"); p.add_argument("--narration"); p.add_argument("--out")
    p.add_argument("--undo", action="store_true")
    p = sub.add_parser("check")
    p.add_argument("narration"); p.add_argument("mixed")
    a = ap.parse_args(argv)
    if a.cmd == "apply":
        return apply(a.proj, a.cues, a.timeline, a.props, a.narration, a.out, a.undo)
    if a.cmd == "check":
        m0, m1 = measure(a.narration), measure(a.mixed)
        same = m0["silences"] == m1["silences"]
        print(f"narration: {m0}\nmixed    : {m1}\nsilences identical: {same}; integrated loudness changed by {None if m0['I'] is None else round(m1['I'] - m0['I'], 2)} LU")
        return 0 if same else 1
    props, quiz = load_props(a.proj, a.props), load_quiz(a.proj, a.timeline)
    kept, dropped = apply_quiz_rule(derive_cues(props, quiz, a.cues), quiz, lengths())
    print(f"profile {a.cues!r}: {len(kept)} cues kept, {len(dropped)} dropped by the quiz-silence rule")
    for c in dropped:
        print(f"  dropped {c['name']} @{c['t']:.2f}s: {c['dropped']}")
    if a.cmd == "cues":
        if a.out:
            Path(a.out).write_text(json.dumps({"cues": kept, "dropped": dropped}, ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            for c in kept:
                print(f"  {c['t']:8.2f}s {c['name']:14s} {c['gain_db']:+.0f} dB  {c['why']}")
        return 0
    narr = decode(a.narration)
    out = mix(narr, kept)
    peak = float(np.max(np.abs(out)))
    write_wav(a.out, out)
    backed = [c for c in kept if "limited_to" in c]
    print(f"mixed {a.out}: {len(out) / SR:.2f} s, peak {20 * np.log10(max(peak, 1e-9)):.1f} dBFS; {len(backed)} cue(s) backed off to stay under -1 dBFS"
          + ("  !! above -1 dBFS" if peak > PEAK_LIMIT * 1.001 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
