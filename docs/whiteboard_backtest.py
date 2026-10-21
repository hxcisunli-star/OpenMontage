#!/usr/bin/env python3
"""Backtests for the whiteboard tools: every check must flag a KNOWN past case and pass the lessons that were fine - a check that has never caught anything has not been shown to work.
Run (repo root):  .venv/bin/python docs/whiteboard_backtest.py [--slow]        exit code 1 if any test fails
Fast tests (seconds) use the published lessons' own data, never modify them (scratch copies in a temp dir); --slow also runs the full compose verifier on a scratch copy of
lesson 43's final video (about 40 s) and checks its numbers against the ones typed by hand in 2026-10 (414.967 s, 12449 frames, -16.0 LUFS, silences, md5), and runs the measured layout
probe (docs/whiteboard_layout_check.py) on a cut of lesson 42 with and without a seeded overlap (about 1 minute).
A test that needs a published lesson's files is skipped (not failed) when they are missing."""
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
PY = str(ROOT / ".venv/bin/python")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def sh(*cmd, **kw):
    return subprocess.run(list(map(str, cmd)), capture_output=True, text=True, cwd=ROOT, **kw)


def have(*rel):
    return all((ROOT / r).exists() for r in rel)


def t_last_item():
    from whiteboard_boardtime import board_rows
    from whiteboard_lessons import lesson_table
    for proj, n in (("c-caller-cn", 41), ("c-record-cn", 42), ("c-clinic-cn", 43)):
        rows = board_rows(ROOT / "projects" / proj)
        m = min(r["margin"] for r in rows)
        check(f"last_item: lesson {n} passes (min margin >= 0.6)", m >= 0.6, f"min margin {m:.2f}")
    rows = {r["id"]: r for r in board_rows(ROOT / "projects/c-stack-cn")}
    r = rows["K6"]
    check("last_item: lesson 18 K6 is flagged and only ~46% drawn at the board end", r["margin"] < -1.5 and 0.4 < r["progress_at_end"] < 0.5, f"margin {r['margin']:.2f}, drawn {r['progress_at_end']:.0%}")
    neg = 0
    for proj, (n, _t) in lesson_table().items():
        if n <= 40 and (ROOT / "projects" / proj / "artifacts/whiteboard_scenes.json").exists():
            neg += min(x["margin"] for x in board_rows(ROOT / "projects" / proj)) < 0
    check("last_item: 30 of lessons 1-40 have a board that fades before its last item is written (the finding of 2026-10-19)", neg == 30, f"{neg} lessons")


def t_thumb():
    for t, want in ((162.5, 1), (164.2, 0)):
        r = sh("python3", "docs/whiteboard_thumb_check.py", "projects/c-queue-cn", t)
        check(f"thumb_check: lesson 27 at {t}s -> {'FAIL' if want else 'OK'} (the 2026-10 take 1 / take 2)", r.returncode == want, r.stdout.strip()[:70])
    r = sh("python3", "docs/whiteboard_thumb_check.py", "projects/c-clinic-cn", "142.0")
    check("thumb_check: lesson 43 at 142.0s is OK", r.returncode == 0, r.stdout.strip()[:70])


def t_script_lint():
    import whiteboard_script_lint as L
    from whiteboard_lessons import lesson_table
    bad = []
    for proj, (n, _t) in lesson_table().items():
        sj = ROOT / "projects" / proj / "artifacts/script.json"
        if sj.exists():
            e, _w, _i = L.lint(json.loads(sj.read_text(encoding="utf-8")), n)
            if e:
                bad.append((n, e[0][:60]))
    check("script_lint: all published scripts of lessons 11-43 have 0 errors", not bad, str(bad[:3]))
    base = json.loads((ROOT / "projects/c-clinic-cn/artifacts/script.json").read_text(encoding="utf-8"))

    def mut(name, fn, expect):
        s = copy.deepcopy(base)
        fn(s)
        e, w, _i = L.lint(s, 43)
        check(f"script_lint mutation caught: {name}", any(expect in x for x in e + w))

    mut("an Arabic digit", lambda s: s["sections"][0].__setitem__("text", s["sections"][0]["text"] + "第5条。"), "Arabic digit")
    mut("an English word", lambda s: s["sections"][0].__setitem__("text", s["sections"][0]["text"] + "用gcc编译。"), "English letters")
    mut("a hard word (折半)", lambda s: s["sections"][2].__setitem__("text", s["sections"][2]["text"] + "这里用折半。"), "hard word")
    mut("a 87-character sentence", lambda s: s["sections"][3].__setitem__("text", s["sections"][3]["text"] + "，".join(["这是一句很长很长的话"] * 8) + "。"), "longest sentence")

    def gap(s):
        s["sections"][1]["enhancement_cues"][-1]["timestamp_seconds"] += 14
    mut("picture cues 14 s further apart", gap, "picture cues")
    mut("the quiz question twice", lambda s: s["sections"][1].__setitem__("text", s["sections"][1]["text"] + "挂号八号，打印什么？"), "appears 2 times")
    mut("a section over 600 characters", lambda s: s["sections"][1].__setitem__("text", s["sections"][1]["text"] + "补充说明一些内容，" * 60), "has")

    def double(s):
        for sec in s["sections"]:
            sec["text"] *= 2
    mut("duration out of range", double, "outside 360-480")
    e, _w, _i = L.lint(base, 43, allow=["折半"])
    s2 = copy.deepcopy(base)
    s2["sections"][2]["text"] += "这里用折半。"
    e2, _w2, _i2 = L.lint(s2, 43, allow=["折半"])
    check("script_lint: --allow lets this lesson's new term through", not any("折半" in x for x in e2))


