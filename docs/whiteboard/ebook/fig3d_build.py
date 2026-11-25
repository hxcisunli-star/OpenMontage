"""3D figures of the e-book (2026-11-24). A chapter block {"t": "fig3d", "scene": <name>, "records": [ids], "refs": [ids], "title": ..., "after": {id: text}, "opts": {...}}
renders as the static figures of its records (show(), unchanged: this is the fallback without script, without WebGL, with reduced motion) inside a
<div class="fig3d">, plus the scene's data as JSON. assets/fig3d.js (three.js + the part kit + the scenes, bundled here with the local esbuild) turns it into a 3D figure.

Data discipline: every block, note and request a scene draws carries the record id it comes from ("rid"); the adapters below take nothing but record fields and
raise ValueError when a record does not say what the scene needs. Anything the 3D figure computes or arranges (an order, a gap) is marked 示意 in its data.
`refs` are records the scene also uses that are shown as static figures elsewhere on the same page (the build checks they are)."""
import html
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REGISTRY_FILE = HERE / "fig3d" / "scenes.json"
ESBUILD = ROOT / "remotion-composer/node_modules/.bin/esbuild"
THREE_MODULE = ROOT / "projects/_ebook/vendor/three/build/three.module.js"
THREE_LICENSE = ROOT / "projects/_ebook/vendor/three/LICENSE"
ALLOWED_KEYS = {"t", "scene", "records", "refs", "title", "after", "opts"}
# the only URL-looking strings the bundle may contain: XML namespace names three.js passes to createElementNS (identifiers, never fetched)
BUNDLE_URL_ALLOW = {"http://www.w3.org/1999/xhtml", "http://www.w3.org/2000/svg"}

esc = lambda s: html.escape(str(s), quote=True)


def registry():
    reg = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    return {k: v for k, v in reg.items() if not k.startswith("_")}


def _fail(b, why):
    raise ValueError(f"fig3d {b.get('scene')!r} {b.get('records')!r}: {why}")


def tag_text(tag_html):
    return re.sub(r"<[^>]+>", "", tag_html).strip()


# ------------------------------------------------------------ adapters: record fields -> scene data
def short_model(m):
    return str(m).split("/")[-1]


ORDINAL = ["第一个模型", "第二个模型", "第三个模型", "第四个模型"]


def _model_labels(models):
    order = list(dict.fromkeys(models))
    if len(order) > len(ORDINAL):
        raise ValueError("more than four models in one figure")
    return {m: ORDINAL[i] for i, m in enumerate(order)}


