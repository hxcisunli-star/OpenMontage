"""Validation, static markup and assets for the optional Python labs."""
import html
import json
import re
import shutil
from pathlib import Path

ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
REQUIRED = {"id", "title", "goal", "starter", "tests"}
DEFAULTS = {"prelude": "", "hints": [], "solution": "", "timeout": 10, "seed": None, "optional": True}
ASSETS = ("lab.js", "lab-core.js", "lab-guard.js", "lab-worker.js", "lab-runner.py")


def validate_lab(block):
    """Return an independent, normalized block; reject unknown or mistyped fields."""
    ident = block.get("id", "<unknown>") if isinstance(block, dict) else "<unknown>"

    def fail(reason):
        raise ValueError(f"lab {ident}: {reason}")

    if not isinstance(block, dict):
        fail("练习块必须是对象")
    unknown = block.keys() - (REQUIRED | DEFAULTS.keys() | {"t"})
    if unknown:
        fail(f"未知字段：{', '.join(sorted(map(str, unknown)))}")
    missing = REQUIRED - block.keys()
    if missing:
        fail(f"缺少必填字段：{', '.join(sorted(missing))}")
    if block.get("t", "lab") != "lab":
        fail("t 必须是 lab")
    if not isinstance(ident, str) or not ID.fullmatch(ident):
        fail("id 必须是小写字母、数字和单个连字符组成的标识")
    result = {"t": "lab", **DEFAULTS, **block}
    for key in ("title", "goal", "starter", "prelude", "solution"):
        if not isinstance(result[key], str):
            fail(f"{key} 必须是字符串")
    if not result["starter"].strip():
        fail("starter 不能为空")
    if not isinstance(result["hints"], list) or any(not isinstance(h, str) for h in result["hints"]):
        fail("hints 必须是字符串数组")
    if type(result["timeout"]) is not int or not 1 <= result["timeout"] <= 10:
        fail("timeout 必须是 1–10 的整数")
    if result["seed"] is not None and type(result["seed"]) is not int:
        fail("seed 必须是整数或 null")
    if type(result["optional"]) is not bool:
        fail("optional 必须是布尔值")
    if not isinstance(result["tests"], list) or not result["tests"]:
        fail("tests 必须是非空数组")
    tests, seen = [], set()
    for test in result["tests"]:
        if not isinstance(test, dict) or set(test) != {"id", "name", "code"}:
            fail("每项检查必须恰有 id、name、code 字段")
        if not all(isinstance(test[key], str) for key in ("id", "name", "code")):
            fail("检查的 id、name、code 必须是字符串")
        if not ID.fullmatch(test["id"]):
            fail(f"检查 id 不合法：{test['id']}")
        if test["id"] in seen:
            fail(f"检查 id 重复：{test['id']}")
        seen.add(test["id"])
        tests.append(dict(test))
    result["tests"], result["hints"] = tests, list(result["hints"])
    return result


def render_lab(block, root):
    b = validate_lab(block)
    esc = lambda s: html.escape(str(s), quote=True)
    ident = "lab-" + b["id"]
    spec = json.dumps({k: v for k, v in b.items() if k != "t"}, ensure_ascii=False).replace("</", "<\\/")
    tag = '<span class="lab-tag">选做，视频里没有</span>' if b["optional"] else ""
    return f'''<section class="lab" id="{ident}" data-lab-id="{b['id']}" data-lab-state="idle" data-paste-guard="allow" data-assets-root="{esc(root)}">
  <header class="lab-head">{tag}<h3 class="lab-title">{esc(b['title'])}</h3><span class="lab-done" id="{ident}-done" hidden>已完成 ✓</span></header>
  <p class="lab-goal">{esc(b['goal'])}</p>
  <script type="application/json" class="lab-spec">{spec}</script>
  <div class="lab-preview" id="{ident}-preview"><pre class="lab-starter"><code>{esc(b['starter'])}</code></pre>
    <div class="lab-actions"><button type="button" class="lab-btn lab-btn-main" id="{ident}-start" data-action="start">开始练习</button></div></div>
  <p class="lab-note" id="{ident}-note" hidden></p>
  <div class="lab-work" id="{ident}-work" hidden>
    <div class="lab-bar">
      <button type="button" class="lab-btn lab-btn-main" id="{ident}-run" data-action="run" title="Ctrl+Enter">运行</button>
      <button type="button" class="lab-btn" id="{ident}-check" data-action="check">运行并检查</button>
      <button type="button" class="lab-btn" id="{ident}-stop" data-action="stop" hidden>停止</button>
      <button type="button" class="lab-btn" id="{ident}-reset" data-action="reset">重置</button>
      <button type="button" class="lab-btn" id="{ident}-hint" data-action="hint" hidden>提示</button>
      <span class="lab-status" id="{ident}-status" role="status" aria-live="polite"></span>
    </div>
    <div class="lab-editor" id="{ident}-editor" data-editor-for="{b['id']}"></div>
    <div class="lab-toast" id="{ident}-toast" role="status" hidden></div>
    <div class="lab-hints" id="{ident}-hints"></div>
    <pre class="lab-out" id="{ident}-stdout" aria-label="输出"></pre>
    <pre class="lab-err" id="{ident}-error" hidden></pre>
    <ul class="lab-checks" id="{ident}-checks"></ul>
    <div class="lab-solution-wrap"><button type="button" class="lab-btn" id="{ident}-solution-btn" data-action="solution" hidden>参考写法</button>
      <div class="lab-solution" id="{ident}-solution" hidden><pre><code></code></pre></div></div>
  </div>
</section>'''


def lab_script_tags(root):
    root = html.escape(str(root), quote=True)
    return "\n".join(f'<script defer src="{root}{name}"></script>' for name in ("lab-guard.js", "lab-core.js", "lab.js"))


def lab_config(books_yaml_data):
    if not isinstance(books_yaml_data, dict):
        raise ValueError("books.yaml 必须是对象")
    config = books_yaml_data.get("labs", {})
    if not isinstance(config, dict):
        raise ValueError("books.yaml: labs 必须是对象")
    blocked = config.get("block_paste", False)
    if type(blocked) is not bool:
        raise ValueError("books.yaml: labs.block_paste 必须是布尔值")
    return {"block_paste": blocked}


def write_lab_config(site_dir, books_yaml_data):
    config = lab_config(books_yaml_data)
    dest = Path(site_dir) / "assets/lab-config.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(config, ensure_ascii=False) + "\n", encoding="utf-8")


def copy_lab_assets(site_dir, repo_root):
    repo_root, site_dir = Path(repo_root), Path(site_dir)
    vendor = repo_root / "projects/_ebook/vendor"
    if not vendor.is_dir():
        raise FileNotFoundError("缺少练习依赖 vendor 目录，请先运行 docs/whiteboard/ebook/fetch_vendor.py")
    sources = [repo_root / "docs/whiteboard/ebook" / name for name in ASSETS]
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError(f"缺少练习资源：{source.name}")
    dest = site_dir / "assets"
    dest.mkdir(parents=True, exist_ok=True)
    for source in sources:
        shutil.copy2(source, dest / source.name)
    shutil.copytree(vendor, dest / "vendor", dirs_exist_ok=True)
