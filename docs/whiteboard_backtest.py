#!/usr/bin/env python3
"""Backtests for the whiteboard tools: every check must flag a KNOWN past case and pass the lessons that were fine - a check that has never caught anything has not been shown to work.
Run (repo root):  .venv/bin/python docs/whiteboard_backtest.py [--slow]        exit code 1 if any test fails
Fast tests (seconds) use the published lessons' own data, never modify them (scratch copies in a temp dir); --slow also runs the full compose verifier on a scratch copy of
lesson 43's final video (about 40 s) and checks its numbers against the ones typed by hand in 2026-10 (414.967 s, 12449 frames, -16.0 LUFS, silences, md5), and runs the measured layout
probe (docs/whiteboard_layout_check.py) on a cut of lesson 42 with and without a seeded overlap (about 1 minute).
A test that needs a published lesson's files is skipped (not failed) when they are missing."""
import copy
import json
import os
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
    # the experiment lesson (EXPERIMENT.md) was written before the new series cut its ties to the C course: its bare "第二课" still means the C course, must resolve there, must not be called a
    # forward reference when the new lesson is numbered 1, and must show the quoted sentence
    quote = {"sections": [{"id": "s1", "text": "第二课里说过：过门的是克隆体，也就是副本。今天也有一扇门。"}]}
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "agent-demo-cn"
        (d / "artifacts").mkdir(parents=True)
        (d / "artifacts" / "script.json").write_text(json.dumps(quote, ensure_ascii=False), encoding="utf-8")
        (d / "EXPERIMENT.md").write_text("experiment\n", encoding="utf-8")
        r = sh("python3", "docs/whiteboard_callbacks.py", d, "--lesson", "1")
    o = r.stdout
    check("callbacks: the frozen experiment lesson's callback resolves to the C course, is not flagged as a forward reference, and lists lesson 2's quoted sentence",
          "智能体篇" in o and "本课是第" not in o and "- ⚠" not in o and "过门的是克隆体，也就是副本，手术只改副本，本人不变" in o, o.strip().splitlines()[0] if o.strip() else r.stderr[-120:])
    # a real lesson of the new series has no tie to the C course: its "第二课" means the series' own lesson 2, which does not exist, so it is flagged, and nothing from the C course is quoted
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "agent-demo-cn"
        (d / "artifacts").mkdir(parents=True)
        (d / "artifacts" / "script.json").write_text(json.dumps(quote, ensure_ascii=False), encoding="utf-8")
        r = sh("python3", "docs/whiteboard_callbacks.py", d, "--lesson", "1")
    o = r.stdout
    check("callbacks: in a new-series lesson a bare \"第二课\" means the series' own lesson 2 (not there: flagged) and never quotes the C course",
          "找不到第 2 课的项目" in o and "过门的是克隆体，也就是副本，手术只改副本" not in o and "与 C 课没有任何联系" in o, o.strip().splitlines()[0] if o.strip() else r.stderr[-120:])


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
        # the agent series' own template and cast library: teacher + AI partner pictures, reference pictures, no doctor, and the leftover doctor names of the template's boards are listed
        if have("projects/_cast/agent/teacher_hold.png", "projects/agent-messages-cn/scripts"):
            (tmp / "projects/agent-messages-cn").symlink_to(ROOT / "projects/agent-messages-cn")
            r5 = sh(PY, "docs/whiteboard_new_lesson.py", "--pid", "agent-castdemo-cn", "--n", "1", "--title", "回测", "--projects-dir", tmp / "projects")
            im = tmp / "projects/agent-castdemo-cn/assets/images"
            scs = tmp / "projects/agent-castdemo-cn/scripts"
            labelled = [f.name for f in scs.iterdir() if f.suffix in (".py", ".sh") and re.search(r"试验品|技术测试|不属于课程|EXPERIMENT", f.read_text(encoding="utf-8")) and "NEW-LESSON GUARD" not in f.read_text(encoding="utf-8")]
            guarded = [f.name for f in scs.iterdir() if f.suffix in (".py", ".sh") and "NEW-LESSON GUARD" in f.read_text(encoding="utf-8")]
            run_g = sh("python3", scs / "publish_prep.py")
            check("new_lesson (agent series): scripts copied from the experiment lesson that carry its 试验品/技术测试 labels are guarded and refuse to run until rewritten (no label can reach the first real lesson)",
                  not labelled and "publish_prep.py" in guarded and "make_exercises.py" in guarded and run_g.returncode != 0 and "EXPERIMENT" in (run_g.stderr + run_g.stdout), f"unguarded: {labelled}; guarded: {guarded}")
            check("new_lesson (agent series): the template comes from series.yaml, the cast is teacher + AI partner + logo + reference pictures (no doctor), the doctor names left in the template's boards are listed, the missing series name is announced",
                  r5.returncode == 0 and (im / "teacher_point_l.png").exists() and (im / "robot_confused.png").exists() and (im / "schoollogo.png").exists() and not (im / "doctor_pointing.png").exists()
                  and (tmp / "projects/agent-castdemo-cn/references/ref_teacher.png").exists() and "still names the C series' doctor pictures" in r5.stdout and "has no name yet" in r5.stdout, r5.stdout[-150:].strip())
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
    c_words = {"sections": [{"id": "s1", "text": "想想医生怎么翻病历，第二课的克隆门也一样。" * 10}], "metadata": {}}
    e_c_words, _wa, _ia = SL.lint(c_words, 1, series="agent")
    e_legacy, _wb, _ib = SL.lint(c_words, 1, series="agent", forbid_terms=[])
    e_c_series, _wc, _ic = SL.lint(c_words, 12, series="c")
    check("series: C-course words (医生, 病历, 克隆门, ...) in a new-series narration are errors; the frozen experiment lesson is exempt; the C series itself is not affected",
          sum("C-course word" in x for x in e_c_words) >= 3 and not any("C-course word" in x for x in e_legacy) and not any("C-course word" in x for x in e_c_series))
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


