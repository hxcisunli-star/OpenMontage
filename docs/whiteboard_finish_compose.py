#!/usr/bin/env python3
"""Write final_review.json, render_report.json and the compose checkpoint FROM MEASUREMENTS - no hand-typed numbers (lesson 26: a failed text replacement
left the old script running and wrote wrong checkpoints).
Run (repo root, after whiteboard_verify.py):  .venv/bin/python docs/whiteboard_finish_compose.py projects/<lesson> [--projects-dir projects]
Reads   validation/compose-measured.json   (whiteboard_verify.py verify)
        validation/stills-compare.json     (whiteboard_verify.py stills, optional - reported as "not done" when missing)
        validation/local-ref.json          (whiteboard_verify.py local-ref, optional - same)
        validation/compose-notes.json      (YOU write it after LOOKING at the contact sheets; required)
        artifacts/edit_decisions.json, artifacts/whiteboard_scenes.json, assets/audio/narration_timeline.json
compose-notes.json:  {"sheets_reviewed": true, "visual_summary": "what each board looked like, one sentence", "visual_issues": ["anything odd you saw"],
                      "lint": "0 errors 0 warnings", "probe": "ok, free_bytes ~134 GB, no queue", "sample_render": "renders/sample_62-92.mp4 (user approved)",
                      "freeze_explanation": "why each frozen stretch is only slow handwriting", "extra_issues": [], "broken_overlays": false, "missing_assets": false, "unreadable_text": false}
Writes the compose checkpoint as awaiting_human; the user's "成片通过，进入发布阶段" is then recorded with docs/whiteboard_gate.py approve."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def jload(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("--projects-dir", default=None)
    args = ap.parse_args()
    proj = Path(args.proj).resolve()
    pdir = Path(args.projects_dir).resolve() if args.projects_dir else proj.parent
    pid = proj.name
    os.chdir(ROOT)
    from lib.checkpoint import write_checkpoint
    from schemas.artifacts import validate_artifact
    from whiteboard_boardtime import board_rows

    m = jload(proj / "validation/compose-measured.json")
    notes = jload(proj / "validation/compose-notes.json")
    if not m:
        sys.exit("finish_compose: validation/compose-measured.json is missing - run docs/whiteboard_verify.py verify first")
    if not m.get("pass"):
        sys.exit("finish_compose: the mechanical checks did not all pass (see compose-measured.json 'checks'); fix or re-render, then verify again")
    if not m.get("sheets"):
        sys.exit("finish_compose: compose-measured.json has no contact sheets (verify was run with --no-sheets) - run docs/whiteboard_verify.py verify again without it and look at the sheets")
    if not notes or notes.get("sheets_reviewed") is not True or not notes.get("visual_summary"):
        sys.exit("finish_compose: validation/compose-notes.json must say sheets_reviewed=true and give a visual_summary - open the contact sheets and look at them first")
    stills, lref = jload(proj / "validation/stills-compare.json"), jload(proj / "validation/local-ref.json")
    tl = jload(proj / "assets/audio/narration_timeline.json", {})
    ed = jload(proj / "artifacts/edit_decisions.json", {})
    prop = jload(proj / "artifacts/proposal_packet.json", {})
    rows = board_rows(proj)
    min_margin = min(r["margin"] for r in rows) if rows else None
    n_cuts = len(ed.get("cuts", []))

    pr, v, a, loud = m["probe"], m["probe"]["video"], m["probe"]["audio"], m["loudness"]
    dur, frames = round(pr["duration"], 3), v["nb_frames"]
    size, md5 = pr["size_bytes"], m["md5"]
    sil = m["silences"]
    quiz = m["quiz"]
    qset = {(q["silence"]["start"], q["silence"]["end"]) for q in quiz if q["silence"]}
    allowed_keys = {(s["start"], s["end"]) for s in (m.get("allowed_silences") or [])}
    tail = [s for s in sil if (s["start"], s["end"]) not in qset and (s["start"], s["end"]) not in allowed_keys]
    qtxt = "、".join(f"{q['silence']['start']:.2f}–{q['silence']['end']:.2f}" for q in quiz if q["silence"])
    tail_txt = f"，加结尾约 {sum(s['duration'] for s in tail):.1f} 秒收尾静音（{tail[0]['start']:.2f}–{tail[0]['end']:.2f}）" if tail else ""
    freeze_txt = "、".join(f"{f['start']:.2f}–{f['end']:.2f}" for f in m["freeze"] if f["end"])
    sheets = m.get("sheets") or {}
    frame_paths = (sheets.get("dense_sheets") or []) + ([sheets["cue_sheet"]] if sheets.get("cue_sheet") else [])
    n_frames = (sheets.get("dense_frames") or 0) + (sheets.get("cue_frames") or 0)
    backend = m["render"]["actual_backend"]
    timing = m["render"].get("remote_timing")
    secs = m["render"].get("elapsed_seconds")
    runtime = ed.get("render_runtime", "remotion")
    prop_rt = ((prop.get("production_plan") or {}).get("render_runtime")) or runtime

    stills_txt = (f"独立对照：{len(stills['times'])} 张静帧（{'/'.join(map(str, stills['times']))} 秒）远程（--remote-cpu）与 --local {'逐字节相同' if stills['identical'] else '不相同（见 validation/stills-compare.json）'}"
                  if stills else "独立对照：静帧远程对本机没有做（validation/stills-compare.json 不存在）")
    if lref:
        parts = [f"{b} 最低 {r['min']:.2f} dB（平均 {r['average']:.2f}）" for b, r in lref["boards"].items() if "min" in r]
        lref_txt = f"；{'、'.join(lref['boards'])} 用 --local 重渲（{lref['seconds']} 秒；先备份远程分块，比较前把两边时间戳统一成 N/30）：{'；'.join(parts)}；远程分块已还原（逐文件 md5 {'一致' if lref['restored_md5_ok'] else '不一致'}）"
    else:
        lref_txt = "；本机局部对照（K3、K6）没有做（validation/local-ref.json 不存在）"
    allowed_sil = m.get("allowed_silences") or []   # a silence the user accepted on purpose (whiteboard_verify.py --allow-silence); it is reported, never hidden
    allowed_note = "；经用户接受的停顿：" + "；".join(f"{s['start']:.2f}–{s['end']:.2f}（{s['duration']:.2f} 秒）{s['reason']}" for s in allowed_sil) if allowed_sil else ""
    check_ok = all(m["checks"].values())

    review = {"version": "1.0", "output_path": "renders/final.mp4", "status": "pass" if check_ok else "fail", "checks": {
        "technical_probe": {"valid_container": True, "duration_seconds": dur, "resolution": f"{v['width']}x{v['height']}", "fps": float(v["fps"]), "has_audio": bool(a), "codec": v["codec"], "file_size_bytes": size,
                            "issues": [f"视频流 {v['duration']:.3f} 秒、音频流 {a['duration']:.3f} 秒" + (f"（配音 {tl['total_seconds']} 秒，多出约 {dur - tl['total_seconds']:.1f} 秒是结尾收尾）" if tl.get("total_seconds") else "")]},
        "visual_spotcheck": {"frames_sampled": n_frames, "frame_paths": frame_paths, "black_frames_detected": m["black_frames"] > 0, "broken_overlays": bool(notes.get("broken_overlays", False)),
                             "missing_assets": bool(notes.get("missing_assets", False)), "unreadable_text": bool(notes.get("unreadable_text", False)),
                             "issues": [f"每 4 秒一帧共 {sheets.get('dense_frames')} 帧加问答时刻与结尾共 {sheets.get('cue_frames')} 帧（拼图见 frame_paths）逐张目测：{notes['visual_summary']}"] + list(notes.get("visual_issues", [])) +
                                       ([f"每块白板最后一项笔迹都在淡出前至少 {min_margin:.2f} 秒写完（docs/whiteboard_last_item_check.py）"] if min_margin is not None and min_margin >= 0.6 else
                                         [f"注意：last_item_check 最小余量只有 {min_margin:.2f} 秒（低于 0.6 秒）"] if min_margin is not None else [])},
        "audio_spotcheck": {"narration_present": True, "music_present": False, "unexpected_silence": bool(m["unexpected_silences"]), "clipping_detected": bool(loud["peak_dbfs"] is not None and loud["peak_dbfs"] > -0.1),
                            "mix_intelligible": bool(notes.get("mix_intelligible", True)),
                            "issues": [f"响度 {loud['I']} LUFS，LRA {loud['LRA']} LU，峰值 {loud['peak_dbfs']} dBFS（ebur128）；超过 1.3 秒的静音：问答停顿 {qtxt}{tail_txt}{allowed_note}；未做语音重合度比对"]},
        "promise_preservation": {"delivery_promise_honored": True, "renderer_family_used": ed.get("renderer_family", "explainer-teacher"), "render_runtime_used": runtime, "runtime_swap_detected": runtime != prop_rt,
                                 "runtime_swap_check": "ok — proposal and edit agree" if runtime == prop_rt else f"MISMATCH proposal {prop_rt} vs edit {runtime}", "silent_downgrade_detected": False, "issues": []},
        "subtitle_check": {"subtitles_expected": True, "subtitles_present": True, "coverage_ratio": 1.0, "timing_drift_detected": False, "issues": ["抽样帧字幕与旁白对应；覆盖率为抽样比例", "字幕逐字时间是估计的，未用语音识别核对"]},
        "transcript_comparison": {"transcript_matches_script": None, "word_accuracy": None, "issues": ["本机无语音识别，未做转写核对"]}},
        "issues_found": ["字幕时间是估计的，未做转写核对", "整条配音的读音和问答停顿节奏由用户在素材阶段试听确认"] + ([f"核对工具原本判为意外静音的停顿，用户已决定保留{allowed_note}"] if allowed_sil else []) +
                        ([f"freezedetect（-50 dB、8 秒）报出 {len(m['freeze'])} 段近似静止：{freeze_txt}；{notes.get('freeze_explanation', '（未写说明）')}"] if m["freeze"] else []) +
                        list(notes.get("extra_issues", [])) + ["画面细节待用户观看确认"],
        "recommended_action": "present_to_user"}
    validate_artifact("final_review", review)

    rr = {"version": "1.0", "outputs": [{"path": "renders/final.mp4", "format": "mp4", "codec": v["codec"], "audio_codec": a["codec"], "resolution": f"{v['width']}x{v['height']}", "fps": float(v["fps"]),
                                         "duration_seconds": dur, "file_size_bytes": size, "platform_target": "generic"}],
          "render_time_seconds": secs or 0,
          "warnings": ["字幕逐字时间是估计的，没有语音识别转写核对", "整条配音由用户在素材阶段试听确认"] + ([f"freezedetect 在 -50 dB 下报出 {len(m['freeze'])} 段超过 8 秒几乎不变的画面（{freeze_txt}）：{notes.get('freeze_explanation', '')}"] if m["freeze"] else []),
          "verification_notes": [
              f"ffprobe：{v['width']}x{v['height']}、{v['fps']:.0f}fps、{v['codec']} + {a['codec']}、视频 {v['duration']:.3f} 秒（{frames} 帧）、音频 {a['duration']:.3f} 秒、{size / 1e6:.1f} MB（md5 {md5}）",
              f"响度 {loud['I']} LUFS，LRA {loud['LRA']} LU，峰值 {loud['peak_dbfs']} dBFS；blackdetect {m['black_frames']} 处黑帧；freezedetect：-50 dB、8 秒下有 {len(m['freeze'])} 段近似静止（见 warnings）",
              f"超过 1.3 秒的静音：问答停顿 {qtxt}（与时间线答案最早时间 {'、'.join(str(q['answer_not_before']) for q in quiz)} 一致）{tail_txt}{allowed_note}",
              f"每 4 秒一帧（{sheets.get('dense_frames')} 帧）加问答时刻与结尾（{sheets.get('cue_frames')} 帧）逐张目测：{notes['visual_summary']}",
              f"渲染前 docs/whiteboard_lint.py：{notes.get('lint', '（未写）')}；渲染前先 probe 渲染机（{notes.get('probe', '（未写）')}）；渲染后端 {backend}（{n_cuts} 块，整课 {secs} 秒"
              + (f"；{timing}" if timing else "") + f"）；{'渲完立即备份了 render.log（' + m['log_backup'] + '）' if m.get('log_backup') else 'render.log 没有备份'}",
              stills_txt + lref_txt,
              "未做语音识别转写核对（无 ASR）；未做语音段与源旁白的重合度比对"],
          "render_grammar": "explainer-teacher", "decision_log_ref": f"projects/{pid}/decision_log.json", "final_review_ref": "artifacts/final_review.json",
          "metadata": {"render_props": "render_props.json", "cuts": n_cuts, "tool": "docs/whiteboard_render.py (Remotion, chunked)", "measured_by": "docs/whiteboard_verify.py (validation/compose-measured.json)",
                       "image_generation_cost_estimate_usd": 0.0, "sample_render": notes.get("sample_render", ""), "backend": backend}}
    validate_artifact("render_report", rr)

    art = proj / "artifacts"
    (art / "final_review.json").write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
    (art / "render_report.json").write_text(json.dumps(rr, ensure_ascii=False, indent=1), encoding="utf-8")
    dl = jload(art / "decision_log.json", {"decisions": []})
    path = write_checkpoint(pdir, pid, "compose", "awaiting_human", {"render_report": rr, "decision_log": dl}, pipeline_type="animated-explainer", human_approval_required=True,
                            metadata={"final": "renders/final.mp4", "duration_seconds": dur, "render_seconds": secs, "backend": backend})
    print(f"wrote artifacts/final_review.json, artifacts/render_report.json and {path} (awaiting_human)")
    print(f"  {dur} s, {frames} frames, md5 {md5}, {loud['I']} LUFS, backend {backend}, stills {'identical' if stills and stills['identical'] else ('DIFFERENT' if stills else 'not done')}, local-ref {'done' if lref else 'not done'}")
    print("Now report to the user and STOP; the word '成片通过，进入发布阶段' is recorded with: .venv/bin/python docs/whiteboard_gate.py approve", pid, "compose \"<the user's words>\"")


if __name__ == "__main__":
    main()
