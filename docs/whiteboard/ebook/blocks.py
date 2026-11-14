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


# ------------------------------------------------------------ lesson 3 kinds: a table the service returned for one request, ten answers per row, official quotes, one strange answer, ten long answers, a request with its stop reason, a made-up sketch
ROW_COLORS = ["#FFF3A8", "#CDEBFA", "#FAD3D9", "#D4F0D2", "#E3CA9B", "#E6D5F7", "#E2EDB0", "#BFEBDD", "#D9DEE5", "#F1C0E8"]    # ten pale hues, none of them orange (orange only means "the token this return actually chose")


def _pct(p):
    return "<0.1%" if p < 0.05 else f"{p:.1f}%"


def ptable(r):
    """Top-5 bars of ONE returned table, 100 % = 200 px; the rest as an empty dashed bar; orange only on `chosen`; the stop token is pink and labelled 停止符."""
    cols = []
    for b in r["bars"]:
        h = max(3.0, b["pct"] * 2.0)
        cls = "pbar" + (" stop" if b.get("stop") else "") + (" pick" if r.get("chosen") and b["token"] == r["chosen"] else "")
        cols.append(f'<div class="pcol" role="img" aria-label="{esc(b["token"] + " " + _pct(b["pct"]))}"><span class="pnum">{esc(_pct(b["pct"]))}</span><div class="{cls}" style="height:{h:.1f}px"></div><span class="ptok">{esc(b["token"])}</span></div>')
    if r.get("rest_pct"):
        h = max(24.0, r["rest_pct"] * 2.0)
        cols.append(f'<div class="pcol" role="img" aria-label="{esc("其余合计 " + _pct(r["rest_pct"]))}"><span class="pnum rest">{esc(_pct(r["rest_pct"]))}</span><div class="pbar restbar" style="height:{h:.1f}px"></div><span class="ptok rest">其余合计</span></div>')
    chosen = f'<p class="pnote"><span class="swatch pick"></span>{esc(r["chosen_note"])}（橙色只表示这一次实际选中的词元）</p>' if r.get("chosen") and r.get("chosen_note") else ""
    head = f'<p class="pq">问：{esc(r["prompt"])}　<span class="muted small">温度 {esc(r["temperature"])} · {esc(r["label"])}</span></p>'
    return f'<div class="ptable">{head}<div class="pbars">{"".join(cols)}</div>{chosen}<p class="pnote muted">{esc(r["note"])}</p></div>'


def rows(r):
    out = []
    for row in r["rows"]:
        cells = "".join(f'<i class="cell" style="background:{ROW_COLORS[c]}"></i>' for c in row["colors"])
        out.append(f'<div class="crow" role="img" aria-label="{esc(row["label"] + "：十遍，" + str(row["versions"]) + " 种不同的文字")}"><span class="clabel">{esc(row["label"])}</span> <span class="cells">{cells}</span> <span class="cnt2">共 {esc(row["versions"])} 种</span></div>')
    return f'<div class="rowsfig"><p class="pq">问：{esc(r["prompt"])}</p>{"".join(out)}<p class="pnote muted">{esc(r["note"])}</p></div>'


def quotes(r):
    cards = []
    for c in r["cards"]:
        when = f'存档 {esc(c["archive"])}（{esc(c["archive_date"])} 存档，{esc(c.get("date", r["date"]))} 重取原页核对）' if c.get("archive_date") else f'存档 {esc(c["archive"])} · 取页 {esc(c.get("date", r["date"]))}'
        foot = f'<p class="qfoot">{esc(c["footnote"])}</p>' if c.get("footnote") else ""
        cards.append(f'<div class="qcard"><b class="qwho">{esc(c["who"])}</b><p class="qen" lang="en">{esc(c["english"])}</p><p class="qzh">{esc(c["zh"])}</p>{foot}<span class="qid">{when}</span></div>')
    return f'<div class="qcards">{"".join(cards)}</div><p class="pnote muted">{esc(r["note"])}</p>'


def excerpt(r):
    latin = " ".join(r["latin_words"])
    return (f'<div class="exc"><p class="pq">问：{esc(r["prompt"])}　<span class="muted small">温度 {esc(r["temperature"])}</span></p>'
            f'<p class="exc-head">{esc(r["normal_head"])}</p><p class="exc-latin" lang="en">{esc(latin)}</p><p class="exc-wave" aria-hidden="true">……</p>'
            f'<p class="pnote muted">{esc(r["note"])}</p></div>')


def lines_fig(r):
    pre = r["common_prefix"]
    rows_html = "".join(f'<li style="background:{ROW_COLORS[i % 10]}"><mark>{esc(h[:len(pre)])}</mark>{esc(h[len(pre):])}</li>' for i, h in enumerate(r["heads"]))
    return f'<div class="linesfig"><p class="pq">问：{esc(r["prompt"])}　<span class="muted small">温度 {esc(r["temperature"])}</span></p><ol class="heads">{rows_html}</ol><p class="pnote muted">{esc(r["note"])}</p></div>'


