"""Block renderers of the ebook platform: a chapter source is a list of sections, a section is a list of blocks, every block becomes static HTML (no script needed to read).
The visual language is the one of the first ebook chapter (warm board paper, ink, red titles, highlighter yellow, model-cyan bubbles); the classes are the ones book.css already styles.
Numbers come from the lesson's records.json (made from archived runs), sources from claims_used.json + the source archive manifest; a block that names a record or a claim that does not exist raises."""
import html
import json
import re

from labs import render_lab

esc = lambda s: html.escape(str(s), quote=True)


class Ctx:
    """What a chapter's blocks may refer to."""

    def __init__(self, records, claims, urls, assets_root="../../assets/"):
        self.records, self.claims, self.urls = records, claims, urls
        self.used_records, self.used_claims = [], []
        self.assets_root = assets_root


# ------------------------------------------------------------ measured records
def params_text(ep):
    """Extra request parameters as a reader sees them: the one we always set is said in words, anything else stays as it is."""
    if ep == {"thinking": {"type": "disabled"}}:
        return "关闭思考的开关已设好（接口参数 thinking 设为 disabled）"
    return json.dumps(ep, ensure_ascii=False)


def caliber(r):
    bits = [r["model"], r["date"], r["mode"], f"{r['n']} 遍"]
    ex = params_text(r["extra_params"]) if r.get("extra_params") else ""
    return (f"（{r['model_note']}）" if r.get("model_note") else "") + " · ".join(bits) + (f" · 额外参数 {ex}" if ex else " · 其余参数默认")


def towers(r):
    cols = "".join(f'<div class="tower"><span class="cnt">{g["count"]}</span>' + "<i></i>" * g["count"] + "</div>" for g in r["groups"])
    ans = "".join(f'<li><span class="c">×{g["count"]}</span><span>{esc(g["text"])}</span></li>' for g in r["groups"])
    label = esc(r["title"] + "：" + "、".join(str(g["count"]) for g in r["groups"]))
    return f'<div class="viz"><div class="towers" role="img" aria-label="{label}">{cols}</div><ol class="ans">{ans}</ol></div>'


def bub(kind, text, count=None, run=None):
    return (f'<div class="bub {kind}">{esc(text)}' + (f'<span class="chip">×{count}</span>' if count else "") + (f'<span class="run">第 {run} 遍起出现</span>' if run else "") + "</div>")


def chat(r):
    if r.get("sum"):        # a record that carries its own summary lines (and maybe a hand-written history), e.g. the "memory" pair
        hist = ""
        if r.get("history"):
            hist = '<div class="hist"><span class="stk">这一段历史是我们手写好、塞进去的</span>' + "".join(bub("u" if h["role"] == "user" else "m", h["text"]) for h in r["history"]) + "</div>"
        shown = "".join(bub("m", g["text"] if len(g["text"]) <= 90 else g["text"][:90] + "……（后面还有）", g["count"], g.get("first_seen_run") if len(r["groups"]) > 1 else None) for g in r["groups"][:3])
        lines = "".join(f'<span class="{esc(x["cls"])}">{esc(x["text"])}</span>' for x in r["sum"])
        more = f'<div class="muted">只摆出前 3 种回答，原样引用；其余 {len(r["groups"]) - 3} 种在记录里。</div>' if len(r["groups"]) > 3 else ""
        return f'<div class="chat">{hist}{bub("u", r["prompt"])}{shown}<div class="sum">{lines}</div>{more}</div>'
    if r.get("system_note"):
        g = r["groups"][0]
        return ('<div class="chat"><div class="sticky"><span class="stk">纸条（实际是放在问题前面的一条系统消息）</span>' + esc(r["system_note"]) + "</div>" + bub("u", r["prompt"]) +
                bub("m", g["text"], g["count"]) + f'<div class="sum"><span class="ok">✓ 答对：{r["correct"]} / {r["n"]} 遍</span></div></div>')
    yrs = "、".join(f"{y} 年" for y in (r.get("years") or {}))
    s = ""
    if r.get("gave_a_date"):
        s += f'<span class="bad">✗ 直接报了一个具体日期：{r["gave_a_date"]} 遍' + (f"（年份：{yrs}）" if yrs else "") + "</span>"
    if r.get("declined"):
        s += f'<span class="info">○ 说无法获取：{r["declined"]} 遍</span>'
    shown = "".join(bub("m", g["text"] if len(g["text"]) <= 90 else g["text"][:90] + "……（后面还有）", g["count"], g["first_seen_run"]) for g in r["groups"][:3])
    more = f'<div class="muted">只摆出出现次数最多的 3 种回答，原样引用；其余 {len(r["groups"]) - 3} 种在记录里。</div>' if len(r["groups"]) > 3 else ""
    return f'<div class="chat">{bub("u", r["prompt"])}{shown}<div class="sum">{s}</div>{more}</div>'


