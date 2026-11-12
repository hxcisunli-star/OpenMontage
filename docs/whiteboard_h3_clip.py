#!/usr/bin/env python3
"""H3 video clips for the whiteboard lessons (EXPERIMENTAL presentation device "H3片段（实验）"): made on the render machine's H3 service, then fitted to the lesson's video format.

  clip <out.mp4> --image FIRST.png --prompt-file P.txt [--seconds 4] [--seed N] [--mode h3_i2v|h3_ref2va] [--reference R.png ...] [--audio A.wav] [--resolution h3_landscape|h3_portrait]
          submit a first-frame (or reference) video job, wait, download the MP4 (raw: 1344x768, 24 fps, with an audio track), write the record <out.mp4>.json (request id first, states, wall time)
  fit   <in.mp4> <out.mp4> (--frames N | --seconds S)
          make it a lesson CUT: 1920x1080, 30 fps, no audio, exactly N frames (a short clip holds its last frame, a long one is cut), in the format of the render chunks (H.264 High level 4.0,
          yuvj420p, full range, bt470bg) so it joins them with `ffmpeg -c copy` (docs/whiteboard_render.py `video_clip` cut) and the cover prepend (docs/whiteboard_prepend_cover.py --sting)

Why not the picture-sequence cut: the render machine cannot PLAY a video file, but the finished lesson is assembled from per-cut mp4 files (and the cover is prepended) by ffmpeg AFTER rendering, so a clip can
be one of those files: no 10 MB JPEG sequence, no upload to the render machine, no second encode of the board.
Measured (2026-10, one clip): 4 s request = 107 frames / 4.458 s, 196.8 s from submit to done, a 603 KB MP4; style (flat 2D, outlines, colours, characters) held; slightly soft, pupils blurred in motion.
The service has no alpha channel: a clip is a whole-screen insert.  CLI path: OPENMONTAGE_H3_CLI (default /opt/h3-api/h3); credentials are its own."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whiteboard_pose_tool import run_job  # noqa: E402  (request id first, polling, record)

FPS = 30


def h3_cli():
    return os.environ.get("OPENMONTAGE_H3_CLI", "/opt/h3-api/h3")


def clip_args(a):
    args = ["--mode", a.mode, "--image", a.image, "--prompt-file", a.prompt_file, "--resolution", a.resolution, "--seconds", a.seconds, "--seed", a.seed]
    for r in a.reference or []:
        args += ["--reference", r]
    if a.audio:
        args += ["--audio", a.audio]
    return args


def fit(src, dst, frames):
    """`src` -> a 1920x1080, 30 fps, audio-free mp4 of exactly `frames` frames in the render chunks' format."""
    vf = (f"fps={FPS},scale=1920:1080:flags=lanczos:in_range=tv:out_range=pc,setsar=1,format=yuvj420p,"
          f"tpad=stop_mode=clone:stop_duration={frames / FPS + 2:.3f}")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-an", "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-profile:v", "high",
                        "-level", "4.0", "-color_range", "pc", "-colorspace", "bt470bg", "-video_track_timescale", "90000", "-movflags", "+faststart", str(dst)], capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg failed: " + r.stderr[-300:])
    n = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(dst)], capture_output=True, text=True).stdout
    if int(n.strip() or 0) != frames:
        sys.exit(f"fit: wanted {frames} frames, got {n.strip()}")
    return int(n)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("clip")
    p.add_argument("out"); p.add_argument("--image", required=True); p.add_argument("--prompt-file", required=True); p.add_argument("--seconds", default="4"); p.add_argument("--seed", default="1")
    p.add_argument("--mode", default="h3_i2v", choices=["h3_i2v", "h3_ref2va"]); p.add_argument("--resolution", default="h3_landscape", choices=["h3_landscape", "h3_portrait"])
    p.add_argument("--reference", action="append"); p.add_argument("--audio"); p.add_argument("--request-id")
    p = sub.add_parser("fit")
    p.add_argument("src"); p.add_argument("dst"); g = p.add_mutually_exclusive_group(required=True); g.add_argument("--frames", type=int); g.add_argument("--seconds", type=float)
    a = ap.parse_args(argv)
    if a.cmd == "fit":
        n = fit(a.src, a.dst, a.frames if a.frames is not None else round(a.seconds * FPS))
        print(f"{a.dst}: {n} frames, 1920x1080, {FPS} fps")
        return 0
    import time
    out = Path(a.out)
    rec = run_job(a.request_id or f"h3-{out.stem}-{int(time.time())}", clip_args(a), out, out.with_suffix(out.suffix + ".json"), cli=h3_cli())
    print(f"{out} | {rec['wall_seconds']} s from submit to done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
