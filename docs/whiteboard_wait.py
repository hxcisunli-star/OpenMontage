"""Wait for a background whiteboard render / verify job by watching its log, then print how it ended.
Run (usually in the background):  python3 docs/whiteboard_wait.py <logfile> [--timeout 10800] [--poll 5] [--grace 15]
Why a script: the copy-pasted `until grep -q 'done in' log` never ended for the REMOTE whole-lesson render (its last line is `success {...}`, not `done in`),
and a background "completed" notice only means the nohup shell exited. Terminal lines understood:
  success   `success {` (whole lesson rendered), `done in N s` (local chunks / `--only` run; waits --grace seconds for a `success` line that may still follow),
            `stills done in`, `local-ref done`, `verify: done`
  failure   `Traceback`, `node render failed`, `remote render failed`, `lint errors`, `local-ref failed`, `verify: FAILED`
  notice    `falling back to local rendering` (still running - printed, not terminal)
Exit code 0 success, 1 failure, 2 timeout."""
import argparse
import re
import sys
import time
from pathlib import Path

OK = re.compile(r"^(success \{|stills done in|local-ref done|verify: done)", re.M)
DONE_IN = re.compile(r"^done in \d+s", re.M)
FAIL = re.compile(r"(Traceback \(most recent call last\)|node render failed|remote render failed|lint errors|local-ref failed|verify: FAILED)")
NOTICE = re.compile(r"^(falling back to local rendering.*)$", re.M)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--timeout", type=float, default=3 * 3600)
    ap.add_argument("--poll", type=float, default=5)
    ap.add_argument("--grace", type=float, default=15)
    ap.add_argument("--tail", type=int, default=8)
    args = ap.parse_args()
    log = Path(args.log)
    t0 = time.time()
    seen_notice, done_in_at, last_prog = set(), None, 0
    while True:
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        for n in NOTICE.findall(text):
            if n not in seen_notice:
                seen_notice.add(n)
                print("NOTICE:", n, flush=True)
        m = FAIL.search(text)
        if m:
            print(f"WAIT-RESULT failed ({m.group(1)}) after {time.time() - t0:.0f}s")
            print("\n".join(text.splitlines()[-args.tail:]))
            return 1
        if OK.search(text):
            print(f"WAIT-RESULT success after {time.time() - t0:.0f}s")
            print("\n".join(text.splitlines()[-args.tail:]))
            return 0
        if DONE_IN.search(text):
            done_in_at = done_in_at or time.time()
            if time.time() - done_in_at >= args.grace:
                print(f"WAIT-RESULT success (done in, no further output for {args.grace:.0f}s) after {time.time() - t0:.0f}s")
                print("\n".join(text.splitlines()[-args.tail:]))
                return 0
        if time.time() - last_prog > 60:
            prog = re.findall(r"progress \d+%[^\n]*", text)
            if prog:
                print(f"[{time.time() - t0:.0f}s] {prog[-1]}", flush=True)
            last_prog = time.time()
        if time.time() - t0 > args.timeout:
            print(f"WAIT-RESULT timeout after {args.timeout:.0f}s (log {'exists' if log.exists() else 'missing'})")
            return 2
        time.sleep(args.poll)


if __name__ == "__main__":
    sys.exit(main())
