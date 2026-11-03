"""Build the ebook platform of 智能体拆拆装装 into projects/_ebook/site/: a shelf (8 books) -> a book (table of contents by stage) -> a chapter (one outline unit).
A chapter with a source file projects/_ebook/chapters/<unit>.json gets its full text (and its video when it has one); every other unit gets a placeholder page made of the outline's
goal, the plain-language summary and the prerequisites, and says plainly that its text is still being made.
All links are relative and name their file (index.html), so the same build works over http and when index.html is opened from a folder.
Run: PYTHONPATH=. .venv/bin/python docs/whiteboard/ebook/build_site.py [--link-media]"""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from blocks import Ctx, esc, inline, lat, render_block, sentence_plain  # noqa: E402
from labs import copy_lab_assets, lab_config, lab_script_tags, validate_lab, write_lab_config  # noqa: E402

ROOT = HERE.parents[2]
EB = ROOT / "projects" / "_ebook"
SITE = EB / "site"
ARCHIVE = ROOT / "projects/roadmap-agent-engineer/evidence/archive/MANIFEST.tsv"
FONT = ROOT / "remotion-composer/public/fonts/ZCOOLKuaiLe-Regular.ttf"
PATH_TAG = {"核心": "core", "加速": "fast", "选修": "opt", "进阶": "adv"}
BOOK_HUES = [212, 4, 150, 36, 280, 190, 330, 100]       # one accent per book (degrees), so the shelf reads at a glance


