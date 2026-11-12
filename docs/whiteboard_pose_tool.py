#!/usr/bin/env python3
"""Character poses and picture cards for the whiteboard lessons: generated on the render machine's Qwen image service, characters then cut out of their solid-colour background.

  pose  <series> <name> --ref REF.png --prompt-file P.txt [--negative-file N.txt] [--seed N] [--bg green|magenta]
          a new pose of a character the series already has: Qwen image edit from the reference picture (the character on a solid background), download, cut out, save as
          <cast_dir>/<name>.png (cast_dir from docs/whiteboard/series.yaml) with the raw picture and the generation record beside it in <cast_dir>/raw/ and <cast_dir>/records/
  scene <out.png> --prompt-file P.txt [--negative-file N.txt] [--aspect 16:9|1:1|9:16] [--seed N]
          a text-to-image picture for a picture card (no cut-out: it goes on the board as a card with rounded corners)
  key   <in.png> <out.png> [--bg green|magenta]
          cut a character out of a solid background by COLOUR DOMINANCE (not a fixed colour: the generator's green drifts and may add a ground shadow): soft edge, spill removed, only the
          main figure kept, trimmed.  Use magenta when the character itself has green in it.

The request id is written to the record BEFORE the job is submitted (the service wants it persisted so a retry of the same submission does not make a second job).  The service takes one job
at a time: a second submit queues behind the first.  Times in the record are the service's own states (queued -> running -> completed), polled every 5 s.  The CLI is the one installed on this
machine for the render machine (path in OPENMONTAGE_QWEN_CLI, default /opt/h3-api/qwen); its credentials are its own, nothing is read from .env here.
Measured 2026-10 (pilot): a pose from a reference ran 56-62 s once started, a text-to-image picture 45 s; every picture came out right the first time (3 tries per picture at most, a failed
one is kept as <name>_v1.png)."""
import argparse
import json
import os
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
NEG_KEYED = "渐变背景，阴影，地面，文字，水印，多人，裁切，绿色的衣服，绿色的物体，绿色的反光"
NEG_CARD = "文字，字母，数字，符号，水印，人物，渐变背景，复杂背景"


def qwen_cli():
    return os.environ.get("OPENMONTAGE_QWEN_CLI", "/opt/h3-api/qwen")


def run_job(request_id, args, out, record_path, cli=None, poll=5.0):
    """Submit one Qwen job, wait for it, download the result to `out`, write the record.  Returns the record."""
    cli = cli or qwen_cli()
    out, record_path = Path(out), Path(record_path)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"api": "qwen", "request_id": request_id, "args": [str(a) for a in args], "t_submit": time.time(), "states": []}
    record_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")   # persisted before the submit
    for attempt in range(3):   # the service says: after "Request/download incomplete" keep the SAME request id and inputs (the job may already exist); never a new id
        r = subprocess.run([cli, "submit", "--request-id", request_id, *map(str, args)], capture_output=True, text=True)
        if r.returncode == 0 or "same request ID" not in (r.stdout + r.stderr):
            break
        time.sleep(poll * 2)
    try:
        job = json.loads(r.stdout)
        jid = job["id"]
    except Exception:
        rec["error"] = (r.stdout + r.stderr)[-600:]
        record_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        raise SystemExit("submit failed: " + rec["error"])
    rec["job_id"] = jid
    last = None
    while True:
        g = subprocess.run([cli, "get", "--job", jid], capture_output=True, text=True)
        try:
            j = json.loads(g.stdout)
        except Exception:
            time.sleep(poll)
            continue
        st = j.get("status")
        if st != last:
            rec["states"].append({"t": round(time.time() - rec["t_submit"], 1), "status": st, "stage": j.get("stage") or j.get("phase")})
            last = st
        if st in ("completed", "failed", "canceled", "needs_attention"):
            rec["final"] = {k: j.get(k) for k in ("status", "error", "files") if k in j}
            break
        time.sleep(poll)
    rec["wall_seconds"] = round(time.time() - rec["t_submit"], 1)
    if st == "completed":
        out.parent.mkdir(parents=True, exist_ok=True)
        d = subprocess.run([cli, "download", "--job", jid, "--output", str(out)], capture_output=True, text=True)
        rec["download"] = (d.stdout + d.stderr)[-300:]
    record_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    if st != "completed" or not out.exists():
        raise SystemExit(f"job {jid} ended as {st}: {rec.get('final')}")
    return rec