def t_v2_fields():
    """The optional fields of the colour/animation upgrade (layer, move, rot, origin, fill, path, camera): lint, key_times and the two layout rules that know them."""
    import whiteboard_lint as W
    import whiteboard_layout_rules as L
    import whiteboard_layout_check as C

    def lint(*items, camera=None, **wb):
        board = {"items": list(items), **wb}
        if camera is not None:
            board["camera"] = camera
        return W.lint_props({"cuts": [{"id": "K1", "in_seconds": 0, "whiteboard": board}]})
    box = [100, 100, 500, 300]
    note = {"kind": "stroke", "shape": "path", "d": "M 100 100 L 500 100 L 500 300 L 100 300 Z", "box": box, "at": 1, "width": 0, "fill": "#FFF3A8", "shadow": True}
    txt = lambda **kw: {"kind": "write", "text": "一条消息", "x": 120, "y": 150, "at": 1.5, "size": 50, **kw}
    e, w = lint(note, txt(rot=-2, origin=[300, 200], move=[{"at": 3, "dx": 0}, {"at": 4, "dx": 200}]), camera=[{"at": 1, "scale": 1}, {"at": 3, "scale": 1.4, "cx": 700, "cy": 400}])
    check("v2 lint: a sticky note (filled path + write with the same move), a top layer and a camera push-in are quiet", not e and not w, str(e + w))
    e, w = lint({**note, "layer": "front"})
    check("v2 lint: a layer other than \"top\" is an error", any("layer must be" in x for x in e))
    e, w = lint(txt(move=[{"dx": 5}]))
    check("v2 lint: a move key without `at` is an error", any("numeric `at`" in x for x in e))
    e, w = lint({"kind": "stroke", "shape": "path", "at": 1})
    check("v2 lint: a path stroke without `d` is an error", any("`d` string" in x for x in e))
    e, w = lint({**note, "fillOpacity": 2})
    check("v2 lint: a fillOpacity above 1 is an error", any("fillOpacity" in x for x in e))
    e, w = lint(note, camera=[{"at": 1, "scale": 0.8}])
    check("v2 lint: a camera zoom-out (scale < 1) is an error", any("camera scale" in x for x in e))
    nb = dict(note); nb.pop("box")
    e, w = lint(nb)
    check("v2 lint: a filled path without `box` is warned", any("without `box`" in x for x in w) and not e)
    e, w = lint({**note, "fill": "#1C3653"}, txt())
    check("v2 lint: dark ink on a navy fill is warned (contrast), the same text on the pale note is not", any("contrast" in x for x in w) and not any("contrast" in x for x in lint(note, txt())[1]))
    big = {"kind": "stroke", "shape": "path", "d": "M 0 0 Z", "box": [0, 0, 900, 700], "at": 0.5, "width": 0, "fill": "#1C3653"}
    check("v2 lint: a pale note lying on a navy block counts as the text's background (the topmost fill), not the block", not [x for x in lint(big, note, txt())[1] if "contrast" in x])
    e, w = lint({**note, "fill": "#1C3653"}, txt(color="#FFFFFF"))
    check("v2 lint: white text on the navy fill is quiet", not [x for x in w if "contrast" in x])

    e, w = lint({"kind": "code", "lines": ["int x = 3;"], "x": 100, "y": 100, "at": 1, "lang": "rust"})
    check("v2 lint: a code item with an unknown `lang` is an error, \"c\" and \"py\" are fine", any("`lang`" in x for x in e) and not lint({"kind": "code", "lines": ["int x = 3;"], "x": 100, "y": 100, "at": 1, "lang": "c"})[0]
          and not lint({"kind": "code", "lines": ["x = 3"], "x": 100, "y": 100, "at": 1, "lang": "py"})[0])
    # the code colours (single source: CODE_COLORS in WhiteboardScene.tsx) keep >= 4.5:1 on the board colour and on the 45 % highlighter
    tsx = (ROOT / "remotion-composer/src/components/WhiteboardScene.tsx").read_text(encoding="utf-8")
    cols = dict(re.findall(r"(\w+): \"(#[0-9A-Fa-f]{6})\"", tsx[tsx.index("const CODE_COLORS"):tsx.index("const C_KW")]))
    worst = min(min(W.contrast(W._rgb(c), W._rgb(bg)) for bg in ("#FBFBF8", "#FBE692")) for c in cols.values())
    check("code colours: every token colour has contrast >= 4.5 on the board and on the highlighter", len(cols) == 7 and worst >= 4.5, f"{len(cols)} colours, worst {worst:.1f}")
    contrast_warn = lambda *items: [x for x in lint(*items)[1] if "contrast" in x]
    early, later = {**note, "fill": "#1C3653", "at": 0.2, "until": 1.0}, {**note, "fill": "#1C3653", "at": 8.0}
    check("v2 lint: a dark fill that is on the board together with the text is its background (warned), one that is gone before the text appears or only appears after it is not",
          contrast_warn({**note, "fill": "#1C3653", "until": 3.0}, txt(at=1.5, until=2.5)) and not contrast_warn(early, txt(at=1.5, until=2.5)) and not contrast_warn(later, txt(at=1.5, until=2.5)))
    # key_times: an item that moves and a camera move are sampled where they end
    cut = {"in_seconds": 10, "out_seconds": 40, "whiteboard": {"items": [{"kind": "write", "text": "甲", "x": 1, "y": 1, "at": 1, "dur": 1,
                                                                          "move": [{"at": 6, "dx": 0}, {"at": 9, "dx": 300}]}],
                                                             "camera": [{"at": 14, "scale": 1}, {"at": 16, "scale": 1.5}]}}
    kt = C.wr.key_times(cut, [])
    plain = C.wr.key_times({"in_seconds": 10, "out_seconds": 40, "whiteboard": {"items": [cut["whiteboard"]["items"][0] | {"move": None}]}}, [])
    check("v2 key_times: the end of a move (10+9+0.3) and of a camera move (10+16+0.3) are sample times", 19.3 in kt and 26.3 in kt and 19.3 not in plain, str(kt))

    sev = lambda fs: sorted({f[1] for f in fs})
    rule = lambda p, name: [f for f in L.frame_findings(p) if f[0] == name]
    # layout rules: no off-board check while the camera is zoomed; text under a top-layer character is a WARN
    off = _payload([_item("html", 0, [_txt("甲", [1800, 500, 1950, 550])])])
    check("v2 layout: text outside the board is an ERROR at zoom 1 but not while the camera is zoomed in",
          any(f[1] == "ERROR" for f in L.frame_findings(off)) and not [f for f in L.frame_findings({**off, "zoom": 1.5}) if f[0] == "off-board"])
    A = [100, 100, 400, 150]
    same = rule(_payload([_item("html", 0, [_txt("甲乙", A)]), _item("html", 1, [_txt("甲乙", [130, 100, 430, 150])])]), "text-overlap")
    diff = rule(_payload([_item("html", 0, [_txt("甲乙", A)]), _item("html", 1, [_txt("丙丁", [130, 100, 430, 150])])]), "text-overlap")
    check("v2 layout: the same text twice, shifted (a note copy sliding off its original), is only a WARN; two different texts that overlap that much are an ERROR",
          sev(same) == ["WARN"] and sev(diff) == ["ERROR"], f"{sev(same)} {sev(diff)}")
    blk = lambda box: {"kind": "path", "box": box, "closed": True, "filled": True, "stroked": False, "opacity": 1.0, "reveal": 1.0, "pts": []}
    covered = _payload([_item("html", 0, [_txt("甲乙", A)]), _item("html-top", 0, [_txt("丙丁", [130, 100, 430, 150])], [blk([90, 90, 470, 160])])])
    uncovered = _payload([_item("html", 0, [_txt("甲乙", A)]), _item("html-top", 0, [_txt("丙丁", [130, 100, 430, 150])], [blk([90, 90, 300, 160])])])
    below = _payload([_item("html", 0, [_txt("甲乙", A)]), _item("svg", 0, shapes=[blk([90, 90, 470, 160])]), _item("html", 1, [_txt("丙丁", [130, 100, 430, 150])])])
    translucent = _payload([_item("html", 0, [_txt("甲乙", A)]), _item("html-top", 0, [_txt("丙丁", [130, 100, 430, 150])], [{**blk([90, 90, 470, 160]), "fillAlpha": 0.45}])])
    check("v2 layout: a text completely under an opaque block of a layer in front of it (a note copy over its original) is not an overlap; a block that only covers part of it, one BEHIND it, or a translucent one (the highlighter), does not hide it",
          not rule(covered, "text-overlap") and sev(rule(uncovered, "text-overlap")) == ["ERROR"] and sev(rule(below, "text-overlap")) == ["ERROR"]
          and sev(rule(translucent, "text-overlap")) == ["ERROR"], f"{sev(rule(covered,'text-overlap'))} {sev(rule(uncovered,'text-overlap'))} {sev(rule(below,'text-overlap'))} {sev(rule(translucent,'text-overlap'))}")
    img = {"kind": "image", "box": [300, 100, 500, 300], "closed": True, "filled": True, "opacity": 1.0, "reveal": 1.0}
    char = _item("html-top", 0, shapes=[img])
    under = [f for f in L.frame_findings(_payload([_item("html", 0, [_txt("甲乙", [320, 150, 480, 200])]), char])) if f[0] == "under-character"]
    check("v2 layout: text lying under a top-layer character picture is a WARN (never an ERROR, the box holds transparent corners)", [f[1] for f in under] == ["WARN"])
    # with the opacity grid the covered share is measured: the picture's left half opaque, its right half transparent
    half = "".join(("1" if x < 16 else "0") for y in range(32) for x in range(32))
    gimg = {**img, "alpha": half}
    on_opaque = [f for f in L.frame_findings(_payload([_item("html", 0, [_txt("甲乙", [310, 150, 400, 200])]), _item("html-top", 0, shapes=[gimg])])) if f[0] == "under-character"]
    on_clear = [f for f in L.frame_findings(_payload([_item("html", 0, [_txt("甲乙", [420, 150, 490, 200])]), _item("html-top", 0, shapes=[gimg])])) if f[0] == "under-character"]
    edge = [f for f in L.frame_findings(_payload([_item("html", 0, [_txt("甲乙", [392, 150, 480, 200])]), _item("html-top", 0, shapes=[gimg])])) if f[0] == "under-character"]
    check("v2 layout: with the opacity grid a text on opaque pixels is an ERROR, a text in the transparent part of the picture's box is quiet, one just touching is a WARN",
          [f[1] for f in on_opaque] == ["ERROR"] and not on_clear and [f[1] for f in edge] == ["WARN"], f"{[f[1] for f in on_opaque]} {[f[1] for f in on_clear]} {[f[1] for f in edge]}")
    note_shape = {"kind": "path", "box": [310, 220, 480, 270], "closed": True, "filled": True, "stroked": False, "opacity": 1.0, "reveal": 1.0, "pts": []}
    on_note = [f for f in L.frame_findings(_payload([_item("svg", 0, shapes=[note_shape]), _item("html-top", 0, shapes=[{**img, "box": [300, 100, 500, 300], "alpha": "1" * 1024}])])) if f[0] == "under-character"]
    beside = [f for f in L.frame_findings(_payload([_item("svg", 0, shapes=[{**note_shape, "box": [520, 220, 700, 270]}]), _item("html-top", 0, shapes=[{**img, "alpha": "1" * 1024}])])) if f[0] == "under-character"]
    check("v2 layout: a character standing on a filled note is an ERROR (grid), a note beside it is quiet", [f[1] for f in on_note] == ["ERROR"] and not beside, f"{[f[1] for f in on_note]} {len(beside)}")
    away = _payload([_item("html", 0, [_txt("甲乙", [700, 150, 900, 200])]), char])
    plainimg = _payload([_item("html", 0, [_txt("甲乙", [320, 150, 480, 200])]), _item("html", 1, shapes=[img])])
    check("v2 layout: text beside the character, or under an ordinary (not top-layer) picture, is quiet",
          not [f for f in L.frame_findings(away) if f[0] == "under-character"] and not [f for f in L.frame_findings(plainimg) if f[0] == "under-character"])


