"""Cover art for the 8 books of the ebook platform (local Qwen image edit; no text is painted, the site writes the titles).

Each book gets a portrait "layout reference" (a pastel sheet in the book's hue with the robot pose pasted in its lower half): with a
reference image the generator follows the first reference's frame, so this is how we get a portrait cover. The robot is the fixed
character of the series (projects/_cast/agent), the scene is the book's "take it apart, put it together" picture.

Files (projects/_ebook/covers/):  <book id>.png        the chosen cover
                                  raw/<book id>.a<N>.png  every attempt;  layout/<book id>.png  the reference sheet
                                  provenance.json         prompt, seed, tool, date, sha256 of every attempt
Run:  PYTHONPATH=. .venv/bin/python docs/whiteboard/ebook/make_covers.py [--only b1-foundation ...] [--attempt 2] [--pick b1-foundation:1]
One job at a time (the GPU server takes one); an attempt that already exists is not generated again."""
import argparse
import colorsys
import datetime
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import yaml
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
os.chdir(ROOT)
from build_site import BOOK_HUES  # noqa: E402
from tools.graphics.qwen_local_image import QwenLocalImage  # noqa: E402

EB = ROOT / "projects/_ebook"
OUT = EB / "covers"
CAST = ROOT / "projects/_cast/agent"
HUE_WORD = {212: "蓝", 4: "红", 150: "绿", 36: "橙黄", 280: "紫", 190: "青", 330: "粉", 100: "黄绿"}

# book id -> (robot pose file, the scene of the book)
SCENES = {
    "b1-foundation": ("robot_wave.png", "机器人站在一条白色起跑线上，向旁边挥手；身旁有一个打开的工具箱、一个小罗盘和一个小键盘，远处一条弯弯的小路通向一面小旗。"),
    "b2-llm": ("robot_idea.png", "机器人头顶飘着一串彩色的积木字块（只画空白积木，上面没有字），旁边有一个大对话气泡，气泡里只画三个圆点和两颗小星星。"),
    "b3-tools-eval": ("robot_point_l.png", "机器人一只手拿着扳手，另一只手拿着放大镜；身后是三块圆形仪表盘和一条向上的折线图，仪表盘上只有刻度线，没有数字。"),
    "b4-rag-workflow": ("robot_read_letter.png", "机器人捧着一叠资料页；资料页之间有弯弯的管道和箭头连成一条流水线，管道里有发光的小方块在流动。"),
    "b5-frameworks-protocols": ("robot_think_tilt.png", "机器人手里拿着一根带插头的电线，面前是一面带插孔的积木墙，几块不同形状的积木正在拼接在一起。"),
    "b6-safety-production": ("robot_barrier_grip.png", "机器人戴着黄色的安全帽，一只手扶着一道红白相间的栏杆；身旁有一面盾牌和一把大锁，盾牌和锁上都没有字。"),
    "b7-multi-capstone": ("robot_cheer.png", "机器人开心地举起手，左右各有一个外观相同、颜色不同的小机器人（一个橙色、一个绿色），三个机器人围着一块项目看板，看板上贴着彩色便签和连线，便签上没有字。"),
    "b8-advanced": ("robot_flag_hold.png", "机器人举着一面旗，沿着一级一级向上的台阶往上走，胸前挂着一架望远镜；远处是山峰和朝阳。"),
}
KEEP = "图1里的蓝色小机器人是固定角色：白色圆头盔、蓝色脸、一根天线、胸前一块蓝色方板，外观、颜色、比例都保持不变，不要改成别的样子。"
STYLE = "彩色平涂的卡通插画，深色轮廓线，暖色纸张质感，柔和的{hue}色淡色背景，竖版封面构图。"
TOP = "画面上方三分之一保持干净的淡色空白，不放任何东西；没有任何文字、字母、数字、标志、水印。"
NEG = "文字，字母，数字，汉字，水印，乱码，标志，商标，照片，写实，过重的阴影，多余的人物，变形的机器人，两个头，三只手"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def layout(book_id, n, pose):
    W, H = 1152, 1536
    r, g, b = [round(255 * x) for x in colorsys.hls_to_rgb(BOOK_HUES[n - 1] / 360, 0.90, 0.55)]
    sheet = Image.new("RGB", (W, H), (r, g, b))
    robot = Image.open(CAST / pose).convert("RGBA")
    robot = robot.crop(robot.getbbox())
    th = 820
    robot = robot.resize((round(robot.width * th / robot.height), th), Image.LANCZOS)
    sheet.paste(robot, ((W - robot.width) // 2, H - robot.height - 90), robot)
    p = OUT / "layout" / f"{book_id}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(p)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--pick", nargs="*", default=[], help="book-id:attempt — make that attempt the chosen cover and stop")
    a = ap.parse_args()
    books = yaml.safe_load((EB / "books.yaml").read_text(encoding="utf-8"))["books"]
    assert [b["id"] for b in books] == list(SCENES), "SCENES must list the books of books.yaml in order"
    prov_f = OUT / "provenance.json"
    prov = json.loads(prov_f.read_text(encoding="utf-8")) if prov_f.exists() else {}
    (OUT / "raw").mkdir(parents=True, exist_ok=True)

    for spec in a.pick:
        bid, n = spec.rsplit(":", 1)
        src = OUT / "raw" / f"{bid}.a{int(n)}.png"
        assert src.is_file(), f"no such attempt: {src.name}"
        shutil.copy2(src, OUT / f"{bid}.png")
        prov.setdefault(bid, {})["chosen"] = int(n)
        print("chosen", bid, "attempt", n)
    if a.pick:
        prov_f.write_text(json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")
        return

    tool = QwenLocalImage()
    for n, b in enumerate(books, 1):
        bid = b["id"]
        if a.only and bid not in a.only:
            continue
        raw = OUT / "raw" / f"{bid}.a{a.attempt}.png"
        if raw.is_file() and raw.stat().st_size > 10000:
            print("skip (exists)", raw.name)
            continue
        pose, scene = SCENES[bid]
        ref = layout(bid, n, pose)
        prompt = KEEP + STYLE.format(hue=HUE_WORD[BOOK_HUES[n - 1]]) + "场景：" + scene + TOP
        seed = 7100 + n * 10 + a.attempt
        t0 = time.time()
        res = tool.execute({"prompt": prompt, "negative_prompt": NEG, "image_paths": [str(ref)], "resolution": 1536, "steps": 40,
                            "seed": seed, "request_version": f"cover-a{a.attempt}", "output_path": str(raw)})
        took = round(time.time() - t0)
        if not res.success:
            print("FAILED", bid, res.error)
            continue
        im = Image.open(raw)
        e = prov.setdefault(bid, {})
        e.setdefault("attempts", {})[str(a.attempt)] = {"prompt": prompt, "negative": NEG, "seed": seed, "layout_ref": f"layout/{bid}.png", "layout_sha256": sha(ref),
                                                       "pose": pose, "size": list(im.size), "sha256": sha(raw), "tool": f"{tool.name} {tool.version}",
                                                       "seconds": took, "date": datetime.date.today().isoformat()}
        e["chosen"] = a.attempt
        shutil.copy2(raw, OUT / f"{bid}.png")
        prov_f.write_text(json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")
        print("ok", bid, im.size, f"{took}s", flush=True)


if __name__ == "__main__":
    main()
