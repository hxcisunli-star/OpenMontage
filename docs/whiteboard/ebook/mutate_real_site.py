import json, os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]          # the repository root (this file lives in docs/whiteboard/ebook/)
SITE = ROOT / "projects/_ebook/site"
CHK = Path(__file__).resolve().parent / "check_site.py"
WORK = Path(sys.argv[1]); shutil.rmtree(WORK, ignore_errors=True); WORK.mkdir(parents=True)
CH = "books/b2-llm/S2-U01.html"


def swap_video(site):
    """the chapter plays a different file than its lesson's original (the new online-quality guard)"""
    p = site / "media/S2-U04/output.mp4"; p.unlink()
    shutil.copyfile(site / "media/S2-U03/output.mp4", p)


def first_placeholder(site):
    """The first chapter page that is still an honest placeholder (it moves on as lessons get their text: S2-U02 was one when this file was written, S2-U05 is the next)."""
    for p in sorted((site / "books/b2-llm").glob("S2-U*.html")):
        if "正文还在制作中" in p.read_text(encoding="utf-8"):
            return p.relative_to(site).as_posix()
    raise SkipCase("every chapter of book 2 has its text: no placeholder page to mutate")


class SkipCase(Exception):
    """The real checkout does not contain the feature this mutation targets."""

def edit(site, rel, fn):
    p = site / rel
    t = p.read_text(encoding="utf-8"); n = fn(t)
    assert n != t, f"mutation changed nothing in {rel}"
    p.unlink(); p.write_text(n, encoding="utf-8")        # unlink first: the copy is made of hard links

def swap_image(site, rel, w, h):
    """replace a picture by a small grey one (unlink first: the copy is made of hard links)"""
    p = site / rel; p.unlink()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=gray:s={w}x{h}", "-frames:v", "1", str(p)], check=True)


def sub1(old, new, count=1):
    def f(t):
        assert old in t, f"pattern not in page: {old[:50]}"
        return t.replace(old, new, count)
    return f

def re1(pat, repl, flags=0):
    def f(t):
        n, k = re.subn(pat, repl, t, count=1, flags=flags); assert k, f"regex not in page: {pat[:50]}"; return n
    return f


def mutate_vendor_byte(site):
    vendor = site / "assets/vendor"
    manifest = vendor / "MANIFEST.sha256"
    if not vendor.is_dir() or not manifest.is_file():
        raise SkipCase("真站点没有 assets/vendor/ 或 MANIFEST.sha256")
    files = [p for p in vendor.rglob("*") if p.is_file() and p.name not in {"MANIFEST.sha256", "VERSIONS.json"}]
    if not files:
        raise SkipCase("vendor 清单没有可变更的文件")
    path = files[0]
    data = path.read_bytes()
    path.unlink()
    path.write_bytes((data[:1] + bytes([data[1] ^ 1]) + data[2:]) if len(data) > 1 else data + b"x")


def remove_lab_config(site):
    path = site / "assets/lab-config.json"
    if not path.is_file():
        raise SkipCase("真站点没有 assets/lab-config.json")
    path.unlink()


def remove_lab_script(site):
    pages = list(site.rglob("*.html"))
    page = next((p for p in pages if "section class=\"lab\"" in p.read_text(encoding="utf-8")), None)
    if page is None:
        raise SkipCase("真站点没有含练习的章页")
    text = page.read_text(encoding="utf-8")
    changed = re.sub(r'<script\b[^>]*\bsrc=["\'][^"\']*lab\.js[^"\']*["\'][^>]*>\s*</script>', "", text, count=1, flags=re.I)
    if changed == text:
        raise SkipCase("含练习的章页没有 lab.js 脚本标签")
    page.unlink()
    page.write_text(changed, encoding="utf-8")


