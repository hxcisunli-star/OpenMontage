# 交接：《智能体拆拆装装》第 2 课——选 B 改动已做完，等用户重说“成片通过”（写于 2026-11-03）

> 读者：新开的 Claude Code 会话。目的：读完它就能不出错地接着做第 2 课的发布阶段。事实来自本机文件、检查点和这一轮会话的记录；没验证的地方直接写“未验证”。
> 项目：`projects/agent-tokens-window-cn`（课名在 `scripts/lesson_title.txt`：“你好”两个字，为什么算五个词元？）。系列总交接仍是 `docs/whiteboard/handoff-agent-series-20261029.zh-CN.md`；本文只写第 2 课现在到哪一步、下一步怎么走、哪里容易错。

> **最终状态（2026-11-04 UTC 02:36）：第 2 课已“发布通过”并记录（approvals.jsonl 共 9 条；发布页上用户的记录是 `overall: ok`、无备注），复盘 `docs/whiteboard/retro/agent-02.md` 已写，登记表加了 E110–E113（`whiteboard_registry.py coverage/render/check` 全过，`checklists/02-script.md`、`06-compose.md`、`07-publish.md` 已重新生成）。`whiteboard_gate.py status` 现在是“没有进行中的课程，已发布 45 课”。只剩一件事：等用户说“提交”（见第 7 节；本课发布阶段之后的全部文本源改动、复盘、登记表、清单、本文都还没提交；渲染机心跳那两个文件不是本课的，不要提交）。下一课由用户另定。下面所有 3.x 步骤都已做完，只作记录。**
>
> **最终状态（2026-11-04 UTC 05:09）：第 2 课已发布通过（第二次，文字类修改之后；approvals.jsonl 共 10 条）并已提交。复盘 `retro/agent-02.md` 已补第 3 次复核，登记表到 E115。`gate status`：没有进行中的课程，已发布 45 课。下一课由用户另定。下面所有“等用户选／等发布通过”的段落都已过期，只作记录。**
>
> **最新（2026-11-04）**：用户在复核页选了“文字类 A、视频类 A”，T1–T11 已全部改完，站点、离线副本、成品包已重建，**发布检查点已重写为 awaiting_human，现在只等用户重说“发布通过”**（视频没动）。收到后：先读 `publish_l2/review`，`approve agent-tokens-window-cn publish "<原话>"`，复盘 `docs/whiteboard/retro/agent-02.md` 补一句第 3 次复核，提交仍要用户说。下面这段“等用户选”已过期。
>
> **发布通过之后的补充（2026-11-04）**：做了第 3 次复核（只核复审之后新写的 69 处；Codex sol×2＋Antigravity Flash×2），结果和裁决在 `validation/fact-check.md` 末尾，原始输出在 `validation/research/review3/`，审阅页 `https://claude.ai/artifact/BPLzFR3uZFPyLexjPkVoUr`（用户在页上选“文字类 A/B/C”和“视频类 A/B/C”，存 `review3_l2/decision`；该页没被监听，用户说选好后用 ArtifactData 读）。**等用户选**；没选之前不要改任何交付物。选文字类 A/B：改章节／简介／练习（T1–T11 清单见 fact-check.md）后重建站点、离线副本、成品包，再请用户重说“发布通过”；选视频类 B/C 才动成片。
>
> **状态更新（2026-11-03，同日稍后）**：用户重说了“成片通过，进入发布阶段”（已记录，approvals.jsonl 共 8 条），又说“继续”，**第 3 节的 3.2→3.1→3.3→3.4→3.5→3.6→3.7 已全部做完**：简介／字幕 195 条／章节（0:00、1:45、3:32、4:56）、封面片头（发布成片 387.82 秒，md5 `0ec3a9e86ebb85ef2cae981c0156efa7`）、电子书第 2 章与 12 张新取帧、站点与离线副本（29/29，第 1 章页面不变）、成品包（733 文件，第 1 课 359 个与基线逐文件相同）、发布检查点（`awaiting_human`）、审阅页第 3 版（同一地址）。**现在只等用户说“发布通过”**，之后做 3.8（读 `publish_l2/review`、`approve … publish`、复盘 `agent-02.md`、登记表、`whiteboard_timeline.py`）。下面的 3.x 步骤保留作为记录和返工参考，**不要重做**。另：这一轮重做发布包后的文本源改动（`publish_prep.py`、`assemble_chapter.py`、`build_publish_page.py`、`publish_meta.json`、导出的元数据等）和本文的这几处修改都**还没提交**。
>
> 这一轮实际踩到、值得记的：封面拼接脚本只沿用 `metadata.json` 里已有的 `chapters_original`，所以先手动换成新章节再拼；`refresh_exports.py` 要在封面拼接之后跑（它读拼接后的 `chapters.txt`）；`publish_prep.py` 里加了对新旁白措辞的断言（旁白版本必须是 `v1.2-draft`）；整站检查脚本的参数是 `--site`、`--repo`、可选 `--report`、`--no-video-probe`，对离线副本跑时给 `--report` 到临时文件，别覆盖 `projects/_ebook/site-check.json`。

