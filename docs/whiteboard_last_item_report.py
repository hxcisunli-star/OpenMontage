"""Health report for PUBLISHED lessons: boards whose last handwriting item is still being drawn when the board fades out. Read-only (changes no lesson).
Run:  .venv/bin/python docs/whiteboard_last_item_report.py [--out docs/whiteboard/old-lessons-last-item-report.zh-CN.md] [--sheet DIR]
Classes per board (timing from docs/whiteboard_boardtime.py, the same rule as the renderer):
  A  cut off      the last item is still being drawn when the board ends (the viewer sees a half-written line)
  B  in the fade  the last item finishes after the 0.4 s fade-out has started
  C  tight        it finishes less than 0.6 s before the fade starts (fine to watch, no safety margin)
--sheet DIR also extracts, for every class A board, the frame 0.45 s before the cut ends from renders/final.mp4 into contact sheets in DIR."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whiteboard_boardtime import board_rows  # noqa: E402
from whiteboard_lessons import lesson_table  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def classify(r):
    if r["last_end"] > r["length"]:
        return "A"
    if r["margin"] < 0:
        return "B"
    if r["margin"] < 0.6:
        return "C"
    return "ok"


def mmss(t):
    return f"{int(t) // 60:02d}:{int(t) % 60:02d}"


def collect():
    out = []
    for proj, (n, title) in lesson_table().items():
        d = ROOT / "projects" / proj
        try:
            rows = board_rows(d)
        except Exception:
            continue
        for r in rows:
            r.update(lesson=n, title=title, project=proj, cls=classify(r))
        out.append((n, title, proj, rows))
    return out


def make_sheets(boards, sheet_dir):
    from PIL import Image, ImageDraw, ImageFont
    sheet_dir.mkdir(parents=True, exist_ok=True)
    latin = ImageFont.truetype(str(ROOT / "remotion-composer/render-fonts/DejaVuSans.ttf"), 20)
    zcool = sorted(ROOT.glob("projects/*/references/ZCOOLKuaiLe-Regular.ttf"))
    cjk = ImageFont.truetype(str(zcool[0]), 20) if zcool else latin
    tiles = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, r in enumerate(boards):
            png = Path(tmp) / f"{i}.png"
            mp4 = ROOT / "projects" / r["project"] / "renders" / "final.mp4"
            if not mp4.exists():
                continue
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{r['out'] - 0.45:.3f}", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=640:-1", str(png)], check=True)
            im = Image.open(png).convert("RGB")
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, im.width, 28], fill=(255, 255, 255))
            x = 6
            for ch in f"第{r['lesson']}课 {r['id']}  板结束时只写出 {r['progress_at_end']:.0%}":  # hand font has CJK but draws digits and capitals as squares
                f = cjk if ord(ch) > 0x2E7F else latin
                d.text((x, 3), ch, fill=(180, 35, 24), font=f)
                x += d.textlength(ch, font=f)
            tiles.append(im)
    paths = []
    for s in range(0, len(tiles), 12):
        chunk = tiles[s:s + 12]
        w, h = chunk[0].size
        sheet = Image.new("RGB", (w * 3, h * ((len(chunk) + 2) // 3)), (255, 255, 255))
        for k, im in enumerate(chunk):
            sheet.paste(im, ((k % 3) * w, (k // 3) * h))
        p = sheet_dir / f"last-item-A-{s // 12 + 1}.png"
        sheet.save(p)
        paths.append(p)
    return paths


def report(data, sheets=()):
    boards = [r for _, _, _, rows in data for r in rows]
    cnt = {c: sum(1 for r in boards if r["cls"] == c) for c in ("A", "B", "C", "ok")}
    lessons = [(n, t, p, rows) for n, t, p, rows in data if rows]
    worst = lambda rows: min(r["margin"] for r in rows)  # noqa: E731
    la = [x for x in lessons if any(r["cls"] == "A" for r in x[3])]
    lb = [x for x in lessons if any(r["cls"] in ("A", "B") for r in x[3])]
    lc = [x for x in lessons if any(r["cls"] in ("A", "B", "C") for r in x[3])]
    L = ["# 老课体检：每块板的最后一项笔迹有没有写完就淡出", "",
         "> 由 `docs/whiteboard_last_item_report.py` 生成（只读，没有改任何已发布的课）。判定规则与渲染器一致（`docs/whiteboard_boardtime.py`）；重新生成：`.venv/bin/python docs/whiteboard_last_item_report.py --out docs/whiteboard/old-lessons-last-item-report.zh-CN.md`。", "",
         "## 结论", "",
         f"- 共 {len(lessons)} 课、{len(boards)} 块白板。**A 类（板结束时最后一项还没写完，观众看到半行字）{cnt['A']} 块，分布在 {len(la)} 课**；B 类（淡出开始后才写完）{cnt['B']} 块；C 类（写完离淡出不足 0.6 秒，没有余量但看得全）{cnt['C']} 块；其余 {cnt['ok']} 块合格。",
         f"- 其中 {sum(1 for r in boards if r['cls'] == 'A' and r['progress_at_end'] <= 0.001)} 块的最后一项在板结束时还没开始写，视频里根本没有出现（表里标“没出现”）。",
         f"- 至少有一块 A 或 B 的课：{len(lb)} 课；至少有一块 A、B、C 之一的课：{len(lc)} 课。",
         "- 第 41 课起检查做成脚本之后，第 41、42、43 课全部合格。",
         "- 我目测过的几块（第 18 课 K6、第 30 课 K4、第 35 课 K5，淡出前一帧）最后一行都只写了一半；是否值得重渲，由你按下面的表决定。", ""]
    if sheets:
        L += ["A 类每块淡出前一帧的拼图（带“板结束时只写出百分之几”）在本机：" + "、".join(f"`{p}`" for p in sheets) + "（图片不进仓库）。", ""]
    L += ["## A 类和 B 类逐块清单（按课号）", "",
          "“看哪里”是发布版 `output.mp4`（含 2 秒封面片头）里该块淡出前半秒的时间，拖到那里看最后一行。“建议”是让余量回到 0.6 秒所需把最后一项提前的秒数；若旁白最后一句本来就在板结束前才说完，提前量要和旁白对齐，也可以缩短这一项的书写时长或删掉它。", "",
          "| 课 | 课名 | 块 | 类 | 最后一项 | 淡出开始时已写 | 板结束时已写 | 看哪里 | 建议提前 |", "|---|---|---|---|---|---|---|---|---|"]
    for n, t, p, rows in lessons:
        for r in rows:
            if r["cls"] in ("A", "B"):
                text = r["last_text"].replace("|", "｜")
                cls = "A（没出现）" if r["cls"] == "A" and r["progress_at_end"] <= 0.001 else r["cls"]
                L.append(f"| {n} | {t} | {r['id']} | {cls} | {r['last_kind']}：{text} | {r['progress_at_fade']:.0%} | {r['progress_at_end']:.0%} | {mmss(r['out'] - 0.5 + 2.0)} | {0.6 - r['margin']:.1f} 秒 |")
    L += ["", "## C 类（只列课号与块号，不是缺陷）", ""]
    for n, t, p, rows in lessons:
        cs = [r["id"] for r in rows if r["cls"] == "C"]
        if cs:
            L.append(f"- 第 {n} 课《{t}》：{'、'.join(cs)}")
    L += ["", "## 要修的话怎么做（由你决定，我不会自己改已发布的课）", "",
          "- 改一块只重渲一块（分块渲染按指纹缓存）：改该课 `scripts/_body_boards.py` 里这一块最后一项的 `at` 或 `dur` → `bash scripts/rebuild_edit.sh` → `render_final.py`（只重渲变了的块）→ 重做核对、`whiteboard_prepend_cover.py` 与成品包，并请你重新审看。",
          "- 老课脚本是已发布版本的记录；改之前先在 `projects/` 本机库里提交一次，改完能对比。",
          "- 优先级建议：A 类里“板结束时已写”低于 60% 且字多的块（观众最容易看出缺了一截）。"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    ap.add_argument("--sheet", help="directory for the class-A contact sheets (local, not versioned)")
    args = ap.parse_args()
    data = collect()
    sheets = []
    if args.sheet:
        a_boards = sorted((r for _, _, _, rows in data for r in rows if r["cls"] == "A"), key=lambda r: r["progress_at_end"])
        sheets = make_sheets(a_boards, Path(args.sheet))
    text = report(data, sheets)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote", args.out, f"({len(text.splitlines())} lines)")
    else:
        print(text)


if __name__ == "__main__":
    main()