def answer_tower(records, ids, refs, opts):
    sets, qkeys = [], {}
    rows = [(rid, records[rid]) for rid in ids + refs]
    labels = _model_labels([r["model"] for _, r in rows])
    kinds = set()
    for rid, r in rows:
        kinds.add(r["kind"])
        n = int(r["n"])
        q = str(r.get("prompt") or r["title"])
        qk = qkeys.setdefault(q, f"q{len(qkeys)}")
        if r["kind"] == "towers":
            groups = [{"text": str(g["text"]), "count": int(g["count"])} for g in r["groups"]]
            if sum(g["count"] for g in groups) != n or any(g["count"] < 1 for g in groups):
                raise ValueError(f"{rid}: the towers do not add up to its {n} runs")
            runs = [i for i, g in enumerate(groups) for _ in range(g["count"])]
            variants = [{"key": "all", "label": "", "order": "shiyi", "runs": runs, "groups": groups}]
            vlabel = ""
        elif r["kind"] == "rows":
            variants = []
            for j, row in enumerate(r["rows"]):
                colors = [int(c) for c in row["colors"]]
                k = int(row["versions"])
                if len(colors) != n or len(set(colors)) != k or sorted(set(colors)) != list(range(k)):
                    raise ValueError(f"{rid} row {row['label']!r}: {n} runs and {k} versions do not match its colours")
                if [c for i, c in enumerate(colors) if c not in colors[:i]] != list(range(k)):
                    raise ValueError(f"{rid} row {row['label']!r}: answer numbers are not in order of first appearance")
                groups = [{"text": f"第 {c + 1} 种", "count": colors.count(c)} for c in range(k)]
                variants.append({"key": f"v{j}", "label": str(row["label"]), "order": "shice", "runs": colors, "groups": groups})
            vlabel = "温度" if all(v["label"].startswith("温度") for v in variants) else "档位"
        else:
            raise ValueError(f"{rid}: kind {r['kind']!r} is not an answer tower")
        for v in variants:
            texts = [g["text"] for g in v["groups"]]
            p = len(os.path.commonprefix(texts)) if len(texts) > 1 else 0
            for g in v["groups"]:
                t = g["text"]
                if len(t) <= 9:
                    g["short"] = t
                elif p >= 4:          # answers that start alike (a continuation): label each from where it parts from the others (Antigravity review)
                    g["short"] = "…" + t[max(0, p - 1):max(0, p - 1) + 8] + ("…" if len(t) > p + 7 else "")
                else:
                    g["short"] = t[:8] + "…"
        sets.append({"rid": rid, "q": q, "qkey": qk, "model": str(r["model"]), "mname": short_model(r["model"]), "mlabel": labels[r["model"]],
                     "n": n, "vlabel": vlabel, "variants": variants})
    note = ("积木落下的先后是示意（记录里只有每种回答出现的遍数）；块数和塔数是实测。" if "towers" in kinds else
            "积木按记录里的遍序落下：哪一遍是哪种回答、块数、塔数都是实测；同色只表示同一种回答，原话在静态图的记录里。")
    return {"sets": sets, "note": note}


CN_DIGIT = dict(zip("零一二三四五六七八九", "0123456789"))
STEP_SEND = re.compile(r"状态码：(没有状态|[零一二三四五六七八九]{3})；等 (\d+) 秒")
NOTE_TOTAL = re.compile(r"场景 ([A-Za-z0-9]+)：发 (\d+) 次，等 (\d+) 秒；结果：([^。]+)。\s*(?:查 (\d+) 次；订单 (\d+) 张。)?\s*(.*)$")


def _policy(rid, r):
    """the limits of our start script, read from its callpanel record (lesson 12 'policy'): every number must be there"""
    fields = {f["name"]: str(f["value"]) for f in (r.get("result") or {}).get("fields", [])}
    def num(name, pat):
        m = re.fullmatch(pat, fields.get(name, ""))
        if not m:
            raise ValueError(f"{rid}: field {name!r} is not in the form the retry timeline reads")
        return m
    waits = [int(x) for x in num("重发前等待", r"([\d、]+) 秒").group(1).split("、")]
    return {"rid": rid, "max_sends": int(num("最多发", r"(\d+) 次").group(1)), "waits": waits,
            "max_single": int(num("单次最多等", r"(\d+) 秒").group(1)), "budget": int(num("总时间预算（含请求、等待和查询）", r"(\d+) 秒").group(1))}


