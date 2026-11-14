import importlib.util
import io
import json
import random
import sys
from contextlib import redirect_stdout
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "docs/whiteboard/ebook"
sys.path.insert(0, str(SOURCE))
import blocks
import build_site
import labs


def sample():
    return {"t": "lab", "id": "s2-test", "title": "练习", "goal": "试一试", "starter": "print(1)",
            "tests": [{"id": "one", "name": "输出一行", "code": "assert STDOUT == '1\\n'"}]}


class DOM(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.nodes, self.stack = [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "text": "", "parent": self.stack[-1] if self.stack else None}
        self.nodes.append(node)
        self.stack.append(node)

    def handle_endtag(self, tag):
        assert self.stack[-1]["tag"] == tag
        self.stack.pop()

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]["text"] += data

    def cls(self, name):
        return [n for n in self.nodes if name in n["attrs"].get("class", "").split()]


def test_normalization_is_independent():
    original = sample()
    normalized = labs.validate_lab(original)
    assert all(normalized[key] == value for key, value in labs.DEFAULTS.items())
    assert original == sample()
    normalized["tests"][0]["code"] = "changed"
    normalized["hints"].append("hint")
    assert original == sample()
    assert labs.validate_lab(original)["hints"] == []


@pytest.mark.parametrize("field", sorted(labs.REQUIRED))
def test_missing_fields(field):
    block = sample()
    del block[field]
    with pytest.raises(ValueError, match=r"^lab .*: 缺少必填字段"):
        labs.validate_lab(block)


@pytest.mark.parametrize(("field", "value"), [
    ("extra", 1), ("t", "p"), ("id", "UPPER"), ("id", "a--b"), ("id", "a\n"), ("id", ""), ("id", 3),
    ("title", None), ("goal", 1), ("starter", False), ("starter", " \n"), ("prelude", []), ("solution", {}),
    ("hints", "提示"), ("hints", [1]), ("timeout", True), ("timeout", 0), ("timeout", 11), ("timeout", 1.0),
    ("seed", False), ("seed", 2.0), ("optional", "true"), ("tests", []), ("tests", {}), ("tests", [None]),
    ("tests", [{"id": "a", "name": "a"}]), ("tests", [{"id": "a", "name": "a", "code": "", "extra": ""}]),
    ("tests", [{"id": "a-", "name": "a", "code": ""}]), ("tests", [{"id": "a", "name": 1, "code": ""}]),
    ("tests", [{"id": "a", "name": "a", "code": None}]), ("tests", [{"id": 1, "name": "a", "code": ""}]),
    ("tests", [{"id": "a", "name": "a", "code": ""}] * 2),
])
def test_invalid_fields(field, value):
    block = dict(sample(), **{field: value})
    with pytest.raises(ValueError, match=r"(?s)^lab .*: "):
        labs.validate_lab(block)


@pytest.mark.parametrize("value", [None, [], "lab", 2])
def test_invalid_block(value):
    with pytest.raises(ValueError, match=r"^lab <unknown>: "):
        labs.validate_lab(value)


@pytest.mark.parametrize("timeout,seed", [(1, -1), (10, 0), (5, None)])
def test_valid_limits(timeout, seed):
    assert labs.validate_lab(dict(sample(), timeout=timeout, seed=seed))["seed"] == seed


def test_markup_matches_contract():
    block = sample()
    dom = DOM(labs.render_lab(block, "../../assets/"))
    assert not dom.stack
    main = dom.cls("lab")[0]
    assert main["attrs"] == {"class": "lab", "id": "lab-s2-test", "data-lab-id": "s2-test",
                             "data-lab-state": "idle", "data-paste-guard": "allow", "data-assets-root": "../../assets/"}
    suffixes = {"done", "preview", "start", "note", "work", "run", "check", "stop", "reset", "hint", "status",
                "editor", "toast", "hints", "stdout", "error", "checks", "solution-btn", "solution"}
    ids = [n["attrs"]["id"] for n in dom.nodes if "id" in n["attrs"]]
    assert len(ids) == len(set(ids))
    assert set(ids) == {"lab-s2-test"} | {f"lab-s2-test-{suffix}" for suffix in suffixes}
    for cls in ("lab-head", "lab-tag", "lab-title", "lab-done", "lab-goal", "lab-spec", "lab-preview",
                "lab-starter", "lab-actions", "lab-note", "lab-work", "lab-bar", "lab-btn", "lab-btn-main",
                "lab-status", "lab-editor", "lab-toast", "lab-hints", "lab-out", "lab-err", "lab-checks",
                "lab-solution-wrap", "lab-solution"):
        assert dom.cls(cls), cls
    for cls in ("lab-done", "lab-note", "lab-work", "lab-toast", "lab-err", "lab-solution"):
        assert "hidden" in dom.cls(cls)[0]["attrs"]
    for action in ("start", "run", "check", "stop", "reset", "hint", "solution"):
        node, = [n for n in dom.nodes if n["attrs"].get("data-action") == action]
        assert node["tag"] == "button" and node["attrs"]["type"] == "button"
        if action in ("stop", "hint", "solution"):
            assert "hidden" in node["attrs"]
    assert dom.cls("lab-editor")[0]["attrs"]["data-editor-for"] == block["id"]
    for cls in ("lab-status", "lab-toast"):
        assert dom.cls(cls)[0]["attrs"]["role"] == "status"
    assert dom.cls("lab-status")[0]["attrs"]["aria-live"] == "polite"
    assert dom.cls("lab-out")[0]["attrs"]["aria-label"] == "输出"
    spec = json.loads(dom.cls("lab-spec")[0]["text"])
    assert spec == {k: v for k, v in labs.validate_lab(block).items() if k != "t"}
    assert dom.cls("lab-spec")[0]["attrs"]["type"] == "application/json"
    assert dom.cls("lab-solution")[0]["parent"]["attrs"]["class"] == "lab-solution-wrap"