def t_board_v2():
    """The Board class of the pilot project (agent-messages-v2-cn/scripts/_build_head.py) with the optional fields of the new composer: pass-through of unknown fields, absolute -> relative
    times of `move` keys, no pen keys for path shapes, camera, and relist carrying motion and camera into the next cut.  The class is cut out of the script (the script itself reads files)."""
    import ast
    head = ROOT / "docs/whiteboard/starter/scripts/_build_head.py"   # the starter is the canonical Board (new lessons are scaffolded from it); the pilot project's copy must be the same code
    import whiteboard_lint as W
    import whiteboard_v2_kit as K
    src = head.read_text(encoding="utf-8").replace("__PID__", "p").replace("__N__", "1")
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "Board")
    pilot = ROOT / "projects/agent-messages-v2-cn/scripts/_build_head.py"
    if pilot.exists():
        pn = next(n for n in ast.parse(pilot.read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef) and n.name == "Board")
        check("board v2: the pilot project's Board is the same code as the starter's", ast.dump(pn) == ast.dump(node))

    class _Im:
        width, height = 200, 400
    ns = {"copy": copy, "Image": type("Image", (), {"open": staticmethod(lambda p: _Im())}), "IMG": Path("/nonexistent"), "GREEN": "#15803D", "RED": "#DC2626", "INK": "#111827",
          "est_w": lambda t, s: sum(s * (0.55 if ord(c) < 128 else 1.0) for c in t.split("\n")[0])}
    exec(compile(ast.Module([node], []), str(head), "exec"), ns)
    Board = ns["Board"]
    b = Board("K1", 10.0, 30.0)
    b.write("甲", 100, 100, 12.0, size=40, rot=-2, origin=[120, 120], layer="top", move=[{"at": 12.5, "dx": 0}, {"at": 13.5, "dx": 300}])
    w = b.items[0]
    check("board v2: write hands unknown fields on and converts move times to cut-relative ones", w["layer"] == "top" and w["rot"] == -2 and w["origin"] == [120, 120]
          and [k["at"] for k in w["move"]] == [2.5, 3.5], str(w))
    b.stroke("path", 12.0, 0.5, width=0, d="M 0 0 Z", box=[0, 0, 10, 10], fill="#FFF3A8", shadow=True)
    check("board v2: a path stroke keeps fill/box/shadow and adds no pen key", b.items[1]["fill"] == "#FFF3A8" and b.items[1]["box"] == [0, 0, 10, 10] and len(b.keys) == 2, str(b.keys))
    b.image("x", 500, 100, 200, 14.0, radius=18, border={"width": 4}, shadow=True, layer="top", pen=False)
    im = b.items[2]
    check("board v2: an image takes radius/border/shadow/layer and pen=False leaves the pen alone", im["radius"] == 18 and im["layer"] == "top" and im["border"] == {"width": 4} and len(b.keys) == 2)
    check("board v2: no camera key, no camera field; with keys it is emitted relative to the cut", "camera" not in b.data()
          and (b.camera([{"at": 20.0, "scale": 1}, {"at": 22.0, "scale": 1.5, "cx": 900, "cy": 500}]) or [k["at"] for k in b.data()["camera"]] == [10.0, 12.0]))
    # the kit on a real Board: a sticky note that flies, lint-clean
    c = Board("K2", 10.0, 30.0)
    K.sticky(c, 100, 200, 220, 140, K.PAL["note_yellow"], [("一条消息", "hand", 34), ("role=user", "mono", 26)], 11.0, rot=-2, move=[{"at": 13.0, "dx": 0}, {"at": 14.0, "dx": 400}])
    K.bubble(c, 100, 500, 500, 90, "model", ["Hi Li."], 12.0, font="mono")
    props = {"cuts": [{"id": "K2", "in_seconds": 10.0, "whiteboard": c.data()}]}
    e, wn = W.lint_props(props)
    note = [i for i in c.items if i["kind"] == "stroke" and i.get("shadow")][0]
    texts = [i for i in c.items if i["kind"] == "write" and i.get("move")]
    check("board v2: a sticky note built with the kit is lint-clean, its parts carry the same move keys and origin",
          not e and not wn and len(texts) == 2 and all(t["move"] == note["move"] and t["origin"] == note["origin"] for t in texts), str(e + wn))
    # block / char / fly of the kit on a real Board
    e = Board("K6", 10.0, 30.0)
    K.block(e, 100, 200, 500, 300, "program", "程序", 11.0)
    K.char(e, "robot", 1500, 700, 300, 12.0)
    K.fly(e, 130, 300, 440, 52, "user", "hello", 14.0, 800, 100)
    blk = e.items[0]; cim = [i for i in e.items if i["kind"] == "image"][0]; fl = [i for i in e.items if i.get("move") and i["kind"] == "stroke"][0]
    ftxt = [i for i in e.items if i.get("move") and i["kind"] == "write"]
    check("board v2: kit block (navy, white label), char (top layer, no pen key) and fly (top layer, text at once, 0.1 s before take-off, same move on every part)",
          blk["fill"] == "#1C3653" and cim["layer"] == "top" and cim["y"] == 400 and fl["layer"] == "top" and abs(fl["at"] - 3.9) < 1e-6 and ftxt and all(t["layer"] == "top" and t["move"] == fl["move"] and t["dur"] == 0.05 for t in ftxt),
          f"{blk.get('fill')} {cim.get('layer')} {fl.get('at')}")
    # static (already drawn) boards collapse a move into its final pose
    d = Board("K3", 10.0, 30.0); d.static = True
    d.write("乙", 1, 1, 12.0, move=[{"at": 12.0, "dx": 0}, {"at": 13.0, "dx": 300, "scale": 2}, {"at": 14.0, "dy": 50}])
    check("board v2: in static mode a move collapses into ONE key holding the final pose", d.items[0]["move"] == [{"dx": 300, "scale": 2, "dy": 50, "at": -10.0}], str(d.items[0]["move"]))
    # relist: the next cut starts with the final pose and the final camera of the board it continues
    n = Board("K4", 20.0, 40.0)
    n.relist(c)
    c.camera([{"at": 14.0, "scale": 1.0}, {"at": 15.0, "scale": 1.4, "cx": 700, "cy": 400}])
    n2 = Board("K5", 20.0, 40.0); n2.relist(c)
    mv = [i for i in n.items if i.get("move")]
    check("board v2: relist shifts move keys (and `until`) into the past of the new cut, items are already drawn",
          mv and all(i["at"] == -10.0 and max(k["at"] for k in i["move"]) <= 0 for i in mv) and n.items[0]["move"][-1]["dx"] == 400, str([i["move"] for i in mv][:1]))
    check("board v2: relist carries the camera of the board it continues (keys in the past, final zoom held)", [k["at"] for k in n2.cam] == [-6.0, -5.0] and n2.cam[-1]["scale"] == 1.4, str(n2.cam))