def retry_timeline(records, ids, refs, opts):
    scenarios, policy = [], None
    for rid in ids + refs:
        r = records[rid]
        if r["kind"] == "callpanel":
            if policy:
                raise ValueError("one policy record per retry timeline")
            policy = _policy(rid, r)
            continue
        if r["kind"] != "sequence" or r.get("lanes") != ["我们的脚本", "本机假服务"]:
            raise ValueError(f"{rid}: not a script-and-fake-service sequence")
        m = NOTE_TOTAL.search(r["note"])
        if not m:
            raise ValueError(f"{rid}: the note does not state the totals (发 N 次，等 M 秒；结果：…)")
        code, sends, wait, result, queries, orders, remark = m.groups()
        steps = []
        for st in r["steps"]:
            if (st.get("from"), st.get("to")) != (0, 1):
                raise ValueError(f"{rid}: a step that does not go from the script to the service")
            sm = STEP_SEND.fullmatch(str(st.get("detail", "")))
            if sm:
                status = None if sm.group(1) == "没有状态" else "".join(CN_DIGIT[c] for c in sm.group(1))
                steps.append({"kind": "send", "label": st["label"], "status": status, "status_text": sm.group(1), "wait": int(sm.group(2))})
            elif "查" in st["label"]:
                steps.append({"kind": "query", "label": st["label"], "text": str(st["detail"])})
            else:
                raise ValueError(f"{rid}: step {st['label']!r} is neither a send (状态码：…；等 N 秒) nor a query")
        if sum(1 for x in steps if x["kind"] == "send") != int(sends) or sum(x.get("wait", 0) for x in steps) != int(wait):
            raise ValueError(f"{rid}: the steps do not add up to the note's {sends} sends and {wait} seconds")
        if queries is not None and sum(1 for x in steps if x["kind"] == "query") != int(queries):
            raise ValueError(f"{rid}: the steps do not add up to the note's {queries} queries")
        scenarios.append({"rid": rid, "title": r["title"], "code": code, "steps": steps,
                          "total": {"sends": int(sends), "wait": int(wait), "result": result, "queries": None if queries is None else int(queries), "orders": None if orders is None else int(orders)},
                          "remark": remark.strip()})
    if not scenarios:
        raise ValueError("a retry timeline needs at least one sequence record")
    if policy:
        for sc in scenarios:
            sends = [x for x in sc["steps"] if x["kind"] == "send"]
            if len(sends) > policy["max_sends"] or any(x["wait"] > policy["max_single"] for x in sends) or sum(x["wait"] for x in sends) > policy["budget"]:
                raise ValueError(f"{sc['rid']}: the scenario breaks the policy it is shown with")
    return {"scenarios": scenarios, "policy": policy,
            "note": "本机模拟，不是服务商的样子。等待的长短按记录里的秒数画；一次请求本身在轴上占的宽度是示意（记录里没有它花了多久）。"}


ROLE_KEYS = {"system": "l4-system", "user": "user", "assistant": "model"}


def _papers(rid, notes):
    out = []
    for i, n in enumerate(notes):
        if n.get("role") not in ROLE_KEYS or not str(n.get("text", "")).strip():
            raise ValueError(f"{rid}: note {i + 1} has no known role or no text")
        out.append({"rid": rid, "i": i, "role": n["role"], "role_cn": n.get("role_cn") or {"system": "系统", "user": "用户", "assistant": "助手"}[n["role"]],
                    "text": str(n["text"]), "stamp": bool(n.get("stamp", n["role"] == "assistant")), "state": n.get("state")})
    return out