## A. 粘贴给新会话的开场提示词（整段复制）

```
继续做《智能体拆拆装装》第 2 课（项目 agent-tokens-window-cn）。请严格按这个顺序，做完前不要动任何文件、不要渲染、不要提交：
1. 读 CLAUDE.md，再读 AGENT_GUIDE.md（仓库规定回应任何消息前先读）。
2. 读 docs/whiteboard/handoff-l2-publish-20261103.zh-CN.md 全文（这是本次交接）。
3. 读 .claude/skills/whiteboard-lesson/SKILL.md，以及 .claude/rules/ 下两份白板规则；再读 docs/whiteboard/checklists/00-always.md 与发布阶段清单。
4. 跑 .venv/bin/python docs/whiteboard_gate.py status，再读记忆索引 /root/.claude/projects/-home-MyProject-OpenMontage/memory/MEMORY.md 和 project_l2_planning.md。
然后用中文、精简地回复我：①你接手后的理解（三五句，含检查点现状）；②我现在要做的事（交接文档第 3 节）；③你要我先定的事。回复后等我的口令，不要自己往下走。
```

## 1. 一句话现状

用户在复审页选了 **B**：只改视频旁白里三处不够准的话（V1 窗口与最大输出、V2 三页文档、V3 “只占一个词元／个数固定”的限定）。**视频已改完并重渲，成片检查点是 `awaiting_human`，等用户重说一遍“成片通过，进入发布阶段”**（E60）。在他说之前，发布阶段的东西（封面片头、简介章节时间、电子书取帧、成品包）都还是**改前的旧版**，不能当成最新。“发布通过”还没说；用户 2026-11-03 又说了一次“提交”，已提交：外层 `c99076a`（`blocks.py`、测试、本交接文档，已推 fork，没推 origin）、projects 本机库 `219226a`（第 2 课选 B 后的文本源快照 61 个文件，不推送）；更早的是 `65eb067`／`342451c`。**提交不等于“发布通过”。**

检查点（`.venv/bin/python docs/whiteboard_gate.py status`）：research 完成；proposal、script、scene_plan、assets、edit 已批准；**compose 等用户**；publish 等用户。`approvals.jsonl` 里有 7 条旧口令，其中那条“成片通过，进入发布阶段”对的是**改旁白之前的成片**，所以必须用户重说，说了用 `approve` 追加一条。

## 2. 这一轮做了什么（不要重做）

**旁白 v1.2（只三处，s1 逐字不变）**：作者文件由 `code/make_author_files_v3.py` 生成（旧版在会话临时目录，不用）；对照表在 `validation/fact-check.md` 末尾“复审后的处置：用户选 B”。