def finish_fig(r):
    body = r.get("content") or (r["content_head"] + "……（后面还有）")
    reason = f'<span class="fr">finish_reason: {esc(r["finish_reason"])}</span>'
    return (f'<div class="finish"><p class="pq">问：{esc(r["prompt"])}</p><pre class="req">max_tokens: {esc(r["max_tokens"])}\ntemperature: {esc(r["temperature"])}</pre>'
            f'<p class="ret">{esc(body)}</p><pre class="req">completion_tokens: {esc(r["completion_tokens"])}\n{reason}</pre><p class="pnote muted">{esc(r["note"])}</p></div>')


def sketch(r):
    names = r["names"]
    panels = []
    for t, v in r["by_temperature"].items():
        cols = "".join(f'<div class="pcol" role="img" aria-label="{esc(n)}"><div class="pbar sk" style="height:{max(3.0, p * 160):.1f}px"></div><span class="ptok">{esc(n)}</span></div>' for n, p in zip(names, v["p"]))
        panels.append(f'<div class="skp"><span class="sk-t">温度 {esc(t)}</span><div class="pbars small">{cols}</div></div>')
    return f'<div class="sketch"><div class="skrow">{"".join(panels)}</div><p class="pnote muted">{esc(r["note"])}</p></div>'



def _cal3(r):
    bits = [r["model"], r["date"], r["mode"]]
    return "（网关标称名，转发身份无法独立验证）" + " · ".join(bits)


TAG_SHICE = '<span class="tag tag-shice">实测</span>'
LESSON3_KINDS = {      # kind -> function(record, ctx) -> (body html, caption, tag html)
    "ptable": lambda r, c: (ptable(r), _cal3(r) + f" · 温度 {r['temperature']} · {r['label']}", TAG_SHICE),
    "rows": lambda r, c: (rows(r), _cal3(r) + f" · 每行 {r['n']} 遍", TAG_SHICE),
    "quotes": lambda r, c: (quotes(r), f"{r['date']} 重取原页核对 · 三页说法各自成立，这里不判谁对", '<span class="tag tag-source">引文</span>'),
    "excerpt": lambda r, c: (excerpt(r), _cal3(r) + f" · 温度 {r['temperature']} · 某一次的返回（节选）", TAG_SHICE),
    "lines": lambda r, c: (lines_fig(r), _cal3(r) + f" · 温度 {r['temperature']} · 共 {r['n']} 遍，各取开头", TAG_SHICE),
    "finish": lambda r, c: (finish_fig(r), _cal3(r) + f" · 温度 {r['temperature']} · 某一次的返回（同样的请求发了 {r['n']} 遍，这是其中一遍）", TAG_SHICE),
    "sketch": lambda r, c: (sketch(r), r["label"], '<span class="tag tag-shiyi">示意</span>'),
}


# ------------------------------------------------------------ lesson 4 kinds: message stacks, ten-answer grids, quotations, token bars, and a probe
L4_GRID_CLASSES = {
    "correct": "correct",
    "admit": "admit",
    "fabricated": "fabricated",
    "other": "other",
    "suffix": "suffix",
    "none": "none",
}


def _l4_model_names(r):
    models = r.get("models")
    if isinstance(models, dict):
        return [str(v) for v in models.values()]
    names = []
    for item in (r.get("items") or []):
        if item.get("model") and item["model"] not in names:
            names.append(str(item["model"]))
    return names


def _l4_caliber(r):
    models = _l4_model_names(r)
    model_part = f"模型名：{'、'.join(str(x) for x in models)} · " if models else ""
    date = str(r.get("date", ""))
    setting = str(r.get("setting") or "关闭思考 · 没设温度（默认值不知道）· 每格问十遍")
    return f"{model_part}（网关标称名，转发身份无法独立验证） · {date} · {setting}"


def stack(r):
    papers = []
    role_classes = {"user": "user", "assistant": "assistant", "system": "system"}
    role_fallback = {"user": "用户", "assistant": "助手", "system": "系统"}
    for note in (r.get("notes") or []):
        role = str(note.get("role", ""))
        role_class = role_classes.get(role, "other")
        role_text = note.get("role_cn") or role_fallback.get(role, role)
        # The stamp describes how the request was assembled.  It belongs on assistant papers only.
        stamped = note["stamp"] if "stamp" in note else role == "assistant"          # the record says whether the paper was written beforehand; without the field only assistant papers are
        stamp = '<span class="l4-stamp">事先写好</span>' if stamped else ""
        papers.append(
            f'<div class="l4-paper l4-paper-{role_class}">'
            f'<div class="l4-paper-head"><span class="l4-role">{esc(role_text)}</span>{stamp}</div>'
            f'<div class="l4-paper-text">{esc(note.get("text", ""))}</div></div>'
        )
    note_text = f'<p class="l4-note">{esc(r["note"])}</p>' if r.get("note") else ""
    return (
        f'<div class="l4-stack"><div class="l4-caller">{esc(r.get("caller_label", "调用的人这一侧的纸条摞"))}</div>'
        f'<div class="l4-papers">{"".join(papers)}</div>{note_text}</div>'
    )