def note_stack(records, ids, refs, opts):
    recs = [(rid, records[rid]) for rid in ids + refs]
    kinds = {r["kind"] for _, r in recs}
    if kinds == {"window"}:
        if len(recs) != 2:
            raise ValueError("the window story takes the whole stack and the cut stack (two window records)")
        (wr, whole), (cr, cut) = recs
        a, b = _papers(wr, whole["notes"]), _papers(cr, cut["notes"])
        if [(x["role"], x["text"]) for x in a] != [(x["role"], x["text"]) for x in b]:
            raise ValueError(f"{wr} and {cr} do not hold the same notes")
        if not all(x["state"] in ("pinned", "kept") for x in a) or any(x["state"] not in ("pinned", "kept", "torn") for x in b):
            raise ValueError(f"{wr} must hold the whole stack and {cr} the cut one")
        if not any(x["state"] == "kept" for x in b):
            raise ValueError(f"{cr}: no kept note, so there is no window to draw")
        if [x["role"] for x in b if x["state"] == "pinned"] != ["system"]:
            raise ValueError(f"{cr}: exactly one pinned system note")
        kept = [x["i"] for x in b if x["state"] == "kept"]
        if kept != list(range(len(b) - len(kept), len(b))):
            raise ValueError(f"{cr}: the kept notes are not the most recent ones")
        folder = (cut.get("folder") or {})
        if int(folder.get("count", -1)) != sum(1 for x in b if x["state"] == "torn"):
            raise ValueError(f"{cr}: the folder count is not the number of torn notes")
        return {"mode": "window", "whole": a, "cut": b, "keep": len(kept), "folder": str(folder.get("label", "")),
                "note": "纸条的取舍和位置是示意（窗口记录本身标的就是示意）；纸条上的字逐字取自本课固定的历史。"}
    stacks = [(rid, r) for rid, r in recs if r["kind"] == "stack"]
    grids = {rid: r for rid, r in recs if r["kind"] == "grids"}
    links = (opts or {}).get("links") or {}
    if not stacks or set(links) != {rid for rid, _ in stacks}:
        raise ValueError("a note-stack figure over stack records needs opts.links: {stack record: [grid record, row label]} for every stack")
    variants = []
    stack_by_id = dict(stacks)
    for rid in links:                      # the order the chapter tells them in (opts.links), not the order of the block's records
        r = stack_by_id[rid]
        grid_id, label = links[rid]
        if grid_id not in grids:
            raise ValueError(f"{rid}: linked grid {grid_id} is not in the block")
        rows = [row for row in grids[grid_id]["rows"] if row.get("label") == label]
        if not rows:
            raise ValueError(f"{rid}: grid {grid_id} has no row {label!r}")
        results = []
        for row in rows:
            t = row["tally"]
            n = sum(1 for c in row["cells"] if c.get("class") == t["class"])
            if n != int(t["n"]) or len(row["cells"]) != int(t["total"]):
                raise ValueError(f"{grid_id} row {label!r}: the tally does not match its cells")
            legend = {x["class"]: x["text"] for x in grids[grid_id].get("legend", [])}
            results.append({"rid": grid_id, "label": label, "model": row.get("model", ""), "short": t["short"], "n": n, "total": int(t["total"]), "class": t["class"],
                            "cells": [c.get("class") for c in row["cells"]], "dots": [c.get("dot") is True for c in row["cells"]], "legend": legend,
                            "dot_legend": str(grids[grid_id].get("dot_legend", ""))})
        variants.append({"rid": rid, "title": r["title"], "notes": _papers(rid, r["notes"]), "note": r.get("note", ""), "results": results})
    if set(grids) - {links[rid][0] for rid, _ in stacks}:
        raise ValueError("a grid record in the block that no stack links to")
    from blocks import _l4_grid_labeler          # who judged the runs, in the static figure's own words (Codex review F12: these were judged by two AI models, not by a program)
    judged = "；".join(dict.fromkeys(_l4_grid_labeler(g) for g in grids.values()))
    return {"mode": "variants", "variants": variants, "setting": next(iter(grids.values())).get("setting", ""),
            "question": str((opts or {}).get("question", "")), "judged": judged,
            "note": f"纸条上的字逐字取自请求记录；每格十遍的结果是实测，标注：{judged}。纸条怎么摆是示意。"}