| 编号 | 段 | 新旧要点 |
|---|---|---|
| V3 | s2 | 字母那句加“按公开的切字规则，它只占一个词元”；“只知道个数固定”→“只知道这几次测，个数是固定的”；“所以，你好自己只占一个词元”→“所以，在这两个模型里，你好自己只占一个词元” |
| V2 | s3 | 去掉“却”“两页还出自同一家公司”；改成“三页，三个数。我读了读，它们各讲各的，也都只是个大概。搭档挠挠头：那我该信谁？谁也别全信。” |
| V1 | s4 | “能读多少，能写多少，都有个总上限”→“一次能装多少，有个总上限”；“你发得越长，留给它回答的地方，就越少”后加“快装满时最明显。另外，它一次最多能写多长，另有专门的上限。” |

**连带改的**：词汇表“上下文窗口”“上下文”两条释义；画面提示补两条；板书四处（K2“公开规则里占一格”、K2 便签“没拆开看，这几次个数固定”、K3 “同一家公司”标签与红括号换成“各讲各的”、K4 新增“一次最多写多长／另有专门的上限”两行小标签，第一次压在车厢框上，下移到 y622/656 后重渲）；只重配了 `s2_1`、`s3`、`s4_1` 三个配音片段，`s1`、`s2_2`、`s4_2` 与改前逐字节相同。

**产物现状**：`renders/final.mp4` 385.80 秒、11574 帧、md5 `184dc7c280dc7c9177bbe72037c6a42d`、−16.5 LUFS，**没有封面片头**；`verify` 全过、真实排版检查 0 错误 0 警告、联系表与改动处全尺寸帧都看过（`validation/compose-notes.json` 写了所见，旧版另存 `compose-notes.before-B.json`）；音效 107 点；`edit_deviations.json` 追加了 4 条。配音时间轴 `assets/audio/narration_timeline.json`：s1 0.3–102.06、s2 102.76–209.12、s3 209.82–292.94、s4 293.64–384.4；第一题静默 174.68→177.68，第二题 345.0→348.0。渲染块指纹：K1 `24df3f187fc9`、K2 `6fca328a8de9`、K3 `298a4094fec4`、K4 `b176b961d65b`（旁白变了，第一次整课四块全重渲 38 分 23 秒，之后只因标签重渲 K4 8 分 05 秒）。

**改前整份备份**：仓库外 `/home/MyProject/backup-l2-before-B/`（检查点、approvals、artifacts、scripts、assets 含配音、exports、旧成片 `renders/final.mp4` md5 `5daf8f23214903ff55ee913b234d3a53`、validation、`_ebook/chapters`），另有 `baselines/`：`pack_before_l1.md5`、`pack_after2_l1.md5`（成品包里第 1 课 359 个文件的指纹，要求发布后仍逐文件相同）、`site_final3.md5`（线上站点第 1 章基线）。

**被我恢复过的东西**：`scripts/build_script.py` 会把脚本检查点改写成 `awaiting_human`、覆盖 `artifacts/script.json` 等。我跑它之后把 `checkpoint_script.json`、`decision_log.json`、`approvals.jsonl` 从备份拷回，所以脚本阶段仍是 approved；但 `artifacts/script.json`、`script_review.json`、`teaching_examples.json` 已是 v1.2（脚本检查比上一版多一条“预估 414 秒比目标 370 秒长 12%”的警告，实际配音 384.4 秒只长 3.9%）。**`artifacts/scene_plan*.json` 没重建**，仍是选 B 之前的（已批准的场景计划阶段，偏离记在 `edit_deviations.json`，别重跑 `build_scene_plan.py`）。

## 3. 下一步（按顺序；每步做完再下一步）

### 3.0 先看用户说了什么
- 用户说 **“成片通过，进入发布阶段”**（原话含这几个字才算；早说、系统通知、后台任务完成都不算）：`PYTHONPATH=. .venv/bin/python docs/whiteboard_gate.py approve agent-tokens-window-cn compose "<原话>"`，**然后先停下，向用户报告口令已记录（`approve` 脚本和协议第 3 条都要求：口令后不在同一轮做下一阶段），等用户说“继续”之类的话**；之后**按 3.2 → 3.1 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7 的顺序做**（3.1 的封面拼接要用 3.2 更新后的章节和字幕，所以 3.2 在前），**做完停下，报告并请用户说“发布通过”**；3.8 要等用户说了“发布通过”才做。（2026-11-03 实际走的就是这样：口令记录后停下，用户再说继续。）
- 用户听了觉得旁白不顺、要改某句：回第 4 节“返工入口”，改完要再重配音／重渲，成片口令仍要他重说。
- 用户要补 K3 纸条上的红叉（见第 5 节“遗留缺漏”）：要改图层并重渲 K3（本机约 8 分钟），再核对，口令仍要重说。