def test_escape_and_script_injection():
    payload = '</script><img src=x onerror="bad()">&\' '
    block = dict(sample(), **{k: payload for k in ("title", "goal", "starter", "prelude", "solution")}, hints=[payload])
    block["tests"][0].update(name=payload, code=payload)
    markup = labs.render_lab(block, '\"<assets>&')
    dom = DOM(markup)
    assert len([n for n in dom.nodes if n["tag"] == "script"]) == 1
    assert not any(n["tag"] == "img" for n in dom.nodes)
    spec_text = dom.cls("lab-spec")[0]["text"]
    assert "</" not in spec_text and "<\\/script>" in spec_text
    assert json.loads(spec_text)["solution"] == payload
    assert dom.cls("lab-title")[0]["text"] == payload
    assert dom.cls("lab")[0]["attrs"]["data-assets-root"] == '\"<assets>&'
    assert not DOM(labs.render_lab(dict(sample(), optional=False), "a/")).cls("lab-tag")


def test_ctx_assets_and_script_tags():
    ctx = blocks.Ctx({}, {}, {}, "../assets/")
    assert 'data-assets-root="../assets/"' in blocks.render_block(sample(), ctx)
    dom = DOM(labs.lab_script_tags("../assets/"))
    assert [n["attrs"]["src"] for n in dom.nodes] == ["../assets/" + f for f in ("lab-guard.js", "lab-core.js", "lab.js")]
    assert all("defer" in n["attrs"] for n in dom.nodes)
    assert "&quot;" in labs.lab_script_tags('a"/')


def test_duplicate_lab_ids():
    chapter = {"sections": [{"blocks": [sample()]}]}
    assert build_site.collect_lab_ids({"a": chapter}) == {"s2-test"}
    for chapters in ({"a": chapter, "b": chapter}, {"a": {"sections": [{"blocks": [sample(), sample()]}]}}):
        with pytest.raises(ValueError, match="lab s2-test: 全站练习 id 重复"):
            build_site.collect_lab_ids(chapters)


@pytest.mark.parametrize("data,expected", [({}, False), ({"labs": {}}, False), ({"labs": {"block_paste": False}}, False),
                                           ({"labs": {"block_paste": True, "other": 1}}, True)])
def test_write_config(tmp_path, data, expected):
    labs.write_lab_config(tmp_path, data)
    assert json.loads((tmp_path / "assets/lab-config.json").read_text()) == {"block_paste": expected}


@pytest.mark.parametrize("data", [None, [], {"labs": None}, {"labs": []}, {"labs": True},
                                  *({"labs": {"block_paste": v}} for v in (0, 1, "false", None, []))])
def test_bad_config_writes_nothing(tmp_path, data):
    with pytest.raises(ValueError):
        labs.write_lab_config(tmp_path, data)
    assert not list(tmp_path.iterdir())


def test_copy_assets(tmp_path):
    repo, site = tmp_path / "repo", tmp_path / "site"
    with pytest.raises(FileNotFoundError, match="fetch_vendor.py"):
        labs.copy_lab_assets(site, repo)
    vendor = repo / "projects/_ebook/vendor"
    (vendor / "nested").mkdir(parents=True)
    (vendor / "nested/data.wasm").write_bytes(b"\x00\xffvendor")
    with pytest.raises(FileNotFoundError, match="lab.js"):
        labs.copy_lab_assets(site, repo)
    for name in labs.ASSETS:
        path = repo / "docs/whiteboard/ebook" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    labs.copy_lab_assets(site, repo)
    assert (site / "assets/vendor/nested/data.wasm").read_bytes() == b"\x00\xffvendor"
    assert all((site / "assets" / name).read_bytes() == name.encode() for name in labs.ASSETS)