def _l4_grid_labeler(r):
    # Keep the distinction visible without copying a source phrase that says “真人标注”.
    # A record may state who judged it (lesson 8: the program judges by rules); older records leave it out and render as before.
    if r.get("judged_by"):
        return str(r["judged_by"])
    if any(cell.get("class") in ("suffix", "none") for row in (r.get("rows") or []) for cell in (row.get("cells") or [])):
        return "程序判"
    return "两个 AI 模型分别标注，不是真人"


def grids(r):
    legend = []
    for item in (r.get("legend") or []):
        cls = L4_GRID_CLASSES.get(item.get("class"), "other")
        legend.append(
            f'<span class="l4-legend-item"><i class="l4-legend-swatch l4-grid-{cls}"></i>{esc(item.get("text", ""))}</span>'
        )
    model_lines = []
    for label, model in (r.get("models") or {}).items():
        model_lines.append(f'<span class="l4-model-line"><b>{esc(label)}</b>：{esc(model)}</span>')
    rows_html = []
    for row in (r.get("rows") or []):
        cells = []
        for cell in (row.get("cells") or []):
            cls = L4_GRID_CLASSES.get(cell.get("class"), "other")
            dot = '<i class="l4-grid-dot" aria-hidden="true"></i>' if cell.get("dot") is True else ""
            cells.append(f'<i class="l4-grid-cell l4-grid-{cls}">{dot}</i>')
        tally = row.get("tally") or {}
        n = tally.get("n", sum(1 for cell in (row.get("cells") or []) if cell.get("class") == tally.get("class")))
        total = tally.get("total", len((row.get("cells") or [])))
        short = tally.get("short", tally.get("class", ""))
        tally_cls = L4_GRID_CLASSES.get(tally.get("class"), "other")
        rows_html.append(
            f'<div class="l4-grid-row"><div class="l4-grid-label">{esc(row.get("label", ""))} · {esc(row.get("model", ""))}</div>'
            f'<div class="l4-grid-cells">{"".join(cells)}</div>'
            f'<div class="l4-grid-tally"><i class="l4-legend-swatch l4-grid-{tally_cls}"></i>{esc(short)} {esc(n)} / {esc(total)}</div></div>'
        )
    dot_legend = f'<p class="l4-dot-legend">{esc(r["dot_legend"])}</p>' if r.get("dot_legend") else ""
    return (
        f'<div class="l4-grid-figure"><div class="l4-grid-meta"><div class="l4-legend">{"".join(legend)}</div>'
        f'<div class="l4-labeler">标注：{esc(_l4_grid_labeler(r))}</div><div class="l4-models">{"".join(model_lines)}</div>'
        f'<div class="l4-setting">{esc(r.get("setting", ""))} · {esc(r.get("date", ""))}</div>{dot_legend}</div>'
        f'<div class="l4-grid-rows">{"".join(rows_html)}</div><p class="l4-note">{esc(r.get("note", ""))}</p></div>'
    )


def answers(r):
    items = []
    for item in (r.get("items") or []):
        items.append(
            f'<article class="l4-answer"><blockquote>“{esc(item.get("text", ""))}”</blockquote>'
            f'<div class="l4-answer-meta"><span>{esc(item.get("model", ""))}</span> · '
            f'<span>{esc(item.get("cell", ""))}</span> · <code>{esc(item.get("file", ""))}</code></div></article>'
        )
    return f'<div class="l4-answers">{"".join(items)}</div><p class="l4-note">{esc(r.get("note", ""))}</p>'


def tokenbars(r):
    model_items = list((r.get("models") or {}).items())
    value_keys = ["ds", "qw"]
    legend = []
    for index, (label, model) in enumerate(model_items):
        color = "first" if index == 0 else "second"
        legend.append(f'<span class="l4-token-legend"><i class="l4-token-swatch l4-token-{color}"></i>{esc(label)}：{esc(model)}</span>')
    rows_html = []
    # bar length is proportional to the number of tokens at every screen width: the longest bar of the figure fills the track, every other bar is value / longest of it (a fixed pixel width would be cut short on a narrow screen and spoil the proportions)
    longest = max([row.get(key, 0) for row in (r.get("rows") or []) for key in value_keys[:len(model_items)]] or [1]) or 1
    for row in (r.get("rows") or []):
        bars_html = []
        for index, key in enumerate(value_keys[:len(model_items)]):
            value = row.get(key, 0)
            color = "first" if index == 0 else "second"
            width = f"{value / longest * 100:.1f}%"
            bars_html.append(
                f'<div class="l4-token-line"><span class="l4-token-name">{esc(model_items[index][0])}</span>'
                f'<div class="l4-token-track"><i class="l4-token-fill l4-token-{color}" style="width:{esc(width)}" aria-label="{esc(str(value) + " 个输入词元")}"></i></div>'
                f'<span class="l4-token-value">{esc(value)}</span></div>'
            )
        rows_html.append(f'<div class="l4-token-row"><b>{esc(row.get("label", ""))}</b>{"".join(bars_html)}</div>')
    return (
        f'<div class="l4-tokenbars"><div class="l4-token-legend">{"".join(legend)}</div>'
        f'<div class="l4-token-rows">{"".join(rows_html)}</div><p class="l4-note">{esc(r.get("note", ""))}</p></div>'
    )


