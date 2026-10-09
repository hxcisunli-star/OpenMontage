"""Chunked, cached, multi-process render for whiteboard lessons.  Change one board, re-render only that board; use every core.

Run (OpenMontage root, project dir first):
  .venv/bin/python docs/whiteboard_render.py projects/<lesson> --plan              # which chunks are stale + which backend would be used
  .venv/bin/python docs/whiteboard_render.py projects/<lesson> --final             # lint, render stale chunks, concat, mux narration -> renders/final.mp4
  .venv/bin/python docs/whiteboard_render.py projects/<lesson> --final --out renders/x.mp4 --force K4
  .venv/bin/python docs/whiteboard_render.py projects/<lesson> --stills 152.5 158 ... # single frames (one bundle per process) -> renders/stills/tNNNNN.png
  .venv/bin/python docs/whiteboard_render.py projects/<lesson> --contact [K4 K5]     # key-moment frames per board + contact sheets -> renders/contact/
  .venv/bin/python docs/whiteboard_render.py projects/<lesson> --sample 85 115       # seconds 85..115 with the matching narration -> renders/sample_85-115.mp4

Where it renders (automatic; same command either way, same output files)
- default `auto`: if the remote CPU render channel answers AND advertises everything needed for pixel-identical output
  (src_overlay + fontconfig_self_managed, see docs/remote-render-agent-brief-v2.zh-CN.md), render there and bring the parts back;
  otherwise render on this machine (the reason is printed once).  `--local` forces this machine.  `--remote-cpu` forces the remote
  channel (error if unusable); add `--allow-drift` only for experiments (pictures may differ from local).
- A chunk that fails remotely is re-rendered locally automatically (unless --remote-cpu), already finished chunks are kept.

How it works
- Each whiteboard cut is a self-contained frame range (Explainer renders cuts as non-overlapping <Sequence>s; captions/logo depend only on the
  absolute frame).  A chunk = [cut start frame, next cut start frame - 1], rendered muted (H.264, same defaults as the CLI full render).
- ONE Remotion process cannot use more than ~2 cores (serial bottleneck; measured: 4 tabs in one process used 53% of 4 cores), so every chunk is
  split into parts that render in parallel in separate processes (each with its own Chrome), then joined with `ffmpeg -c copy`.
- Fingerprint of a chunk = that cut's JSON + hashes of the media files it uses + the caption pages and overlays that touch its time range
  + global props (theme, caption style) + hash of remotion-composer/src, package-lock.json, render-tools, public/fonts and render-fonts.
  Same fingerprint -> cached file renders/chunks/<id>-<fp>.mp4 is reused.
- Fonts are deterministic: render_chunks.mjs runs Chrome with the private fontconfig in remotion-composer/render-fonts (DejaVu only).
- The narration (props.audio.narration.src) is muxed once at the end (stereo 48 kHz AAC 320k, padded to the video length).  Concat is `-c copy`; frame count is verified.
- whiteboard_lint.py runs first; errors stop the render (use --no-lint to skip).
"""
import argparse, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "docs")); os.chdir(ROOT)
from tools.video.video_compose import VideoCompose  # noqa: E402
import whiteboard_lint  # noqa: E402