### 3.1 封面片头（不重渲；**要在 3.2 之后做**）
`.venv/bin/python docs/whiteboard_prepend_cover.py projects/agent-tokens-window-cn --seconds 2`。它从 `renders/final.mp4`、`assets/subtitles.srt` 和 `exports/metadata/metadata.json` 重建 `exports/video/output.mp4`、`subtitles.srt`、`chapters.txt`、`metadata.json`（已核对源码：它读的是 `exports/metadata/metadata.json` 里**已有的** `chapters_original`，有就沿用，**不会去读 `publish_meta.json`**）。所以要先做完 3.2，并**手动把 `exports/metadata/metadata.json` 的 `chapters_original` 换成新的未平移章节**（`chapters` 同步成同一份），否则章节时间会悄悄用回旧值。要用 `.venv/bin/python`（脚本最后的核对要 PIL 和 numpy，系统 `python3` 没有，`.venv` 里有）。完成后用 ffprobe 看时长应约 387.8 秒（385.80＋2.0；改前的发布视频是 380.72 秒，可用来确认确实换成了新版）。
**不要跑 `scripts/finish_publish.py`**：它会把成片重导出成不带封面的版本。

### 3.2 简介、字幕、章节、缩略图（`scripts/publish_prep.py`）
- 读脚本头注释后再跑：`PYTHONPATH=. .venv/bin/python projects/agent-tokens-window-cn/scripts/publish_prep.py`。它做缩略图（默认 `THUMB_T=101.5`，在 K1 里，K1 板书没变，但仍要过 `docs/whiteboard_thumb_check.py` 的检查）、SRT（按字幕估时）、章节（按配音时间轴的段起点：新 s2/s3/s4 起点 102.76、209.82、293.64，取整后约 103、210、294，旧的是 103、210、292）、简介。
- **先改它里面还写着旧说法的地方**：章节第四条标题“窗口：模型一次能读多少”→改成与新旁白一致（如“窗口：模型一次能装多少”）；简介里“上下文窗口：模型一次能读多少、能写多少的总上限，输入和输出共用”（`exports/metadata/description.txt` 第 10 行，源在 `publish_prep.py`）要按新旁白和“最大输出另有上限”改；脚本里对简介数字与旁白做断言，改了措辞断言可能要跟着改，**断言不要删，要改对**。
- 这脚本不写 `exports/video`；它写 `publish_meta.json`。之后用 `scripts/refresh_exports.py` 把已导出的 `description.txt`／`metadata.json` 对齐（它不会动视频）。章节的新值写在 `publish_meta.json` 的 `chapters`；`exports/metadata/metadata.json` 里的 `chapters_original` 是首次导出时留下的旧值（现在是 0、103、210、292 秒），**publish_prep 不会更新它**，要手动同步（见 3.1）。同步后跑 3.1，核对 `chapters.txt` 的时间等于“段起点取整＋2”，首条仍是 0:00；不对就修正后再跑 3.1（封面拼接脚本可重复运行，每次从源重建）。

