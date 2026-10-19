#!/usr/bin/env python3
"""Compose-stage verification battery for a whiteboard lesson: measure instead of typing numbers by hand.
Run (repo root, after the lesson is rendered):
  .venv/bin/python docs/whiteboard_verify.py verify  projects/<lesson> [--final renders/final.mp4] [--no-sheets] [--no-backup]
  .venv/bin/python docs/whiteboard_verify.py probe                      remote render channel + free disk (read the output before rendering!)
  .venv/bin/python docs/whiteboard_verify.py compare A.mp4 B.mp4        PSNR with both time bases forced to N/30 (otherwise a few microseconds of drift show up as 29-40 dB)
  .venv/bin/python docs/whiteboard_verify.py stills  projects/<lesson>  6 stills rendered remote and local must be byte-identical (needs the remote channel)
  nohup .venv/bin/python docs/whiteboard_verify.py local-ref projects/<lesson> [--boards K3,K6] > log 2>&1 &   then  python3 docs/whiteboard_wait.py log
`verify` first backs up renders/render.log (later still renders overwrite it), then measures: ffprobe, loudness, silences vs the quiz windows of
assets/audio/narration_timeline.json, black frames, frozen stretches, md5; builds the 4-second contact sheets (renders/review_dense/sheet_N.png, 4x3) and the
quiz/end frame sheet (renders/review_cues/sheet.png, 4x4) that a human MUST still look at; writes validation/compose-measured.json (read by docs/whiteboard_finish_compose.py).
Exit code 1 when a mechanical check fails. It cannot judge whether the pictures are right - open the sheets."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv/bin/python")
TARGET_LUFS, LUFS_TOL, PEAK_MAX = -16.0, 1.0, -1.0


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def md5(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def ffprobe(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,duration,sample_rate,channels",
             "-show_entries", "format=duration,size", "-of", "json", str(path)])
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    num, den = (v["r_frame_rate"].split("/") + ["1"])[:2] if v else ("0", "1")
    fps = float(num) / float(den)
    return {"duration": float(d["format"]["duration"]), "size_bytes": int(d["format"]["size"]),
            "video": v and {"codec": v["codec_name"], "width": v["width"], "height": v["height"], "fps": fps, "nb_frames": int(v.get("nb_frames") or 0), "duration": float(v.get("duration") or 0)},
            "audio": a and {"codec": a["codec_name"], "sample_rate": int(a["sample_rate"]), "channels": a["channels"], "duration": float(a.get("duration") or 0)}}


def audio_pass(path, duration):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true,silencedetect=n=-40dB:d=1.3", "-f", "null", "-"])
    err = r.stderr
    tail = err[err.rfind("Summary:"):] if "Summary:" in err else err
    g = lambda rx: (lambda m: float(m.group(1)) if m else None)(re.search(rx, tail, re.M))  # noqa: E731
    loud = {"I": g(r"^\s+I:\s+(-?[\d.]+) LUFS"), "LRA": g(r"^\s+LRA:\s+([\d.]+) LU"), "peak_dbfs": g(r"^\s+Peak:\s+(-?[\d.]+) dBFS")}
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [(float(a), float(b)) for a, b in re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", err)]
    sil = []
    for i, s in enumerate(starts):
        e = ends[i][0] if i < len(ends) else duration
        sil.append({"start": round(max(s, 0), 2), "end": round(e, 2), "duration": round(e - max(s, 0), 2)})
    return loud, sil


def video_pass(path):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf", "blackdetect=d=0.2:pic_th=0.98,freezedetect=n=-50dB:d=8", "-f", "null", "-"])
    err = r.stderr
    black = len(re.findall(r"black_start:", err))
    fs = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", err)]
    fe = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", err)]
    freeze = []
    for i, s in enumerate(fs):
        e = round(fe[i], 2) if i < len(fe) else None
        if freeze and freeze[-1]["end"] is not None and abs(freeze[-1]["end"] - s) < 0.1:  # one stretch reported in two pieces
            freeze[-1]["end"] = e
        else:
            freeze.append({"start": round(s, 2), "end": e})
    return black, freeze


def font_pair():
    from PIL import ImageFont
    latin = ImageFont.truetype(str(ROOT / "remotion-composer/render-fonts/DejaVuSans.ttf"), 22)
    z = sorted(ROOT.glob("projects/*/references/ZCOOLKuaiLe-Regular.ttf"))
    return latin, (ImageFont.truetype(str(z[0]), 22) if z else latin)


def label(im, text):
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    latin, cjk = font_pair()
    d.rectangle([0, 0, im.width, 30], fill=(255, 255, 255))
    x = 6
    for ch in text:
        f = cjk if ord(ch) > 0x2E7F else latin
        d.text((x, 3), ch, fill=(180, 35, 24), font=f)
        x += d.textlength(ch, font=f)


def sheet(tiles, cols, path):
    from PIL import Image
    w, h = tiles[0].size
    s = Image.new("RGB", (w * cols, h * ((len(tiles) + cols - 1) // cols)), (255, 255, 255))
    for k, im in enumerate(tiles):
        s.paste(im, ((k % cols) * w, (k // cols) * h))
    s.save(path)


def frame_at(path, t, tmp, name):
    from PIL import Image
    out = Path(tmp) / name
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(t, 0):.3f}", "-i", str(path), "-frames:v", "1", "-vf", "scale=480:270", str(out)])
    return Image.open(out).convert("RGB")


def mmss(t):
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def make_sheets(proj, final, duration, quiz):
    from PIL import Image
    dense_dir, cue_dir = proj / "renders/review_dense", proj / "renders/review_cues"
    for d in (dense_dir, cue_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        run(["ffmpeg", "-v", "error", "-i", str(final), "-vf", r"select='not(mod(n\,120))',scale=480:270", "-vsync", "vfr", f"{tmp}/d%04d.png"])
        files = sorted(Path(tmp).glob("d*.png"))
        tiles = []
        for i, f in enumerate(files):
            im = Image.open(f).convert("RGB")
            label(im, f"{i * 4}s  {mmss(i * 4)}")
            tiles.append(im)
        dense = []
        for s in range(0, len(tiles), 12):
            p = dense_dir / f"sheet_{s // 12 + 1}.png"
            sheet(tiles[s:s + 12], 4, p)
            dense.append(str(p.relative_to(proj)))
        marks = []
        for n, q in enumerate(quiz, 1):
            qe, an = q["question_end"], q["answer_not_before"]
            marks += [(qe + 0.65, f"Q{n} +0.65s (silence)"), (qe + 1.65, f"Q{n} +1.65s (silence)"), (qe + 2.65, f"Q{n} +2.65s (silence)"), (an + 0.65, f"Q{n} answer +0.65s")]
        marks += [(duration - 6.5, "end -6.5s"), (duration - 4.5, "end -4.5s"), (duration - 2.5, "end -2.5s"), (duration - 0.6, "end -0.6s")]
        ctiles = []
        for i, (t, text) in enumerate(marks):
            im = frame_at(final, t, tmp, f"c{i}.png")
            label(im, f"{t:.1f}s  {text}")
            ctiles.append(im)
        cue = cue_dir / "sheet.png"
        sheet(ctiles, 4, cue)
    return {"dense_sheets": dense, "dense_frames": len(tiles), "cue_sheet": str(cue.relative_to(proj)), "cue_frames": len(marks)}


def backup_logs(proj):
    rd = proj / "renders"
    names = [n for n in ("render.log", "render.log.remote_full", "render_stdout.log", "render_result.json") if (rd / n).exists()]
    if not names:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = rd / "log_backup" / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(rd / n, dest / n)
    return str(dest.relative_to(proj))


def actual_backend(proj, job_log=None):
    """render_result.json's backend is only what was asked for; the real answer is in the job's stdout (`remote timing:` / `falling back`)."""
    text = ""
    for log in [proj / "renders/render.log", Path(job_log) if job_log else None]:
        if log and log.exists():
            text += log.read_text(encoding="utf-8", errors="replace") + "\n"
    timing = re.findall(r"^remote timing: .*$", text, re.M)
    fallback = re.findall(r"^falling back to local rendering.*$", text, re.M)
    if timing and not fallback:
        return "remote", timing[-1]
    if timing and fallback:
        return "mixed (remote + local fallback)", timing[-1]
    if not job_log:
        return "unknown (pass --render-log <the render job's stdout log> to tell remote from local)", None
    return "local (no `remote timing:` line in the logs)", None


def cmd_verify(args):
    proj = Path(args.proj).resolve()
    final = (proj / args.final) if not Path(args.final).is_absolute() else Path(args.final)
    if not final.exists():
        print(f"verify: FAILED - no {final}")
        return 1
    t0 = time.time()
    backup = None if args.no_backup else backup_logs(proj)
    print("1/5 ffprobe", flush=True)
    pr = ffprobe(final)
    dur = pr["duration"]
    tl_path = proj / "assets/audio/narration_timeline.json"
    tl = json.loads(tl_path.read_text(encoding="utf-8")) if tl_path.exists() else {"quiz": [], "total_seconds": None}
    quiz = tl.get("quiz", [])
    print("2/5 loudness + silences", flush=True)
    loud, sil = audio_pass(final, dur)
    print("3/5 black + frozen frames", flush=True)
    black, freeze = video_pass(final)
    quiz_ok, used = [], set()
    for q in quiz:
        hit = next((i for i, s in enumerate(sil) if i not in used and abs(s["start"] - q["question_end"]) <= 0.7 and abs(s["end"] - q["answer_not_before"]) <= 0.7), None)
        if hit is not None:
            used.add(hit)
        quiz_ok.append({"section_id": q.get("section_id"), "question_end": q["question_end"], "answer_not_before": q["answer_not_before"], "silence": sil[hit] if hit is not None else None})
    total = tl.get("total_seconds")
    tail_ok = lambda s: s["end"] >= dur - 0.3 and (total is None or s["start"] >= total - 1.0)  # noqa: E731
    unexpected = [s for i, s in enumerate(sil) if i not in used and not tail_ok(s)]
    sheets = None
    if not args.no_sheets:
        print("4/5 contact sheets", flush=True)
        sheets = make_sheets(proj, final, dur, quiz)
    print("5/5 md5", flush=True)
    backend, timing = actual_backend(proj, args.render_log)
    rr_path = proj / "renders/render_result.json"
    rr = json.loads(rr_path.read_text(encoding="utf-8")) if rr_path.exists() else {}
    v = pr["video"] or {}
    checks = {
        "has_video_and_audio": bool(pr["video"] and pr["audio"]),
        "h264_1920x1080_30fps": bool(v and v["codec"] == "h264" and v["width"] == 1920 and v["height"] == 1080 and abs(v["fps"] - 30) < 0.01),
        "loudness_near_-16_lufs": loud["I"] is not None and abs(loud["I"] - TARGET_LUFS) <= LUFS_TOL,
        "peak_below_-1_dbfs": loud["peak_dbfs"] is not None and loud["peak_dbfs"] <= PEAK_MAX,
        "every_quiz_has_its_silence": all(q["silence"] for q in quiz_ok),
        "no_unexpected_silence": not unexpected,
        "no_black_frames": black == 0,
        "duration_matches_timeline": total is None or 0 <= dur - total <= 3.0,
        "frame_count_matches_duration": bool(v and v["nb_frames"] and abs(v["nb_frames"] - round(v["fps"] * dur)) <= 2),
    }
    out = {"project": proj.name, "measured_at": datetime.now(timezone.utc).isoformat(), "tool": "docs/whiteboard_verify.py", "final": str(final.relative_to(proj)) if final.is_relative_to(proj) else str(final),
           "md5": md5(final), "probe": pr, "loudness": loud, "silences": sil, "quiz": quiz_ok, "unexpected_silences": unexpected, "black_frames": black, "freeze": freeze,
           "sheets": sheets, "log_backup": backup, "render": {"actual_backend": backend, "remote_timing": timing, "requested_backend": rr.get("backend"), "elapsed_seconds": rr.get("elapsed_seconds")},
           "checks": checks, "pass": all(checks.values()), "human_still_must": ["open renders/review_dense/sheet_*.png and renders/review_cues/sheet.png and look at every frame", "no speech recognition: subtitles timing is an estimate"]}
    outp = proj / "validation/compose-measured.json"
    outp.parent.mkdir(exist_ok=True)
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{proj.name}: {dur:.3f}s {v.get('width')}x{v.get('height')} {v.get('fps'):.0f}fps {v.get('nb_frames')} frames, {pr['size_bytes'] / 1e6:.1f} MB, md5 {out['md5']}")
    print(f"  loudness I {loud['I']} LUFS, LRA {loud['LRA']}, peak {loud['peak_dbfs']} dBFS; black {black}; frozen stretches {len(freeze)} {[(f['start'], f['end']) for f in freeze]}")
    print("  silences >1.3s:", [(s["start"], s["end"]) for s in sil], "| unexpected:", [(s["start"], s["end"]) for s in unexpected])
    print(f"  backend {backend}" + (f" | {timing}" if timing else "") + (f" | logs backed up to {backup}" if backup else ""))
    for k, ok in checks.items():
        print(f"  [{'OK' if ok else 'FAIL'}] {k}")
    print(f"  wrote {outp.relative_to(ROOT) if outp.is_relative_to(ROOT) else outp} in {time.time() - t0:.0f}s; now OPEN the sheets: {sheets and (sheets['dense_sheets'][0] + ' ... ' + sheets['cue_sheet'])}")
    print("verify: done" if out["pass"] else "verify: FAILED (see the [FAIL] lines)")
    return 0 if out["pass"] else 1


def psnr(a, b):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(a), "-i", str(b), "-lavfi", "[0:v]setpts=N/30/TB[a];[1:v]setpts=N/30/TB[b];[a][b]psnr", "-f", "null", "-"])
    m = re.search(r"average:(inf|[\d.]+)\s+min:(inf|[\d.]+)\s+max:(inf|[\d.]+)", r.stderr)
    if not m:
        raise SystemExit("psnr: no summary in ffmpeg output:\n" + r.stderr[-600:])
    f = lambda x: float("inf") if x == "inf" else float(x)  # noqa: E731
    return {"average": f(m.group(1)), "min": f(m.group(2)), "max": f(m.group(3))}


def cmd_compare(args):
    p = psnr(args.a, args.b)
    print(f"PSNR average {p['average']} min {p['min']} max {p['max']}   (both time bases forced to N/30)")
    return 0


def cmd_probe(_args):
    r = run([sys.executable, str(ROOT / "tools/video/remote_cpu_render.py"), "probe"], cwd=ROOT)
    print((r.stdout + r.stderr).strip())
    free = shutil.disk_usage(ROOT).free / 2 ** 30
    print(f"local free disk: {free:.0f} GiB")
    return r.returncode


def cmd_stills(args):
    proj = Path(args.proj).resolve()
    dur = json.loads((proj / "artifacts/edit_decisions.json").read_text(encoding="utf-8"))["cuts"][-1]["out_seconds"]
    times = [round(dur * f) for f in (0.05, 0.2, 0.36, 0.58, 0.72, 0.94)]
    sd = proj / "renders/stills"
    res = {}
    for mode in ("--remote-cpu", "--local"):
        if sd.exists():
            shutil.rmtree(sd)
        r = run([PY, str(ROOT / "docs/whiteboard_render.py"), str(proj), mode, "--stills", *map(str, times)], cwd=ROOT)
        if r.returncode:
            print(f"stills: {mode} failed:\n{(r.stdout + r.stderr)[-500:]}")
            return 1
        res[mode] = {p.name: md5(p) for p in sorted(sd.glob("*.png"))}
    same = res["--remote-cpu"] == res["--local"] and len(res["--local"]) == len(times)
    out = proj / "validation/stills-compare.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"times": times, "identical": same, "files": len(res["--local"]), "total_seconds": dur}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"stills at {times}s: remote vs local {'BYTE-IDENTICAL' if same else 'DIFFERENT'} ({len(res['--local'])} files)")
    return 0 if same else 1


def cmd_local_ref(args):
    proj = Path(args.proj).resolve()
    boards = [b.strip() for b in args.boards.split(",")]
    chunks = proj / "renders/chunks"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bk = proj / "renders" / f"local_ref_backup_{stamp}"
    bk.mkdir(parents=True)
    t0 = time.time()
    saved = {}
    for b in boards:
        for f in sorted(chunks.glob(f"{b}-*.mp4")):
            shutil.copy2(f, bk / f.name)
            saved[f.name] = md5(f)
    final = proj / "renders/final.mp4"
    final_md5 = md5(final) if final.exists() else None
    shutil.copy2(proj / "renders/render.log", bk / "render.log") if (proj / "renders/render.log").exists() else None
    print(f"local-ref: backed up {len(saved)} remote chunk file(s) of {boards} to {bk.relative_to(proj)} (md5 recorded)", flush=True)
    results, ok = {}, True
    try:
        r = subprocess.run([PY, str(ROOT / "docs/whiteboard_render.py"), str(proj), "--final", "--local", "--only", ",".join(boards), "--force", ",".join(boards)], cwd=ROOT)
        if r.returncode:
            ok = False
            print("local-ref failed: local render returned", r.returncode)
        else:
            for b in boards:
                main = next((f for f in sorted(chunks.glob(f"{b}-*.mp4")) if ".p" not in f.stem.split("-", 1)[1]), None)
                old = bk / main.name if main else None
                if main and old and old.exists():
                    results[b] = {"file": main.name, **psnr(old, main)}
                    print(f"local-ref: {b} remote vs local PSNR min {results[b]['min']} average {results[b]['average']}", flush=True)
                else:
                    results[b] = {"error": "no matching chunk file"}
                    ok = False
    finally:
        for name in saved:
            shutil.copy2(bk / name, chunks / name)
    restored = all(md5(chunks / n) == m for n, m in saved.items()) and (final_md5 is None or md5(final) == final_md5)
    print(f"local-ref: remote chunks restored, md5 {'identical' if restored else 'DIFFERENT'}; final.mp4 {'unchanged' if restored else 'CHANGED'}", flush=True)
    out = proj / "validation/local-ref.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"boards": results, "restored_md5_ok": restored, "seconds": round(time.time() - t0), "backup": str(bk.relative_to(proj))}, ensure_ascii=False, indent=1), encoding="utf-8")
    good = ok and restored and all(v.get("min", 0) >= args.min_psnr for v in results.values())
    print(f"local-ref {'done' if good else 'failed'} in {time.time() - t0:.0f}s (threshold min PSNR {args.min_psnr} dB)", flush=True)
    return 0 if good else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify"); v.add_argument("proj"); v.add_argument("--final", default="renders/final.mp4"); v.add_argument("--no-sheets", action="store_true"); v.add_argument("--no-backup", action="store_true")
    v.add_argument("--render-log", help="stdout log of the render job (what nohup wrote); tells the real backend and keeps the `remote timing:` line")
    sub.add_parser("probe")
    c = sub.add_parser("compare"); c.add_argument("a"); c.add_argument("b")
    s = sub.add_parser("stills"); s.add_argument("proj")
    l = sub.add_parser("local-ref"); l.add_argument("proj"); l.add_argument("--boards", default="K3,K6"); l.add_argument("--min-psnr", type=float, default=45.0)
    args = ap.parse_args()
    return {"verify": cmd_verify, "probe": cmd_probe, "compare": cmd_compare, "stills": cmd_stills, "local-ref": cmd_local_ref}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
