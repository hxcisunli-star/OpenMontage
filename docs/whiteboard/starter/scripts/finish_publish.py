"""Export bundle (local only, nothing uploaded) and write the publish checkpoint (awaiting_human)."""
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
from lib.checkpoint import write_checkpoint
from tools.publishers.export_bundle import ExportBundle
PID = "__PID__"; PDIR = ROOT / "projects"; PROJ = PDIR / PID
meta = json.loads((PROJ / "publish_meta.json").read_text(encoding="utf-8"))
ex = ExportBundle().execute({
    "video_path": str(PROJ / "renders/final.mp4"), "title": meta["title"], "project_name": PID, "description": meta["description"],
    "tags": meta["tags"], "hashtags": meta["hashtags"], "chapters": meta["chapters"],
    "subtitles_path": str(PROJ / "assets/subtitles.srt"), "thumbnail_path": str(PROJ / "assets/thumbnail.png"),
    "platform": "generic", "visibility": "private"})
if not ex.success:
    print("export FAILED:", ex.error); sys.exit(4)
for f in ex.data["files_written"]:
    print("  ", Path(f).relative_to(ROOT), f"{Path(f).stat().st_size / 1e6:.2f}MB")
write_checkpoint(PDIR, PID, "publish", "awaiting_human", {"publish_log": ex.data["publish_log"]}, pipeline_type="animated-explainer",
                 human_approval_required=True, metadata={"note": "offline export only; nothing uploaded. Platform not chosen (generic); visibility private."})
print("publish checkpoint: awaiting_human | export:", ex.data["export_path"])
