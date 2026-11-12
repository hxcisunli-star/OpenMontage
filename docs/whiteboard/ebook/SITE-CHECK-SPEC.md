> **现状（2026-11-06）**：这份文件原来是交给 Codex 的任务书，现在当整站检查的**规格**用。检查脚本是 `docs/whiteboard/ebook/check_site.py`，测试是 `tests/tools/test_ebook_site_check.py`，对真站点的变异测试是 `docs/whiteboard/ebook/mutate_real_site.py`（三者都在版本库里）。运行：`.venv/bin/python docs/whiteboard/ebook/check_site.py --site $PWD/projects/_ebook/site --repo $PWD`。
> 下面的“工作规矩”“命令行”等是当时的任务书原文，路径以这里为准。**与原文不同的两条**：①`size-limits` 不再有整站 300 MB 上限（用户 2026-11-06：课程要上线，视频必须是原画质；整站大小只在结果里报告）；②新增规则 `ch-video-stream`。

# 任务书：把电子书检查脚本升级成“整站”检查脚本 `check_site.py`（和它的测试）

## 背景
上一轮你（或同类的审稿工程师）写过 `reference/check_ebook.py`（+ `reference/test_check_ebook.py`）：它检查一本离线的单章电子书，26 个测试。效果很好，也帮我们查出了书本身的问题。
现在书变成了一个**多册的网站**：书架首页 → 8 册的目录页 → 293 个章页（只有第 1 章 S2-U01 有完整正文，其余都是“正文制作中”的占位页）。网站是静态 HTML，由 `reference/build_site.py` 和 `reference/blocks.py` 生成（给你看，是为了让你知道页面长什么样；**检查要按下面的规则写，不要照抄生成器的实现**）。
真实的页面样本在 `real_pages/`（书架、第 2 册目录、第 1 章、一个占位章）；真实的数据在 `data/`。请**以 `reference/check_ebook.py` 为底**升级：能复用的代码复用，规则 id 沿用（`no-external-load`、`no-claude-runtime`、`no-secret-or-path`、`no-experiment-labels`、`page-basics` 等），并加上整站的新规则。

## 工作规矩
- 只写工作区 `/home/MyProject/codex-ws-sitecheck` 里的文件，产出放 `out/`：`out/check_site.py`、`out/test_check_site.py`。不读工作区外的文件，不联网，只用 Python 3 标准库（视频探测用命令行 `ffprobe`/`ffmpeg`，机器上有）。
- 引用原话每条不超过 120 字；读不到写“未核实”。最终消息只给下面“最终消息”要求的 JSON。

## 命令行
```
python3 check_site.py --site DIR --repo DIR [--report FILE] [--no-video-probe]
```
- `--site`：网站根（里面有 `index.html`、`books/`、`assets/`、`media/`、`downloads/`）。
- `--repo`：数据根，里面按这些相对路径放数据（`data/` 里就是一个这样的数据根）：`projects/_ebook/outline.json`、`projects/_ebook/books.yaml`、`projects/_ebook/chapters/*.json`（有正文的章的源文件）、`projects/agent-what-is-llm-cn/validation/records.json`、`validation/claims_used.json`、`artifacts/script.json`（旁白）、`exports/metadata/exercises.txt`。
- 报告 `--report`（默认 `<repo>/projects/_ebook/site-check.json`）：`{"pass": bool, "checks": [{"id","ok","detail"}], "failed": [ids]}`；终端逐项打印 PASS/FAIL；全过退出码 0，否则 1。`--no-video-probe` 不调 ffprobe（测试用）。
- `books.yaml` 是 YAML：只有简单的映射、列表和字符串，**没有 PyYAML 可用**，请自己写一个够用的小解析器（只需读出 `books[].id/title/stages[]` 和 `series.name`），并给它写测试。