def minimal_chapter():
    return {"id": "u0", "lesson_title": "正文", "basic_question": "什么？", "takeaway": [],
            "sections": [{"id": "read", "title": "读一读", "blocks": [{"t": "p", "x": "原有正文"}]}],
            "exercises": {"items": [], "intro": [], "record": ["学习记录"]},
            "records": "records.json", "claims_file": "claims.json"}


@pytest.fixture
def site_inputs(tmp_path):
    from PIL import Image

    repo = tmp_path / "repo"
    eb = repo / "projects/_ebook"
    (eb / "chapters").mkdir(parents=True)
    outline = {"unit_count": 293, "stages": [{"id": "s", "title": "阶段", "notes": [], "units": [
        {"id": f"u{i}", "title": "章", "path": "核心", "prereq": [], "plain": {},
         "goal": "目标", "check": "检查", "points": "要点", "practice": "动手"} for i in range(293)]}]}
    books = {"series": {"name": "书", "subtitle": "副标题", "tagline": "介绍"},
             "books": [{"id": "book", "title": "册", "stages": ["s"], "blurb": "简介", "cover_alt": "图"}]}
    for path, obj in ((eb / "outline.json", outline), (eb / "books.yaml", books),
                      (eb / "chapters/u0.json", minimal_chapter()), (repo / "records.json", {}),
                      (repo / "claims.json", {"sourced": []})):
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    (eb / "covers").mkdir()
    Image.new("RGB", (3, 4), "white").save(eb / "covers/book.png")
    cast = repo / "projects/_cast/agent"
    cast.mkdir(parents=True)
    for name in ("teacher_hold.png", "robot_wave.png"):
        Image.new("RGBA", (2, 2), "white").save(cast / name)
    source = repo / "docs/whiteboard/ebook"
    source.mkdir(parents=True)
    # Shared static input isolates whether the build pipeline itself changes.
    for name in ("book.css", "book.js"):
        ref = REPO.parent / "ref/docs/whiteboard/ebook" / name
        source.joinpath(name).write_bytes(ref.read_bytes() if ref.exists() else (SOURCE / name).read_bytes())
    (repo / "font.ttf").write_bytes(b"font fixture")
    (repo / "archive.tsv").write_text("")
    return repo, eb, source


def run_build(module, site_inputs, target, monkeypatch):
    repo, eb, source = site_inputs
    for name, value in {"ROOT": repo, "EB": eb, "SITE": target, "HERE": source,
                        "FONT": repo / "font.ttf", "ARCHIVE": repo / "archive.tsv"}.items():
        monkeypatch.setattr(module, name, value)
    monkeypatch.setattr(sys, "argv", ["build_site.py"])
    module.main()


def test_full_build_only_lab_chapter_loads_scripts(site_inputs, tmp_path, monkeypatch):
    repo, eb, source = site_inputs
    chapter = minimal_chapter()
    chapter["sections"][0]["blocks"].append(sample())
    (eb / "chapters/u0.json").write_text(json.dumps(chapter))
    no_lab_chapter = minimal_chapter()
    no_lab_chapter["id"] = "u1"
    (eb / "chapters/u1.json").write_text(json.dumps(no_lab_chapter))
    books = json.loads((eb / "books.yaml").read_text())
    books["labs"] = {"block_paste": True}
    (eb / "books.yaml").write_text(json.dumps(books))
    (eb / "vendor").mkdir()
    (eb / "vendor/file.bin").write_bytes(b"vendor fixture")
    for name in labs.ASSETS:
        (source / name).write_text(name)
    target = repo / "site"
    run_build(build_site, site_inputs, target, monkeypatch)
    lab_page = target / "books/book/u0.html"
    for path in target.rglob("*.html"):
        text = path.read_text()
        scripts = [f'{name}.js' in text for name in ("lab-guard", "lab-core", "lab")]
        assert scripts == ([True] * 3 if path == lab_page else [False] * 3)
    text = lab_page.read_text()
    assert text.index("lab-guard.js") < text.index("lab-core.js") < text.index('src="../../assets/lab.js"') < text.index("</body>")
    assert 'data-assets-root="../../assets/"' in text
    assert "monaco" not in text.lower() and "pyodide" not in text.lower()
    assert json.loads((target / "assets/lab-config.json").read_text()) == {"block_paste": True}
    assert (target / "assets/vendor/file.bin").read_bytes() == b"vendor fixture"
    assert all((target / "assets" / name).is_file() for name in labs.ASSETS)


def test_duplicate_rejected_before_replacing_site(site_inputs, tmp_path, monkeypatch):
    _, eb, _ = site_inputs
    chapter = minimal_chapter()
    chapter["sections"][0]["blocks"] = [sample(), sample()]
    (eb / "chapters/u0.json").write_text(json.dumps(chapter))
    target = tmp_path / "site"
    target.mkdir()
    (target / "keep").write_text("old")
    with pytest.raises(ValueError, match="重复"):
        run_build(build_site, site_inputs, target, monkeypatch)
    assert (target / "keep").read_text() == "old"