### 3.3 电子书第 2 章同步（`code/assemble_chapter.py`）
这一章里还写着旧旁白的说法，要同步（脚本的 EDITS 是“旧→新”列表，每条必须在原稿里恰好命中一次；改完连跑两次比指纹，E104）：
1. 第 52 行附近：“（视频里的说法是“能读多少、能写多少”）”——视频现在说“一次能装多少，有个总上限；它一次最多能写多长，另有专门的上限”，章里的括号要改成新的说法。
2. `f05` 的 `alt`（便条文字）和 `narr`（“所以，在这两个模型里，你好自己只占一个词元：两个字，合成了一整块。”）；`f10` 的 `narr`（新句“三页，三个数。我读了读，它们各讲各的，也都只是个大概。”）和 `alt`（可加“各讲各的”）；其余 9 张的 `narr` 对着新字幕逐条核一遍。
3. 12 张取帧的时间 `t`（**成片时间轴，不含封面**；章里的 `seek` 会自己加 `COVER=2.0`）。我按新字幕把同一句话的起点算过：f01–f04 不变（47.5、57.0、72.5、93.0）；f05 144.7→约 146.25；f06 159.3→约 161.21；f07 185.0→约 184.68；f08 207.9→约 207.58；f09 228.3→约 228.58；f10 272.0→取约 272.5（三张文档卡已写满、标签“各讲各的”已出现，274 秒帧看过是这样）；f11 314.7→约 314.44；f12 345.0→约 352.12（官方文档错误卡）。**这些是由字幕推算的，取帧后必须逐张看全尺寸图再定**。
4. 取帧命令（从无封面的成片取）：`ffmpeg -v error -y -ss <t> -i renders/final.mp4 -frames:v 1 -vf scale=1280:720 -q:v 3 assets/ebook-frames/fNN.jpg`。
5. 章节页其余内容（三个页内小练习、练习题、术语表）不受旁白影响，不用动；章里“连同一家公司（阿里云）的两页文档写的也不一样”是章自己的事实陈述（阿里云两页确实不同），可保留。

### 3.4 站点与离线副本
`PYTHONPATH=. .venv/bin/python projects/agent-tokens-window-cn/code/assemble_chapter.py`（连跑两次）→ `.venv/bin/python docs/whiteboard/ebook/build_site.py --link-media --export projects/agent-tokens-window-cn/exports/ebook` → `python3 projects/_ebook/site_check/out/check_site.py --site projects/_ebook/site --repo .`（29 条规则全过；离线副本再用同一脚本对 `exports/ebook` 跑一次，参数写法看脚本头）。线上站点由用户电脑上的服务进程静态提供（`bash docs/whiteboard/ebook/serve_ctl.sh status` 看是否在跑；重建站点不需要重启，改了服务器代码才要重启）。**第 1 章页面与基线逐字节相同**：对照 `/home/MyProject/backup-l2-before-B/baselines/site_final3.md5`。
可选再跑页内练习的真实浏览器检查：`cd remotion-composer && FONTCONFIG_FILE=<含字体的 fonts.conf> node ../projects/agent-tokens-window-cn/code/e2e_labs_l2.cjs ../projects/_ebook/site <输出目录>`（上一轮 ok:true；章里练习没改，只在改了练习时才需重跑）。

### 3.5 成品包
`PYTHONPATH=. .venv/bin/python docs/whiteboard_release_pack.py --series agent`（会清空并重建 `projects/智能体拆拆装装_成品/` 和 `.zip`，约 449 MB；文件夹名带弯引号“ ”）。核对：第 1 课 359 个文件与 `baselines/pack_after2_l1.md5` 逐文件相同；第 2 课里的视频是带封面的新版（md5 与 `exports/video/output.mp4` 相同）；电子书离线副本与 `exports/ebook` 逐文件相同；文本扫描无 IP、端口、密钥、本机路径、试验品标注（命中“密码”二字都是大纲占位章里的课程话题，不是泄露）。

### 3.6 发布检查点与审阅页
- 检查点：用 `lib.checkpoint.write_checkpoint(Path("projects"), "agent-tokens-window-cn", "publish", "awaiting_human", …)` 重写（第一个参数传 `Path`，不是字符串；参照上一次的写法：读现有 `checkpoint_publish.json` 的 `artifacts` 与 `metadata`，更新视频时长、md5、`ebook_check`、包路径），状态仍 `awaiting_human`。
- 审阅页：`code/build_publish_page.py` 生成 `review/publish/publish-review.html`（它有 4 个自带测试），要在页首写清“选 B 已执行、视频已改、成片已重新通过”，并把本文第 2 节里“没验证的”列进去；然后用 Artifact 工具更新**同一个地址** https://claude.ai/artifact/5f8HmYv5ZY7wVwHAwdJudY（本会话没读过它，先 `action: read` 再发布；页面带共享记录 `publish_l2/review`，不要清空）。复审页 https://claude.ai/artifact/HLPcbq1oQuWFYRChsFwegj 的选择 `review2_l2/decision` = `{"overall":"B"}` 不要改。

