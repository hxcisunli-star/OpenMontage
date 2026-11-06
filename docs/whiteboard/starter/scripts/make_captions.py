"""Estimated per-character caption timing for lesson __N__ from the real clips (no local ASR: the timing is an ESTIMATE)."""
import json, re, subprocess
from pathlib import Path
P = Path(__file__).resolve().parents[1]
tl = json.load(open(P / "assets/audio/narration_timeline.json", encoding="utf-8"))
script = {s["id"]: s for s in json.load(open(P / "artifacts/script.json", encoding="utf-8"))["sections"]}
quiz = json.load(open(P / "artifacts/script.json", encoding="utf-8"))["metadata"]["quiz_pauses"]
PUNCT = "，。？！：；、,.?!:;"
def speech_intervals(wav, dur):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af", "silencedetect=n=-40dB:d=0.12", "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]; en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    iv, cur = [], 0.0
    for s, e in zip(st, en):
        if s > cur + 0.02: iv.append((cur, s))
        cur = e
    if len(st) > len(en):
        if st[-1] > cur + 0.02: iv.append((cur, st[-1]))
    elif cur < dur - 0.02: iv.append((cur, dur))
    return iv or [(0.0, dur)]
def weight(ch): return 0.0 if ch in PUNCT or ch.isspace() else (0.5 if ord(ch) < 128 else 1.0)
def clip_texts(sid):
    text = script[sid]["delivery_cues"]["provider_text"]; cuts = [q["after_exact_text"] for q in quiz if q["section_id"] == sid]
    pos, parts = 0, []
    for c in cuts:
        k = text.index(c, pos) + len(c); parts.append(text[pos:k]); pos = k
    return parts + [text[pos:]]
tokens = []
for sec in tl["sections"]:
    texts = clip_texts(sec["id"]); assert len(texts) == len(sec["clips"])
    for clip, text in zip(sec["clips"], texts):
        iv = speech_intervals(P / clip["file"], clip["seconds"]); total = sum(e - s for s, e in iv); W = sum(weight(c) for c in text)
        def to_time(frac):
            acc = frac * total
            for s, e in iv:
                if acc <= e - s + 1e-9: return s + acc
                acc -= e - s
            return iv[-1][1]
        toks, cum = [], 0.0
        for c in text:
            w = weight(c)
            if w == 0 and toks: toks[-1]["word"] += c; continue
            t0 = to_time(cum / W); cum += w; t1 = to_time(cum / W)
            toks.append(dict(word=c, startMs=round((clip["start"] + t0) * 1000), endMs=round((clip["start"] + t1) * 1000)))
        tokens += toks
json.dump(tokens, open(P / "assets/captions/captions.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(tokens), tokens[0], tokens[-1], "monotonic", all(a["startMs"] <= b["startMs"] for a, b in zip(tokens, tokens[1:])))