def _has_cjk(text):
    return bool(re.search(r"[\u3400-\u9fff]", str(text)))


def cards(r):
    cards_html = []
    for card in (r.get("cards") or []):
        quote = card.get("quote", "")
        lang = ' lang="en"' if not _has_cjk(quote) else ""
        gloss = ""
        if card.get("gloss"):
            gloss = f'<p class="l4-gloss">{esc(card.get("gloss_kind", "大意"))}：{esc(card["gloss"])}</p>'
        ours = ""
        if card.get("ours"):
            ours = f'<p class="l4-ours">我们的说明（不是页面原话）：{esc(card["ours"])}</p>'
        if card.get("recheck_date"):
            archive_line = f'存档 {esc(card.get("archive", ""))}（{esc(card.get("archive_date", ""))} 存档，{esc(card["recheck_date"])} 重取原页核对）'
        else:
            archive_line = f'存档 {esc(card.get("archive", ""))} · 取页 {esc(r.get("date", ""))}'
        cards_html.append(
            f'<article class="l4-source-card"><h4>{esc(card.get("who", ""))}</h4><p class="l4-iface">接口：{esc(card.get("iface", ""))}</p>'
            f'<blockquote class="l4-quote"{lang}>“{esc(quote)}”</blockquote>{gloss}{ours}'
            f'<p class="l4-archive">{archive_line}</p></article>'
        )
    return f'<div class="l4-source-cards">{"".join(cards_html)}</div><p class="l4-note">{esc(r.get("note", ""))}</p>'


def probe(r):
    calls = int(r.get("calls") or 0)         # a record with "calls": null draws no call rows instead of crashing the build
    call_rows = "".join(
        f'<div class="l4-probe-call"><code>{esc(r.get("request", ""))}</code><span>status {esc(r.get("status", ""))}</span><span>message: {esc(r.get("message", ""))}</span></div>'
        for _ in range(calls)
    )
    return f'<div class="l4-probe"><div class="l4-probe-request">请求：{esc(r.get("request", ""))}</div>{call_rows}<p class="l4-note">{esc(r.get("note", ""))}</p></div>'


LESSON4_KINDS = {      # kind -> function(record, ctx) -> (body html, caption, tag html)
    "stack": lambda r, c: (stack(r), f"{r.get('date', '')} · 关闭思考 · 没设温度（默认值不知道） · 纸条在调用的人一侧", TAG_SHICE),
    "grids": lambda r, c: (grids(r), _l4_caliber(r), TAG_SHICE),
    "answers": lambda r, c: (answers(r), _l4_caliber(r) + " · 原话摘引", TAG_SHICE),
    "tokenbars": lambda r, c: (tokenbars(r), _l4_caliber(r), TAG_SHICE),
    "cards": lambda r, c: (cards(r), f"取页日期：{r.get('date', '')} · 每张卡只对名下的接口成立", '<span class="tag tag-source">引文</span>'),
    "probe": lambda r, c: (probe(r), f"{r.get('date', '')} · 单独一次探测，没有控制思考，不是正式实验", TAG_SHICE),
}


# ------------------------------------------------------------ lesson 5 kinds: code/result panels and sequence diagrams
CP_ROLE_LABELS = {
    "key": "密钥",
    "address": "地址",
    "model": "模型名",
    "messages": "消息",
    "format": "输出格式",
}
CP_FIELD_ROLES = {"answer", "receipt", "stop", "error"}
CP_FIELD_LABELS = {"answer": "答案", "receipt": "回执", "stop": "停止", "error": "错误"}
SEQ_SOURCE_LABELS = {
    "shice": "实测",
    "shiyi": "示意",
    "doc": "文档写的，不是我们测的",
    "hypo": "假设",
}


def _cp_marked_code(code, marks):
    """Escape a request code block while marking each requested raw substring once."""
    raw = str(code)
    intervals = []
    for mark in marks or []:
        if not isinstance(mark, dict):
            raise ValueError("callpanel marks must be objects")
        text = str(mark.get("text", ""))
        role = str(mark.get("role", ""))
        if not text:
            raise ValueError("callpanel mark text must not be empty")
        occurrences = sum(raw.startswith(text, index) for index in range(max(0, len(raw) - len(text) + 1)))
        if occurrences != 1:
            raise ValueError(f"callpanel mark {text!r} must occur exactly once in code")
        if role not in CP_ROLE_LABELS:
            raise ValueError(f"unknown callpanel mark role: {role!r}")
        start = raw.index(text)
        intervals.append((start, start + len(text), role))
    intervals.sort()
    for previous, current in zip(intervals, intervals[1:]):
        if current[0] < previous[1]:
            raise ValueError("callpanel marks must not overlap")
    chunks = []
    pos = 0
    for start, end, role in intervals:
        chunks.append(esc(raw[pos:start]))
        chunks.append(f'<mark class="cp-mark cp-{role}">{esc(raw[start:end])}</mark>')
        pos = end
    chunks.append(esc(raw[pos:]))
    return "".join(chunks)