def t_pose_tool():
    """docs/whiteboard_pose_tool.py: the colour-dominance cut-out on synthetic pictures (green and magenta backgrounds, a white shirt, a character that is itself green) and the submit/poll/
    download flow against a fake CLI (the request id is on disk BEFORE the submit)."""
    import stat
    import whiteboard_pose_tool as PT
    from PIL import Image, ImageDraw
    tmp = Path(tempfile.mkdtemp())
    try:
        def pic(bg, body):
            im = Image.new("RGB", (240, 360), bg)
            d = ImageDraw.Draw(im)
            d.ellipse((90, 20, 150, 100), fill=(240, 205, 160))                  # head (touches the body: a real character is one connected figure)
            d.rectangle((70, 90, 170, 230), fill=body)                              # body
            d.rectangle((70, 140, 170, 170), fill=(255, 255, 255))                  # white shirt band
            d.rectangle((75, 225, 165, 340), fill=(30, 55, 85))                     # trousers
            d.ellipse((10, 300, 40, 330), fill=bg)                                  # nothing there
            d.rectangle((200, 10, 206, 16), fill=(200, 30, 30))                     # a stray speck: must be dropped
            return im
        pic((0, 255, 0), (210, 190, 140)).save(tmp / "g.png")
        pic((255, 0, 255), (0, 170, 40)).save(tmp / "m.png")                       # a character that is itself green: needs a magenta background
        r1 = PT.key_image(tmp / "g.png", tmp / "g_out.png", "green")
        r2 = PT.key_image(tmp / "m.png", tmp / "m_out.png", "magenta")
        gi, mi = Image.open(tmp / "g_out.png"), Image.open(tmp / "m_out.png")
        cx, cy = gi.width // 2, gi.height // 2
        check("pose tool: green background cut out - the figure is opaque (white band included), the corner is clear, the stray speck is dropped, the picture is trimmed",
              gi.getpixel((cx, cy))[3] > 250 and gi.getpixel((2, 2))[3] == 0 and gi.width < 240 and r1["blobs_kept"] == 1 and r1["blobs"] >= 2, str(r1))
        mx, my = mi.width // 2, 30
        check("pose tool: magenta background cut out and the character's own green stays opaque", mi.getpixel((mx, my + 50))[3] > 250 and mi.getpixel((2, 2))[3] == 0 and r2["blobs_kept"] == 1, str(r2))
        # fake CLI: submit refuses unless the record (with the request id) is already on disk
        cli = tmp / "fakeqwen"
        cli.write_text("#!/usr/bin/env python3\n"
                       "import json, os, sys\nfrom pathlib import Path\na = sys.argv[1:]\nstate = Path(os.environ['FAKE_STATE'])\n"
                       "if a[0] == 'submit':\n    rec = json.loads(Path(os.environ['FAKE_REC']).read_text())\n    sys.exit(3) if rec.get('request_id') != a[a.index('--request-id') + 1] else None\n"
                       "    state.write_text('0'); print(json.dumps({'id': 'job1'}))\n"
                       "elif a[0] == 'get':\n    n = int(state.read_text()); state.write_text(str(n + 1))\n"
                       "    print(json.dumps({'status': ['queued', 'running', 'completed'][min(n, 2)], 'files': [{'index': 0}]}))\n"
                       "elif a[0] == 'download':\n    Path(a[a.index('--output') + 1]).write_bytes(open(os.environ['FAKE_PNG'], 'rb').read())\n", encoding="utf-8")
        cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
        os.environ.update(FAKE_STATE=str(tmp / "state"), FAKE_REC=str(tmp / "rec.json"), FAKE_PNG=str(tmp / "g.png"))
        rec = PT.run_job("req-1", ["--mode", "image_edit"], tmp / "out.png", tmp / "rec.json", cli=str(cli), poll=0.01)
        saved = json.loads((tmp / "rec.json").read_text(encoding="utf-8"))
        check("pose tool: the request id is on disk before the submit, the states are recorded, the result is downloaded",
              rec["request_id"] == "req-1" and [x["status"] for x in saved["states"]] == ["queued", "running", "completed"] and (tmp / "out.png").exists() and saved["job_id"] == "job1", str(saved.get("states")))
        try:
            PT.run_job("other-id", ["--mode", "image_edit"], tmp / "o2.png", tmp / "rec2.json", cli=str(cli), poll=0.01)
            refused = False
        except SystemExit as e:
            refused = "submit failed" in str(e)
        # a transient "Request/download incomplete ... keep the same request ID" is retried with the SAME id (twice in a row here), then succeeds
        flaky = tmp / "flakyqwen"
        flaky.write_text("#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\na = sys.argv[1:]\nst = Path(os.environ['FAKE_STATE'])\nlog = Path(os.environ['FAKE_IDS'])\n"
                         "if a[0] == 'submit':\n    log.write_text(log.read_text() + a[a.index('--request-id') + 1] + '\\n' if log.exists() else a[a.index('--request-id') + 1] + '\\n')\n"
                         "    n = len(log.read_text().split())\n    if n < 3:\n        print('Request/download incomplete (ConnectionResetError). Keep the same request ID and inputs', file=sys.stderr); sys.exit(2)\n"
                         "    st.write_text('0'); print(json.dumps({'id': 'job9'}))\n"
                         "elif a[0] == 'get':\n    print(json.dumps({'status': 'completed'}))\n"
                         "elif a[0] == 'download':\n    Path(a[a.index('--output') + 1]).write_bytes(open(os.environ['FAKE_PNG'], 'rb').read())\n", encoding="utf-8")
        flaky.chmod(flaky.stat().st_mode | stat.S_IEXEC)
        os.environ.update(FAKE_IDS=str(tmp / "ids.txt"))
        real_sleep = PT.time.sleep
        PT.time.sleep = lambda s: None
        try:
            PT.run_job("req-same", ["--mode", "image_edit"], tmp / "o3.png", tmp / "rec3.json", cli=str(flaky), poll=0.01)
        finally:
            PT.time.sleep = real_sleep
        ids = (tmp / "ids.txt").read_text().split()
        check("pose/h3 tools: a transient submit failure ('keep the same request ID') is retried with the same id (3 submits, one id) and then succeeds", ids == ["req-same"] * 3 and (tmp / "o3.png").exists(), str(ids))
        check("pose tool: a failing submit is reported and leaves the record with the error", refused and "error" in json.loads((tmp / "rec2.json").read_text(encoding="utf-8")))
    finally:
        for k in ("FAKE_STATE", "FAKE_REC", "FAKE_PNG", "FAKE_IDS"):
            os.environ.pop(k, None)
        shutil.rmtree(tmp, ignore_errors=True)


