#!/usr/bin/env python3
"""Static checker for the multi-book offline ebook site.

The checker intentionally uses only the Python standard library.  It is kept
as a small DOM walker rather than depending on a third party HTML or YAML
package, because the site is meant to work when copied to an offline machine.
"""

from html.parser import HTMLParser
import ast
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from urllib.parse import unquote


def sha256_file(path, chunk=1 << 20):
    """sha256 of a (possibly 90 MB) file without reading it all into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}
TEXT_EXTS = {".html", ".css", ".js", ".txt", ".json"}


class Element:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag.lower()
        self.attrs = {str(k).lower(): (v or "") for k, v in (attrs or [])}
        self.parent = parent
        self.children = []


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("#document")
        self.stack = [self.root]
        self.errors = []

    def handle_starttag(self, tag, attrs):
        el = Element(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(el)
        if el.tag not in VOID_TAGS:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Element(tag, attrs, self.stack[-1]))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in VOID_TAGS:
            self.errors.append("void tag </%s> should not be closed" % tag)
            return
        if len(self.stack) == 1:
            self.errors.append("unmatched </%s>" % tag)
            return
        if self.stack[-1].tag == tag:
            self.stack.pop()
            return
        positions = [i for i in range(1, len(self.stack)) if self.stack[i].tag == tag]
        if not positions:
            self.errors.append("unmatched </%s>" % tag)
            return
        self.errors.append("misnested </%s>" % tag)
        while len(self.stack) - 1 >= positions[-1]:
            self.stack.pop()

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(data)

    def finish(self):
        if len(self.stack) > 1:
            self.errors.append("unclosed: " + ", ".join(x.tag for x in self.stack[1:]))


def read_text(path):
    try:
        raw = pathlib.Path(path).read_bytes()
        if b"\0" in raw[:4096]:
            return ""
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def load_json(path):
    try:
        with pathlib.Path(path).open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def parse_html(path):
    parser = PageParser()
    try:
        parser.feed(read_text(path))
        parser.close()
        parser.finish()
    except Exception as exc:
        parser.errors.append("parser error: %s" % exc)
    return parser


def descendants(node, tag=None, cls=None):
    found = []
    for child in node.children:
        if isinstance(child, Element):
            if (tag is None or child.tag == tag) and (cls is None or has_class(child, cls)):
                found.append(child)
            found.extend(descendants(child, tag, cls))
    return found


def first_descendant(node, tag=None, cls=None):
    items = descendants(node, tag, cls)
    return items[0] if items else None


def has_class(node, cls):
    return cls in node.attrs.get("class", "").split()


def text_of(node):
    out = []
    for child in node.children:
        out.append(text_of(child) if isinstance(child, Element) else child)
    return "".join(out)


def norm_text(value):
    return re.sub(r"\s+", "", value or "")


def norm_quote(value):
    return re.sub(r"[\s\W_]+", "", value or "", flags=re.UNICODE)


def rel_value(value):
    return " ".join((value or "").split()).lower()


def attr_external(value):
    value = (value or "").strip().lower()
    return value.startswith(("http://", "https://", "//"))


def is_protocol(value):
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", (value or "").strip()))


def source_link(node):
    return has_class(node, "src-link")


def css_urls(value):
    for match in re.finditer(r"url\s*\(\s*(['\"]?)(.*?)\1\s*\)", value or "", re.I | re.S):
        yield match.group(2).strip()


def fmt_path(path, root):
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def image_size(path):
    """(width, height) from the file header of a PNG or JPEG, else None"""
    try:
        data = pathlib.Path(path).read_bytes()
    except OSError:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data.startswith(b"\xff\xd8"):
        pos = 2
        sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
               0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while pos + 9 < len(data):
            if data[pos] != 0xFF:
                pos += 1
                continue
            while pos < len(data) and data[pos] == 0xFF:
                pos += 1
            if pos >= len(data):
                break
            marker = data[pos]
            pos += 1
            if marker in (0xD8, 0xD9):
                continue
            if pos + 2 > len(data):
                break
            length = int.from_bytes(data[pos:pos + 2], "big")
            if length < 2 or pos + length > len(data):
                break
            if marker in sof and length >= 7:
                return int.from_bytes(data[pos + 5:pos + 7], "big"), int.from_bytes(data[pos + 3:pos + 5], "big")
            pos += length
    return None


def image_width(path):
    size = image_size(path)
    return size[0] if size else None


def norm_id(value):
    """Normalize S02-U01 and S2-U01 spellings for source-file lookup."""
    value = str(value or "").strip()
    m = re.match(r"^([A-Za-z]+)0*(\d+)-U0*(\d+)$", value)
    if m:
        return "%s%s-U%02d" % (m.group(1).upper(), int(m.group(2)), int(m.group(3)))
    return value


def parse_scalar(value):
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        try:
            return list(ast.literal_eval(value))
        except Exception:
            return [x.strip().strip("'\"") for x in value[1:-1].split(",") if x.strip()]
    if (value.startswith("\"") and value.endswith("\"")) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def _yaml_uncomment(line):
    quote = None
    for i, ch in enumerate(line):
        if ch in "'\"":
            quote = None if quote == ch else ch if quote is None else quote
        elif ch == "#" and quote is None and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line.rstrip()


def parse_books_yaml(path_or_text):
    """Parse the deliberately small books.yaml dialect used by this project.

    Accepts either a path or YAML text.  It handles mappings, a ``books`` list,
    inline lists, and the equivalent indented list form for ``stages``.
    """
    if isinstance(path_or_text, (str, pathlib.Path)):
        try:
            candidate = pathlib.Path(path_or_text)
            raw = candidate.read_text(encoding="utf-8") if candidate.is_file() else str(path_or_text)
        except (OSError, ValueError):
            raw = str(path_or_text)
    else:
        raw = str(path_or_text)
    result = {"series": {}, "books": []}
    current = None
    in_books = False
    stages_block = False
    stage_indent = None
    for original in raw.splitlines():
        line = _yaml_uncomment(original)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if stripped == "series:":
            in_books = False
            stages_block = False
            continue
        if stripped == "books:":
            in_books = True
            stages_block = False
            continue
        if in_books and stages_block and stripped.startswith("-") and indent > (stage_indent or -1):
            current.setdefault("stages", []).append(parse_scalar(stripped[1:]))
            continue
        if in_books and stripped.startswith("-"):
            payload = stripped[1:].strip()
            current = {}
            result["books"].append(current)
            stages_block = False
            if payload and ":" in payload:
                key, val = payload.split(":", 1)
                current[key.strip()] = parse_scalar(val)
            continue
        if ":" not in stripped:
            continue
        key, val = stripped.split(":", 1)
        key, val = key.strip(), val.strip()
        if in_books and current is not None:
            if key == "stages" and not val:
                current["stages"] = []
                stages_block, stage_indent = True, indent
            else:
                current[key] = parse_scalar(val)
                stages_block = False
        elif not in_books:
            # The only series value needed by the checker is ``name``.
            result["series"][key] = parse_scalar(val)
    return result


def parse_exercises(path):
    """Return {number: (question_lines, answer_lines)} from exercises.txt."""
    try:
        lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    numerals = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
                "七": 7, "八": 8, "九": 9, "十": 10}
    starts = []
    for i, line in enumerate(lines):
        m = re.match(r"^\s*练习([一二三四五六七八九十]+|\d+)【", line)
        if m:
            token = m.group(1)
            number = int(token) if token.isdigit() else numerals.get(token)
            if number is not None:
                starts.append((i, number))
    result = {}
    for pos, (start, number) in enumerate(starts):
        stop = starts[pos + 1][0] if pos + 1 < len(starts) else next((j for j in range(start, len(lines)) if lines[j].strip().startswith("你的学习记录")), len(lines))
        block = lines[start + 1:stop]
        answer_at = next((i for i, line in enumerate(block) if line.strip().startswith("答案")), None)
        if answer_at is None:
            result[number] = ([x for x in block if x.strip()], [])
        else:
            result[number] = ([x for x in block[:answer_at] if x.strip()], [x for x in block[answer_at + 1:] if x.strip()])
    return result


class SiteChecker:
    CHECK_IDS = [
        "site-files", "books-complete", "shelf-covers", "vendor-pinned", "labs", "chapter-pages", "placeholders-honest",
        "prereq-links", "search-index", "no-external-load", "no-claude-runtime",
        "no-secret-or-path", "no-experiment-labels", "relative-links-resolve",
        "page-basics", "size-limits", "ch-header", "ch-video", "ch-video-stream", "ch-frames",
        "ch-sections", "ch-shice", "ch-sources", "ch-metaphors", "ch-thinks",
        "ch-exercises", "ch-evidence", "ch-coverage", "ch-extras", "ch-nav",
    ]

    def __init__(self, site, repo, no_video_probe=False):
        self.site = pathlib.Path(site).resolve()
        self.repo = pathlib.Path(repo).resolve()
        self.no_video_probe = no_video_probe
        self.checks = []
        self.pages = {}
        if self.site.is_dir():
            for p in self.site.rglob("*.html"):
                self.pages[p.resolve()] = parse_html(p)
        self.outline = load_json(self.repo / "projects/_ebook/outline.json") or {}
        self.yaml = parse_books_yaml(self.repo / "projects/_ebook/books.yaml") if (self.repo / "projects/_ebook/books.yaml").is_file() else {"series": {}, "books": []}
        self.stage_map = {str(x.get("id")): x for x in self.outline.get("stages", []) if isinstance(x, dict)}
        self.units_by_id = {}
        for stage in self.outline.get("stages", []):
            for unit in stage.get("units", []) if isinstance(stage, dict) else []:
                if isinstance(unit, dict) and unit.get("id"):
                    self.units_by_id[str(unit["id"])] = unit
        self.book_units = {}
        for book in self.yaml.get("books", []):
            units = []
            for stage_id in book.get("stages", []) if isinstance(book, dict) else []:
                stage = self.stage_map.get(str(stage_id), {})
                units.extend([str(u.get("id")) for u in stage.get("units", []) if isinstance(u, dict) and u.get("id")])
            self.book_units[str(book.get("id", ""))] = units
        self.all_units = [u for units in self.book_units.values() for u in units]
        self.unit_book = {}
        for bid, units in self.book_units.items():
            for n, uid in enumerate(units, 1):
                self.unit_book[uid] = (bid, n)
        self.sources = {}
        chapter_dir = self.repo / "projects/_ebook/chapters"
        if chapter_dir.is_dir():
            for p in chapter_dir.glob("*.json"):
                data = load_json(p)
                if isinstance(data, dict) and data.get("id"):
                    self.sources[str(data["id"])] = (p, data)
                else:
                    self.sources[norm_id(p.stem)] = (p, data or {})
        # Real data keeps validation assets in the project named in the source JSON.
        self.records = load_json(self.repo / "projects/agent-what-is-llm-cn/validation/records.json") or {}
        self.claims = load_json(self.repo / "projects/agent-what-is-llm-cn/validation/claims_used.json") or {}
        self.script = load_json(self.repo / "projects/agent-what-is-llm-cn/artifacts/script.json") or {}
        exercise_path = self.repo / "projects/agent-what-is-llm-cn/exports/metadata/exercises.txt"
        if not exercise_path.is_file():
            exercise_path = self.repo / "exports/metadata/exercises.txt"
        self.exercise_data = parse_exercises(exercise_path)

    def add(self, rule_id, ok, detail):
        self.checks.append({"id": rule_id, "ok": bool(ok), "detail": str(detail)})

    def run(self):
        for name in self.CHECK_IDS:
            method = getattr(self, "check_" + name.replace("-", "_"), None)
            if method:
                try:
                    method()
                except Exception as exc:
                    self.add(name, False, "检查异常：%s" % exc)
        # Preserve a fixed one-entry-per-rule report even if future code adds a method.
        seen = {x["id"] for x in self.checks}
        for rule_id in self.CHECK_IDS:
            if rule_id not in seen:
                self.add(rule_id, False, "未执行")
        failed = [x["id"] for x in self.checks if not x["ok"]]
        return {"pass": not failed, "checks": self.checks, "failed": failed}

    def iter_files(self):
        return [p for p in self.site.rglob("*") if p.is_file()] if self.site.is_dir() else []

    def is_vendor_path(self, path):
        """Whether *path* is below the generated vendor directory."""
        try:
            pathlib.Path(path).resolve().relative_to((self.site / "assets/vendor").resolve())
            return True
        except ValueError:
            return False

    def iter_text_files(self):
        """Text files scanned by content rules; vendored code is third-party."""
        return [p for p in self.iter_files()
                if p.suffix.lower() in TEXT_EXTS and not self.is_vendor_path(p)]

    def relative_target(self, value, current):
        """Return (target, error) for a relative site URL."""
        value = unquote((value or "").strip())
        if not value:
            return None, None
        if value.startswith("/") or value.lower().startswith("file:"):
            return None, "绝对或 file 路径：%s" % value
        if is_protocol(value) or value.startswith("//"):
            return None, None
        clean = value.split("#", 1)[0].split("?", 1)[0]
        if not clean:
            return current, None
        target = (current.parent / pathlib.PurePosixPath(clean.replace("\\", "/"))).resolve()
        try:
            target.relative_to(self.site)
        except ValueError:
            return target, "越出站点根：%s" % value
        if not target.is_file():
            return target, "目标不存在：%s" % value
        return target, None

    def canonical_page(self, value, current):
        target, error = self.relative_target(value, current)
        return target if not error else None

    def page_for_unit(self, unit_id):
        pair = self.unit_book.get(unit_id)
        return self.site / "books" / pair[0] / (unit_id + ".html") if pair else None

    def parser_for(self, path):
        return self.pages.get(path.resolve()) or parse_html(path)

    def check_site_files(self):
        required = ["index.html", "robots.txt", "assets/book.css", "assets/book.js", "assets/search-index.js"]
        problems = [x for x in required if not (self.site / x).is_file()]
        if not (self.site / "robots.txt").is_file() or "Disallow: /" not in read_text(self.site / "robots.txt"):
            problems.append("robots.txt 缺少 Disallow: /")
        fonts = self.site / "assets/fonts"
        license_path = fonts / "FONT-LICENSE.txt"
        if not license_path.is_file() or "SIL Open Font License" not in read_text(license_path):
            problems.append("assets/fonts/FONT-LICENSE.txt 缺少 SIL Open Font License")
        if not fonts.is_dir() or not any(p.suffix.lower() == ".ttf" for p in fonts.iterdir() if p.is_file()):
            problems.append("assets/fonts/ 缺少 .ttf")
        for name in ("teacher.png", "robot.png"):
            if not (self.site / "assets/img" / name).is_file():
                problems.append("assets/img/%s 不存在" % name)
        for name in ("books", "assets", "media", "downloads"):
            if not (self.site / name).is_dir():
                problems.append("%s/ 不存在" % name)
        self.add("site-files", not problems, "通过" if not problems else "；".join(problems[:12]))

    def check_books_complete(self):
        problems = []
        expected_all = []
        for book in self.yaml.get("books", []):
            bid = str(book.get("id", ""))
            for stage in book.get("stages", []) if isinstance(book, dict) else []:
                if str(stage) not in self.stage_map:
                    problems.append("books.yaml %s 引用不存在阶段 %s" % (bid, stage))
            expected_all.extend(self.book_units.get(bid, []))
            index = self.site / "books" / bid / "index.html"
            if not index.is_file():
                problems.append("缺少册目录 %s" % fmt_path(index, self.site))
                continue
            parser = self.parser_for(index)
            listed = [e.attrs.get("data-unit", "") for e in descendants(parser.root, "li") if e.attrs.get("data-unit")]
            if listed != self.book_units.get(bid, []):
                problems.append("%s 目录单元顺序不匹配" % fmt_path(index, self.site))
            eyebrow = first_descendant(parser.root, "div", "eyebrow")
            if not eyebrow or not re.search(r"共\s*%d\s*章" % len(self.book_units.get(bid, [])), text_of(eyebrow)):
                problems.append("%s 的共 N 章不匹配" % fmt_path(index, self.site))
        counts = {}
        for unit in expected_all:
            counts[unit] = counts.get(unit, 0) + 1
        duplicated = [u for u, n in counts.items() if n != 1]
        if duplicated:
            problems.append("单元未恰好出现一次：" + ",".join(duplicated[:12]))
        if len(expected_all) != int(self.outline.get("unit_count", -1)):
            problems.append("单元总数 %d 不等于 outline unit_count %s" % (len(expected_all), self.outline.get("unit_count")))
        outline_units = [str(u.get("id")) for stage in self.outline.get("stages", []) if isinstance(stage, dict)
                         for u in stage.get("units", []) if isinstance(u, dict) and u.get("id")]
        if set(expected_all) != set(outline_units):
            problems.append("books.yaml 单元集合与 outline 不一致")
        shelf = self.parser_for(self.site / "index.html")
        cards = descendants(shelf.root, "a", "book-card")
        if len(cards) != len(self.yaml.get("books", [])):
            problems.append("书架 book-card 数量不匹配")
        for card in cards:
            href = card.attrs.get("href", "")
            bid = pathlib.PurePosixPath(href.split("#", 1)[0]).parent.name if href else ""
            units = [x for x in card.attrs.get("data-units", "").split(",") if x]
            if bid not in self.book_units or units != self.book_units[bid]:
                problems.append("书架卡片 %s 的 data-units 不匹配" % href)
        self.add("books-complete", not problems, "通过" if not problems else "；".join(problems[:15]))

    def directory_unit_element(self, bid, unit):
        path = self.site / "books" / bid / "index.html"
        parser = self.parser_for(path)
        return next((x for x in descendants(parser.root, "li") if x.attrs.get("data-unit") == unit), None)

    def check_chapter_pages(self):
        problems = []
        outline_ids = {str(x) for x in self.all_units}
        for source_id in self.sources:
            if source_id not in outline_ids and norm_id(source_id) not in {norm_id(x) for x in outline_ids}:
                problems.append("源文件对应未知单元 %s" % source_id)
        for unit in self.all_units:
            pair = self.unit_book.get(unit)
            if not pair:
                continue
            bid = pair[0]
            page = self.page_for_unit(unit)
            if not page or not page.is_file():
                problems.append("缺少章页 %s" % fmt_path(page or self.site, self.site))
                continue
            parser = self.parser_for(page)
            source = self.source_for(unit)
            li = self.directory_unit_element(bid, unit)
            chip = first_descendant(li, "span", "chip-st") if li else None
            if source:
                if not descendants(parser.root, "main") or not any(e.attrs.get("data-unit") == unit for e in descendants(parser.root, "main")):
                    problems.append("%s 缺少 main[data-unit]" % fmt_path(page, self.site))
                if not chip or not has_class(chip, "on") or norm_text(text_of(chip)) != "有正文" or "制作中" in text_of(chip):
                    problems.append("%s 目录正文状态不正确" % unit)
            else:
                warn = first_descendant(parser.root, "div", "callout")
                if not warn or not has_class(warn, "warn") or "正文还在制作中" not in text_of(warn):
                    problems.append("%s 占位页缺少正文还在制作中" % fmt_path(page, self.site))
                if descendants(parser.root, "section", "sec") or descendants(parser.root, "video"):
                    problems.append("%s 占位页含正文 section 或 video" % fmt_path(page, self.site))
                if not chip or not has_class(chip, "off"):
                    problems.append("%s 目录占位状态不正确" % unit)
        self.add("chapter-pages", not problems, "通过" if not problems else "；".join(problems[:15]))

    def source_for(self, unit):
        if unit in self.sources:
            return self.sources[unit]
        n = norm_id(unit)
        for key, pair in self.sources.items():
            if norm_id(key) == n:
                return pair
        return None

    def check_placeholders_honest(self):
        problems = []
        for unit in self.all_units:
            if self.source_for(unit):
                continue
            page = self.page_for_unit(unit)
            if not page or not page.is_file():
                continue
            parser = self.parser_for(page)
            body = norm_text(text_of(parser.root)).replace("`", "")
            info = self.units_by_id.get(unit, {})
            goal = norm_text(str(info.get("goal", ""))).replace("`", "")
            if goal and goal not in body:
                problems.append("%s 占位页缺少大纲 goal" % fmt_path(page, self.site))
            for prereq in info.get("prereq", []) or []:
                if prereq not in self.unit_book:
                    continue
                expected = self.page_for_unit(prereq).resolve()
                links = [a for a in descendants(parser.root, "a", "pre")]
                targets = {self.canonical_page(a.attrs.get("href", ""), page) for a in links}
                if expected not in targets:
                    problems.append("%s 缺少先修链接 %s" % (unit, prereq))
        self.add("placeholders-honest", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_prereq_links(self):
        problems = []
        for path, parser in self.pages.items():
            for link in descendants(parser.root, "a", "pre"):
                href = link.attrs.get("href", "")
                if href.strip().startswith("#"):
                    problems.append("%s a.pre 不得是同页锚点" % fmt_path(path, self.site))
                    continue
                target, error = self.relative_target(href, path)
                if error or target is None or target.suffix.lower() != ".html":
                    problems.append("%s a.pre %s" % (fmt_path(path, self.site), error or "不是页面"))
        self.add("prereq-links", not problems, "通过" if not problems else "；".join(problems[:12]))

    def check_shelf_covers(self):
        """each book on the shelf is a picture of a book: one cover image in assets/covers/ (real file, at least 600 px wide, 3:4, with a text description),
        the title is real text (not painted into the picture), the book's catalog page shows the same cover"""
        problems = []
        shelf = self.site / "index.html"
        if not shelf.is_file():
            self.add("shelf-covers", False, "没有书架页 index.html")
            return
        root = self.parser_for(shelf).root
        cards = descendants(root, "a", "book-card")
        covers_dir = (self.site / "assets" / "covers").resolve()
        for card in cards:
            href = card.attrs.get("href", "")
            label = href or "(没有 href)"
            imgs = descendants(card, "img")
            if len(imgs) != 1:
                problems.append("%s 书里应恰有 1 张封面图，现在 %d 张" % (label, len(imgs)))
                continue
            img = imgs[0]
            src = img.attrs.get("src", "")
            target = (shelf.parent / src).resolve() if src and not is_protocol(src) and not src.startswith("/") else None
            if target is None or covers_dir not in target.parents:
                problems.append("%s 封面图不在 assets/covers/：%s" % (label, src))
            elif not target.is_file():
                problems.append("%s 封面文件不存在：%s" % (label, src))
            else:
                width = image_width(target)
                if width is None or width < 600:
                    problems.append("%s 封面宽度不足 600：%s" % (label, width))
                else:
                    size = image_size(target)
                    if size and abs(size[0] / size[1] - 0.75) > 0.02:
                        problems.append("%s 封面不是 3:4：%dx%d" % (label, size[0], size[1]))
            if len(img.attrs.get("alt", "").strip()) < 6:
                problems.append("%s 封面图缺少文字说明（alt）" % label)
            titles = [text_of(x).strip() for x in descendants(card, None, "bk-t")]
            if len(titles) != 1 or not titles[0]:
                problems.append("%s 册名应是页面里的真文字（.bk-t）" % label)
            catalog = (shelf.parent / href).resolve() if href and not href.startswith(("http", "/")) else None
            if catalog is not None and catalog.is_file() and src:
                same = [x for x in descendants(self.parser_for(catalog).root, "img", "cover-art") if x.attrs.get("src", "").endswith(src)]
                if not same:
                    problems.append("%s 册目录页没有放同一张封面" % label)
        if not cards:
            problems.append("书架上没有 a.book-card")
        self.add("shelf-covers", not problems, "通过" if not problems else "；".join(problems[:12]))

    def check_vendor_pinned(self):
        """Validate the generated vendor tree against its pinned manifest."""
        vendor = self.site / "assets/vendor"
        has_labs = any(descendants(parser.root, "section", "lab")
                       for parser in self.pages.values())
        if not vendor.is_dir():
            self.add("vendor-pinned", not has_labs,
                     "无练习，跳过" if not has_labs else "含练习但缺少 assets/vendor/")
            return

        problems = []
        manifest = vendor / "MANIFEST.sha256"
        entries = []
        listed = set()
        if not manifest.is_file():
            problems.append("缺少 MANIFEST.sha256")
        else:
            for number, line in enumerate(read_text(manifest).splitlines(), 1):
                if not line.strip():
                    continue
                if "  " not in line:
                    problems.append("MANIFEST 第 %d 行格式错误" % number)
                    continue
                digest, rel = line.split("  ", 1)
                digest, rel = digest.strip().lower(), rel.strip()
                rel_path = pathlib.PurePosixPath(rel)
                if (not re.fullmatch(r"[0-9a-f]{64}", digest) or not rel or
                        rel_path.is_absolute() or ".." in rel_path.parts or
                        str(rel_path) != rel or rel in listed):
                    problems.append("MANIFEST 第 %d 行路径或哈希格式错误" % number)
                    continue
                listed.add(rel)
                entries.append((rel, digest))
            if [rel for rel, _ in entries] != sorted(rel for rel, _ in entries):
                problems.append("MANIFEST 未按路径字典序排列")
        for rel, expected in entries:
            path = vendor / pathlib.PurePosixPath(rel)
            if not path.is_file():
                problems.append("清单文件不存在：%s" % rel)
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                problems.append("清单哈希不符：%s" % rel)
        actual_files = {
            str(path.relative_to(vendor).as_posix())
            for path in vendor.rglob("*")
            if path.is_file() and path.name not in {"MANIFEST.sha256", "VERSIONS.json"}
        }
        extras = sorted(actual_files - listed)
        if extras:
            problems.append("目录文件未列入清单：%s" % ",".join(extras[:8]))
        for license_rel in ("monaco/LICENSE", "pyodide/LICENSE"):
            if not (vendor / license_rel).is_file():
                problems.append("缺少 %s" % license_rel)
        versions = load_json(vendor / "VERSIONS.json")
        if not isinstance(versions, dict):
            problems.append("VERSIONS.json 无效")
        else:
            for package in ("monaco-editor", "pyodide"):
                value = versions.get(package)
                if (not isinstance(value, dict) or not isinstance(value.get("version"), str) or not value.get("version") or
                        not isinstance(value.get("integrity"), str) or not value.get("integrity") or
                        not value["integrity"].startswith("sha512-")):
                    problems.append("VERSIONS.json 缺少 %s 的 version/integrity" % package)
        self.add("vendor-pinned", not problems,
                 "通过" if not problems else "；".join(problems[:15]))

    @staticmethod
    def _has_hidden(element):
        return element is not None and "hidden" in element.attrs

    def _lab_element(self, lab, tag, cls=None, element_id=None):
        candidates = descendants(lab, tag)
        if cls:
            required_classes = cls.split()
            candidates = [x for x in candidates if all(has_class(x, name) for name in required_classes)]
        if element_id is not None:
            candidates = [x for x in candidates if x.attrs.get("id") == element_id]
        return candidates[0] if candidates else None

    def _validate_lab_dom(self, page, lab, seen_ids, problems):
        lab_id = lab.attrs.get("data-lab-id", "")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", lab_id):
            problems.append("%s 练习 id 无效" % fmt_path(page, self.site))
        if lab.attrs.get("id") != "lab-" + lab_id:
            problems.append("%s 练习根 id 不一致" % fmt_path(page, self.site))
        if lab_id in seen_ids:
            problems.append("练习 id 重复：%s" % lab_id)
        if lab_id:
            seen_ids.add(lab_id)
        if lab.attrs.get("data-lab-state") != "idle":
            problems.append("%s data-lab-state 不是 idle" % fmt_path(page, self.site))
        if lab.attrs.get("data-paste-guard") != "allow":
            problems.append("%s data-paste-guard 不是 allow" % fmt_path(page, self.site))
        if not lab.attrs.get("data-assets-root", "").strip():
            problems.append("%s 缺少 data-assets-root" % fmt_path(page, self.site))
        else:
            assets_root = lab.attrs["data-assets-root"].strip()
            if (assets_root.startswith(("/", "//")) or is_protocol(assets_root) or
                    (page.parent / pathlib.PurePosixPath(assets_root)).resolve() != (self.site / "assets").resolve()):
                problems.append("%s data-assets-root 未指向 assets/" % fmt_path(page, self.site))

        expected = [
            ("header", "lab-head", None, None), ("span", "lab-tag", None, None),
            ("h3", "lab-title", None, None), ("span", "lab-done", "lab-%s-done" % lab_id, True),
            ("p", "lab-goal", None, None), ("script", "lab-spec", None, None),
            ("div", "lab-preview", "lab-%s-preview" % lab_id, None),
            ("pre", "lab-starter", None, None),
            ("div", "lab-actions", None, None),
            ("button", "lab-btn lab-btn-main", "lab-%s-start" % lab_id, None),
            ("p", "lab-note", "lab-%s-note" % lab_id, True),
            ("div", "lab-work", "lab-%s-work" % lab_id, True),
            ("div", "lab-bar", None, None),
            ("button", "lab-btn lab-btn-main", "lab-%s-run" % lab_id, None),
            ("button", "lab-btn", "lab-%s-check" % lab_id, None),
            ("button", "lab-btn", "lab-%s-stop" % lab_id, True),
            ("button", "lab-btn", "lab-%s-reset" % lab_id, None),
            ("button", "lab-btn", "lab-%s-hint" % lab_id, True),
            ("span", "lab-status", "lab-%s-status" % lab_id, None),
            ("div", "lab-editor", "lab-%s-editor" % lab_id, None),
            ("div", "lab-toast", "lab-%s-toast" % lab_id, True),
            ("div", "lab-hints", "lab-%s-hints" % lab_id, None),
            ("pre", "lab-out", "lab-%s-stdout" % lab_id, None),
            ("pre", "lab-err", "lab-%s-error" % lab_id, True),
            ("ul", "lab-checks", "lab-%s-checks" % lab_id, None),
            ("div", "lab-solution-wrap", None, None),
            ("button", "lab-btn", "lab-%s-solution-btn" % lab_id, True),
            ("div", "lab-solution", "lab-%s-solution" % lab_id, True),
        ]
        spec_element = self._lab_element(lab, "script", "lab-spec")
        try:
            optional = bool(json.loads(text_of(spec_element).replace("<\\/", "</")).get("optional", True)) if spec_element is not None else True
        except (ValueError, AttributeError):
            optional = True
        if not optional:                                       # a lab that is not "选做" has no label: the builder leaves it out on purpose
            expected = [item for item in expected if item[1] != "lab-tag"]
        for tag, cls, element_id, hidden in expected:
            element = self._lab_element(lab, tag, cls, element_id)
            if element is None:
                problems.append("%s 缺少 .%s%s" % (fmt_path(page, self.site), cls or tag, "#" + element_id if element_id else ""))
            elif hidden is True and not self._has_hidden(element):
                problems.append("%s 缺少 hidden：%s" % (fmt_path(page, self.site), element_id or cls or tag))
        editor = self._lab_element(lab, "div", "lab-editor", "lab-%s-editor" % lab_id)
        if editor is not None and editor.attrs.get("data-editor-for") != lab_id:
            problems.append("%s 编辑器 data-editor-for 不符" % fmt_path(page, self.site))
        starter = self._lab_element(lab, "pre", "lab-starter")
        if starter is not None and not first_descendant(starter, "code"):
            problems.append("%s starter 缺少 code" % fmt_path(page, self.site))
        solution = self._lab_element(lab, "div", "lab-solution", "lab-%s-solution" % lab_id)
        if solution is not None and not first_descendant(solution, "code"):
            problems.append("%s solution 缺少 code" % fmt_path(page, self.site))
        action_ids = {
            "start": "lab-%s-start" % lab_id, "run": "lab-%s-run" % lab_id,
            "check": "lab-%s-check" % lab_id, "stop": "lab-%s-stop" % lab_id,
            "reset": "lab-%s-reset" % lab_id, "hint": "lab-%s-hint" % lab_id,
            "solution": "lab-%s-solution-btn" % lab_id,
        }
        for action, element_id in action_ids.items():
            button = self._lab_element(lab, "button", None, element_id)
            if button is not None and button.attrs.get("data-action") != action:
                problems.append("%s 按钮 data-action 不符：%s" % (fmt_path(page, self.site), element_id))
        spec_el = self._lab_element(lab, "script", "lab-spec")
        if spec_el is None or spec_el.attrs.get("type") != "application/json":
            problems.append("%s .lab-spec 类型不正确" % fmt_path(page, self.site))
            return
        try:
            spec = json.loads(text_of(spec_el))
        except Exception as exc:
            problems.append("%s .lab-spec JSON 无效：%s" % (fmt_path(page, self.site), exc))
            return
        keys = {"id", "title", "goal", "starter", "prelude", "tests", "hints", "solution", "timeout", "seed", "optional"}
        if not isinstance(spec, dict) or set(spec) != keys:
            problems.append("%s .lab-spec 字段不完整" % fmt_path(page, self.site))
            return
        if spec.get("id") != lab_id or not isinstance(spec.get("title"), str) or not isinstance(spec.get("goal"), str) or not isinstance(spec.get("starter"), str) or not spec.get("starter") or not isinstance(spec.get("prelude"), str) or not isinstance(spec.get("solution"), str):
            problems.append("%s .lab-spec 基本字段不符" % fmt_path(page, self.site))
        tests = spec.get("tests")
        if not isinstance(tests, list) or not tests:
            problems.append("%s .lab-spec tests 为空" % fmt_path(page, self.site))
        else:
            test_ids = set()
            for test in tests:
                if not isinstance(test, dict) or set(test) != {"id", "name", "code"} or not isinstance(test.get("id"), str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", test.get("id", "")) or test.get("id") in test_ids or not isinstance(test.get("name"), str) or not isinstance(test.get("code"), str):
                    problems.append("%s .lab-spec tests 项无效" % fmt_path(page, self.site))
                else:
                    test_ids.add(test["id"])
        if not isinstance(spec.get("hints"), list) or not all(isinstance(x, str) for x in spec["hints"]):
            problems.append("%s .lab-spec hints 无效" % fmt_path(page, self.site))
        timeout = spec.get("timeout")
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 10:
            problems.append("%s .lab-spec timeout 无效" % fmt_path(page, self.site))
        seed = spec.get("seed")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
            problems.append("%s .lab-spec seed 无效" % fmt_path(page, self.site))
        if not isinstance(spec.get("optional"), bool):
            problems.append("%s .lab-spec optional 无效" % fmt_path(page, self.site))

    def check_labs(self):
        lab_pages = []
        problems = []
        seen_ids = set()
        for path, parser in self.pages.items():
            labs = descendants(parser.root, "section", "lab")
            scripts = [x for x in descendants(parser.root, "script")
                       if pathlib.PurePosixPath(x.attrs.get("src", "").split("#", 1)[0].split("?", 1)[0]).name in {"lab-guard.js", "lab-core.js", "lab.js"}]
            if not labs:
                if scripts:
                    problems.append("%s 不含练习却加载练习脚本" % fmt_path(path, self.site))
                continue
            lab_pages.append(path)
            for lab in labs:
                self._validate_lab_dom(path, lab, seen_ids, problems)
            names = [pathlib.PurePosixPath(x.attrs.get("src", "").split("#", 1)[0].split("?", 1)[0]).name for x in scripts]
            if names != ["lab-guard.js", "lab-core.js", "lab.js"]:
                problems.append("%s 练习脚本顺序或数量不正确" % fmt_path(path, self.site))
            for script in scripts:
                if "defer" not in script.attrs:
                    problems.append("%s 练习脚本缺少 defer" % fmt_path(path, self.site))
                src = script.attrs.get("src", "")
                src_path = src.split("#", 1)[0].split("?", 1)[0]
                target = ((path.parent / pathlib.PurePosixPath(src_path)).resolve()
                          if src and not src.startswith(("/", "//")) and not is_protocol(src) else None)
                if target != (self.site / "assets" / pathlib.PurePosixPath(src_path).name).resolve():
                    problems.append("%s 练习脚本路径不在 assets/" % fmt_path(path, self.site))
        for path, parser in self.pages.items():           # a reference is a resource attribute or an inline script, not the words in the course text (the outline talks about Monaco)
            for el in descendants(parser.root):
                refs = [el.attrs.get(a, "") for a in ("src", "href", "poster")]
                inline = el.tag == "script" and not el.attrs.get("src") and "json" not in el.attrs.get("type", "") and re.search(r"monaco|pyodide", text_of(el), re.I)
                if inline or any(re.search(r"monaco|pyodide", r, re.I) for r in refs):
                    problems.append("%s 页面直接引用 Monaco/Pyodide" % fmt_path(path, self.site))
                    break
        assets = self.site / "assets"
        required_assets = ("lab.js", "lab-core.js", "lab-guard.js", "lab-worker.js", "lab-runner.py", "lab-config.json")
        if lab_pages:
            for name in required_assets:
                if not (assets / name).is_file():
                    problems.append("缺少 assets/%s" % name)
            config = load_json(assets / "lab-config.json")
            if not isinstance(config, dict) or set(config) != {"block_paste"} or not isinstance(config.get("block_paste"), bool):
                problems.append("lab-config.json 必须只含布尔 block_paste")
            for name in ("lab.js", "lab-core.js", "lab-guard.js", "lab-worker.js"):
                path = assets / name
                if path.is_file():
                    raw = read_text(path)
                    if "http://" in raw or "https://" in raw:
                        problems.append("assets/%s 含外部网址字样" % name)
                    if "innerHTML" in raw:
                        problems.append("assets/%s 使用 innerHTML" % name)
        self.add("labs", not problems,
                 "无练习，跳过" if not lab_pages and not problems else ("通过" if not problems else "；".join(problems[:20])))

    def check_search_index(self):
        path = self.site / "assets/search-index.js"
        raw = read_text(path)
        problems = []
        prefix = "window.SEARCH_INDEX = "
        if not raw.startswith(prefix) or not raw.rstrip().endswith(";"):
            problems.append("search-index.js 包装格式不正确")
            entries = []
        else:
            try:
                entries = json.loads(raw[len(prefix):].rstrip()[:-1].strip())
            except Exception as exc:
                entries = []
                problems.append("search-index.js JSON 无效：%s" % exc)
        if not isinstance(entries, list):
            problems.append("搜索索引不是数组")
            entries = []
        by_id = {str(x.get("id")): x for x in entries if isinstance(x, dict) and x.get("id")}
        if set(by_id) != set(self.all_units) or len(by_id) != len(entries):
            problems.append("搜索索引 id 集合不等于全部单元")
        for unit in self.all_units:
            item = by_id.get(unit)
            if not item:
                continue
            source = self.source_for(unit)
            if (item.get("w") is not bool(source)):
                problems.append("%s w 状态不匹配" % unit)
            pair = self.unit_book.get(unit)
            if pair and (item.get("b") != pair[0] or item.get("n") != pair[1]):
                problems.append("%s b/n 不匹配" % unit)
            if source and not str(item.get("x", "")).strip():
                problems.append("%s 正文摘录为空" % unit)
        self.add("search-index", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_no_external_load(self):
        problems = []
        for path, parser in self.pages.items():
            if self.is_vendor_path(path):
                continue
            for el in descendants(parser.root):
                if el.tag == "a":
                    href = el.attrs.get("href", "").strip()
                    if attr_external(href):
                        allowed = source_link(el) and href.lower().startswith("https://") and el.attrs.get("target") == "_blank" and "noopener" in rel_value(el.attrs.get("rel"))
                        if not allowed:
                            problems.append("%s 外部链接 %s" % (fmt_path(path, self.site), href))
                    elif is_protocol(href) and not href.startswith("#"):
                        problems.append("%s 非允许协议链接 %s" % (fmt_path(path, self.site), href))
                attrs = []
                if el.tag == "link":
                    attrs += [el.attrs.get("href", ""), el.attrs.get("src", "")]
                if el.tag == "script":
                    attrs.append(el.attrs.get("src", ""))
                if el.tag in {"img", "source", "video", "audio", "iframe", "embed", "object"}:
                    attrs += [el.attrs.get("src", ""), el.attrs.get("poster", "")]
                for value in attrs:
                    if attr_external(value):
                        problems.append("%s 外部资源 %s" % (fmt_path(path, self.site), value))
        for path in self.iter_text_files():
            text = read_text(path)
            if path.suffix.lower() == ".css":
                if any(attr_external(x) for x in css_urls(text)) or re.search(r"@import\s+(?:url\s*\(\s*)?['\"]?(?:https?:|//)", text, re.I):
                    problems.append("%s CSS 外部资源" % fmt_path(path, self.site))
            elif path.suffix.lower() == ".js" and re.search(r"(?:fetch\s*\(|import\s*\(|\.open\s*\()[^\n;]*(?:https?:|//)", text, re.I):
                problems.append("%s JS 外部请求" % fmt_path(path, self.site))
        self.add("no-external-load", not problems, "通过" if not problems else "；".join(problems[:12]))

    def check_no_claude_runtime(self):
        problems = [fmt_path(p, self.site) for p in self.iter_text_files() if re.search(r"window\.claude|claude\.use|googleapis|gstatic", read_text(p), re.I)]
        self.add("no-claude-runtime", not problems, "通过" if not problems else "发现运行时词样：" + ", ".join(problems[:12]))

    def check_no_secret_or_path(self):
        # 课程本身会讲 .env、Authorization 请求头、DASHSCOPE_API_KEY 这类话题，所以只抓真泄露：本机路径、网关名、带值的密钥、长串令牌、IP 地址
        patterns = [(r"/home/", "/home/"), (r"/root/", "/root/"), (r"/Users/", "/Users/"), (r"(?<![A-Za-z])[A-Za-z]:\\[^\s\\]+\\", "Windows 路径"), (r"MODELINK", "MODELINK"),
                    (r"api[_-]?key[\"']?\s*[=:]\s*[\"']?[A-Za-z0-9_\-]{12,}", "带值的 api_key"), (r"Bearer\s+[A-Za-z0-9._\-]{16,}", "Bearer 长串"), (r"sk-[A-Za-z0-9]{16,}", "sk- 长串"), (r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "IPv4")]
        problems = []
        for p in self.iter_text_files():
            text = read_text(p)
            for pattern, label in patterns:
                if re.search(pattern, text, re.I if label in {"MODELINK", "带值的 api_key"} else 0):
                    problems.append("%s:%s" % (fmt_path(p, self.site), label))
        self.add("no-secret-or-path", not problems, "通过" if not problems else "；".join(problems[:12]))

    def check_no_experiment_labels(self):
        # 只认标签的写法：课程里会讲“核对注册表”“辅助技术测试”，那不是标签
        words = ["试验品", "不属于课程", "EXPERIMENT", "试读版", "教案页", "暂定课题名", "零基础学生能看懂吗", "【试验", "【技术测试", "技术测试品", "技术测试视频", "这是技术测试", "核对注：", "【核对注"]
        problems = [fmt_path(p, self.site) for p in self.iter_text_files() if any(w in read_text(p) for w in words)]
        self.add("no-experiment-labels", not problems, "通过" if not problems else "发现禁用词：" + ", ".join(problems[:12]))

    def check_relative_links_resolve(self):
        problems = []
        for path, parser in self.pages.items():
            ids = {e.attrs.get("id") for e in descendants(parser.root) if e.attrs.get("id")}
            for el in descendants(parser.root):
                for attr in ("href", "src", "poster"):
                    if attr not in el.attrs:
                        continue
                    value = el.attrs[attr].strip()
                    if not value:
                        continue
                    if value.startswith("#"):
                        anchor = value[1:].split("?", 1)[0]
                        if anchor and anchor not in ids:
                            problems.append("%s #%s 不存在" % (fmt_path(path, self.site), anchor))
                        continue
                    if value.startswith("/") or value.lower().startswith("file:"):
                        problems.append("%s %s 禁止绝对/file 路径" % (fmt_path(path, self.site), attr))
                        continue
                    if is_protocol(value) or value.startswith("//"):
                        continue
                    target, error = self.relative_target(value, path)
                    if error:
                        problems.append("%s %s %s" % (fmt_path(path, self.site), attr, error))
                    elif target and target.suffix.lower() == ".html" and not value.split("#", 1)[0].split("?", 1)[0].lower().endswith(".html"):
                        problems.append("%s 页面链接未写 .html：%s" % (fmt_path(path, self.site), value))
                    if target and "#" in value:
                        anchor = value.split("#", 1)[1].split("?", 1)[0]
                        if anchor and target.suffix.lower() == ".html":
                            tp = self.parser_for(target)
                            target_ids = {e.attrs.get("id") for e in descendants(tp.root) if e.attrs.get("id")}
                            if anchor not in target_ids:
                                problems.append("%s 目标锚点不存在：%s" % (fmt_path(path, self.site), value))
        for path in self.iter_files():
            if path.suffix.lower() == ".css":
                for value in css_urls(read_text(path)):
                    if not value or value.startswith(("#", "/")) or is_protocol(value) or value.startswith("//"):
                        continue
                    _, error = self.relative_target(value, path)
                    if error:
                        problems.append("%s CSS %s" % (fmt_path(path, self.site), error))
        self.add("relative-links-resolve", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_page_basics(self):
        problems = []
        for path, parser in self.pages.items():
            html = first_descendant(parser.root, "html")
            if not html or html.attrs.get("lang") != "zh-CN":
                problems.append("%s 缺少 lang=zh-CN" % fmt_path(path, self.site))
            title = first_descendant(parser.root, "title")
            if not title or not norm_text(text_of(title)):
                problems.append("%s title 为空" % fmt_path(path, self.site))
            viewport = [x for x in descendants(parser.root, "meta") if x.attrs.get("name", "").lower() == "viewport"]
            if not viewport:
                problems.append("%s 缺少 viewport" % fmt_path(path, self.site))
            robots = [x for x in descendants(parser.root, "meta") if x.attrs.get("name", "").lower() == "robots" and rel_value(x.attrs.get("content")) == "noindex, nofollow"]
            if not robots:
                problems.append("%s 缺少 robots noindex,nofollow" % fmt_path(path, self.site))
            css_ok = False
            for link in descendants(parser.root, "link"):
                href = link.attrs.get("href", "")
                target, error = self.relative_target(href, path)
                if not error and target == (self.site / "assets/book.css").resolve():
                    css_ok = True
            if not css_ok:
                problems.append("%s 缺少 assets/book.css" % fmt_path(path, self.site))
            for img in descendants(parser.root, "img"):
                if not img.attrs.get("alt", "").strip():
                    problems.append("%s img 缺少 alt" % fmt_path(path, self.site))
            ids = [x.attrs["id"] for x in descendants(parser.root) if x.attrs.get("id")]
            duplicate = sorted({x for x in ids if ids.count(x) > 1})
            if duplicate:
                problems.append("%s id 重复：%s" % (fmt_path(path, self.site), ",".join(duplicate)))
            if parser.errors:
                problems.append("%s HTML 解析：%s" % (fmt_path(path, self.site), ";".join(parser.errors[:3])))
        self.add("page-basics", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_size_limits(self):
        """Every html page stays small (<= 3 MB).  The whole site has NO size cap (user decision 2026-11-06: the lessons go online and the videos are the original files); the total and the share of media/ are only reported."""
        problems, total, media = [], 0, 0
        media_dir = self.site / "media"
        for p in self.iter_files():
            try:
                size = p.stat().st_size
            except OSError:
                continue
            total += size
            try:
                p.relative_to(media_dir)
                media += size
            except ValueError:
                pass
            if p.suffix.lower() == ".html" and size > 3 * 1024 * 1024:
                problems.append("HTML 超过 3 MB：%s" % fmt_path(p, self.site))
        mb = lambda n: "%.0f MB" % (n / 1048576)
        self.add("size-limits", not problems, ("通过（整站 %s，其中 media/ %s；整站不设大小上限）" % (mb(total), mb(media))) if not problems else "；".join(problems))

    def bind_data(self, source):
        """Each chapter source names its own records, claims file and project (lesson 1 was the only chapter when this checker was written): load that chapter's data before it is checked."""
        rec, cl = source.get("records"), source.get("claims_file")
        if not rec or not cl:
            return
        proj = (self.repo / rec).parent.parent
        self.records = load_json(self.repo / rec) or {}
        self.claims = load_json(self.repo / cl) or {}
        self.script = load_json(proj / "artifacts/script.json") or {}
        ex = proj / "exports/metadata/exercises.txt"
        if ex.is_file():
            self.exercise_data = parse_exercises(ex)

    def source_pages(self):
        for unit in self.all_units:
            pair = self.unit_book.get(unit)
            source = self.source_for(unit)
            if pair and source:
                self.bind_data(source[1])
                yield unit, pair[0], self.page_for_unit(unit), source[1], source[0]

    def outline_unit(self, unit):
        return self.units_by_id.get(unit) or self.units_by_id.get(norm_id(unit)) or {}

    def check_ch_header(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            parser = self.parser_for(page)
            h1 = first_descendant(parser.root, "h1")
            title = self.outline_unit(unit).get("title", "")
            if not h1 or norm_text(text_of(h1)) != norm_text(title):
                problems.append("%s h1 与大纲标题不符" % fmt_path(page, self.site))
            lesson = first_descendant(parser.root, "p", "lesson-title")
            if not lesson or norm_text(text_of(lesson)) != norm_text(source.get("lesson_title", "")):
                problems.append("%s lesson-title 不符" % fmt_path(page, self.site))
            basic = first_descendant(parser.root, "div", "basic")
            if not basic or norm_text(str(source.get("basic_question", ""))) not in norm_text(text_of(basic)):
                problems.append("%s basic_question 缺失" % fmt_path(page, self.site))
            takeaway = first_descendant(parser.root, "div", "takeaway")
            lis = descendants(takeaway, "li") if takeaway else []
            expected = source.get("takeaway", []) or []
            if [norm_text(text_of(x)) for x in lis] != [norm_text(str(x)) for x in expected]:
                problems.append("%s takeaway 不符" % fmt_path(page, self.site))
        self.add("ch-header", not problems, "通过" if not problems else "；".join(problems[:15]))

    def video_data(self, source):
        return source.get("video") if isinstance(source.get("video"), dict) else None

    def check_ch_video(self):
        problems = []
        checked = False
        for unit, bid, page, source, source_path in self.source_pages():
            video_data = self.video_data(source)
            if not video_data:
                continue
            checked = True
            parser = self.parser_for(page)
            videos = [x for x in descendants(parser.root, "video") if x.attrs.get("id") == "lesson-video"]
            if len(videos) != 1 or len(descendants(parser.root, "video")) != 1:
                problems.append("%s 需要恰好一个 video#lesson-video" % fmt_path(page, self.site))
                continue
            video = videos[0]
            try:
                duration = float(video.attrs.get("data-duration", ""))
            except ValueError:
                duration = None
                problems.append("%s data-duration 不是数" % fmt_path(page, self.site))
            sources = descendants(video, "source")
            if len(sources) != 1 or not sources[0].attrs.get("src"):
                problems.append("%s 需要恰好一个 video source（多个时浏览器可能播的不是被检查的那个）" % fmt_path(page, self.site))
            elif sources[0].attrs.get("type") != "video/mp4":
                problems.append("%s video source 的 type 必须是 video/mp4" % fmt_path(page, self.site))
            else:
                _, error = self.relative_target(sources[0].attrs.get("src"), page)
                if error:
                    problems.append("%s source %s" % (fmt_path(page, self.site), error))
            if not video.attrs.get("poster"):
                problems.append("%s 缺少 poster" % fmt_path(page, self.site))
            else:
                _, error = self.relative_target(video.attrs.get("poster"), page)
                if error:
                    problems.append("%s poster %s" % (fmt_path(page, self.site), error))
            chapters = video_data.get("chapters", []) or []
            buttons = descendants(parser.root, "button", "seek")
            actual = []
            for button in buttons:
                try:
                    actual.append((float(button.attrs.get("data-seek", "")), norm_text(text_of(button))))
                except ValueError:
                    problems.append("%s seek data-seek 不是数" % unit)
            expected = [(float(x.get("start")), norm_text(str(x.get("title", "")))) for x in chapters if isinstance(x, dict) and x.get("start") is not None]
            if actual != expected:
                problems.append("%s 视频章节按钮与源文件不符" % unit)
            if duration is not None:
                for el in descendants(parser.root):
                    if (has_class(el, "seek") or has_class(el, "frame")) and "data-seek" in el.attrs:
                        try:
                            value = float(el.attrs["data-seek"])
                            if value < 0 or value >= duration:
                                problems.append("%s data-seek 越界 %s" % (unit, el.attrs["data-seek"]))
                        except ValueError:
                            problems.append("%s data-seek 不是数" % unit)
            if self.no_video_probe:
                continue
            source_el = sources[0] if sources else None
            media = self.canonical_page(source_el.attrs.get("src", ""), page) if source_el else None
            if duration is None or not media or not media.is_file():
                continue
            try:
                result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(media)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                info = json.loads(result.stdout or "{}")
                actual_duration = float(info.get("format", {}).get("duration", "nan"))
                types = {x.get("codec_type") for x in info.get("streams", [])}
                if result.returncode != 0 or actual_duration != actual_duration:
                    problems.append("%s ffprobe 失败" % unit)
                elif abs(actual_duration - duration) > 0.05:
                    problems.append("%s data-duration 与 ffprobe 相差超过 0.05 秒" % unit)
                if not {"video", "audio"}.issubset(types):
                    problems.append("%s 缺少视频流或音频流" % unit)
            except Exception as exc:
                problems.append("%s ffprobe 异常 %s" % (unit, exc))
        self.add("ch-video", not problems, "skipped (--no-video-probe)" if self.no_video_probe and checked and not problems else ("通过" if not problems else "；".join(problems[:15])))

    @staticmethod
    def mp4_boxes(path, limit=4096):
        """Top-level boxes of an mp4 file as (type, offset, size), read from the box headers only.  The scan ends when both moov and mdat have been seen (or at the end of the file).
        A box whose header is cut off, or whose declared size is smaller than its header or runs past the end of the file, ends the scan as ("!broken", offset, declared size):
        a truncated or scribbled file must not pass for a streamable one."""
        out = []
        size = path.stat().st_size
        with open(path, "rb") as f:
            pos, seen = 0, set()
            while pos < size and len(out) < limit:
                f.seek(pos)
                head = f.read(8)
                if len(head) < 8:
                    out.append(("!broken", pos, len(head)))
                    break
                box_size, box_type, header = int.from_bytes(head[:4], "big"), head[4:8].decode("latin1"), 8
                if box_size == 1:
                    ext = f.read(8)
                    if len(ext) < 8:
                        out.append(("!broken", pos, 0))
                        break
                    box_size, header = int.from_bytes(ext, "big"), 16
                elif box_size == 0:
                    box_size = size - pos
                if box_size < header or pos + box_size > size:
                    out.append(("!broken", pos, box_size))
                    break
                out.append((box_type, pos, box_size))
                seen.add(box_type)
                if "moov" in seen and "mdat" in seen:
                    break
                pos += box_size
        return out

    def check_ch_video_stream(self):
        """Online quality guard (replaces the old whole-site size cap, 2026-11-06): the video a chapter page plays is the lesson's own original, byte for byte
        (the chapter source names projects/<lesson>/exports/video/output.mp4 and the site file is that very file), and it streams straight from the file:
        mp4, H.264 video + AAC audio, the moov box in front of the mdat box (playback starts before the download ends; the server answers Range requests, so seeking works)."""
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            video_data = self.video_data(source)
            if not video_data:
                continue
            parser = self.parser_for(page)
            videos = [x for x in descendants(parser.root, "video") if x.attrs.get("id") == "lesson-video"]
            sources = descendants(videos[0], "source") if videos else []
            media = self.canonical_page(sources[0].attrs.get("src", ""), page) if sources else None
            if not media or not media.is_file():
                continue      # ch-video already reports a missing file
            rel = str(video_data.get("file", "")).replace("\\", "/")
            if not re.fullmatch(r"projects/[A-Za-z0-9][A-Za-z0-9_-]*/exports/video/output\.mp4", rel):
                problems.append("%s 书里的视频必须是该课的原件 projects/<课>/exports/video/output.mp4，不是 %s" % (unit, rel))
            else:
                original = self.repo.resolve() / rel
                if not original.is_file():
                    problems.append("%s 找不到该课的原件 %s" % (unit, rel))
                elif original.resolve() != original:
                    problems.append("%s 该课原件的路径经过符号链接，不接受（%s）" % (unit, rel))
                else:
                    same = False
                    try:
                        same = os.path.samefile(original, media)
                    except OSError:
                        pass
                    if not same:
                        same = original.stat().st_size == media.stat().st_size and sha256_file(original) == sha256_file(media)
                    if not same:
                        problems.append("%s 站点里的视频不是该课原件（大小或内容不同：重编码过的“网页版”不允许，线上要原画质）" % unit)
            boxes = [b[0] for b in self.mp4_boxes(media)]
            if "!broken" in boxes:
                problems.append("%s 视频文件的 mp4 盒头损坏或文件被截断" % unit)
            elif boxes[:1] != ["ftyp"] or "moov" not in boxes or "mdat" not in boxes or boxes.index("moov") > boxes.index("mdat"):
                problems.append("%s 视频不能边下边播：mp4 的 moov 要在 mdat 之前（用 ffmpeg -movflags +faststart 重新封装，不重编码）" % unit)
            if self.no_video_probe:
                continue
            try:
                result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name:stream_disposition=attached_pic", "-of", "json", str(media)],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                streams = json.loads(result.stdout or "{}").get("streams", [])
                vcodecs = {x.get("codec_name") for x in streams if x.get("codec_type") == "video" and not x.get("disposition", {}).get("attached_pic")}
                acodecs = {x.get("codec_name") for x in streams if x.get("codec_type") == "audio"}
                if vcodecs != {"h264"} or acodecs != {"aac"}:
                    problems.append("%s 视频编码要 H.264＋AAC（浏览器都能播），现在是 %s／%s" % (unit, sorted(map(str, vcodecs)), sorted(map(str, acodecs))))
            except Exception as exc:
                problems.append("%s ffprobe 异常 %s" % (unit, exc))
        self.add("ch-video-stream", not problems, "通过" if not problems else "；".join(problems[:15]))

    def script_texts(self):
        found = []
        def walk(value):
            if isinstance(value, dict):
                if isinstance(value.get("text"), str):
                    found.append(value["text"])
                for v in value.values():
                    walk(v)
            elif isinstance(value, list):
                for v in value:
                    walk(v)
        walk(self.script)
        return found

    def check_ch_frames(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            parser = self.parser_for(page)
            figures = descendants(parser.root, "figure", "frame-fig")
            expected = source.get("frames", []) or []
            if len(figures) != len(expected):
                problems.append("%s 抽帧数量不符" % unit)
            for i, item in enumerate(expected):
                if i >= len(figures):
                    break
                fig = figures[i]
                link = first_descendant(fig, "a", "frame")
                img = first_descendant(fig, "img")
                if not link or not img:
                    problems.append("%s 第%d张抽帧缺少 a.frame/img" % (unit, i + 1)); continue
                try:
                    actual_seek = float(link.attrs.get("data-seek", ""))
                    if abs(actual_seek - float(item.get("seek"))) > 1e-6:
                        problems.append("%s 第%d张抽帧 seek 不符" % (unit, i + 1))
                except (ValueError, TypeError):
                    problems.append("%s 第%d张抽帧 seek 无效" % (unit, i + 1))
                if norm_text(img.attrs.get("alt", "")) != norm_text(str(item.get("alt", ""))):
                    problems.append("%s 第%d张抽帧 alt 不符" % (unit, i + 1))
                src = img.attrs.get("src", "")
                target, error = self.relative_target(src, page)
                if error:
                    problems.append("%s 抽帧图片 %s" % (unit, error))
                elif image_width(target) is None or image_width(target) < 480:
                    problems.append("%s 抽帧图片宽度不足" % unit)
                q = first_descendant(fig, "q", "narr")
                if not q:
                    problems.append("%s 第%d张抽帧缺少 q.narr" % (unit, i + 1)); continue
                qtext = text_of(q)
                if len(qtext) > 120:
                    problems.append("%s q.narr 超过 120 字" % unit)
                if norm_quote(qtext) != norm_quote(str(item.get("narr", ""))):
                    problems.append("%s 第%d张 q.narr 与源文件不符" % (unit, i + 1))
                quote = norm_quote(qtext)
                if quote and not any(quote in norm_quote(x) for x in self.script_texts()):
                    problems.append("%s 第%d张 q.narr 不是旁白子串" % (unit, i + 1))
        self.add("ch-frames", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_ch_sections(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            parser = self.parser_for(page)
            actual = descendants(parser.root, "section", "sec")
            expected = source.get("sections", []) or []
            if len(actual) != len(expected):
                problems.append("%s section.sec 数量不符" % unit)
            for i, item in enumerate(expected):
                if i >= len(actual): break
                sec = actual[i]
                if sec.attrs.get("id") != "sec-" + str(item.get("id", "")):
                    problems.append("%s section id 不符" % unit)
                h2 = first_descendant(sec, "h2")
                if not h2 or norm_text(text_of(h2)) != norm_text(str(item.get("title", ""))):
                    problems.append("%s section h2 不符" % unit)
                content_blocks = [c for c in sec.children if isinstance(c, Element) and c.tag != "h2"]
                if not content_blocks:
                    problems.append("%s section %s 没有块" % (unit, item.get("id")))
        self.add("ch-sections", not problems, "通过" if not problems else "；".join(problems[:15]))

    def record_data(self, record_id):
        item = self.records.get(record_id) if isinstance(self.records, dict) else None
        return item if isinstance(item, dict) and record_id != "_meta" else None

    def check_ch_shice(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            parser = self.parser_for(page)
            shows = descendants(parser.root, "figure", "show")
            if len(shows) < 6:
                problems.append("%s figure.show 少于 6 个" % unit)
            for show in shows:
                rid = show.attrs.get("data-record", "")
                record = self.record_data(rid)
                if not record:
                    problems.append("%s 未知 data-record %s" % (unit, rid)); continue
                cap = first_descendant(show, "figcaption", "rec")
                body = text_of(show)
                if not cap:
                    problems.append("%s %s 缺少 figcaption.rec" % (unit, rid)); continue
                ct = text_of(cap)
                for value, label in ((str(record.get("model", "")).split("/")[-1], "模型"), (str(record.get("date", "")), "日期"), (str(record.get("mode", "")), "mode")):
                    if record.get("kind") == "window" and record.get("date") is None and label == "日期":
                        continue  # A window sketch may have no measurement date.
                    if value and value not in ct:
                        problems.append("%s %s 缺少%s" % (unit, rid, label))
                if record.get("n") is not None and not re.search(r"(?<!\d)%s\s*遍" % re.escape(str(record["n"])), ct):
                    problems.append("%s %s 缺少次数" % (unit, rid))
                kind = record.get("kind")
                if kind in ("callpanel", "window", "turnbars", "classgrid"):
                    want_tag = "tag-shice" if record.get("honest") == "shice" else "tag-shiyi"
                else:
                    want_tag = {"sketch": "tag-shiyi", "sequence": "tag-shiyi", "quotes": "tag-source", "cards": "tag-source"}.get(kind, "tag-shice")   # made-up numbers are labelled 示意 and must never carry the 实测 stamp; official quotes carry 引文
                if not first_descendant(cap, "span", want_tag):
                    problems.append("%s %s 缺少 %s" % (unit, rid, want_tag))
                if kind in ("quotes", "cards") and first_descendant(show, "span", "tag-shice"):
                    problems.append("%s %s 引文卡不能带 实测 章" % (unit, rid))
                if kind == "sketch" and (first_descendant(show, "span", "tag-shice") or "示意" not in ct):
                    problems.append("%s %s 示意图不能带 实测 章，且图注要写 示意" % (unit, rid))
                if kind == "sequence" and (first_descendant(show, "span", "tag-shice") or "示意" not in ct):
                    problems.append("%s %s 时序示意图不能带 实测 章，且图注要写 示意" % (unit, rid))
                if kind == "sequence" and first_descendant(show, "span", "seq-badge-doc") and first_descendant(show, "span", "tag-shice"):
                    problems.append("%s %s 引文步骤不能带 实测 章" % (unit, rid))
                if kind == "callpanel" and record.get("honest") == "shiyi" and (first_descendant(show, "span", "tag-shice") or "示意" not in ct):
                    problems.append("%s %s 示意面板不能带 实测 章，且图注要写 示意" % (unit, rid))
                if kind in ("window", "turnbars", "classgrid"):
                    honest = record.get("honest")
                    if honest not in ("shice", "shiyi") or (kind != "window" and honest != "shice"):
                        problems.append("%s %s 新图 honest 无效" % (unit, rid))
                    if honest == "shiyi" and (first_descendant(show, "span", "tag-shice") or "示意" not in ct):
                        problems.append("%s %s 示意图不能带 实测 章，且图注要写 示意" % (unit, rid))
                    if honest == "shice" and (first_descendant(show, "span", "tag-shiyi") or "示意" in body):
                        problems.append("%s %s 实测图不能写 示意 或带 示意 章" % (unit, rid))
                    if kind == "window" and any(n.get("state") == "missing" for n in record.get("notes", [])) and honest != "shiyi":
                        problems.append("%s %s 有 missing 的纸条图只能是示意" % (unit, rid))
                    if kind == "classgrid":
                        labeler = str(record.get("labeler", ""))
                        if not labeler or "AI" not in labeler or "真人" in labeler or "人工" in labeler:
                            problems.append("%s %s classgrid 标注应写 AI 模型" % (unit, rid))
                if record.get("kind") == "towers":
                    for group in record.get("groups", []) or []:
                        if str(group.get("text", "")) not in body or str(group.get("count", "")) not in body:
                            problems.append("%s %s 缺少塔组" % (unit, rid))
                if record.get("kind") == "chat" and record.get("sum"):
                    for row in record["sum"]:
                        if str(row.get("text", "")) not in body:
                            problems.append("%s %s 缺少 sum" % (unit, rid))
                if record.get("kind") == "task":
                    answer = str(record.get("answer", ""))
                    if answer[:40] and answer[:40] not in body:
                        problems.append("%s %s 缺少 task answer" % (unit, rid))
                    for check in record.get("check", []) or []:
                        if str(check.get("text", "")) not in body:
                            problems.append("%s %s 缺少 task check" % (unit, rid))
        self.add("ch-shice", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_ch_sources(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            sourced = {x.get("id"): x for x in self.claims.get("sourced", []) if isinstance(x, dict)}
            parser = self.parser_for(page)
            facts = descendants(parser.root, "aside", "fact")
            for fact in facts:
                cid = fact.attrs.get("data-claim", "")
                claim = sourced.get(cid)
                body = text_of(fact)
                if not claim:
                    problems.append("%s 未知 data-claim %s" % (unit, cid)); continue
                if str(claim.get("statement", "")) not in body or "适用范围：" + str(claim.get("scope", "")) not in body:
                    problems.append("%s %s 断言或适用范围不符" % (unit, cid))
                if not first_descendant(fact, "span", "tag-source"):
                    problems.append("%s %s 缺少 tag-source" % (unit, cid))
                links = descendants(fact, "a", "src-link")
                if not links:
                    problems.append("%s %s 缺少 src-link" % (unit, cid))
            links = descendants(parser.root, "a", "src-link")
            if not links:
                problems.append("%s 至少需要一个 src-link" % unit)
            # Reading links are also marked src-link but use a human title.
            # Require at least one canonical source link whose visible text is
            # the URL (the format used by fact/source citations).
            canonical = [link for link in links
                         if link.attrs.get("href", "").startswith("https://")
                         and norm_text(text_of(link)).replace("https://", "") == link.attrs.get("href", "").replace("https://", "")]
            if not canonical:
                problems.append("%s 缺少文字与 href 一致的 src-link" % unit)
        self.add("ch-sources", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_ch_metaphors(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            parser = self.parser_for(page)
            for term in descendants(parser.root, "div", "term"):
                if not first_descendant(term, "b", "word") or not first_descendant(term, "span", "tag-metaphor"):
                    problems.append("%s term 缺少 word/tag-metaphor" % unit)
                gap = first_descendant(term, "p", "gap")
                if not gap or len(re.findall(r"[\u3400-\u9fff]", text_of(gap))) < 6:
                    problems.append("%s term gap 少于 6 个汉字" % unit)
        self.add("ch-metaphors", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_ch_thinks(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            parser = self.parser_for(page)
            thinks = descendants(parser.root, "details", "think")
            expected = sum(1 for s in source.get("sections", []) or [] for b in s.get("blocks", []) or [] if isinstance(b, dict) and b.get("t") == "think")
            if len(thinks) < expected:
                problems.append("%s think 数量少于源文件" % unit)
            if any("open" in x.attrs for x in thinks):
                problems.append("%s think 不应有 open" % unit)
        self.add("ch-thinks", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_ch_exercises(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            parser = self.parser_for(page)
            articles = descendants(parser.root, "article", "exercise")
            expected = self.exercise_data
            if expected and len(articles) != len(expected):
                problems.append("%s exercise 数量不符" % unit)
            by_num = {}
            for article in articles:
                num = article.attrs.get("data-ex", "")
                by_num[num] = article
                q = first_descendant(article, "div", "q")
                ans = first_descendant(article, "details", "answer")
                if not q or not norm_text(text_of(q)):
                    problems.append("%s 练习%s 缺少题面" % (unit, num))
                if not ans or "open" in ans.attrs:
                    problems.append("%s 练习%s 答案缺失或打开" % (unit, num))
            allq = norm_text("".join(text_of(first_descendant(a, "div", "q")) for a in articles if first_descendant(a, "div", "q")))
            for forbidden in ("北京", "校门口咖啡", "2025", "2026", "知味咖啡"):
                if forbidden in allq:
                    problems.append("%s 题面泄露答案关键值 %s" % (unit, forbidden))
            for number, (q_expected, a_expected) in expected.items():
                article = by_num.get(str(number))
                if not article: continue
                q = first_descendant(article, "div", "q")
                ans = first_descendant(article, "details", "answer")
                qtext, atext = norm_text(text_of(q)), norm_text(text_of(ans)) if ans else ""
                for line in q_expected:
                    if norm_text(line) not in qtext:
                        problems.append("%s 练习%d 题面不符" % (unit, number))
                for line in a_expected:
                    if norm_text(line) not in atext:
                        problems.append("%s 练习%d 答案不符" % (unit, number))
        self.add("ch-exercises", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_ch_evidence(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            known_records = {k for k in self.records if k != "_meta"}
            parser = self.parser_for(page)
            drawer = [x for x in descendants(parser.root, "details") if x.attrs.get("id") == "evidence"]
            shows = {x.attrs.get("data-record") for x in descendants(parser.root, "figure", "show") if x.attrs.get("data-record")}
            facts = {x.attrs.get("data-claim") for x in descendants(parser.root, "aside", "fact") if x.attrs.get("data-claim")}
            if len(drawer) != 1:
                problems.append("%s 缺少 details#evidence" % unit); continue
            body = text_of(drawer[0])
            listed_records = {rid for rid in known_records if rid in body}
            if listed_records != shows:
                problems.append("%s evidence 记录集合不符" % unit)
            listed_claims = {cid for cid in {x.get("id") for x in self.claims.get("sourced", []) if isinstance(x, dict)} if cid and cid in body}
            if listed_claims != facts:
                problems.append("%s evidence 来源集合不符" % unit)
            date_match = re.search(r"录制日期是([^。\n]*)", text_of(parser.root))
            dates = set(re.findall(r"\d{4}-\d{2}-\d{2}", date_match.group(1) if date_match else ""))
            # A chapter that uses the lesson-6 figure kinds says "录制日期" only for recorded data: a quote card's date is the day its page was fetched (build_site.py leaves it out of that sentence in such a chapter);
            # every older chapter keeps the old rule (all dates of the shown records), so their pages and this check do not change.
            _l6 = any((self.record_data(rid) or {}).get("kind") in ("window", "turnbars", "classgrid") for rid in shows)
            expected_dates = {str(self.record_data(rid).get("date")) for rid in shows if self.record_data(rid) and self.record_data(rid).get("date")
                              and not (_l6 and self.record_data(rid).get("kind") in ("quotes", "cards"))}
            if dates != expected_dates:
                problems.append("%s 录制日期集合不符" % unit)
        self.add("ch-evidence", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_ch_coverage(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            parser = self.parser_for(page)
            coverage = [x for x in descendants(parser.root, "details") if x.attrs.get("id") == "coverage"]
            if len(coverage) != 1:
                problems.append("%s 缺少 details#coverage" % unit); continue
            body = text_of(coverage[0])
            for point in source.get("points", []) or []:
                pid = point.get("id") if isinstance(point, dict) else None
                if pid and pid not in body:
                    problems.append("%s coverage 缺少 %s" % (unit, pid))
            page_ids = {x.attrs.get("id") for x in descendants(parser.root) if x.attrs.get("id")}
            for link in descendants(coverage[0], "a"):
                href = link.attrs.get("href", "")
                if href.startswith("#") and href[1:] not in page_ids:
                    problems.append("%s coverage 锚点不存在 %s" % (unit, href))
        self.add("ch-coverage", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_ch_extras(self):
        problems = []
        for unit, bid, page, source, source_path in self.source_pages():
            parser = self.parser_for(page)
            readings = source.get("readings", []) or []
            if readings:
                detail = first_descendant(parser.root, "details")
                details = [x for x in descendants(parser.root, "details") if x.attrs.get("id") == "readings"]
                links = descendants(details[0], "a", "src-link") if details else []
                if len(links) < len(readings):
                    problems.append("%s readings 链接不足" % unit)
                for link in links:
                    if not link.attrs.get("href", "").startswith("https://") or link.attrs.get("target") != "_blank" or "noopener" not in rel_value(link.attrs.get("rel")):
                        problems.append("%s readings src-link 属性不合规" % unit)
            downloads = source.get("downloads", []) or []
            if downloads:
                area = next((x for x in descendants(parser.root) if x.attrs.get("id") == "downloads"), None)
                links = descendants(area, "a") if area else []
                if not area or len(links) < len(downloads):
                    problems.append("%s downloads 链接不足" % unit)
                for link in links:
                    target, error = self.relative_target(link.attrs.get("href", ""), page)
                    if error or not target or target.relative_to(self.site).parts[:1] != ("downloads",):
                        problems.append("%s download 目标不在 downloads/" % unit)
        self.add("ch-extras", not problems, "通过" if not problems else "；".join(problems[:15]))

    def check_ch_nav(self):
        problems = []
        for bid, units in self.book_units.items():
            for index, unit in enumerate(units):
                page = self.page_for_unit(unit)
                parser = self.parser_for(page)
                navs = descendants(parser.root, "nav", "chapter-nav")
                if not navs:
                    problems.append("%s 缺少 nav.chapter-nav" % unit); continue
                nav = navs[0]
                links = descendants(nav, "a")
                prev = next((x for x in links if "上一章" in text_of(x)), None)
                nxt = next((x for x in links if "下一章" in text_of(x)), None)
                if index == 0:
                    prev_text = "" if prev else next((text_of(x) for x in descendants(nav, "span") if "上一章" in text_of(x)), "")
                    if prev or "上一章" not in prev_text or "没有了" not in prev_text:
                        problems.append("%s 第一章上一章导航不正确" % unit)
                elif not prev or self.canonical_page(prev.attrs.get("href", ""), page) != self.page_for_unit(units[index - 1]).resolve():
                    problems.append("%s 上一章导航不正确" % unit)
                if index == len(units) - 1:
                    next_text = "" if nxt else next((text_of(x) for x in descendants(nav, "span") if "下一章" in text_of(x)), "")
                    if nxt or "下一章" not in next_text or "没有了" not in next_text:
                        problems.append("%s 最后一章下一章导航不正确" % unit)
                elif not nxt or self.canonical_page(nxt.attrs.get("href", ""), page) != self.page_for_unit(units[index + 1]).resolve():
                    problems.append("%s 下一章导航不正确" % unit)
                crumbs = descendants(parser.root, "nav", "crumbs")
                if not crumbs:
                    problems.append("%s 缺少 nav.crumbs" % unit)
                else:
                    targets = {self.canonical_page(a.attrs.get("href", ""), page) for a in descendants(crumbs[0], "a")}
                    if (self.site / "index.html").resolve() not in targets or (self.site / "books" / bid / "index.html").resolve() not in targets:
                        problems.append("%s 面包屑缺少书架或本册目录" % unit)
        self.add("ch-nav", not problems, "通过" if not problems else "；".join(problems[:15]))


def parse_args(argv):
    values = {"site": None, "repo": None, "report": None, "no_video_probe": False}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--no-video-probe":
            values["no_video_probe"] = True
        elif arg in {"--site", "--repo", "--report"}:
            if i + 1 >= len(argv):
                raise ValueError("缺少 %s 的值" % arg)
            values[arg[2:].replace("-", "_")] = argv[i + 1]
            i += 1
        else:
            raise ValueError("未知参数：%s" % arg)
        i += 1
    if not values["site"] or not values["repo"]:
        raise ValueError("必须指定 --site 和 --repo")
    site = pathlib.Path(values["site"]).resolve()
    repo = pathlib.Path(values["repo"]).resolve()
    report = pathlib.Path(values["report"]).resolve() if values["report"] else repo / "projects/_ebook/site-check.json"
    return site, repo, report, values["no_video_probe"]


def main(argv=None):
    try:
        site, repo, report, no_video_probe = parse_args(sys.argv[1:] if argv is None else argv)
        result = SiteChecker(site, repo, no_video_probe).run()
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        for item in result["checks"]:
            print("%s %s: %s" % ("PASS" if item["ok"] else "FAIL", item["id"], item["detail"]))
        return 0 if result["pass"] else 1
    except Exception as exc:
        print("FAIL checker: %s" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