def callpanel(r):
    request = r.get("request") or {}
    result = r.get("result") or {}
    lang = str(request.get("lang", ""))
    lang_slug = re.sub(r"[^A-Za-z0-9_-]+", "-", lang).strip("-") or "text"
    code = _cp_marked_code(request.get("code", ""), request.get("marks") or [])
    legend = "".join(
        f'<span class="cp-legend-item cp-{role}"><i aria-hidden="true"></i>{esc(CP_ROLE_LABELS[role])}</span>'
        for role in dict.fromkeys(str(mark.get("role", "")) for mark in (request.get("marks") or []))
        if role in CP_ROLE_LABELS
    )
    fields = []
    for field in result.get("fields") or []:
        role = field.get("role")
        role_class = f" cp-{role}" if role in CP_FIELD_ROLES else ""
        role_label = f' <span class="cp-field-kind" aria-hidden="true">{esc(CP_FIELD_LABELS[role])}</span>' if role in CP_FIELD_LABELS else ""
        fields.append(
            f'<div class="cp-field{role_class}"><dt>{esc(field.get("name", ""))}{role_label}</dt>'
            f'<dd>{esc(field.get("value", ""))}</dd></div>'
        )
    status = "" if result.get("status") is None else f'<p class="cp-status">状态码：{esc(result.get("status"))}</p>'
    return (
        '<div class="cp-panel"><div class="cp-columns">'
        f'<section class="cp-request"><h4>{esc(request.get("label", "请求"))}</h4>'
        f'<pre class="cp-code cp-lang-{esc(lang_slug)}" aria-label="代码（语言：{esc(lang)}）"><code>{code}</code></pre>'
        f'<div class="cp-legend" aria-label="代码标记图例">{legend}</div></section>'
        f'<section class="cp-result"><h4>{esc(result.get("label", "结果"))}</h4>'
        f'<dl class="cp-fields">{"".join(fields)}</dl>{status}</section>'
        f'</div><p class="cp-note">{esc(r.get("note", ""))}</p></div>'
    )


def _seq_sentence(lanes, step):
    source = SEQ_SOURCE_LABELS.get(step.get("source"), str(step.get("source", "")))
    from_index, to_index = int(step.get("from", 0)), int(step.get("to", 0))
    from_name = str(lanes[from_index]) if 0 <= from_index < len(lanes) else str(from_index)
    to_name = str(lanes[to_index]) if 0 <= to_index < len(lanes) else str(to_index)
    detail = str(step.get("detail")) if step.get("detail") is not None else ""
    pieces = [f"{from_name} 到 {to_name}：{step.get('label', '')}", source]
    if detail:
        pieces.append(detail)
    if step.get("blocked"):
        pieces.append("被拦住")
    return "；".join(str(x) for x in pieces) + "。"


def sequence(r):
    lanes = [str(x) for x in (r.get("lanes") or [])]
    if len(lanes) != 2:
        raise ValueError("sequence requires exactly two lanes")
    visual_steps = []
    text_steps = []
    for number, step in enumerate(r.get("steps") or [], 1):
        source = str(step.get("source", ""))
        if source not in SEQ_SOURCE_LABELS:
            raise ValueError(f"unknown sequence step source: {source!r}")
        from_index, to_index = int(step.get("from", 0)), int(step.get("to", 0))
        if from_index not in (0, 1) or to_index not in (0, 1):
            raise ValueError("sequence step endpoints must be 0 or 1")
        direction = "right" if from_index == 0 and to_index == 1 else "left" if from_index == 1 and to_index == 0 else "same"
        classes = f"seq-step seq-step-{source} seq-from-{from_index} seq-to-{to_index} seq-{source} seq-{direction}"
        if step.get("blocked"):
            classes += " seq-blocked"
        badge = f'<span class="seq-badge seq-source-{source} seq-badge-{source}">{esc(SEQ_SOURCE_LABELS[source])}</span>'
        cross = '<span class="seq-cross" aria-hidden="true">×</span>' if step.get("blocked") else ""
        blocked_text = '<span class="seq-blocked-text">被拦住</span>' if step.get("blocked") else ""
        detail = f'<span class="seq-detail">{esc(step.get("detail"))}</span>' if step.get("detail") is not None else ""
        arrow = {"right": "→", "left": "←", "same": "↻"}[direction]
        # the two end cells always sit in lane order (left = lane 0, right = lane 1), like the lane heads above; the arrow shows the direction (a step that stays in one lane has no arrow, only the lane lit)
        left_on = " seq-end-on" if 0 in (from_index, to_index) else ""
        right_on = " seq-end-on" if 1 in (from_index, to_index) else ""
        visual_steps.append(
            f'<li class="{classes}" aria-hidden="true"><span class="seq-end seq-end-left{left_on}">{esc(lanes[0])}</span>'
            f'<span class="seq-route"><span class="seq-arrow">{arrow}</span></span>'
            f'<span class="seq-end seq-end-right{right_on}">{esc(lanes[1])}</span>'
            f'<span class="seq-step-copy"><span class="seq-number">{number}</span>{badge}'
            f'<span class="seq-label">{esc(step.get("label", ""))}</span>{detail}{cross}{blocked_text}</span></li>'
        )
        text_steps.append(f"<li>{esc(_seq_sentence(lanes, step))}</li>")
    return (
        f'<div class="seq-figure"><div class="seq-lane-head"><h4 class="seq-lane seq-lane-0"><span>0</span>{esc(lanes[0])}</h4><h4 class="seq-lane seq-lane-1"><span>1</span>{esc(lanes[1])}</h4></div>'
        f'<ol class="seq-steps">{"".join(visual_steps)}</ol>'
        f'<div class="seq-text"><h4>文字版（每步一句话）</h4><ol>{"".join(text_steps)}</ol></div>'
        f'<p class="seq-note">{esc(r.get("note", ""))}</p></div>'
    )


