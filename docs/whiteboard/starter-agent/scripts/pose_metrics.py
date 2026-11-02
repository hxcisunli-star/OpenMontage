"""Display-size table for the character poses, so that every pose of a character shows the same body size on the board (the images are trimmed to their opaque pixels, so a pose with a
flag above the head or a key below the hand is taller than the figure itself).
Robot: the sky-blue visor of the head is the measuring stick (largest sky-blue blob in the upper half); teacher: the trimmed height (no prop sticks out above her head).
Writes assets/images/pose_metrics.json: per pose the source size, the visor width (robot) and `h_at_std` = the display height that gives the standard body size."""
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

P = Path(__file__).resolve().parents[1]
IMG = P / "assets/images"
ROBOT_STD_H, TEACHER_STD_H = 300, 540          # board heights of the reference poses (robot_wave, teacher_hold)
SKY = np.array([86, 203, 253])


def visor_width(path):
    im = Image.open(path).convert("RGBA")
    a = np.array(im)
    h, w = a.shape[:2]
    mask = (a[:, :, 3] > 200) & (np.abs(a[:, :, :3].astype(int) - SKY).sum(axis=2) < 90)
    s = 4
    m = mask[: h // 2 + h // 8 : 1, :][::s, ::s]            # head region only, downscaled
    seen = np.zeros_like(m, dtype=bool)
    best = (0, None)
    for y in range(m.shape[0]):
        for x in range(m.shape[1]):
            if m[y, x] and not seen[y, x]:
                q = deque([(y, x)]); seen[y, x] = True; pts = []
                while q:
                    cy, cx = q.popleft(); pts.append((cy, cx))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < m.shape[0] and 0 <= nx < m.shape[1] and m[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True; q.append((ny, nx))
                if len(pts) > best[0]:
                    best = (len(pts), pts)
    xs = [p[1] for p in best[1]]
    return (max(xs) - min(xs) + 1) * s


names = sorted(p.stem for p in IMG.glob("*.png"))
robot = [n for n in names if n.startswith("robot_")]
teacher = [n for n in names if n.startswith("teacher_")]
ref_r = Image.open(IMG / "robot_wave.png"); vref = visor_width(IMG / "robot_wave.png")
target_visor = vref * ROBOT_STD_H / ref_r.height          # visor width on the board of the reference robot pose
out = {"standard": {"robot_h": ROBOT_STD_H, "teacher_h": TEACHER_STD_H, "robot_visor_px_on_board": round(target_visor, 1)}, "poses": {}}
for n in robot:
    im = Image.open(IMG / f"{n}.png"); v = visor_width(IMG / f"{n}.png")
    out["poses"][n] = {"who": "robot", "src_w": im.width, "src_h": im.height, "visor_w": v, "h_at_std": round(im.height * target_visor / v)}
for n in teacher:
    im = Image.open(IMG / f"{n}.png")
    out["poses"][n] = {"who": "teacher", "src_w": im.width, "src_h": im.height, "h_at_std": TEACHER_STD_H}   # full-body trimmed figures: the display height is the body height whatever the source resolution
(IMG / "pose_metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for n, v in out["poses"].items():
    print(f"{n:26s} src {v['src_w']}x{v['src_h']}  visor {v.get('visor_w','-')}  h_at_std {v['h_at_std']}")
