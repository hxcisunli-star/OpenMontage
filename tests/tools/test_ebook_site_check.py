"""Small, self-contained tests for check_site.py.

The fixture deliberately mirrors the public DOM contract while staying tiny:
three units in two books, one complete chapter and two honest placeholders.
"""
import json
import hashlib
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2] / "docs/whiteboard/ebook"       # the checker lives next to the platform (check_site.py)
sys.path.insert(0, str(ROOT))
import check_site


SHELF_BOOK = '<div class="book"><div class="cover"><img class="cover-art" src="assets/covers/%s.jpg" alt="蓝色封面的一本书，机器人在挥手"><div class="plate"><div class="bk-t">%s</div></div></div></div>'


class SiteCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = pathlib.Path(cls.tmp.name)
        cls.base_site = cls.work / "site"
        cls.base_repo = cls.work / "repo"
        cls.make_fixture(cls.base_site, cls.base_repo)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def make_fixture(cls, site, repo):
        # Data root
        (repo / "projects/_ebook/chapters").mkdir(parents=True)
        (repo / "projects/agent-what-is-llm-cn/validation").mkdir(parents=True)
        (repo / "projects/agent-what-is-llm-cn/artifacts").mkdir(parents=True)
        (repo / "projects/agent-what-is-llm-cn/exports/metadata").mkdir(parents=True)
        (repo / "projects/_ebook/books.yaml").write_text("""series:\n  name: 小站\nbooks:\n  - id: b1\n    title: 基础\n    stages: [S1]\n  - id: b2\n    title: 实践\n    stages: [S2]\n""", encoding="utf-8")
        outline = {
            "unit_count": 3,
            "stages": [
                {"id": "S1", "units": [
                    {"id": "S1-U01", "title": "认识基础", "goal": "认识基础概念。", "prereq": []},
                    {"id": "S1-U02", "title": "掌握前置", "goal": "掌握前置知识。", "prereq": ["S1-U01"]},
                ]},
                {"id": "S2", "units": [
                    {"id": "S2-U01", "title": "完整一章", "goal": "掌握完整内容。", "prereq": ["S1-U02"]},
                ]},
            ],
        }
        (repo / "projects/_ebook/outline.json").write_text(json.dumps(outline, ensure_ascii=False), encoding="utf-8")
        chapter = {
            "id": "S2-U01", "lesson_title": "同一个问题问三遍", "basic_question": "为什么答案会变？",
            "takeaway": ["先观察", "再核对"],
            "video": {"file": "projects/agent-what-is-llm-cn/exports/video/output.mp4", "poster": "unused.jpg", "duration": 2.0,
                      "chapters": [{"start": 0, "title": "开始"}, {"start": 1, "title": "继续"}]},
            "frames": [{"src": "unused.jpg", "sec": "one", "seek": 0.5, "alt": "一张测试图", "narr": "旁白中的一句话"}],
            "sections": [{"id": "one", "title": "第一节", "blocks": [{"t": "think"}]}],
            "points": [{"id": "p1", "text": "覆盖点", "sections": ["one"]}],
            "readings": [{"title": "资料", "url": "https://example.test/read"}],
            "downloads": [{"file": "projects/x/example.txt"}],
        }
        (repo / "projects/_ebook/chapters/S2-U01.json").write_text(json.dumps(chapter, ensure_ascii=False), encoding="utf-8")
        records = {"R%d" % i: {"kind": "labels", "model": "vendor/model", "date": "2026-01-01", "mode": "默认", "n": 2} for i in range(1, 7)}
        (repo / "projects/agent-what-is-llm-cn/validation/records.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        claims = {"sourced": [{"id": "U1", "statement": "这是来源事实。", "scope": "仅用于测试。"}]}
        (repo / "projects/agent-what-is-llm-cn/validation/claims_used.json").write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")
        script = {"sections": [{"text": "旁白中的一句话。"}]}
        (repo / "projects/agent-what-is-llm-cn/artifacts/script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
        (repo / "projects/agent-what-is-llm-cn/exports/metadata/exercises.txt").write_text("练习一【测试】\n请回答一个问题。\n答案：\n这是答案。\n你的学习记录\n", encoding="utf-8")

        # Site files and generated media
        for d in ("assets/fonts", "assets/img", "books/b1", "books/b2", "media/S2-U01/frames", "downloads"):
            (site / d).mkdir(parents=True, exist_ok=True)
        (site / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        (site / "assets/book.css").write_text("body{font-family:test}", encoding="utf-8")
        (site / "assets/book.js").write_text("window.OK=true;", encoding="utf-8")
        (site / "assets/fonts/FONT-LICENSE.txt").write_text("SIL Open Font License", encoding="utf-8")
        (site / "assets/fonts/test.ttf").write_bytes(b"\0font")
        (site / "downloads/example.txt").write_text("download", encoding="utf-8")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=640x480:r=25", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2", "-shortest", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(site / "media/S2-U01/lesson.mp4")], check=True)
        (repo / "projects/agent-what-is-llm-cn/exports/video").mkdir(parents=True, exist_ok=True)
        shutil.copy2(site / "media/S2-U01/lesson.mp4", repo / "projects/agent-what-is-llm-cn/exports/video/output.mp4")      # the lesson's original: the page must play exactly this file
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=640x480", "-frames:v", "1", str(site / "media/S2-U01/frames/f01.jpg")], check=True)
        (site / "assets/covers").mkdir(parents=True, exist_ok=True)
        for bid in ("b1", "b2"):
            cls.make_image(site / "assets/covers" / (bid + ".jpg"), 900, 1200)
        for name in ("teacher.png", "robot.png"):
            shutil.copyfile(site / "media/S2-U01/frames/f01.jpg", site / "assets/img" / name)
        (site / "assets/search-index.js").write_text("window.SEARCH_INDEX = " + json.dumps([
            {"id": "S1-U01", "b": "b1", "n": 1, "w": False},
            {"id": "S1-U02", "b": "b1", "n": 2, "w": False},
            {"id": "S2-U01", "b": "b2", "n": 1, "w": True, "x": "摘录"},
        ], ensure_ascii=False) + ";", encoding="utf-8")

        def head(title):
            return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>%s</title><meta name="viewport" content="width=device-width"><meta name="robots" content="noindex, nofollow"><link rel="stylesheet" href="../../assets/book.css"></head><body>' % title
        def nav(unit, all_units, bid):
            i = all_units.index(unit)
            prev = '<span>← 上一章：没有了</span>' if i == 0 else '<a href="%s.html">← 上一章</a>' % all_units[i - 1]
            nxt = '<span>下一章：没有了</span>' if i == len(all_units) - 1 else '<a href="%s.html">下一章 →</a>' % all_units[i + 1]
            return '<nav class="crumbs"><a href="../../index.html">书架</a><a href="index.html">本册</a></nav><nav class="chapter-nav">%s<a href="index.html">本册目录</a>%s</nav>' % (prev, nxt)
        def placeholder(unit, goal, prereq, bid, units):
            link = ('<a class="pre" href="%s.html">前置</a>' % prereq) if prereq else ''
            return head(unit) + '<nav class="crumbs"><a href="../../index.html">书架</a><a href="index.html">本册</a></nav><div class="callout warn"><p>正文还在制作中。%s</p>%s</div>' % (goal, link) + nav(unit, units, bid) + '</body></html>'
        (site / "books/b1/S1-U01.html").write_text(placeholder("S1-U01", "认识基础概念。", "", "b1", ["S1-U01", "S1-U02"]), encoding="utf-8")
        (site / "books/b1/S1-U02.html").write_text(placeholder("S1-U02", "掌握前置知识。", "S1-U01", "b1", ["S1-U01", "S1-U02"]), encoding="utf-8")
        shows = "".join('<figure class="show" data-record="R%d"><figcaption class="rec"><span class="tag tag-shice">实测</span> model 2026-01-01 默认 2 遍</figcaption></figure>' % i for i in range(1, 7))
        source_page = head("完整一章") + '''<nav class="crumbs"><a href="../../index.html">书架</a><a href="index.html">本册</a></nav><main class="main" data-unit="S2-U01"><h1>完整一章</h1><p class="lesson-title">同一个问题问三遍</p><div class="basic">为什么答案会变？</div><div class="takeaway"><ul><li>先观察</li><li>再核对</li></ul></div>
<video id="lesson-video" controls preload="metadata" playsinline poster="../../media/S2-U01/frames/f01.jpg" data-duration="2"><source src="../../media/S2-U01/lesson.mp4" type="video/mp4"></video><nav class="chapters"><button class="seek" data-seek="0">开始</button><button class="seek" data-seek="1">继续</button></nav>
<figure class="frame-fig"><a class="frame" data-seek="0.5" href="#lesson-video"><img src="../../media/S2-U01/frames/f01.jpg" alt="一张测试图"></a><figcaption><q class="narr">旁白中的一句话</q></figcaption></figure>
<section class="sec" id="sec-one"><h2>第一节</h2><p>内容块</p></section>''' + shows + '''<aside class="fact" data-claim="U1"><span class="tag tag-source">来源说</span>这是来源事实。适用范围：仅用于测试。<a class="src-link" href="https://example.test/fact" target="_blank" rel="noopener">example.test/fact</a></aside>
<div class="term"><b class="word">比喻</b><span class="tag tag-metaphor">比喻</span><p class="gap">这里是六个汉字说明</p></div><details class="think"><summary>想一想</summary>记录</details><section id="exercises"><article class="exercise" data-ex="1"><div class="q">请回答一个问题。</div><details class="answer"><summary>答案</summary>这是答案。</details></article></section>
<details id="evidence">R1 R2 R3 R4 R5 R6 U1 录制日期是 2026-01-01</details><details id="coverage"><a href="#sec-one">p1</a></details><details id="readings"><a class="src-link" href="https://example.test/read" target="_blank" rel="noopener">example.test/read</a></details><div id="downloads"><a href="../../downloads/example.txt">下载</a></div></main>''' + nav("S2-U01", ["S2-U01"], "b2") + '</body></html>'
        # The generated lab fixture exercises the complete page contract.
        lab_spec = {
            "id": "demo-lab", "title": "小练习", "goal": "输出一行文字。",
            "starter": "print('好')", "prelude": "", "tests": [
                {"id": "one-line", "name": "输出一行", "code": "assert STDOUT == '好\\n'"},
            ], "hints": ["先运行起始代码。"], "solution": "print('好')",
            "timeout": 3, "seed": None, "optional": True,
        }
        lab_json = json.dumps(lab_spec, ensure_ascii=False, separators=(",", ":"))
        lab_markup = '''<section class="lab" id="lab-demo-lab" data-lab-id="demo-lab" data-lab-state="idle" data-paste-guard="allow" data-assets-root="../../assets/">
<header class="lab-head"><span class="lab-tag">选做，视频里没有</span><h3 class="lab-title">小练习</h3><span class="lab-done" id="lab-demo-lab-done" hidden>已完成 ✓</span></header>
<p class="lab-goal">输出一行文字。</p><script type="application/json" class="lab-spec">%s</script>
<div class="lab-preview" id="lab-demo-lab-preview"><pre class="lab-starter"><code>print('好')</code></pre><div class="lab-actions"><button type="button" class="lab-btn lab-btn-main" id="lab-demo-lab-start" data-action="start">开始练习</button></div></div>
<p class="lab-note" id="lab-demo-lab-note" hidden></p><div class="lab-work" id="lab-demo-lab-work" hidden><div class="lab-bar">
<button type="button" class="lab-btn lab-btn-main" id="lab-demo-lab-run" data-action="run" title="Ctrl+Enter">运行</button><button type="button" class="lab-btn" id="lab-demo-lab-check" data-action="check">运行并检查</button><button type="button" class="lab-btn" id="lab-demo-lab-stop" data-action="stop" hidden>停止</button><button type="button" class="lab-btn" id="lab-demo-lab-reset" data-action="reset">重置</button><button type="button" class="lab-btn" id="lab-demo-lab-hint" data-action="hint" hidden>提示</button><span class="lab-status" id="lab-demo-lab-status" role="status" aria-live="polite"></span></div>
<div class="lab-editor" id="lab-demo-lab-editor" data-editor-for="demo-lab"></div><div class="lab-toast" id="lab-demo-lab-toast" role="status" hidden></div><div class="lab-hints" id="lab-demo-lab-hints"></div><pre class="lab-out" id="lab-demo-lab-stdout" aria-label="输出"></pre><pre class="lab-err" id="lab-demo-lab-error" hidden></pre><ul class="lab-checks" id="lab-demo-lab-checks"></ul><div class="lab-solution-wrap"><button type="button" class="lab-btn" id="lab-demo-lab-solution-btn" data-action="solution" hidden>参考写法</button><div class="lab-solution" id="lab-demo-lab-solution" hidden><pre><code></code></pre></div></div></div></section>''' % lab_json
        source_page = source_page.replace("</main>", lab_markup + "</main>")
        source_page = source_page.replace("</body>", '<script defer src="../../assets/lab-guard.js"></script><script defer src="../../assets/lab-core.js"></script><script defer src="../../assets/lab.js"></script></body>')
        (site / "assets/lab-config.json").write_text('{"block_paste":false}', encoding="utf-8")
        for name, content in {
            "lab.js": "window.lab = true;",
            "lab-core.js": "window.core = true;",
            "lab-guard.js": "window.guard = true;",
            "lab-worker.js": "self.onmessage = function () {};",
            "lab-runner.py": "def run_request(*args):\n    return {}\n",
        }.items():
            (site / "assets" / name).write_text(content, encoding="utf-8")

        vendor = site / "assets/vendor"
        (vendor / "monaco").mkdir(parents=True, exist_ok=True)
        (vendor / "monaco/vs").mkdir(parents=True, exist_ok=True)
        (vendor / "pyodide").mkdir(parents=True, exist_ok=True)
        (vendor / "monaco/LICENSE").write_text("MIT", encoding="utf-8")
        (vendor / "monaco/vs/loader.js").write_text("loader", encoding="utf-8")
        (vendor / "pyodide/LICENSE").write_text("MPL-2.0", encoding="utf-8")
        manifest_lines = []
        for path in sorted(p for p in vendor.rglob("*") if p.is_file()):
            rel = path.relative_to(vendor).as_posix()
            manifest_lines.append("%s  %s" % (hashlib.sha256(path.read_bytes()).hexdigest(), rel))
        (vendor / "MANIFEST.sha256").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
        (vendor / "VERSIONS.json").write_text(json.dumps({
            "monaco-editor": {"version": "0.52.0", "integrity": "sha512-fixture"},
            "pyodide": {"version": "0.27.0", "integrity": "sha512-fixture"},
        }), encoding="utf-8")

        (site / "books/b2/S2-U01.html").write_text(source_page, encoding="utf-8")

        def book_index(bid, units):
            lis = ''.join('<li data-unit="%s"><a href="%s.html"><span class="chip-path">路径</span><span class="chip-st %s">%s</span></a></li>' % (u, u, "on" if u == "S2-U01" else "off", "有正文" if u == "S2-U01" else "正文制作中") for u in units)
            return head("册目录") + '<img class="cover-art" src="../../assets/covers/%s.jpg" alt="这一册的封面插画：机器人在挥手">' % bid + '<div class="eyebrow">共 %d 章</div><ul>%s</ul></body></html>' % (len(units), lis)
        (site / "books/b1/index.html").write_text(book_index("b1", ["S1-U01", "S1-U02"]), encoding="utf-8")
        (site / "books/b2/index.html").write_text(book_index("b2", ["S2-U01"]), encoding="utf-8")
        (site / "index.html").write_text(head("书架").replace('../../assets/book.css', 'assets/book.css') + '<a class="book-card" href="books/b1/index.html" data-units="S1-U01,S1-U02">' + SHELF_BOOK % ("b1", "第一册") + '</a><a class="book-card" href="books/b2/index.html" data-units="S2-U01">' + SHELF_BOOK % ("b2", "第二册") + '</a></body></html>', encoding="utf-8")

    @staticmethod
    def make_image(path, w, h):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=orange:s=%dx%d" % (w, h), "-frames:v", "1", str(path)], check=True)

    def run_case(self, mutate=None, probe=False):
        case = self.work / ("case-%d" % len(list(self.work.glob("case-*"))))
        site, repo = case / "site", case / "repo"
        shutil.copytree(self.base_site, site)
        shutil.copytree(self.base_repo, repo)
        if mutate:
            mutate(site, repo)
        report = case / "report.json"
        cmd = [sys.executable, str(ROOT / "check_site.py"), "--site", str(site), "--repo", str(repo), "--report", str(report)]
        if not probe:
            cmd.append("--no-video-probe")
        done = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return done, json.loads(report.read_text(encoding="utf-8"))

    def assert_fails(self, rule, mutate):
        done, result = self.run_case(mutate)
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(rule, result["failed"], result)

    @staticmethod
    def rewrite_vendor_manifest(site):
        vendor = site / "assets/vendor"
        lines = []
        for path in sorted(p for p in vendor.rglob("*") if p.is_file() and p.name not in {"MANIFEST.sha256", "VERSIONS.json"}):
            lines.append("%s  %s" % (hashlib.sha256(path.read_bytes()).hexdigest(), path.relative_to(vendor).as_posix()))
        (vendor / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_vendor_pinned_failure_paths(self):
        def omit_manifest_entry(site, repo):
            path = site / "assets/vendor/MANIFEST.sha256"
            lines = path.read_text(encoding="utf-8").splitlines()
            path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")

        cases = [
            ("missing manifest", lambda s, r: (s / "assets/vendor/MANIFEST.sha256").unlink()),
            ("manifest omits file", omit_manifest_entry),
            ("hash mismatch", lambda s, r: (s / "assets/vendor/monaco/LICENSE").write_text("changed", encoding="utf-8")),
            ("missing monaco license", lambda s, r: (s / "assets/vendor/monaco/LICENSE").unlink()),
            ("missing pyodide license", lambda s, r: (s / "assets/vendor/pyodide/LICENSE").unlink()),
            ("versions field missing", lambda s, r: (s / "assets/vendor/VERSIONS.json").write_text(json.dumps({"pyodide": {"version": "0.27", "integrity": "sha512-x"}}), encoding="utf-8")),
        ]
        for name, mutate in cases:
            with self.subTest(case=name):
                self.assert_fails("vendor-pinned", mutate)

    def test_labs_failure_paths(self):
        def edit_chapter(site, fn):
            page = site / "books/b2/S2-U01.html"
            page.write_text(fn(page.read_text(encoding="utf-8")), encoding="utf-8")

        cases = [
            ("missing button id", lambda s, r: edit_chapter(s, lambda t: t.replace('id="lab-demo-lab-start"', "", 1))),
            ("invalid spec json", lambda s, r: edit_chapter(s, lambda t: re.sub(r'(<script type="application/json" class="lab-spec">).*?(</script>)', r'\1{bad\2', t, count=1, flags=re.S))),
            ("spec field missing", lambda s, r: edit_chapter(s, lambda t: t.replace('"optional":true', '"optional_missing":true', 1))),
            ("duplicate lab id", lambda s, r: edit_chapter(s, lambda t: t.replace('</main>', re.search(r'(<section class="lab".*?</div></div></section>)', t, re.S).group(1) + '</main>', 1))),
            ("lab.js not loaded", lambda s, r: edit_chapter(s, lambda t: t.replace('<script defer src="../../assets/lab.js"></script>', "", 1))),
            ("nonlab page loads lab.js", lambda s, r: (s / "books/b1/S1-U01.html").write_text((s / "books/b1/S1-U01.html").read_text(encoding="utf-8").replace('</body>', '<script defer src="../../assets/lab.js"></script></body>'), encoding="utf-8")),
            ("config missing", lambda s, r: (s / "assets/lab-config.json").unlink()),
            ("config nonboolean", lambda s, r: (s / "assets/lab-config.json").write_text('{"block_paste":"false"}', encoding="utf-8")),
            ("js external text", lambda s, r: (s / "assets/lab.js").write_text('fetch("https://bad.example/");', encoding="utf-8")),
            ("innerHTML", lambda s, r: (s / "assets/lab.js").write_text('node.innerHTML = "x";', encoding="utf-8")),
            ("page direct pyodide", lambda s, r: edit_chapter(s, lambda t: t.replace('</main>', '<script src="../../assets/vendor/pyodide/pyodide.js"></script></main>', 1))),
            ("page inline monaco", lambda s, r: edit_chapter(s, lambda t: t.replace('</main>', '<script>var m = window.monaco;</script></main>', 1))),
        ]
        for name, mutate in cases:
            with self.subTest(case=name):
                self.assert_fails("labs", mutate)

    def test_vendor_text_is_excluded_from_content_scans(self):
        def mutate(site, repo):
            path = site / "assets/vendor/monaco/vs/loader.js"
            path.write_text('fetch("https://vendor.example/library.js");', encoding="utf-8")
            self.rewrite_vendor_manifest(site)
        done, result = self.run_case(mutate)
        self.assertEqual(done.returncode, 0, result)
        for rule in ("no-external-load", "no-claude-runtime", "no-secret-or-path", "no-experiment-labels"):
            self.assertNotIn(rule, result["failed"], result)

    def test_no_labs_no_vendor_skips_new_rules(self):
        def mutate(site, repo):
            page = site / "books/b2/S2-U01.html"
            text = page.read_text(encoding="utf-8")
            text = re.sub(r'<section class="lab".*?</div></div></section>', "", text, count=1, flags=re.S)
            text = text.replace('<script defer src="../../assets/lab-guard.js"></script>', "")
            text = text.replace('<script defer src="../../assets/lab-core.js"></script>', "")
            text = text.replace('<script defer src="../../assets/lab.js"></script>', "")
            page.write_text(text, encoding="utf-8")
            shutil.rmtree(site / "assets/vendor")
        done, result = self.run_case(mutate)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("vendor-pinned", result["failed"], result)
        self.assertNotIn("labs", result["failed"], result)

    def test_course_text_may_mention_the_editors(self):
        # the outline's front-end chapters talk about Monaco and Pyodide: words in the text are not a reference
        def mutate(site, repo):
            page = site / "books/b2/S2-U01.html"
            page.write_text(page.read_text(encoding="utf-8").replace("</main>", "<p>代码编辑器（Monaco）和浏览器里的 Pyodide 是两回事。</p></main>", 1), encoding="utf-8")
        done, result = self.run_case(mutate)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("labs", result["failed"], result)

    def test_lab_that_is_not_optional_has_no_tag(self):
        def mutate(site, repo):
            page = site / "books/b2/S2-U01.html"
            text = page.read_text(encoding="utf-8").replace('"optional":true', '"optional":false', 1)
            page.write_text(re.sub(r'<span class="lab-tag">.*?</span>', "", text, count=1, flags=re.S), encoding="utf-8")
        done, result = self.run_case(mutate)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("labs", result["failed"], result)

    def test_valid_fixture_passes(self):
        done, result = self.run_case()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(result["pass"], result)

    def test_video_probe_passes(self):
        done, result = self.run_case(probe=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        by_id = {c["id"]: c for c in result["checks"]}
        self.assertTrue(by_id["ch-video"]["ok"] and by_id["ch-video-stream"]["ok"], (by_id["ch-video"], by_id["ch-video-stream"]))

    def test_there_is_no_whole_site_size_cap(self):
        """2026-11-06: the lessons go online with their original videos, so a site far bigger than the old 300 MB cap passes; only a single html over 3 MB fails (test_site_rule_failures)."""
        def big_media(site, repo):
            with open(site / "media/S2-U01/big.bin", "wb") as f:
                f.truncate(310 * 1024 * 1024)          # a sparse file: no disk space is used
        done, result = self.run_case(big_media)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        size_rule = next(c for c in result["checks"] if c["id"] == "size-limits")
        self.assertTrue(size_rule["ok"] and "不设大小上限" in size_rule["detail"], size_rule)

    def test_chapter_video_must_be_the_streamable_original(self):
        orig = lambda repo: repo / "projects/agent-what-is-llm-cn/exports/video/output.mp4"

        def not_the_original(site, repo):                # a re-encoded "web copy" differs from the original
            p = site / "media/S2-U01/lesson.mp4"
            p.write_bytes(p.read_bytes() + b"\0")

        def source_points_elsewhere(site, repo):         # the chapter source names a file that is not a lesson's output.mp4
            f = repo / "projects/_ebook/chapters/S2-U01.json"
            d = json.loads(f.read_text(encoding="utf-8"))
            d["video"]["file"] = "projects/agent-what-is-llm-cn/exports/video/book_web.mp4"
            f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

        def moov_behind_the_data(site, repo):            # the same file in both places, but the header sits behind the data: no playback before the download ends
            src, tmp = site / "media/S2-U01/lesson.mp4", site.parent / "nofast.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-c", "copy", str(tmp)], check=True)
            types = [b[0] for b in check_site.SiteChecker.mp4_boxes(tmp)]
            self.assertLess(types.index("mdat"), types.index("moov"), types)        # the fixture really has its header behind the data
            shutil.copy2(tmp, src)
            shutil.copy2(tmp, orig(repo))

        def dotdot_in_the_lesson_folder(site, repo):     # "projects/../exports/..." is not a lesson folder
            f = repo / "projects/_ebook/chapters/S2-U01.json"
            d = json.loads(f.read_text(encoding="utf-8"))
            d["video"]["file"] = "projects/../exports/video/output.mp4"
            f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            (repo / "exports/video").mkdir(parents=True)                       # the file really exists there and has the same bytes: only the shape of the path can refuse it
            shutil.copy2(orig(repo), repo / "exports/video/output.mp4")

        def lesson_folder_is_a_link(site, repo):         # the same bytes, but reached through a symbolic link (could point anywhere on the disk)
            outside = repo.parent / "outside"
            outside.mkdir()
            shutil.move(str(repo / "projects/agent-what-is-llm-cn"), str(outside / "agent-what-is-llm-cn"))
            (repo / "projects/agent-what-is-llm-cn").symlink_to(outside / "agent-what-is-llm-cn")

        def box(kind, payload=b""):
            return (8 + len(payload)).to_bytes(4, "big") + kind + payload

        def cut_off_file(site, repo):                    # ftyp, moov, and an mdat that claims 100 bytes in a 24-byte file: the same scribble in both places
            data = box(b"ftyp") + box(b"moov") + (100).to_bytes(4, "big") + b"mdat" + b"\0" * 4
            (site / "media/S2-U01/lesson.mp4").write_bytes(data)
            orig(repo).write_bytes(data)

        for label, mutate in (("not the original", not_the_original), ("source points elsewhere", source_points_elsewhere), ("moov behind mdat", moov_behind_the_data),
                              ("dotdot in the lesson folder", dotdot_in_the_lesson_folder), ("lesson folder is a symbolic link", lesson_folder_is_a_link), ("cut-off file", cut_off_file)):
            with self.subTest(label):
                self.assert_fails("ch-video-stream", mutate)

    def test_mp4_box_scan_is_not_fooled_by_many_leading_boxes_and_stops_at_the_data(self):
        box = lambda kind, payload=b"": (8 + len(payload)).to_bytes(4, "big") + kind + payload
        good = box(b"ftyp", b"isom\0\0\0\0") + b"".join(box(b"free") for _ in range(30)) + box(b"moov", b"x" * 8) + box(b"mdat", b"y" * 8) + box(b"free", b"z" * 1000)
        path = self.work / "many-free.mp4"
        path.write_bytes(good)
        types = [b[0] for b in check_site.SiteChecker.mp4_boxes(path)]
        self.assertEqual(types[:1], ["ftyp"])
        self.assertLess(types.index("moov"), types.index("mdat"))
        self.assertNotIn("!broken", types)
        path.write_bytes(box(b"ftyp") + (10 ** 6).to_bytes(4, "big") + b"mdat")                  # the claimed size runs past the end of the file
        self.assertEqual([b[0] for b in check_site.SiteChecker.mp4_boxes(path)], ["ftyp", "!broken"])
        path.write_bytes(box(b"ftyp") + b"\x00\x00")                                                # a header cut off in the middle
        self.assertEqual([b[0] for b in check_site.SiteChecker.mp4_boxes(path)], ["ftyp", "!broken"])
        path.write_bytes((1).to_bytes(4, "big") + b"mdat" + b"\x00\x00")                         # 64-bit size announced, but the 8 size bytes are missing
        self.assertEqual([b[0] for b in check_site.SiteChecker.mp4_boxes(path)], ["!broken"])

    def test_the_chapter_video_has_exactly_one_mp4_source(self):
        def second_source(site, repo):
            page = site / "books/b2/S2-U01.html"
            text = page.read_text(encoding="utf-8")
            assert "</video>" in text
            page.write_text(text.replace("</video>", '<source src="../../media/S2-U01/lesson.mp4" type="video/mp4"></video>', 1), encoding="utf-8")

        def wrong_type(site, repo):
            page = site / "books/b2/S2-U01.html"
            page.write_text(page.read_text(encoding="utf-8").replace('type="video/mp4"', 'type="video/unknown"', 1), encoding="utf-8")
        for label, mutate in (("second source", second_source), ("wrong type", wrong_type)):
            with self.subTest(label):
                self.assert_fails("ch-video", mutate)

    def test_chapter_video_codecs_are_checked_with_ffprobe(self):
        def mpeg4_video(site, repo):                     # identical in both places and streamable, but not H.264
            tmp = site.parent / "mpeg4.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=640x480:r=25", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2", "-shortest",
                            "-c:v", "mpeg4", "-c:a", "aac", "-movflags", "+faststart", str(tmp)], check=True)
            shutil.copy2(tmp, site / "media/S2-U01/lesson.mp4")
            shutil.copy2(tmp, repo / "projects/agent-what-is-llm-cn/exports/video/output.mp4")
        done, result = self.run_case(mpeg4_video, probe=True)
        self.assertIn("ch-video-stream", result["failed"], result)

    def test_yaml_parser_reads_real_data(self):
        books = ROOT.parents[2] / "projects/_ebook/books.yaml"
        if not books.is_file():
            self.skipTest("projects/_ebook/books.yaml is not in this checkout")
        parsed = check_site.parse_books_yaml(books)
        self.assertEqual(len(parsed["books"]), 8)
        self.assertEqual(parsed["series"]["name"], "智能体拆拆装装")

    def test_site_rule_failures(self):
        cases = [
            ("site-files", lambda s, r: (s / "robots.txt").write_text("", encoding="utf-8")),
            ("books-complete", lambda s, r: (s / "books/b1/index.html").write_text((s / "books/b1/index.html").read_text(encoding="utf-8").replace('data-unit="S1-U02"', 'data-unit="S1-U99"'), encoding="utf-8")),
            ("chapter-pages", lambda s, r: (s / "books/b1/S1-U01.html").unlink()),
            ("placeholders-honest", lambda s, r: (s / "books/b1/S1-U02.html").write_text((s / "books/b1/S1-U02.html").read_text(encoding="utf-8").replace("掌握前置知识。", ""), encoding="utf-8")),
            ("prereq-links", lambda s, r: (s / "books/b1/S1-U02.html").write_text((s / "books/b1/S1-U02.html").read_text(encoding="utf-8").replace("S1-U01.html", "missing.html"), encoding="utf-8")),
            ("search-index", lambda s, r: (s / "assets/search-index.js").write_text("window.SEARCH_INDEX = [];", encoding="utf-8")),
            ("no-external-load", lambda s, r: (s / "index.html").write_text((s / "index.html").read_text(encoding="utf-8").replace("</head>", '<link rel="stylesheet" href="https://bad.example/x.css"></head>'), encoding="utf-8")),
            ("no-claude-runtime", lambda s, r: (s / "assets/book.js").write_text("window.claude.use();", encoding="utf-8")),
            ("no-secret-or-path", lambda s, r: (s / "assets/book.js").write_text("/home/private", encoding="utf-8")),
            ("no-experiment-labels", lambda s, r: (s / "assets/book.js").write_text("试验品", encoding="utf-8")),
            ("relative-links-resolve", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace("#lesson-video", "#missing"), encoding="utf-8")),
            ("page-basics", lambda s, r: (s / "books/b1/S1-U01.html").write_text((s / "books/b1/S1-U01.html").read_text(encoding="utf-8").replace('lang="zh-CN"', 'lang="en"', 1), encoding="utf-8")),
            ("size-limits", lambda s, r: (s / "index.html").write_bytes(b"x" * (3 * 1024 * 1024 + 1))),
            ("ch-header", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace("<h1>完整一章</h1>", "<h1>错误标题</h1>"), encoding="utf-8")),
            ("ch-video", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace('data-seek="1"', 'data-seek="9"'), encoding="utf-8")),
            ("ch-frames", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace("旁白中的一句话", "错误旁白"), encoding="utf-8")),
            ("ch-sections", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace('id="sec-one"', 'id="sec-bad"'), encoding="utf-8")),
            ("ch-shice", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace('data-record="R1"', 'data-record="BAD"'), encoding="utf-8")),
            ("ch-sources", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace("这是来源事实。", "缺少事实。"), encoding="utf-8")),
            ("ch-metaphors", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace('class="gap"', 'class="bad"'), encoding="utf-8")),
            ("ch-thinks", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace('class="think"', 'class="think" open'), encoding="utf-8")),
            ("ch-exercises", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace('class="answer"', 'class="answer" open'), encoding="utf-8")),
            ("ch-evidence", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace("R6 ", ""), encoding="utf-8")),
            ("ch-coverage", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace(">p1<", ">missing<"), encoding="utf-8")),
            ("ch-extras", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace("../../downloads/example.txt", "../../downloads/missing.txt"), encoding="utf-8")),
            ("ch-nav", lambda s, r: (s / "books/b2/S2-U01.html").write_text((s / "books/b2/S2-U01.html").read_text(encoding="utf-8").replace("上一章：没有了", "上一章：错误"), encoding="utf-8")),
        ]
        for rule, mutate in cases:
            with self.subTest(rule=rule):
                self.assert_fails(rule, mutate)

    def test_course_topic_words_are_not_leaks(self):
        # 课程会讲 .env、Authorization 请求头、环境变量名、“核对注册表”“辅助技术测试”：这些话题词不是泄露，也不是实验标签
        def mutate(site, repo):
            page = site / "books/b1/S1-U02.html"
            page.write_text(page.read_text(encoding="utf-8").replace("</body>", "<p>把 .env 放进 .gitignore；Authorization 请求头；环境变量 DASHSCOPE_API_KEY 放密钥；安装前须核对注册表；辅助技术测试取决于条件。</p></body>"), encoding="utf-8")
        done, result = self.run_case(mutate)
        self.assertNotIn("no-secret-or-path", result["failed"], result)
        self.assertNotIn("no-experiment-labels", result["failed"], result)

    def test_real_leaks_and_real_labels_are_caught(self):
        def add(text):
            def mutate(site, repo):
                page = site / "books/b1/S1-U02.html"
                page.write_text(page.read_text(encoding="utf-8").replace("</body>", "<p>%s</p></body>" % text), encoding="utf-8")
            return mutate
        for text in ("api_key = abcdef0123456789abcdef", "DASHSCOPE_API_KEY=sk-0123456789abcdefghij", "Authorization: Bearer abcdefghijklmnopqrstuvwx", "https://10.1.2.3:8443/", "MODELINK_API_KEY", "C:\\Users\\x"):
            with self.subTest(leak=text):
                self.assert_fails("no-secret-or-path", add(text))
        for text in ("这是技术测试视频", "核对注：待查", "【试验品】", "本章不属于课程"):
            with self.subTest(label=text):
                self.assert_fails("no-experiment-labels", add(text))

    def test_shelf_cover_failures(self):
        def edit(rel, fn):
            def mutate(site, repo):
                f = site / rel
                f.write_text(fn(f.read_text(encoding="utf-8")), encoding="utf-8")
            return mutate
        cases = {
            "no image in the book": edit("index.html", lambda s: s.replace('<img class="cover-art" src="assets/covers/b1.jpg" alt="蓝色封面的一本书，机器人在挥手">', "")),
            "image is not under assets/covers": edit("index.html", lambda s: s.replace('src="assets/covers/b1.jpg"', 'src="assets/img/b1.jpg"')),
            "cover file missing": lambda site, repo: (site / "assets/covers/b2.jpg").unlink(),
            "empty alt": edit("index.html", lambda s: s.replace('alt="蓝色封面的一本书，机器人在挥手"', 'alt=""', 1)),
            "title is not text": edit("index.html", lambda s: s.replace('class="bk-t"', 'class="x"', 1)),
            "not 3:4": lambda site, repo: self.make_image(site / "assets/covers/b1.jpg", 900, 900),
            "too narrow": lambda site, repo: self.make_image(site / "assets/covers/b1.jpg", 300, 400),
            "catalog page lacks the cover": edit("books/b1/index.html", lambda s: s.replace('class="cover-art"', 'class="plain"')),
            "no books on the shelf": edit("index.html", lambda s: s.replace("book-card", "x-card")),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                self.assert_fails("shelf-covers", mutate)

    def test_empty_chapter_fails_many_rules(self):
        def mutate(site, repo):
            (site / "books/b2/S2-U01.html").write_text("<!doctype html><html><body>空</body></html>", encoding="utf-8")
        _, result = self.run_case(mutate)
        self.assertGreaterEqual(len(result["failed"]), 5)


if __name__ == "__main__":
    unittest.main()