def _lesson5_caption(r):
    if r["kind"] == "callpanel":
        if r.get("caption"):      # a record may say in its own words what the panel is (e.g. a local experiment, a return with a request id cut out); a 示意 record must still say 示意
            assert r.get("honest") == "shice" or "示意" in str(r["caption"]), "a 示意 callpanel caption must say 示意"
            return f'{r.get("date", "")} · {r["caption"]}'
        return f'{r.get("date", "")} · ' + ("某一次的返回，原样" if r.get("honest") == "shice" else "是示意，不是实测")
    caption = f'{r.get("date", "")} · 示意图：是示意，不是实测'
    if any(step.get("source") == "doc" for step in (r.get("steps") or [])):
        caption += " · 其中标‘文档写的’的步骤只是引文档"
    return caption


LESSON5_KINDS = {
    "callpanel": lambda r, c: (
        callpanel(r),
        _lesson5_caption(r),
        TAG_SHICE if r.get("honest") == "shice" else '<span class="tag tag-shiyi">示意</span>',
    ),
    "sequence": lambda r, c: (sequence(r), _lesson5_caption(r), '<span class="tag tag-shiyi">示意</span>'),
}


# ------------------------------------------------------------ lesson 6 kinds
L6_STATES = {"pinned": "固定", "kept": "保留", "torn": "撕下", "missing": "缺"}
L6_CLASSES = {"correct": "答对", "unknown": "没有看到", "named": "说出名字", "not_named": "没有说出名字"}


def _l6_required(obj, key):
    value = obj[key]
    assert value is not None and value != "" and value != [], f"{key} 不能为空"
    return value


def _l6_int(obj, key, minimum=0):
    value = _l6_required(obj, key)
    if type(value) is not int or value < minimum:
        raise ValueError(f"{key} must be an integer >= {minimum}")
    return value


def _l6_number_text(text):
    """Escape raw chunks, wrapping only ASCII digit runs (never HTML entities)."""
    return "".join(f"<code>{part}</code>" if re.fullmatch(r"[0-9]+", part) else esc(part)
                   for part in re.split(r"([0-9]+)", str(text)))


def window(r):
    notes = _l6_required(r, "notes")
    folder = r["folder"]
    torn = sum(note["state"] == "torn" for note in notes)
    if folder is not None and _l6_int(folder, "count") != torn:
        raise ValueError("window folder.count must equal the number of torn notes")
    papers, sentences = [], []
    in_window = False
    for number, note in enumerate(notes, 1):
        state, role = note["state"], note["role"]
        if state not in L6_STATES or role not in ("system", "user", "assistant"):
            raise ValueError("unknown window state or role")
        if state == "pinned" and role != "system":
            raise ValueError("a pinned note must be a system message")
        if state == "missing" and r["honest"] != "shiyi":
            raise ValueError("missing notes are only allowed in a shiyi window")
        if state == "kept" and not in_window:
            papers.append('<div class="l6-window-frame" role="group" aria-label="在窗口里">')
            in_window = True
        elif state != "kept" and in_window:
            papers.append('</div>')
            in_window = False
        role_cn = _l6_required(note, "role_cn")
        text = _l6_required(note, "text")
        state_text = {"pinned": "系统消息，固定在摞上", "kept": "在窗口里", "torn": "这一次不在信封里", "missing": "缺"}[state]
        pin = '<i class="l6-pin" aria-hidden="true"></i>' if state == "pinned" else ""
        mark = f'<p class="l6-window-mark">{esc(note["mark"])}</p>' if note["mark"] else ""
        papers.append(f'<div class="l6-window-paper l6-window-{state}">{pin}'
                      f'<b>{esc(role_cn)}</b><p>{_l6_number_text(text)}</p>'
                      f'<span class="l6-window-state">{state_text}</span>{mark}</div>')
        shown = text[:-1] if (note["mark"] and text.endswith("。")) else text          # the paper's own full stop would meet the semicolon of the mark ("。；")
        sentence = f'第 {number} 条，{role_cn}，{L6_STATES[state]}，{shown}'
        if note["mark"]:
            sentence += f'；{note["mark"]}'
        end = "" if sentence.rstrip()[-1:] in "。？！" else "。"          # a paper's own sentence-final mark is kept (no "。。" or "？。" in the text version)
        sentences.append(f'<li>{_l6_number_text(sentence)}{end}</li>')
    if in_window:
        papers.append('</div>')
    folder_html = (f'<aside class="l6-folder"><b>{esc(_l6_required(folder, "label"))}</b>'
                   f'<p>撕下的 {esc(folder["count"])} 张在这里，没有消失</p></aside>') if folder is not None else ""
    return (f'<div class="l6-window"><div class="l6-window-layout">'
            f'<div class="l6-window-papers" aria-hidden="true">{"".join(papers)}</div>{folder_html}</div>'
            f'<div class="l6-window-text"><h4>文字版（每张纸条一句话）</h4><ol>{"".join(sentences)}</ol></div>'
            f'<p class="l6-note">{esc(r["note"])}</p></div>')