def t_lint_mixed():
    import whiteboard_lint as W
    def props(text, font=None):
        it = {"kind": "write", "text": text, "x": 100, "y": 100, "at": 1.0, "dur": 1.0, "size": 40}
        if font:
            it["font"] = font
        return {"cuts": [{"id": "K1", "in_seconds": 0, "whiteboard": {"items": [it]}}]}
    e, w = W.lint_props(props("文件 list.txt 有三行"))
    check("lint: file name next to Chinese in the hand font is warned (lesson 40)", any("mixed into a CJK hand-font" in x for x in w), str(w[:1]))
    e, w = W.lint_props(props("文件有三行"))
    check("lint: plain Chinese hand text is quiet", not w and not e)
    e, w = W.lint_props(props("list.txt", font="mono"))
    check("lint: the same name in mono is quiet", not w and not e)
    e, w = W.lint_props(props("第一个是 0"))
    check("lint: a 0 in the hand font is still an error", bool(e))


def t_callbacks():
    r = sh("python3", "docs/whiteboard_callbacks.py", "projects/c-clinic-cn")
    out = r.stdout
    s6 = out[out.find("## s6 → 第40课"):]
    s6 = s6[:s6.find("\n## ", 5)]
    check("callbacks: lesson 43 s6 -> lesson 40 shows the 'not three' and 'not two' sentences side by side", "不是三" in s6 and "个数不是二" in s6, "candidates listed")
    check("callbacks: finds all 7 callbacks of lesson 43", "共 7 处" in out)
    # a later series says a bare "第二课" and means the C course: it must resolve there, must not be called a forward reference when the new lesson is numbered 1, and must show the quoted sentence
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "agent-demo-cn" / "artifacts"
        d.mkdir(parents=True)
        (d / "script.json").write_text(json.dumps({"sections": [{"id": "s1", "text": "第二课里说过：过门的是克隆体，也就是副本。今天也有一扇门。"}]}, ensure_ascii=False), encoding="utf-8")
        r = sh("python3", "docs/whiteboard_callbacks.py", Path(td) / "agent-demo-cn", "--lesson", "1")
    o = r.stdout
    check("callbacks: a callback from the agent series resolves to the C course, is not flagged as a forward reference, and lists lesson 2's quoted sentence",
          "智能体篇" in o and "本课是第" not in o and "- ⚠" not in o and "过门的是克隆体，也就是副本，手术只改副本，本人不变" in o, o.strip().splitlines()[0] if o.strip() else r.stderr[-120:])