### 3.7 回复用户并停下
只讲要他决定的：发布包是否按新版出齐、没验证的有哪些、请他说“发布通过”。**不要自己写“发布通过”进检查点。**

### 3.8 用户说“发布通过”之后
先 `ArtifactData get publish_l2/review`（读他在发布页上的选择：电子书“换回原句”之类，选了就按选择改再重出包）；`approve agent-tokens-window-cn publish "<原话>"`；写复盘 `docs/whiteboard/retro/agent-02.md`（模板 `docs/whiteboard/retro-template.md`）；教训分流进登记表 `docs/whiteboard/lessons-learned.yaml`（接在 E109 之后），跑 `whiteboard_registry.py coverage/render/check`；跑 `docs/whiteboard_timeline.py agent-tokens-window-cn` 记每个口令的生产时间。**提交只在用户说“提交”时做**，见第 7 节。

## 4. 返工入口（用户听了成片要改某句时）

1. 改 `code/make_author_files_v3.py` 里对应句（旁白唯一来源，运行它会重写 `scripts/narration.json`、`section_data.json`、`glosses.json`、`number_claims.json`），先 `ast.parse` 确认，**另起一条命令**再运行（用户的规矩：改与运行分开）。
2. `build_script.py` 会覆盖脚本检查点——运行前把 `checkpoint_script.json`、`decision_log.json`、`approvals.jsonl` 备份，运行后拷回（本轮就是这样做的，仍是 approved）。画面提示相邻间隔要 ≤10 秒，超了脚本检查会报错，补一条提示。
3. 删 `assets/audio/narration_raw/<片段>.wav` 和 `assets/audio/narration/<片段>.wav` 只删改过的片段，跑 `scripts/gen_tts.py`（只补缺失的；配音是 DashScope Cherry，唯一的付费服务）→ `scripts/make_captions.py` → 改板书文件 `_board_s*.py`（锚点用旁白的子串，随时间轴走）→ `scripts/build_parts.py`（lint 0 错、最后一笔余量 ≥0.6 秒）→ `docs/whiteboard_sfx.py apply … --cues all` 和 `cues`（每次重建后都要重跑）→ `docs/whiteboard_layout_check.py … --stills 6`（约 4 分钟）→ `docs/whiteboard_render.py … --plan --local` 看哪些块要重渲 → `scripts/render_final.py --local`（后台跑，等通知，不轮询）→ `docs/whiteboard_verify.py verify` → **逐张看联系表和改动处的全尺寸帧** → 改 `validation/compose-notes.json` → `scripts/finish_compose.py`。
4. 命令都要在仓库根目录、`PYTHONPATH=.`、用 `.venv/bin/python`；Bash 沙箱在本机总失败，带 `dangerouslyDisableSandbox` 并说明原因。

## 5. 已知遗留缺漏与没验证的