## 网站结构（相对 `--site`）
```
index.html                      书架：8 张 a.book-card（href 指向 books/<册id>/index.html）
robots.txt                      "Disallow: /"
assets/book.css, book.js, search-index.js, fonts/（.ttf 和 FONT-LICENSE.txt）, img/（teacher.png、robot.png）
books/<册id>/index.html         册目录：按阶段分组，每章一个 li[data-unit="S2-U01"]，里面有 a[href="S2-U01.html"]，a 里有 span.chip-path 和 span.chip-st（“有正文”class=on，“有视频”class=vid，“正文制作中”class=off）
books/<册id>/<单元id>.html      章页：有正文的章有 main.main[data-unit]；占位章有 div.callout.warn（文字含“正文还在制作中”）
media/<单元id>/…                有视频的章的视频、封面、抽帧
downloads/…                     章页提供下载的文件
```
所有站内链接都是**相对路径**（章页里是 `../../assets/…`、`../b2-llm/S2-U01.html` 这样），而且指向页面时写明文件名（`…/index.html`、`…/S2-U01.html`），这样用文件夹直接双击打开也能用。

## 规则（每条一个固定的 id；失败要在 detail 里说清楚哪个文件、哪里）
**整站**
- `site-files`：上面列的固定文件都在；`robots.txt` 含 `Disallow: /`；`assets/fonts/FONT-LICENSE.txt` 含 `SIL Open Font License`；`assets/fonts/` 至少一个 `.ttf`。
- `books-complete`：`books.yaml` 的每册，stages 里每个阶段在 `outline.json` 的 `stages[].id` 里；每个单元在**所有册里恰好出现一次**；单元总数等于 `outline.json` 的 `unit_count`（293）；`books/<册id>/index.html` 里 `li[data-unit]` 的顺序、个数和 books.yaml 展开后的单元顺序完全一致；册目录里的“共 N 章”（出现在 `.eyebrow` 文字里）等于该册章数；书架上 `a.book-card` 的个数等于册数，`data-units` 属性（逗号分隔）等于该册单元顺序。
- `chapter-pages`：每个单元都有 `books/<册id>/<单元id>.html`；有 `chapters/<单元id>.json` 的单元，页面里有 `main[data-unit="<单元id>"]`，册目录里对应 li 的 `span.chip-st.on` 文字是“有正文”，且不含“制作中”；没有源文件的单元，页面是占位页（`div.callout.warn` 含“正文还在制作中”、不含 `section.sec`、不含 `<video>`），目录里是 `span.chip-st.off`。
- `placeholders-honest`：占位页必须含：大纲里这个单元的 `goal` 文字（去掉反引号和空白后是页面文字的子串）、先修单元的链接（`outline.json` 里 `prereq` 的每个存在的单元都有一个 `a.pre`，href 指向它的页面）。
- `prereq-links`：所有 `a.pre` 的 href 都能解析到站内真实存在的页面。
- `search-index`：`assets/search-index.js` 以 `window.SEARCH_INDEX = ` 开头、以 `;` 结尾，中间是 JSON 数组；条目 `id` 集合等于全部单元；`w` 为 true 的恰好是有源文件的章；每条的 `b`（册 id）和 `n`（册内序号）与 books.yaml 一致；有正文的章，`x`（正文摘录）非空。
- `no-external-load`、`no-claude-runtime`、`no-secret-or-path`、`no-experiment-labels`：沿用 `reference/check_ebook.py` 的规则，范围扩大到整站的 `.html/.css/.js/.txt/.json`（二进制文件不当文本扫）。`no-external-load` 的例外：只有 `class` 含 `src-link` 的 `<a>`（来源链接）可以是 `https://`，并且必须带 `target="_blank"` 和含 `noopener` 的 `rel`。`no-secret-or-path` 里，禁用的路径样式沿用，**但站内的 `../` 相对链接是正常的**。
- `relative-links-resolve`：所有页面里的相对 `href/src/poster` 和 CSS 的 `url()`，解析（相对该页面所在目录，处理 `..`）后必须落在站点根里、并指向真实存在的文件；指向页面的链接必须以 `.html` 结尾（不得指向目录）；`#锚点` 必须在目标页面里有对应 id（同页或别的页，别的页要去读）；不得以 `/` 或 `file:` 开头。
- `page-basics`：每个页面都有 `lang="zh-CN"`、非空 `<title>`、viewport meta、`<meta name="robots" content="noindex, nofollow">`、对 `assets/book.css` 的引用；每个 `<img>` 有非空 alt；页内 id 不重复；全站每页都能被 `html.parser` 解析。
- `size-limits`：每个 html ≤ 3 MB。**整站不设大小上限**（2026-11-06 取消），只在结果的说明里报告整站大小与 `media/` 的大小。
**有正文的章（对每个 `chapters/<单元id>.json` 各检查一次；下面的“源文件”指这个 JSON）**
- `ch-header`：页面 `h1` 文字等于该单元在 outline 里的标题；有 `p.lesson-title` 等于源文件 `lesson_title`；有 `div.basic` 含 `basic_question`；`div.takeaway li` 的个数和文字等于源文件 `takeaway`。
- `ch-video`（源文件有 `video` 才查）：恰好一个 `video#lesson-video`，`data-duration` 是数；`<source src>` 和 `poster` 指向的文件存在；`ffprobe` 的 `format.duration` 与 `data-duration` 相差 ≤ 0.05 秒，且有视频流和音频流（`--no-video-probe` 时跳过并在 detail 写 skipped）；`button.seek` 的个数、`data-seek`（秒）、文字与源文件 `video.chapters` 一致（`data-t` 属性是显示用的时间，不算按钮文字）；所有 `data-seek`（按钮和抽帧）≥ 0 且 < `data-duration`。
- `ch-video-stream`（源文件有 `video` 才查，2026-11-06 新增，代替整站大小上限）：①章源的 `video.file` 必须是 `projects/<课>/exports/video/output.mp4`，且站点里页面播放的那个文件就是它本身（同一个文件，或大小与 sha256 相同）——重编码过的“网页版”不允许，线上要原画质；②mp4 顶层 `ftyp` 开头，`moov` 在 `mdat` 之前（边下边播，配合服务器的 Range 拖进度）；③（没加 `--no-video-probe` 时）`ffprobe` 看出视频流是 H.264、音频流是 AAC（不算封面那条 attached_pic 视频流）。
- `ch-frames`：`a.frame` 的个数和 `data-seek`、`img` 的 alt 与源文件 `frames` 一致；图片存在且宽度 ≥ 480（读 jpg/png 头）；每张的 `q.narr` 文字去掉空白和标点后必须是 `script.json` 某一段 `text`（同样去标点）的子串，且与源文件 `frames[].narr` 一致。
- `ch-sections`：`section.sec` 的个数、id（`sec-<id>`）、`h2` 文字和顺序与源文件 `sections` 一致；每节的块个数不得为 0。
- `ch-shice`：`figure.show` 每个都有 `data-record`，在 `records.json` 里；`figcaption.rec` 含该记录有的这些字段：模型名（`model` 最后一段）、`date`、`mode`、“{n} 遍”，以及 `span.tag-shice`；`kind=towers` 的每一组 `text` 和 `count` 在块文字里；`kind=chat` 且有 `sum` 的，每条 `sum[].text` 在块文字里；`kind=task` 的，`answer` 的前 40 个字和每条 `check[].text` 在块文字里；块里的“{n} 遍”和日期与记录一致。至少 6 个 `figure.show`。`kind=classgrid` 的 `labeler` 写实际做法：含“AI”或“程序”（第 8 课起主实验由程序按规则判），不得含“真人”“人工”。
- `ch-sources`：`aside.fact` 每个的 `data-claim` 在 `claims_used.json` 的 `sourced[].id` 里；块文字含该条 `statement`，且含“适用范围：”加 `scope`（逐字）；有 `span.tag-source`；至少一个 `a.src-link`，href 是 `https://`，且文字（去掉 `https://`）等于 href 去掉 `https://`。
- `ch-metaphors`：`div.term` 每个有 `b.word`、`span.tag-metaphor`、非空 `p.gap`（至少 6 个汉字）。
- `ch-thinks`：`details.think` 每个都没有 `open`；个数不少于源文件 `sections` 里 `think` 块的个数。
- `ch-exercises`：`article.exercise` 的个数等于 `exercises.txt` 里“练习X【”开头的题数；每题有 `.q` 和没有 `open` 的 `details.answer`；题面（`.q`）文字包含 `exercises.txt` 对应题“答案”之前的每一行（去空白），答案（`details.answer`）包含“答案”之后、下一题或“你的学习记录”之前的每一行（去空白）；**答案不泄露**：`北京`、`校门口咖啡`、`2025`、`2026`、`知味咖啡` 不得出现在任何 `.q` 里。
- `ch-evidence`：`details#evidence` 存在；它列出的记录号集合等于页面里所有 `data-record` 的集合；它列出的来源号集合等于页面里所有 `data-claim` 的集合；正文里写的“录制日期是 …”里的日期集合等于这些记录的 `date` 的集合。
- `ch-coverage`：`details#coverage` 存在；源文件 `points` 里的每个 `id` 都在其中列出；它里面每个 `href="#…"` 指向页面里存在的 id（`#exercises` 也算）。
- `ch-extras`：源文件有 `readings` 的，`details#readings` 里每条都有 `a.src-link`（https、`target=_blank`、`rel` 含 `noopener`）；有 `downloads` 的，`#downloads` 里每个链接指向 `downloads/` 里真实存在的文件。
- `ch-nav`：每个章页有 `nav.chapter-nav`，里面“上一章／下一章”的链接指向同册里相邻的单元页面（第一章没有上一章、最后一章没有下一章，页面上写“没有了”）；面包屑 `nav.crumbs` 里有指向书架和本册目录的链接。