LABEL_CASE = {"H2_fake_book": "《深海蒲公英学导论》第三章", "H2b_fake_paper": "论文《校园共享雨伞的借还行为研究》", "H2c_fake_book2": "《春季蜜蜂行为入门》第三章"}


def labels(r):
    rows = "".join(f'<tr><td>{esc(LABEL_CASE.get(k, k))}</td><td class="{"bad" if c.get("fabricated") else ""}">{c.get("fabricated", 0)} 遍</td><td>{c.get("declined", 0)} 遍</td><td>{c.get("canned", 0)} 遍</td></tr>'
                   for k, c in r["counts"].items())
    return f'<div class="scroll"><table class="t"><tr><th>问法</th><th>编造</th><th>无法确认／说不存在</th><th>套话</th></tr>{rows}</table></div>'


MODE_TEXT = {"think_off": "关闭思考", "think_default": "默认（思考开）"}


def labels_all(r):
    """The 12 groups (2 models x 2 thinking settings x 3 questions, 10 answers each) in one table, with a total row."""
    rows = "".join(f'<tr><td>{esc(x["model"])}</td><td>{esc(MODE_TEXT[x["mode"]])}</td><td>{esc(LABEL_CASE.get(x["case"], x["case"]))}</td>'
                   f'<td class="{"bad" if x["counts"].get("fabricated") else ""}">{x["counts"].get("fabricated", 0)} 遍</td><td>{x["counts"].get("declined", 0)} 遍</td><td>{x["counts"].get("canned", 0)} 遍</td></tr>'
                   for x in r["rows"])
    t = r["totals"]
    total = (f'<tr><td colspan="3"><b>合计 {sum(t.values())} 个回答</b></td><td class="{"bad" if t.get("fabricated") else ""}"><b>{t.get("fabricated", 0)} 遍</b></td>'
             f'<td><b>{t.get("declined", 0)} 遍</b></td><td><b>{t.get("canned", 0)} 遍</b></td></tr>')
    return f'<div class="scroll"><table class="t"><tr><th>模型（网关标称名）</th><th>思考设置</th><th>问法</th><th>编造</th><th>无法确认／说不存在</th><th>套话</th></tr>{rows}{total}</table></div>'


def task(r):
    """A small real task: the prompt, one real answer (shown whole, folded when long) and how many runs there were.  Used for 'what it is good at' examples."""
    ans = r["answer"]
    long_ = len(ans) > 260
    body = f'<div class="bub m">{esc(ans)}</div>' if not long_ else f'<details class="bub-fold"><summary>展开这一次的完整回答（{len(ans)} 字）</summary><div class="bub m">{esc(ans)}</div></details>'
    checks = "".join(f'<span class="{esc(x["cls"])}">{esc(x["text"])}</span>' for x in r.get("check", []))
    note = f'<div class="muted">一次示例：同一个任务共 {r["n"]} 遍，这里摆出第 {r.get("shown_run", 1)} 遍；换一遍，措辞会不一样。</div>'
    return f'<div class="chat">{bub("u", r["prompt"])}{body}{note}' + (f'<div class="sum">{checks}</div>' if checks else "") + "</div>"