- **K3 红叉没显示（已批准成片里本来就有，不是选 B 引入）**：K3 纸条“一个汉字／一个词元”上的两笔红线 `s3_red_cross`（`scripts/_board_s3.py`，坐标 520–610×610–700）画在纸条图层下面被盖住，新旧成片全尺寸帧都看不到。我上一版 `compose-notes.json` 曾写“红叉划掉纸条”，**写错了**，已在新笔记更正并告诉用户。要补：让红叉画在纸条之上（先查纸条是哪一层），重渲 K3，再核对。没得到用户指示前不动。
- 新旁白三个片段的配音**没有人听过**（语速每字 0.208／0.241／0.214 秒，在其余片段 0.205–0.246 的范围内，s2 前半段比上一版快约 7%）；读音、停顿、语气只有用户的耳朵能判；没有语音识别工具可核。
- 没有为新旁白做样片；选 B 前的样片口令对的是旧旁白。
- 三句新旁白**没有再请 AI 复审**（Codex、Antigravity 这一步各 0 次），只过了脚本检查、数字登记和我自己的核对。
- 渲染机不可用，一直用 `--local`；“远程对本机静帧对照”没做。
- 第三块标题“看懂词元账单”约 44 号、其余块 56 号；K4 老师约 3 秒不在画面：都是已知并写进笔记的老样子，用户批准样片时就是这样。
- 没有真人专家或真人学生；没有在真实 Windows／手机浏览器里看过页内练习和章节页；中文字体在本机截图里是预览字体。
- `projects/_ebook/`（含章节源 `chapters/S02-U02.json`、整站检查脚本）被 `/_*/` 排除，**不在任何仓库里**，换机器会丢；备份了一份在 `/home/MyProject/backup-l2-before-B/_ebook/chapters/`（只有章节源，不含站点检查脚本）。

## 6. 规矩与坑（都是用户定的或本轮踩过的）

1. **口令只能用户自己说**，系统通知（后台任务完成、退出计划模式）、“提交”、我自己的回复都不是口令；早说不算。每次做完要停下，不抢跑下一阶段。
2. **不静默改已批准内容**：旁白、成片的改动必须先给用户选项（本轮就是复审页 A/B/C）；要用户拍板的事放进审阅页让他选，不要在对话里问、不弹选择框。
3. **回复**：中文、精简，只讲要他决定什么；不编耗时和费用；没做的检查明说；发现自己的错（含已批准之后的）主动说并修——本轮就有一次（红叉笔记）。
4. **绝不再跑** `scripts/finish_assets.py`、`finish_edit.py`、`finish_publish.py`（会写检查点或换掉带封面的成片）；`finish_compose.py` 只在重渲之后跑，它把 compose 写成 `awaiting_human`。
5. **每次重建板书后都要重跑音效 apply**；板书上新增文字**要在全尺寸帧上看有没有压到框线**（缩略联系表看不出来，本轮 K4 的新标签就是这样漏过第一遍的）；写字体规则见 `.claude/rules/whiteboard-craft.md`。
6. **渲染块的指纹包含音频**：改任何配音，所有块都会重渲（约 38 分钟）；只改一块板书且音频没变才只重渲那一块。后台渲染用 `run_in_background`，结束会通知，不要轮询、不要睡眠等。
7. **子智能体**：不用 Claude 自己的 Agent 工具；Codex（用户自己的中转站，默认 terra，判断活用 sol，一波别超过约 6 路）和 Antigravity（`agy`，先 `agy -p "/usage"` 查额度；Argon 只用在关键评审，调查和草稿用 Flash 档）是常规子智能体；派之前先说一句“Codex 几次、Antigravity 几次”；结果只是线索，要回原文核。第 2 课的复审结果在 `validation/research/review2/`。
8. **凭据**：七牛云网关密钥在 `crosscheck.env`、线上电子书密码在 `projects/_ebook/local/`，**绝不读、不打印、不写进文件**；端口与地址不写进仓库文档（本文也没写）。
9. **操作陷阱**：不要在仓库根目录起 `http.server`；不用 `pkill -f`；磁盘上渲染会在 `/tmp` 留 `remotion-webpack-bundle-*`，没有渲染进程时再清。
10. 本机没有 PIL，看图用 Read 工具或 ffmpeg 裁剪；ffmpeg 取帧时间用成片时间轴。

## 7. 提交规矩与现在未提交的东西

