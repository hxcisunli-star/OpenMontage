"""List every "第N课" callback in a lesson's narration next to the sentences of lesson N that it most resembles, so a human can check the quote against the source.
Run:  .venv/bin/python docs/whiteboard_callbacks.py projects/<lesson> [--lesson N] [--top 3] [--out validation/callbacks.md]
It cannot decide that a callback is right (that is docs/../.claude/skills/lesson-fact-check's job); it does the deterministic half: find the mention, find the cited lesson's
script.json, rank its sentences by shared character bigrams, and flag (a) a forward or missing reference, (b) no similar sentence at all, (c) different Chinese numerals in
the best match (lesson 43 says "不是二" where lesson 40's example program says "不是三" - a different program, but exactly the kind of thing to look at).
Lessons 22 ("有时原地变大，有时搬到新的地方" vs "长大就是搬家") and 43 ("九条命令" vs eight commands) were wrong the first time; this is how the first one is found."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whiteboard_lessons import lesson_refs_to, number_of, project_of, series_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
MENTION = re.compile(r"第([零〇一二两三四五六七八九十百]+)课")
NUMERALS = set("一二三四五六七八九十零〇两")


def cn2int(s):
    if "百" in s:
        h, _, rest = s.partition("百")
        return (DIGITS.get(h, 1) if h else 1) * 100 + (cn2int(rest) if rest else 0)
    if "十" in s:
        t, _, u = s.partition("十")
        return (DIGITS.get(t, 1) if t else 1) * 10 + (DIGITS.get(u, 0) if u else 0)
    return DIGITS.get(s, 0) if len(s) == 1 else int("".join(str(DIGITS.get(c, 0)) for c in s))


QUANT = re.compile(r"(?:([零〇一二两三四五六七八九十]+)(?=[个条句行张次步处份种位项遍秒倍格])|不是([零〇一二两三四五六七八九十]))")


def quantities(s):
    """Counts the sentence states ("三行", "不是二"); numerals inside words (零件, 一遍, 一律) are ignored."""
    return {a or b for a, b in QUANT.findall(MENTION.sub("", s))}


def sentences(text):
    return [x.strip() for x in re.split(r"(?<=[。？！])", text) if x.strip()]


def bigrams(s):
    s = re.sub(r"[，。？！：；、“”（）\s]", "", MENTION.sub("", s))
    return {s[i:i + 2] for i in range(len(s) - 1)}


def load_sections(project):
    p = ROOT / "projects" / project / "artifacts/script.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))["sections"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("--lesson", type=int)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--out")
    args = ap.parse_args()
    proj = Path(args.proj)
    me = args.lesson or number_of(proj.name)
    target = lesson_refs_to(proj)         # which series a bare "第N课" means: the project's own (new series), or the C course (the C series, and the frozen experiment lesson that quotes it)
    cross = target != series_of(proj.name)   # lesson numbers of two series are not comparable, so a reference into the other series gets no forward-reference check
    secs = load_sections(proj.name) if (ROOT / "projects" / proj.name).exists() else json.loads((proj / "artifacts/script.json").read_text(encoding="utf-8"))["sections"]
    cache, out, flagged = {}, [], 0
    for sec in secs:
        for sent in sentences(sec["text"]):
            for m in MENTION.finditer(sent):
                n = cn2int(m.group(1))
                head = f"## {sec['id']} → 第{n}课（{m.group(0)}）"
                lines = [head, f"- 本课：{sent}"]
                problems = []
                if me is not None and n >= me and not cross:
                    problems.append(f"引用的是第 {n} 课，本课是第 {me} 课：如果是预告，确认那一课真的这样安排；否则课号写错了")
                proj_n = project_of(n, target)
                if proj_n is None:
                    problems.append(f"找不到第 {n} 课的项目")
                else:
                    if proj_n not in cache:
                        cache[proj_n] = load_sections(proj_n)
                    src = cache[proj_n]
                    if src is None:
                        problems.append(f"第 {n} 课（{proj_n}）没有 artifacts/script.json")
                    else:
                        mine = bigrams(sent)
                        ranked = sorted(((len(mine & bigrams(x)) / max(len(mine | bigrams(x)), 1), s["id"], x) for s in src for x in sentences(s["text"])), reverse=True)[:args.top]
                        for score, sid, x in ranked:
                            lines.append(f"- 第{n}课 {sid}（相似度 {score:.2f}）：{x}")
                        if not ranked or ranked[0][0] < 0.08:
                            problems.append("第 %d 课里没有相似的句子（可能只是点了课号的泛泛回扣）：需要时人工去那一课找原话" % n)
                        else:
                            a = quantities(sent)
                            theirs = set().union(*(quantities(x) for _, _, x in ranked))
                            if a and not (a & theirs):
                                problems.append(f"数量不同：本课说 {'、'.join(sorted(a))}，原课最像的几句里是 {'、'.join(sorted(theirs)) or '没有数量'}——确认指的是同一个东西")
                for p in problems:
                    lines.append(f"- ⚠ {p}")
                flagged += bool(problems)
                out.append("\n".join(lines))
    where = f"第 {me} 课" if me is not None and not cross else "智能体篇" if cross else "课号未登记"
    note = "旁白里的“第N课”按 C 篇的课号查（这是写在“与 C 课脱钩”之前的试验课）。" if cross else ("旁白里的“第N课”指本系列自己的课；本系列与 C 课没有任何联系，找不到的课号就是写错了或在回扣 C 课。" if series_of(proj.name) != "c" else "")
    head = f"# 回扣核对：{proj.name}（{where}）\n\n{note}旁白里共 {len(out)} 处“第N课”，其中 {flagged} 处有提醒（⚠）。逐处对着原话看：课号对不对、说法有没有被改写成原课没说过的话。\n"
    text = head + "\n" + "\n\n".join(out) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}: {len(out)} callbacks, {flagged} flagged")
    else:
        print(text)


if __name__ == "__main__":
    main()
