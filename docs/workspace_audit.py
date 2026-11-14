#!/usr/bin/env python3
"""Read-only housekeeping check for /home/MyProject (rules: .claude/rules/workspace-layout.md).

Run:  .venv/bin/python docs/workspace_audit.py [--root /home/MyProject] [--max-age-days 3]

Prints NOTHING when everything is in order, so it can run as a SessionStart hook without adding noise.
Otherwise prints at most 10 lines (Chinese) that name what is out of place. It never deletes or moves anything,
and any internal error ends silently with exit code 0 (a hygiene check must never disturb a session).

Checks:
  1. Entries directly under the root that are not on the allow-list (new scratch folders, backups, probes, loose files).
  2. Entries under <root>/_scratch that have no WHY.md, or whose newest file is older than --max-age-days.
  3. Disk usage above 70 %.
"""
import argparse
import os
import shutil
import sys
import time

ALLOWED = {
    "OpenMontage", "openhands-team", "openhands-harness2", "_scratch",
    "AGENTS.md", "OPENHANDS-DISPATCH.md", "OPENHANDS-DISPATCH.html",
}
# Present before the rules existed; the user's own or origin unclear. Tolerated until the user decides (2026-11-04).
# The names live in a small file OUTSIDE the repository (one folder name per line, a trailing space is part of the name), so personal folder names never enter the repository.
LEGACY_FILE = os.path.join(os.path.expanduser("~"), ".claude", "workspace_audit_legacy.txt")
LEGACY = set()
try:
    with open(LEGACY_FILE, encoding="utf-8") as _f:
        LEGACY = {_l.rstrip("\n") for _l in _f if _l.strip()}
except OSError:
    pass
DISK_WARN_PERCENT = 70
MAX_LISTED = 6
SCAN_CAP = 20000  # files looked at per scratch entry when finding its newest mtime


def newest_mtime(path):
    newest = os.lstat(path).st_mtime
    seen = 0
    stack = [path]
    while stack and seen < SCAN_CAP:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    seen += 1
                    try:
                        newest = max(newest, e.stat(follow_symlinks=False).st_mtime)
                    except OSError:
                        continue
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
            if seen >= SCAN_CAP:
                break
        except OSError:
            continue
    return newest


def listed(names):
    names = sorted(names)
    shown = "、".join(f"`{n}`" for n in names[:MAX_LISTED])
    return shown + (f" 等共 {len(names)} 个" if len(names) > MAX_LISTED else "")


def audit(root, max_age_days):
    problems = []
    strays = []
    with os.scandir(root) as it:
        for e in it:
            if e.name.startswith(".") or e.name in ALLOWED or e.name in LEGACY:
                continue
            strays.append(e.name)
    if strays:
        problems.append(f"根目录 {root} 里有不在规范里的条目：{listed(strays)}。临时工作区、备份、探针应建在 _scratch/ 下。")

    scratch = os.path.join(root, "_scratch")
    if os.path.isdir(scratch):
        no_why, stale = [], []
        now = time.time()
        with os.scandir(scratch) as it:
            for e in it:
                if e.name == "README.md" or e.name.startswith("."):
                    continue
                if not (e.is_dir(follow_symlinks=False) and os.path.isfile(os.path.join(e.path, "WHY.md"))):
                    no_why.append(e.name)
                if (now - newest_mtime(e.path)) / 86400 > max_age_days:
                    stale.append(e.name)
        if no_why:
            problems.append(f"_scratch/ 里缺 WHY.md 的条目：{listed(no_why)}。")
        if stale:
            problems.append(f"_scratch/ 里超过 {max_age_days} 天没动的条目（孤儿？先看 WHY.md，存档核对后再删）：{listed(stale)}。")

    usage = shutil.disk_usage(root)
    percent = round(usage.used * 100 / usage.total)
    if percent > DISK_WARN_PERCENT:
        problems.append(f"磁盘已用 {percent}%（超过 {DISK_WARN_PERCENT}%），硬盘有限，先清理用完的工作区和备份。")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default="/home/MyProject")
    parser.add_argument("--max-age-days", type=float, default=3)
    args = parser.parse_args(argv)
    try:
        problems = audit(args.root, args.max_age_days)
    except Exception:
        return 0
    if problems:
        print("【目录检查】docs/workspace_audit.py（只读）发现：")
        for line in problems[:8]:
            print("- " + line)
        print("规范：.claude/rules/workspace-layout.md。不是自己建的不要删，先看 WHY.md 或问用户。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