def t_cover_series():
    """Series-aware covers: the C covers come out byte-identical to the published ones, a series without a name refuses, a series with a cast draws it."""
    import hashlib
    import whiteboard_cover_maker as CM
    tmp = Path(tempfile.mkdtemp())
    keep_root, keep_cfg = CM.ROOT, CM.series_config
    try:
        CM.ROOT = tmp
        same = 0
        rows = [r for r in CM.LESSONS if (ROOT / "projects" / r[0] / "exports/thumbnails/cover.png").exists()][::14]
        for row in rows:
            (tmp / row[0] / "exports/thumbnails").mkdir(parents=True, exist_ok=True)
            CM.make(*row)
            same += hashlib.sha256((tmp / row[0] / "exports/thumbnails/cover.png").read_bytes()).hexdigest() == hashlib.sha256((ROOT / "projects" / row[0] / "exports/thumbnails/cover.png").read_bytes()).hexdigest()
        check("cover: the C series' covers (doctor + tag from series.yaml) are byte-identical to the published ones", rows and same == len(rows), f"{same}/{len(rows)} identical")
        (tmp / "agent-demo-cn/exports/thumbnails").mkdir(parents=True, exist_ok=True)
        if not keep_cfg("agent")["name"]:
            try:
                CM.make("agent-demo-cn", 1, "标题", "副标题", "x = 1;")
                refused = False
            except SystemExit as e:
                refused = "has no name yet" in str(e)
            check("cover: a series without a name refuses to make a cover (no placeholder name)", refused)
        import importlib.util
        sp = importlib.util.spec_from_file_location("rp", ROOT / "docs/whiteboard_release_pack.py")
        RP = importlib.util.module_from_spec(sp); sp.loader.exec_module(RP)
        cfg_c, dest_c, zip_c = RP.pack_paths("c")
        try:
            RP.pack_paths("agent") if not keep_cfg("agent")["name"] else None
            nameless = bool(keep_cfg("agent")["name"])
        except SystemExit as e:
            nameless = "has no name yet" in str(e)
        check("release pack: the C series' folder and zip are named as before; a series without a name refuses", dest_c.name == "C语言白板课_成品" and zip_c.name == "C语言白板课_成品.zip" and nameless, f"{dest_c} {zip_c}")
        if have("projects/_cast/agent/teacher_point_l.png"):
            CM.series_config = lambda series="c": {**keep_cfg(series), "name": "测试系列"} if series == "agent" else keep_cfg(series)
            CM.make("agent-demo-cn", 1, "标题", "副标题", "x = 1;")
            from PIL import Image
            im = Image.open(tmp / "agent-demo-cn/exports/thumbnails/cover.png").convert("RGB")
            cardigan = sum(1 for x in range(1500, 1800, 6) for y in range(400, 800, 6) if abs(im.getpixel((x, y))[0] - 227) < 14 and abs(im.getpixel((x, y))[1] - 202) < 14 and abs(im.getpixel((x, y))[2] - 155) < 14)
            check("cover: a series with a cast draws its teacher on the right (cardigan pixels there), not the doctor", cardigan > 200, f"{cardigan} cardigan-coloured samples")
    finally:
        CM.ROOT, CM.series_config = keep_root, keep_cfg
        shutil.rmtree(tmp, ignore_errors=True)


def t_scene_plan_devices():
    import whiteboard_scene_plan_check as SC
    import whiteboard_lessons as WL
    devs = WL.series_config("agent")["devices"]
    ok = [{"id": "sc01", "movement": "呈现手段：便条飞行、镜头推近；便条从程序飞到模型。"}, {"id": "sc02", "movement": "呈现手段：聊天气泡、柱状图、角色表演；…"}, {"id": "sc03", "movement": "呈现手段：插画卡片；…"}]
    e, w, used = SC.check(ok, devs)
    check("scene plan devices: scenes that name devices from the list are accepted", not e and not w and len(used) == 6, f"{e} {w}")
    e, w, _ = SC.check([{"id": "sc01", "movement": "代码逐行写出"}, {"id": "sc02", "movement": "呈现手段：魔法特效；…"}], devs)
    check("scene plan devices: a scene without 呈现手段 or with a device that is not in the list is an ERROR", len(e) == 2, str(e))
    e, w, _ = SC.check([{"id": f"sc0{i}", "movement": "呈现手段：纯板书；方框与箭头"} for i in range(1, 5)] + [{"id": "sc05", "movement": "呈现手段：便条飞行"}], devs)
    check("scene plan devices: a lesson of boxes and arrows only is warned (the complaint that started the visual upgrade)", not e and any("过于单一" in x for x in w) and any("少于 4 种" in x for x in w), str(w))


def t_composer_baseline_slow(slow):
    """The composer still draws the published lessons exactly as before the colour/animation upgrade: the reference stills (projects/_baseline/ref, 226 frames of 5 lessons) re-rendered now are
    byte-identical (about 2 minutes)."""
    if not slow:
        print("SKIP composer baseline (use --slow)")
        return
    if not have("projects/_baseline/ref/times.json") and not have("projects/_baseline/ref"):
        print("SKIP composer baseline (no reference set)")
        return
    r = sh(PY, "docs/whiteboard_baseline_stills.py", "render", "_bt")
    c = sh(PY, "docs/whiteboard_baseline_stills.py", "compare", "ref", "_bt")
    shutil.rmtree(ROOT / "projects/_baseline/_bt", ignore_errors=True)
    for d in (ROOT / "projects/_baseline").glob("_mirror_*"):
        shutil.rmtree(d, ignore_errors=True)
    last = c.stdout.strip().splitlines()[-1] if c.stdout.strip() else r.stderr[-120:]
    check("composer baseline: the 226 reference stills of five published lessons re-render byte-identical", r.returncode == 0 and c.returncode == 0 and "TOTAL 226 stills, 0 differ" in c.stdout, last)


