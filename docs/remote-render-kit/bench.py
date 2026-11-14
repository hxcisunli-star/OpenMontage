#!/usr/bin/env python3
"""Self-test and benchmark kit for the OpenMontage remote render machine (stdlib only; needs node, ffmpeg+ffprobe with psnr/ssim filters).

What it does: renders the SAME frames the reference machine rendered, under every configuration of a matrix (render processes x tabs x Chrome GL mode
x Chrome mode x NVENC), and for each reports speed, CPU/GPU load, and how close the pictures are to the reference (PSNR/SSIM).  You run it, read the
table, pick the best configuration that passes, publish it as `probe.render_profile`, and report in docs/remote-render-replies/.

  python3 bench.py --node-modules /path/to/runtime/node_modules                 # default matrix, writes results/bench_results.md
  python3 bench.py --node-modules ... --matrix my_matrix.json --stills-only      # only the 6 stills (fast: a few minutes)
  python3 bench.py --node-modules ... --only baseline-w1,gpu-angle-egl-w8         # selected rows

Kit layout (made by docs/make_remote_kit.py on the reference machine):
  input/composer/   the exact source overlay a real job uploads (src, render-tools/render_chunks.mjs, render-fonts, package*.json, tsconfig.json)
  input/props.json, input/public/   the lesson-16 props and staged media
  refs/stills/*.png reference stills from the reference machine; refs/ref_K4_3173-3472.mp4 reference frames 3173..3472 (300 frames)
Acceptance (also in the brief): CPU path (gl null/swangle/swiftshader): stills PSNR >= 50 dB (inf = identical), video min PSNR >= 45 dB.
GPU path (any other gl, or NVENC): stills PSNR >= 45 dB and SSIM >= 0.995, video min PSNR >= 42 dB and average >= 45 dB.
"""
import argparse, json, os, re, shutil, statistics, subprocess, sys, threading, time
from pathlib import Path

KIT = Path(__file__).resolve().parent
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
STILL_TIMES = {"t00060": 6.0, "t01200": 120.0, "t01533": 153.3, "t01580": 158.0, "t02908": 290.8, "t03360": 336.0}
VIDEO_FROM, VIDEO_TO = 3173, 3472  # 300 frames of board K4 (monospace rows, arrows, digits)

DEFAULT_MATRIX = [
    {"name": "baseline-w1", "workers": 1, "tabs": 4, "render": {}},
    {"name": "cpu-w4", "workers": 4, "tabs": 2, "render": {}},
    {"name": "cpu-w8", "workers": 8, "tabs": 2, "render": {}},
    {"name": "cpu-w16", "workers": 16, "tabs": 1, "render": {}},
    {"name": "swangle-w8", "workers": 8, "tabs": 2, "render": {"gl": "swangle"}},
    {"name": "gpu-angle-egl-w8", "workers": 8, "tabs": 2, "render": {"gl": "angle-egl"}},
    {"name": "gpu-egl-w8", "workers": 8, "tabs": 2, "render": {"gl": "egl"}},
    {"name": "gpu-vulkan-w8", "workers": 8, "tabs": 2, "render": {"gl": "vulkan"}},
    {"name": "gpu-angle-w8", "workers": 8, "tabs": 2, "render": {"gl": "angle"}},
    {"name": "gpu-angle-egl-cft-w8", "workers": 8, "tabs": 2, "render": {"gl": "angle-egl", "chromeMode": "chrome-for-testing"}},
    {"name": "gpu-angle-egl-w16", "workers": 16, "tabs": 1, "render": {"gl": "angle-egl"}},
    {"name": "gpu-angle-egl-nvenc-w8", "workers": 8, "tabs": 2, "render": {"gl": "angle-egl", "hardwareAcceleration": "if-possible", "videoBitrate": "8M"}},
]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def have_ffmpeg_filters():
    r = run([FFMPEG, "-hide_banner", "-filters"])
    return " psnr " in r.stdout and " ssim " in r.stdout