def token_blocks(records, ids, refs, opts):
    """the receipt of one request, as blocks: the fixed wrapper and the content; the split rests on the chapter's premise that "a" is one token (so it is marked 推算)"""
    rows = [(rid, records[rid]) for rid in ids + refs]
    labels = _model_labels([r["model"] for _, r in rows])
    by_model = {}
    for rid, r in rows:
        toks = [int(x) for x in r["prompt_tokens"]]
        if len(set(toks)) != 1 or int(r["median_prompt_tokens"]) != toks[0]:
            raise ValueError(f"{rid}: the runs disagree; the blocks need one number")
        by_model.setdefault(r["model"], []).append({"rid": rid, "text": str(r["prompt"]), "tokens": toks[0], "runs": len(toks), "chars": int(r["chars"])})
    base = (opts or {}).get("unit_text", "a")
    texts = {m: [x["text"] for x in items] for m, items in by_model.items()}
    if len({tuple(sorted(t)) for t in texts.values()}) != 1:
        raise ValueError(f"every model needs the same texts (the figure lets the reader switch models): {texts}")          # Codex review F8
    models = []
    for m, items in by_model.items():
        unit = [x for x in items if x["text"] == base]
        if len(unit) != 1:
            raise ValueError(f"{m}: the block needs exactly one record of the one-token text {base!r}")
        wrapper = unit[0]["tokens"] - 1
        for x in items:
            x["wrapper"] = wrapper
            x["content"] = x["tokens"] - wrapper
            if x["content"] < 1:
                raise ValueError(f"{x['rid']}: fewer tokens than the wrapper")
        models.append({"model": m, "mname": short_model(m), "mlabel": labels[m], "items": items})
    return {"models": models, "unit_text": base,
            "note": f"小票上的总数是实测；“包装”和“内容”各占几块是推算：按本章的前提“单个字母 {base} 只占 1 个词元”，用总数减出来。"}


ADAPTERS = {"answer-tower": answer_tower, "retry-timeline": retry_timeline, "note-stack": note_stack, "token-blocks": token_blocks}


def scene_data(scene, records, ids, refs, opts):
    if scene not in ADAPTERS:
        raise ValueError(f"no adapter for scene {scene!r}")
    return ADAPTERS[scene](records, ids, refs, opts or {})


def rids_in(data):
    """every record id the scene data refers to (the check that each drawn thing maps back to a record)"""
    out = set()
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "rid":
                out.add(v)
            else:
                out |= rids_in(v)
    elif isinstance(data, list):
        for v in data:
            out |= rids_in(v)
    return out


# ------------------------------------------------------------ the block
def render_fig3d(b, ctx):
    from blocks import show, show_parts          # blocks imports this module lazily; no import cycle at load time
    reg = registry()
    if set(b) - ALLOWED_KEYS:
        _fail(b, f"unknown keys {sorted(set(b) - ALLOWED_KEYS)}")
    scene = b.get("scene")
    if scene not in reg or reg[scene].get("demo"):
        _fail(b, "scene is not registered in fig3d/scenes.json (or is a demo-only scene)")
    ids, refs = b.get("records"), b.get("refs", [])
    if not isinstance(ids, list) or not ids or not all(isinstance(x, str) and x for x in ids) or len(set(ids)) != len(ids):
        _fail(b, "records must be a non-empty list of distinct record ids")
    if not isinstance(refs, list) or not all(isinstance(x, str) and x for x in refs) or len(set(refs)) != len(refs) or set(refs) & set(ids):
        _fail(b, "refs must be distinct record ids not in records")
    for rid in ids + refs:
        if rid not in ctx.records:
            _fail(b, f"record {rid!r} is not in the chapter's records")
        if ctx.records[rid].get("kind") not in reg[scene]["kinds"]:
            _fail(b, f"record {rid!r} has kind {ctx.records[rid].get('kind')!r}; scene {scene} takes {reg[scene]['kinds']}")
    after = b.get("after", {})
    if not isinstance(after, dict) or set(after) - set(ids):
        _fail(b, "after must map some of the records to a sentence")
    statics = "".join(show(dict({"id": rid}, **({"after": after[rid]} if rid in after else {})), ctx) for rid in ids)
    caps = {}
    for rid in ids + refs:
        _, cap, tag = show_parts(ctx.records[rid], ctx)
        caps[rid] = {"tag": tag_text(tag), "cap": cap}
    data = scene_data(scene, ctx.records, ids, refs, b.get("opts"))
    stray = rids_in(data) - set(ids) - set(refs)
    if stray:
        _fail(b, f"scene data names records outside the block: {sorted(stray)}")
    if set(ids) - rids_in(data):
        _fail(b, f"records not used by the scene: {sorted(set(ids) - rids_in(data))}")
    title = str(b.get("title") or reg[scene]["name"])
    data = dict(data, title=title, caps=caps, scene=scene, afters={rid: str(t) for rid, t in after.items()})          # the static figures' own "after" sentences go with the 3D figure too (Codex review F11)
    if not hasattr(ctx, "fig3d_refs"):
        ctx.fig3d_refs = []
    ctx.fig3d_refs.extend(refs)
    payload = json_for_script(data)
    return (f'<div class="fig3d" data-scene="{esc(scene)}" data-records="{esc(",".join(ids))}"' + (f' data-refs="{esc(",".join(refs))}"' if refs else "") + ">"
            f'<div class="fig3d-head" hidden><span class="tag tag-3d">立体图</span><span class="fig3d-title">{esc(title)}</span></div>'
            f'<div class="fig3d-static">{statics}</div>'
            f'<script type="application/json" class="fig3d-data">{payload}</script></div>')