def test_no_lab_build_identical_to_reference(site_inputs, tmp_path, monkeypatch):
    reference = REPO.parent / "ref/docs/whiteboard/ebook/build_site.py"
    if not reference.is_file():
        pytest.skip("reference snapshot is only present in the isolated task workspace")
    spec = importlib.util.spec_from_file_location("reference_build_site", reference)
    original = importlib.util.module_from_spec(spec)
    block_spec = importlib.util.spec_from_file_location("reference_blocks", reference.with_name("blocks.py"))
    original_blocks = importlib.util.module_from_spec(block_spec)
    block_spec.loader.exec_module(original_blocks)
    with monkeypatch.context() as context:
        context.setitem(sys.modules, "blocks", original_blocks)
        spec.loader.exec_module(original)
    old, new = site_inputs[0] / "old", site_inputs[0] / "new"
    run_build(original, site_inputs, old, monkeypatch)
    run_build(build_site, site_inputs, new, monkeypatch)
    tree = lambda root: {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert tree(old) == tree(new)
    assert not (new / "assets/vendor").exists()
    assert not (new / "assets/lab-config.json").exists()


def test_css_only_appended():
    reference = REPO.parent / "ref/docs/whiteboard/ebook/book.css"
    if not reference.is_file():
        pytest.skip("reference snapshot is only present in the isolated task workspace")
    assert (SOURCE / "book.css").read_bytes().startswith(reference.read_bytes())


def test_sample_solution_and_bad_answers():
    section = json.loads((REPO / "projects/agent-what-is-llm-cn/code/lab_section.json").read_text())
    assert section["id"] == "lab-draw" and section["blocks"][0]["t"] == "p"
    block, = [b for b in section["blocks"] if b["t"] == "lab"]
    normalized = labs.validate_lab(block)
    DOM(labs.render_lab(block, "../../assets/"))
    assert len(normalized["tests"]) >= 3 and 2 <= len(normalized["hints"]) <= 3
    assert "玩具模拟" in section["blocks"][0]["x"] and "不是大模型内部真实的做法" in section["blocks"][0]["x"]

    def checks(code):
        def run(seed=None):
            ns = {"__name__": "__main__"}
            output = io.StringIO()
            with redirect_stdout(output):
                exec(block["prelude"], ns)
                if seed is not None:
                    random.seed(seed)
                exec(code, ns)
            return output.getvalue(), ns

        stdout, ns = run()
        results = []
        for test in block["tests"]:
            try:
                exec(test["code"], {"STDOUT": stdout, "NS": ns, "USER_CODE": code,
                                    "RUN_WITH_SEED": lambda seed: run(seed)[0]})
                results.append(True)
            except AssertionError:
                results.append(False)
        return results

    assert all(checks(block["solution"]))
    assert not checks('print("小猫")')[0]
    assert not checks('print("其他词\\n其他词\\n其他词")')[1]
    assert not checks('print("小猫\\n小猫\\n小猫")')[-1]
    assert not checks('import random\nrandom.seed(1)\n' + block["solution"])[-1]


def test_assemble_inserts_section_idempotently(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("assemble", REPO / "projects/agent-what-is-llm-cn/code/assemble_chapter.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lesson = tmp_path / "lesson"
    (lesson / "code").mkdir(parents=True)
    (lesson / "code/lab_section.json").write_bytes((REPO / "projects/agent-what-is-llm-cn/code/lab_section.json").read_bytes())
    drafts = lesson / "drafts"
    drafts.mkdir()
    sections = []
    for sid in module.ORDER:
        if sid == "lab-draw":
            continue
        section = {"id": sid, "title": sid, "blocks": [{"t": "callout", "x": "示例"}] if sid == "product" else [{"t": "think"}]}
        if sid in module.NEW:
            (drafts / f"{sid}.run.json").write_text(json.dumps({"structured_output": {"section": section}}))
        else:
            sections.append(section)
    chapter = lesson / "chapter.json"
    chapter.write_text(json.dumps({"sections": sections}))
    for name, value in {"P": lesson, "ROOT": tmp_path, "DRAFTS": drafts, "CH_FILE": chapter,
                        "EDITS": {sid: [] for sid in (*module.NEW, "deeper", "note", "date")}}.items():
        monkeypatch.setattr(module, name, value)
    module.main()
    first = chapter.read_bytes()
    module.main()
    assert chapter.read_bytes() == first
    sections = json.loads(first)["sections"]
    assert [s["id"] for s in sections][-2:] == ["deeper", "lab-draw"]
    assert sections[-1]["only_book"] == module.ONLY_BOOK
