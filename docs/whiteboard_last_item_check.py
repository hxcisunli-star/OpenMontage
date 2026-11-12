"""Check that the last handwriting item of every whiteboard cut finishes before the board fades out (lesson 40 lesson).
Run after rebuild_edit.sh:  .venv/bin/python docs/whiteboard_last_item_check.py projects/<lesson> [--min-margin 0.6] [--include-memory]
Prints, per cut, when the last item ends, when the fade-out starts and the margin; margin < --min-margin (default 0.6 s) is reported as TOO LATE (exit code 1).
Timing follows the renderer (docs/whiteboard_boardtime.py): code items end at their last line start + lineDur (the version used for lessons 41-43 counted
only 0.5 s after the first line, so it under-reported late code lines)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whiteboard_boardtime import board_rows  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj", nargs="?", default=".")
    ap.add_argument("--min-margin", type=float, default=0.6)
    ap.add_argument("--include-memory", action="store_true", help="also count memory boxes, arrows and value changes")
    args = ap.parse_args()
    bad = 0
    for r in board_rows(args.proj, include_memory=args.include_memory):
        late = r["margin"] < args.min_margin
        bad += late
        note = f"  (at the end of the board only {r['progress_at_end']:.0%} is drawn)" if r["last_end"] > r["length"] else ""
        print(r["id"], "len", round(r["length"], 1), "last item ends", round(r["last_end"], 2), "fade starts", round(r["fade_start"], 1), "margin", round(r["margin"], 2),
              (r["last_kind"], r["last_text"][:24]), "TOO LATE" if late else "OK", note)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
