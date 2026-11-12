"""Build the self-test kit for the remote render machine into projects/_remote_kit/ (not in git; safe to rebuild any time).

  .venv/bin/python docs/make_remote_kit.py [projects/c-recursion-cn]

Contents: the exact job input a real remote job uploads (composer overlay, props, public), reference stills and a 300-frame reference video
rendered on THIS machine (the reference environment), bench.py and README.md (copied from docs/remote-render-kit/).
No credentials are copied.
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "docs")); os.chdir(ROOT)
import whiteboard_render as wr  # noqa: E402

proj = (ROOT / (sys.argv[1] if len(sys.argv) > 1 else "projects/c-recursion-cn")).resolve()
kit = ROOT / "projects" / "_remote_kit"
STILLS = {"t00060": 6.0, "t01200": 120.0, "t01533": 153.3, "t01580": 158.0, "t02908": 290.8, "t03360": 336.0}

shutil.rmtree(kit, ignore_errors=True); (kit / "refs" / "stills").mkdir(parents=True); (kit / "results").mkdir()
props, _ = wr.load_props(proj)
pub = wr.stage(proj, props, ".kit-public")
pp = proj / "renders" / ".kit_props.json"; pp.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
spec = {"propsPath": "props.json", "publicDir": "public", "composition": "Explainer", "concurrency": 2, "workers": 1, "timeoutMs": 1800000, "chunks": [], "stills": [],
        "composer_hash": wr.composer_hash()}
wr.build_remote_input(kit / "input", pp, pub, spec)
shutil.rmtree(proj / "renders" / ".kit-public", ignore_errors=True)

# reference stills: rendered locally with the deterministic fonts
subprocess.check_call([str(ROOT / ".venv/bin/python"), "docs/whiteboard_render.py", str(proj), "--local", "--stills", *[str(t) for t in STILLS.values()]])
for name, t in STILLS.items():
    shutil.copy2(proj / "renders" / "stills" / f"t{int(round(t * 10)):05d}.png", kit / "refs" / "stills" / f"{name}.png")

# reference video: frames 3173..3472 (board K4) rendered here as ONE clean part (default profile, single process)
ref_spec = {"propsPath": str(kit / "input/props.json"), "publicDir": str(kit / "input/public"), "composition": "Explainer", "concurrency": 4, "workers": 1,
            "timeoutMs": 1800000, "chunks": [{"out": str(kit / "refs" / "ref_K4_3173-3472.mp4"), "from": 3173, "to": 3472}], "stills": []}
(kit / "refs" / "_ref_job.json").write_text(json.dumps(ref_spec), encoding="utf-8")
subprocess.check_call(["node", str(ROOT / "remotion-composer/render-tools/render_chunks.mjs"), str(kit / "refs" / "_ref_job.json")], cwd=ROOT / "remotion-composer")
(kit / "refs" / "_ref_job.json").unlink()

for f in ("bench.py", "README.md"):
    shutil.copy2(ROOT / "docs" / "remote-render-kit" / f, kit / f)
(kit / "REFERENCE_ENV.txt").write_text(
    "Reference machine: Ubuntu 24.04 x86_64, Node 18.19.1, Remotion 4.0.484, private fontconfig remotion-composer/render-fonts (DejaVu only),\n"
    "CPU rasterization (Remotion default gl for 4.0 = null), libx264 CRF 18 default.\n", encoding="utf-8")
size = sum(p.stat().st_size for p in kit.rglob("*") if p.is_file()) / 1e6
print(f"kit ready: {kit}  ({size:.1f} MB)")
for p in sorted(kit.rglob("*")):
    if p.is_file() and p.stat().st_size > 500_000:
        print(f"  {p.relative_to(kit)}  {p.stat().st_size / 1e6:.1f} MB")