def t_gate():
    if not have("projects/c-clinic-cn/checkpoint_script.json"):
        print("SKIP gate (no lesson 43 checkpoints)")
        return
    tmp = Path(tempfile.mkdtemp())
    try:
        P = tmp / "projects/c-clinic-cn"
        P.mkdir(parents=True)
        S = ROOT / "projects/c-clinic-cn"
        for f in list(S.glob("checkpoint_*.json")) + [S / "project.json", S / "decision_log.json"]:
            shutil.copy2(f, P / f.name)
        for st, status, appr in (("script", "awaiting_human", False), ("scene_plan", "awaiting_human", False), ("assets", "awaiting_human", False), ("edit", "awaiting_human", False),
                                 ("compose", "completed", False), ("publish", "awaiting_human", False)):
            p = P / f"checkpoint_{st}.json"
            c = json.loads(p.read_text(encoding="utf-8"))
            c["status"], c["human_approved"] = status, appr
            c.get("metadata", {}).pop("approved_by_user", None)
            p.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
        g = lambda *a: sh(PY, "docs/whiteboard_gate.py", "--projects", tmp / "projects", *a)  # noqa: E731
        check("gate: assets cannot be approved while script is still waiting", g("approve", "c-clinic-cn", "assets", "素材通过").returncode == 1)
        check("gate: another stage's word is refused", g("approve", "c-clinic-cn", "script", "场景计划通过").returncode == 1)
        check("gate: the sample-voice word is refused for a stage", g("approve", "c-clinic-cn", "script", "样音通过").returncode == 1)
        check("gate: dry-run writes nothing", g("approve", "c-clinic-cn", "script", "脚本通过", "--dry-run").returncode == 0 and json.loads((P / "checkpoint_script.json").read_text(encoding="utf-8"))["status"] == "awaiting_human")
        r = g("approve", "c-clinic-cn", "script", "脚本通过")
        c = json.loads((P / "checkpoint_script.json").read_text(encoding="utf-8"))
        check("gate: the right word on a waiting stage completes it with approved_by_user", r.returncode == 0 and c["status"] == "completed" and c["human_approved"] and c["metadata"]["approved_by_user"] == "脚本通过")
        check("gate: the same word again is refused as a repeat", g("approve", "c-clinic-cn", "script", "脚本通过").returncode == 1)
        ok = all(g("approve", "c-clinic-cn", st, w).returncode == 0 for st, w in (("scene_plan", "场景计划通过"), ("assets", "素材通过"), ("edit", "样片通过，开始合成")))
        check("gate: the next gates follow in order", ok)
        check("gate: a compose written 'completed' before approval (old flow) accepts the bare word 进入发布阶段", g("approve", "c-clinic-cn", "compose", "进入发布阶段").returncode == 0)
        check("gate: record-only gates (样音通过) need the right word", g("record", "c-clinic-cn", "sample", "样音通过").returncode == 0 and g("record", "c-clinic-cn", "sample", "好的").returncode == 1)
        lines = (P / "approvals.jsonl").read_text(encoding="utf-8").splitlines()
        check("gate: every approval was appended to approvals.jsonl", len(lines) == 6, f"{len(lines)} lines")
        st = g("status").stdout
        check("gate: status names the next gate", "发布通过" in st)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    r = sh(PY, "docs/whiteboard_gate.py", "status")
    # depends on what is going on in the real projects folder: either nothing is in progress, or the status names the lesson, its stage and the gate word it waits for
    check("gate: status on the real projects either says nothing is in progress or names the next gate word", r.returncode == 0 and ("没有进行中的课程" in r.stdout or "下一步：等用户在对话里说" in r.stdout), r.stdout.strip().splitlines()[-1][:80] if r.stdout.strip() else "")