- **只在用户说“提交”时提交**；提交后自动推 fork：`git -c 'credential.helper=!gh auth git-credential' push fork <分支>`，不推 origin、不强推；推送前扫增行里的密钥与外部 IP；提交要带 `-c user.name=… -c user.email=…`，署名行按当前会话要求；同时在 `projects/` 本机库提交本课文本源快照（不推送）。分支 `feat/whiteboard-scene-dashscope-image`。
- **外层仓库**：`blocks.py`、测试和本交接文档已在 `c99076a` 提交并推 fork（本节这次修改是提交之后改的，下次“提交”时随带）。**仍未提交且不属于第 2 课的**：`docs/remote-render-client.md` 和 `tools/video/remote_cpu_render.py`（别的进程 2026-11-02 晚加的渲染机心跳与重连改动，含渲染机端口和主机细节，**不要提交**，除非用户另有指示）；以及老的未提交项：`.claude/skills/anatomy/`、`.pyodide-integration/`、`.remotion/`、`docs/anatomy-skill-evaluation.zh-CN.md`、渲染机验收 json 和证据压缩包（这些不提交）。
- **projects 本机库**：第 2 课选 B 之后的文本源改动已在 `219226a` 提交；之后发布阶段（封面、章节、电子书、成品包文本）产生的新改动还没提交；roadmap 的 v1.1 等无关改动（52 个文件）仍未提交，范围要用户定。
- 发布阶段完成后的提交要新建一个提交（在 `65eb067` 之后），不要改写已推送的历史。

## 8. 关键位置速查

| 东西 | 位置 |
|---|---|
| 当前成片（无封面） | `projects/agent-tokens-window-cn/renders/final.mp4` |
| 发布用成片（带封面，**现在是旧版**） | `…/exports/video/output.mp4`、`subtitles.srt`；`…/exports/metadata/{description,chapters,exercises,tags}.txt`、`metadata.json` |
| 配音与字幕 | `assets/audio/{narration_raw,narration}/`、`narration_timeline.json`；`assets/captions/captions.json`；`assets/subtitles.srt` |
| 旁白与板书源 | `code/make_author_files_v3.py`；`scripts/_board_s1…s4.py`、`_body_*.py`、`build_parts.py` |
| 电子书章节 | `code/assemble_chapter.py` → `projects/_ebook/chapters/S02-U02.json`；取帧 `assets/ebook-frames/f01…f12.jpg`；离线副本 `exports/ebook/`；站点 `projects/_ebook/site/` |
| 页内小练习 | `code/make_lab_section.py` → `code/lab_section.json`；验证 `code/verify_labs.py`、`code/e2e_labs_l2.cjs` |
| 复审与记录 | `validation/fact-check.md`（含“第 2 次复审”“选 B 处置”）；`validation/research/review2/`；`validation/compose-notes.json` |
| 审阅页（Artifact，私有） | 发布包 `5f8HmYv5ZY7wVwHAwdJudY`；复审 `HLPcbq1oQuWFYRChsFwegj`（地址前缀 `https://claude.ai/artifact/`） |
| 备份与基线 | `/home/MyProject/backup-l2-before-B/`（含 `baselines/`） |
| 记忆 | `/root/.claude/projects/-home-MyProject-OpenMontage/memory/project_l2_planning.md`（流水账，比本文更细）、`MEMORY.md`（索引） |

## 9. 复盘时要分流进登记表的教训（候选，写 retro 时用）

1. 重跑 `build_script.py` 会覆盖已批准的脚本检查点和产物——对已批准阶段重跑要先备份、跑完恢复，并核对 `gate status`。
2. 画面描述写进核对笔记前要对**全尺寸帧逐项核**，不凭事件表：红叉被图层盖住而笔记写成“已划掉”（上一版笔记的错）。
3. 新增板书标签要看全尺寸帧是否压框线；缩略联系表看不出。
4. 改配音会让全部渲染块的指纹变化，整课要重渲——判断改动代价时要算上这 38 分钟。
5. 改已批准旁白的流程：复审页 A/B/C → 用户选 → 备份 → 只改选定处 → 重配音重渲 → 笔记如实写新旁白没人听过、样片对的是旧旁白 → 请用户重说成片口令（E60）。本轮这个流程走通了，可写成通用步骤。
6. 复审里 AI 审稿人的误报类型：搭档故意说错的台词、“不讲”声明、时间偏移、猜测性断言——裁决时回原文，不按票数。
