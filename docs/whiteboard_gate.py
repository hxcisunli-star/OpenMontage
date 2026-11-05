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
never approved and that the quoted word matches the stage. lib/checkpoint.py is not modified (edit and compose are extra gates it does not enforce).

托管 (delegation, user's choice 2026-11-03): the user may hand ONLY the text gates 计划确认 / 提案通过 / 脚本通过 / 场景计划通过 to an independent reviewer:
  delegate start <project> <plan|proposal|script|scene_plan> "<user's words, containing 托管>"   records the words and this session's CLAUDE_CODE_SESSION_ID
  delegate halt <project> "<reason>" | delegate stop <project> | delegate status [<project>]
  review <project> <stage> [--files F ...]     runs the stage's scripted checks, then a fresh read-only `claude -p --model opus` (run it in the BACKGROUND: up to 30 min)
                                               -> projects/<p>/review/gate-review-<stage>-<n>.json; at most 2 per gate, needs_human or a 2nd fail halts the delegation
  approve-by-review <project> <stage>          completed with metadata approval_kind=delegated_review (never approved_by_user) - only on a pass whose artifacts are unchanged
  record-by-review <project> plan              the same for 计划确认 (no checkpoint)
  stop-hook                                    Claude Code Stop hook: blocks the stop only for the delegating session while its delegation is active."""
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
            meta = (cps[s] or {}).get("metadata") or {}
            who = meta.get("approved_by_user", "")
            if not who and meta.get("approval_kind") == "delegated_review":
                who = f"评审放行（{(meta.get('approved_by_review') or {}).get('review_file', '')}；托管授权“{meta.get('delegated_by_user', '')}”）"
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
        dl = _dload(pdir, name)
        if dl:
            print(f"  托管：{dl['id']} {dl['status']}，到“{DELEGABLE_WORD[dl['upto']]}”为止" + (f"，停下原因：{dl['halt_reason']}" if dl.get("halt_reason") else ""))
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


# ---------------------------------------------------------------- 托管（delegation）: the user hands the text gates to an independent Opus reviewer
# Only these four gates can ever be delegated (hard-coded, so a model cannot widen the scope). 样音 / 素材 / 样片 / 成片 / 发布 / 提交 stay with the user.
DELEGABLE = ["plan", "proposal", "script", "scene_plan"]
DELEGABLE_WORD = {"plan": "计划确认", "proposal": "提案通过", "script": "脚本通过", "scene_plan": "场景计划通过"}
MAX_REVIEWS = 2                     # per gate and delegation: one review, one rework + re-review; a third is refused and halts
MAX_IDLE_NUDGES = 2                 # stop-hook: nudges in a row with no tool call in between before it halts
REVIEW_MODEL = "opus"
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail", "needs_human"]},
        "summary": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "object", "properties": {
            "severity": {"type": "string", "enum": ["blocking", "minor"]},
            "checklist_item": {"type": "string"}, "where": {"type": "string"}, "issue": {"type": "string"}, "quote": {"type": "string"}},
            "required": ["severity", "where", "issue", "quote"]}},
        "needs_human_reason": {"type": "string"},
    },
    "required": ["verdict", "summary", "findings"],
}
STAGE_CHECKLIST = {"plan": "01-plan.md", "proposal": "01-plan.md", "script": "02-script.md", "scene_plan": "03-scene-plan.md"}


def _dpath(pdir, pid):
    return Path(pdir) / pid / "delegation.json"


def _dload(pdir, pid):
    p = _dpath(pdir, pid)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _atomic_write(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _dsave(pdir, pid, d):
    _atomic_write(_dpath(pdir, pid), json.dumps(d, ensure_ascii=False, indent=1))


def _active_delegations(pdir):
    out = []
    for p in sorted(Path(pdir).glob("*/delegation.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("status") == "active":
            out.append((p.parent.name, d))
    return out


def _halt(pdir, pid, d, reason):
    d["status"], d["halt_reason"], d["halted_at"] = "halted", reason, _now()
    _dsave(pdir, pid, d)
    _append(pdir, pid, {"time": _now(), "project": pid, "delegation": d["id"], "event": "halt", "reason": reason})


def cmd_delegate(args):
    pdir = Path(args.projects)
    if args.action == "start":
        pid, upto, words = args.project, args.upto, args.words
        if upto not in DELEGABLE:
            print(f"拒绝：只能托管到 {DELEGABLE} 之一（计划确认、提案、脚本、场景计划）；样音、素材、样片、成片、发布、提交始终由用户自己说。收到的终点是“{upto}”。")
            return 1
        if "托管" not in words:
            print(f"拒绝：开启托管要用户的原话里带“托管”两个字，收到的是“{words}”。")
            return 1
        if not (pdir / pid / "project.json").exists():
            print(f"拒绝：{pid} 不是已建的课程项目（没有 project.json）。")
            return 1
        sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
        if not sid:
            print("拒绝：环境里没有 CLAUDE_CODE_SESSION_ID，认不出是哪个会话，Stop 钩子没法只管这一个会话。")
            return 1
        others = [p for p, _ in _active_delegations(pdir) if p != pid]
        if others:
            print(f"拒绝：{others[0]} 已在托管中；一次只托管一课。")
            return 1
        stages = DELEGABLE[:DELEGABLE.index(upto) + 1]
        d = {"id": datetime.now(timezone.utc).strftime("D%Y%m%dT%H%M%S"), "project": pid, "said": words, "upto": upto, "stages": stages,
             "session_id": sid, "status": "active", "started": _now(), "reviews": {}, "nudge": {}}
        _dsave(pdir, pid, d)
        _append(pdir, pid, {"time": _now(), "project": pid, "delegation": d["id"], "event": "start", "said": words, "upto": upto, "stages": stages, "session_id": sid})
        print(f"托管已开始 id={d['id']}：{pid}，交给 Opus 评审的门：{'、'.join(DELEGABLE_WORD[s] for s in stages)}（到“{DELEGABLE_WORD[upto]}”为止）。")
        print("每到这些门：先写 awaiting_human，再在后台跑 review，结论 pass 后 approve-by-review（计划确认用 record-by-review），然后不停，接着做下一阶段。")
        print("硬停点（评审 needs_human、两次评审没过、要超出已批准计划花钱或调外部接口、要改已批准的内容、被自动模式拦下、要提交或推送）：先 delegate halt 再停下等用户。")
        return 0
    if args.action == "status":
        rows = [(args.project, _dload(pdir, args.project))] if args.project else [(p.parent.name, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(pdir.glob("*/delegation.json"))]
        rows = [r for r in rows if r[1]]
        if not rows:
            print("没有托管记录。")
            return 0
        for pid, d in rows:
            print(f"{pid}：托管 {d['id']} 状态 {d['status']}，终点“{DELEGABLE_WORD[d['upto']]}”，用户原话“{d['said']}”，评审次数 {d.get('reviews', {})}"
                  + (f"，停下原因：{d.get('halt_reason')}" if d.get("halt_reason") else ""))
        return 0
    pid = args.project
    d = _dload(pdir, pid) if pid else None
    if not d:
        print(f"拒绝：{pid} 没有托管记录。")
        return 1
    if args.action == "halt":
        if d["status"] != "active":
            print(f"托管已是 {d['status']}，不用再停。")
            return 0
        _halt(pdir, pid, d, args.reason or "（没写原因）")
        print(f"托管已停下：{args.reason}。现在停下，向用户说明需要他定什么。")
        return 0
    if args.action == "stop":
        d["status"], d["stopped_at"] = "stopped", _now()
        _dsave(pdir, pid, d)
        _append(pdir, pid, {"time": _now(), "project": pid, "delegation": d["id"], "event": "stop", "said": args.reason or ""})
        print("托管已收回：以后的门照旧等用户自己说口令。")
        return 0
    return 1


def _fingerprint(pdir, pid, stage, files):
    """sha256 over what the reviewer saw: the stage checkpoint's artifacts (canonical JSON) plus every extra file named for the review."""
    import hashlib
    parts = {}
    cp = _load(pdir, pid, stage) if stage != "plan" else None
    if cp is not None:
        parts["checkpoint_artifacts"] = hashlib.sha256(json.dumps(cp.get("artifacts"), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    for f in files:
        p = Path(f)
        parts[str(f)] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"
    return parts


def _scripted_checks(pdir, pid, stage):
    """Real runs of the stage's scripted checks, so the read-only reviewer sees actual output, not a claim."""
    import subprocess
    cmds = []
    if stage == "script":
        lint = [sys.executable, str(ROOT / "docs/whiteboard_script_lint.py"), str(Path(pdir) / pid)]
        try:                                              # the checklist runs lint with --allow <this lesson's new terms>, declared in script.json lint_allow
            sj = json.loads((Path(pdir) / pid / "artifacts/script.json").read_text(encoding="utf-8"))
            allow = (sj.get("metadata") or {}).get("lint_allow") or sj.get("lint_allow") or []
        except (OSError, ValueError):
            allow = []
        if allow:
            lint += ["--allow", ",".join(allow)]
        cmds.append(lint)
        cmds.append([sys.executable, str(ROOT / "docs/whiteboard_callbacks.py"), str(Path(pdir) / pid)])
    out = []
    for c in cmds:
        r = subprocess.run(c, capture_output=True, text=True, cwd=ROOT, timeout=300)
        out.append({"command": " ".join(Path(x).name if i < 2 else x for i, x in enumerate(c)), "exit_code": r.returncode, "output": (r.stdout + r.stderr)[-6000:]})
    return out


def _review_prompt(pdir, pid, stage, files, checks, prior):
    cp_path = Path(pdir) / pid / f"checkpoint_{stage}.json"
    lines = [
        f"你是白板课《{pid}》“{DELEGABLE_WORD[stage]}”这一门的独立评审。用户事先授权：这一门由你代他判断能不能放行。做课的是另一个会话，你和它不是同一个模型调用；不要相信它对自己工作的描述，只看文件。",
        "只读文件（Read、Grep、Glob），不要试图运行命令、联网或改文件；不要读 .env 或任何密钥文件。",
        "",
        "## 要读的",
        "1. 协议：.claude/rules/whiteboard-protocol.md 与 .claude/rules/whiteboard-craft.md",
        f"2. 本阶段清单：docs/whiteboard/checklists/00-always.md 与 docs/whiteboard/checklists/{STAGE_CHECKLIST[stage]}（逐条对照，特别是“要人判断”那几条）",
        f"3. 被审的产物：{cp_path if stage != 'plan' else '（计划阶段没有检查点）'}" + "".join(f"\n   - {f}" for f in files),
        f"4. 同一课已批准的前序阶段：{Path(pdir) / pid}/checkpoint_*.json（status=completed 的）与 {Path(pdir) / pid}/approvals.jsonl",
        "",
        "## 脚本检查的真实输出（由评审脚本刚刚运行，不是做课会话的转述）",
    ]
    if checks:
        for c in checks:
            lines += [f"$ {c['command']}  (exit {c['exit_code']})", "```", c["output"], "```"]
    else:
        lines.append("本阶段没有由评审脚本自动运行的检查。清单里标着已有脚本拦的项，只能看产物里留下的运行记录；没有记录就当没跑。")
    if prior:
        lines += ["", "## 上一次评审（没过）的意见，看这次是否都改好了", "```json", json.dumps(prior, ensure_ascii=False, indent=1)[:8000], "```"]
    lines += [
        "",
        "## 怎么判",
        "- pass：清单每一条都满足，或只有不影响学生理解与事实正确的小问题（severity=minor）。",
        "- fail：有任何 blocking 问题：事实错、与已批准的计划或提案矛盾、违反协议或清单、旁白规则不满足、脚本检查报 ERROR、引用的数据找不到出处。",
        "- needs_human：这件事不该由评审代定——要额外花钱或调外部接口、要改已经批准的内容、系列名或课名这类只有用户能拍板的取舍、你读不到判断所需的文件。写清 needs_human_reason。",
        "- 每条意见的 quote 必须是你在文件里逐字看到的原文（不超过 120 字），where 写文件路径与位置。没有原文支撑的意见不要写。",
        "- 不要因为“可以更好”就 fail；只拦会让成片出错或违反规则的问题。",
        "最终只输出符合给定 JSON Schema 的对象。",
    ]
    return "\n".join(lines)


def _review_command():
    """Default reviewer: a fresh read-only Claude Opus run. WB_GATE_REVIEW_CMD (a shell command reading the prompt on stdin, printing the JSON) replaces it in tests."""
    fake = os.environ.get("WB_GATE_REVIEW_CMD")
    if fake:
        return fake, True
    return ["claude", "-p", "--model", REVIEW_MODEL, "--effort", "xhigh", "--tools", "Read,Grep,Glob",
            "--disallowedTools", "Read(./.env)", "Read(./.env.*)", "Bash", "Edit", "Write", "WebFetch", "WebSearch",
            "--no-session-persistence", "--output-format", "json", "--json-schema", json.dumps(REVIEW_SCHEMA)], False


def _parse_review(stdout):
    data = json.loads(stdout)
    if isinstance(data, dict) and "verdict" not in data:
        if isinstance(data.get("structured_output"), dict):
            data = data["structured_output"]
        elif isinstance(data.get("result"), str):
            txt = data["result"]
            data = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    if not isinstance(data, dict) or data.get("verdict") not in ("pass", "fail", "needs_human"):
        raise ValueError(f"no valid verdict in reviewer output: {str(data)[:200]}")
    return data


def cmd_review(args):
    import subprocess
    pdir, pid, stage = Path(args.projects), args.project, args.stage
    d = _dload(pdir, pid)
    if not d or d.get("status") != "active":
        print(f"拒绝：{pid} 没有进行中的托管（{(d or {}).get('status', '没有记录')}）。")
        return 1
    if stage not in d["stages"]:
        print(f"拒绝：{stage} 不在这次托管的范围 {d['stages']} 里。")
        return 1
    if stage != "plan":
        cp = _load(pdir, pid, stage)
        if cp is None or stage_state(cp, stage) != "awaiting":
            print(f"拒绝：{stage} 阶段现在是 {stage_state(cp, stage)}，要先做完并写 awaiting_human 再评审。")
            return 1
    elif not args.files:
        print("拒绝：计划确认的评审要用 --files 指出计划文件（计划页、计划文档）。")
        return 1
    n = int(d.get("reviews", {}).get(stage, 0)) + 1
    if n > MAX_REVIEWS:
        _halt(pdir, pid, d, f"{DELEGABLE_WORD[stage]}已评审 {MAX_REVIEWS} 次仍没过")
        print(f"拒绝：{stage} 已评审 {MAX_REVIEWS} 次，托管已停下，等用户定。")
        return 1
    files = [str(Path(f).resolve()) for f in (args.files or [])]
    rdir = pdir / pid / "review"
    rdir.mkdir(parents=True, exist_ok=True)
    prior = None
    if n > 1:
        pp = rdir / f"gate-review-{stage}-{n - 1}.json"
        prior = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else None
    checks = _scripted_checks(pdir, pid, stage)
    prompt = _review_prompt(pdir, pid, stage, files, checks, prior and {k: prior.get(k) for k in ("verdict", "summary", "findings")})
    (rdir / f"gate-review-{stage}-{n}.prompt.md").write_text(prompt, encoding="utf-8")
    fp_before = _fingerprint(pdir, pid, stage, files)
    cmd, shell = _review_command()
    env = dict(os.environ, WB_GATE_REVIEWER="1")
    t0 = datetime.now(timezone.utc)
    d.setdefault("reviews", {})[stage] = n            # counted before the run, so a crashed run still uses up a try
    _dsave(pdir, pid, d)
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=ROOT, env=env, shell=shell, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print(f"评审超时（{args.timeout} 秒）没有结论；这次算用掉一次评审。")
        return 1
    secs = (datetime.now(timezone.utc) - t0).total_seconds()
    (rdir / f"gate-review-{stage}-{n}.raw.txt").write_text(r.stdout + ("\n--- stderr ---\n" + r.stderr if r.stderr else ""), encoding="utf-8")
    try:
        v = _parse_review(r.stdout)
    except (ValueError, KeyError, TypeError) as e:
        print(f"评审没有给出可用结论（exit {r.returncode}，{e}）；原始输出在 {rdir / f'gate-review-{stage}-{n}.raw.txt'}。这次算用掉一次评审。")
        return 1
    if _fingerprint(pdir, pid, stage, files) != fp_before:
        print("拒绝：评审运行期间产物被改过，这次结论作废，改完再评审。")
        return 1
    usage = {}
    try:
        meta = json.loads(r.stdout)
        usage = {k: meta.get(k) for k in ("total_cost_usd", "num_turns", "duration_ms", "session_id") if isinstance(meta, dict) and k in meta}
    except ValueError:
        pass
    rec = {"project": pid, "stage": stage, "gate": DELEGABLE_WORD[stage], "n": n, "time": _now(), "seconds": round(secs, 1), "delegation": d["id"],
           "reviewer": "fake" if shell else f"claude -p --model {REVIEW_MODEL}", "verdict": v["verdict"], "summary": v.get("summary", ""),
           "findings": v.get("findings", []), "needs_human_reason": v.get("needs_human_reason", ""), "files": files, "fingerprint": fp_before,
           "scripted_checks": checks, "prompt_file": f"gate-review-{stage}-{n}.prompt.md", "usage": usage}
    out = rdir / f"gate-review-{stage}-{n}.json"
    _atomic_write(out, json.dumps(rec, ensure_ascii=False, indent=1))
    blocking = [f for f in rec["findings"] if f.get("severity") == "blocking"]
    print(f"评审结论：{v['verdict']}（第 {n} 次，{secs:.0f} 秒，blocking {len(blocking)} 条，minor {len(rec['findings']) - len(blocking)} 条）→ {out}")
    print(f"  {rec['summary'][:300]}")
    if v["verdict"] == "pass":
        print(f"下一步：{'record-by-review ' + pid + ' plan' if stage == 'plan' else 'approve-by-review ' + pid + ' ' + stage}（评审之后不要再改产物，否则要重审）。")
    elif v["verdict"] == "needs_human":
        _halt(pdir, pid, _dload(pdir, pid), f"评审认为要用户定：{rec['needs_human_reason'] or rec['summary'][:200]}")
        print("评审认为这件事要用户定：托管已停下。现在停下，向用户说明。")
    elif n >= MAX_REVIEWS:
        _halt(pdir, pid, _dload(pdir, pid), f"{DELEGABLE_WORD[stage]}评审 {n} 次仍没过")
        print(f"已评审 {n} 次仍没过：托管已停下。现在停下，向用户报告评审意见。")
    else:
        print("没过：按 blocking 意见改一轮（只改被指出的问题），重写 awaiting_human 检查点，再评审一次。")
    return 0


def _latest_review(pdir, pid, stage, d):
    n = int(d.get("reviews", {}).get(stage, 0))
    p = Path(pdir) / pid / "review" / f"gate-review-{stage}-{n}.json"
    if n == 0 or not p.exists():
        return None, p
    rv = json.loads(p.read_text(encoding="utf-8"))
    return (rv if rv.get("delegation") == d["id"] else None), p


def _check_review_ok(pdir, pid, stage):
    d = _dload(pdir, pid)
    if not d or d.get("status") != "active":
        return None, None, f"{pid} 没有进行中的托管（{(d or {}).get('status', '没有记录')}）"
    if stage not in d["stages"]:
        return None, None, f"{stage} 不在这次托管的范围 {d['stages']} 里"
    rv, p = _latest_review(pdir, pid, stage, d)
    if rv is None:
        return None, None, f"{stage} 在这次托管里还没有评审结论"
    if rv["verdict"] != "pass":
        return None, None, f"最近一次评审（{p.name}）结论是 {rv['verdict']}，不是 pass"
    if _fingerprint(pdir, pid, stage, rv.get("files", [])) != rv.get("fingerprint"):
        return None, None, f"评审（{p.name}）之后产物被改过，要重新评审"
    return d, (rv, p), ""


def _after_gate(pdir, pid, d, stage):
    if stage == d["upto"]:
        d["status"], d["finished_at"] = "finished", _now()
        _dsave(pdir, pid, d)
        _append(pdir, pid, {"time": _now(), "project": pid, "delegation": d["id"], "event": "finished", "upto": stage})
        print(f"托管到终点了（{DELEGABLE_WORD[stage]}）：现在停下，向用户汇报；下一个门由用户自己说口令。")
    else:
        print("托管中：不要停，接着做下一阶段（先读该阶段清单）。")


def cmd_approve_by_review(args):
    pdir, pid, stage = Path(args.projects), args.project, args.stage
    if stage not in GATES or stage not in DELEGABLE:
        print(f"拒绝：{stage} 不能由评审放行（只有 {[s for s in DELEGABLE if s in GATES]}；计划确认用 record-by-review）。")
        return 1
    d, got, why = _check_review_ok(pdir, pid, stage)
    if not d:
        print(f"拒绝：{why}。")
        return 1
    rv, rp = got
    cp = _load(pdir, pid, stage)
    if cp is None or not pending(cp, stage) or stage_state(cp, stage) == "approved":
        print(f"拒绝：{stage} 阶段现在是 {stage_state(cp, stage)}，不在等待批准。")
        return 1
    for s in STAGE_ORDER[:STAGE_ORDER.index(stage)]:
        ps = stage_state(_load(pdir, pid, s), s)
        if ps not in ("approved", "completed", "done_unapproved"):
            print(f"拒绝：更早的阶段 {s} 还没完成（{ps}）。")
            return 1
        if s in GATES and s not in EXTRA_GATES and ps != "approved":
            print(f"拒绝：更早的门控阶段 {s} 没有批准记录。")
            return 1
    cpm = _checkpoint_api()
    meta = dict(cp.get("metadata") or {})
    meta.pop("approved_by_user", None)
    meta["approval_kind"] = "delegated_review"
    meta["approved_by_review"] = {"reviewer": rv["reviewer"], "review_file": rp.name, "verdict": rv["verdict"], "time": rv["time"]}
    meta["delegated_by_user"] = d["said"]
    meta["delegation_id"] = d["id"]
    # human_approved=True is what lib/checkpoint requires for a gated stage; the human approval is the user's advance delegation (delegated_by_user), the decision is the reviewer's.
    path = cpm.write_checkpoint(pdir, pid, stage, "completed", cp["artifacts"], pipeline_type=cp.get("pipeline_type"), style_playbook=cp.get("style_playbook"),
                                checkpoint_policy=cp.get("checkpoint_policy", "guided"), human_approval_required=True, human_approved=True,
                                review=cp.get("review"), cost_snapshot=cp.get("cost_snapshot"), metadata=meta)
    new = json.loads(Path(path).read_text(encoding="utf-8"))
    rec = _append(pdir, pid, {"time": _now(), "project": pid, "stage": stage, "gate": GATES[stage][0], "by": "review", "reviewer": rv["reviewer"],
                              "review_file": rp.name, "delegated_by_user": d["said"], "delegation": d["id"], "from_status": cp.get("status"),
                              "awaiting_since": cp.get("timestamp"), "checkpoint_timestamp": new.get("timestamp")})
    print(f"评审放行：{pid} {stage} → completed（approval_kind=delegated_review，评审 {rp.name}；用户事先授权“{d['said']}”）；记录 {rec}")
    _after_gate(pdir, pid, _dload(pdir, pid), stage)
    return 0


def cmd_record_by_review(args):
    pdir, pid = Path(args.projects), args.project
    d, got, why = _check_review_ok(pdir, pid, "plan")
    if not d:
        print(f"拒绝：{why}。")
        return 1
    rv, rp = got
    ap = Path(pdir) / pid / "approvals.jsonl"
    done = [json.loads(x) for x in ap.read_text(encoding="utf-8").splitlines() if x.strip()] if ap.exists() else []
    if any(x.get("stage") == "plan" and x.get("delegation") == d["id"] for x in done):
        print("拒绝：这次托管里计划确认已记录过。")
        return 1
    rec = _append(pdir, pid, {"time": _now(), "project": pid, "stage": "plan", "gate": "计划确认", "by": "review", "reviewer": rv["reviewer"], "review_file": rp.name,
                              "delegated_by_user": d["said"], "delegation": d["id"], "recorded_only": True})
    print(f"评审放行：计划确认（评审 {rp.name}）→ {rec}")
    _after_gate(pdir, pid, _dload(pdir, pid), "plan")
    return 0


def _count_tool_uses(transcript_path):
    n = 0
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                if '"tool_use"' not in line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("type") == "assistant":
                    n += sum(1 for b in ((o.get("message") or {}).get("content") or []) if isinstance(b, dict) and b.get("type") == "tool_use")
    except (OSError, TypeError):
        return -1
    return n


def cmd_stop_hook(args):
    """Claude Code Stop hook. Prints nothing (the turn may end) unless an active delegation belongs to THIS session and should go on; then prints a block decision.
    Any error lets the turn end (a broken hook must never trap a session)."""
    try:
        return _stop_hook(args)
    except Exception as e:                                # noqa: BLE001
        print(f"whiteboard stop-hook error, letting the turn end: {e}", file=sys.stderr)
        return 0


def _stop_hook(args):
    if os.environ.get("WB_GATE_REVIEWER"):
        return 0
    try:
        hin = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    pdir = Path(args.projects)
    mine = [(p, d) for p, d in _active_delegations(pdir) if d.get("session_id") and d.get("session_id") == hin.get("session_id")]
    if not mine:
        return 0
    if hin.get("background_tasks"):
        return 0                                         # background work will wake the session up by itself
    pid, d = mine[0]
    total = _count_tool_uses(hin.get("transcript_path", ""))
    nd = d.setdefault("nudge", {})
    idle = nd.get("idle", 0) + 1 if (total >= 0 and nd.get("tool_uses") == total) else 0
    if idle >= MAX_IDLE_NUDGES:
        _halt(pdir, pid, d, f"Stop 钩子催了以后，连续 {idle} 次停下前都没调用工具")
        return 0
    nd.update({"tool_uses": total, "idle": idle, "time": _now(), "count": nd.get("count", 0) + 1})
    _dsave(pdir, pid, d)
    where = "全部阶段已完成"
    for s in STAGE_ORDER:
        st = stage_state(_load(pdir, pid, s), s)
        if st not in ("approved", "completed"):
            where = f"{s}/{st}"
            break
    reason = (f"托管中（{d['id']}，到“{DELEGABLE_WORD[d['upto']]}”为止）：{pid} 现在在 {where}。不要停，按该阶段清单继续做；"
              f"到委托的门先写 awaiting_human，再在后台跑 `.venv/bin/python docs/whiteboard_gate.py review {pid} <阶段>`，pass 后 approve-by-review。"
              f"真碰到需要用户定的事（硬停点），先 `.venv/bin/python docs/whiteboard_gate.py delegate halt {pid} \"<原因>\"` 再停。"
              + ("（上次催促之后你没有调用任何工具；再这样一次，托管会自动停下。）" if idle else ""))
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects", default=str(ROOT / "projects"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status"); s.add_argument("--all", action="store_true")
    a = sub.add_parser("approve"); a.add_argument("project"); a.add_argument("stage"); a.add_argument("words"); a.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("record"); r.add_argument("project"); r.add_argument("gate", choices=list(RECORD_ONLY)); r.add_argument("words")
    dg = sub.add_parser("delegate"); dg.add_argument("action", choices=["start", "halt", "stop", "status"]); dg.add_argument("project", nargs="?")
    dg.add_argument("rest", nargs="*")
    rv = sub.add_parser("review"); rv.add_argument("project"); rv.add_argument("stage", choices=DELEGABLE); rv.add_argument("--files", nargs="*", default=[])
    rv.add_argument("--timeout", type=int, default=1800)
    ab = sub.add_parser("approve-by-review"); ab.add_argument("project"); ab.add_argument("stage")
    rb = sub.add_parser("record-by-review"); rb.add_argument("project"); rb.add_argument("gate", choices=["plan"])
    sub.add_parser("stop-hook")
    args = ap.parse_args()
    if args.cmd == "delegate":
        if args.action == "start":
            if len(args.rest) != 2:
                ap.error("delegate start <project> <upto-stage> \"<user's words>\"")
            args.upto, args.words = args.rest
        else:
            args.reason = " ".join(args.rest)
    return {"status": cmd_status, "approve": cmd_approve, "record": cmd_record, "delegate": cmd_delegate, "review": cmd_review,
            "approve-by-review": cmd_approve_by_review, "record-by-review": cmd_record_by_review, "stop-hook": cmd_stop_hook}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