def _l6_interval(value):
    lo, hi = _l6_int(value, "lo"), _l6_int(value, "hi")
    if lo > hi:
        raise ValueError("range requires lo <= hi")
    display = _l6_required(value, "display")
    number = r"([0-9]+(?:,[0-9]{3})*)"
    match = re.fullmatch(r"\s*" + number + r"\s*(?:[–—\-~～至到]\s*" + number + r")?\s*", str(display))
    shown = [int(x.replace(",", "")) for x in match.groups() if x is not None] if match else []
    if shown != ([lo] if lo == hi else [lo, hi]):
        raise ValueError("display must match lo/hi and distinguish a point from a range")
    return lo, hi


def _l6_bar(value, label, color, maximum, plateau=None):
    lo, hi = _l6_interval(value)
    solid = f'<i class="l6-bar-solid" style="width:{lo / maximum * 100:.6f}%"></i>'
    outline = (f'<i class="l6-bar-range" style="left:{lo / maximum * 100:.6f}%;width:{(hi - lo) / maximum * 100:.6f}%"></i>'
               if lo < hi else "")
    band = ""
    if plateau is not None:
        low, high = _l6_interval(plateau)
        band = (f'<i class="l6-plateau-band" style="left:{low / maximum * 100:.6f}%;width:{(high - low) / maximum * 100:.6f}%"></i>')
    plateau_text = f'<span class="l6-plateau-label">淡绿色带：{esc(plateau["display"])}</span>' if plateau is not None else ""
    return (f'<div class="l6-bar-line l6-bar-{color}"><span>{label}</span>'
            f'<div class="l6-bar-track" aria-hidden="true">{band}{solid}{outline}</div>'
            f'<span class="l6-bar-value">{esc(value["display"])}</span>{plateau_text}</div>')


def turnbars(r):
    turns = _l6_required(r, "turns")
    plateau, cumulative = r["plateau"], r["cumulative"]
    values = [turn[key] for turn in turns for key in ("full", "trim")]
    numbers = [_l6_int(turn, "turn", 1) for turn in turns]
    if numbers != sorted(set(numbers)):
        raise ValueError("turn numbers must be unique and increasing")
    if plateau is not None:
        if _l6_int(plateau, "from_turn", 1) not in numbers:
            raise ValueError("plateau.from_turn must name a plotted turn")
        values.append(plateau)
    if cumulative is not None:
        values.extend(cumulative[key] for key in ("full", "trim"))
        _l6_interval(cumulative["saved"])
    # All plotted bars and bands use one scale, including the cumulative bars.
    maximum = max(_l6_interval(value)[1] for value in values) or 1
    rows_html = []
    for turn in turns:
        band = plateau if plateau is not None and turn["turn"] >= plateau["from_turn"] else None
        rows_html.append(f'<section class="l6-turn"><h4>第 {esc(turn["turn"])} 轮</h4>'
                         + _l6_bar(turn["full"], "整摞", "full", maximum)
                         + _l6_bar(turn["trim"], "只留六条", "trim", maximum, band) + '</section>')
    cumulative_html = ""
    if cumulative is not None:
        cumulative_html = ('<section class="l6-cumulative"><h4>累计（把各轮的数加起来）</h4>'
                           + _l6_bar(cumulative["full"], "整摞", "full", maximum)
                           + _l6_bar(cumulative["trim"], "只留六条", "trim", maximum)
                           + f'<p>少了 {esc(cumulative["saved"]["display"])}</p></section>')
    return (f'<div class="l6-turnbars"><h4>{esc(_l6_required(r, "model"))}</h4>'
            '<p class="l6-bar-legend">整摞 · 只留六条；实心到下限，描边到上限</p>'
            f'{"".join(rows_html)}{cumulative_html}<p class="l6-note">{esc(r["note"])}</p></div>')


