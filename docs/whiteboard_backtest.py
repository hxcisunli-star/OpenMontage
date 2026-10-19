#!/usr/bin/env python3
"""Backtests for the whiteboard tools: every check must flag a KNOWN past case and pass the lessons that were fine - a check that has never caught anything has not been shown to work.
Run (repo root):  .venv/bin/python docs/whiteboard_backtest.py [--slow]        exit code 1 if any test fails
Fast tests (seconds) use the published lessons' own data, never modify them (scratch copies in a temp dir); --slow also runs the full compose verifier on a scratch copy of
lesson 43's final video (about 40 s) and checks its numbers against the ones typed by hand in 2026-10 (414.967 s, 12449 frames, -16.0 LUFS, silences, md5).
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
    check("gate: status on the real projects says nothing is in progress", "没有进行中的课程" in r.stdout)


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
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_registry():
    r = sh(PY, "docs/whiteboard_registry.py", "coverage")
    check("registry: every playbook row and handoff note clause is mapped (0 unmapped)", r.returncode == 0 and "未映射共 0 条" in r.stdout)
    r = sh(PY, "docs/whiteboard_registry.py", "check")
    check("registry: stage checklists match the registry", r.returncode == 0)


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
    for t in (t_last_item, t_thumb, t_script_lint, t_lint_mixed, t_callbacks, t_gate, t_wait, t_new_lesson, t_registry):
        try:
            t()
        except Exception as e:  # a crashing test is a failing test
            check(t.__name__ + " crashed", False, repr(e)[:120])
    try:
        t_verify(slow)
    except Exception as e:
        check("t_verify crashed", False, repr(e)[:120])
    bad = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed" + (f"; FAILED: {[b[0] for b in bad]}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