def mmss(s):
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def load():
    outline = json.loads((EB / "outline.json").read_text(encoding="utf-8"))
    books = yaml.safe_load((EB / "books.yaml").read_text(encoding="utf-8"))
    stages = {s["id"]: s for s in outline["stages"]}
    units = {}
    for s in outline["stages"]:
        for u in s["units"]:
            units[u["id"]] = dict(u, stage=s["id"], stage_title=s["title"])
    # every unit belongs to exactly one book, in outline order
    seen = {}
    for bi, b in enumerate(books["books"]):
        b["n"] = bi + 1
        b["units"] = []
        for sid in b["stages"]:
            assert sid in stages, f"books.yaml: unknown stage {sid}"
            for u in stages[sid]["units"]:
                assert u["id"] not in seen, f"unit {u['id']} is in two books ({seen[u['id']]} and {b['id']})"
                seen[u["id"]] = b["id"]
                b["units"].append(u["id"])
        for k, uid in enumerate(b["units"], 1):
            units[uid]["book"], units[uid]["no"] = b["id"], k
    assert set(seen) == set(units), f"books.yaml leaves out units: {sorted(set(units) - set(seen))[:5]}"
    assert len(seen) == outline["unit_count"] == 293
    chapters = {}
    for f in sorted((EB / "chapters").glob("*.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        assert c["id"] in units, f"{f.name}: unit {c['id']} is not in the outline"
        chapters[c["id"]] = c
    return outline, books, stages, units, chapters


def archive_urls():
    out = {}
    for line in ARCHIVE.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if len(cols) >= 5 and re.fullmatch(r"A\d+", cols[0]):
            out[cols[0]] = {"url": cols[3], "date": cols[4]}
    return out


# ------------------------------------------------------------------ page frame
def page(title, depth, body, body_class="", scripts=""):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{esc(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<link rel="stylesheet" href="{up}assets/book.css">
</head>
<body class="{body_class}" data-root="{up}">
<div class="bar"><div class="bar-fill" id="progress"></div></div>
{body}
<script src="{up}assets/search-index.js"></script>
<script src="{up}assets/book.js"></script>
{scripts}</body>
</html>
"""


def topbar(depth, crumbs):
    up = "../" * depth
    cr = " › ".join(f'<a href="{esc(h)}">{esc(t)}</a>' if h else f"<span>{esc(t)}</span>" for t, h in crumbs)
    return (f'<div class="topbar"><nav class="crumbs" aria-label="位置">{cr}</nav>'
            f'<form class="search" role="search" onsubmit="return false"><input id="q" type="search" placeholder="搜章节" aria-label="搜章节" autocomplete="off"><div id="hits" class="hits" hidden></div></form>'
            f'<button class="theme" id="theme" type="button" aria-label="切换浅色或深色">◐</button></div>')


def status_chips(u, ch):
    chips = [f'<span class="chip-path {PATH_TAG.get(u["path"], "opt")}">{esc(u["path"])}</span>']
    if ch:
        chips.append('<span class="chip-st on">有正文</span>')
        if ch.get("video"):
            chips.append('<span class="chip-st vid">有视频</span>')
    else:
        chips.append('<span class="chip-st off">正文制作中</span>')
    return "".join(chips)


# ------------------------------------------------------------------ shelf and book pages
def cover_asset(b):
    """projects/_ebook/covers/<book id>.png -> site/assets/covers/<book id>.jpg, 3:4 and 900x1200 (too wide: centred crop; too tall: keep the bottom, the top third is the title space)"""
    src = EB / "covers" / f"{b['id']}.png"
    assert src.is_file(), f"no cover for {b['id']}: run docs/whiteboard/ebook/make_covers.py"
    assert b.get("cover_alt", "").strip(), f"books.yaml: {b['id']} needs a cover_alt (what the picture shows)"
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if w * 4 > h * 3:
        nw = round(h * 3 / 4)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    elif w * 4 < h * 3:
        nh = round(w * 4 / 3)
        im = im.crop((0, h - nh, w, h))
    dst = SITE / "assets/covers" / f"{b['id']}.jpg"
    im.resize((900, 1200), Image.LANCZOS).save(dst, "JPEG", quality=86, optimize=True, progressive=True)


def book_object(b, series, up, mini=False):
    """the picture of one book: cover (illustration, plate with the real-text title), spine, page edge. `up` is the path back to the site root."""
    plate = ""
    if not mini:
        latin = " latin" if re.search(r"[A-Za-z0-9]", b["title"]) else ""
        title = esc(b["title"]).replace("、", "、<br>", 1)             # a long title breaks after its first 、, not in the middle of a word
        plate = f'<div class="plate"><div class="bk-n"><span class="ser">{esc(series)} · </span>第 {b["n"]} 册</div><div class="bk-t{latin}">{title}</div></div>'
    return (f'<div class="book{" mini" if mini else ""}"><div class="cover"><img class="cover-art" src="{up}assets/covers/{esc(b["id"])}.jpg" alt="{esc(b["cover_alt"])}" width="900" height="1200">{plate}</div>'
            f'<span class="spine" aria-hidden="true"></span><span class="edge" aria-hidden="true"></span></div>')


def shelf_html(meta, books, units, chapters):
    cards = []
    for b in books["books"]:
        n = len(b["units"])
        written = sum(1 for u in b["units"] if u in chapters)
        vids = sum(1 for u in b["units"] if u in chapters and chapters[u].get("video"))
        stages = "、".join(sorted({units[u]["stage_title"] for u in b["units"]}, key=lambda t: [units[x]["stage_title"] for x in b["units"]].index(t)))
        ids = ",".join(b["units"])
        cards.append(
            f'<a class="book-card" href="books/{esc(b["id"])}/index.html" style="--bk:{BOOK_HUES[b["n"] - 1]}" data-units="{esc(ids)}">'
            f'<div class="book-wrap">{book_object(b, meta["name"], "")}</div>'
            f'<div class="info"><p class="bk-b">{esc(b["blurb"])}</p><div class="bk-s">{esc(stages)}</div>'
            f'<div class="bk-c"><span><b>{n}</b> 章</span><span><b>{written}</b> 章有正文</span><span><b>{vids}</b> 章有视频</span><span class="rd"><b class="rd-n">0</b> 章读过</span></div></div></a>')
    total = sum(len(b["units"]) for b in books["books"])
    written = len(chapters)
    body = f"""<div class="page narrow home">
{topbar(0, [("书架", None)])}
<header class="top"><div class="titles"><div class="eyebrow">{esc(meta['subtitle'])}</div><h1{lat(meta['name'])}>{esc(meta['name'])}</h1><p class="muted">{esc(meta['tagline'])}</p></div>
<div class="cast"><img src="assets/img/teacher.png" alt="老师"><img src="assets/img/robot.png" alt="AI 小搭档"></div></header>
<div class="callout info"><b>这是制作中的版本</b><p>全部 {total} 个单元的目录都在，但目前只有 {written} 章写完了完整正文；其余章节显示大纲目标和人话版提要，页面上会写明“正文制作中”。</p></div>
<h2 class="shelf-h">书架上的 8 册</h2>
<div class="shelf">{''.join(cards)}</div>
<footer class="foot muted small">旁白为 AI 合成语音；画面里的插画、角色姿势和书封插画为 AI 生成。字体 ZCOOL KuaiLe 采用 SIL Open Font License 1.1，见 assets/fonts/FONT-LICENSE.txt。</footer>
</div>"""
    return page(meta["name"], 0, body, "home")


def book_html(b, books, units, chapters, stages):
    rows, last_stage = [], None
    for uid in b["units"]:
        u = units[uid]
        if u["stage"] != last_stage:
            if last_stage is not None:
                rows.append("</ol></section>")
            st = stages[u["stage"]]
            note = next((n for n in st["notes"] if n.startswith("**阶段目标**")), "")
            rows.append(f'<section class="stage"><h2{lat(st["title"])}>{esc(st["title"])}</h2>' + (f'<p class="muted small">{esc(re.sub(r"[*]", "", note))}</p>' if note else "") + '<ol class="toc">')
            last_stage = u["stage"]
        ch = chapters.get(uid)
        sub = ch["lesson_title"] if ch else u["plain"].get("plain_title", "")
        rows.append(f'<li data-unit="{esc(uid)}"><a href="{esc(uid)}.html"><span class="no">{u["no"]}</span><span class="tt"><b>{esc(u["title"])}</b>'
                    + (f'<span class="sub">{esc(sub)}</span>' if sub else "") + f'</span><span class="chips">{status_chips(u, ch)}<span class="rd-mark" aria-hidden="true"></span></span></a></li>')
    rows.append("</ol></section>")
    n = len(b["units"])
    written = sum(1 for x in b["units"] if x in chapters)
    body = f"""<div class="page narrow" style="--bk:{BOOK_HUES[b['n'] - 1]}">
{topbar(2, [("书架", "../../index.html"), (f"第 {b['n']} 册 {b['title']}", None)])}
<header class="top"><div class="titles"><div class="eyebrow">第 {b['n']} 册 · 共 {n} 章，{written} 章有正文</div><h1{lat(b['title'])}>{esc(b['title'])}</h1><p class="muted">{esc(b['blurb'])}</p></div>{book_object(b, books['series']['name'], '../../', mini=True)}</header>
<div class="legend muted small"><span class="chip-path core">核心</span> 主线必学　<span class="chip-path fast">加速</span> 想快的人走　<span class="chip-path opt">选修</span> 按需　<span class="chip-path adv">进阶</span> 中级工程能力</div>
{''.join(rows)}
<footer class="foot muted small"><a href="../../index.html">← 回书架</a></footer>
</div>"""
    return page(f"第 {b['n']} 册 {b['title']}", 2, body)


# ------------------------------------------------------------------ chapter pages
def collect_lab_ids(chapters):
    seen = set()
    for ch in chapters.values():
        for section in ch["sections"]:
            for block in section["blocks"]:
                if block.get("t") == "lab":
                    ident = validate_lab(block)["id"]
                    if ident in seen:
                        raise ValueError(f"lab {ident}: 全站练习 id 重复")
                    seen.add(ident)
    return seen


def pager(b, uid, units, chapters):
    i = b["units"].index(uid)
    def link(j, label):
        if j < 0 or j >= len(b["units"]):
            return f'<span class="muted">{label}：没有了</span>'
        v = b["units"][j]
        return f'<a href="{esc(v)}.html">{label}：{esc(units[v]["title"])}</a>'
    return f'<nav class="chapter-nav" aria-label="章节导航">{link(i - 1, "← 上一章")}<a href="index.html">本册目录</a>{link(i + 1, "下一章 →")}</nav>'


def prereq_html(u, units):
    out = []
    for pid in u["prereq"]:
        if pid in units:
            v = units[pid]
            out.append(f'<a class="pre" href="../{esc(v["book"])}/{esc(pid)}.html" title="{esc(v["title"])}"><b>{esc(pid)}</b> {esc(v["title"])}</a>')
        else:
            out.append(f'<span class="pre">{esc(pid)}</span>')
    return "".join(out) or '<span class="muted">没有（可以直接学）</span>'


def placeholder_html(u, b, books, units, chapters, stages):
    p = u["plain"]
    terms = "".join(f'<li><b>{esc(t["term"])}</b>：{esc(t["plain"])}</li>' for t in p.get("terms", []))
    body = f"""<div class="page narrow" style="--bk:{BOOK_HUES[b['n'] - 1]}">
{topbar(2, [("书架", "../../index.html"), (f"第 {b['n']} 册 {b['title']}", "index.html"), (f"第 {u['no']} 章", None)])}
<header class="top"><div class="titles"><div class="eyebrow">第 {b['n']} 册 · 第 {u['no']} 章 · {esc(u['id'])} · {esc(u['stage_title'])}</div><h1{lat(u['title'])}>{esc(u['title'])}</h1><p class="muted">{esc(p.get('plain_title', ''))}</p><div class="chips">{status_chips(u, None)}</div></div></header>
<div class="callout warn"><b>这一章的正文还在制作中</b><p>下面是大纲里这个单元的目标和一份人话版提要，让你知道它讲什么、该在什么时候学。完整的正文会按“大纲要点逐条写透＋真实实测＋来源核对＋动手做＋自测”来写，写完才会换掉这一页。</p></div>
<section class="blk"><h2>这一章要做到什么</h2><p>{inline(u['goal'])}</p></section>
<section class="blk"><h2>人话版提要</h2><p>{esc(p.get('what', ''))}</p><p><b>为什么要学：</b>{esc(p.get('why', ''))}</p><p><b>打个比方：</b>{esc(p.get('analogy', ''))}</p>{('<h3 class="sub">本章新词</h3><ul>' + terms + '</ul>') if terms else ''}</section>
<section class="blk"><h2>先学哪些章</h2><div class="pres">{prereq_html(u, units)}</div></section>
<section class="blk"><h2>怎么检验自己学会了</h2><p>{inline(u['check'])}</p></section>
<details class="evidence"><summary>大纲里这个单元的原文要点（给想对照大纲的人）</summary><p class="muted small">这是大纲的原文，没有改成人话；方括号里的 S-编号是来源编号。</p><p>{inline(u['points'])}</p><p><b>实践：</b>{inline(u['practice'])}</p></details>
{pager(b, u['id'], units, chapters)}
</div>"""
    return page(f"{u['id']} {u['title']}", 2, body)


def exercises_html(ex):
    arts = []
    for n, e in enumerate(ex["items"], 1):
        arts.append(f'<article class="exercise" data-ex="{n}"><div class="q"><h3>{esc(e["title"])}</h3>{"".join(f"<p>{esc(l)}</p>" for l in e["q"])}</div>'
                    f'<details class="answer"><summary>{esc(e["a_head"])}</summary>{"".join(f"<p>{esc(l)}</p>" for l in e["a"])}</details></article>')
    return ('<section id="exercises" class="exsec"><header class="sec-head"><span class="no">★</span><h2>课后练习</h2></header>'
            f'<div class="intro">{"".join(f"<p>{esc(l)}</p>" for l in ex["intro"])}</div>{"".join(arts)}'
            f'<div class="record"><h3>{esc(ex["record"][0])}</h3>{"".join(f"<p>{esc(l)}</p>" for l in ex["record"][1:])}</div></section>')


def chapter_html(u, b, books, units, chapters, stages, ctx_data, site_media):
    ch = chapters[u["id"]]
    assets_root = "../" * 2 + "assets/"
    ctx = Ctx(ctx_data["records"], ctx_data["claims"], ctx_data["urls"], assets_root)
    vid = ch.get("video")
    secs, toc = [], []
    first_seek = {}
    frames_by_sec = {}
    for f in ch.get("frames", []):
        frames_by_sec.setdefault(f["sec"], []).append(f)
        first_seek.setdefault(f["sec"], f["seek"])
    for no, s in enumerate(ch["sections"], 1):
        fr = frames_by_sec.get(s["id"], [])
        watch = ""
        if vid and s["id"] in first_seek:
            watch = f'<a class="watch" data-seek="{first_seek[s["id"]]}" href="#lesson-video">▶ 看视频这一段（{mmss(first_seek[s["id"]])} 起）</a>'
        elif s.get("only_book"):
            watch = f'<span class="only-book">{esc(s["only_book"])}</span>'
        strip = ""
        if fr:
            strip = '<div class="frames">' + "".join(
                f'<figure class="frame-fig"><a class="frame" data-seek="{f["seek"]}" href="#lesson-video"><img src="{esc(site_media[f["src"]])}" alt="{esc(f["alt"])}"><span class="at">▶ {mmss(f["seek"])}</span></a>'
                f'<figcaption>视频里这一刻，老师说：<q class="narr">{esc(f["narr"])}</q></figcaption></figure>' for f in fr) + "</div>"
        blocks = "".join(render_block(blk, ctx) for blk in s["blocks"])
        secs.append(f'<section class="sec" id="sec-{esc(s["id"])}"><header class="sec-head"><span class="no">{no}</span><h2{lat(s["title"])}>{esc(s["title"])}</h2>{watch}</header>{strip}{blocks}</section>')
        toc.append(f'<li><a href="#sec-{esc(s["id"])}">{esc(s["title"])}</a></li>')
    toc.append('<li><a href="#exercises">课后练习</a></li>')
    # coverage of the outline's points
    cov = ""
    if ch.get("points"):
        ids = {s["id"] for s in ch["sections"]}
        for p in ch["points"]:
            assert p["sections"] and all(x in ids or x == "exercises" for x in p["sections"]), f"{u['id']}: point {p['id']} points at a section that does not exist"
        cov = ('<details id="coverage" class="evidence"><summary>这一章对照大纲逐条讲了什么</summary><p class="muted small">大纲给这个单元列的每一个要点，在本章哪一节讲：</p><ul>' +
               "".join(f'<li><b>{esc(p["id"])}</b> {esc(p["text"])} → ' + "、".join((f'<a href="#sec-{esc(x)}">{esc(next(s["title"] for s in ch["sections"] if s["id"] == x))}</a>' if x != "exercises" else '<a href="#exercises">课后练习</a>') for x in p["sections"]) + "</li>" for p in ch["points"]) + "</ul></details>")
    glossary = ""
    if ch.get("glossary"):
        glossary = '<details id="glossary" class="evidence"><summary>几个词的大白话</summary><ul>' + "".join(f'<li><b>{esc(w)}</b>：{esc(d)}</li>' for w, d in ch["glossary"]) + "</ul></details>"
    def model_names(r):      # one model, or (the bars record of lesson 2) the list of models it compares
        return esc(r["model"].split("/")[-1]) if r.get("model") else esc("、".join(m["model"].split("/")[-1] for m in r["models"]))
    rec_rows = "".join(f'<li><b>{esc(i)}</b>：{esc(ctx.records[i]["title"])}' + (f'　<span class="mono">{model_names(ctx.records[i])} · {esc(ctx.records[i]["date"])} · {esc(ctx.records[i]["mode"])} · {ctx.records[i]["n"]} 遍</span>' if ctx.records[i].get("n") else "") + "</li>"
                       for i in dict.fromkeys(ctx.used_records))
    used_claims = list(dict.fromkeys(ctx.used_claims))
    src_rows = "".join(f'<li><b>{esc(k)}</b>：{esc(ctx.claims[k]["statement"])} <span class="muted">适用范围：{esc(ctx.claims[k]["scope"])}</span></li>' for k in used_claims)
    mixed = any(ctx.records[i].get("kind") in ("cuts", "docs") for i in ctx.used_records)      # lesson 2: a local reproduction of two public cutting rules and quotes from archived pages are records too
    evidence_lead = ("这一章的“实测”里，模型调用的记录都是经模型网关调用的；切法示意是在本机用公开规则复现的；文档摘引取自存档页面（日期见各自的来源）。" if mixed else "这一章的“实测”都是经模型网关调用的记录，")
    evidence = ('<details id="evidence" class="evidence"><summary>证据抽屉：这一章的数字和说法从哪里来</summary>'
                f'<h4>实测记录（{len(set(ctx.used_records))} 条）</h4><ul>{rec_rows}</ul>'
                f"<p>{evidence_lead}录制日期是 {'、'.join(sorted({ctx.records[i]['date'] for i in ctx.used_records if ctx.records[i].get('date')}))}（每条记录上都标了）。模型名是网关标称名，无法独立验证；这是我们自己设计的小测试，不是评测；模型会更新，表现以录制那天为准。</p>"
                f'<h4>来源说（{len(used_claims)} 条）</h4><ul>{src_rows}</ul></details>')
    side = ""
    if vid:
        chap_btns = "".join(f'<button class="seek" type="button" data-seek="{c["start"]}" data-t="{mmss(c["start"])}">{esc(c["title"])}</button>' for c in vid["chapters"])
        side = (f'<aside class="side" aria-label="视频与本章目录"><video id="lesson-video" controls preload="metadata" playsinline poster="{esc(site_media[vid["poster"]])}" data-duration="{vid["duration"]:.2f}">'
                f'<source src="{esc(site_media[vid["file"]])}" type="video/mp4"><p>你的浏览器不能播放这个视频。</p></video>'
                f'<nav class="chapters" aria-label="视频章节"><h2>视频章节</h2>{chap_btns}</nav><p class="muted small">点正文里的小图或“▶ 看视频这一段”，视频会跳到那一刻。</p>'
                f'<nav class="toc-side" aria-label="本章目录"><h2>本章目录</h2><ol>{"".join(toc)}</ol></nav></aside>')
    else:
        side = f'<aside class="side" aria-label="本章目录"><nav class="toc-side"><h2>本章目录</h2><ol>{"".join(toc)}</ol></nav></aside>'
    take = "".join(f"<li>{esc(x)}</li>" for x in ch["takeaway"])
    exercises = exercises_html(ch["exercises"])
    closing = ch.get("closing", "")
    readings = ""
    if ch.get("readings"):
        readings = ('<details id="readings" class="evidence"><summary>延伸阅读（想多看一点的人）</summary><p class="muted small">这些是大纲里列的延伸资料，不是本章说法的证据。标“没通读”的，我们只确认过页面存在，请你先自己看一眼再决定读不读。</p><ul>' +
                    "".join(f'<li><a class="src-link" href="{esc(r["url"])}" target="_blank" rel="noopener noreferrer">{esc(r["title"])}</a>　<span class="muted">{esc(r["by"])} · {esc(r["level"])} · {esc(r["note"])}</span></li>' for r in ch["readings"]) + "</ul></details>")
    downloads = ""
    if ch.get("downloads"):
        downloads = ('<section class="blk" id="downloads"><h2>下载</h2><ul>' + "".join(f'<li><a href="../../downloads/{esc(Path(d["file"]).name)}" download>{esc(Path(d["file"]).name)}</a>　<span class="muted">{esc(d["what"])}</span></li>' for d in ch["downloads"]) + "</ul></section>")
    meta_line = f'对应岗位大纲 {esc(u["id"])}' + (f' · 视频 {mmss(vid["duration"])}（含 2 秒片头）· 视频自带字幕' if vid else "") + (f' · 时效：{esc(ch["timeliness"])}' if ch.get("timeliness") else "")
    body = f"""<div class="page" id="root" style="--bk:{BOOK_HUES[b['n'] - 1]}">
{topbar(2, [("书架", "../../index.html"), (f"第 {b['n']} 册 {b['title']}", "index.html"), (f"第 {u['no']} 章", None)])}
<header class="top">
  <div class="titles">
    <div class="eyebrow">第 {b['n']} 册 · 第 {u['no']} 章 · {esc(u['stage_title'])}</div>
    <h1{lat(u['title'])}>{esc(u['title'])}</h1>
    <p class="lesson-title">{esc(ch['lesson_title'])}</p>
    <p class="muted">{meta_line}</p>
    <div class="chips">{status_chips(u, ch)}</div>
    <div class="basic"><div class="k">基本问题</div>{esc(ch['basic_question'])}</div>
    <div class="pre-row"><span class="muted small">先学：</span>{prereq_html(u, units)}</div>
  </div>
  <div class="cast"><img src="../../assets/img/teacher.png" alt="老师，手里拿着白板笔"><img src="../../assets/img/robot.png" alt="AI 小搭档，一个会聊天的机器人，在挥手"></div>
</header>
<div class="takeaway"><h2>读完你会带走什么</h2><ul>{take}</ul></div>
<div class="layout">
{side}
<main class="main" data-unit="{esc(u['id'])}">
{''.join(secs)}
{exercises}
{downloads}
{('<section class="closing"><h2>留给下一课的问题</h2><p>' + closing + '</p></section>') if closing else ''}
{cov}
{readings}
{glossary}
{evidence}
{pager(b, u['id'], units, chapters)}
<footer class="foot muted small">旁白为 AI 合成语音；画面里的插画和角色姿势为 AI 生成；视频字幕时间为估计；音效来自 Pixabay（Pixabay Content License）。</footer>
</main>
</div>
</div>"""
    has_labs = any(blk.get("t") == "lab" for s in ch["sections"] for blk in s["blocks"])
    scripts = lab_script_tags(assets_root) + "\n" if has_labs else ""
    return page(f"{u['id']} {u['title']}", 2, body, scripts=scripts), ctx


# ------------------------------------------------------------------ assets
def avatar(name, h, out):
    img = Image.open(ROOT / "projects/_cast/agent" / name).convert("RGBA")
    img = img.resize((round(img.width * h / img.height), h), Image.LANCZOS)
    img.save(out, optimize=True)


def copy_media(ch, uid, link):
    """Copy (or link) a chapter's media into site/media/<unit>/ and return {source path: site path relative to the site root}."""
    out = {}
    base = SITE / "media" / uid
    base.mkdir(parents=True, exist_ok=True)
    items = []
    if ch.get("video"):
        items += [ch["video"]["file"], ch["video"]["poster"]]
    items += [f["src"] for f in ch.get("frames", [])]
    for src in items:
        s = ROOT / src
        assert s.is_file(), f"{uid}: media file missing: {src}"
        d = base / (f"frames/{s.name}" if src in [f["src"] for f in ch.get("frames", [])] else s.name)
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.exists() or d.is_symlink():
            d.unlink()
        if link and s.stat().st_size > 5e6:      # a hard link: no second copy of the video, and the file really lies inside the site folder (the server refuses symlinks that leave it)
            try:
                os.link(s, d)
            except OSError:
                shutil.copy2(s, d)
        else:
            shutil.copy2(s, d)
        out[src] = f"../../media/{uid}/{d.relative_to(base).as_posix()}"
    return out


def plain_text(html_text):
    t = re.sub(r"<(script|style|button)[^>]*>.*?</\1>", "", html_text, flags=re.S)       # buttons are interface, not reading text
    t = re.sub(r'<a class="watch"[^>]*>.*?</a>|<span class="at">.*?</span>', "", t, flags=re.S)       # "watch this part" links and the time on a frame
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", "", re.sub(r"▶[\d:]+", "", t)).strip()               # whitespace is dropped so a term split by an inline tag still matches (the search drops it from the term too)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--link-media", action="store_true", help="hard-link the big media files instead of copying them (same file system)")
    ap.add_argument("--export", help="after the build, replace this folder by a copy of the site (the offline copy that goes into the lesson's release pack)")
    a = ap.parse_args()
    outline, books, stages, units, chapters = load()
    lab_ids = collect_lab_ids(chapters)
    lab_config(books)
    if SITE.exists():
        shutil.rmtree(SITE)
    for d in ("assets/img", "assets/covers", "assets/fonts", "books", "media", "downloads"):
        (SITE / d).mkdir(parents=True)
    shutil.copy2(HERE / "book.css", SITE / "assets/book.css")
    shutil.copy2(HERE / "book.js", SITE / "assets/book.js")
    if lab_ids:
        copy_lab_assets(SITE, ROOT)
        write_lab_config(SITE, books)
    shutil.copy2(FONT, SITE / "assets/fonts/ZCOOLKuaiLe-Regular.ttf")
    (SITE / "assets/fonts/FONT-LICENSE.txt").write_text(
        "ZCOOLKuaiLe-Regular.ttf\nCopyright 2018 The ZCOOL KuaiLe Project Authors (https://github.com/googlefonts/zcool-kuaile)\n\n"
        "This Font Software is licensed under the SIL Open Font License, Version 1.1.\nThis license is available with a FAQ at: https://openfontlicense.org\n"
        "(The notice above is the one written inside the font file itself.)\n", encoding="utf-8")
    avatar("teacher_hold.png", 280, SITE / "assets/img/teacher.png")
    avatar("robot_wave.png", 280, SITE / "assets/img/robot.png")
    for b in books["books"]:
        cover_asset(b)
    (SITE / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    meta = books["series"]
    urls = archive_urls()
    index = []
    (SITE / "index.html").write_text(shelf_html(meta, books, units, chapters), encoding="utf-8")
    book_by_id = {b["id"]: b for b in books["books"]}
    for b in books["books"]:
        d = SITE / "books" / b["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(book_html(b, books, units, chapters, stages), encoding="utf-8")
        for uid in b["units"]:
            u = units[uid]
            if uid in chapters:
                ch = chapters[uid]
                records = json.loads((ROOT / ch["records"]).read_text(encoding="utf-8"))
                used = json.loads((ROOT / ch["claims_file"]).read_text(encoding="utf-8"))
                claims = {c["id"]: c for c in used["sourced"]}
                media = copy_media(ch, uid, a.link_media)
                html_text, ctx = chapter_html(u, b, books, units, chapters, stages, {"records": records, "claims": claims, "urls": urls}, media)
                for dl in ch.get("downloads", []):
                    shutil.copy2(ROOT / dl["file"], SITE / "downloads" / Path(dl["file"]).name)
                text = plain_text(re.search(r'<main class="main".*?</main>', html_text, re.S).group(0))
            else:
                html_text = placeholder_html(u, b, books, units, chapters, stages)
                text = ""
            (d / f"{uid}.html").write_text(html_text, encoding="utf-8")
            index.append({"id": uid, "t": u["title"], "p": u["plain"].get("plain_title", ""), "g": u["goal"], "b": b["id"], "bt": b["title"], "n": u["no"], "w": uid in chapters, "x": text[:40000]})
    blob = "window.SEARCH_INDEX = " + json.dumps(index, ensure_ascii=False, separators=(",", ":")) + ";\n"
    assert len(blob.encode("utf-8")) < 8e6, "the search index is over 8 MB and every page loads it: split it by book and load the book's part on demand"
    (SITE / "assets/search-index.js").write_text(blob, encoding="utf-8")
    pages = len(list((SITE / "books").rglob("*.html"))) + 1
    size = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file() and not f.is_symlink()) / 1e6
    if a.export:
        dst = Path(a.export).resolve()
        assert dst.parent.is_dir() and dst != SITE and "exports" in dst.parts, f"--export must name a folder under some lesson's exports/: {dst}"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(SITE, dst, copy_function=lambda s, d, **kw: (os.link(s, d) if Path(s).stat().st_size > 5e6 else shutil.copy2(s, d)))
        print(f"exported a copy to {dst.relative_to(ROOT)}")
    print(f"built {SITE.relative_to(ROOT)}: {len(books['books'])} books, {len(units)} chapter pages ({len(chapters)} with text), {pages} html files, {size:.1f} MB (links not counted)")


if __name__ == "__main__":
    main()