def usage(r):
    """A prompt bubble beside a small receipt of the three token measurements."""
    prompt_values = r["prompt_tokens"]
    completion_values = r["completion_tokens"]
    total_values = r["total_tokens"]

    def row(label, values, same=False):
        cells = "".join(f'<span class="usage-cell">{esc(value)}</span>' for value in values)
        marker = '<span class="usage-same">三遍相同</span>' if same else ""
        return f'<div class="usage-row"><span class="usage-label">{esc(label)}</span><span class="usage-values">{cells}</span>{marker}</div>'

    same_prompt = len(set(prompt_values)) == 1
    run_count = int(r.get("n", len(prompt_values)))
    columns = "".join(f'<span class="usage-run">第 {i} 遍</span>' for i in range(1, run_count + 1))
    ticket_label = (
        f'三行词元记录：prompt_tokens 为 {"、".join(map(str, prompt_values))}，'
        f'completion_tokens 为 {"、".join(map(str, completion_values))}，'
        f'total_tokens 为 {"、".join(map(str, total_values))}'
    )
    receipt = (
        '<div class="usage-ticket" role="img" aria-label="'
        + esc(ticket_label)
        + '">'
        + f'<div class="usage-colhead"><span>测量</span><span class="usage-values">{columns}</span></div>'
        + row("prompt_tokens", prompt_values, same_prompt)
        + row("completion_tokens", completion_values)
        + row("total_tokens", total_values)
        + f'<div class="usage-summary">发出的话共 {esc(r["chars"])} 个字符，输入词元数（中位数）{esc(r["median_prompt_tokens"])}</div>'
        + "</div>"
    )
    label = f'{r["title"]}：发出的话 {r["chars"]} 个字符，输入词元数中位数 {r["median_prompt_tokens"]}'
    return f'<div class="usage-viz" role="group" aria-label="{esc(label)}">{bub("u", r["prompt"])}{receipt}</div>'


def bars(r):
    """Compare the three 1000-character inputs on a single scale."""
    values = [m[k] for m in r["models"] for k in ("zh", "code", "en")]
    maximum = max(values) if values else 1
    names = (("zh", "中文"), ("code", "代码"), ("en", "英文"))
    groups = []
    for model in r["models"]:
        rows = sorted(((label, model[key]) for key, label in names), key=lambda item: item[1], reverse=True)
        bars_html = "".join(
            '<div class="measure-bar" role="img" aria-label="'
            + esc(f"{label} {value} 个词元")
            + '"><span class="measure-bar-label">'
            + esc(label)
            + '</span><div class="measure-bar-track"><div class="measure-bar-fill" style="width:'
            + f"{value / maximum * 100:.1f}%"
            + '">'
            + f'<span class="measure-bar-number">{esc(value)}</span></div></div></div>'
            for label, value in rows
        )
        model_text = str(model["model"])
        short_model = model_text.rsplit("/", 1)[-1] if "<" not in model_text else model_text
        model_class = "measure-model" + (" latin" if lat(short_model) else "")
        groups.append(
            f'<div class="measure-group"><h4 class="{model_class}">{esc(short_model)}</h4>{bars_html}'
            f'<div class="measure-note">固定开销 {esc(model["wrapper"])} 个；中文扣掉后 {esc(model["net_zh"])} 个</div></div>'
        )
    return f'<div class="measure-bars">{"".join(groups)}</div>'


def cuts(r):
    rows = []
    for row in r["rows"]:
        pieces = []
        for piece in row["pieces"]:
            if piece == "▯":
                pieces.append('<span class="cut-chip cut-incomplete" title="不完整的字节块" aria-label="不完整的字节块">▯</span>')
            else:
                pieces.append(f'<span class="cut-chip">{esc(piece)}</span>')
        rows.append(
            f'<div class="cut-row"><div class="cut-rule">{esc(row["name"])}</div>'
            f'<div class="cut-pieces">{"".join(pieces)}</div><span class="cut-count">共 {esc(len(row["pieces"]))} 块</span>'
            f'<div class="cut-note">{esc(row["note"])}</div></div>'
        )
    return f'<div class="cuts-viz"><div class="cuts-original">原句：{esc(r["text"])}</div>{"".join(rows)}</div>'


