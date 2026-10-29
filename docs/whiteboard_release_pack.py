"""Collect every lesson's finished bundle of ONE series into an ordered, distribution-ready folder (+ zip).

Run (OpenMontage root):  PYTHONPATH=. .venv/bin/python docs/whiteboard_release_pack.py [--series c|agent]     (default: the C series)
The folder is named after the series (docs/whiteboard/series.yaml: pack_dir, default "<name>_成品"); a series without a name refuses to build a pack (the user chooses the name).
Rebuilding a pack empties and recreates ITS folder only.
Needs per lesson: exports/video/output.mp4 (cover intro already added by whiteboard_prepend_cover.py), exports/video/subtitles.srt,
exports/thumbnails/cover.png, exports/metadata/{metadata.json,chapters.txt}.
Output: projects/C语言白板课_成品/第NN课_课名/{第NN课_课名.mp4, .srt, _封面.png, _简介.txt, _课后练习.txt（第 11 课起）} + 目录.txt, and projects/C语言白板课_成品.zip.
File names avoid shell-sensitive characters such as '&'.
"""
import importlib.util, json, shutil, subprocess, sys, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whiteboard_lessons import series_config, series_of  # noqa: E402

spec = importlib.util.spec_from_file_location("covers", Path(__file__).with_name("whiteboard_cover_maker.py"))
covers = importlib.util.module_from_spec(spec); spec.loader.exec_module(covers)
NAME_OVERRIDE = {5: "scanf与取地址符"}        # the on-board title contains '&'
ROOT = Path("projects")


def pack_paths(series):
    """(series config, folder, zip) of a series' release pack; refuses while the series has no name."""
    cfg = series_config(series)
    if not cfg["pack_dir"]:
        raise SystemExit(f"the {series} series has no name yet: set `name:` in docs/whiteboard/series.yaml (the user chooses it); the release pack folder is named after it")
    return cfg, ROOT / cfg["pack_dir"], ROOT / f"{cfg['pack_dir']}.zip"


def duration(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)


def main(series="c"):
    cfg, DEST, zp = pack_paths(series)
    shutil.rmtree(DEST, ignore_errors=True); DEST.mkdir()
    index = [f"{cfg['name']} 成品清单（按课程顺序）", "每个文件夹含：视频（开头 2 秒封面）、字幕 SRT（时间已对应带封面的视频）、封面图、简介（标题、简介、章节、标签）；" + ("第 11 课起另含课后练习。" if series == "c" else "有课后练习的另含课后练习。"), ""]
    for proj, no, title, *_ in covers.LESSONS:
        if series_of(proj) != series:
            continue
        E = ROOT / proj / "exports"
        if not (E / "video/output.mp4").exists():
            print("skip (no bundle yet):", proj); continue
        name = (NAME_OVERRIDE.get(no, title) if series == "c" else title); base = f"第{no:02d}课_{name}"; d = DEST / base; d.mkdir()
        shutil.copy(E / "video/output.mp4", d / f"{base}.mp4"); shutil.copy(E / "video/subtitles.srt", d / f"{base}.srt"); shutil.copy(E / "thumbnails/cover.png", d / f"{base}_封面.png")
        m = json.loads((E / "metadata/metadata.json").read_text(encoding="utf-8"))
        ch = (E / "metadata/chapters.txt").read_text(encoding="utf-8").strip()
        desc = m["description"].rstrip()
        if not desc.endswith("章节时间轴："):
            desc += "\n\n章节时间轴："
        (d / f"{base}_简介.txt").write_text(f"{m['title']}\n\n{desc}\n{ch}\n\n标签：{'、'.join(m['tags'])}\n{' '.join(m['hashtags'])}\n", encoding="utf-8")
        if (E / "metadata/exercises.txt").exists():   # from lesson 11 on: homework (read, modify, find the bug, write), answers from real runs
            shutil.copy(E / "metadata/exercises.txt", d / f"{base}_课后练习.txt")
        dur = duration(d / f"{base}.mp4")
        index.append(f"第{no:02d}课 {name}  时长 {int(dur // 60)}分{int(dur % 60):02d}秒  文件夹：{base}")
        print(base, f"{dur:.1f}s")
    (DEST / "目录.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
        for f in sorted(DEST.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(ROOT))
    z = zipfile.ZipFile(zp); print("zip", zp, "test:", z.testzip(), "files:", len(z.namelist()), f"{zp.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--series") + 1] if "--series" in sys.argv else "c")
