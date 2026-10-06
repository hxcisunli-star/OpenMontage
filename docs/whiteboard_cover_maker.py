"""Unified 16:9 covers (1920x1080) for the six C-lesson videos.

Run: PYTHONPATH=. .venv/bin/python docs/whiteboard_cover_maker.py
Latin letters / digits / symbols always use a mono font (ZCOOL draws 0, o, c and
capitals as squares, see playbook 2.6).
"""
import random
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path("projects")
ZCOOL = str("remotion-composer/public/fonts/ZCOOLKuaiLe-Regular.ttf")
MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
DOCTOR = ROOT / "c-struct-parameters-cn/assets/images/doctor_pointing.png"
LOGO = ROOT / "c-struct-parameters-cn/assets/images/schoollogo.png"

INK = (30, 34, 48)
RED = (214, 40, 40)
BLUE = (110, 128, 168)
PAPER = (250, 250, 247)

LESSONS = [
    ("bubble-sort-tutorial-cn", 1, "冒泡排序", "一趟一趟，把大数“冒”到最后", "7 3 9 1 5"),
    ("c-value-vs-address-cn", 2, "值传递与地址传递", "函数里改了，为什么原件没变？", "swap(a, b);"),
    ("c-array-parameters-cn", 3, "数组传参", "为什么函数能改掉数组里的元素？", "a[0] = 99;"),
    ("c-strings-cn", 4, "字符串", "字符串为什么不用另外传长度？", "'h' 'i' '\\0'"),
    ("c-scanf-address-cn", 5, "scanf 与 &", "读整数要加 &，读字符串却不用？", 'scanf("%d", &n);'),
    ("c-struct-parameters-cn", 6, "结构体传参", "传整张卡，函数改了也白改？", "birthday_value(card);"),
    ("c-pointer-basics-cn", 7, "指针初步", "地址纸条原来是个变量，星号什么意思？", "int *p = &age;"),
    ("c-pointer-array-cn", 8, "指针与数组", "数组名为什么是地址？函数为什么数不出？", "a[i] == *(a + i)"),
    ("c-function-return-cn", 9, "函数返回值", "为什么不能把局部变量的地址交出来？", "return &local;"),
    ("c-two-dim-array-cn", 10, "二维数组传参", "为什么列数不能省？", "int a[][3]"),
    ("c-dynamic-memory-cn", 11, "动态内存分配", "函数结束了，申请的病房为什么还在？", "malloc(3 * sizeof(int))"),
    ("c-linked-list-intro-cn", 12, "链表初识", "数组要挪，病历卡为什么不用挪？", "head → 9 → 1 → 2 → 3"),
]


def runs(text):
    out, cur, ascii_ = [], "", None
    for ch in text:
        a = ord(ch) < 128
        if ascii_ is None or a == ascii_:
            cur += ch
        else:
            out.append((cur, ascii_))
            cur = ch
        ascii_ = a
    if cur:
        out.append((cur, ascii_))
    return out


def draw_mixed(d, xy, text, size, fill, bold_mono=True):
    """Draw text; returns end x. ASCII runs in mono, the rest in ZCOOL."""
    x, y = xy
    zf = ImageFont.truetype(ZCOOL, size)
    mf = ImageFont.truetype(MONO_B if bold_mono else MONO, int(size * 0.92))
    for seg, is_ascii in runs(text):
        f = mf if is_ascii else zf
        d.text((x, y), seg, font=f, fill=fill)
        x += d.textlength(seg, font=f)
    return x


def width_mixed(d, text, size):
    zf = ImageFont.truetype(ZCOOL, size)
    mf = ImageFont.truetype(MONO_B, int(size * 0.92))
    return sum(d.textlength(s, font=mf if a else zf) for s, a in runs(text))


def wobble_line(d, x1, x2, y, color, w, rnd):
    pts = []
    n = 14
    for i in range(n + 1):
        pts.append((x1 + (x2 - x1) * i / n, y + rnd.uniform(-3, 3)))
    d.line(pts, fill=color, width=w, joint="curve")


