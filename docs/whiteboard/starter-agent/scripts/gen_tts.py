"""Lesson __N__ narration: clips from the approved script, two voices (the second voice only when the script has metadata.partner_lines).
The teacher reads in the series voice; the partner's own lines (script.metadata.partner_lines) are read in the partner voice
chosen in assets/audio/voices.json (written when the user has picked one; without the file both voices are the script's `voice`, default Cherry).  A section is cut at (a) the end of every prediction question (3 s of real silence follows) and
(b) both edges of every partner line (a short turn gap, 0.3 s, follows; the section gap 0.7 s follows the last clip of a section).
Every clip carries its text, speaker and voice in narration_timeline.json (make_captions.py and the edit stage read it)."""
import hashlib, json, os, subprocess, sys
from pathlib import Path
from project_paths import ROOT, P
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(".env", override=True)
from tools.audio.dashscope_tts import DashscopeTTS
AD = P / "assets/audio"
for d in ("narration_raw", "narration"): (AD / d).mkdir(parents=True, exist_ok=True)
script = json.load(open(P / "artifacts/script.json", encoding="utf-8"))
_vf = AD / "voices.json"
_v0 = script["metadata"].get("voice", "Cherry")
voices = json.load(open(_vf, encoding="utf-8")) if _vf.exists() else {"teacher": _v0, "partner": _v0}
quiz = script["metadata"]["quiz_pauses"]
partner = script["metadata"].get("partner_lines", {})
GAP, TURN, LEAD, QSIL = 0.7, 0.3, 0.3, 3.0
def sh(*a): return subprocess.check_output(list(a)).decode()
def dur(p): return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)))
def silence(path, sec): subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(sec), "-c:a", "pcm_s16le", str(path)])
costs_f = AD / "tts_costs.json"
costs = json.load(open(costs_f, encoding="utf-8")) if costs_f.exists() else {}
tool = DashscopeTTS()
def tts(name, voice, text):
    assert len(text) <= 600, (name, len(text))
    key = hashlib.sha1(f"{voice}|{text}".encode("utf-8")).hexdigest()[:10]
    raw, wav = AD / "narration_raw" / f"{name}_{key}.wav", AD / "narration" / f"{name}_{key}.wav"
    if not (raw.exists() and raw.stat().st_size > 5000):
        r = tool.execute({"text": text, "voice": voice, "language_type": "Chinese", "output_path": str(raw)})
        if not r.success: print("FAIL", name, voice, (r.error or "")[:300]); sys.exit(2)
        costs[name] = r.cost_usd
        print("OK", name, voice, len(text), "chars", r.cost_usd, flush=True)
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)])
    return wav
# clips: (clip name, section id, speaker, voice, text, kind of silence after: "quiz" | "turn" | "section")
clips = []
for s in script["sections"]:
    sid, text = s["id"], s["delivery_cues"]["provider_text"]
    spans = []
    for line in partner.get(sid, []):
        assert text.count(line) == 1, (sid, line)
        a = text.index(line); spans.append((a, a + len(line)))
    spans.sort()
    assert all(spans[i][1] <= spans[i + 1][0] for i in range(len(spans) - 1)), sid
    qends = []
    for q in quiz:
        if q["section_id"] == sid:
            qends.append(text.index(q["after_exact_text"]) + len(q["after_exact_text"]))
    cuts = sorted({0, len(text), *[x for sp in spans for x in sp], *qends})
    pieces = [(a, b) for a, b in zip(cuts, cuts[1:]) if text[a:b].strip()]
    assert "".join(text[a:b] for a, b in pieces) == text
    for k, (a, b) in enumerate(pieces, 1):
        who = "partner" if any(sa <= a and b <= sb for sa, sb in spans) else "teacher"
        kind = "quiz" if b in qends else ("section" if k == len(pieces) else "turn")
        clips.append((f"{sid}_{k}", sid, who, voices[who], text[a:b], kind))
wavs = {n: tts(n, v, t) for n, _, _, v, t, _ in clips}
json.dump(costs, open(costs_f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
sil = AD / "_sil_q.wav"; silence(sil, QSIL); gap = AD / "_gap.wav"; silence(gap, GAP); turn = AD / "_turn.wav"; silence(turn, TURN); lead = AD / "_lead.wav"; silence(lead, LEAD)
items, t, secs = [lead], LEAD, {}
for n, sid, who, voice, text, kind in clips:
    d = dur(wavs[n])
    after = QSIL if kind == "quiz" else 0.0
    gap_after = {"quiz": 0.0, "turn": TURN, "section": GAP}[kind]
    seg = {"clip": n, "speaker": who, "voice": voice, "text": text, "chars": len(text), "seconds": round(d, 2), "start": round(t, 2), "end": round(t + d, 2),
           "silence_after": after, "gap_after": gap_after, "file": str(wavs[n].relative_to(P)), "text_end": text[-14:]}
    secs.setdefault(sid, {"id": sid, "clips": []})["clips"].append(seg); items.append(wavs[n]); t += d
    if kind == "quiz": items.append(sil); t += QSIL
    elif kind == "turn": items.append(turn); t += TURN
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
json.dump({"gap_seconds": GAP, "turn_gap_seconds": TURN, "quiz_silence_seconds": QSIL, "voices": voices, "total_seconds": round(dur(AD / "narration.wav"), 2),
           "sections": list(secs.values()), "quiz": qm}, open(AD / "narration_timeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(AD / "narration.wav"), "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", "24000", "-ac", "1", str(AD / "narration_norm.wav")])
print("total", round(dur(AD / "narration.wav"), 2), "norm", round(dur(AD / "narration_norm.wav"), 2), "clips", len(clips))
for v in secs.values(): print(v["id"], v["chars"], v["seconds"], "start", v["start"], "end", v["end"], "clips", len(v["clips"]))
print(qm)