def t_kit_devices():
    """The second-round devices of docs/whiteboard_v2_kit.py: result panel, countdown ring, quiz card, right/wrong panels, idle motion, token meter, lanes, curve.  Each must come out lint-clean
    (the lint knows the fields, the contrast rule, the quiz silence) and have the structure its docstring promises."""
    import ast
    import whiteboard_lint as W
    import whiteboard_v2_kit as K
    src = (ROOT / "docs/whiteboard/starter/scripts/_build_head.py").read_text(encoding="utf-8").replace("__PID__", "p").replace("__N__", "1")
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "Board")

    class _Im:
        width, height = 200, 400
    ns = {"copy": copy, "Image": type("Image", (), {"open": staticmethod(lambda p: _Im())}), "IMG": Path("/nonexistent"), "GREEN": "#15803D", "RED": "#DC2626", "INK": "#111827",
          "est_w": lambda t, s: sum(s * (0.55 if ord(c) < 128 else 1.0) for c in t.split("\n")[0])}
    exec(compile(ast.Module([node], []), "starter", "exec"), ns)
    Board = ns["Board"]

    def lint(items, quiz=None):
        return W.lint_props({"cuts": [{"id": "K1", "in_seconds": 0, "whiteboard": {"items": items}}]}, quiz)

    r = K.RawBoard()
    K.result_panel(r, 900, 200, 500, 200, [("$ python ask.py", "cmd"), "OK, Ming!", "Your name is Ming."], 3.0)
    e, w = lint(r.items)
    check("kit: a result panel (command line + output lines) is lint-clean and its monospace lines are English only", not e and not w and sum(1 for i in r.items if i.get("font") == "mono") == 3, str(e + w))
    r = K.RawBoard()
    K.ring(r, 300, 700, 50, 10.0, 13.2)
    ends = [i["until"] for i in r.items]
    quiz = [{"question_end": 10.0, "answer_not_before": 13.2}]
    e, w = lint(r.items, quiz)
    check("kit: the countdown ring is three arcs that vanish one after the other, the last one before the answer, and the quiz-silence lint accepts it",
          len(r.items) == 3 and ends == sorted(ends) and len(set(ends)) == 3 and ends[-1] <= 13.2 - 0.4 + 1e-6 and all(i["at"] < 10.3 for i in r.items) and not [x for x in e if "silence" in x], f"{ends} {e}")
    r = K.RawBoard()
    K.quiz_card(r, 100, 300, 800, 200, ["第三次提问时，", "递过去几张？"], 5.0)
    boxes = K.split_panels(r, 100, 600, 900, 300, 6.0)
    K.mark_ok(r, 200, 700, 7.0); K.mark_bad(r, 700, 700, 7.5)
    e, w = lint(r.items)
    check("kit: a quiz card (red tag, white text) and right/wrong panels with tick and cross are lint-clean, the panels are two equal halves", not e and not w and len(boxes) == 2 and boxes[0][2] == boxes[1][2], str(e + w))
    keys = K.idle_keys(2.0, 8.0, amp=5, period=2.0, sway=1.5)
    check("kit: idle motion alternates rest and raised keys inside the given time span", len(keys) == 6 and keys[0]["dy"] == 0 and keys[1]["dy"] == -5 and keys[1]["rot"] == 1.5 and keys[0]["rot"] == -1.5 and keys[-1]["at"] < 8.0, str(keys))
    b = Board("K1", 10.0, 50.0)
    K.char(b, "robot", 1500, 700, 300, 12.0, until=30.0, idle=True)
    im = b.items[0]
    check("kit: a character with idle motion carries relative move keys, the feet as the transform origin and no pen key", im["origin"] == [1500, 700] and im["move"][0]["at"] == 2.0 and im["move"][-1]["at"] < 20.0 and len(b.keys) == 0, str(im.get("move", [])[:2]))
    r = K.RawBoard()
    placed = K.token_meter(r, 1300, 900, 360, 420, [("user", 90, 3.0), ("assistant", 120, 5.0), ("user", 90, 7.0), ("assistant", 140, 9.0)], 2.0)
    dropped = [p for p in placed if p[2] is not None]
    slips = [i for i in r.items if i.get("shadow")]
    e, w = lint(r.items)
    out = [i for i in slips if any(k.get("dx", 0) < 0 for k in i.get("move", []))]
    check("kit: the token meter stacks notes from the bottom and, once the stack passes the red limit line, the oldest slides out (dx < 0, fades) while the others settle down (dy keys)",
          dropped and placed[0][2] is not None and len(out) == len(dropped) and any(k.get("dy", 0) > 0 for i in slips for k in i.get("move", [])) and not e, f"{placed} {e}")
    r = K.RawBoard()
    xs = K.lanes(r, 100, 200, 1200, 500, [("用户", "user"), ("程序", "program"), ("模型", "model")], 3.0)
    K.lane_msg(r, xs, 1, 2, 350, "ask(first)", 5.0)
    K.lane_msg(r, xs, 2, 1, 450, "OK, Ming!", 6.0, color="#15803D")
    arrows = [i for i in r.items if i.get("shape") == "arrow"]
    e, w = lint(r.items)
    check("kit: lanes (three headers, three lifelines) and two messages between them are lint-clean; the reply arrow points back", len(xs) == 3 and len(arrows) == 2 and arrows[0]["x2"] > arrows[0]["x1"] and arrows[1]["x2"] < arrows[1]["x1"] and not e, str(e + w))
    r = K.RawBoard()
    K.curve(r, 200, 300, 500, 300, [(0, 0.05), (0.3, 0.12), (0.6, 0.35), (1.0, 0.95)], 4.0)
    path = [i for i in r.items if i.get("shape") == "path"][0]
    e, w = lint(r.items)
    check("kit: the curve is ONE path stroke that draws along its length (4 points, 4 dots, 2 axes) and is lint-clean", path["d"].count("C") == 3 and sum(1 for i in r.items if i.get("shape") == "circle") == 4 and not e and not w, str(e + w))


