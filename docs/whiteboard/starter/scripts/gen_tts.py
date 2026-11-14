"""Lesson __N__ narration: one Cherry clip per script section; s2 is cut at its quiz question and s8 into three clips at the two quiz questions,
with 3 s of real silence after each question. Writes narration_timeline.json, narration.wav and narration_norm.wav."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(".env", override=True)
from tools.audio.dashscope_tts import DashscopeTTS
P = ROOT / "projects/__PID__"; AD = P / "assets/audio"
for d in ("narration_raw", "narration"): (AD / d).mkdir(parents=True, exist_ok=True)
script = json.load(open(P / "artifacts/script.json", encoding="utf-8"))
quiz = script["metadata"]["quiz_pauses"]
GAP, LEAD, QSIL = 0.7, 0.3, 3.0
def sh(*a): return subprocess.check_output(list(a)).decode()
def dur(p): return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)))
def silence(path, sec): subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(sec), "-c:a", "pcm_s16le", str(path)])
def tts(name, text):
    raw, wav = AD / "narration_raw" / f"{name}.wav", AD / "narration" / f"{name}.wav"
    assert len(text) <= 600, (name, len(text))
    if not (raw.exists() and raw.stat().st_size > 10000):
        r = DashscopeTTS().execute({"text": text, "voice": "Cherry", "language_type": "Chinese", "output_path": str(raw)})
        if not r.success: print("FAIL", name, (r.error or "")[:300]); sys.exit(2)
        print("OK", name, len(text), "chars", r.cost_usd, flush=True)
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)])
    return wav
# clips: (clip name, section id, text, silence seconds after it)
clips = []
for s in script["sections"]:
    text = s["delivery_cues"]["provider_text"]
    cuts = [q["after_exact_text"] for q in quiz if q["section_id"] == s["id"]]
    if not cuts: clips.append((s["id"], s["id"], text, 0.0)); continue
    pos, parts = 0, []
    for c in cuts:
        k = text.index(c, pos) + len(c); parts.append(text[pos:k]); pos = k
    parts.append(text[pos:])
    assert "".join(parts) == text
    for i, ptxt in enumerate(parts): clips.append((f"{s['id']}_{i + 1}", s["id"], ptxt, QSIL if i < len(parts) - 1 else 0.0))
wavs = {n: tts(n, t) for n, _, t, _ in clips}
sil = AD / "_sil_q.wav"; silence(sil, QSIL); gap = AD / "_gap.wav"; silence(gap, GAP); lead = AD / "_lead.wav"; silence(lead, LEAD)
items, t, secs, order = [lead], LEAD, {}, []
for n, sid, text, after in clips:
    d = dur(wavs[n]); seg = {"clip": n, "chars": len(text), "seconds": round(d, 2), "start": round(t, 2), "end": round(t + d, 2), "silence_after": after,
                             "file": str(wavs[n].relative_to(P)), "text_end": text[-14:]}
    secs.setdefault(sid, {"id": sid, "clips": []})["clips"].append(seg); items.append(wavs[n]); t += d
    if after: items.append(sil); t += after
    else: items.append(gap); t += GAP
items.pop(); t -= GAP  # no gap after the last clip
for sid, v in secs.items():
    v["start"], v["end"] = v["clips"][0]["start"], v["clips"][-1]["end"]; v["chars"] = sum(c["chars"] for c in v["clips"]); v["seconds"] = round(v["end"] - v["start"], 2)
qm = []
for q in quiz:  # question end and the earliest allowed answer time, from the real clips
    c = [c for c in secs[q["section_id"]]["clips"] if c["silence_after"]][sum(1 for m in qm if m["section_id"] == q["section_id"])]
    qm.append({"section_id": q["section_id"], "question_end": c["end"], "answer_not_before": round(c["end"] + QSIL, 2), "answer": q["answer"]})
lst = AD / "_concat.txt"; lst.write_text("".join(f"file '{p}'\n" for p in items))
subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(AD / "narration.wav")])
json.dump({"gap_seconds": GAP, "quiz_silence_seconds": QSIL, "total_seconds": round(dur(AD / "narration.wav"), 2), "sections": list(secs.values()), "quiz": qm},
          open(AD / "narration_timeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(AD / "narration.wav"), "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", "24000", "-ac", "1", str(AD / "narration_norm.wav")])
print("total", round(dur(AD / "narration.wav"), 2), "norm", round(dur(AD / "narration_norm.wav"), 2))
for v in secs.values(): print(v["id"], v["chars"], v["seconds"], "start", v["start"], "end", v["end"])
print(qm)