## 测试 `test_check_site.py`（`python3 -m unittest` 能直接跑）
- 在临时目录里自己造一个**迷你站点**和迷你数据根：3 个单元、2 册，其中 1 个单元有正文（用字符串拼 HTML，严格按上面的 DOM 约定；有一个很短的视频：用 `ffmpeg` 造 2 秒的 mp4，图片用 `ffmpeg` 造）。合格站点必须全部 PASS。
- **每条规则至少一个反例**，每次只破坏一件事（例如：某册少一个单元、一个单元出现在两册、占位页缺“正文还在制作中”、占位页出现 `<video>`、搜索索引少一项、加一个外部 `<link href="https://…">`、一条 `../../` 链接指向站外、一个页面链接指向目录、锚点不存在、`a.pre` 指向不存在的页面、章页的 `q.narr` 改成旁白里没有的句子、`details.answer` 加 `open`、答案关键值进了题面、证据抽屉少一个记录号、覆盖矩阵少一个点、`robots.txt` 不含 Disallow……），断言预期的规则 id 在 `failed` 里。再加“不空过”的测试：把章页换成几乎空的页面，必须多个 id 失败。
- 还要测：小 YAML 解析器能读 `books.yaml` 的真实样子（用 `data/projects/_ebook/books.yaml` 的内容当测试输入）。
- 对 `real_pages/` 里的真实页面**不要求**整站通过（它只有 4 个页面），但你可以用它们核对你的选择器写对了（例如 `books/b2-llm/S2-U01.html` 能被各条 ch-* 规则正确解析）。

## 最终消息
只给一个 JSON：`{"files": ["out/check_site.py", "out/test_check_site.py"], "tests_run": N, "tests_passed": N, "rule_ids": [...], "known_limits": ["…"], "deviations_from_spec": ["…"]}`。`known_limits` 如实写检查做不到的事；`deviations_from_spec` 写你没按任务书做的地方和原因（没有就空数组）。