def t_sfx():
    """docs/whiteboard_sfx.py: cue derivation from the boards, the quiz-silence rule, and a real mix on a synthetic narration (the silence stays bit-identical)."""
    import numpy as np
    import whiteboard_sfx as S
    note = lambda at, **kw: {"kind": "stroke", "shape": "path", "at": at, "dur": 0.4, "width": 0, "fill": "#E3CA9B", "shadow": True, "d": "M 0 0 Z", "box": [0, 0, 10, 10], **kw}
    props = {"cuts": [{"id": "K1", "in_seconds": 100.0, "whiteboard": {"items": [
        note(2.0), note(-10.0),                                                                       # a note appears / one that is already drawn
        note(3.0, layer="top", move=[{"at": 5.0, "dx": 0}, {"at": 6.2, "dx": 400}]),                    # a flying copy: a whoosh, no pop
        note(3.1, layer="top", move=[{"at": 5.3, "dx": 0}, {"at": 6.5, "dx": 400}]),                    # a second flight 0.3 s later: the same whoosh cluster
        {"kind": "stroke", "shape": "path", "at": 7.0, "width": 0, "fill": "#DC2626", "move": [{"at": 7.0, "sy": 0.02}, {"at": 8.0, "sy": 1}], "d": "M 0 0 Z"},   # a bar growing: no sound of its own
        {"kind": "write", "text": "x", "x": 1, "y": 1, "at": 9.0, "sfx": "sparkle"}]}}]}
    quiz = [{"section_id": "s2", "question_end": 120.0, "answer_not_before": 123.0}]
    cues = S.derive_cues(props, quiz)
    names = [(round(c["t"], 2), c["name"]) for c in cues]
    check("sfx: cues from the boards - pop for a note that appears (not for one already drawn, a top-layer copy or a growing bar), one whoosh for a cluster of flights, the explicit sfx field, a chime for the answer",
          names == [(102.05, "pop"), (104.98, "whoosh-short"), (109.0, "sparkle"), (123.3, "chime")], str(names))
    ln = S.lengths()
    kept, dropped = S.apply_quiz_rule([{"t": 121.0, "name": "pop", "gain_db": -18}, {"t": 119.8, "name": "chime", "gain_db": -16}, {"t": 130.0, "name": "pop", "gain_db": -18}], quiz, ln)
    check("sfx: a cue that starts in the quiz silence is dropped, one that would run into it is cut before it, one after it is kept",
          [c["t"] for c in dropped] == [121.0] and [(c["t"], c["cut_at"]) for c in kept] == [(119.8, 120.0), (130.0, None)], f"{kept} {dropped}")
    merged = S.derive_cues({"cuts": [{"id": "K1", "in_seconds": 0.0, "whiteboard": {"items": [note(2.0), note(2.04), note(2.5)]}}]}, [])
    check("sfx: two notes appearing in the same instant (within 80 ms) are one pop, not a doubled one", [round(c["t"], 2) for c in merged] == [2.05, 2.55], str(merged))
    cut_short = S.derive_cues({"cuts": [{"id": "K7a", "in_seconds": 100.0, "out_seconds": 105.0, "whiteboard": {"items": [
        note(2.0), note(6.0), note(3.0, layer="top", move=[{"at": 6.0, "dx": 0}, {"at": 7.0, "dx": 400}])]}}]}, [])
    check("sfx: items that start after the end of their cut (a board cut short for a video clip) make no sound", [(round(c["t"], 2), c["name"]) for c in cut_short] == [(102.05, "pop")], str(cut_short))
    loud = (0.85 * np.sin(2 * np.pi * 220 * np.arange(5 * S.SR) / S.SR)).astype(np.float32)
    cue_loud = [{"t": 1.0, "name": "chime", "gain_db": -6}]
    m_loud = S.mix(loud, cue_loud)
    check("sfx: a cue on top of a narration peak backs off so the mix stays below -1 dBFS (AAC overshoots)", float(np.max(np.abs(m_loud))) <= S.PEAK_LIMIT * 1.001 and "limited_to" in cue_loud[0], f"{float(np.max(np.abs(m_loud))):.4f} {cue_loud}")
    tmp = Path(tempfile.mkdtemp())
    try:
        rng = np.random.default_rng(7)
        t = np.arange(20 * S.SR) / S.SR
        narr = (rng.standard_normal(len(t)) * 0.05 * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t) ** 2)).astype(np.float32)
        narr[int(8 * S.SR):int(11.2 * S.SR)] = 0.0                                                      # the quiz silence: digital zeros
        cues = [{"t": 3.0, "name": "pop", "gain_db": -18}, {"t": 9.0, "name": "pop", "gain_db": -18}, {"t": 7.9, "name": "chime", "gain_db": -16}]
        kept, dropped = S.apply_quiz_rule(cues, [{"question_end": 8.0, "answer_not_before": 11.2}], ln)
        m1, m2 = S.mix(narr, kept), S.mix(narr, kept)
        sil = slice(int(8 * S.SR), int(11.2 * S.SR))
        check("sfx: the mix has the length of the narration, is deterministic, keeps the quiz silence bit-identical, changes the narration where a cue sits and stays below -1 dBFS",
              len(m1) == len(narr) and np.array_equal(m1, m2) and np.array_equal(m1[sil], narr[sil]) and not np.array_equal(m1[int(3 * S.SR):int(3.5 * S.SR)], narr[int(3 * S.SR):int(3.5 * S.SR)])
              and float(np.max(np.abs(m1))) < 0.89 and len(dropped) == 1, f"peak {float(np.max(np.abs(m1))):.3f}")
        S.write_wav(tmp / "n.wav", narr); S.write_wav(tmp / "m.wav", m1)
        r = sh(PY, "docs/whiteboard_sfx.py", "check", tmp / "n.wav", tmp / "m.wav")
        check("sfx: the check command finds the same silences in the narration and in the mix and a small loudness change", r.returncode == 0 and "silences identical: True" in r.stdout, r.stdout.strip().splitlines()[-1][:120])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_sfx_apply():
    """docs/whiteboard_sfx.py profiles (`light` = the answer chime + what a board names, `all`, `none`, a name list) and the lesson-facing `apply` / `apply --undo` on a temporary project."""
    import numpy as np
    import whiteboard_sfx as S
    note = lambda at, **kw: {"kind": "stroke", "shape": "path", "at": at, "dur": 0.4, "width": 0, "fill": "#E3CA9B", "shadow": True, "d": "M 0 0 Z", "box": [0, 0, 10, 10], **kw}
    items = [note(2.0), note(3.0, layer="top", move=[{"at": 5.0, "dx": 0}, {"at": 6.2, "dx": 400}]), {"kind": "write", "text": "x", "x": 1, "y": 1, "at": 9.0, "sfx": "sparkle"}]
    props = {"cuts": [{"id": "K1", "in_seconds": 0.0, "out_seconds": 30.0, "whiteboard": {"items": items}}]}
    quiz = [{"section_id": "s2", "question_end": 12.0, "answer_not_before": 15.2}]
    names = lambda w: [c["name"] for c in S.derive_cues(props, quiz, w)]
    check("sfx profiles: light = the answer chime + the cue a board names; all = also pop and whoosh; none = only the named one; a name list adds those names",
          names("light") == ["sparkle", "chime"] and names("all") == ["pop", "whoosh-short", "sparkle", "chime"] and names("none") == ["sparkle"] and names("pop") == ["pop", "sparkle"],
          f"{names('light')} {names('all')} {names('none')} {names('pop')}")
    tmp = Path(tempfile.mkdtemp())
    try:
        rng = np.random.default_rng(11)
        t = np.arange(24 * S.SR) / S.SR
        narr = (rng.standard_normal(len(t)) * 0.05 * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t) ** 2)).astype(np.float32)
        narr[int(12 * S.SR):int(15.2 * S.SR)] = 0.0
        (tmp / "assets/audio").mkdir(parents=True)
        plain = tmp / "assets/audio/narration_norm.wav"
        S.write_wav(plain, narr)
        (tmp / "assets/audio/narration_timeline.json").write_text(json.dumps({"quiz": quiz}), encoding="utf-8")
        p = dict(props, audio={"narration": {"src": str(plain), "volume": 1.0}})
        pp = tmp / "render_props.json"
        pp.write_text(json.dumps(p), encoding="utf-8")
        rc = S.apply(tmp, "light")
        a1 = json.loads(pp.read_text(encoding="utf-8"))["audio"]["narration"]
        check("sfx apply: the props narration points to assets/audio/narration_sfx.wav, the plain path is kept in src_plain, the mix exists, the silences were checked",
              rc == 0 and a1["src"] == str(tmp / "assets/audio/narration_sfx.wav") and a1["src_plain"] == str(plain) and (tmp / "assets/audio/narration_sfx.wav").exists(), str(a1))
        rc2 = S.apply(tmp, "all")
        a2 = json.loads(pp.read_text(encoding="utf-8"))["audio"]["narration"]
        check("sfx apply: a second run starts again from the plain narration (src_plain unchanged, never a mix of a mix)", rc2 == 0 and a2["src_plain"] == str(plain) and a2["src"] == a1["src"], str(a2))
        rc3 = S.apply(tmp, undo=True)
        a3 = json.loads(pp.read_text(encoding="utf-8"))["audio"]["narration"]
        check("sfx apply --undo: the props point to the plain narration again and src_plain is gone", rc3 == 0 and a3 == {"src": str(plain), "volume": 1.0}, str(a3))
        before = pp.read_text(encoding="utf-8")
        rc4 = S.apply(tmp, "light", max_change=-1)   # any loudness change exceeds a negative limit: the refusal path
        check("sfx apply: a mix that fails the check changes nothing in the props and says so", rc4 == 1 and pp.read_text(encoding="utf-8") == before, f"rc {rc4}")
        nq = dict(p, cuts=[{"id": "K1", "in_seconds": 0.0, "out_seconds": 30.0, "whiteboard": {"items": [note(2.0)]}}])
        pp.write_text(json.dumps(nq), encoding="utf-8")
        (tmp / "assets/audio/narration_timeline.json").write_text(json.dumps({"quiz": []}), encoding="utf-8")
        rc5 = S.apply(tmp, "light")
        check("sfx apply: a lesson with no cue in the profile (no quiz, nothing named) is left alone", rc5 == 0 and json.loads(pp.read_text(encoding="utf-8")) == nq, f"rc {rc5}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_h3_clip():
    """docs/whiteboard_h3_clip.py: `fit` makes any clip a lesson cut (1920x1080, 30 fps, no audio, EXACT frame count, the render chunks' stream format); `clip` hands the right arguments to the CLI."""
    import stat
    import whiteboard_h3_clip as H
    import whiteboard_render as wr
    tmp = Path(tempfile.mkdtemp())
    try:
        src = tmp / "raw.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1344x768:rate=24:duration=4.458", "-f", "lavfi", "-i", "sine=frequency=440:duration=4.458", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", str(src)], check=True)
        n1 = H.fit(src, tmp / "fit120.mp4", 120)                                  # a clip longer than the cut is cut
        short = tmp / "short.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", "2", "-c", "copy", str(short)], check=True)
        n2 = H.fit(short, tmp / "fit150.mp4", 150)                                # a clip shorter than the cut holds its last frame
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "csv=p=0", str(tmp / "fit120.mp4")], capture_output=True, text=True).stdout.split()
        sig = json.loads(wr.stream_sig(tmp / "fit120.mp4"))
        want = {"codec_name": "h264", "profile": "High", "level": 40, "pix_fmt": "yuvj420p", "color_range": "pc", "color_space": "bt470bg", "width": 1920, "height": 1080, "r_frame_rate": "30/1"}
        chunk = next(iter(sorted((ROOT / "projects/c-clinic-cn/renders/chunks").glob("K1-*.mp4"))), None) if have("projects/c-clinic-cn/renders/chunks") else None
        same_as_chunk = (wr.stream_sig(chunk) == wr.stream_sig(tmp / "fit120.mp4")) if chunk else True
        check("h3 clip: fit gives exactly the asked frames (cut 120 from 107, hold to 150 from 60), 1920x1080, no audio stream, and the render chunks' stream format (so `-c copy` joins it)",
              n1 == 120 and n2 == 150 and probe == ["video,1920,1080"] and all(sig.get(k) == v for k, v in want.items()) and same_as_chunk, f"{n1} {n2} {probe} {sig}")
        tb = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=time_base", "-of", "csv=p=0", str(tmp / "fit120.mp4")], capture_output=True, text=True).stdout.strip()
        check("h3 clip: fit writes the render chunks' time base (1/90000), so the concat join does not rescale timestamps", tb == "1/90000", tb)
        rec_args = tmp / "args.txt"
        cli = tmp / "fakeh3"
        cli.write_text("#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\na = sys.argv[1:]\nst = Path(os.environ['FAKE_STATE'])\n"
                       "if a[0] == 'submit':\n    Path(os.environ['FAKE_ARGS']).write_text(' '.join(a)); st.write_text('0'); print(json.dumps({'id': 'j1'}))\n"
                       "elif a[0] == 'get':\n    n = int(st.read_text()); st.write_text(str(n + 1)); print(json.dumps({'status': ['running', 'completed'][min(n, 1)]}))\n"
                       "elif a[0] == 'download':\n    Path(a[a.index('--output') + 1]).write_bytes(open(os.environ['FAKE_MP4'], 'rb').read())\n", encoding="utf-8")
        cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
        os.environ.update(OPENMONTAGE_H3_CLI=str(cli), FAKE_STATE=str(tmp / "st"), FAKE_ARGS=str(rec_args), FAKE_MP4=str(src))
        import whiteboard_pose_tool as PT
        keep = PT.time.sleep
        PT.time.sleep = lambda s: None
        try:
            H.main(["clip", str(tmp / "out.mp4"), "--image", "first.png", "--prompt-file", "p.txt", "--seconds", "5", "--seed", "7", "--reference", "r1.png", "--request-id", "req-h3"])
        finally:
            PT.time.sleep = keep
        a = rec_args.read_text()
        rec = json.loads((tmp / "out.mp4.json").read_text(encoding="utf-8"))
        check("h3 clip: `clip` passes mode, first frame, prompt, resolution, seconds, seed and references to the CLI with the request id, downloads the mp4 and writes the record",
              all(x in a for x in ("--request-id req-h3", "--mode h3_i2v", "--image first.png", "--prompt-file p.txt", "--resolution h3_landscape", "--seconds 5", "--seed 7", "--reference r1.png")) and (tmp / "out.mp4").exists() and rec["request_id"] == "req-h3", a)
    finally:
        for k in ("OPENMONTAGE_H3_CLI", "FAKE_STATE", "FAKE_ARGS", "FAKE_MP4"):
            os.environ.pop(k, None)
        shutil.rmtree(tmp, ignore_errors=True)


