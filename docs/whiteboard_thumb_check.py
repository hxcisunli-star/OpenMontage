"""Check that the thumbnail frame is fully drawn and not yet fading (lessons 21, 27 and 40 each took a half-written frame).
Run:  .venv/bin/python docs/whiteboard_thumb_check.py projects/<lesson> <seconds> [--margin 0.05]      exit code 1 if the frame is not usable
      .venv/bin/python docs/whiteboard_thumb_check.py projects/<lesson> --list                          valid window for every board (pick the time from here)
A frame at time t (video seconds, no cover intro) is usable when every pen item and memory box of its board has finished (+ --margin) and the fade-out has not started.
It checks timing only: still LOOK at the exported image before approving (the pen is removed from the thumbnail, captions are off)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whiteboard_boardtime import board_rows  # noqa: E402


def windows(proj, margin):
    out = []
    for r in board_rows(proj, include_memory=True):
        lo, hi = r["in"] + r["last_end"] + margin, r["in"] + r["fade_start"]
        out.append((r["id"], r["in"], r["out"], lo, hi, r["last_text"]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("seconds", nargs="?", type=float)
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    wins = windows(args.proj, args.margin)
    if args.list or args.seconds is None:
        for cid, a, b, lo, hi, text in wins:
            ok = f"{lo:.2f} - {hi:.2f}" if lo <= hi else "none (the last item finishes inside the fade)"
            print(f"{cid}: board {a:.2f}-{b:.2f}  usable frame time {ok}   last item: {text[:24]}")
        return 0
    t = args.seconds
    for cid, a, b, lo, hi, text in wins:
        if a <= t < b:
            if t < lo:
                print(f"FAIL {t}s is in {cid} but its last item ({text[:24]!r}) is still being drawn until {lo - args.margin:.2f}s; earliest usable {lo:.2f}s" + (f", latest {hi:.2f}s" if lo <= hi else " (no usable time)"))
                return 1
            if t > hi:
                print(f"FAIL {t}s is in {cid} but the board is already fading (fade starts {hi:.2f}s); usable window {lo:.2f}-{hi:.2f}s" if lo <= hi else f"FAIL {t}s: {cid} has no usable time")
                return 1
            print(f"OK   {t}s in {cid}: fully drawn since {lo - args.margin:.2f}s, fade starts {hi:.2f}s")
            return 0
    print(f"FAIL {t}s is not inside any board (total {wins[-1][2]:.2f}s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
