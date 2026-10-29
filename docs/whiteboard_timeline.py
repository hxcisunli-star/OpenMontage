"""Per-stage time table of one whiteboard project, read from its own records (no typed numbers).
Run: python3 docs/whiteboard_timeline.py projects/<project> [--since 2026-10-27T12:54:00+00:00] [--json]
Source: projects/<p>/approvals.jsonl (one line per recorded password: time, stage, gate, said, awaiting_since) and project.json created_at.
For every recorded gate:  production = previous gate (or the start) -> awaiting_since;  waiting for the user = awaiting_since -> the password.
Limits: only gates that have an approvals line appear; work before the project folder exists (planning, research done outside the folder) is not recorded unless
--since gives its start; a gate whose awaiting_since is missing is counted as production in full (marked '?'). Times are UTC as written in the files."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def parse(s):
    return datetime.fromisoformat(s)


def hours(a, b):
    return (b - a).total_seconds() / 3600


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--since", help="ISO time to count production from instead of project.json created_at")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    p = Path(args.project)
    rows = [json.loads(l) for l in (p / "approvals.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        sys.exit("approvals.jsonl is empty")
    rows.sort(key=lambda r: r["time"])
    start = args.since or json.loads((p / "project.json").read_text(encoding="utf-8")).get("created_at")
    prev = parse(start) if start else parse(rows[0].get("awaiting_since") or rows[0]["time"])
    out, prod_total, wait_total = [], 0.0, 0.0
    for r in rows:
        t = parse(r["time"])
        aw = parse(r["awaiting_since"]) if r.get("awaiting_since") else None
        if aw is None:
            prod, wait, mark = hours(prev, t), 0.0, "?"
        else:
            prod, wait, mark = max(0.0, hours(prev, aw)), max(0.0, hours(aw, t)), ""
        prod_total += prod
        wait_total += wait
        out.append({"stage": r["stage"], "gate": r["gate"], "production_h": round(prod, 2), "waiting_for_user_h": round(wait, 2), "at": r["time"][:19], "unknown_split": bool(mark)})
        prev = t
    if args.json:
        print(json.dumps({"project": p.name, "rows": out, "production_h": round(prod_total, 2), "waiting_for_user_h": round(wait_total, 2)}, ensure_ascii=False, indent=1))
        return
    print(f"{p.name}  (production counted from {start or 'the first awaiting_human'}; UTC)")
    print(f"{'stage':<12}{'gate':<18}{'production h':>13}{'waiting h':>11}  password at")
    for o in out:
        print(f"{o['stage']:<12}{o['gate']:<18}{o['production_h']:>13.2f}{o['waiting_for_user_h']:>11.2f}  {o['at']}{'  ? no awaiting_since: all counted as production' if o['unknown_split'] else ''}")
    print(f"{'total':<30}{prod_total:>13.2f}{wait_total:>11.2f}")
    print("Not in the records: work before the project folder was made, and everything after the last recorded gate.")


if __name__ == "__main__":
    main()