def t_gate_experiment():
    """A project folder with an EXPERIMENT.md is a technical test, not a lesson: status never counts it as a published lesson or names it as the latest lesson (2026-10-21: the first
    experiment, agent-messages-cn, was counted as lesson 44 the moment its publish gate was approved)."""
    tmp = Path(tempfile.mkdtemp())
    try:
        def proj(name, ts, experiment):
            d = tmp / "projects" / name
            d.mkdir(parents=True)
            (d / "project.json").write_text("{}", encoding="utf-8")
            (d / "checkpoint_publish.json").write_text(json.dumps({"status": "completed", "human_approved": True, "timestamp": ts, "metadata": {"approved_by_user": "发布通过"}}), encoding="utf-8")
            if experiment:
                (d / "EXPERIMENT.md").write_text("experiment", encoding="utf-8")
        proj("c-demo-cn", "2026-10-19T00:00:00", False)
        proj("agent-test-cn", "2026-10-21T00:00:00", True)      # the later one is the experiment
        out = sh(PY, "docs/whiteboard_gate.py", "--projects", tmp / "projects", "status").stdout
        check("gate: an experiment (EXPERIMENT.md) is not counted as a published lesson", "已发布 1 课" in out, out.strip().splitlines()[-2][:60])
        check("gate: the latest published lesson is the real lesson, not the later experiment", "c-demo-cn" in out.split("最近发布")[1].splitlines()[0])
        check("gate: the experiment is listed apart and named as not belonging to the course", "试验品 1 个" in out and "agent-test-cn" in out.split("另有试验品")[1] and "不属于课程" in out)
        out_all = sh(PY, "docs/whiteboard_gate.py", "--projects", tmp / "projects", "status", "--all").stdout
        check("gate: status --all labels the experiment 试验品", "试验品" in out_all and "agent-test-cn" in out_all)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_wait():
    tmp = Path(tempfile.mkdtemp())
    try:
        def w(text, *args):
            p = tmp / "x.log"
            p.write_text(text, encoding="utf-8")
            return sh("python3", "docs/whiteboard_wait.py", p, "--poll", "0.3", *args)
        check("wait: remote `success {` ends it", w('chunk ok\nsuccess {"operation": "chunked_render"}\n').returncode == 0)
        check("wait: Traceback is a failure", w("x\nTraceback (most recent call last):\n").returncode == 1)
        check("wait: `done in` alone ends it after the grace period", w("done in 5s (local)\n", "--grace", "1").returncode == 0)
        check("wait: falling back is not terminal (times out)", w("falling back to local rendering for ['K3']\n", "--timeout", "1").returncode == 2)
        if Path("/tmp/final43.log").exists():
            check("wait: the real lesson-43 remote log (the one the old until-grep never ended on) ends at once", sh("python3", "docs/whiteboard_wait.py", "/tmp/final43.log", "--poll", "0.3", "--timeout", "5").returncode == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_new_lesson():
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "projects").mkdir()
        (tmp / "projects/c-clinic-cn").symlink_to(ROOT / "projects/c-clinic-cn")
        r = sh(PY, "docs/whiteboard_new_lesson.py", "--pid", "c-backtest-cn", "--n", "44", "--title", "回测", "--projects-dir", tmp / "projects", "--from", "c-clinic-cn")
        sc = tmp / "projects/c-backtest-cn/scripts"
        check("new_lesson: scaffold ran and every .py compiles", r.returncode == 0 and (sc / "build_script.py").exists(), r.stdout[-80:].strip())
        left = [p.name for p in sc.iterdir() if p.suffix in (".py", ".sh") and "c-clinic-cn" in p.read_text(encoding="utf-8")]
        check("new_lesson: no source project name is left in the scripts", not left, str(left))
        check("new_lesson: render_stills.py points at the NEW project (the copy in 41-43 pointed at lesson 30)", "projects/c-backtest-cn" in (sc / "render_stills.py").read_text(encoding="utf-8"))
        check("new_lesson: rebuild_edit.sh runs last_item_check", "whiteboard_last_item_check.py projects/c-backtest-cn" in (sc / "rebuild_edit.sh").read_text(encoding="utf-8"))
        check("new_lesson: build_script.py reads the single wordlist", "wordlist.yaml" in (sc / "build_script.py").read_text(encoding="utf-8") and "LESSON = 44" in (sc / "build_script.py").read_text(encoding="utf-8"))
        r2 = sh(PY, "docs/whiteboard_new_lesson.py", "--pid", "c-backtest-cn", "--n", "44", "--title", "回测", "--projects-dir", tmp / "projects", "--from", "c-clinic-cn")
        check("new_lesson: refuses to touch an existing project", r2.returncode != 0)
        # the agent series: its own numbering from 1, its own wordlist
        r3 = sh(PY, "docs/whiteboard_new_lesson.py", "--pid", "agent-backtest-cn", "--n", "1", "--title", "回测", "--projects-dir", tmp / "projects", "--from", "c-clinic-cn")
        bs = (tmp / "projects/agent-backtest-cn/scripts/build_script.py")
        txt = bs.read_text(encoding="utf-8") if bs.exists() else ""
        check("new_lesson (agent series): scaffold runs, lesson 1 does not collide with C lesson 1, build_script.py reads series_terms.agent from lesson 1",
              r3.returncode == 0 and "LESSON = 1" in txt and 'get("series_terms", {}).get("agent", {})' in txt and 's.get("from", 1)' in txt, r3.stdout[-80:].strip())
        r4 = sh(PY, "docs/whiteboard_new_lesson.py", "--pid", "x-bad-cn", "--n", "1", "--title", "x", "--projects-dir", tmp / "projects", "--from", "c-clinic-cn")
        check("new_lesson: a project name outside the two series is refused", r4.returncode != 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_series():
    import whiteboard_lessons as WL
    import whiteboard_script_lint as SL
    check("series: agent-… is the agent series, c-… and bubble-sort-tutorial-cn are the C series",
          WL.series_of("agent-messages-cn") == "agent" and WL.series_of("projects/c-clinic-cn") == "c" and WL.series_of("bubble-sort-tutorial-cn") == "c")
    check("series: project_of(1) is still the C series' first lesson (existing callers unchanged)", WL.project_of(1) == "bubble-sort-tutorial-cn" and WL.project_of(43) == "c-clinic-cn")
    c, a = WL.load_terms("c"), WL.load_terms("agent")
    check("series: the two wordlists are separate (接口 is a C-series hard word from lesson 41 but a core word of the agent series)", "遍历" in c and "遍历" not in a and "接口" in c and "接口" not in a and "工具调用" in a)
    bad = {"sections": [{"id": "s1", "text": "这里写了 Python 和 3 个词。" * 5}], "metadata": {}}
    e_agent, _w, _i = SL.lint(bad, 1, series="agent")
    e_c, _w2, i_c = SL.lint(bad, 1)
    check("series: the agent series is checked from its first lesson (the C series' rules only start at lesson 11)", any("English letters" in x for x in e_agent) and not e_c and "not in force" in i_c.get("note", ""))
    hard = {"sections": [{"id": "s1", "text": "这次我们先讲工具调用。" * 20}], "metadata": {}}
    e1, _w3, _i3 = SL.lint(hard, 1, series="agent")
    e2, _w4, _i4 = SL.lint(hard, 1, allow=["工具调用"], series="agent")
    check("series: a hard word of the agent list is refused from lesson 1 and passes when listed as this lesson's new term", any("工具调用" in x for x in e1) and not any("工具调用" in x for x in e2))


def t_registry():
    r = sh(PY, "docs/whiteboard_registry.py", "coverage")
    check("registry: every playbook row and handoff note clause is mapped (0 unmapped)", r.returncode == 0 and "未映射共 0 条" in r.stdout)
    r = sh(PY, "docs/whiteboard_registry.py", "check")
    check("registry: stage checklists match the registry", r.returncode == 0)


def _payload(items=None, overlays=None):
    return {"frame": 90, "scene": "whiteboard", "board": [28, 28, 1892, 1052], "items": items or [], "overlays": overlays or []}


def _txt(text, box, font="hand", lines=1, opacity=1.0, reveal=1.0):
    return {"text": text, "font": font, "size": 40, "lines": lines, "box": box, "rects": [box], "opacity": opacity, "reveal": reveal}


def _item(layer, idx, texts=(), shapes=()):
    return {"layer": layer, "idx": idx, "tag": "div", "texts": list(texts), "shapes": list(shapes)}


def _stroke(pts, sub=None, closed=False, fill=None, width=6):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {"kind": "path", "box": [min(xs), min(ys), max(xs), max(ys)], "pts": pts, "sub": sub or [0] * len(pts), "closed": closed, "stroked": True, "filled": False,
            "width": width, "opacity": 1.0, "reveal": 1.0, "fill": fill}


def t_layout_rules():
    import whiteboard_layout_rules as L
    import whiteboard_layout_check as C
    rule = lambda p, name: [f for f in L.frame_findings(p) if f[0] == name]
    sev = lambda fs: sorted({f[1] for f in fs})
    A, B = [100, 100, 400, 150], [150, 110, 450, 160]
    check("layout rules: two separate texts are quiet", not L.frame_findings(_payload([_item("html", 0, [_txt("甲", A)]), _item("html", 1, [_txt("乙", [100, 300, 400, 350])])])))
    check("layout rules: texts of different items that overlap are an ERROR", sev(rule(_payload([_item("html", 0, [_txt("甲", A)]), _item("html", 1, [_txt("乙", B)])]), "text-overlap")) == ["ERROR"])
    check("layout rules: the same two boxes inside ONE item (a memory cell's name and value) are quiet", not rule(_payload([_item("svg", 0, [_txt("甲", A), _txt("乙", B)])]), "text-overlap"))
    check("layout rules: only the line leading overlapping (stacked lines) is quiet", not rule(_payload([_item("html", 0, [_txt("甲", [100, 100, 400, 150])]), _item("html", 1, [_txt("乙", [100, 148, 400, 198])])]), "text-overlap"))
    check("layout rules: text sticking out of the board is an ERROR (the board clips it)", sev(rule(_payload([_item("html", 0, [_txt("甲", [1800, 500, 1950, 550])])]), "off-board")) == ["ERROR"])
    check("layout rules: ink hugging the board edge is only a WARN", sev(rule(_payload([_item("html", 0, [_txt("甲", [30, 500, 300, 550])])]), "off-board")) == ["WARN"])
    check("layout rules: a text two lines tall without a line break in its source is an ERROR; with the break it is fine",
          sev(rule(_payload([_item("html", 0, [_txt("甲乙", A, lines=2)])]), "wrap")) == ["ERROR"] and not rule(_payload([_item("html", 0, [_txt("甲\n乙", A, lines=2)])]), "wrap"))
    T = [_txt("甲乙丙丁", [300, 300, 700, 360])]   # ink box 300..700 x 306..354
    thru = _stroke([[500, 100 + 10 * i] for i in range(60)])                    # a long connector that crosses the label
    check("layout rules: a long open stroke that crosses a text is reported", sev(rule(_payload([_item("html", 0, T), _item("svg", 0, shapes=[thru])]), "stroke-on-text")) == ["WARN"])
    strike = _stroke([[250 + 10 * i, 330] for i in range(50)])                  # most of it lies on the text
    check("layout rules: a strike-through (most of the stroke lies on the text) is quiet", not rule(_payload([_item("html", 0, T), _item("svg", 0, shapes=[strike])]), "stroke-on-text"))
    mark = _stroke([[480 + 3 * i, 310 + 3 * i] for i in range(12)])             # a small diagonal drawn on the text
    check("layout rules: a short mark drawn on the text (cross-out of a value) is quiet", not rule(_payload([_item("html", 0, T), _item("svg", 0, shapes=[mark])]), "stroke-on-text"))
    arm1 = _stroke([[200 + 8 * i, 100 + 8 * i] for i in range(60)])             # two long diagonals that cross: an X over a whole box
    arm2 = _stroke([[200 + 8 * i, 583 - 8 * i] for i in range(60)])           # (offset 3 px: hand-drawn lines never meet exactly at a vertex)
    check("layout rules: two strokes that cross each other (an X over a box) are quiet, one of them alone is reported",
          not rule(_payload([_item("html", 0, T), _item("svg", 0, shapes=[arm1]), _item("svg", 1, shapes=[arm2])]), "stroke-on-text")
          and sev(rule(_payload([_item("html", 0, T), _item("svg", 0, shapes=[arm1])]), "stroke-on-text")) == ["WARN"])
    ends = _stroke([[250 + 10 * i, 330] for i in range(30)])                    # ends inside the text
    check("layout rules: a stroke that ends inside a text (arrow onto a label) is quiet", not rule(_payload([_item("html", 0, T), _item("svg", 0, shapes=[ends])]), "stroke-on-text"))
    under = _stroke([[300 + 10 * i, 352] for i in range(40)])
    check("layout rules: an underline at the bottom of the text is quiet", not rule(_payload([_item("html", 0, T), _item("svg", 0, shapes=[under])]), "stroke-on-text"))
    head = _stroke([[250 + 10 * i, 200] for i in range(10)] + [[450, 320], [450, 330], [450, 340], [450, 332]], sub=[0] * 10 + [1] * 4)
    check("layout rules: the head of an arrow pointing at a text (second subpath) is quiet", not rule(_payload([_item("html", 0, T), _item("svg", 0, shapes=[head])]), "stroke-on-text"))
    pen = {"kind": "circle", "box": [440, 320, 484, 364], "closed": True, "stroked": True, "filled": True, "width": 2, "opacity": 1.0, "reveal": 1.0, "fill": L.PEN_FILL}
    check("layout rules: the pointer pen item is never reported", not rule(_payload([_item("html", 0, T), _item("svg", 0, shapes=[thru, pen])]), "stroke-on-text"))
    frame = _stroke([[290, 296], [710, 296], [710, 364], [290, 364], [290, 296]], closed=True)
    check("layout rules: another item's emphasis frame round a word is quiet", not rule(_payload([_item("html", 0, T), _item("svg", 0, shapes=[frame])]), "stroke-on-text"))
    small = _stroke([[320, 290], [500, 290], [500, 370], [320, 370], [320, 290]], closed=True)
    check("layout rules: a frame of the SAME item that does not hold its text (value wider than its cell) is reported (rule frame-fit)",
          sev(rule(_payload([_item("svg", 0, T, shapes=[small])]), "frame-fit")) == ["WARN"])
    pill = {"kind": "panel", "box": [790, 910, 1130, 1000], "closed": True, "filled": True, "stroked": False, "opacity": 1.0, "reveal": 1.0}
    ov = [{"tag": "div", "box": pill["box"], "texts": [], "shapes": [pill]}]
    check("layout rules: text under the caption pill is reported, more than 40 % of it is an ERROR",
          sev(rule(_payload([_item("html", 0, [_txt("甲", [800, 925, 1100, 975])])], ov), "under-overlay")) == ["ERROR"] and not rule(_payload([_item("html", 0, [_txt("甲", [800, 700, 1100, 750])])], ov), "under-overlay"))
    fade = _txt("甲", B, opacity=0.2)
    check("layout rules: texts that are fading out or still being drawn are not compared", not rule(_payload([_item("html", 0, [_txt("乙", A)]), _item("html", 1, [fade])]), "text-overlap")
          and not rule(_payload([_item("html", 0, [_txt("乙", A)]), _item("html", 1, [_txt("甲", B, reveal=0.5)])]), "text-overlap"))
    check("layout rules: two texts in the middle of a crossfade (opacity 0.7) are not an overlap", not rule(_payload([_item("html", 0, [_txt("乙", A, opacity=0.7)]), _item("html", 1, [_txt("甲", B)])]), "text-overlap"))
    dup = rule(_payload([_item("html", 0, [_txt("主函数里", A)]), _item("html", 1, [_txt("主函数里", A)])]), "text-overlap")
    check("layout rules: the same text written twice at the same place is only a WARN (it just looks bolder)", sev(dup) == ["WARN"] and "twice" in dup[0][3])
    cross = _payload([_item("html", 0, T), _item("svg", 0, shapes=[thru])])
    check("layout rules: a stroke through a text needs two neighbouring samples too (the first arm of a cross-out exists before the second one)",
          not L.analyze({90: cross}, lambda fr: "K1") and len(L.analyze({90: cross, 120: cross}, lambda fr: "K1")) == 1)
    fit = _payload([_item("svg", 0, T, shapes=[small])])
    one = L.analyze({90: fit}, lambda fr: "K1")
    two = L.analyze({90: fit, 120: fit}, lambda fr: "K1")
    check("layout rules: a text that does not fit its frame needs two neighbouring samples (a value flying across a memory board is there for a moment); an overlap needs one",
          not one and len(two) == 1 and two[0]["n"] == 2 and len(L.analyze({90: _payload([_item("html", 0, [_txt("甲", A)]), _item("svg", 0, [_txt("乙", B)])])}, lambda fr: "K1")) == 1)
    fx = json.loads((ROOT / "docs/whiteboard/fixtures/layout_probe_real_frame.json").read_text(encoding="utf-8"))["payload"]
    n_arrow = sum(1 for it in fx["items"] for s in it["shapes"] if s.get("sub") and max(s["sub"]) >= 1)
    check("layout rules: a real frame (pen, arrows from labels, 48 texts) reports nothing", n_arrow >= 1 and not L.frame_findings(fx), f"{n_arrow} arrows")
    # merging: consecutive samples are one event, a gap makes two
    f = lambda: [("text-overlap", "WARN", ("tt", "a", "b"), "m", [])]
    one = L.collect({90: f(), 120: f(), 150: f()}, lambda fr: "K1")
    two = L.collect({90: f(), 120: [], 150: f()}, lambda fr: "K1")
    check("layout rules: the same finding in consecutive samples is one event, a gap makes two", len(one) == 1 and one[0]["n"] == 3 and len(two) == 2)
    # glyph coverage from the props
    props = {"cuts": [{"id": "K1", "in_seconds": 0, "whiteboard": {"items": [{"kind": "write", "text": "箭头→好", "at": 1, "font": "hand"}, {"kind": "write", "text": "中文", "at": 2, "font": "mono"},
                                                                          {"kind": "write", "text": "x = 1;", "at": 3, "font": "mono"}]}}]}
    g = L.glyph_findings(props, C.HAND_FONT, C.MONO_FONT, C.FALLBACK_FONT)
    check("layout rules: glyph coverage - an arrow in the hand font is a WARN, CJK in the mono font a tofu ERROR, plain code is quiet",
          [(x["severity"], x["t0"]) for x in g] == [("WARN", 1.0), ("ERROR", 2.0)], str([(x["severity"], x["t0"]) for x in g]))
    # the sample plan: every wanted frame lies on its cut's grid and inside a cluster, clusters never leave their cut
    if have("projects/c-variable-life-cn/render_props.json"):
        pr, _ = C.wr.load_props(ROOT / "projects/c-variable-life-cn")
        ranges, wanted, clusters = C.plan(pr, C.load_quiz(ROOT / "projects/c-variable-life-cn"))
        on_grid = all(any(lo <= w <= hi and (w - lo) % C.STEP == 0 for _, lo, hi in ranges) for w in wanted)
        covered = all(any(c[0] <= w <= c[1] for c in clusters) for w in wanted)
        inside_cut = all(any(lo <= c[0] and c[1] <= hi for _, lo, hi in ranges) for c in clusters)
        check("layout check: sample frames are on the cut grid, every one is in a cluster, no cluster crosses a cut", on_grid and covered and inside_cut, f"{len(wanted)} frames, {len(clusters)} clusters")
        groups = C.split_groups(clusters, 3)
        check("layout check: the clusters are spread over the processes without loss", sorted(map(tuple, sum(groups, []))) == sorted(map(tuple, clusters)) and len(groups) == 3)


def t_layout_probe_slow(slow):
    if not slow:
        print("SKIP layout probe (use --slow)")
        return
    if not have("projects/c-variable-life-cn/render_props.json", "remotion-composer/probe/layout_probe.mjs"):
        print("SKIP layout probe (no lesson 42 props)")
        return
    tmp = Path(tempfile.mkdtemp())
    try:
        src = json.loads((ROOT / "projects/c-variable-life-cn/render_props.json").read_text(encoding="utf-8"))
        for name, extra in (("control", []), ("overlap", [{"kind": "write", "text": "重叠测试甲乙丙丁", "x": 700, "y": 790, "at": 2.0, "size": 50, "font": "hand"},
                                                         {"kind": "write", "text": "戊己庚辛重叠", "x": 760, "y": 800, "at": 2.0, "size": 50, "font": "hand"}])):
            p = copy.deepcopy(src)
            next(c for c in p["cuts"] if c["id"] == "K4")["whiteboard"]["items"] += extra
            (tmp / name).mkdir()
            (tmp / name / "render_props.json").write_text(json.dumps(p), encoding="utf-8")
        r = sh(PY, "docs/whiteboard_layout_check.py", tmp / "control", "--cuts", "K4", "--no-glyph")
        check("layout probe: an unmodified cut of lesson 42 passes (exit 0, 0 errors)", r.returncode == 0 and "0 error(s)" in r.stdout and "CHECK INCOMPLETE" not in r.stdout, r.stdout.strip().splitlines()[-1][:100] if r.stdout else r.stderr[-100:])
        r = sh(PY, "docs/whiteboard_layout_check.py", tmp / "overlap", "--cuts", "K4", "--no-glyph")
        check("layout probe: two texts written on top of each other are an ERROR (exit 1)", r.returncode == 1 and "[text-overlap]" in r.stdout, r.stdout.strip().splitlines()[-1][:100] if r.stdout else r.stderr[-100:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_verify(slow):
    if not slow:
        print("SKIP verify (use --slow)")
        return
    if not have("projects/c-clinic-cn/renders/final.mp4"):
        print("SKIP verify (no lesson 43 final.mp4)")
        return
    tmp = Path(tempfile.mkdtemp())
    try:
        p = tmp / "c-clinic-cn"
        for d in ("renders", "assets/audio", "artifacts"):
            (p / d).mkdir(parents=True)
        S = ROOT / "projects/c-clinic-cn"
        (p / "renders/final.mp4").symlink_to(S / "renders/final.mp4")
        shutil.copy2(S / "assets/audio/narration_timeline.json", p / "assets/audio")
        r = sh(PY, "docs/whiteboard_verify.py", "verify", p, "--no-sheets", "--no-backup")
        m = json.loads((p / "validation/compose-measured.json").read_text(encoding="utf-8"))
        loud, sil = m["loudness"], [(s["start"], s["end"]) for s in m["silences"]]
        check("verify: duration, frames and md5 equal the hand-measured lesson-43 values", abs(m["probe"]["duration"] - 414.967) < 0.002 and m["probe"]["video"]["nb_frames"] == 12449 and m["md5"].startswith("548ebe29e731"), f"{m['probe']['duration']} s, {m['probe']['video']['nb_frames']} frames")
        check("verify: loudness -16.0 LUFS, LRA 3.1, peak -4.5", loud["I"] == -16.0 and loud["LRA"] == 3.1 and loud["peak_dbfs"] == -4.5, str(loud))
        check("verify: the three quiz silences and the tail are found", sil[:3] == [(75.89, 79.06), (375.9, 379.04), (388.74, 391.88)] and m["unexpected_silences"] == [], str(sil))
        check("verify: three frozen stretches (slow handwriting), no black frames", len(m["freeze"]) == 3 and m["black_frames"] == 0, str(m["freeze"]))
        check("verify: all mechanical checks pass", r.returncode == 0 and m["pass"])
        c = next((q for q in [S / "renders/chunks"] if q.exists()), None)
        k1 = sorted(c.glob("K1-*.mp4"))[0] if c else None
        if k1:
            r = sh(PY, "docs/whiteboard_verify.py", "compare", k1, k1)
            check("verify: PSNR of a chunk against itself is infinite", "average inf" in r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    slow = "--slow" in sys.argv
    for t in (t_last_item, t_thumb, t_script_lint, t_lint_mixed, t_layout_rules, t_callbacks, t_gate, t_gate_experiment, t_wait, t_new_lesson, t_series, t_registry):
        try:
            t()
        except Exception as e:  # a crashing test is a failing test
            check(t.__name__ + " crashed", False, repr(e)[:120])
    for t in (t_layout_probe_slow, t_verify):
        try:
            t(slow)
        except Exception as e:
            check(t.__name__ + " crashed", False, repr(e)[:120])
    bad = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed" + (f"; FAILED: {[b[0] for b in bad]}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