def classgrid(r):
    labeler = _l6_required(r, "labeler")
    if "真人" in labeler or "人工" in labeler or ("AI" not in labeler and "程序" not in labeler):
        raise ValueError("classgrid labeler must say who judged: AI models or a program (never a human)")
    legend = {}
    legend_html = []
    for item in _l6_required(r, "legend"):
        cls = item["class"]
        if cls not in L6_CLASSES or cls in legend:
            raise ValueError("unknown or duplicate classgrid legend class")
        legend[cls] = _l6_required(item, "text")
        symbol = "✓" if cls in ("correct", "named") else "·"
        legend_html.append(f'<span><i class="l6-grid-symbol l6-grid-{cls}" aria-hidden="true">{symbol}</i> {esc(legend[cls])}</span>')
    rows_html = []
    for row in _l6_required(r, "rows"):
        cells, tally = _l6_required(row, "cells"), row["tally"]
        total, n = _l6_int(tally, "total", 1), _l6_int(tally, "n")
        if total != 10 or len(cells) != total:
            raise ValueError("classgrid requires ten cells and cells length == tally.total")
        if tally["class"] not in legend or n != sum(c["class"] == tally["class"] for c in cells):
            raise ValueError("classgrid tally.n must equal the count of tally.class")
        cells_html = []
        for number, cell in enumerate(cells, 1):
            cls = cell["class"]
            if cls not in legend:
                raise ValueError("classgrid cells must use a declared legend class")
            symbol = "✓" if cls in ("correct", "named") else "·"
            cells_html.append(f'<span class="l6-grid-cell l6-grid-{cls}" role="img" '
                              f'aria-label="{esc(f"第 {number} 遍，{legend[cls]}")}">{symbol}</span>')
        rows_html.append(f'<div class="l6-grid-row"><div>{esc(_l6_required(row, "label"))} · {esc(_l6_required(row, "model"))}</div>'
                         f'<div class="l6-grid-cells">{"".join(cells_html)}</div>'
                         f'<p class="l6-grid-tally">{esc(_l6_required(tally, "short"))} {n} / {total}</p></div>')
    return (f'<div class="l6-classgrid"><h4 class="l6-labeler">标注：{esc(labeler)}</h4>'
            f'<div class="l6-grid-legend">{"".join(legend_html)}</div>{"".join(rows_html)}'
            f'<p class="l6-note">{esc(r["note"])}</p></div>')


def _lesson6_record(r, renderer):
    honest = _l6_required(r, "honest")
    if honest not in ("shice", "shiyi") or (r["kind"] != "window" and honest != "shice"):
        raise ValueError("invalid lesson 6 honest value")
    date = r["date"] if honest == "shiyi" else _l6_required(r, "date")
    if date is not None:
        from datetime import date as calendar_date
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date):
            raise ValueError("date must be YYYY-MM-DD")
        calendar_date.fromisoformat(date)
    elif honest == "shice":
        raise ValueError("a measured lesson 6 record requires a date")
    cap = _l6_required(r, "caliber")
    if date is not None:
        cap = f"{_l6_required(r, 'date')} · {cap}"
    if r["kind"] == "turnbars":
        cap += f" · {_l6_required(r, 'model')} · {_l6_int(r, 'runs', 1)} 遍"
    body = renderer(r)
    if honest == "shice":
        if "示意" in str(_l6_required(r, "title")) + body + cap:
            raise ValueError("a measured lesson 6 figure must not say 示意")
        tag = TAG_SHICE
    else:
        # the badge already says 示意 (the whole-site check reads it from the caption element, badge included); the caption does not say it again
        tag = '<span class="tag tag-shiyi">示意</span>'
    return body, cap, tag


LESSON6_KINDS = {
    "window": lambda r, c: _lesson6_record(r, window),
    "turnbars": lambda r, c: _lesson6_record(r, turnbars),
    "classgrid": lambda r, c: _lesson6_record(r, classgrid),
}


def show(b, ctx):
    r = ctx.records[b["id"]]
    ctx.used_records.append(b["id"])
    head = f'<div class="fh">{esc(r["title"])}</div>'
    tag = TAG_SHICE
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
    elif r["kind"] in LESSON3_KINDS:
        body, cap, tag = LESSON3_KINDS[r["kind"]](r, ctx)
    elif r["kind"] in LESSON4_KINDS:
        body, cap, tag = LESSON4_KINDS[r["kind"]](r, ctx)
    elif r["kind"] in LESSON5_KINDS:
        body, cap, tag = LESSON5_KINDS[r["kind"]](r, ctx)
    elif r["kind"] in LESSON6_KINDS:
        body, cap, tag = LESSON6_KINDS[r["kind"]](r, ctx)
    else:
        raise AssertionError(r["kind"])
    after = f'<p class="after">{esc(b["after"])}</p>' if b.get("after") else ""
    return f'<figure class="show" data-record="{esc(b["id"])}">{head}{body}<figcaption class="rec">{tag} {esc(cap)}</figcaption>{after}</figure>'


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
