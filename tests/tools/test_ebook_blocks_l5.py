"""Contract tests for lesson 5 callpanel and sequence figures."""
from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BOOK_DIR = ROOT / "docs" / "whiteboard" / "ebook"
sys.path.insert(0, str(BOOK_DIR))
import blocks  # noqa: E402


FIXTURES = ROOT / "tests" / "fixtures" / "ebook_l5"
EXAMPLES = FIXTURES / "example_records.json"


def records():
    return json.loads(EXAMPLES.read_text(encoding="utf-8"))


def render(record_id, data=None):
    data = records() if data is None else data
    return blocks.show({"id": record_id}, blocks.Ctx(data, {}, {}))


def test_each_l5_record_renders_with_its_own_tag():
    data = records()
    assert {record["kind"] for record in data.values()} == {"callpanel", "sequence"}
    assert "tag-shice" in render("CP_shice", data)
    assert "tag-shiyi" in render("CP_shiyi", data)
    assert "tag-shiyi" in render("SEQ_mixed", data)
    assert "tag-shice" not in render("CP_shiyi", data)
    assert "tag-shice" not in render("SEQ_mixed", data)


def test_all_l5_strings_are_escaped():
    data = records()
    fake = deepcopy(data)
    fake["CP_shice"]["request"]["code"] = "<b>x</b>"
    fake["CP_shice"]["request"]["marks"] = [{"text": "<b>x</b>", "role": "messages"}]
    fake["CP_shice"]["result"]["fields"][0]["value"] = "<b>answer</b>"
    fake["SEQ_mixed"]["lanes"][0] = "<b>lane</b>"
    fake["SEQ_mixed"]["steps"][0]["label"] = "<b>step</b>"
    out = render("CP_shice", fake)
    assert "&lt;b&gt;x&lt;/b&gt;" in out and "<b>x</b>" not in out
    assert "&lt;b&gt;answer&lt;/b&gt;" in out
    out = render("SEQ_mixed", fake)
    assert "&lt;b&gt;lane&lt;/b&gt;" in out and "&lt;b&gt;step&lt;/b&gt;" in out
    assert "<b>lane</b>" not in out and "<b>step</b>" not in out


def test_callpanel_marks_are_exactly_once_and_legend_is_minimal():
    data = records()
    out = render("CP_shice", data)
    assert out.count('class="cp-mark') == 3
    assert all(label in out for label in ("密钥", "模型名", "消息"))
    assert "地址" not in out
    bad = deepcopy(data)
    bad["CP_shice"]["request"]["marks"] = [{"text": "not-there", "role": "key"}]
    try:
        render("CP_shice", bad)
    except ValueError:
        pass
    else:
        raise AssertionError("a missing mark must fail the build")
    bad = deepcopy(data)
    bad["CP_shice"]["request"]["code"] = "token token"
    bad["CP_shice"]["request"]["marks"] = [{"text": "token", "role": "key"}]
    try:
        render("CP_shice", bad)
    except ValueError:
        pass
    else:
        raise AssertionError("a repeated mark must fail the build")


def test_callpanel_honesty_status_and_caption():
    measured = render("CP_shice")
    sketch = render("CP_shiyi")
    assert "状态码：200" in measured and "状态码" not in sketch
    assert "某一次的返回，原样" in measured and "是示意，不是实测" not in measured
    assert "是示意，不是实测" in sketch and "tag-shiyi" in sketch
    assert "tag-shice" not in sketch


def test_sequence_has_accessible_steps_sources_cross_and_hypothesis_style():
    out = render("SEQ_mixed")
    assert out.count('class="seq-step seq-') == 4
    assert "实测" in out and "示意" in out
    assert "文档写的，不是我们测的" in out and "假设" in out
    assert "seq-hypo" in out and "seq-cross" in out and "被拦住" in out
    assert "文字版（每步一句话）" in out
    assert out.count("<li>") >= 4
    assert "其中标‘文档写的’的步骤只是引文档" in out
    assert "是示意，不是实测" in out
    assert "tag-shice" not in out


def test_honesty_rules_are_checked_as_rules():
    data = records()
    measured = render("CP_shice", data)
    sketch = render("CP_shiyi", data)
    sequence = render("SEQ_mixed", data)
    assert 'class="tag tag-shice"' in measured and 'class="tag tag-shiyi"' not in measured
    assert 'class="tag tag-shiyi"' in sketch and 'class="tag tag-shice"' not in sketch
    assert 'class="tag tag-shiyi"' in sequence and 'class="tag tag-shice"' not in sequence


def test_old_record_html_is_byte_identical_to_pre_change_baseline():
    manifest = json.loads((FIXTURES / "baseline" / "manifest.json").read_text(encoding="utf-8"))
    sources = {}
    for source in (
        ROOT / "projects" / "agent-sampling-temp-cn" / "validation" / "ebook_records.json",
        ROOT / "projects" / "agent-roles-history-cn" / "validation" / "ebook_records.json",
        ROOT / "projects" / "agent-tokens-window-cn" / "validation" / "records.json",
    ):
        data = json.loads(source.read_text(encoding="utf-8"))
        for record_id, record in data.items():
            if isinstance(record, dict) and "kind" in record:
                sources[record_id] = data
    for filename, item in manifest.items():
        output = render(item["id"], sources[item["id"]])
        expected = (FIXTURES / "baseline" / filename).read_text(encoding="utf-8")
        assert output == expected, filename


def test_callpanel_caption_override_is_escaped_and_shiyi_must_say_shiyi():
    data = records()
    fake = deepcopy(data)
    fake["CP_shice"]["caption"] = "本机实验：<b>x</b>"
    out = render("CP_shice", fake)
    assert "本机实验：&lt;b&gt;x&lt;/b&gt;" in out and "<b>x</b>" not in out
    assert "某一次的返回，原样" not in out
    bad = deepcopy(data)
    bad["CP_shiyi"]["caption"] = "一次真实返回"
    try:
        render("CP_shiyi", bad)
    except AssertionError:
        pass
    else:
        raise AssertionError("a 示意 callpanel caption without 示意 must be refused")
    ok = deepcopy(data)
    ok["CP_shiyi"]["caption"] = "示意写法，不是某一次返回"
    assert "示意写法，不是某一次返回" in render("CP_shiyi", ok)


def test_sequence_steps_follow_the_lane_order_and_the_arrow_direction():
    import re
    data = records()
    out = render("SEQ_mixed", data)
    record = data["SEQ_mixed"]
    lanes = record["lanes"]
    items = re.findall(r'<li class="seq-step[^"]*" aria-hidden="true">(.*?)</li>', out, re.S)
    assert len(items) == len(record["steps"])
    for step, item in zip(record["steps"], items):
        left = re.search(r'seq-end seq-end-left[^"]*">(.*?)</span>', item).group(1)
        right = re.search(r'seq-end seq-end-right[^"]*">(.*?)</span>', item).group(1)
        assert (left, right) == (lanes[0], lanes[1]), "the cells follow the lane heads, not from/to"
        arrow = re.search(r'seq-arrow">(.*?)</span>', item).group(1)
        want = "→" if (step["from"], step["to"]) == (0, 1) else "←" if (step["from"], step["to"]) == (1, 0) else "↻"
        assert arrow == want