def json_for_script(data):
    """JSON inside <script type="application/json">: every "<" written as \\u003c, so no text in a record (</script>, <!--<script>) can end or bend the script element (Codex review F1)"""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def has_fig3d(chapter):
    return any(blk.get("t") == "fig3d" for s in chapter["sections"] for blk in s["blocks"])


def script_tag(assets_root):
    return f'<script defer src="{esc(assets_root)}fig3d.js"></script>'


# ------------------------------------------------------------ the bundle
def bundle_banner():
    lic = THREE_LICENSE.read_text(encoding="utf-8").strip()
    if "*/" in lic:
        raise ValueError("three.js LICENSE text would end the banner comment")
    return ("/* fig3d: the 3D figures of the e-book (OpenMontage, AGPL-3.0). This file also contains three.js "
            + json.loads((ROOT / "projects/_ebook/vendor/VERSIONS.json").read_text(encoding="utf-8"))["three"]["version"]
            + ", under the following licence:\n\n" + lic + "\n*/")


def build_bundle(dst, scenes=None):
    """bundle three.js (pinned in projects/_ebook/vendor) + core/ + scenes/<name>.js into one classic script (works from file:// too)"""
    if not ESBUILD.is_file():
        raise FileNotFoundError(f"esbuild not found at {ESBUILD} (the one installed with remotion-composer; nothing is installed for this)")
    if not THREE_MODULE.is_file():
        raise FileNotFoundError("three.js is not in projects/_ebook/vendor: run docs/whiteboard/ebook/fetch_vendor.py")
    names = list(scenes or registry())
    for name in names:
        src = HERE / "fig3d" / "scenes" / f"{name}.js"
        if not src.is_file() or f"name: '{name}'" not in src.read_text(encoding="utf-8"):
            raise ValueError(f"scene {name}: fig3d/scenes/{name}.js missing or does not declare name: '{name}'")
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fig3d-") as td:
        entry = Path(td) / "entry.js"
        lines = [f"import {{ boot }} from {json.dumps(str(HERE / 'fig3d/core/mount.js'))};"]
        lines += [f"import s{i} from {json.dumps(str(HERE / 'fig3d/scenes' / (n + '.js')))};" for i, n in enumerate(names)]
        lines.append(f"boot([{', '.join(f's{i}' for i in range(len(names)))}]);")
        entry.write_text("\n".join(lines) + "\n", encoding="utf-8")
        cmd = [str(ESBUILD), str(entry), "--bundle", "--format=iife", "--minify", "--legal-comments=none", "--target=es2020", "--charset=utf8",
               f"--alias:three={THREE_MODULE}", f"--outfile={dst}", "--log-level=warning", f"--banner:js={bundle_banner()}"]
        subprocess.run(cmd, check=True, cwd=td)
    text = dst.read_text(encoding="utf-8")
    urls = set(re.findall(r"https?://[^\s'\"`)\\]+", text))
    if urls - BUNDLE_URL_ALLOW:
        raise ValueError(f"the bundle contains URL-looking strings: {sorted(urls - BUNDLE_URL_ALLOW)[:5]}")
    return dst


