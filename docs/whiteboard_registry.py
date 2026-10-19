#!/usr/bin/env python3
"""白板课“登记表”工具：让经验只存一处，清单是它的视图。在仓库根目录运行：

  .venv/bin/python docs/whiteboard_registry.py index [--src P6|H|L] [--lesson N[-M]]   列出可映射的来源条目（带编号）
  .venv/bin/python docs/whiteboard_registry.py coverage   每个踩坑行（P6）与笔记子句（H）都要映射到登记条目或标“叙述”；未映射的列出，退出码 1
  .venv/bin/python docs/whiteboard_registry.py stats      各条规则出现在几课的笔记里；停在“清单”级却反复出现的，列为待做成脚本
  .venv/bin/python docs/whiteboard_registry.py render     由 docs/whiteboard/lessons-learned.yaml 生成 docs/whiteboard/checklists/*.md
  .venv/bin/python docs/whiteboard_registry.py check      清单与登记表不一致时退出码 1（改了登记表却没重新 render）

来源编号：P6-n = 做课手册 §6“踩坑速查表”第 n 行；Hn-k = 交接文档（归档全文）里“做下一课要注意（来自第 n 课）”的第 k 个子句；
Ln-k = 手册逐课章节里第 n 课“教训”的第 k 个分点（只作旁证，不要求映射）。
晋升规则：一条教训第二次出现仍停在文字上（level: 清单 而且 stats 里出现 ≥3 课），就该做成脚本（level: 检查）或模板默认（level: 默认）。
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REG = DOCS / "whiteboard" / "lessons-learned.yaml"
OUT = DOCS / "whiteboard" / "checklists"
PLAYBOOK = DOCS / "whiteboard-course-playbook.zh-CN.md"
HANDOFF = DOCS / "whiteboard" / "archive" / "handoff-full-20261019.zh-CN.md"
PERLESSON = DOCS / "whiteboard" / "archive" / "playbook-2.12-2.48-per-lesson.zh-CN.md"

LEVELS = ("检查", "默认", "清单", "叙述")
STAGE_ORDER = ["any", "plan", "script", "scene", "assets", "edit", "compose", "publish"]
FILES = {"any": "00-always.md", "plan": "01-plan.md", "script": "02-script.md", "scene": "03-scene-plan.md",
         "assets": "04-assets.md", "edit": "05-edit.md", "compose": "06-compose.md", "publish": "07-publish.md"}
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"


# ---------- 来源条目 ----------
def load_p6():
    lines = PLAYBOOK.read_text(encoding="utf-8").split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("## 6. "))
    items, n = {}, 0
    for l in lines[start + 1:]:
        if l.startswith("## "):
            break
        if l.strip() == "---" and items:
            break
        if not l.startswith("|"):
            continue
        m = re.match(r"^\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$", l)
        if not m or m.group(1) in ("现象",) or set(m.group(1)) <= set("-: "):
            continue
        n += 1
        items[f"P6-{n}"] = f"{m.group(1)} ⇒ {m.group(3)}（原因：{m.group(2)}）"
    return items


def split_clauses(text):
    out = []
    for c in re.split(r"；", text):
        c = c.strip()
        if not c:
            continue
        if len(c) > 130:
            out.extend(p.strip() for p in re.split(r"(?<=。)", c) if p.strip())
        else:
            out.append(c)
    return out


def load_h():
    items = {}
    rx = re.compile(r"^做下一课要注意（(?:来自第 (\d+) 课|(教学设计 skill)[^）]*)）：(.*)$")
    for l in HANDOFF.read_text(encoding="utf-8").split("\n"):
        m = rx.match(l)
        if not m:
            continue
        tag = m.group(1) or "skill"
        k0 = sum(1 for i in items if i.startswith(f"H{tag}-"))
        for k, c in enumerate(split_clauses(m.group(3)), start=k0 + 1):
            items[f"H{tag}-{k}"] = c
    return items


def load_l():
    items = {}
    text = PERLESSON.read_text(encoding="utf-8")
    for sec in re.split(r"\n(?=### 2\.\d+ )", text):
        head = sec.split("\n", 1)[0]
        m = re.search(r"第 (\d+) 课", head)
        mm = re.search(r"^- \*\*教训\*\*：(.+)$", sec, re.M)
        if not (m and mm):
            continue
        parts = [p.strip() for p in re.split("[" + CIRCLED + "]", mm.group(1)) if p.strip()]
        for k, p in enumerate(parts, start=1):
            items[f"L{m.group(1)}-{k}"] = p
    return items


def lesson_of(item_id):
    m = re.match(r"^[HL](\d+)-\d+$", item_id)
    return int(m.group(1)) if m else None


def expand(tok):
    tok = str(tok).strip()
    m = re.match(r"^([A-Z])(\w+?)-(\d+)\.\.(\d+)$", tok)
    if m:
        return [f"{m.group(1)}{m.group(2)}-{i}" for i in range(int(m.group(3)), int(m.group(4)) + 1)]
    return [tok]


def sort_key(item_id):
    m = re.match(r"^([A-Z])(\w+?)-(\d+)$", item_id)
    if not m:
        return (item_id, 0, 0)
    num = int(m.group(2)) if m.group(2).isdigit() else 999
    return (m.group(1), num, int(m.group(3)))


# ---------- 登记表 ----------
def load_reg():
    if not REG.exists():
        sys.exit(f"没有找到登记表：{REG}")
    text = REG.read_text(encoding="utf-8")
    reg = yaml.safe_load(text)
    # 普通字符串里的“ #”会被 YAML 当成注释，把后面的字悄悄截掉——逐行扫一遍
    reg["_risks"] = [(n, l.strip()[:60]) for n, l in enumerate(text.split("\n"), 1)
                     if not l.strip().startswith("#") and re.search(r"\s#", l)]
    return reg


def validate(reg):
    errs, ids = [], set()
    errs += [f"登记表第 {n} 行含“ #”，会被当作注释截断：{s}" for n, s in reg.get("_risks", [])]
    stages = set(reg.get("stages", {}))
    for e in reg.get("entries", []):
        eid = e.get("id", "?")
        if eid in ids:
            errs.append(f"重复的条目编号 {eid}")
        ids.add(eid)
        if e.get("stage") not in stages:
            errs.append(f"{eid}: stage 不在 stages 里：{e.get('stage')}")
        if e.get("level") not in LEVELS:
            errs.append(f"{eid}: level 必须是 {LEVELS}")
        if not e.get("rule"):
            errs.append(f"{eid}: 缺 rule")
        if e.get("level") == "检查" and not e.get("by"):
            errs.append(f"{eid}: level 为检查时必须写 by（脚本路径）")
        if not e.get("from"):
            errs.append(f"{eid}: 缺 from（来源编号）")
    return errs


def cmd_index(args):
    items = {}
    srcs = [args.src] if args.src else ["P6", "H", "L"]
    if "P6" in srcs:
        items.update(load_p6())
    if "H" in srcs:
        items.update(load_h())
    if "L" in srcs:
        items.update(load_l())
    lo, hi = 0, 10 ** 6
    if args.lesson:
        a, _, b = args.lesson.partition("-")
        lo, hi = int(a), int(b or a)
    for i in sorted(items, key=sort_key):
        n = lesson_of(i)
        if args.lesson and (n is None or not lo <= n <= hi):
            continue
        print(f"{i}\t{items[i]}")


def mapped_ids(reg, universe):
    mapped, unknown = {}, []
    for e in reg.get("entries", []):
        for tok in e.get("from", []):
            for i in expand(tok):
                if i not in universe:
                    unknown.append((e["id"], i))
                else:
                    mapped.setdefault(i, []).append(e["id"])
    for tok in reg.get("narrative", []):
        for i in expand(tok):
            if i not in universe:
                unknown.append(("narrative", i))
            else:
                mapped.setdefault(i, []).append("叙述")
    return mapped, unknown


def cmd_coverage(_):
    reg = load_reg()
    errs = validate(reg)
    p6, h, l = load_p6(), load_h(), load_l()
    universe = {**p6, **h, **l}
    mapped, unknown = mapped_ids(reg, universe)
    must = {**p6, **h}
    unmapped = [i for i in sorted(must, key=sort_key) if i not in mapped]
    print(f"来源条目：踩坑行 {len(p6)}、笔记子句 {len(h)}、教训分点 {len(l)}（旁证）；登记条目 {len(reg.get('entries', []))}")
    print(f"已映射：踩坑行 {sum(1 for i in p6 if i in mapped)}/{len(p6)}，笔记子句 {sum(1 for i in h if i in mapped)}/{len(h)}")
    for e in errs:
        print("错误:", e)
    for eid, i in unknown:
        print(f"错误: {eid} 引用了不存在的来源 {i}")
    for i in unmapped:
        print(f"未映射 {i}\t{must[i][:110]}")
    print(f"未映射共 {len(unmapped)} 条")
    return 1 if (unmapped or unknown or errs) else 0


def seen_lessons(entry):
    s = set(entry.get("seen_extra", []) or [])
    for tok in entry.get("from", []):
        for i in expand(tok):
            n = lesson_of(i)
            if n is not None:
                s.add(n)
    return sorted(s)


def cmd_stats(_):
    reg = load_reg()
    rows = []
    for e in reg.get("entries", []):
        rows.append((len(seen_lessons(e)), e))
    rows.sort(key=lambda r: -r[0])
    print("出现在几课的笔记里（≠出错次数） | 编号 | 阶段 | 级别 | 规则")
    for n, e in rows[:25]:
        print(f"{n:3d} 课 | {e['id']} | {e['stage']} | {e['level']} | {e['rule'][:50]}")
    by_level = {}
    for _, e in rows:
        by_level[e["level"]] = by_level.get(e["level"], 0) + 1
    print("级别分布:", by_level)
    cand = [(n, e) for n, e in rows if e["level"] == "清单" and n >= 3]
    print(f"\n待做成脚本或模板默认（停在清单级、出现在 ≥3 课的笔记里）：{len(cand)} 条")
    for n, e in cand:
        print(f"  {e['id']} 〔{n} 课〕{e['rule'][:60]}" + (f"  → 拟：{e['todo']}" if e.get("todo") else ""))
    return 0


def lessons_str(entry):
    ls = seen_lessons(entry)
    if not ls:
        return f"第 {entry['first']} 课" if entry.get("first") else ""
    if len(ls) > 7:
        return f"共 {len(ls)} 课，首见第 {ls[0]} 课"
    return "第 " + "、".join(map(str, ls)) + " 课"


def render_stage(reg, stage):
    st = reg["stages"][stage]
    ents = [e for e in reg["entries"] if e["stage"] == stage and e["level"] != "叙述"]
    out = [f"# 阶段清单 · {st['title']}（{stage}）", "",
           "> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。", ""]
    if st.get("gate"):
        out += [f"**口令**：{st['gate']}", ""]
    if st.get("read"):
        out += ["**开始前先 Read**："] + [f"- `{r['path']}` —— {r['why']}" for r in st["read"]] + [""]
    if st.get("steps"):
        out += ["**本阶段做什么**："] + [f"{i}. {s}" for i, s in enumerate(st["steps"], 1)] + [""]
    if st.get("outputs"):
        out += [f"**产出**：{st['outputs']}", ""]

    def line(e):
        bits = [f"- **[{e['id']}]** {e['rule']}"]
        if e.get("why"):
            bits.append(f"—— {e['why']}")
        tail = []
        ls = lessons_str(e)
        if ls:
            tail.append(ls)
        if e.get("by"):
            tail.append(f"脚本：`{e['by']}`")
        if e.get("todo"):
            tail.append(f"拟做成脚本：{e['todo']}")
        if tail:
            bits.append("〔" + "；".join(tail) + "〕")
        return " ".join(bits)

    groups = [("检查", "**已由脚本拦下**（先跑，红了就改，不要放宽阈值）："), ("清单", "**要人判断**（逐条过一遍）："),
              ("默认", "**已是模板或工具的默认做法**（知道即可，别改掉）：")]
    for lv, title in groups:
        sel = [e for e in ents if e["level"] == lv]
        if sel:
            out += [title] + [line(e) for e in sel] + [""]
    return "\n".join(out).rstrip() + "\n"


def render_all(reg):
    return {OUT / FILES[s]: render_stage(reg, s) for s in STAGE_ORDER if s in reg["stages"]}


def cmd_render(_):
    reg = load_reg()
    errs = validate(reg)
    if errs:
        print("\n".join("错误: " + e for e in errs))
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for path, text in render_all(reg).items():
        path.write_text(text, encoding="utf-8")
        print(f"写入 {path.relative_to(ROOT)}  {len(text.splitlines())} 行")
    return 0


def cmd_check(_):
    reg = load_reg()
    errs = validate(reg)
    stale = []
    for path, text in render_all(reg).items():
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            stale.append(path.relative_to(ROOT))
    for e in errs:
        print("错误:", e)
    for p in stale:
        print("过期（需要重新 render）:", p)
    if not errs and not stale:
        print("清单与登记表一致")
    return 1 if (errs or stale) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("index"); pi.add_argument("--src", choices=["P6", "H", "L"]); pi.add_argument("--lesson")
    for name in ("coverage", "stats", "render", "check"):
        sub.add_parser(name)
    args = ap.parse_args()
    sys.exit({"index": cmd_index, "coverage": cmd_coverage, "stats": cmd_stats, "render": cmd_render, "check": cmd_check}[args.cmd](args) or 0)


if __name__ == "__main__":
    main()