def key_image(src, dst, bg="green"):
    """Cut a character out of a solid green / magenta background by colour dominance.  Returns a small report dict."""
    import numpy as np
    from PIL import Image, ImageFilter
    a = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    dom = (g - np.maximum(r, b)) if bg == "green" else (np.minimum(r, b) - g)   # how much of the background colour a pixel has
    alpha = 1.0 - np.clip((dom - 25.0) / (110.0 - 25.0), 0, 1)                   # opaque below 25, transparent above 110, soft in between
    spill = np.clip(dom / 110.0, 0, 1) * 1.4
    spill = np.clip(spill, 0, 1)
    if bg == "green":
        g = np.where(dom > 0, g - dom * spill, g)
    else:
        r = np.where(dom > 0, r - (r - g) * spill, r)
        b = np.where(dom > 0, b - (b - g) * spill, b)
    rgb = np.dstack([r, g, b]).clip(0, 255).astype(np.uint8)
    H, W = alpha.shape
    s = 4                                                                          # main figure only: label the opaque mask on a 1/4 scale, keep blobs >= 2 % of the biggest
    small = alpha[::s, ::s] > 0.5
    lab = np.zeros(small.shape, np.int32)
    sizes, n = {}, 0
    for y in range(small.shape[0]):
        for x in np.nonzero(small[y] & (lab[y] == 0))[0]:
            if lab[y, x]:
                continue
            n += 1
            q = deque([(y, x)])
            lab[y, x] = n
            c = 0
            while q:
                cy, cx = q.popleft()
                c += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < small.shape[0] and 0 <= nx < small.shape[1] and small[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = n
                        q.append((ny, nx))
            sizes[n] = c
    if not sizes:
        raise SystemExit("key: nothing but background found (wrong --bg?)")
    keep = [k for k, v in sizes.items() if v >= 0.02 * max(sizes.values())]
    m = Image.fromarray((np.isin(lab, keep) * 255).astype(np.uint8)).resize((W, H), Image.NEAREST).filter(ImageFilter.MaxFilter(13))
    alpha = alpha * (np.asarray(m, dtype=np.float32) / 255.0)
    out = np.dstack([rgb, (alpha * 255).astype(np.uint8)])
    ys, xs = np.nonzero(out[..., 3] > 8)
    pad = 8
    box = (int(max(xs.min() - pad, 0)), int(max(ys.min() - pad, 0)), int(min(xs.max() + pad, W)), int(min(ys.max() + pad, H)))
    Image.fromarray(out, "RGBA").crop(box).save(dst)
    return {"blobs_kept": len(keep), "blobs": len(sizes), "box": box, "partly_transparent_px": int(((alpha > 0.02) & (alpha < 0.98)).sum())}


def _cast_dir(series):
    from whiteboard_lessons import series_config
    cd = series_config(series)["cast_dir"]
    if not cd:
        sys.exit(f"series {series!r} has no cast_dir in docs/whiteboard/series.yaml")
    return ROOT / cd


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pose")
    p.add_argument("series"); p.add_argument("name"); p.add_argument("--ref", required=True); p.add_argument("--prompt-file", required=True)
    p.add_argument("--negative-file"); p.add_argument("--seed", type=int, default=1); p.add_argument("--bg", default="green", choices=["green", "magenta"])
    p.add_argument("--resolution", default="1536"); p.add_argument("--steps", default="40")
    p = sub.add_parser("scene")
    p.add_argument("out"); p.add_argument("--prompt-file", required=True); p.add_argument("--negative-file"); p.add_argument("--aspect", default="16:9", choices=["1:1", "16:9", "9:16"])
    p.add_argument("--seed", type=int, default=1); p.add_argument("--resolution", default="1536"); p.add_argument("--steps", default="40")
    p = sub.add_parser("key")
    p.add_argument("src"); p.add_argument("dst"); p.add_argument("--bg", default="green", choices=["green", "magenta"])
    a = ap.parse_args(argv)
    if a.cmd == "key":
        print(key_image(a.src, a.dst, a.bg))
        return 0
    neg = a.negative_file
    if a.cmd == "pose":
        cast = _cast_dir(a.series)
        raw = cast / "raw" / f"{a.name}.png"
        neg = neg or _tmp_negative(NEG_KEYED)
        args = ["--mode", "image_edit", "--image", a.ref, "--prompt-file", a.prompt_file, "--negative-file", neg, "--resolution", a.resolution, "--steps", a.steps, "--seed", a.seed]
        rec = run_job(f"pose-{a.series}-{a.name}-{int(time.time())}", args, raw, cast / "records" / f"{a.name}.json")
        print(key_image(raw, cast / f"{a.name}.png", a.bg), f"| {rec['wall_seconds']} s from submit to done")
        return 0
    out = Path(a.out)
    neg = neg or _tmp_negative(NEG_CARD)
    args = ["--mode", "text_to_image", "--aspect-ratio", a.aspect, "--prompt-file", a.prompt_file, "--negative-file", neg, "--resolution", a.resolution, "--steps", a.steps, "--seed", a.seed]
    rec = run_job(f"scene-{out.stem}-{int(time.time())}", args, out, out.with_suffix(".json"))
    print(f"{out} | {rec['wall_seconds']} s from submit to done")
    return 0


def _tmp_negative(text):
    import tempfile
    f = Path(tempfile.mkdtemp()) / "negative.txt"
    f.write_text(text, encoding="utf-8")
    return str(f)


if __name__ == "__main__":
    sys.exit(main())
