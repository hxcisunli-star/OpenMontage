"""Write the publish checkpoint (awaiting_human) AFTER the cross review, the fixes, the e-book export and the release pack (finish_publish.py --no-checkpoint only exports).
The checkpoint says what exists and what was NOT done; approval is the user's own word 发布通过 (docs/whiteboard_gate.py approve), never written here.
Needs validation/publish_export_log.json (finish_publish.py), projects/_ebook/site-check.json (passing) and, optionally, review/publish/checkpoint_notes.json (a JSON object merged into the metadata).
Run (repo root): PYTHONPATH=. .venv/bin/python projects/<lesson>/scripts/write_publish_checkpoint.py"""
import json
import os
import sys

from project_paths import ROOT, P, PID
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from lib.checkpoint import write_checkpoint  # noqa: E402

log = json.loads((P / "validation/publish_export_log.json").read_text(encoding="utf-8"))
chk = json.loads((ROOT / "projects/_ebook/site-check.json").read_text(encoding="utf-8"))
assert chk["pass"] and not chk["failed"], "the whole-site check must pass before the checkpoint is written"
assert (P / "exports/video/output.mp4").exists() and (P / "exports/metadata/exercises.txt").exists(), "the export and the exercises must exist"
notes_f = P / "review/publish/checkpoint_notes.json"
notes = json.loads(notes_f.read_text(encoding="utf-8")) if notes_f.exists() else {}
write_checkpoint(P.parent, PID, "publish", "awaiting_human", {"publish_log": log["publish_log"]}, pipeline_type="animated-explainer",
                 human_approval_required=True, metadata={"note": "offline export only; nothing uploaded. Platform not chosen (generic); visibility private.", **notes})
print("publish checkpoint: awaiting_human")
