#!/usr/bin/env python3
"""Check that a scene plan names its presentation devices (series with `presentation_required` in docs/whiteboard/series.yaml).
Run:  .venv/bin/python docs/whiteboard_scene_plan_check.py projects/<lesson>        exit code 1 on any ERROR
The scene plan schema has no field for it, so the convention is: the `movement` text of every scene STARTS with "呈现手段：手段一、手段二；…", every device from the series' `devices` list.
  ERROR  a scene whose movement does not start with 呈现手段：, or names a device that is not in the list
  WARN   a scene that uses only 纯板书 (hand-written text, boxes, arrows) - fine now and then, but the series exists because lessons built only from boxes were too thin;
         WARN when half or more of the scenes are 纯板书 only, or when the whole lesson uses fewer than 4 different devices"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whiteboard_lessons import series_config, series_of  # noqa: E402

HEAD = re.compile(r"^\s*呈现手段：([^；。]*)")


def check(scenes, devices):
    errors, warns, used, plain_only = [], [], set(), 0
    for sc in scenes:
        m = HEAD.match(sc.get("movement", ""))
        if not m:
            errors.append(f"{sc['id']}: movement must start with 呈现手段：手段一、手段二；…（手段取自：{'、'.join(devices)}）")
            continue
        names = [x.strip() for x in re.split(r"[、,，]", m.group(1)) if x.strip()]
        bad = [x for x in names if x not in devices]
        if not names or bad:
            errors.append(f"{sc['id']}: 呈现手段 {'、'.join(bad) or '为空'} 不在清单里（{'、'.join(devices)}）")
            continue
        used.update(names)
        if set(names) == {"纯板书"}:
            plain_only += 1
            warns.append(f"{sc['id']}: 只用纯板书")
    n = len(scenes)
    if n and plain_only * 2 >= n:
        warns.append(f"{plain_only}/{n} 个场景只用纯板书：表达手段过于单一")
    if n and len(used - {"纯板书"}) < 3:
        warns.append(f"全课只用了 {len(used)} 种手段（{'、'.join(sorted(used))}）：少于 4 种，想想哪些内容该换个说法")
    return errors, warns, used


def main(argv):
    proj = Path(argv[0])
    cfg = series_config(series_of(proj))
    if not cfg.get("presentation_required"):
        print(f"series {series_of(proj)}: no presentation devices required")
        return 0
    scenes = json.loads((proj / "artifacts/scene_plan.json").read_text(encoding="utf-8"))["scenes"]
    errors, warns, used = check(scenes, cfg["devices"])
    for w in warns:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"scene plan devices: {len(scenes)} scenes, {len(used)} devices used ({'、'.join(sorted(used))}); {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