class Sampler:
    """Background CPU (vmstat) and GPU (nvidia-smi) sampling while a render runs."""

    def __init__(self):
        self.cpu, self.gpu_util, self.gpu_mem, self.mem_free = [], [], [], []
        self.stop = threading.Event()
        self.threads = [threading.Thread(target=self._cpu, daemon=True)]
        if shutil.which("nvidia-smi"):
            self.threads.append(threading.Thread(target=self._gpu, daemon=True))

    def _cpu(self):
        p = subprocess.Popen(["vmstat", "2"], stdout=subprocess.PIPE, text=True)
        n = 0
        for line in p.stdout:
            parts = line.split()
            if len(parts) >= 15 and parts[0].isdigit():
                n += 1
                if n > 1:  # first line is the average since boot
                    self.cpu.append(100 - int(parts[14])); self.mem_free.append(int(parts[3]) // 1024)
            if self.stop.is_set():
                break
        p.kill()

    def _gpu(self):
        while not self.stop.is_set():
            r = run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"])
            for line in r.stdout.strip().splitlines():
                try:
                    u, m = [int(x) for x in line.split(",")]
                    self.gpu_util.append(u); self.gpu_mem.append(m)
                except ValueError:
                    pass
            self.stop.wait(2)

    def __enter__(self):
        for t in self.threads:
            t.start()
        return self

    def __exit__(self, *a):
        self.stop.set()
        for t in self.threads:
            t.join(timeout=5)

    def summary(self):
        f = lambda xs, fn: f"{fn(xs):.0f}" if xs else "-"
        return {"cpu": f(self.cpu, statistics.mean), "gpu": f(self.gpu_util, statistics.mean), "vram": f(self.gpu_mem, max), "mem_free_min_mb": f(self.mem_free, min)}


def psnr_ssim(a, b, stats):
    r = run([FFMPEG, "-hide_banner", "-nostats", "-i", str(a), "-i", str(b), "-lavfi", f"[0:v][1:v]psnr=stats_file={stats};[0:v][1:v]ssim", "-f", "null", "-"])
    vals = []
    for line in Path(stats).read_text().splitlines():
        m = re.search(r"psnr_avg:(\S+)", line)
        if m:
            vals.append(float(m.group(1)))
    s = re.search(r"SSIM.*All:([0-9.]+)", r.stderr)
    finite = [v for v in vals if v != float("inf")]
    return {"min": (min(vals) if vals else None), "avg": (statistics.mean(finite) if finite else float("inf")), "ssim": float(s.group(1)) if s else None}


def prepare_work(node_modules, work):
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    shutil.copytree(KIT / "input" / "composer", work / "composer")
    (work / "composer" / "node_modules").symlink_to(Path(node_modules).resolve())


def split(a, b, n):
    total = b - a + 1; n = max(1, min(n, total)); size = -(-total // n)
    return [(a + i * size, min(b, a + (i + 1) * size - 1)) for i in range(n) if a + i * size <= b]


def render_job(work, name, spec):
    jp = work / f"{name}.json"; jp.write_text(json.dumps(spec))
    log = work / f"{name}.log"
    t0 = time.time()
    with Sampler() as smp, open(log, "w") as lg:
        rc = subprocess.call(["node", str(work / "composer/render-tools/render_chunks.mjs"), str(jp)], cwd=work / "composer", stdout=lg, stderr=subprocess.STDOUT)
    return rc, time.time() - t0, smp.summary(), log


def base_spec(cfg, out):
    spec = {"propsPath": str(KIT / "input/props.json"), "publicDir": str(KIT / "input/public"), "composition": "Explainer", "concurrency": cfg["tabs"],
            "workers": cfg["workers"], "timeoutMs": 1800000, "chunks": [], "stills": []}
    if cfg["render"]:
        spec["render"] = cfg["render"]
    return spec


def verdict(cfg, still, video):
    gpu = bool(cfg["render"].get("gl") not in (None, "swangle", "swiftshader") or cfg["render"].get("hardwareAcceleration") not in (None, "disabled"))
    ok = True; why = []
    if still:
        if gpu:
            ok &= still["min"] is not None and still["min"] >= 45 and (still["ssim"] or 0) >= 0.995
        else:
            ok &= still["min"] is not None and still["min"] >= 50
        if not ok: why.append("stills")
    if video:
        v_ok = video["min"] is not None and (video["min"] >= (42 if gpu else 45) and (not gpu or video["avg"] >= 45))
        if not v_ok: why.append("video")
        ok &= v_ok
    return ("PASS" if ok else "FAIL " + "+".join(why)) + (" (GPU path)" if gpu else " (CPU path)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node-modules", required=True, help="the runtime's node_modules (same dependencies as input/composer/package-lock.json)")
    ap.add_argument("--matrix"); ap.add_argument("--only"); ap.add_argument("--stills-only", action="store_true")
    ap.add_argument("--out", default=str(KIT / "results"))
    args = ap.parse_args()
    if not have_ffmpeg_filters():
        sys.exit("ffmpeg with psnr+ssim filters is required (set FFMPEG=/path/to/ffmpeg)")
    matrix = json.loads(Path(args.matrix).read_text()) if args.matrix else DEFAULT_MATRIX
    if args.only:
        wanted = set(args.only.split(",")); matrix = [m for m in matrix if m["name"] in wanted]
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    work = KIT / "work"; prepare_work(args.node_modules, work)
    refs = KIT / "refs"
    rows = []
    for cfg in matrix:
        print(f"== {cfg['name']}: {cfg['workers']} processes x {cfg['tabs']} tabs, render={cfg['render']}", flush=True)
        row = {"cfg": cfg, "still": None, "video": None, "notes": []}
        # ---- stills
        sdir = work / f"{cfg['name']}_stills"; shutil.rmtree(sdir, ignore_errors=True)
        spec = base_spec(cfg, sdir)
        spec["stills"] = [{"out": str(sdir / f"{n}.png"), "frame": round(t * 30)} for n, t in STILL_TIMES.items()]
        rc, el, smp, log = render_job(work, f"{cfg['name']}_stills", spec)
        row["still_seconds"] = round(el, 1)
        if rc != 0:
            row["notes"].append(f"stills render failed (see {log.name}: {log.read_text()[-300:]!r})")
        else:
            vals = [psnr_ssim(sdir / f"{n}.png", refs / "stills" / f"{n}.png", work / "ps.log") for n in STILL_TIMES]
            row["still"] = {"min": min(v["min"] for v in vals), "ssim": min(v["ssim"] for v in vals)}
        # ---- video (300 frames of K4)
        if not args.stills_only:
            vdir = work / f"{cfg['name']}_video"; shutil.rmtree(vdir, ignore_errors=True); vdir.mkdir()
            spec = base_spec(cfg, vdir)
            parts = split(VIDEO_FROM, VIDEO_TO, cfg["workers"])
            spec["chunks"] = [{"out": str(vdir / f"p{i}.mp4"), "from": a, "to": b} for i, (a, b) in enumerate(parts)]
            rc, el, smp, log = render_job(work, f"{cfg['name']}_video", spec)
            row.update({"video_seconds": round(el, 1), "fps": round(300 / el, 1), **smp})
            if rc != 0:
                row["notes"].append(f"video render failed (see {log.name}: {log.read_text()[-300:]!r})")
            else:
                lst = vdir / "list.txt"; lst.write_text("".join(f"file '{vdir / f'p{i}.mp4'}'\n" for i in range(len(parts))))
                joined = vdir / "joined.mp4"
                j = run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
                if j.returncode:
                    row["notes"].append("join failed: " + j.stderr[-200:])
                else:
                    row["video"] = psnr_ssim(joined, refs / "ref_K4_3173-3472.mp4", work / "pv.log")
        row["verdict"] = verdict(cfg, row["still"], row["video"])
        rows.append(row)
        print(f"   -> {row['verdict']}  fps={row.get('fps')}  stills_min={row['still'] and round(row['still']['min'], 1)}  video_min={row['video'] and round(row['video']['min'], 1)}", flush=True)
    # ---- report
    lines = ["| config | procs x tabs | render options | video s | fps | CPU% | GPU% | VRAM MB | min free MB | stills PSNR min / SSIM min | video PSNR min / avg / SSIM | verdict |", "|" + "---|" * 12]
    fmt = lambda x, d=1: "-" if x is None else ("inf" if x == float("inf") else f"{x:.{d}f}")
    for r in rows:
        c = r["cfg"]; st = r["still"] or {}; vd = r["video"] or {}
        lines.append(f"| {c['name']} | {c['workers']} x {c['tabs']} | `{json.dumps(c['render'])}` | {r.get('video_seconds', '-')} | {r.get('fps', '-')} | {r.get('cpu', '-')} | {r.get('gpu', '-')} | {r.get('vram', '-')} | "
                     f"{r.get('mem_free_min_mb', '-')} | {fmt(st.get('min'))} / {fmt(st.get('ssim'), 4)} | {fmt(vd.get('min'))} / {fmt(vd.get('avg'))} / {fmt(vd.get('ssim'), 4)} | {r['verdict']}{' ' + '; '.join(r['notes']) if r['notes'] else ''} |")
    (out / "bench_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "bench_results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    print("\n".join(lines)); print(f"\nwritten: {out / 'bench_results.md'}")


if __name__ == "__main__":
    main()
