#!/usr/bin/env python3
"""Measured layout check for whiteboard lessons: look at what is REALLY on the board, not at an estimate from character counts.

Run (OpenMontage root):  .venv/bin/python docs/whiteboard_layout_check.py projects/<lesson> [--cuts K1 K4] [--times 85.2 120] [--stills 4] [--json out.json]
  Exit code 1 if any ERROR is found (WARN never fails), 2 if the measurement itself was incomplete (never a silent pass).
  It takes minutes, not milliseconds: run it after the scene plan is built and before the sample render (the millisecond pre-check whiteboard_lint.py still
  runs first inside whiteboard_render.py).  Local only: the probe needs a DOM, which the remote render channel does not give.

How it works: remotion-composer/probe/ wraps the unchanged Explainer, visits the frames of every whiteboard cut WITHOUT taking pictures (Remotion
renderFrames, imageFormat none), waits for the fonts, and prints the real DOM boxes of every text, stroke, panel and image; docs/whiteboard_layout_rules.py
looks at those boxes.  Sample frames = the "state after each burst" times of the contact-sheet tool plus one frame every --grid seconds; nearby samples share
one browser call (a call costs about as much as 8 visited frames), and the work is spread over --workers browser processes.
The probe uses the private fontconfig of render_chunks.mjs, so the boxes belong to the fonts the final frames are drawn with.  Nothing in src/ or in the
lesson folder is touched (staging goes to a temp dir); the chunk-cache fingerprint is unchanged.  --stills writes annotated pictures of the worst findings.
"""
import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "docs"))
import whiteboard_render as wr  # noqa: E402  (chdirs to ROOT; load_props / key_times / total_frames are the render script's own)
import whiteboard_layout_rules as rules  # noqa: E402
from tools.video.video_compose import VideoCompose  # noqa: E402

COMPOSER = ROOT / "remotion-composer"
FPS = 30
STEP = 3           # visit every 3rd frame (0.1 s) inside a range
CLUSTER_GAP = 24   # frames: wanted frames closer than this share one browser call (a call ~ 8 visited frames, measured)
HAND_FONT = COMPOSER / "public" / "fonts" / "ZCOOLKuaiLe-Regular.ttf"
MONO_FONT = COMPOSER / "render-fonts" / "DejaVuSansMono.ttf"
FALLBACK_FONT = COMPOSER / "render-fonts" / "DejaVuSans.ttf"


def whiteboard_cuts(props, only=None):
    return [c for c in props.get("cuts", []) if c.get("whiteboard") and (not only or c.get("id") in only)]


def cut_range(cut, total):
    lo = int(round(float(cut["in_seconds"]) * FPS))
    return lo, min(total - 1, int(round(float(cut["out_seconds"]) * FPS)) - 1)