# ------------------------------------------------------------ the demo page (not part of the book): the same part kit on two other courses
def _demo_rc():
    rs = [{"key": "10k", "text": "10 千欧", "ohm": 10000}, {"key": "22k", "text": "22 千欧", "ohm": 22000}, {"key": "47k", "text": "47 千欧", "ohm": 47000}]          # τ from 0.1 s to 4.7 s: every curve shows its shape in the 10-second window
    cs = [{"key": "10u", "text": "10 微法", "farad": 1e-5}, {"key": "47u", "text": "47 微法", "farad": 4.7e-5}, {"key": "100u", "text": "100 微法", "farad": 1e-4}]
    return {"rid": "demo-rc", "volts": 5, "window_s": 10, "r_options": rs, "c_options": cs,
            "caps": {"demo-rc": {"tag": "示意", "cap": "按公式 V_C(t) ＝ V（1 − e^(−t/τ)）、τ ＝ R × C 算出来的示意，不是测量；动画把 10 秒压成 4 秒播放。"}},
            "note": "电子电工演示：部件包换一门课也能用。"}


CIRCLED = "〇①②③④⑤⑥⑦⑧⑨"


def _demo_cpu():
    """a toy machine, run here step by step: the page only shows what this simulation computed"""
    mem = ["LOAD R1, [4]", "ADD R1, R2", "STORE R1, [5]", "HALT", "7", "0"]
    st = {"pc": 0, "ir": "", "r1": 0, "r2": 5, "mem": list(mem)}
    snap = lambda: {"pc": st["pc"], "ir": st["ir"], "r1": st["r1"], "r2": st["r2"], "mem": list(st["mem"])}
    start, steps, n = snap(), [], 0
    while True:
        n += 1
        addr = st["pc"]
        st["ir"] = st["mem"][addr]
        st["pc"] += 1
        steps.append({"title": f"{CIRCLED[n]} 取指", "lit": ["pc", f"mem{addr}", "ir"], "bus": True, "after": snap(),
                      "changed": f"PC 指着地址 {addr}：把内存里的“{st['ir']}”经总线取进 IR，PC 加一变成 {st['pc']}。"})
        op = st["ir"].split()[0]
        steps.append({"title": f"{CIRCLED[n]} 译码", "lit": ["ir", "cu"], "bus": False, "after": snap(),
                      "changed": {"LOAD": "控制器读懂了：把内存里的一个数装进 R1。", "ADD": "控制器读懂了：R1 和 R2 相加，结果放回 R1。",
                                  "STORE": "控制器读懂了：把 R1 的数存回内存。", "HALT": "控制器读懂了：停机。"}[op]})
        if op == "HALT":
            steps.append({"title": "停机", "lit": ["cu"], "bus": False, "after": snap(), "changed": "程序做完了：地址 5 里现在是 R1 算出来的数。"})
            break
        if op == "LOAD":
            a = int(st["ir"].split("[")[1].rstrip("]"))
            st["r1"] = int(st["mem"][a])
            lit, ch = [f"mem{a}", "r1"], f"从地址 {a} 读出 {st['r1']}，经总线装进 R1。"
        elif op == "ADD":
            before = st["r1"]
            st["r1"] = st["r1"] + st["r2"]
            lit, ch = ["r1", "r2", "alu"], f"R1（{before}）和 R2（{st['r2']}）送进 ALU 相加，结果 {st['r1']} 放回 R1。"
        else:
            a = int(st["ir"].split("[")[1].rstrip("]"))
            st["mem"][a] = str(st["r1"])
            lit, ch = ["r1", f"mem{a}"], f"R1 的 {st['r1']} 经总线写进地址 {a}。"
        steps.append({"title": f"{CIRCLED[n]} 执行", "lit": lit, "bus": True, "after": snap(), "changed": ch})
    return {"rid": "demo-cpu", "memory": [{"addr": i, "text": t} for i, t in enumerate(mem)], "start": start, "steps": steps, "program": mem,
            "caps": {"demo-cpu": {"tag": "示意", "cap": "一台玩具计算机的教学模型；每一步的数由构建脚本把这三条指令真的跑一遍算出来，不是哪台真机器的样子。"}},
            "note": "计算机组成演示：部件包换一门课也能用。"}


