"""The small Markdown of the exercise text (build_site.ex_lines_html, 2026-11-24, handoff-l21 §6).
A line without Markdown renders exactly as before; fences, pipe tables, "- " lists and "#" headings become HTML; nothing of the text is lost."""
import html
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "docs/whiteboard/ebook"))
import build_site  # noqa: E402

md = build_site.ex_lines_html


def test_plain_lines_are_rendered_exactly_as_before():
    lines = ["第一行", "", "  缩进的行 <b> & “引号”", "1. 带编号的行不变成列表", "2) 也不变"]
    assert md(lines) == "".join(f"<p>{html.escape(x, quote=True)}</p>" for x in lines)


def test_fence_three_and_four_backticks_and_language():
    out = md(["```python", "x = 1", "```"])
    assert out == '<pre class="code ex-code" data-lang="python"><code>x = 1</code></pre>'
    out = md(["````text", "a ``` inside", "```", "still code", "````", "after"])
    assert out.startswith('<pre class="code ex-code" data-lang="text"><code>a ``` inside\n```\nstill code</code></pre>')
    assert out.endswith("<p>after</p>")


def test_fence_opened_at_the_end_of_a_line_keeps_the_lead_text():
    out = md(["签名（构造）：```python", "case = {'a': 1}", "```"])
    assert out == '<p>签名（构造）：</p><pre class="code ex-code" data-lang="python"><code>case = {&#x27;a&#x27;: 1}</code></pre>'


def test_unclosed_fence_stays_plain_lines():
    lines = ["```python", "x = 1"]
    assert md(lines) == "<p>```python</p><p>x = 1</p>"


def test_table_header_body_pipes_in_code_and_escaped():
    out = md(["| 名字 | 值 |", "|---|:--:|", "| `a|b` | 1 \\| 2 |", "| 甲 | 乙 |"])
    assert out.startswith('<div class="scroll ex-table"><table class="t"><tr><th>名字</th><th>值</th></tr>')
    assert "<td><code>a|b</code></td><td>1 | 2</td>" in out and "<td>甲</td><td>乙</td>" in out
    assert "---" not in out


def test_table_with_separator_lower_down_has_no_header():
    out = md(["| 甲 | 乙 |", "| 丙 | 丁 |", "|---|---|", "| 戊 | 己 |"])
    assert "<th>" not in out and out.count("<tr>") == 3


def test_bold_markers_inside_code_stay_code():          # Codex review F16
    assert md(["看 `a**b**c` 和 **重点**"]) == "<p>看 <code>a**b**c</code> 和 <b>重点</b></p>"


def test_a_pipe_line_without_separator_row_is_text():          # Codex review F17: |x| is an absolute value, not a table
    assert md(["|x|"]) == "<p>|x|</p>"
    assert md(["|a|", "|b|"]) == "<p>|a|</p><p>|b|</p>"


def test_list_heading_inline_code_and_bold():
    out = md(["# 第十课 练习", "- 一 `code`", "- 二 **重点**", "正文"])
    assert out == ('<h4 class="ex-h">第十课 练习</h4><ul class="ex-list"><li>一 <code>code</code></li><li>二 <b>重点</b></li></ul><p>正文</p>')


def _visible(h):
    h = re.sub(r"</(p|li|tr|h[1-6]|pre)>", "\n", h)
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def _strip_marks(t):
    t = re.sub(r"`{3,}[A-Za-z0-9_+-]*", "", t)
    t = re.sub(r"(?m)^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$", "", t)
    t = t.replace("|", "").replace("`", "").replace("**", "").replace("\\", "")
    t = re.sub(r"(?m)^\s*#{1,6}\s+", "", t)
    t = re.sub(r"(?m)^\s*- ", "", t)
    return re.sub(r"\s+", "", t)


CHAPTERS = sorted((ROOT / "projects/_ebook/chapters").glob("*.json"))


@pytest.mark.skipif(not CHAPTERS, reason="no chapter sources in this checkout")
@pytest.mark.parametrize("path", CHAPTERS, ids=lambda p: p.stem)
def test_real_exercises_lose_no_text_and_leave_no_raw_marks(path):
    ex = json.loads(path.read_text(encoding="utf-8"))["exercises"]
    groups = [ex["intro"], ex["record"][1:]] + [it["q"] for it in ex["items"]] + [it["a"] for it in ex["items"]]
    for lines in groups:
        out = md(lines)
        assert _strip_marks("\n".join(lines)) == _strip_marks(_visible(out))
        paras = [html.unescape(x) for x in re.findall(r"<p>(.*?)</p>", out, re.S)]
        assert not [x for x in paras if "```" in x], "a fence was left as a raw line"
        assert not [x for x in paras if x.strip().startswith("|") and x.strip().endswith("|")], "a table row was left as a raw line"
