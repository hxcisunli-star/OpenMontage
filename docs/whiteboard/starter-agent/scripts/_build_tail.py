
# ----------------------------------------------------------------- outputs
import hashlib
sp = json.loads((ART / "scene_plan.json").read_text(encoding="utf-8"))
covers = {}
for i, sid in enumerate(SIDS):
    ids = [s["id"] for s in sp["scenes"] if s["script_section_id"] == sid]
    covers[f"K{i+1}"] = (",".join(ids), sp["metadata"]["boards"][i]["title"])
PARTIAL = len(cuts) < len(K)          # a workshop build of one or two boards: the files are written for these cuts only and the build says so
if not PARTIAL:
    assert list(cuts) == list(K), (list(cuts), list(K))
cut_rows, wb_data = [], {}
for cid, b in cuts.items():
    wb_data[cid] = b.data()
    cut_rows.append({"id": cid, "source": f"whiteboard:{cid}", "in_seconds": round(b.cin, 4), "out_seconds": round(b.cout, 4), "layer": "primary", "transition_in": "fade", "transition_out": "fade",
                     "transition_duration": 0.4, "reason": f"场景 {covers[cid][0]}：{covers[cid][1]}"})
LOGO_PATH = IMG / "schoollogo.png"
_lw, _lh = Image.open(LOGO_PATH).size
LOGO_H, LOGO_PAD, LOGO_X, LOGO_Y = 44, 11, 40, 38
LOGO_W = round(LOGO_H * _lw / _lh); LOGO_END = B[-1]
_dev = ART.parent / "scripts" / "edit_deviations.json"
deviations = json.loads(_dev.read_text(encoding="utf-8")) if _dev.exists() else []
edit_decisions = {
    "version": "1.0", "cuts": cut_rows,
    "overlays": [{"asset_id": "logo-school", "start_seconds": 0, "end_seconds": LOGO_END,
                  "position": {"x": LOGO_X, "y": LOGO_Y, "width": LOGO_W + 2 * LOGO_PAD, "height": LOGO_H + 2 * LOGO_PAD}, "opacity": 1}],
    "audio": {"narration": {"segments": [{"asset_id": "narration-full", "start_seconds": 0, "end_seconds": round(TOTAL, 2)}]}},
    "subtitles": {"enabled": True, "style": "sentence", "source": "assets/captions/captions.json", "font": "ZCOOL KuaiLe", "font_size": 44, "color": "#1F2937",
                  "background": "#FFFFFFD9", "position": "bottom-center", "max_words_per_line": 16},
    "renderer_family": "explainer-teacher", "render_runtime": "remotion", "composition_mode": "templated",
    "metadata": {"music": "none", "whiteboard_data": "artifacts/whiteboard_scenes.json", "render_props": "render_props.json", "partial_build": PARTIAL,
                 "scene_map": {sid: cid for cid, (cover, _) in covers.items() for sid in cover.split(",")},
                 "timing": "时间来自 assets/audio/narration_timeline.json 的真实旁白时长；白板动作用场景计划的 anchor_phrase 在估计字幕中定位（字幕时间是估计值，误差约零点几秒）。",
                 "deviations_from_scene_plan": deviations}}
props = {"cuts": [{"id": r["id"], "source": r["source"], "in_seconds": r["in_seconds"], "out_seconds": r["out_seconds"], "type": "whiteboard", "whiteboard": wb_data[r["id"]]} for r in cut_rows],
         "overlays": [{"type": "logo", "src": str(LOGO_PATH), "in_seconds": 0, "out_seconds": LOGO_END, "x": LOGO_X, "y": LOGO_Y, "height": LOGO_H, "pad": LOGO_PAD, "background": "#14244A"}],
         "captions": caps, "audio": {"narration": {"src": str(AUD / "narration_norm.wav"), "volume": 1.0}}, "playbook": "clean-professional",
         "renderer_family": "explainer-teacher", "render_runtime": "remotion", "composition_mode": "templated", "captionWordsPerPage": 16, "captionFontSize": 44,
         "captionFontFamily": "WBHand, 'Noto Sans SC', sans-serif", "captionWordSeparator": ""}
(ART / "whiteboard_scenes.json").write_text(json.dumps(wb_data, ensure_ascii=False, indent=1), encoding="utf-8")
(ART / "edit_decisions.json").write_text(json.dumps(edit_decisions, ensure_ascii=False, indent=2), encoding="utf-8")
(PROJ / "render_props.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
print("cuts:" + (" (PARTIAL build)" if PARTIAL else ""))
for r in cut_rows: print(f"  {r['id']:4s} {r['in_seconds']:8.3f} -> {r['out_seconds']:8.3f} ({r['out_seconds']-r['in_seconds']:6.2f}s)")
print("items per cut:", {k: len(v['items']) for k, v in wb_data.items()}); print("total video seconds:", B[-1])

# pre-render lint (docs/whiteboard_lint.py): errors here mean a known board mistake; fix before rendering
import subprocess as _sp
_lint = _sp.call([sys.executable, str(ROOT / "docs/whiteboard_lint.py"), str(PROJ)])
print("lint exit code:", _lint)

if _lint:
    raise SystemExit(_lint)