def snap(frame, lo, hi, step=STEP):
    f = lo + int(round((frame - lo) / step)) * step
    return max(lo, min(f, lo + ((hi - lo) // step) * step))


def plan(props, quiz, only=None, times=None, step=STEP, grid=2.0):
    """-> (cut frame ranges, wanted frames, clusters).  A cluster [lo, hi] is one browser call that visits lo, lo+step, ... (all wanted frames inside it are of
    that form because they were snapped onto the cut's grid and a cluster starts at a wanted frame)."""
    total = wr.total_frames(props)
    ranges, wanted, clusters = [], set(), []
    for cut in whiteboard_cuts(props, only):
        lo, hi = cut_range(cut, total)
        ranges.append((cut.get("id", "?"), lo, hi))
        a, b = float(cut["in_seconds"]), float(cut["out_seconds"])
        ts = list(times) if times else list(wr.key_times(cut, quiz)) + [a + 0.5 + k * grid for k in range(int((b - a) / grid))]
        mine = sorted({snap(int(round(t * FPS)), lo, hi, step) for t in ts if lo <= int(round(t * FPS)) <= hi})
        wanted.update(mine)
        cur = None
        for f in mine:
            if cur and f - cur[1] <= CLUSTER_GAP:
                cur[1] = f
            else:
                cur = [f, f]; clusters.append(cur)
    return ranges, sorted(wanted), clusters


def split_groups(clusters, workers, step=STEP):
    """Greedy balance by estimated cost: 0.6 s per call + 0.07 s per visited frame (measured on a 9-cut lesson)."""
    cost = lambda c: 0.6 + 0.07 * ((c[1] - c[0]) // step + 1)
    groups = [[] for _ in range(max(1, workers))]
    load = [0.0] * len(groups)
    for c in sorted(clusters, key=cost, reverse=True):
        i = load.index(min(load))
        groups[i].append(c); load[i] += cost(c)
    return [g for g in groups if g]


def stage(proj, tmp, wanted, dump=False):
    """Temp public dir + props copy (the media paths of OUR copy are rewritten; the lesson folder is never written)."""
    props, _ = wr.load_props(proj)
    props = copy.deepcopy(props)
    pub = tmp / "public"
    if pub.exists():
        shutil.rmtree(pub)
    pub.mkdir(parents=True)
    for e in (COMPOSER / "public").iterdir():
        (pub / e.name).symlink_to(e, target_is_directory=e.is_dir())
    VideoCompose._stage_remotion_media(props, pub)
    props["probe"] = {"frames": list(wanted), "dump": dump}
    (tmp / "props.json").write_text(json.dumps(props), encoding="utf-8")
    return pub


def run_probe(tmp, pub, groups, step, total, tag="p", concurrency=2):
    """One node process per group, run in parallel; returns the merged probe output (frames, errors, bad lines).  Every range gets ONE extra visited frame at
    its end that nobody asked for: the console line of the LAST frame of a call is lost about one time in five (measured: 17 of 307 sample frames, every one the
    last of its range), so the last wanted frame is never the last visited one."""
    def launch(i, g):
        ranges = [[lo, min(total - 1, hi + step)] for lo, hi in g]
        job = {"propsPath": str(tmp / "props.json"), "publicDir": str(pub), "out": str(tmp / f"layout_{tag}{i}.json"), "ranges": ranges, "step": step, "mode": "range",
               "concurrency": concurrency, "timeoutMs": 900000}
        (tmp / f"job_{tag}{i}.json").write_text(json.dumps(job), encoding="utf-8")
        (tmp / f"layout_{tag}{i}.json").unlink(missing_ok=True)
        log = open(tmp / f"probe_{tag}{i}.log", "w")
        return subprocess.Popen(["node", str(COMPOSER / "probe" / "layout_probe.mjs"), str(tmp / f"job_{tag}{i}.json")], cwd=COMPOSER, stdout=log, stderr=subprocess.STDOUT), log, i

    # The first process builds the bundle (webpack cache); the others start only when it says "bundle ok".  Three processes that rebuild the cache at the same moment after the probe's source
    # changed used to die at start (measured: the first three-process run after every edit of probe/index.tsx failed, the next one passed).
    procs = []
    for i, g in enumerate(groups):
        procs.append(launch(i, g))
        if i == 0 and len(groups) > 1:
            t0 = time.time()
            while time.time() - t0 < 180 and procs[0][0].poll() is None and "bundle ok" not in (tmp / f"probe_{tag}0.log").read_text(errors="replace"):
                time.sleep(0.5)
    merged = {"frames": {}, "errors": [], "bad": [], "meta": {"calls": 0, "visited": 0, "workers": len(groups)}}
    failed = []
    for p, log, i in procs:
        rc = p.wait(); log.close()
        out = tmp / f"layout_{tag}{i}.json"
        if rc != 0 or not out.exists():
            # a probe process now and then dies right after it starts (nothing in its log after the font line; 3 of 7 runs of one check on a loaded 4-core machine): run that group once more
            # on its own before giving up - the check is a quality gate, it must not be flaky
            p2, log2, _ = launch(i, groups[i])
            rc = p2.wait(); log2.close()
        if rc != 0 or not out.exists():
            failed.append((i, f"exit code {rc}\n" + (tmp / f"probe_{tag}{i}.log").read_text(errors="replace")[-1500:]))
            continue
        d = json.loads(out.read_text(encoding="utf-8"))
        merged["frames"].update(d["frames"])
        for k in ("errors", "bad"):
            merged[k] += d.get(k, [])
        merged["meta"]["calls"] += d["meta"]["calls"]; merged["meta"]["visited"] += d["meta"]["visited"]
    if failed:
        raise SystemExit("probe process failed:\n" + "\n".join(f"[{i}] {t}" for i, t in failed))
    return merged


def load_quiz(proj):
    tl = Path(proj) / "assets/audio/narration_timeline.json"
    return json.loads(tl.read_text(encoding="utf-8")).get("quiz", []) if tl.exists() else []


def annotate(png_in, payload, finding, png_out):
    from PIL import Image, ImageDraw
    img = Image.open(png_in).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rectangle(payload["board"], outline=(255, 200, 0), width=2)
    for it in payload["items"]:
        for t in it["texts"]:
            if t["opacity"] >= 0.5:
                for r in t["rects"]:
                    d.rectangle(r, outline=(120, 120, 120), width=1)
    for b in finding.get("boxes", []):
        d.rectangle(b, outline=(255, 0, 0), width=4)
    img.save(png_out)


def render_stills(tmp, frames, outdir):
    jobs = {"propsPath": str(tmp / "props.json"), "publicDir": str(tmp / "public"), "composition": "Explainer", "concurrency": 1, "workers": 1, "timeoutMs": 600000,
            "stills": [{"out": str(outdir / f"raw_{f}.png"), "frame": f} for f in frames]}
    (tmp / "stills_job.json").write_text(json.dumps(jobs), encoding="utf-8")
    r = subprocess.run(["node", str(COMPOSER / "render-tools" / "render_chunks.mjs"), str(tmp / "stills_job.json")], cwd=COMPOSER, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        print("stills failed:", r.stdout[-800:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--cuts", nargs="*", help="only these cut ids")
    ap.add_argument("--times", nargs="*", type=float, help="only these absolute seconds (inside whiteboard cuts)")
    ap.add_argument("--grid", type=float, default=2.0, help="also sample every N seconds (default 2)")
    ap.add_argument("--step", type=int, default=STEP)
    ap.add_argument("--workers", type=int, default=3, help="parallel browser processes (default 3)")
    ap.add_argument("--stills", type=int, default=0, help="write annotated pictures of the N worst findings (ERRORs first)")
    ap.add_argument("--out-dir", help="where --stills go (default <project>/renders/layout)")
    ap.add_argument("--json", help="write findings + raw probe output here")
    ap.add_argument("--keep", help="keep the staging dir here (debugging)")
    ap.add_argument("--dump", action="store_true", help="include a DOM outline in each frame (debugging the probe)")
    ap.add_argument("--no-glyph", action="store_true", help="skip the font-coverage check")
    args = ap.parse_args()

    proj = Path(args.project)
    props, _ = wr.load_props(proj)
    ranges, wanted, clusters = plan(props, load_quiz(proj), set(args.cuts) if args.cuts else None, args.times, args.step, args.grid)
    if not wanted:
        print("no whiteboard frames to measure"); return 0
    groups = split_groups(clusters, args.workers, args.step)
    print(f"layout check: {len(ranges)} whiteboard cuts, {len(wanted)} sample frames in {len(clusters)} browser calls on {len(groups)} processes")
    tmp = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="om-layout-"))
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        t0 = time.time()
        pub = stage(proj, tmp, wanted, args.dump)
        total = wr.total_frames(props)
        data = run_probe(tmp, pub, groups, args.step, total)
        retried = 0
        for attempt in (1, 2):  # whatever is still missing is measured again, one frame per call
            miss = [f for f in wanted if str(f) not in data["frames"] and f not in data["frames"]]
            if not miss:
                break
            retried += len(miss)
            more = run_probe(tmp, pub, split_groups([[f, f] for f in miss], args.workers, args.step), args.step, total, tag=f"r{attempt}_")
            data["frames"].update(more["frames"])
            for k in ("errors", "bad"):
                data[k] += more[k]
        data["missing"] = [f for f in wanted if str(f) not in data["frames"] and f not in data["frames"]]
        secs = time.time() - t0
        cut_of = lambda f: next((cid for cid, lo, hi in ranges if lo <= f <= hi), "?")
        findings = rules.analyze(data["frames"], cut_of)
        if not args.no_glyph:
            findings += rules.glyph_findings(props, HAND_FONT, MONO_FONT, FALLBACK_FONT)
        findings.sort(key=lambda f: (f["t0"], f["rule"]))
        unstable = sorted(int(k) for k, p in data["frames"].items() if p.get("scene") == "whiteboard" and not p.get("stable", True))
        incomplete = bool(data["missing"] or data["bad"] or data["errors"])

        for f in findings:
            print(rules.format_finding(f))
        errs = sum(1 for f in findings if f["severity"] == "ERROR")
        print(f"layout: {errs} error(s), {len(findings) - errs} warning(s); {len(data['frames'])} of {len(wanted)} sample frames measured in {secs:.0f}s"
              + (f" ({retried} had to be measured again)" if retried else ""))
        if unstable:
            print(f"NOTE  {len(unstable)} sample frame(s) never settled (fonts/layout still changing), e.g. frame {unstable[0]}: their boxes may be off")
        if incomplete:
            print("CHECK INCOMPLETE:", json.dumps({k: data[k][:3] for k in ("missing", "bad", "errors") if data[k]}, ensure_ascii=False)[:600])

        if args.stills and findings:
            outdir = Path(args.out_dir) if args.out_dir else proj / "renders" / "layout"
            outdir.mkdir(parents=True, exist_ok=True)
            worst = sorted([f for f in findings if f.get("frame") is not None], key=lambda f: (f["severity"] != "ERROR", f["t0"]))[: args.stills]
            frames = sorted({f["frame"] for f in worst})
            render_stills(tmp, frames, outdir)
            for i, f in enumerate(worst):
                raw = outdir / f"raw_{f['frame']}.png"
                if raw.exists():
                    out = outdir / f"{i + 1:02d}_{f['cut']}_{f['t0']:.1f}s_{f['rule']}.png"
                    annotate(raw, data["frames"][str(f["frame"])], f, out)
                    print("picture:", out)
            for fr in frames:
                (outdir / f"raw_{fr}.png").unlink(missing_ok=True)
        if args.json:
            Path(args.json).write_text(json.dumps({"findings": findings, "meta": {**data["meta"], "seconds": round(secs, 1), "wanted": len(wanted), "got": len(data["frames"]),
                                                    "unstable": len(unstable), "retried": retried, "missing": len(data["missing"])}, "frames": data["frames"]}, ensure_ascii=False), encoding="utf-8")
        return 2 if incomplete else (1 if errs else 0)
    finally:
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