def clone_site(src, dst):
    """Use hard links when possible, with a copy fallback across filesystems."""
    try:
        subprocess.run(["cp", "-al", str(src), str(dst)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)

CASES = [
 ("vendor-pinned",   mutate_vendor_byte),
 ("labs",            remove_lab_config),
 ("labs",            remove_lab_script),
 ("ch-shice",      lambda s: edit(s, CH, re1(r'(<figcaption class="rec".*?)(\d+) 遍', lambda m: m.group(1)+f"{int(m.group(2))+7} 遍", re.S))),
 ("ch-exercises",  lambda s: edit(s, CH, sub1('<details class="answer"', '<details open class="answer"'))),
 ("ch-exercises",  lambda s: edit(s, CH, re1(r'(<div class="q"[^>]*>)', r'\1北京。'))),
 ("ch-coverage",   lambda s: edit(s, CH, re1(r'(<details id="coverage".*?)(<li[^>]*>.*?p5.*?</li>)', r'\1', re.S))),
 ("ch-frames",     lambda s: edit(s, CH, re1(r'(<q class="narr"[^>]*>)[^<]{4}', r'\1这句旁白不存在'))),
 ("books-complete",lambda s: edit(s, "books/b2-llm/index.html", re1(r'<li[^>]*data-unit="S2-U10".*?</li>', '', re.S))),
 ("ch-sources",    lambda s: edit(s, CH, sub1("适用范围：", "适用范围:"))),
 ("no-external-load", lambda s: edit(s, "index.html", sub1("</head>", '<script src="https://cdn.example.org/x.js"></script></head>'))),
 ("ch-video",      lambda s: edit(s, CH, re1(r'data-duration="[\d.]+"', 'data-duration="99.0"'))),
 ("ch-video-stream", swap_video),
 ("size-limits",   lambda s: edit(s, CH, sub1("</body>", "<!--" + "x" * 3_200_000 + "--></body>"))),
 ("chapter-pages", lambda s: edit(s, first_placeholder(s), sub1("正文还在制作中", "正文即将上线"))),
 ("placeholders-honest", lambda s: edit(s, first_placeholder(s), re1(r'<a class="pre"[^>]*>.*?</a>', '', re.S))),
 ("relative-links-resolve", lambda s: edit(s, CH, re1(r'href="\.\./\.\./assets/book\.css"', 'href="../../assets/missing.css"'))),
 ("search-index",  lambda s: edit(s, "assets/search-index.js", re1(r'\{"id":"S2-U03"[^}]*\},?', ''))),
 ("no-secret-or-path", lambda s: edit(s, CH, sub1("</body>", "<p>/home/someone/key</p></body>"))),
 ("ch-evidence",   lambda s: edit(s, CH, re1(r'(<details id="evidence".*?)H3_ds', r'\1H3_xx', re.S))),
 ("ch-nav",        lambda s: edit(s, CH, sub1('<a href="S2-U02.html">下一章', '<a href="S2-U09.html">下一章'))),
 ("ch-thinks",     lambda s: edit(s, CH, sub1('<details class="think"', '<details open class="think"'))),
 ("shelf-covers",  lambda s: edit(s, "index.html", re1(r'<img class="cover-art"[^>]*>', ''))),
 ("shelf-covers",  lambda s: swap_image(s, "assets/covers/b3-tools-eval.jpg", 300, 400)),
]
res = []
ONLY = set(sys.argv[2:])
for i, (rule, mut) in enumerate(CASES):
    if ONLY and rule not in ONLY: continue
    site = WORK / f"c{i}"
    clone_site(SITE, site)
    try:
        mut(site)
    except SkipCase as e:
        res.append((rule, "SKIPPED", str(e))); shutil.rmtree(site); continue
    except AssertionError as e:
        res.append((rule, "MUTATION-NOT-APPLIED", str(e)[:80])); shutil.rmtree(site); continue
    rep = WORK / f"r{i}.json"
    subprocess.run([sys.executable, str(CHK), "--site", str(site), "--repo", str(ROOT), "--report", str(rep)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    failed = json.loads(rep.read_text())["failed"]
    res.append((rule, "CAUGHT" if rule in failed else "MISSED", ",".join(failed)))
    shutil.rmtree(site)
for r in res: print(f"{r[1]:22} {r[0]:24} failed={r[2][:70]}")
print("missed:", sum(1 for r in res if r[1] == "MISSED"), "of", len(res))