def make(proj, no, title, sub, code):
    rnd = random.Random(no)
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), (200, 210, 226))
    d = ImageDraw.Draw(img)
    # paper card with border
    d.rounded_rectangle((18, 18, W - 18, H - 18), 36, fill=(160, 172, 198))
    d.rounded_rectangle((28, 28, W - 28, H - 28), 30, fill=PAPER)
    for gx in range(88, W - 28, 60):
        d.line((gx, 30, gx, H - 30), fill=(238, 238, 234), width=1)
    for gy in range(88, H - 28, 60):
        d.line((30, gy, W - 30, gy), fill=(238, 238, 234), width=1)

    # logo top-left
    logo = Image.open(LOGO).convert("RGBA")
    lw = 330
    logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    d.rounded_rectangle((70, 52, 70 + lw + 40, 52 + logo.height + 40), 14, fill=(22, 36, 82))
    img.paste(logo, (90, 72), logo)

    # series tag top-right
    tag = "C语言白板课"
    tw = width_mixed(d, tag, 44)
    draw_mixed(d, (W - 90 - tw, 72), tag, 44, BLUE)

    # lesson badge
    bx, by = 110, 250
    bw = max(270, int(width_mixed(d, f"第{no}课", 80)) + 72)   # two-digit lesson numbers need a wider badge
    d.rounded_rectangle((bx, by, bx + bw, by + 112), 28, fill=RED)
    draw_mixed(d, (bx + 36, by + 12), f"第{no}课", 80, (255, 255, 255))

    # title (shrink to fit left area)
    size = 190
    while width_mixed(d, title, size) > 1130:
        size -= 6
    tx, ty = 110, 400
    draw_mixed(d, (tx, ty), title, size, INK)
    ul_y = ty + int(size * 1.28)
    wobble_line(d, tx, tx + width_mixed(d, title, size), ul_y, RED, 10, rnd)

    # subtitle
    sub_size = 60
    while width_mixed(d, sub, sub_size) > 1130:
        sub_size -= 2
    draw_mixed(d, (tx, ul_y + 40), sub, sub_size, (70, 84, 118))

    # code chip
    cf = ImageFont.truetype(MONO, 56)
    cw = int(d.textlength(code, font=cf)) + 80
    cy = 820
    d.rounded_rectangle((tx, cy, tx + cw, cy + 120), 22, fill=(236, 240, 248),
                        outline=(150, 164, 196), width=4)
    d.text((tx + 40, cy + 26), code, font=cf, fill=INK)

    # doctor right
    doc = Image.open(DOCTOR).convert("RGBA")
    dh = 900
    doc = doc.resize((int(doc.width * dh / doc.height), dh), Image.LANCZOS)
    img.paste(doc, (W - 90 - doc.width - 60, H - 70 - dh), doc)

    out = ROOT / proj / "exports/thumbnails/cover.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    img.resize((1280, 720), Image.LANCZOS).save(out.parent / "cover_1280x720.jpg", quality=92)
    mp = ROOT / proj / "exports/metadata/metadata.json"
    if mp.exists():  # lesson number and cover paths go into the publish metadata
        import json
        m = json.loads(mp.read_text(encoding="utf-8"))
        m.update(lesson_number=no, cover_path="exports/thumbnails/cover.png", cover_path_1280x720="exports/thumbnails/cover_1280x720.jpg")
        mp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return out, img


def main():
    """No argument: rebuild every lesson and the contact sheet. With lesson numbers (e.g. `... 7`): only those lessons."""
    only = {int(a) for a in sys.argv[1:]}
    imgs = []
    for row in LESSONS:
        if only and row[1] not in only:
            continue
        out, img = make(*row)
        print("wrote", out)
        imgs.append(img.resize((960, 540), Image.LANCZOS))
    if only:
        return
    rows = (len(imgs) + 1) // 2
    sheet = Image.new("RGB", (960 * 2, 540 * rows), (255, 255, 255))
    for i, im in enumerate(imgs):
        sheet.paste(im, ((i % 2) * 960, (i // 2) * 540))
    (ROOT / "_covers").mkdir(exist_ok=True)
    sheet.save(ROOT / "_covers/contact_sheet.png")


if __name__ == "__main__":
    main()
