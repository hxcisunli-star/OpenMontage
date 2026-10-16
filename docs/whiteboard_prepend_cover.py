"""Prepend a ~2 s cover to a finished lesson video WITHOUT re-rendering.

Usage (from the OpenMontage root):
    .venv/bin/python docs/whiteboard_prepend_cover.py projects/<lesson> [--seconds 2] [--out-dir DIR]

Source of truth stays untouched: renders/final.mp4, assets/subtitles.srt.
Writes (default into <lesson>/exports/):
    video/output.mp4        cover (still + silence) + final.mp4, stream copy, cover also attached as picture
    video/subtitles.srt     original SRT shifted by the cover length
    metadata/chapters.txt + metadata.json chapters shifted (first chapter stays 0:00)
Idempotent: always rebuilt from renders/final.mp4, assets/subtitles.srt and metadata "chapters_original".
Needs exports/thumbnails/cover.png and cover_1280x720.jpg (docs/whiteboard_cover_maker.py).
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("FAILED: " + " ".join(map(str, cmd)) + "\n" + r.stderr[-800:])
    return r.stdout


def dur(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]))


def shift_srt(text, s):
    def f(m):
        h, mi, se, ms = map(int, m.groups())
        t = round((h * 3600 + mi * 60 + se + s) * 1000 + ms)
        return f"{t // 3600000:02d}:{t // 60000 % 60:02d}:{t // 1000 % 60:02d},{t % 1000:03d}"
    return re.sub(r"(\d\d):(\d\d):(\d\d),(\d\d\d)", f, text)


def fmt(sec):
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}" if sec < 3600 else f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--seconds", type=float, default=2.0)
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()
    P = Path(a.project)
    s = a.seconds
    out = Path(a.out_dir) if a.out_dir else P / "exports"
    final, cover_png, cover_jpg = P / "renders/final.mp4", P / "exports/thumbnails/cover.png", P / "exports/thumbnails/cover_1280x720.jpg"
    for f in (final, cover_png, cover_jpg):
        if not f.exists():
            sys.exit(f"missing {f}")
    (out / "video").mkdir(parents=True, exist_ok=True)
    (out / "metadata").mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="cover_"))

    # 1. intro clip: same codec parameters as the Remotion final (h264 High, yuvj420p, 30 fps, aac 48 kHz stereo)
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", str(s), "-i", str(cover_png),
         "-f", "lavfi", "-t", str(s), "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", "format=yuvj420p,setrange=pc", "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuvj420p",
         "-r", "30", "-video_track_timescale", "90000", "-c:a", "aac", "-b:a", "128k", "-shortest", str(tmp / "intro.mp4")])
    run(["ffmpeg", "-v", "error", "-y", "-i", str(final), "-c", "copy", str(tmp / "main.mp4")])
    (tmp / "list.txt").write_text("file 'intro.mp4'\nfile 'main.mp4'\n")

    # 2. concat (stream copy) + attach the cover picture
    target = out / "video/output.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-i", str(cover_jpg),
         "-map", "0:v", "-map", "0:a", "-map", "1", "-c", "copy", "-disposition:v:1", "attached_pic",
         "-movflags", "+faststart", str(target)])

    # 3. subtitles and chapters
    srt = P / "assets/subtitles.srt"
    (out / "video/subtitles.srt").write_text(shift_srt(srt.read_text(encoding="utf-8"), s), encoding="utf-8")
    mp = P / "exports/metadata/metadata.json"
    meta = json.loads(mp.read_text(encoding="utf-8"))
    orig = meta.get("chapters_original") or meta["chapters"]
    meta["chapters_original"] = orig
    meta["chapters"] = [dict(c, start_seconds=(0 if i == 0 else c["start_seconds"] + s)) for i, c in enumerate(orig)]
    meta["cover_seconds"] = s
    (out / "metadata/metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "metadata/chapters.txt").write_text(
        "\n".join(f"{fmt(c['start_seconds'])} - {c['title']}" for c in meta["chapters"]) + "\n", encoding="utf-8")

    # 4. verification: duration, decode, content frame identical, cover frame close to cover.png
    d0, d1 = dur(final), dur(target)
    run(["ffmpeg", "-v", "error", "-i", str(target), "-f", "null", "-"])
    from PIL import Image
    import numpy as np
    def frame(path, t, name):
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(path), "-frames:v", "1", str(tmp / name)])
        return np.asarray(Image.open(tmp / name).convert("RGB"), float)
    same = abs(frame(target, s + 0.5, "a.png") - frame(final, 0.5, "b.png")).mean()
    cov = abs(frame(target, s / 2, "c.png") - np.asarray(Image.open(cover_png).convert("RGB"), float)).mean()
    print(f"duration {d0:.3f} -> {d1:.3f} (+{d1 - d0:.3f}); content-frame diff {same:.3f} (expect 0); cover-frame diff {cov:.2f}")
    if same > 0.5 or abs(d1 - d0 - s) > 0.1:
        sys.exit("VERIFY FAILED")
    print("ok ->", target)


if __name__ == "__main__":
    main()