def t_video_clip_cut():
    """The `video_clip` cut of docs/whiteboard_render.py: a finished mp4 is one of the files the lesson is joined from (no Remotion render): fingerprint = file hash + range, exact frame count,
    stills and samples refuse to enter it."""
    import whiteboard_h3_clip as H
    import whiteboard_render as wr
    tmp = Path(tempfile.mkdtemp())
    try:
        raw = tmp / "raw.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(raw)], check=True)
        clip = tmp / "fit.mp4"
        H.fit(raw, clip, 30)
        wb = {"items": [], "pointer": []}
        props = {"cuts": [{"id": "K1", "in_seconds": 0.0, "out_seconds": 4.0, "type": "whiteboard", "whiteboard": wb}, {"id": "K2", "in_seconds": 4.0, "out_seconds": 5.0, "type": "video_clip", "video_clip": str(clip)},
                          {"id": "K3", "in_seconds": 5.0, "out_seconds": 8.0, "type": "whiteboard", "whiteboard": wb}], "captions": [], "overlays": []}
        pub = tmp / "pub"; pub.mkdir()
        chunks, total = wr.make_chunks(props, pub, "h")
        k2 = chunks[1]
        c = {**k2, "path": tmp / "K2.mp4"}
        wr.install_clip(c)
        raw2 = tmp / "raw2.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=2", "-vf", "hue=h=90", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(raw2)], check=True)
        clip2 = tmp / "fit2.mp4"
        H.fit(raw2, clip2, 30)
        props2 = json.loads(json.dumps(props)); props2["cuts"][1]["video_clip"] = str(clip2)
        fp2 = wr.make_chunks(props2, pub, "h")[0][1]["fp"]
        bad = {**k2, "to": k2["to"] + 5, "path": tmp / "K2bad.mp4"}
        try:
            wr.install_clip(bad); refused = False
        except SystemExit as e:
            refused = "needs 35" in str(e) and "--frames 35" in str(e)
        check("video_clip cut: its chunk is the clip file (range 4-5 s = 30 frames, copied into the cache), its fingerprint follows the file, a clip with the wrong frame count is refused with the fit command",
              k2["from"] == 120 and k2["to"] == 149 and k2.get("clip") == str(clip) and (tmp / "K2.mp4").exists() and fp2 != k2["fp"] and refused and total > 149, f"{k2} {fp2}")
        refused_still = bool(wr.clip_cuts_in(props, 4.2, 4.2 + 1e-6)) and not wr.clip_cuts_in(props, 5.0, 6.0) and bool(wr.clip_cuts_in(props, 3.5, 4.5))
        check("video_clip cut: stills and samples can ask which clip cuts a time range touches (and refuse), neighbouring boards are not touched", refused_still)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_prepend_sting():
    """docs/whiteboard_prepend_cover.py --sting: an animated opening before the still cover; duration, subtitles, chapters and metadata all shift by sting + cover."""
    import whiteboard_h3_clip as H
    from PIL import Image
    tmp = Path(tempfile.mkdtemp())
    try:
        P = tmp / "proj"
        for d in ("renders", "assets", "exports/thumbnails", "exports/metadata"):
            (P / d).mkdir(parents=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=4", "-f", "lavfi", "-i", "sine=frequency=330:duration=4:sample_rate=48000", "-ac", "2",
                        "-vf", "format=yuvj420p", "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuvj420p", "-c:a", "aac", "-shortest", str(P / "renders/final.mp4")], check=True)
        Image.new("RGB", (1920, 1080), (200, 30, 30)).save(P / "exports/thumbnails/cover.png")
        Image.new("RGB", (1280, 720), (200, 30, 30)).save(P / "exports/thumbnails/cover_1280x720.jpg")
        (P / "assets/subtitles.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nhello\n", encoding="utf-8")
        (P / "exports/metadata/metadata.json").write_text(json.dumps({"chapters": [{"start_seconds": 0, "title": "a"}, {"start_seconds": 2, "title": "b"}]}), encoding="utf-8")
        raw = tmp / "raw.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1344x768:rate=24:duration=1.2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(raw)], check=True)
        H.fit(raw, tmp / "sting.mp4", 30)                                                  # 1.0 s
        r = sh(PY, "docs/whiteboard_prepend_cover.py", P, "--sting", tmp / "sting.mp4")
        out = P / "exports/video/output.mp4"
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout) if out.exists() else 0
        meta = json.loads((P / "exports/metadata/metadata.json").read_text(encoding="utf-8")) if r.returncode == 0 else {}
        srt = (P / "exports/video/subtitles.srt").read_text(encoding="utf-8") if r.returncode == 0 else ""
        check("prepend cover --sting: opening 1.0 s + still cover 2.0 s + lesson 4.0 s, subtitles and chapters shifted by 3.0 s, the tool's own verification passes",
              r.returncode == 0 and abs(dur - 7.0) < 0.15 and "00:00:04,000 --> 00:00:05,000" in srt and meta.get("cover_seconds") == 3.0 and meta.get("sting_seconds") == 1.0
              and [c["start_seconds"] for c in meta["chapters"]] == [0, 5.0], f"{dur:.2f} s {r.stdout[-100:]} {r.stderr[-200:]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
    for t in (t_last_item, t_thumb, t_script_lint, t_lint_mixed, t_layout_rules, t_v2_fields, t_board_v2, t_pose_tool, t_cover_series, t_scene_plan_devices, t_kit_devices, t_sfx, t_sfx_apply, t_h3_clip, t_video_clip_cut, t_prepend_sting, t_callbacks, t_gate, t_gate_experiment, t_wait, t_new_lesson, t_series, t_registry):
        try:
            t()
        except Exception as e:  # a crashing test is a failing test
            check(t.__name__ + " crashed", False, repr(e)[:120])
    for t in (t_layout_probe_slow, t_composer_baseline_slow, t_verify):
        try:
            t(slow)
        except Exception as e:
            check(t.__name__ + " crashed", False, repr(e)[:120])
    bad = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed" + (f"; FAILED: {[b[0] for b in bad]}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