def docs(r):
    cards = []
    for card in r["cards"]:
        url = str(card["url"])
        visible_url = re.sub(r"^https?://", "", url)
        cards.append(
            f'<article class="docs-card"><h4 class="docs-who">{esc(card["who"])}</h4>'
            f'<blockquote>“{esc(card["quote"])}”</blockquote>'
            f'<p class="docs-says">一句话：{esc(card["says"])}</p>'
            f'<a class="docs-link src-link" href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(visible_url)}</a>'
            f'<span class="docs-archive">存档 {esc(card["archive"])}</span></article>'
        )
    return f'<div class="docs-cards">{"".join(cards)}</div>'


def show(b, ctx):
    r = ctx.records[b["id"]]
    ctx.used_records.append(b["id"])
    head = f'<div class="fh">{esc(r["title"])}</div>'
    if r["kind"] == "towers":
        body, cap = towers(r), caliber(r)
    elif r["kind"] == "chat":
        body, cap = chat(r), caliber(r)
    elif r["kind"] == "task":
        body, cap = task(r), caliber(r)
    elif r["kind"] == "labels":
        main = ctx.records["H1_open_ds"]
        body, cap = labels(r), f"主模型 {main['model']} · {main['date']} · 关闭思考 · 逐条标注（AI 模型标注，没有真人） · 每个问法 10 遍"
    elif r["kind"] == "labels_all":
        body, cap = labels_all(r), f"模型名都是{r['model_note']} · {r['date']} · 每个问法 10 遍 · 标注人：{r['labelers']}"
    elif r["kind"] == "stat":
        body = (f'<p>同一句“{esc(r["prompt"])}”：关闭思考时，送进模型的内容长度是 {"、".join(map(str, r["think_off_prompt_tokens"]))}，默认思考时是 {"、".join(map(str, r["think_default_prompt_tokens"]))}'
                "（单位叫“词元”，不一定正好是一个字，这一章先不展开）。</p>")
        cap = (f"（{r['model_note']}）" if r.get("model_note") else "") + f"{r['model']} · {r['date']} · 关闭思考和默认思考各 {r['n']} 遍" + (f" · 额外参数（关闭思考时） {params_text(r['extra_params'])}" if r.get("extra_params") else "")
    elif r["kind"] == "usage":
        body, cap = usage(r), caliber(r)
    elif r["kind"] == "bars":
        body, cap = bars(r), f"{r['model_note']} · {r['date']} · {r['mode']} · 每个用例 {r['n']} 遍；每段文字恰好 1000 个字符"
    elif r["kind"] == "cuts":
        body, cap = cuts(r), f"{r['date']} 在本机用两套公开的切字规则复现，只是示意，不代表你正在用的模型"
    elif r["kind"] == "docs":
        dates = "、".join(f"{c['archive']} {ctx.urls.get(c['archive'], {}).get('date') or r['date']}" for c in r["cards"])        # each page has its own archive/fetch date
        body, cap = docs(r), f"取页日期：{dates} · 三页是各自场景里大致的参考，说法互不相同，这里不判谁对"
    else:
        raise AssertionError(r["kind"])
    after = f'<p class="after">{esc(b["after"])}</p>' if b.get("after") else ""
    return f'<figure class="show" data-record="{esc(b["id"])}">{head}{body}<figcaption class="rec"><span class="tag tag-shice">实测</span> {esc(cap)}</figcaption>{after}</figure>'


# ------------------------------------------------------------ sources, metaphors, questions
def fact(b, ctx):
    c = ctx.claims[b["id"]]
    ctx.used_claims.append(b["id"])
    links = []
    dates = {ctx.urls[a]["date"] for a in c["archive"]}
    for a in c["archive"]:
        u = ctx.urls[a]["url"]
        links.append(f'<a class="src-link" href="{esc(u)}" target="_blank" rel="noopener noreferrer">{esc(re.sub(r"^https?://", "", u))}</a>' + (f'（{esc(ctx.urls[a]["date"])}）' if len(dates) > 1 else ""))
    lead = f'原页（{esc(ctx.urls[c["archive"][0]]["date"])} 存档）：' if len(dates) == 1 else "原页（各页存档日期写在链接后面）："
    return (f'<aside class="fact" data-claim="{esc(b["id"])}"><span class="tag tag-source">来源说</span> <span class="src">{esc(b["src"])}</span><p>{esc(c["statement"])}</p>'
            f'<p class="scope">适用范围：{esc(c["scope"])}</p><p class="srcline">{lead}{"　".join(links)}</p></aside>')


