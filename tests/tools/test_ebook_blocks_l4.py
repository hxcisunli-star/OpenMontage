"""Tests for the lesson 4 record figures in agent-roles-history-cn."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
BOOK_DIR = ROOT / "docs/whiteboard/ebook"
sys.path.insert(0, str(BOOK_DIR))
import blocks  # noqa: E402


KINDS = {"stack", "grids", "answers", "tokenbars", "cards", "probe"}


def records():
    return json.loads((ROOT / "projects/agent-roles-history-cn/validation/ebook_records.json").read_text(encoding="utf-8"))


def render(record_id, data=None):
    data = records() if data is None else data
    return blocks.show({"id": record_id}, blocks.Ctx(data, {}, {}))


def test_every_l4_record_renders_with_its_own_tag():
    data = records()
    ids = [rid for rid, record in data.items() if record.get("kind") in KINDS]
    assert len(ids) == 14
    assert {data[rid]["kind"] for rid in ids} == KINDS
    for rid in ids:
        out = render(rid, data)
        assert data[rid]["title"] in out
        assert "<script" not in out.lower()
        tag = "tag-source" if data[rid]["kind"] == "cards" else "tag-shice"
        assert f'class="tag {tag}"' in out


def test_l4_text_is_escaped():
    data = records()
    fake = deepcopy(data)
    fake["ST_full"]["notes"][0]["text"] = "<b>stack</b>"
    fake["GR_name"]["rows"][0]["label"] = "<b>grid</b>"
    fake["AN_fab"]["items"][0]["text"] = "<b>answer</b>"
    fake["CD_roles"]["cards"][0]["quote"] = "<b>quote</b>"
    fake["PB_resp"]["message"] = "<b>probe</b>"
    for rid in ("ST_full", "GR_name", "AN_fab", "CD_roles", "PB_resp"):
        out = render(rid, fake)
        assert "&lt;b&gt;" in out
        assert "<b>stack</b>" not in out and "<b>grid</b>" not in out
        assert "<b>answer</b>" not in out and "<b>quote</b>" not in out and "<b>probe</b>" not in out


def test_grids_have_metadata_counts_and_only_the_recorded_dots():
    data = records()
    for rid, record in data.items():
        if record.get("kind") != "grids":
            continue
        out = render(rid, data)
        assert "l4-legend" in out and "l4-labeler" in out and "l4-models" in out
        assert record["date"] in out
        for model in record["models"].values():
            assert model in out
        if rid == "GR_role":
            assert "程序判" in out and "AI 模型" not in out
        else:
            assert "AI 模型" in out and "真人标注" not in out
        assert out.count('class="l4-grid-cell l4-grid-') == sum(len(row["cells"]) for row in record["rows"])
        assert out.count("l4-grid-dot") == sum(1 for row in record["rows"] for cell in row["cells"] if cell.get("dot") is True)
        for row in record["rows"]:
            tally = row["tally"]
            assert f'{tally["short"]} {tally["n"]} / {tally["total"]}' in out


def test_stack_marks_only_assistant_papers_as_pre_written():
    data = records()
    for rid, record in data.items():
        if record.get("kind") != "stack":
            continue
        out = render(rid, data)
        assert out.count('class="l4-stamp"') == sum(1 for note in record["notes"] if note["role"] == "assistant")
        assert "调用的人" in out


def test_tokenbars_use_token_value_times_the_recorded_scale_and_show_legend():
    record = records()["TK_cost"]
    out = render("TK_cost")
    widths = [float(value) for value in re.findall(r'style="width:([0-9.]+)%"', out)]
    values = [value for row in record["rows"] for value in (row["ds"], row["qw"])]
    assert len(widths) == len(values) == 8 and max(widths) == 100.0
    assert all(abs(w - v / max(values) * 100) < 0.06 for w, v in zip(widths, values))        # proportional to the token count at any screen width
    assert "l4-token-first" in out and "l4-token-second" in out and "l4-token-legend" in out


def test_cards_show_interface_archive_dates_gloss_and_ours():
    data = records()
    for rid, record in data.items():
        if record.get("kind") != "cards":
            continue
        out = render(rid, data)
        sections = re.findall(r'<article class="l4-source-card">(.*?)</article>', out, re.S)
        assert len(sections) == len(record["cards"])
        for card, section in zip(record["cards"], sections):
            assert card["iface"] in section and card["archive"] in section
            if card.get("recheck_date"):
                assert card["archive_date"] in section and card["recheck_date"] in section
            else:
                assert section.count(record["date"]) == 1
            if card.get("gloss"):
                assert f'{card["gloss_kind"]}：' in section
            if card.get("ours"):
                assert "不是页面原话" in section
        assert "每张卡只对名下的接口成立" in out


def test_probe_repeats_status_for_each_call_and_states_scope():
    record = records()["PB_resp"]
    out = render("PB_resp")
    assert out.count(f'status {record["status"]}') == record["calls"]
    assert record["message"] in out and "不是百炼" in out
    assert "单独一次探测，没有控制思考，不是正式实验" in out


def test_l4_output_has_no_lesson_three_orange_value():
    data = records()
    for rid, record in data.items():
        if record.get("kind") in KINDS:
            assert "#E8873A" not in render(rid, data).upper()
