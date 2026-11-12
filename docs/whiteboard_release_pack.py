"""Collect every lesson's finished bundle of ONE series into an ordered, distribution-ready folder (+ zip).

Run (OpenMontage root):  PYTHONPATH=. .venv/bin/python docs/whiteboard_release_pack.py [--series c|agent]     (default: the C series)
The folder is named after the series (docs/whiteboard/series.yaml: pack_dir, default "<name>_成品"); a series without a name refuses to build a pack (the user chooses the name).
Rebuilding a pack empties and recreates ITS folder only.
Needs per lesson: exports/video/output.mp4 (cover intro already added by whiteboard_prepend_cover.py), exports/video/subtitles.srt,
exports/thumbnails/cover.png, exports/metadata/{metadata.json,chapters.txt}.
Output: projects/C语言白板课_成品/第NN课_课名/{第NN课_课名.mp4, .srt, _封面.png, _简介.txt, _课后练习.txt（第 11 课起）, _随课勘误.txt（有 exports/metadata/errata.txt 才有）} + 目录.txt, and projects/C语言白板课_成品.zip.
File names avoid shell-sensitive characters such as '&'.
The agent series also gets ONE offline copy of the whole e-book site at the root of the pack (电子书（离线完整版）); the lesson folders hold no e-book copy (a refused build: the whole-site check is missing or red).
"""
import importlib.util, json, os, shutil, subprocess, sys, zipfile
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


OFFLINE = "电子书（离线完整版）"
SITE_DIR, SITE_CHECK = ROOT / "_ebook/site", ROOT / "_ebook/site-check.json"


def add_offline_site(dest, index):
    """The offline e-book as ONE copy of the whole site at the root of the pack.  (It used to be one copy inside every lesson's folder; each of those held all the videos made so far,
    so the pack grew with the square of the lesson count: 106, 177, 262, 274 MB for lessons 1 to 4.)  Refuses when the whole-site check is missing or red."""
    if not (SITE_DIR / "index.html").exists():
        print("no e-book site is built yet: the pack has no offline e-book")
        return
    chk = json.loads(SITE_CHECK.read_text(encoding="utf-8")) if SITE_CHECK.exists() else {}
    if not chk.get("pass"):
        raise SystemExit("projects/_ebook/site-check.json is missing or red: run docs/whiteboard/ebook/check_site.py until it passes, then build the pack")
    links = [p for p in SITE_DIR.rglob("*") if p.is_symlink()]
    if links:       # copytree would copy what a link points at, from anywhere on the disk
        raise SystemExit("the e-book site contains symbolic links (%s …): the offline copy takes only real files" % links[0])
    newest = max((p.stat().st_mtime for p in SITE_DIR.rglob("*") if p.is_file()), default=0)
    if SITE_CHECK.stat().st_mtime < newest:       # the site was rebuilt (or a file replaced) after the check ran: its green says nothing about this site
        raise SystemExit("projects/_ebook/site-check.json is older than the site: run docs/whiteboard/ebook/check_site.py on the current site until it passes, then build the pack")

    def link_or_copy(src, dst, **kw):          # big files (the videos) are hard-linked: one file on disk, however many folders name it
        if Path(src).stat().st_size > 5e6:
            try:
                return os.link(src, dst)
            except OSError:
                pass
        return shutil.copy2(src, dst)

    shutil.copytree(SITE_DIR, dest / OFFLINE, copy_function=link_or_copy)
    index += ["", f"{OFFLINE}：用浏览器打开 {OFFLINE}/index.html（不用联网）；含所有已做完的章节和各章视频（原画质原件）；每出一课重建一次；整个成品包里只有这一份，各课文件夹里没有电子书副本。"]
    print(OFFLINE, "added once at the root of the pack")


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
        if (E / "metadata/errata.txt").exists():   # optional: a note for students about something in the video that differs from the delivered files; lessons without the file are packed exactly as before
            shutil.copy(E / "metadata/errata.txt", d / f"{base}_随课勘误.txt")
        if (E / "metadata/exercises.txt").exists():   # from lesson 11 on: homework (read, modify, find the bug, write), answers from real runs
            shutil.copy(E / "metadata/exercises.txt", d / f"{base}_课后练习.txt")
        dur = duration(d / f"{base}.mp4")
        index.append(f"第{no:02d}课 {name}  时长 {int(dur // 60)}分{int(dur % 60):02d}秒  文件夹：{base}")
        print(base, f"{dur:.1f}s")
    if series == "agent":
        add_offline_site(DEST, index)
    (DEST / "目录.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
        for f in sorted(DEST.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(ROOT))
    z = zipfile.ZipFile(zp); print("zip", zp, "test:", z.testzip(), "files:", len(z.namelist()), f"{zp.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--series") + 1] if "--series" in sys.argv else "c")