def term(b, ctx=None):
    return (f'<div class="term"><div class="head"><span class="tag tag-metaphor">比喻</span><b class="word">{esc(b["word"])}</b></div>'
            f'<div class="row"><div class="k">一句话</div><div class="v">{esc(b["plain"])}</div></div>'
            f'<div class="row"><div class="k">类比</div><div class="v">{esc(b["analogy"])}</div></div>'
            f'<div class="row gap"><div class="k">哪里不像</div><div class="v"><p class="gap">哪里不像：{esc(b["gap"])}</p></div></div></div>')


def render_block(b, ctx):
    t = b["t"]
    if t == "lab":
        return render_lab(b, ctx.assets_root)
    if t == "p":
        return f'<p>{esc(b["x"])}</p>'
    if t == "h3":
        return f'<h3 class="sub">{esc(b["x"])}</h3>'
    if t == "story":
        return '<div class="story"><div class="label">故事</div>' + "".join(f"<p>{esc(x)}</p>" for x in b["x"]) + "</div>"
    if t == "ul":
        return "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in (b.get("items") or b["x"])) + "</ul>"
    if t == "ol":
        return "<ol class='steps'>" + "".join(f"<li>{esc(x)}</li>" for x in (b.get("items") or b["x"])) + "</ol>"
    if t == "callout":      # kind: tip | warn | info
        return f'<aside class="callout {esc(b.get("kind", "info"))}"><b>{esc(b.get("title", ""))}</b><p>{esc(b["x"])}</p></aside>'
    if t == "table":
        head = "".join(f"<th>{esc(h)}</th>" for h in b["head"])
        rows = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in b["rows"])
        cap = f'<p class="muted small">{esc(b["caption"])}</p>' if b.get("caption") else ""
        return f'<div class="scroll"><table class="t"><tr>{head}</tr>{rows}</table></div>{cap}'
    if t == "code":
        return f'<pre class="code" data-lang="{esc(b.get("lang", ""))}"><code>{esc(b["x"])}</code></pre>'
    if t == "show":
        return show(b, ctx)
    if t == "fact":
        return fact(b, ctx)
    if t == "term":
        return term(b, ctx)
    if t == "think":
        return f'<details class="think"><summary>想一想：{esc(b["q"])}</summary><p>{esc(b["a"])}</p></details>'
    if t == "assembly":      # the assembly diagram of the lesson: six slots, the filled ones in model colour; slots: [{"label","on","note"}]
        cells = "".join(f'<div class="slot{" on" if s.get("on") else ""}"><b>{esc(s["label"])}</b><span>{esc(s.get("note", ""))}</span></div>' for s in b["slots"])
        cap = f'<figcaption class="muted small">{esc(b["caption"])}</figcaption>' if b.get("caption") else ""
        return f'<figure class="assembly-fig"><div class="assembly" role="img" aria-label="{esc(b.get("alt", "装配图示意"))}">{cells}</div>{cap}</figure>'
    if t == "link":         # a pointer to another chapter or an outside page: {"x": text, "unit": "S4-U01"} or {"x":..., "href": "https://..."}
        return f'<p class="pointer">→ {esc(b["x"])}</p>' if not b.get("unit") else f'<p class="pointer" data-unit="{esc(b["unit"])}">→ {esc(b["x"])}</p>'
    raise AssertionError(f"unknown block type {t!r}")


def inline(text):
    """escape, then turn `code` into <code> (the outline text uses backticks for file and field names)"""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(text))


def lat(text):
    """class attribute for a heading: the hand-writing font has no Latin letters or digits, so a heading that has some is set in the body font"""
    return ' class="latin"' if re.search(r"[A-Za-z0-9]", text) else ""


def sentence_plain(s):
    return "".join(c for c in s if c not in "，。？！：；、,.?!:;…“”‘’（）()" and not c.isspace())