COMPOSER = ROOT / "remotion-composer"
FPS = 30
CORES = os.cpu_count() or 4
TOOL_VERSION = "chunks-v3"  # bump when the way chunks are rendered/stitched changes
MIN_PART = 120              # do not split a chunk into parts shorter than this many frames
REMOTE_MIN_PART = 30        # remote default (the machine has far more workers than a small job has frames): measured on a 900-frame sample, parts >=120 frames 74 s, >=60 57 s, >=30 54 s end to end (PSNR between them >=48.6 dB)
STILLS_LOCAL_MAX = 60       # auto mode: up to this many stills are faster here than through the channel (6 stills: 7 s local, 36 s remote; 137 stills: about equal)
JOB_MIN_FRAMES = 2400       # remote: do not open another job for less than this many frames (each job costs ~3 SSH round trips + a bundle)
TABS = 2                    # browser tabs per render process (more does not help: the process, not the tab count, is the limit)
REMOTE_NEEDS = ("src_overlay", "fontconfig_self_managed")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def jhash(obj):
    return sha(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def hashed_files():
    """Everything that decides what a frame looks like.  render_chunks.mjs is deliberately NOT here: tuning how we render
    (workers, GL mode, ...) must not throw away chunks that are visually equivalent; fonts and sources are."""
    files = sorted(p for p in (COMPOSER / "src").rglob("*") if p.is_file())
    files += [COMPOSER / "package-lock.json", COMPOSER / "package.json", COMPOSER / "tsconfig.json"]
    files += sorted(p for p in (COMPOSER / "public" / "fonts").rglob("*") if p.is_file())
    files += sorted(p for p in (COMPOSER / "render-fonts").rglob("*") if p.is_file())
    return [p for p in files if p.exists()]


def composer_files():
    """Everything uploaded to a remote job as the composer overlay (hashed files + the render script)."""
    return hashed_files() + [COMPOSER / "render-tools" / "render_chunks.mjs"]


def composer_hash():
    h = hashlib.sha256()
    for p in hashed_files():
        h.update(str(p.relative_to(COMPOSER)).encode()); h.update(p.read_bytes())
    return h.hexdigest()


def load_props(proj):
    """render_props.json -> (props for Remotion without audio, narration path or None). Mirrors VideoCompose._remotion_render."""
    props = json.loads((proj / "render_props.json").read_text(encoding="utf-8"))
    vc = VideoCompose()
    if "themeConfig" not in props:
        name = props.get("playbook") or props.get("theme") or props.get("metadata", {}).get("playbook")
        theme = vc._build_theme_from_playbook(name, props)
        if theme:
            props["themeConfig"] = theme
    narr = ((props.get("audio") or {}).get("narration") or {}).get("src")
    props["audio"] = {}
    return props, narr


def stage(proj, props, name):
    pub = proj / "renders" / name
    if pub.exists():
        shutil.rmtree(pub)
    pub.mkdir(parents=True)
    for e in (COMPOSER / "public").iterdir():
        (pub / e.name).symlink_to(e, target_is_directory=e.is_dir())
    VideoCompose._stage_remotion_media(props, pub)
    return pub


def total_frames(props):
    return math.ceil((max(c.get("out_seconds", 0) for c in props["cuts"]) + 1) * FPS)  # Root.tsx calculateMetadata


def caption_pages(props):
    words = props.get("captions") or []
    per = int(props.get("captionWordsPerPage") or 6)
    pages, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= per or w.get("pageBreakAfter"):
            pages.append(cur); cur = []
    if cur:
        pages.append(cur)
    return pages


def media_hashes(node, pub, cache, out):
    if isinstance(node, dict):
        for v in node.values():
            media_hashes(v, pub, cache, out)
    elif isinstance(node, list):
        for v in node:
            media_hashes(v, pub, cache, out)
    elif isinstance(node, str):
        f = pub / node
        if node and not f.is_symlink() and f.is_file():
            if node not in cache:
                cache[node] = sha(f.read_bytes())
            out[node] = cache[node]


def make_chunks(props, pub, comp_hash):
    cuts = sorted(props["cuts"], key=lambda c: c["in_seconds"])
    total = total_frames(props)
    pages = caption_pages(props)
    glob = {k: v for k, v in props.items() if k not in ("cuts", "captions", "overlays", "audio")}
    cache, chunks = {}, []
    for i, cut in enumerate(cuts):
        a = 0 if i == 0 else round(cut["in_seconds"] * FPS)
        b = (round(cuts[i + 1]["in_seconds"] * FPS) - 1) if i + 1 < len(cuts) else total - 1
        t0, t1 = a / FPS - 1.0, (b + 1) / FPS + 1.0
        pg = [p for p in pages if p[0]["startMs"] / 1000 < t1 and p[-1]["endMs"] / 1000 > t0]
        ov = [o for o in props.get("overlays", []) if o.get("in_seconds", 0) < t1 and o.get("out_seconds", 1e9) > t0]
        media = {}
        media_hashes([cut, ov], pub, cache, media)
        fp = jhash({"tool": TOOL_VERSION, "composer": comp_hash, "global": glob, "cut": cut, "range": [a, b], "total": total,
                    "pages": pg, "overlays": ov, "media": media})[:12]
        chunks.append({"id": cut["id"], "from": a, "to": b, "fp": fp})
    return chunks, total


def ffprobe_frames(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return int(r.stdout.strip().strip(",") or 0)


def ffprobe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())


def stream_sig(path):
    """Everything that must match for `ffmpeg -c copy` concatenation to be valid."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=codec_name,profile,level,pix_fmt,color_range,color_space,width,height,r_frame_rate", "-of", "json", str(path)],
                       capture_output=True, text=True)
    try:
        return json.dumps(json.loads(r.stdout)["streams"][0], sort_keys=True)
    except (ValueError, KeyError, IndexError):
        return "unknown"


def reencode_join(lst, out):
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                           "-pix_fmt", "yuv420p", "-an", str(out)])


def fmt_t(sec):
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


# ------------------------------------------------------------------------------------------------ progress ---
class Progress:
    """Turns the render processes' output into the same kind of progress for local and remote runs."""

    def __init__(self, log_path, expected):
        self.expected = dict(expected)          # part file name -> frames
        self.rendered = {}
        self.t0 = time.time(); self.last_print = 0.0; self.last_pct = -1; self.fonts_shown = False
        self.log = open(log_path, "w", encoding="utf-8")

    def total(self):
        return sum(self.expected.values())

    def feed(self, line):
        line = line.rstrip()
        if not line:
            return
        self.log.write(line + "\n"); self.log.flush()
        if line.startswith("@@progress"):
            _, name, r, t = line.split()
            self.rendered[name] = int(r); self.expected.setdefault(name, int(t))
        elif line.startswith("@@done"):
            name = line.split(None, 1)[1]
            if name in self.expected:
                self.rendered[name] = self.expected[name]
        elif line.startswith("still "):
            print(line, flush=True)
        elif "fonts:" in line:
            if not self.fonts_shown:
                self.fonts_shown = True; print(re.sub(r"^\[w\d+\] ", "", line)[:200], flush=True)
        elif line.startswith("workers:") or re.search(r"error|Error|failed|FAILED|timed out|Timeout", line):
            print(line[:300], flush=True)
        self.tick()

    def tick(self, force=False):
        total = self.total()
        if not total:
            return
        done = sum(min(self.rendered.get(n, 0), t) for n, t in self.expected.items())
        pct = int(100 * done / total)
        now = time.time()
        if (force or now - self.last_print >= 5) and (pct != self.last_pct or force):
            el = now - self.t0
            eta = f", about {fmt_t(el * (total - done) / done)} left" if done > 50 and not force else ""
            print(f"  progress {pct}% ({done}/{total} frames), elapsed {fmt_t(el)}{eta}", flush=True)
            self.last_print, self.last_pct = now, pct

    def close(self):
        self.tick(force=True); self.log.close()


# -------------------------------------------------------------------------------------------------- backends ---
def local_backend(reason):
    workers = max(1, CORES // 2)
    return {"kind": "local", "workers": workers, "total_workers": workers, "max_jobs": 1, "render": {}, "tabs": TABS, "note": reason, "label": f"local ({CORES} cores: {workers} processes x {TABS} tabs)"}


def make_client(args):
    from tools.video.remote_cpu_render import RemoteRenderClient
    return RemoteRenderClient(identity=args.remote_identity, known_hosts=args.remote_known_hosts, port=args.remote_port)


def parse_profile(args, probe=None):
    """Render profile: --render-profile '<json>' wins over what the remote agent publishes in probe.render_profile."""
    if args.render_profile:
        try:
            prof = json.loads(args.render_profile)
        except ValueError as exc:
            raise SystemExit(f"--render-profile is not valid JSON: {exc}")
    else:
        prof = dict((probe or {}).get("render_profile") or {})
    allowed = {"gl", "chromeMode", "hardwareAcceleration", "videoBitrate", "x264Preset", "jpegQuality", "restartEvery"}
    return {k: v for k, v in prof.items() if k in allowed}


def choose_backend(args, quiet=False):
    """Decide where to render.  Never raises for `auto`: any doubt means local."""
    if args.local:
        return local_backend("forced by --local")
    try:
        client = make_client(args)
        probe = client.probe()
    except Exception as exc:  # noqa: BLE001 - any failure of the optional channel means "render locally"
        if args.remote_cpu:
            raise SystemExit(f"remote render channel unavailable: {str(exc)[:300]}")
        return local_backend(f"remote channel not available ({str(exc)[:120]}); rendering locally")
    feats = set(probe.get("features") or [])
    problems = []
    missing = [f for f in REMOTE_NEEDS if f not in feats]
    if missing:
        problems.append(f"remote agent lacks {missing} (needed for pixel-identical output; see docs/remote-render-agent-brief-v2.zh-CN.md)")
    lock = probe.get("runtime_lock_sha256")
    local_lock = sha((COMPOSER / "package-lock.json").read_bytes())
    if lock and lock != local_lock:
        problems.append("remote node_modules differ from local package-lock.json")
    busy = len(probe.get("running") or []) + int(probe.get("queued") or 0)
    maxq = int((probe.get("limits") or {}).get("max_queue", 16))
    if busy >= maxq:
        problems.append(f"remote queue is full ({busy})")
    if problems and not (args.remote_cpu and args.allow_drift):
        if args.remote_cpu:
            raise SystemExit("remote rendering refused: " + "; ".join(problems) + "  (--allow-drift to try anyway; output may differ from local)")
        return local_backend("; ".join(problems) + "; rendering locally")
    cap = probe.get("capacity") or {}
    prof = parse_profile(args, probe)
    max_jobs = max(1, int(cap.get("max_concurrent_jobs") or probe.get("max_concurrent") or 1))
    total = int(args.workers or cap.get("max_total_workers") or probe.get("recommended_workers") or max(1, int(probe.get("max_concurrency", 16)) // 2))
    tabs = int(args.concurrency or prof.get("tabs") or TABS)
    note = "WARNING: allow-drift, pictures may differ from local; " + "; ".join(problems) if problems else "pixel-identical path"
    return {"kind": "remote", "workers": total, "total_workers": total, "max_jobs": max_jobs, "tabs": tabs, "client": client, "probe": probe,
            "features": feats, "render": {k: v for k, v in prof.items() if k != "tabs"}, "note": note,
            "label": f"remote (up to {total} processes x {tabs} tabs in {max_jobs} job(s); {probe.get('agent', 'agent')}, runtime {args.remote_runtime}"
                     + (f", profile {json.dumps({k: v for k, v in prof.items() if k != 'tabs'})}" if prof else "") + ")"}


def set_min_part(args, backend):
    """Shortest allowed part: --min-part wins; otherwise 120 frames locally, REMOTE_MIN_PART on the remote machine."""
    globals()["MIN_PART"] = args.min_part or (REMOTE_MIN_PART if backend["kind"] == "remote" else 120)


def plan_workers(backend, n_groups):
    """Processes per job: the machine's total split over the jobs it can run at the same time."""
    if backend["kind"] == "remote":
        backend["workers"] = max(1, backend["total_workers"] // max(1, min(backend["max_jobs"], n_groups)))
    return backend["workers"]


def announce(backend):
    print(f"render backend: {backend['label']}" + (f"  [{backend['note']}]" if backend["kind"] == "local" and backend["note"] else ""), flush=True)
    if backend["kind"] == "remote" and not backend["note"].startswith("pixel"):
        print("  " + backend["note"], flush=True)


# ---------------------------------------------------------------------------------------------------- parts ---
def split_parts(chunk, workers, part_dir):
    a, b = chunk["from"], chunk["to"]
    total = b - a + 1
    k = max(1, min(workers, total // MIN_PART))
    base, extra = divmod(total, k)  # sizes differ by at most one frame: no tiny last part (a 1-frame part encodes noticeably worse)
    parts, fa = [], a
    for i in range(k):
        fb = fa + base + (1 if i < extra else 0) - 1
        parts.append({"id": chunk["id"], "from": fa, "to": fb, "name": f"{chunk['id']}-{chunk['fp']}.p{i}.mp4", "path": part_dir / f"{chunk['id']}-{chunk['fp']}.p{i}.mp4"})
        fa = fb + 1
    return parts


def part_counts(frames, budget):
    """Parts per chunk so that their total is EXACTLY min(budget, what MIN_PART allows) -- one part per worker.  A plain round() per chunk
    gave 30 parts for a budget of 32 and 65 for 64; the surplus part made one worker render two parts and the lesson ended with a lone straggler.
    Largest-remainder rounding: floor of each chunk's share first, then the leftover parts go to the chunks with the biggest remainders."""
    T = sum(frames.values())
    cap = {c: max(1, n // MIN_PART) for c, n in frames.items()}
    want = max(1, min(budget, T // MIN_PART, sum(cap.values())))
    quota = {c: want * n / T for c, n in frames.items()}
    ks = {c: max(1, min(cap[c], int(quota[c]))) for c in frames}
    while sum(ks.values()) < want:
        c = max((c for c in frames if ks[c] < cap[c]), key=lambda c: quota[c] - ks[c])
        ks[c] += 1
    while sum(ks.values()) > want:
        c = min((c for c in frames if ks[c] > 1), key=lambda c: quota[c] - ks[c])
        ks[c] -= 1
    return ks


def remote_groups(todo, backend, part_dir):
    """Remote work plan: cut ALL stale chunks into about `total_workers` parts of similar length, then deal the parts to as many jobs as
    are worth it (LPT: biggest part to the emptiest job), so every job carries about the same number of frames and no long board is left
    rendering alone at the end.  Returns (groups by id, parts by chunk id)."""
    total_w, max_jobs = backend["total_workers"], backend["max_jobs"]
    frames = {c["id"]: c["to"] - c["from"] + 1 for c in todo}
    T = sum(frames.values())
    ks = part_counts(frames, total_w)
    parts, by_chunk = [], {}
    for c in todo:
        by_chunk[c["id"]] = split_parts(c, ks[c["id"]], part_dir)
        parts += by_chunk[c["id"]]
    n_jobs = max(1, min(max_jobs, len(parts), math.ceil(T / JOB_MIN_FRAMES)))
    bins = [[] for _ in range(n_jobs)]
    for p in sorted(parts, key=lambda p: p["to"] - p["from"], reverse=True):
        min(bins, key=lambda b: sum(q["to"] - q["from"] for q in b)).append(p)
    groups = {}
    for i, ps in enumerate(b for b in bins if b):
        gid = f"j{i + 1}"
        ps.sort(key=lambda p: p["from"])
        groups[gid] = {"id": gid, "parts": ps, "local_parts": ps, "local_stills": [], "stills": [],
                       "workers": min(len(ps), math.ceil(total_w / n_jobs)),
                       "chunks": [{"out": p["name"], "from": p["from"], "to": p["to"]} for p in ps],
                       "outputs": [(p["name"], p["path"]) for p in ps], "expected": {p["name"]: p["to"] - p["from"] + 1 for p in ps}}
    return groups, by_chunk


def merge_parts(parts, out):
    """Join parts of one chunk (in frame order) into the final chunk file; verify the frame count."""
    out.parent.mkdir(parents=True, exist_ok=True)
    want = sum(p["to"] - p["from"] + 1 for p in parts)
    if len(parts) == 1:
        shutil.move(str(parts[0]["path"]), str(out))
    else:
        lst = out.with_suffix(".parts.txt")
        lst.write_text("".join(f"file '{p['path']}'\n" for p in parts), encoding="utf-8")
        tmp = out.with_suffix(".joining.mp4")
        if len({stream_sig(p["path"]) for p in parts}) > 1:
            print(f"  {out.name}: parts have different stream parameters, joining with a re-encode", flush=True)
            reencode_join(lst, tmp)
        else:
            subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(tmp)])
        tmp.replace(out); lst.unlink()
        for p in parts:
            p["path"].unlink(missing_ok=True)
    n = ffprobe_frames(out)
    if n != want:
        out.unlink(missing_ok=True)
        raise SystemExit(f"{out.name}: {n} frames after joining parts, expected {want}")


# ----------------------------------------------------------------------------------------------- local run ---
def run_local(proj, backend, pp, pub, parts, stills, timeout_ms=7200000):
    expected = {p["name"]: p["to"] - p["from"] + 1 for p in parts}
    jobs = {"propsPath": str(pp), "publicDir": str(pub), "composition": "Explainer", "concurrency": backend["tabs"], "workers": backend["workers"],
            "timeoutMs": timeout_ms, "chunks": [{"out": str(p["path"]), "from": p["from"], "to": p["to"]} for p in parts],
            "stills": [{"out": s["out"], "frame": s["frame"]} for s in stills]}
    if backend.get("render"):
        jobs["render"] = backend["render"]
    jp = proj / "renders" / ".local_jobs.json"; jp.write_text(json.dumps(jobs), encoding="utf-8")
    prog = Progress(proj / "renders" / "render.log", expected)
    proc = subprocess.Popen(["node", str(COMPOSER / "render-tools" / "render_chunks.mjs"), str(jp)], cwd=COMPOSER,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for line in proc.stdout:
            prog.feed(line)
        rc = proc.wait()
    except BaseException:
        proc.terminate(); proc.wait(); raise
    finally:
        prog.close()
    if rc != 0:
        raise SystemExit(f"node render failed (see {proj / 'renders' / 'render.log'})")


# ---------------------------------------------------------------------------------------------- remote run ---
def build_remote_input(dest, props_path, pub, spec):
    """input/ for one remote job: props, public (dereferenced), composer overlay (src + render-tools + fonts + lock), jobs.json."""
    dest.mkdir(parents=True)
    shutil.copy2(props_path, dest / "props.json")
    shutil.copytree(pub, dest / "public", symlinks=False)
    for p in composer_files():
        rel = p.relative_to(COMPOSER)
        if rel.parts[0] == "public":
            continue
        target = dest / "composer" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    (dest / "jobs.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")


def run_remote(proj, args, backend, pp, pub, groups, install, cleanup_dir):
    """groups: [{"id", "chunks":[{"out","from","to"}], "stills":[{"out","frame"}], "outputs":[(name, dest Path)], "expected":{name:frames}, "workers"?}].
    One remote job per group.  Jobs are queued in parallel, polled in parallel, and each finished job is downloaded in the background while the
    others keep rendering, then handed to install(group).  Returns the ids of groups that failed (caller falls back to local)."""
    from concurrent.futures import ThreadPoolExecutor, wait
    from tools.video.remote_cpu_render import RemoteRenderError
    client, feats = backend["client"], backend["features"]
    runtime = args.remote_runtime
    expected = {n: f for g in groups for n, f in g["expected"].items()}
    prog = Progress(proj / "renders" / "render.log", expected)
    jobs, failed = [], set()
    stamp = int(time.time() * 1000)
    t0 = time.time()
    tm = {}  # phase timings, printed at the end so we see where the time goes
    pool = ThreadPoolExecutor(max_workers=max(4, 2 * len(groups)))

    def since():
        return time.time() - t0

    bg = []  # best-effort cleanups running in the background: they must never hold up the render

    def tidy(job, cancel):
        t1 = time.time()
        for fn in ((client.cancel, client.cleanup) if cancel else (client.cleanup,)):
            try:
                fn(job["id"])
            except Exception:  # noqa: BLE001 - best effort
                pass
        if time.time() - t1 > 10:
            print(f"remote: cleanup of {job['id']} took {time.time() - t1:.0f}s", flush=True)

    def drop(job, background=True):
        if background:
            bg.append(pool.submit(tidy, job, True))
        else:
            tidy(job, True)

    def queue(g):
        job = {"id": f"om-{sha(proj.name.encode())[:10]}-{g['id']}-{stamp}".lower(), "group": g, "shown": 0, "offset": 0, "state": None}
        spec = {"propsPath": "props.json", "publicDir": "public", "composition": "Explainer", "concurrency": backend["tabs"],
                "workers": g.get("workers") or backend["workers"], "timeoutMs": 7200000, "chunks": g["chunks"], "stills": g["stills"], "render": backend.get("render") or {},
                "composer_hash": composer_hash(), "lock_sha256": sha((COMPOSER / "package-lock.json").read_bytes())}
        try:
            with tempfile.TemporaryDirectory(prefix=".remote-in-", dir=cleanup_dir) as tmp:
                build_remote_input(Path(tmp) / "input", pp, pub, spec)
                client.prepare(job["id"]); client.upload(job["id"], Path(tmp) / "input"); client.submit(job["id"], runtime)
            return job, None
        except RemoteRenderError as exc:
            return job, exc

    def poll(job):
        st = client.status(job["id"])
        state, text, offset, shown = st.get("state"), "", job["offset"], job["shown"]
        if state in ("running", "completed", "failed"):  # stream the log of jobs that are (or were) running
            if "log_offset" in feats:
                r = client.logs(job["id"], job["offset"]); text, offset = r.get("log", ""), r.get("next", job["offset"])
            else:
                full = client.logs(job["id"]).get("log", ""); text, shown = full[job["shown"]:], len(full)
        return st, state, text, offset, shown

    def fetch(job):
        out = Path(tempfile.mkdtemp(prefix=".remote-out-", dir=cleanup_dir))
        try:
            client.download(job["id"], out)
            for name, dest in job["group"]["outputs"]:
                src = out / name
                if not src.is_file():
                    raise RemoteRenderError(f"remote output missing: {name}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        finally:
            shutil.rmtree(out, ignore_errors=True)

    try:
        for fut in [pool.submit(queue, g) for g in groups]:
            job, exc = fut.result()
            if exc is None:
                jobs.append(job)
                print(f"remote: queued {job['group']['id']} ({job['id']})", flush=True)
            else:
                print(f"remote: could not queue {job['group']['id']}: {str(exc)[:200]}", flush=True)
                drop(job); failed.add(job["group"]["id"])
        tm["queued"] = since()
        deadline = time.time() + args.remote_timeout
        while jobs:
            round_start = time.time()
            polls = {j["id"]: pool.submit(poll, j) for j in jobs if "fetch" not in j}  # all jobs asked at the same time
            for job in list(jobs):
                g = job["group"]
                if "fetch" in job:
                    if not job["fetch"].done():
                        continue
                    try:
                        job["fetch"].result()
                        g["rendered_by"] = "remote"
                        install(g)
                        tm["installed"] = since()
                        bg.append(pool.submit(tidy, job, False))
                    except (RemoteRenderError, SystemExit) as exc:  # bad/missing download or a part that fails verification
                        print(f"remote: {g['id']} result rejected: {str(exc)[:200]}", flush=True)
                        failed.add(g["id"]); drop(job)
                    jobs.remove(job)
                    continue
                try:
                    st, state, text, job["offset"], job["shown"] = polls[job["id"]].result()
                    job["errors"] = 0
                    for line in text.splitlines():
                        prog.feed(line)
                    if state != job["state"]:
                        job["state"] = state
                        if state not in ("queued", None):
                            print(f"remote: {g['id']} {state}", flush=True)
                        if state == "running":
                            tm.setdefault("first_running", since())
                    if state == "completed":
                        tm["last_done"] = since()
                        job["fetch"] = pool.submit(fetch, job)  # download in the background; the other jobs keep being polled
                    elif state in ("failed", "canceled"):
                        print(f"remote: {g['id']} {state}: {str(st.get('error'))[:300]}", flush=True)
                        failed.add(g["id"]); drop(job); jobs.remove(job)
                except RemoteRenderError as exc:  # the client already retried; give up on this job after 3 rounds of that
                    job["errors"] = job.get("errors", 0) + 1
                    if job["errors"] >= 3:
                        print(f"remote: channel problem for {g['id']} ({str(exc)[:160]}); it will render locally", flush=True)
                        failed.add(g["id"]); drop(job); jobs.remove(job)
            if jobs:
                if time.time() > deadline:
                    for j in list(jobs):
                        print(f"remote: timeout for {j['group']['id']}; it will render locally", flush=True)
                        failed.add(j["group"]["id"]); drop(j); jobs.remove(j)
                    break
                time.sleep(max(0.5, args.remote_poll_seconds - (time.time() - round_start)))
    except BaseException:
        for j in jobs:
            drop(j, background=False)  # Ctrl-C and errors: the cancel must really be sent
        raise
    finally:
        wait(bg, timeout=10)  # then give up on stragglers; the agent also cleans old jobs by itself
        pool.shutdown(wait=False, cancel_futures=True)
        prog.close()
        if tm:
            print("remote timing: " + ", ".join(f"{k.replace('_', ' ')} {v:.0f}s" for k, v in tm.items()) + f", total {since():.0f}s", flush=True)
    return failed


# -------------------------------------------------------------------------------------------------- driver ---
def render_parts(proj, args, backend, pp, pub, groups_by_id, install):
    """Render all groups (each: chunk parts or stills) on `backend`; remote failures fall back to local.  install(group) runs per finished group."""
    work = proj / "renders"
    ids = list(groups_by_id)
    failed = set()
    if backend["kind"] == "remote":
        groups = list(groups_by_id.values())
        failed = run_remote(proj, args, backend, pp, pub, groups, install, work)
        if failed and args.remote_cpu:
            raise SystemExit(f"remote render failed for {sorted(failed)}")
        if failed:
            print(f"falling back to local rendering for {sorted(failed)}", flush=True)
    todo = [i for i in ids if backend["kind"] == "local" or i in failed]
    if todo:
        lb = backend if backend["kind"] == "local" else local_backend("fallback")
        parts = [p for i in todo for p in groups_by_id[i].get("local_parts", [])]
        stills = [s for i in todo for s in groups_by_id[i].get("local_stills", [])]
        run_local(proj, lb, pp, pub, parts, stills)
        for i in todo:
            groups_by_id[i]["rendered_by"] = "local"
            install(groups_by_id[i])


def cmd_final(proj, args):
    t0 = time.time()
    if not args.no_lint and not do_lint(proj):
        raise SystemExit("lint errors: fix them or pass --no-lint")
    props, narr = load_props(proj)
    pub = stage(proj, props, ".chunk-public")
    pp = proj / "renders" / ".chunk_props.json"; pp.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    chunks, total = make_chunks(props, pub, composer_hash())
    cdir = proj / "renders" / "chunks"; cdir.mkdir(exist_ok=True)
    force = set((args.force or "").split(",")) - {""}
    todo = []
    for c in chunks:
        c["path"] = cdir / f"{c['id']}-{c['fp']}.mp4"
        c["stale"] = c["id"] in force or not c["path"].exists()
        if c["stale"]:
            todo.append(c)
    print(f"chunks: {len(chunks)} total, {len(todo)} to render: {[c['id'] for c in todo]}  (frames {total})", flush=True)
    for c in chunks:
        print(f"  {c['id']} frames {c['from']}-{c['to']} ({(c['to'] - c['from'] + 1) / FPS:.1f}s) fp {c['fp']} {'RENDER' if c['stale'] else 'cached'}")
    only = set((args.only or "").split(",")) - {""}
    if only:
        todo = [c for c in todo if c["id"] in only]
        print(f"--only {sorted(only)}: rendering {[c['id'] for c in todo]} into the cache, no final video", flush=True)
    backend = choose_backend(args)
    set_min_part(args, backend)
    announce(backend)
    if args.plan:
        if todo and backend["kind"] == "remote":
            groups, by_chunk = remote_groups(todo, backend, cdir / ".parts")
            print(f"remote plan: {sum(len(v) for v in by_chunk.values())} parts in {len(groups)} job(s): "
                  + ", ".join(f"{g['id']} {sum(p['to'] - p['from'] + 1 for p in g['parts'])} frames/{g['workers']} processes" for g in groups.values()), flush=True)
        return
    used = backend["kind"]
    audio = start_audio(proj, narr, total) if narr and not only else None
    if todo:
        parts_dir = cdir / ".parts"
        shutil.rmtree(parts_dir, ignore_errors=True); parts_dir.mkdir()
        chunk_by_id = {c["id"]: c for c in todo}
        if backend["kind"] == "remote":
            groups, by_chunk = remote_groups(todo, backend, parts_dir)
            print(f"remote plan: {sum(len(v) for v in by_chunk.values())} parts in {len(groups)} job(s): "
                  + ", ".join(f"{g['id']} {sum(p['to'] - p['from'] + 1 for p in g['parts'])} frames/{g['workers']} processes" for g in groups.values()), flush=True)
        else:
            groups, by_chunk = {}, {}
            plan_workers(backend, len(todo))
            for c in todo:
                parts = split_parts(c, backend["workers"], parts_dir)
                by_chunk[c["id"]] = parts
                groups[c["id"]] = {"id": c["id"], "parts": parts, "local_parts": parts, "local_stills": [],
                                   "chunks": [{"out": p["name"], "from": p["from"], "to": p["to"]} for p in parts], "stills": [],
                                   "outputs": [(p["name"], p["path"]) for p in parts], "expected": {p["name"]: p["to"] - p["from"] + 1 for p in parts}}

        def install(g):
            """Check the parts of one finished job; every chunk whose parts are all there is joined and goes into the cache."""
            for p in g["parts"]:
                n = ffprobe_frames(p["path"]); want = p["to"] - p["from"] + 1
                if n != want:
                    p["path"].unlink(missing_ok=True)
                    raise SystemExit(f"part {p['name']}: {n} frames, expected {want}")
                p["ok"] = True; p["by"] = g.get("rendered_by")
            for cid in dict.fromkeys(p["id"] for p in g["parts"]):
                ps = by_chunk[cid]
                if not all(p.get("ok") for p in ps) or chunk_by_id[cid].get("installed"):
                    continue
                c = chunk_by_id[cid]
                merge_parts(ps, c["path"])
                c["installed"] = True
                c["path"].with_suffix(".json").write_text(json.dumps({"rendered_by": "+".join(sorted({p["by"] or "?" for p in ps})), "backend": backend["label"],
                    "render_profile": backend.get("render") or {}, "parts": len(ps), "at": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False), encoding="utf-8")
                print(f"  {cid} ready ({c['path'].name})", flush=True)

        render_parts(proj, args, backend, pp, pub, groups, install)
        shutil.rmtree(parts_dir, ignore_errors=True)
    if only:
        print(f"done in {time.time() - t0:.0f}s ({used})", flush=True)
        return
    for c in chunks:
        n = ffprobe_frames(c["path"]); want = c["to"] - c["from"] + 1
        if n != want:
            raise SystemExit(f"chunk {c['id']}: {n} frames, expected {want}; delete {c['path']} and retry")
    out = (proj / args.out) if args.out else proj / "renders" / "final.mp4"
    t_mux = time.time()
    mux_final(proj, chunks, total, narr, out, audio)
    print(f"joined and muxed in {time.time() - t_mux:.0f}s", flush=True)
    if audio:
        audio[1].unlink(missing_ok=True)
    keep = {c["path"].name for c in chunks}
    for f in list(cdir.glob("*.mp4")) + list(cdir.glob("*.json")):
        if f.stem not in {Path(k).stem for k in keep} and not args.keep_old:
            f.unlink()
    n = ffprobe_frames(out)
    res = {"success": True, "error": None, "elapsed_seconds": round(time.time() - t0),
           "data": {"operation": "chunked_render", "output": str(out), "chunks_total": len(chunks), "chunks_rendered": [c["id"] for c in todo],
                    "frames": n, "duration_seconds": round(ffprobe_dur(out), 3), "backend": used, "tool": TOOL_VERSION}}
    (proj / "renders" / "render_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("success", json.dumps(res["data"], ensure_ascii=False), flush=True)


def start_audio(proj, narr, total):
    """Encode the narration (stereo 48 kHz AAC 320k, padded/cut to the video length) in the background while the video renders:
    AAC at 320k takes ~30 s of one core, which used to be added after the last chunk."""
    dest = proj / "renders" / ".narration.m4a"
    dest.unlink(missing_ok=True)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-i", narr, "-af", "apad", "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "320k",
                             "-t", f"{total / FPS:.6f}", str(dest)])
    return proc, dest


def mux_final(proj, chunks, total, narr, out, audio=None):
    lst = proj / "renders" / ".concat.txt"
    lst.write_text("".join(f"file '{c['path']}'\n" for c in chunks), encoding="utf-8")
    vid = proj / "renders" / ".video_only.mp4"
    if len({stream_sig(c["path"]) for c in chunks}) > 1:
        print("chunks have different stream parameters (rendered with different encoders?): joining with a re-encode", flush=True)
        reencode_join(lst, vid)
    else:
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(vid)])
    n = ffprobe_frames(vid)
    if n != total:
        print(f"copy-concat gave {n} frames, expected {total}: re-encoding the join", flush=True)
        reencode_join(lst, vid)
        if ffprobe_frames(vid) != total:
            raise SystemExit(f"still {ffprobe_frames(vid)} frames, expected {total}")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(vid)]
    if audio and audio[0].wait() == 0 and audio[1].is_file():  # pre-encoded while rendering: just copy both streams
        cmd += ["-i", str(audio[1]), "-map", "0:v", "-map", "1:a", "-c", "copy"]
    elif narr:
        # same audio as the CLI render: stereo 48 kHz AAC 320k, padded with silence to the video length
        cmd += ["-i", narr, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "apad", "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "320k", "-shortest"]
    else:
        cmd += ["-c:v", "copy"]
    subprocess.check_call(cmd + ["-movflags", "+faststart", str(out)])


def cmd_stills(proj, args, times=None, outdir=None, names=None):
    props, _ = load_props(proj)
    pub = stage(proj, props, ".still-public")
    pp = proj / "renders" / ".still_props.json"; pp.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    times = times if times is not None else [float(t) for t in args.stills]
    outdir = outdir or proj / "renders" / "stills"
    outdir.mkdir(parents=True, exist_ok=True)
    stills = []
    for i, t in enumerate(times):
        nm = names[i] if names else f"t{int(round(t * 10)):05d}.png"
        stills.append({"out": str(outdir / nm), "frame": round(t * FPS), "name": nm})
    backend = choose_backend(args)
    if backend["kind"] == "remote" and not args.remote_cpu and len(stills) <= STILLS_LOCAL_MAX:
        backend = local_backend(f"only {len(stills)} stills: faster on this machine than through the channel")
    announce(backend)
    g = {"id": "stills", "local_parts": [], "local_stills": [{"out": s["out"], "frame": s["frame"]} for s in stills], "chunks": [],
         "stills": [{"out": s["name"], "frame": s["frame"]} for s in stills], "outputs": [(s["name"], Path(s["out"])) for s in stills], "expected": {}}
    render_parts(proj, args, backend, pp, pub, {"stills": g}, lambda grp: None)
    missing = [s["name"] for s in stills if not Path(s["out"]).is_file()]
    if missing:
        raise SystemExit(f"stills missing: {missing[:5]}")


def cmd_sample(proj, args):
    a, b = float(args.sample[0]), float(args.sample[1])
    props, narr = load_props(proj)
    pub = stage(proj, props, ".chunk-public")
    pp = proj / "renders" / ".chunk_props.json"; pp.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    fa, fb = round(a * FPS), round(b * FPS) - 1
    backend = choose_backend(args)
    set_min_part(args, backend)
    announce(backend)
    parts_dir = proj / "renders" / ".sample_parts"
    shutil.rmtree(parts_dir, ignore_errors=True); parts_dir.mkdir()
    chunk = {"id": "S", "from": fa, "to": fb, "fp": f"{fa}-{fb}"}
    plan_workers(backend, 1)
    parts = split_parts(chunk, backend["workers"], parts_dir)
    vid = proj / "renders" / ".sample_video.mp4"
    g = {"id": "sample", "parts": parts, "local_parts": parts, "local_stills": [],
         "chunks": [{"out": p["name"], "from": p["from"], "to": p["to"]} for p in parts], "stills": [],
         "outputs": [(p["name"], p["path"]) for p in parts], "expected": {p["name"]: p["to"] - p["from"] + 1 for p in parts}}
    render_parts(proj, args, backend, pp, pub, {"sample": g}, lambda grp: merge_parts(grp["parts"], vid))
    out = (proj / args.out) if args.out else proj / "renders" / f"sample_{args.sample[0]}-{args.sample[1]}.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(vid)]
    if narr:
        cmd += ["-ss", str(a), "-t", str(b - a), "-i", narr, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "apad", "-ac", "2", "-ar", "48000",
                "-c:a", "aac", "-b:a", "320k", "-shortest"]
    else:
        cmd += ["-c:v", "copy"]
    subprocess.check_call(cmd + ["-movflags", "+faststart", str(out)])
    shutil.rmtree(parts_dir, ignore_errors=True)
    print(f"sample ready: {out} ({ffprobe_dur(out):.2f}s)", flush=True)


def do_lint(proj, props_name="render_props.json"):
    props = json.loads((proj / props_name).read_text(encoding="utf-8"))
    tl = proj / "assets/audio/narration_timeline.json"
    quiz = json.loads(tl.read_text(encoding="utf-8")).get("quiz", []) if tl.exists() else []
    errs, warns = whiteboard_lint.lint_props(props, quiz)
    for w in warns:
        print("lint WARN ", w)
    for e in errs:
        print("lint ERROR", e)
    print(f"lint: {len(errs)} error(s), {len(warns)} warning(s)")
    return not errs


def key_times(cut, quiz):
    """State-after-each-burst sample times (absolute seconds) for one whiteboard cut."""
    base, end = float(cut["in_seconds"]), float(cut["out_seconds"])
    ev = []  # (start, finish)
    for it in cut["whiteboard"].get("items", []):
        k = it.get("kind")
        if k == "memory":
            for c in it.get("cells", []):
                ev.append((c["at"], c["at"] + 1.0))
                for s in c.get("sets", []):
                    ev.append((s["at"], s["at"] + 0.8))
            for a in it.get("arrows", []):
                ev.append((a["at"], a["at"] + a.get("dur", 0.6)))
        elif k == "code":
            ats = it.get("lineAts") or [it["at"] + i * it.get("lineGap", it.get("lineDur", 0.8)) for i in range(len(it.get("lines", [])))]
            ev.append((min(ats), max(ats) + it.get("lineDur", 0.8)))
        else:
            ev.append((it["at"], it["at"] + float(it.get("dur", 0.8) or 0.8)))
    ev.sort()
    times, i = [], 0
    while i < len(ev):
        j = i; fin = ev[i][1]
        while j + 1 < len(ev) and ev[j + 1][0] - ev[i][0] < 1.5:
            j += 1; fin = max(fin, ev[j][1])
        times.append(base + fin + 0.3); i = j + 1
    for q in quiz:
        if base <= q["question_end"] < end:
            times += [q["question_end"] + 1.5, q["answer_not_before"] + 1.8]
    times.append(end - 0.1)
    return sorted({round(min(max(t, base + 0.2), end - 0.05), 1) for t in times})


def cmd_contact(proj, args):
    from PIL import Image, ImageDraw
    props = json.loads((proj / "render_props.json").read_text(encoding="utf-8"))
    tl = proj / "assets/audio/narration_timeline.json"
    quiz = json.loads(tl.read_text(encoding="utf-8")).get("quiz", []) if tl.exists() else []
    cuts = [c for c in props["cuts"] if c.get("whiteboard") and (not args.contact or c["id"] in args.contact)]
    outdir = proj / "renders" / "contact"; sdir = outdir / "stills"
    if outdir.exists():
        shutil.rmtree(outdir)
    plan = [(c["id"], t) for c in cuts for t in key_times(c, quiz)]
    print(f"contact: {len(plan)} key moments in {len(cuts)} boards", flush=True)
    t0 = time.time()
    cmd_stills(proj, args, times=[t for _, t in plan], outdir=sdir, names=[f"{i}_{cid}_{t:.1f}.png" for i, (cid, t) in enumerate(plan)])
    print(f"stills done in {time.time() - t0:.0f}s", flush=True)
    for c in cuts:
        items = [(i, t) for i, (cid, t) in enumerate(plan) if cid == c["id"]]
        cols, tw, th = 4, 480, 270
        rows = math.ceil(len(items) / cols)
        sheet = Image.new("RGB", (cols * tw, rows * th), "white")
        d = ImageDraw.Draw(sheet)
        for n, (i, t) in enumerate(items):
            im = Image.open(sdir / f"{i}_{c['id']}_{t:.1f}.png").convert("RGB").resize((tw, th), Image.LANCZOS)
            x, y = (n % cols) * tw, (n // cols) * th
            sheet.paste(im, (x, y)); d.rectangle([x, y + th - 22, x + 90, y + th], fill="black"); d.text((x + 4, y + th - 18), f"{t:.1f}s", fill="white")
        sheet.save(outdir / f"{c['id']}.png")
        print(f"  {c['id']}: {len(items)} frames -> {outdir / (c['id'] + '.png')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj"); ap.add_argument("--final", action="store_true"); ap.add_argument("--plan", action="store_true")
    ap.add_argument("--stills", nargs="+"); ap.add_argument("--contact", nargs="*"); ap.add_argument("--sample", nargs=2, metavar=("START", "END"))
    ap.add_argument("--force"); ap.add_argument("--only", help="render only these boards (comma list, e.g. K1,K5) into the chunk cache; no final video is assembled"); ap.add_argument("--out"); ap.add_argument("--no-lint", action="store_true"); ap.add_argument("--keep-old", action="store_true")
    ap.add_argument("--concurrency", type=int, default=None, help="browser tabs per render process (default 2)")
    ap.add_argument("--workers", type=int, default=None, help="parallel render processes (default: cores/2 locally, the agent's recommendation remotely)")
    ap.add_argument("--local", action="store_true", help="render on this machine only")
    ap.add_argument("--render-profile", default=None, help="JSON performance profile for experiments, e.g. '{\"gl\":\"angle-egl\",\"chromeMode\":\"chrome-for-testing\"}' (default: what the remote agent publishes)")
    ap.add_argument("--remote-cpu", action="store_true", help="require the remote CPU render channel (error if unusable)")
    ap.add_argument("--allow-drift", action="store_true", help="with --remote-cpu: use the channel even if it cannot guarantee identical pictures (experiments only)")
    ap.add_argument("--remote-runtime", default=os.environ.get("OPENMONTAGE_RENDER_RUNTIME", "om-20261007-remotion-v2"))
    ap.add_argument("--remote-identity", default=os.environ.get("OPENMONTAGE_RENDER_IDENTITY", "/root/.ssh/openmontage_render_local"))
    ap.add_argument("--remote-known-hosts", default=os.environ.get("OPENMONTAGE_RENDER_KNOWN_HOSTS", "/root/.ssh/openmontage_render_known_hosts"))
    ap.add_argument("--remote-port", type=int, default=int(os.environ.get("OPENMONTAGE_RENDER_PORT", "17865")))
    ap.add_argument("--min-part", type=int, default=None, help="shortest part (frames) a chunk may be split into (default 120); longer parts mean fewer Chrome start-ups")
    ap.add_argument("--remote-poll-seconds", type=float, default=3.0)
    ap.add_argument("--remote-timeout", type=float, default=8 * 60 * 60)
    args = ap.parse_args()
    proj = Path(args.proj).resolve()
    if args.final or args.plan or args.only:
        cmd_final(proj, args)
    elif args.stills:
        cmd_stills(proj, args)
    elif args.contact is not None:
        cmd_contact(proj, args)
    elif args.sample:
        cmd_sample(proj, args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
