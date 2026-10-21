"""Gate helper for the whiteboard lessons: which lesson / stage are we at, and record a user approval only when it is valid.
Run (repo root):
  .venv/bin/python docs/whiteboard_gate.py status [--all]
  .venv/bin/python docs/whiteboard_gate.py approve <project> <stage> "<the user's exact words>" [--dry-run]
  .venv/bin/python docs/whiteboard_gate.py record <project|-> plan|sample "<the user's exact words>"      (gates that have no checkpoint: 计划确认, 样音通过)
`approve` calls lib.checkpoint.write_checkpoint(... human_approved=True ...) ONLY when
  - the user's words contain this stage's gate word (a different stage's word, or a missing one, is refused),
  - the stage's checkpoint is awaiting_human (for the extra gates edit/compose also a legacy `completed` without approval),
  - every earlier stage is completed (and approved where the pipeline requires it),
and appends the quote to projects/<project>/approvals.jsonl. It cannot prove the user really said it - it only guarantees that an unfinished stage is
never approved and that the quoted word matches the stage. lib/checkpoint.py is not modified (edit and compose are extra gates it does not enforce)."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

STAGE_ORDER = ["research", "proposal", "script", "scene_plan", "assets", "edit", "compose", "publish"]
# stage -> (full gate sentence, tokens of which at least one must be in the user's words)
GATES = {
    "proposal": ("提案通过", ["提案通过"]),
    "script": ("脚本通过", ["脚本通过"]),
    "scene_plan": ("场景计划通过", ["场景计划通过"]),
    "assets": ("素材通过", ["素材通过"]),
    "edit": ("样片通过，开始合成", ["样片通过", "开始合成"]),
    "compose": ("成片通过，进入发布阶段", ["成片通过", "进入发布阶段"]),
    "publish": ("发布通过", ["发布通过"]),
}
EXTRA_GATES = ("edit", "compose")          # the pipeline manifest does not gate these; the series does
RECORD_ONLY = {"plan": "计划确认", "sample": "样音通过"}


def _checkpoint_api():
    os.chdir(ROOT)
    from lib import checkpoint
    return checkpoint


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(pdir, pid, stage):
    path = Path(pdir) / pid / f"checkpoint_{stage}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def stage_state(cp, stage):
    """('missing'|'in_progress'|'awaiting'|'approved'|'done_unapproved'|'completed', text)."""
    if cp is None:
        return "missing"
    st, appr = cp.get("status"), bool(cp.get("human_approved"))
    if st == "awaiting_human":
        return "awaiting"
    if st == "completed":
        if stage in GATES and appr:
            return "approved"
        if stage in EXTRA_GATES and not appr:
            return "done_unapproved"          # legacy flow: written completed before the user said the word
        return "completed"
    return st or "in_progress"


def pending(cp, stage):
    s = stage_state(cp, stage)
    return s in ("awaiting", "done_unapproved")


def _is_experiment(pdir, name):
    """A project folder that holds an EXPERIMENT.md is a technical test, not a lesson: it is listed apart and never counted as a published lesson."""
    return (Path(pdir) / name / "EXPERIMENT.md").exists()


def cmd_status(args):
    pdir = Path(args.projects)
    from whiteboard_lessons import lesson_table
    table = lesson_table()
    rows = []
    for d in sorted(p for p in pdir.iterdir() if p.is_dir() and (p / "project.json").exists()):
        cps = {s: _load(pdir, d.name, s) for s in STAGE_ORDER}
        if not any(cps.values()):
            continue
        done = stage_state(cps["publish"], "publish") == "approved"
        rows.append((d.name, cps, done))
    exp = {r[0] for r in rows if _is_experiment(pdir, r[0])}
    lessons = [r for r in rows if r[0] not in exp]
    active = [r for r in rows if not r[2]]
    if args.all:
        for name, cps, done in rows:
            n, t = table.get(name, (None, name))
            print(f"{'试验品' if name in exp else '第%s课' % n if n else '-':>6} {t}  {name}  {'发布已通过' if done else '进行中'}")
        print(f"共 {len(rows)} 个项目（其中试验品 {len(exp)} 个，不属于课程），{len(active)} 个进行中")
        return 0
    if not active:
        last = max(lessons, key=lambda r: (r[1]["publish"] or {}).get("timestamp", "")) if lessons else None
        print("没有进行中的课程；下一课由用户另定（用户说“继续策划下一课”或给题目）。")
        if last:
            n, t = table.get(last[0], (None, last[0]))
            print(f"最近发布：{'第%s课' % n if n else ''}《{t}》（{last[0]}）{(last[1]['publish'] or {}).get('timestamp', '')[:19]}")
        print(f"已发布 {len(lessons)} 课。")
        if exp:
            print(f"另有试验品 {len(exp)} 个（技术测试，不属于课程，不计入课数）：{'、'.join(sorted(exp))}")
        return 0
    for name, cps, _ in active:
        n, t = table.get(name, (None, name))
        print(f"进行中：{'试验品（不属于课程）' if name in exp else '第%s课' % n if n else ''}《{t}》（{name}）")
        nxt = None
        for s in STAGE_ORDER:
            state = stage_state(cps[s], s)
            who = ((cps[s] or {}).get("metadata") or {}).get("approved_by_user", "")
            print(f"  {s:11s} {state}{('  ← ' + who) if who else ''}")
            if nxt is None and state not in ("approved", "completed"):
                nxt = (s, state)
        if nxt:
            s, state = nxt
            if state in ("awaiting", "done_unapproved") and s in GATES:
                print(f"  下一步：等用户在对话里说“{GATES[s][0]}”（早说不算；说了之后用 approve 记录）")
            elif state == "missing":
                print(f"  下一步：做 {s} 阶段（先读 docs/whiteboard/checklists/）")
            else:
                print(f"  下一步：{s} 阶段进行中（{state}）")
        appr = Path(pdir) / name / "approvals.jsonl"
        if appr.exists():
            print(f"  已记录的口令：{sum(1 for _ in appr.open(encoding='utf-8'))} 条（{appr}）")
    return 0


def _append(pdir, pid, record):
    base = Path(pdir) / pid if (Path(pdir) / pid).is_dir() else Path(pdir)
    path = base / ("approvals.jsonl" if base.name == pid else "_approvals.jsonl")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def cmd_record(args):
    gate = RECORD_ONLY[args.gate]
    if gate not in args.words:
        print(f"拒绝：这一步要的口令是“{gate}”，收到的是“{args.words}”。")
        return 1
    pid = args.project if args.project != "-" else "_plan"
    path = _append(args.projects, pid, {"time": _now(), "project": pid, "stage": args.gate, "gate": gate, "said": args.words, "recorded_only": True})
    print(f"已记录“{gate}”（没有检查点，只追加记录）→ {path}")
    return 0


def cmd_approve(args):
    cpm = _checkpoint_api()
    pdir, pid, stage, words = Path(args.projects), args.project, args.stage, args.words
    if stage not in GATES:
        hint = "（样音通过、计划确认没有检查点，用 record）" if stage in RECORD_ONLY or stage == "sample" else ""
        print(f"拒绝：{stage} 不是需要批准的阶段；可选 {list(GATES)}。{hint}")
        return 1
    gate, tokens = GATES[stage]
    if not any(t in words for t in tokens):
        others = [s for s, (g, tk) in GATES.items() if s != stage and any(t in words for t in tk)]
        extra = f"（这句话对应的是 {others[0]} 阶段）" if others else ("（“样音通过”是样音门，用 record）" if "样音通过" in words else "")
        print(f"拒绝：{stage} 阶段要的口令是“{gate}”，收到的是“{words}”{extra}。")
        return 1
    cp = _load(pdir, pid, stage)
    if cp is None:
        print(f"拒绝：{pid} 没有 {stage} 阶段的检查点。")
        return 1
    state = stage_state(cp, stage)
    if state == "approved":
        print(f"拒绝：{stage} 已在 {cp.get('timestamp', '')[:19]} 批准过（approved_by_user={(cp.get('metadata') or {}).get('approved_by_user')}）——这是重复口令，先查检查点并如实说明，不往下走。")
        return 1
    if not pending(cp, stage):
        print(f"拒绝：{stage} 阶段现在是 {state}（status={cp.get('status')}），不在等待批准——步骤还没做完，早说的口令不算，做完并报告后请用户再说一次。")
        return 1
    for s in STAGE_ORDER[:STAGE_ORDER.index(stage)]:
        prev = _load(pdir, pid, s)
        ps = stage_state(prev, s)
        if ps not in ("approved", "completed", "done_unapproved"):
            print(f"拒绝：更早的阶段 {s} 还没完成（{ps}）。")
            return 1
        if s in GATES and s not in EXTRA_GATES and ps != "approved":
            print(f"拒绝：更早的门控阶段 {s} 没有批准记录。")
            return 1
    if args.dry_run:
        print(f"可以批准（dry-run，没有写入）：{pid} {stage}，等待自 {cp.get('timestamp', '')[:19]}，原话“{words}”。")
        return 0
    meta = dict(cp.get("metadata") or {})
    meta["approved_by_user"] = words
    path = cpm.write_checkpoint(pdir, pid, stage, "completed", cp["artifacts"], pipeline_type=cp.get("pipeline_type"), style_playbook=cp.get("style_playbook"),
                                checkpoint_policy=cp.get("checkpoint_policy", "guided"), human_approval_required=True, human_approved=True,
                                review=cp.get("review"), cost_snapshot=cp.get("cost_snapshot"), metadata=meta)
    new = json.loads(Path(path).read_text(encoding="utf-8"))
    rec = _append(pdir, pid, {"time": _now(), "project": pid, "stage": stage, "gate": gate, "said": words, "from_status": cp.get("status"),
                              "awaiting_since": cp.get("timestamp"), "checkpoint_timestamp": new.get("timestamp")})
    print(f"已批准：{pid} {stage} → completed（human_approved=True，approved_by_user=“{words}”）；记录 {rec}")
    print("现在停下，向用户汇报；不要在同一轮里做下一阶段。" if stage != "publish" else "发布已通过：写复盘（docs/whiteboard/retro-template.md），再等用户说“提交”。")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects", default=str(ROOT / "projects"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status"); s.add_argument("--all", action="store_true")
    a = sub.add_parser("approve"); a.add_argument("project"); a.add_argument("stage"); a.add_argument("words"); a.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("record"); r.add_argument("project"); r.add_argument("gate", choices=list(RECORD_ONLY)); r.add_argument("words")
    args = ap.parse_args()
    return {"status": cmd_status, "approve": cmd_approve, "record": cmd_record}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
