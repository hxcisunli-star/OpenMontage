"""Tests for the measured-record renderers of the ebook platform added for lesson 2 (usage, bars, cuts, docs); uses the real records of projects/agent-tokens-window-cn."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
BOOK_DIR = ROOT / "docs/whiteboard/ebook"
sys.path.insert(0, str(BOOK_DIR))
import blocks  # noqa: E402


KINDS = {"usage", "bars", "cuts", "docs"}


def records():
    return json.loads((ROOT / "projects/agent-tokens-window-cn/validation/records.json").read_text(encoding="utf-8"))


def render(record_id, data=None):
    data = records() if data is None else data
    ctx = blocks.Ctx(data, {}, {})
    return blocks.show({"id": record_id}, ctx)


def test_every_l2_record_renders_and_escapes():
    data = records()
    ids = [key for key, value in data.items() if isinstance(value, dict) and value.get("kind") in KINDS]
    assert ids
    assert {data[key]["kind"] for key in ids} == KINDS
    for record_id in ids:
        record = data[record_id]
        output = render(record_id, data)
        assert "<script" not in output.lower()
        assert record["title"] in output
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if field in record:
                for value in record[field]:
                    assert str(value) in output
        if record["kind"] == "bars":
            for model in record["models"]:
                for field in ("zh", "en", "code", "wrapper", "net_zh"):
                    assert str(model[field]) in output
        if record["kind"] == "cuts":
            assert "validation/research" not in output
            assert record["how"] not in output

    fake = deepcopy(data)
    fake["U_B1_nihao_off_ds"]["prompt"] = "<b>x</b>"
    assert "&lt;b&gt;x&lt;/b&gt;" in render("U_B1_nihao_off_ds", fake)
    assert "<b>x</b>" not in render("U_B1_nihao_off_ds", fake)


def test_usage_same_marker_and_bars_shared_scale():
    data = records()
    usage_output = render("U_B1_nihao_off_ds", data)
    assert usage_output.count("三遍相同") == 1
    varied = deepcopy(data)
    varied["U_B1_nihao_off_ds"]["prompt_tokens"] = [5, 6, 5]
    assert "三遍相同" not in render("U_B1_nihao_off_ds", varied)

    bars_output = render("W_langs", data)
    widths = [float(width) for width in re.findall(r'style="width:([0-9]+(?:\.[0-9])?)%"', bars_output)]
    assert widths and max(widths) == 100.0


def test_all_record_text_is_escaped():
    data = records()
    fake = deepcopy(data)
    fake["W_langs"]["models"][0]["model"] = "<b>x</b>"
    fake["K_knife"]["rows"][0]["note"] = "<b>x</b>"
    fake["D_docs"]["cards"][0]["quote"] = "<b>x</b>"
    assert "&lt;b&gt;x&lt;/b&gt;" in render("W_langs", fake)
    assert "&lt;b&gt;x&lt;/b&gt;" in render("K_knife", fake)
    assert "&lt;b&gt;x&lt;/b&gt;" in render("D_docs", fake)


def main():
    for test in (test_every_l2_record_renders_and_escapes, test_usage_same_marker_and_bars_shared_scale, test_all_record_text_is_escaped):
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
