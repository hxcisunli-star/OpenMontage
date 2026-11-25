"""3D figures (fig3d block, 2026-11-24): the fallback is exactly the static figures, the scene data maps every drawn thing back to a record,
bad blocks fail the build, the registry and the scene files agree, and the bundle holds three.js's licence and no URL."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "docs/whiteboard/ebook"))
import blocks  # noqa: E402
import fig3d_build as f3  # noqa: E402

L1 = ROOT / "projects/agent-what-is-llm-cn/validation/records.json"
L3 = ROOT / "projects/agent-sampling-temp-cn/validation/ebook_records.json"
need_data = pytest.mark.skipif(not (L1.is_file() and L3.is_file()), reason="lesson records are not in this checkout")


def ctx_for(path):
    return blocks.Ctx(json.loads(path.read_text(encoding="utf-8")), {}, {})


@need_data
def test_fallback_is_exactly_the_static_figures_and_counts_as_shown():
    ctx = ctx_for(L1)
    ids = ["H1_open_ds", "H1_open_qw", "H1_fact_ds"]
    out = blocks.render_block({"t": "fig3d", "scene": "answer-tower", "records": ids, "after": {"H1_open_ds": "一句话。"}}, ctx)
    ref = blocks.Ctx(ctx.records, {}, {})
    want = "".join(blocks.show(dict({"id": r}, **({"after": "一句话。"} if r == "H1_open_ds" else {})), ref) for r in ids)
    static = re.search(r'<div class="fig3d-static">(.*?)</div><script', out, re.S).group(1)
    assert static == want
    assert ctx.used_records == ids
    assert '<div class="fig3d-head" hidden>' in out and 'data-records="H1_open_ds,H1_open_qw,H1_fact_ds"' in out


@need_data
def test_every_tower_block_maps_to_a_record_run():
    ctx = ctx_for(L1)
    ids = ["H1_open_ds", "H1_open_qw", "H1_fact_ds", "H1_fact_qw"]
    data = f3.answer_tower(ctx.records, ids, [], {})
    assert [s["rid"] for s in data["sets"]] == ids
    for s in data["sets"]:
        r = ctx.records[s["rid"]]
        v = s["variants"][0]
        assert len(v["runs"]) == r["n"] == sum(g["count"] for g in v["groups"])
        assert [g["count"] for g in v["groups"]] == [g["count"] for g in r["groups"]]
        assert [g["text"] for g in v["groups"]] == [g["text"] for g in r["groups"]]
        assert v["order"] == "shiyi"          # the record has no run order: the drop order is a sketch
    assert {s["mlabel"] for s in data["sets"]} == {"第一个模型", "第二个模型"}
    assert "示意" in data["note"]


@need_data
def test_rows_keep_the_measured_run_order():
    ctx = ctx_for(L3)
    data = f3.answer_tower(ctx.records, ["ROWS_cap_ds", "ROWS_hi_name_ds"], [], {})
    for s in data["sets"]:
        r = ctx.records[s["rid"]]
        assert [v["label"] for v in s["variants"]] == [row["label"] for row in r["rows"]]
        for v, row in zip(s["variants"], r["rows"]):
            assert v["runs"] == row["colors"] and len(v["groups"]) == row["versions"] and v["order"] == "shice"
    assert s["vlabel"] == "温度"


@need_data
@pytest.mark.parametrize("damage", ["count", "versions", "order"])
def test_adapter_refuses_records_that_do_not_add_up(damage):
    ctx = ctx_for(L1 if damage == "count" else L3)
    recs = copy.deepcopy(ctx.records)
    if damage == "count":
        recs["H1_open_ds"]["groups"][0]["count"] += 1
        ids = ["H1_open_ds"]
    elif damage == "versions":
        recs["ROWS_cap_ds"]["rows"][0]["versions"] = 2
        ids = ["ROWS_cap_ds"]
    else:
        recs["ROWS_hi_name_ds"]["rows"][0]["colors"][0], recs["ROWS_hi_name_ds"]["rows"][0]["colors"][1] = 1, 0
        ids = ["ROWS_hi_name_ds"]
    with pytest.raises(ValueError):
        f3.answer_tower(recs, ids, [], {})


@need_data
@pytest.mark.parametrize("block,why", [
    ({"t": "fig3d", "scene": "nope", "records": ["H1_open_ds"]}, "not registered"),
    ({"t": "fig3d", "scene": "rc-charge", "records": ["H1_open_ds"]}, "demo-only"),
    ({"t": "fig3d", "scene": "answer-tower", "records": []}, "non-empty"),
    ({"t": "fig3d", "scene": "answer-tower", "records": ["H1_open_ds", "H1_open_ds"]}, "distinct"),
    ({"t": "fig3d", "scene": "answer-tower", "records": ["XX"]}, "not in the chapter"),
    ({"t": "fig3d", "scene": "answer-tower", "records": ["H6_qa"]}, "kind"),
    ({"t": "fig3d", "scene": "answer-tower", "records": ["H1_open_ds"], "refs": ["H1_open_ds"]}, "refs"),
    ({"t": "fig3d", "scene": "answer-tower", "records": ["H1_open_ds"], "after": {"H1_fact_ds": "x"}}, "after"),
    ({"t": "fig3d", "scene": "answer-tower", "records": ["H1_open_ds"], "colour": "red"}, "unknown keys"),
])
def test_bad_blocks_fail_the_build(block, why):
    with pytest.raises(ValueError, match=why):
        blocks.render_block(block, ctx_for(L1))


def test_registry_and_scene_files_agree():
    reg = f3.registry()
    files = {p.stem for p in (ROOT / "docs/whiteboard/ebook/fig3d/scenes").glob("*.js")}
    assert files <= set(reg), f"scene files without a registry entry: {files - set(reg)}"
    for name in files:
        assert f"name: '{name}'" in (ROOT / f"docs/whiteboard/ebook/fig3d/scenes/{name}.js").read_text(encoding="utf-8")
    for name, entry in reg.items():
        assert entry.get("name") and isinstance(entry.get("kinds"), list)
        if not entry.get("demo"):
            assert entry["kinds"], name


def test_rids_in_finds_nested_ids():
    assert f3.rids_in({"a": [{"rid": "X", "b": {"rid": "Y"}}], "rid": "Z"}) == {"X", "Y", "Z"}


def test_our_fig3d_code_has_no_urls_and_no_innerhtml():
    for path in (ROOT / "docs/whiteboard/ebook/fig3d").rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"https?://", text.replace("'http://www.w3.org/2000/svg'", "")), path          # the SVG namespace name is an identifier, not a load
        assert "innerHTML" not in text and "eval(" not in text and "new Function" not in text, path


@pytest.mark.skipif(not (f3.ESBUILD.is_file() and f3.THREE_MODULE.is_file()), reason="esbuild or the pinned three.js is not here")
def test_bundle_carries_the_licence_and_no_url(tmp_path):
    out = f3.build_bundle(tmp_path / "fig3d.js", ["answer-tower"])
    text = out.read_text(encoding="utf-8")
    assert text.startswith("/* fig3d:") and "three.js authors" in text[:3000] and "Permission is hereby granted" in text[:3000]
    assert set(re.findall(r"https?://[^\s'\"`)\\]+", text)) <= f3.BUNDLE_URL_ALLOW
    with pytest.raises(ValueError):
        f3.build_bundle(tmp_path / "x.js", ["no-such-scene"])


def test_script_json_cannot_end_or_bend_the_script_element():          # Codex review F1
    s = f3.json_for_script({"t": "</script><!--<script>"})
    assert "<" not in s and json.loads(s) == {"t": "</script><!--<script>"}


R4 = ROOT / "projects/agent-roles-history-cn/validation/ebook_records.json"
R6 = ROOT / "projects/agent-long-chat-cn/validation/ebook_records.json"


@pytest.mark.skipif(not R4.is_file(), reason="lesson 4 records are not in this checkout")
def test_note_stack_says_who_judged_the_runs():          # Codex review F12: these grids were labelled by two AI models
    r = json.loads(R4.read_text(encoding="utf-8"))
    d = f3.note_stack(r, ["ST_swap", "GR_neg"], ["ST_removed"], {"links": {"ST_removed": ["GR_neg", "去掉助手"], "ST_swap": ["GR_neg", "换成“好的，我明白了。”"]}})
    assert "AI" in d["note"] and "程序按规则判" not in d["note"]
    assert [v["rid"] for v in d["variants"]] == ["ST_removed", "ST_swap"]
    for v in d["variants"]:
        for res in v["results"]:
            assert len(res["cells"]) == res["total"] == 10 and res["cells"].count(res["class"]) == res["n"]


@pytest.mark.skipif(not R6.is_file(), reason="lesson 6 records are not in this checkout")
def test_window_needs_a_kept_note():          # Codex review F14
    r = copy.deepcopy(json.loads(R6.read_text(encoding="utf-8")))
    for n in r["WIN_cut"]["notes"]:
        if n["state"] == "kept":
            n["state"] = "torn"
    r["WIN_cut"]["folder"]["count"] = sum(1 for n in r["WIN_cut"]["notes"] if n["state"] == "torn")
    with pytest.raises(ValueError, match="kept"):
        f3.note_stack(r, ["WIN_whole", "WIN_cut"], [], {})


R12 = ROOT / "projects/agent-reliability-cn/validation/ebook_records.json"


@pytest.mark.skipif(not R12.is_file(), reason="lesson 12 records are not in this checkout")
def test_retry_scenarios_must_fit_the_policy_budget():          # Codex review F15
    r = copy.deepcopy(json.loads(R12.read_text(encoding="utf-8")))
    d = f3.retry_timeline(r, ["policy", "sim_S07", "sim_S06"], [], {})
    assert [s["total"]["sends"] for s in d["scenarios"]] == [3, 4]
    for f in r["policy"]["result"]["fields"]:
        if f["name"].startswith("总时间预算"):
            f["value"] = "5 秒"
    with pytest.raises(ValueError, match="policy"):
        f3.retry_timeline(r, ["policy", "sim_S07", "sim_S06"], [], {})


@need_data
def test_token_blocks_need_the_same_texts_for_every_model():          # Codex review F8
    r = json.loads((ROOT / "projects/agent-tokens-window-cn/validation/records.json").read_text(encoding="utf-8"))
    d = f3.token_blocks(r, ["U_B0_min_a_ds", "U_B0_min_a_qw"], ["U_B1_nihao_off_ds", "U_B1_nihao_off_qw"], {})
    assert [(x["text"], x["tokens"], x["wrapper"], x["content"]) for x in d["models"][0]["items"]] == [("a", 5, 4, 1), ("你好", 5, 4, 1)]
    with pytest.raises(ValueError, match="same texts"):
        f3.token_blocks(r, ["U_B0_min_a_ds", "U_B0_min_a_qw"], ["U_B1_nihao_off_ds"], {})

