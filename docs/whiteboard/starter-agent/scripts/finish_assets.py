"""Assets stage, last step: the asset manifest (narration, captions, generated pictures, cast poses) and the assets checkpoint (awaiting_human).
Everything is read from files that exist (timeline, captions, tts costs, approvals, picked images and their generation records); nothing is typed from an older lesson (E74).
Run after: gen_tts.py -> make_captions.py -> the pictures are picked (gen_images.py pick ...)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from project_paths import ROOT, P
sys.path.insert(0, str(ROOT))
from lib.checkpoint import write_checkpoint
from schemas.artifacts import validate_artifact

PID = "__PID__"
SETTINGS = json.loads((P / "scripts/scene_data/assets.json").read_text(encoding="utf-8"))
A = P / "artifacts"
IMG = P / "assets" / "images"
tl = json.loads((P / "assets/audio/narration_timeline.json").read_text(encoding="utf-8"))
script = json.loads((A / "script.json").read_text(encoding="utf-8"))
cap = json.loads((P / "assets/captions/captions.json").read_text(encoding="utf-8"))
sp = json.loads((A / "scene_plan.json").read_text(encoding="utf-8"))
costs = json.loads((P / "assets/audio/tts_costs.json").read_text(encoding="utf-8"))
sample_costs = json.loads((P / "assets/audio/samples/costs.json").read_text(encoding="utf-8"))
captext = "".join(t["word"] for t in cap)
sec_text = "".join(s["delivery_cues"]["provider_text"] for s in script["sections"])
assert captext == sec_text, "captions text != script text"


def loud(f):   # measured, never typed: ffmpeg loudnorm analysis pass
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(f), "-af", "loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(out[out.rindex("{"):])
    return float(j["input_i"]), float(j["input_lra"]), float(j["input_tp"])


(ni, nl, nt), (ri, _rl, _rt) = loud(P / "assets/audio/narration_norm.wav"), loud(P / "assets/audio/narration.wav")

# ---- approvals: the sample voice was approved by the user (read from the record, not typed)
approvals = [json.loads(l) for l in (P / "approvals.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
sample_ok = [a for a in approvals if a.get("stage") == "sample" and a.get("gate") == "样音通过"]
assert sample_ok, "no 样音通过 in approvals.jsonl: the batch voice may only be made after the user approved the sample"
sample_ok = sample_ok[-1]

# ---- scene ids: the first scene of each section, and the scene of every cue
first, cue_scene = {}, {}
for s in sp["scenes"]:
    first.setdefault(s["script_section_id"], s["id"])
for b in sp["metadata"]["boards"]:
    for e in b["events"]:
        cue_scene[e["cue_id"]] = e["scene_id"]

assets = []
for s in tl["sections"]:
    for c in s["clips"]:
        assets.append({"id": "narration-" + c["clip"], "type": "narration", "path": c["file"], "source_tool": "dashscope_tts", "scene_id": first[s["id"]],
                       "model": "qwen3-tts-flash", "provider": "dashscope", "cost_usd": costs[c["clip"]], "duration_seconds": c["seconds"], "format": "wav 24kHz mono",
                       "generation_summary": "DashScope Qwen-TTS，" + script["metadata"].get("voice", "Cherry") + "，language_type=Chinese；按脚本段生成" + ("；在问句后切开，问句后另插 3 秒真实静音" if c["silence_after"] else "") + "。",
                       "voice_performance": {"source_section_id": s["id"], "delivery_cues_applied": True, "provider_text_used": True,
                                             "provider_settings": {"model": "qwen3-tts-flash", "voice": script["metadata"].get("voice", "Cherry"), "language_type": "Chinese"}, "sample_approved": True,
                                             "sample_path": SETTINGS["sample_path"], "review_notes": "DashScope 不支持 SSML；停顿靠标点、段间 0.7 秒和问句后 3 秒静音。"}})

# ---- pictures: the specs (what was asked), the generation records (what was done) and the picks (what was chosen)
specs = {}
for f in [P / "scripts/scene_data/images.json"]:   # the other json files in that folder are amendments, drops and regeneration helpers
    for a in json.loads(f.read_text(encoding="utf-8"))["assets"]:
        specs[a["id"]] = a
picks = {}
pf = IMG / "picked.json"
if pf.exists():
    for p in json.loads(pf.read_text(encoding="utf-8"))["picks"]:
        picks[p["id"]] = p            # a later pick of the same id replaces the earlier one
missing = [i for i in specs if i not in picks]
models = set()
for aid, p in picks.items():
    spec = specs[aid]
    rec = json.loads((IMG / "records" / f"{aid}.json").read_text(encoding="utf-8"))
    runs = rec["runs"]
    model = runs[-1]["model"]
    models.add(model)
    assert (P / p["file"]).is_file(), p["file"]
    scene = cue_scene.get(spec["uses"][0], "reference") if spec.get("uses") else "reference"
    assets.append({"id": "image-" + spec["name"], "type": "image", "subtype": spec["kind"], "path": p["file"], "source_tool": "scripts/gen_images.py", "scene_id": scene,
                   "prompt": spec["prompt"], "model": model, "provider": "gateway (google image model)", "format": "png",
                   "generation_summary": f"{spec['kind']}；候选 {p['candidate']}" + ("，水平翻转" if p.get("flipped") else "") + f"；用于 {'、'.join(spec.get('uses', []))}；记录 assets/images/records/{aid}.json。"})
# existing cast poses and the school logo that the scene plan still uses (read-only copies from the cast library)
used_png = sorted({m for b in sp["metadata"]["boards"] for e in b["events"] for m in re.findall(r"[a-z_]+\.png", e["action"])})
generated_names = {specs[i]["name"] + ".png" for i in picks}
for name in used_png:
    if name in generated_names:
        continue
    assert (IMG / name).is_file(), f"scene plan names {name} but it is neither generated nor in assets/images/"
    assets.append({"id": "image-" + name[:-4], "type": "image", "subtype": "pose", "path": f"assets/images/{name}", "source_tool": "user_provided", "scene_id": "cast",
                   "generation_summary": "既有角色素材库（projects/_cast/agent）的姿势，只读复制；本课不重新生成。"})
assets.append({"id": "image-schoollogo", "type": "image", "path": "assets/images/schoollogo.png", "source_tool": "user_provided", "scene_id": "overlay", "generation_summary": "学校 logo，深蓝底板。"})
tts_cost = round(sum(costs.values()) + sum(sample_costs.values()), 4)
manifest = {"version": "1.0", "assets": assets, "total_cost_usd": tts_cost, "metadata": {
    "music_status": "not_used", "music_reason": SETTINGS["music_reason"],
    "narration_total_seconds": tl["total_seconds"], "timeline": "assets/audio/narration_timeline.json",
    "narration_track": "assets/audio/narration_norm.wav（loudnorm 目标 -16 LUFS，本机实测 %.1f LUFS（LRA %.1f），峰值 %.1f dBFS；归一化之前 %.1f LUFS）" % (ni, nl, nt, ri),
    "quiz": tl["quiz"],
    "measured_pace": "全课约 %.3f 秒/字（含段间停顿与问句静音）；脚本估算总长 %.1f 秒，实测 %.2f 秒" % (tl["total_seconds"] / sum(len(s["delivery_cues"]["provider_text"]) for s in script["sections"]), script["total_duration_seconds"], tl["total_seconds"]),
    "captions": "assets/captions/captions.json：%d 个字符级时间点，文本与脚本逐字一致（已核对）；时间是按真实片段的有声区间估计的，无语音识别核对。" % len(cap),
    "tts_samples": {"count": len(sample_costs), "approved": "用户说“%s”（%s UTC，见 approvals.jsonl）；样音：以 scene_data/assets.json 的 sample_path 为准" % (sample_ok["said"], sample_ok["time"][:19]),
                    "cost_note": "样音费用为工具返回的估算，见 assets/audio/samples/costs.json"},
    "image_generation": {"models": sorted(models), "assets_picked": len(picks), "assets_specified": len(specs), "not_picked": missing, "candidate_images_saved": len(list((IMG / "raw").glob("*.png"))) if (IMG / "raw").is_dir() else 0,
                         "note": SETTINGS["image_generation_note"]},
    "cost_note": "配音费用为工具返回的估算（见 assets/audio/tts_costs.json），不是账单，真实以云服务账单为准；生图费用没有核算（total_cost_usd 只含配音）。",
    "pending_verification": SETTINGS["pending_verification"]}}
validate_artifact("asset_manifest", manifest)
json.dump(manifest, open(A / "asset_manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("total", tts_cost, "assets", len(assets), "pictures picked", len(picks), "not picked", missing)
if os.environ.get("ASSETS_REFRESH_ONLY"):   # a change the user asked for AFTER the gate was passed (lesson 3: a new partner voice): refresh the manifest, leave the approved checkpoint as it is, say so in the report
    print("manifest refreshed; checkpoint_assets.json untouched (ASSETS_REFRESH_ONLY)")
else:
    print(write_checkpoint(P.parent, PID, "assets", "awaiting_human", {"asset_manifest": manifest}, pipeline_type="animated-explainer", human_approval_required=True))
