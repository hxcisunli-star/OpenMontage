"""Tests for the figure kinds of the ebook platform added for lesson 3 (ptable, rows, quotes, excerpt, lines, finish, sketch); uses the real records of projects/agent-sampling-temp-cn/validation/ebook_records.json.
The honesty rules of the lesson are tested as rules: orange only on the token the return really chose, the stop token never "chosen", a made-up sketch never carries the 实测 stamp, quotes carry 引文."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
BOOK_DIR = ROOT / "docs/whiteboard/ebook"
sys.path.insert(0, str(BOOK_DIR))
import blocks  # noqa: E402

KINDS = {"ptable", "rows", "quotes", "excerpt", "lines", "finish", "sketch"}


def records():
    return json.loads((ROOT / "projects/agent-sampling-temp-cn/validation/ebook_records.json").read_text(encoding="utf-8"))


def render(record_id, data=None):
    data = records() if data is None else data
    return blocks.show({"id": record_id}, blocks.Ctx(data, {}, {}))


def test_every_l3_record_renders_with_its_own_tag():
    data = records()
    assert {r["kind"] for r in data.values()} == KINDS
    for rid, r in data.items():
        out = render(rid, data)
        assert "<script" not in out.lower() and r["title"] in out
        tag = {"sketch": "tag-shiyi", "quotes": "tag-source"}.get(r["kind"], "tag-shice")
        assert f'class="tag {tag}"' in out, rid
        if r["kind"] == "sketch":
            assert "tag-shice" not in out and "示意" in out        # made-up numbers never carry the measured stamp
        else:
            assert "tag-shiyi" not in out


def test_measured_captions_name_model_date_mode_and_number_of_runs():
    data = records()
    for rid, r in data.items():
        if r["kind"] in ("sketch", "quotes"):
            continue
        out = render(rid, data)
        cap = re.search(r'<figcaption class="rec">(.*?)</figcaption>', out, re.S).group(1)
        assert r["model"].split("/")[-1] in cap and r["date"] in cap and r["mode"] in cap and "无法独立验证" in cap, rid
        if r.get("n") is not None:
            assert re.search(r"(?<!\d)%s\s*遍" % r["n"], cap), rid


def test_orange_only_on_the_chosen_token_and_stop_is_never_chosen():
    data = records()
    for rid, r in data.items():
        if r["kind"] != "ptable":
            continue
        out = render(rid, data)
        n_pick = out.count("pbar pick")
        assert n_pick == (1 if r.get("chosen") else 0), rid
        for b in r["bars"]:
            if b.get("stop"):
                assert r.get("chosen") is None, rid                      # the return does not say the stop token was drawn
                assert "停止符" in out and "pbar stop" in out
        assert re.search(r"某一次|另一次|同一次请求", out), rid          # every table says whose return it is: one request's, not "the" distribution


def test_ptable_bars_share_one_scale_and_the_rest_is_an_empty_dashed_bar():
    r = records()["P_name_a"]
    out = render("P_name_a")
    heights = [float(h) for h in re.findall(r'class="pbar[^"]*" style="height:([0-9.]+)px"', out)]
    assert len(heights) == len(r["bars"]) + 1                                # five names and the rest
    assert abs(heights[0] - r["bars"][0]["pct"] * 2.0) < 0.2                 # 100 % = 200 px
    assert "restbar" in out and "其余合计" in out


def test_rows_use_pale_colours_and_no_orange_and_say_how_many_kinds():
    data = records()
    out = render("ROWS_name_ds", data)
    assert "#E8873A" not in out.upper()
    assert out.count('class="crow"') == 3 and "共 5 种" in out and "共 10 种" in out
    assert out.count('class="cell"') == 30


def test_quotes_show_both_dates_the_footnote_and_escape_text():
    data = records()
    out = render("Q_official", data)
    assert out.count('class="qcard"') == 3 and "qfoot" in out and "存档" in out and "重取原页核对" in out
    bad = deepcopy(data)
    bad["Q_official"]["cards"][0]["english"] = "<img src=x onerror=alert(1)>"
    assert "<img" not in render("Q_official", bad)


def test_finish_panel_marks_the_stop_reason_and_the_number_of_runs():
    data = records()
    for rid, reason in (("F_mt5", "length"), ("F_400", "stop"), ("F_mt1", "length")):
        out = render(rid, data)
        assert f"finish_reason: {reason}" in out and "max_tokens:" in out and "completion_tokens:" in out
        assert re.search(r"发了 10 遍", out)


def test_sketch_heights_are_scaled_from_the_made_up_probabilities():
    data = records()
    out = render("S_sketch", data)
    assert out.count('class="skp"') == 3 and out.count('pbar sk') == 15
    assert "自编" in out