def build_demo(out_dir):
    """the part-kit demo page: two scenes from other courses (electronics, computer organisation); not in the book. Returns the page path."""
    out = Path(out_dir)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "assets/book.css").write_bytes((HERE / "book.css").read_bytes())
    build_bundle(out / "assets/fig3d.js", ["rc-charge", "fetch-decode"])
    rc, cpu = _demo_rc(), _demo_cpu()
    taus = "".join(f"<tr><td>{esc(r['text'])}</td>" + "".join(f"<td>{r['ohm'] * c['farad']:.3g} 秒</td>" for c in rc["c_options"]) + "</tr>" for r in rc["r_options"])
    rc_static = (f'<figure class="show" data-record="demo-rc"><div class="fh">RC 充电：各档的时间常数 τ ＝ R × C</div><div class="scroll"><table class="t"><tr><th>电阻 ＼ 电容</th>'
                 + "".join(f"<th>{esc(c['text'])}</th>" for c in rc["c_options"]) + f"</tr>{taus}</table></div>"
                 f'<figcaption class="rec"><span class="tag tag-shiyi">示意</span> {esc(rc["caps"]["demo-rc"]["cap"])}</figcaption></figure>')
    cpu_static = (f'<figure class="show" data-record="demo-cpu"><div class="fh">取指、译码、执行：三条指令一步一步</div><ol class="steps">'
                  + "".join(f"<li><b>{esc(s['title'])}</b>：{esc(s['changed'])}</li>" for s in cpu["steps"]) +
                  f'</ol><figcaption class="rec"><span class="tag tag-shiyi">示意</span> {esc(cpu["caps"]["demo-cpu"]["cap"])}</figcaption></figure>')
    def block(scene, title, data, static):
        payload = json_for_script(dict(data, title=title, scene=scene))
        return (f'<div class="fig3d" data-scene="{scene}" data-records="{data["rid"]}"><div class="fig3d-head" hidden><span class="tag tag-3d">立体图</span><span class="fig3d-title">{esc(title)}</span></div>'
                f'<div class="fig3d-static">{static}</div><script type="application/json" class="fig3d-data">{payload}</script></div>')
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>立体图部件包：换一门课也能用（演示页，不在书里）</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<link rel="stylesheet" href="assets/book.css">
</head>
<body>
<div class="page chapter"><div class="layout"><main class="main">
<header class="sec-head"><h2>立体图部件包：换一门课也能用</h2></header>
<p>这一页不在书里。它用和智能体课同一套零件（积木、导线和流动的光点、档位面板、读数条、曲线面板、分步控制、先猜再看），做两门别的课的小场景，也当部件包的回归测试。两张图都是示意：数由公式或一段小程序算出来，不是测量。</p>
<section class="sec" id="sec-rc"><header class="sec-head"><span class="no">1</span><h2>电子电工：RC 充电</h2></header>
{block("rc-charge", "RC 充电：拨电阻和电容，看电压曲线", rc, rc_static)}</section>
<section class="sec" id="sec-cpu"><header class="sec-head"><span class="no">2</span><h2>计算机组成：取指、译码、执行</h2></header>
{block("fetch-decode", "取指·译码·执行：一条指令怎么走", cpu, cpu_static)}</section>
</main></div></div>
<script defer src="assets/fig3d.js"></script>
</body>
</html>
"""
    (out / "index.html").write_text(page, encoding="utf-8")
    return out / "index.html"


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "demo":
        print("demo page:", build_demo(sys.argv[2]))
    else:
        raise SystemExit("usage: fig3d_build.py demo <out dir>   (the book's own bundle is built by build_site.py)")
