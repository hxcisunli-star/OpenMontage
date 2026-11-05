"""Export bundle (local only, nothing uploaded).  Run BEFORE docs/whiteboard_prepend_cover.py: it exports renders/final.mp4 as exports/video/output.mp4 (running it again after the cover
would overwrite the video that has the cover: redo the cover then).  With --no-checkpoint (lesson 3) nothing is written to the gate: the checkpoint is written by write_publish_checkpoint.py
once the cross review, the fixes, the e-book export and the release pack are done, so nobody reads "awaiting_human" before that.  Without the flag it also writes the publish checkpoint (older lessons)."""
import json
import os
import sys
from pathlib import Path

from project_paths import ROOT, P
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from lib.checkpoint import write_checkpoint  # noqa: E402
from tools.publishers.export_bundle import ExportBundle  # noqa: E402

PID = "__PID__"
PDIR = P.parent
PROJ = P
meta = json.loads((PROJ / "publish_meta.json").read_text(encoding="utf-8"))
ex = ExportBundle().execute({
    "video_path": str(PROJ / "renders/final.mp4"), "title": meta["title"], "project_name": PID, "description": meta["description"],
    "tags": meta["tags"], "hashtags": meta["hashtags"], "chapters": meta["chapters"],
    "subtitles_path": str(PROJ / "assets/subtitles.srt"), "thumbnail_path": str(PROJ / "assets/thumbnail.png"),
    "platform": "generic", "visibility": "private"})
if not ex.success:
    print("export FAILED:", ex.error)
    sys.exit(4)
for f in ex.data["files_written"]:
    print("  ", Path(f).relative_to(ROOT), f"{Path(f).stat().st_size / 1e6:.2f}MB")
(PROJ / "validation").mkdir(exist_ok=True)
(PROJ / "validation/publish_export_log.json").write_text(json.dumps({"publish_log": ex.data["publish_log"], "export_path": ex.data["export_path"]}, ensure_ascii=False, indent=1), encoding="utf-8")
if "--no-checkpoint" in sys.argv:
    print("export done; no checkpoint written | export:", ex.data["export_path"])
    sys.exit(0)
write_checkpoint(PDIR, PID, "publish", "awaiting_human", {"publish_log": ex.data["publish_log"]}, pipeline_type="animated-explainer",
                 human_approval_required=True, metadata={"note": "offline export only; nothing uploaded. Platform not chosen (generic); visibility private."})
print("publish checkpoint: awaiting_human | export:", ex.data["export_path"])
