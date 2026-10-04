# 白板课程项目交接文档（C 语言系列，已做完 6 课）

> 目的：新开一个 Claude Code 会话，读完本文档就能接着做第 7 课，不用重新摸索。
> 写于 2026-10-03。事实来自本机文件、检查点和提交记录；没测过的地方直接写“未测”。
> 配套文档：`docs/whiteboard-course-playbook.zh-CN.md`（做课方法与踩坑大全，**必读**）。本文档只讲“现状 + 怎么接着干 + 注意事项”。

---

## 0. 新会话开场三步（照做）

1. **读 `CLAUDE.md` → `AGENT_GUIDE.md`**。仓库规定：回应任何用户消息之前必须先读 `AGENT_GUIDE.md`（它决定第一步做什么）。
2. **读 `docs/whiteboard-course-playbook.zh-CN.md` 的第 0、2、8 部分**，再扫一眼第 6 部分“踩坑速查表”。
3. **读本文档第 2、3、5、6 节**，然后告诉用户你已接手，并问“下一课做哪个知识点”（或直接给推荐，见第 9 节）。

自动加载的用户记忆在 `/root/.claude/projects/-home-MyProject-OpenMontage/memory/`（`MEMORY.md` 是索引），里面有用户画像、操作陷阱、各课状态；与本文档冲突时，**以本文档和仓库文件为准**，并更新记忆。

---

## 1. 一句话现状

用户是中文 C 语言教师，在做一套“老师边讲边画”的白板风格教学视频，用 OpenMontage（`animated-explainer` 管道 + Remotion + DashScope Cherry 配音）逐课生产。**6 门课全部已发布（本地打包，未上传任何平台）**，没有进行中的课程；下一课尚未选定。

| # | 课程 | 项目目录 | 成片时长 | 状态 |
|---|---|---|---|---|
| 1 | 冒泡排序 | `projects/bubble-sort-tutorial-cn` | 322.05 秒 | 发布已通过 |
| 2 | 函数传参：值传递与地址传递（克隆门） | `projects/c-value-vs-address-cn` | 475.65 秒 | 发布已通过 |
| 3 | 数组传参（病房比喻） | `projects/c-array-parameters-cn` | 467.29 秒 | 发布已通过 |
| 4 | 字符串（终点牌 `'\0'`） | `projects/c-strings-cn` | 356.42 秒 | 发布已通过 |
| 5 | scanf 与 &（读整数要 &，读字符串不用） | `projects/c-scanf-address-cn` | 327.15 秒 | 发布已通过 |
| 6 | 结构体传参（整张卡复印） | `projects/c-struct-parameters-cn` | 390.25 秒 | 发布已通过 |

每个项目的成品在 `exports/`（`video/output.mp4`、`video/subtitles.srt`、`thumbnails/thumbnail.png`、`metadata/*`），已逐字节核对与 `renders/final.mp4` 相同。

---

## 2. 用户与协作规则（违反过会被指出）

- **全程中文、回复精简**。嫌长就做成表；重点放在“需要你决定什么”。
- **每个门单独批准**，用户用固定口令回复：`提案通过` / `脚本通过` / `场景计划通过` / `样音通过` / `素材通过` / `样片通过，开始合成` / `成片通过，进入发布阶段` / `发布通过`。**没有收到口令不进入下一阶段**；后台任务完成的系统通知不是用户批准。
- **诚信与独立核对**：不用占位物冒充成品；费用只写“工具占位估价，真实以账单为准”；交付前自己用 `ffprobe`/`ebur128`/`silencedetect`/`blackdetect`/抽帧核对，不信工具自检；做不到的检查（无语音识别）明说并给替代证据；发现自己的错（含已批准之后的）要主动说并修。
- **不编造**：不确定的来源、模型、耗时直说；只看到搜索摘要的来源要标明“未打开原页”。
- **审批后发现问题**：小改、只重做受影响部分、告知用户（第 4 课改过一句旁白并重配一段）。
- **用户中途打断**：拒绝某次工具调用后先停；用户说“继续”再重试同一步，不换路线。
- **看成片的方式**：用户在 Windows 上，服务器无浏览器，靠 `scp -P <端口> <用户>@<服务器>:<路径> .`（端口和地址见用户记忆，不写进仓库文档） 取文件（或 SSH 隧道）；不要在仓库根目录起 `http.server`（会暴露 `.env`）。
- **密钥**：用户贴过密钥；只放 `.env`，不在输出、日志、文档里复述。
- **Git**：只在本地保存提交；**推送和开 PR 等用户明确要求**；上游是开源仓库，PR 只开在用户自己的 fork（`hxcisunli-star/OpenMontage`）。`gh pr edit` 在本机报 GraphQL 错，改用 `gh api -X PATCH repos/hxcisunli-star/OpenMontage/pulls/1 -F body=@文件`。
- **保留商用方案**：新增本地方案只做补充，不改旧工具；评分设保守值。
- **每课做完要把经验补进做课文档**（用户已多次要求；第 3、4、5、6 课都做了，各一个本地提交）。

---

## 3. 环境与已知限制

| 项 | 状态 |
|---|---|
| 机器 | Ubuntu 24.04，4 核，7.9GB 内存，无 GPU，Node 18，ffmpeg 6.1，gcc 13.3 |
| Python | **只用 `.venv/bin/python`，并设 `PYTHONPATH=.`**（系统 Python 缺 PIL，`jsonschema` 太旧会报 `$ref` 错） |
| 渲染 | 只能用 Remotion（HyperFrames 需要 Node 22）；约 3.9 帧/秒，6 分钟成片约 40–50 分钟 |
| 配音 | DashScope `qwen3-tts-flash`，音色 Cherry，`language_type=Chinese`；单次 ≤600 字；WAV 头时长不可信（脚本里已用 ffmpeg 重封装）；约 0.2–0.22 秒/字 |
| 生图 | `dashscope_image`（商用，默认）与 `qwen_local_image`（本地补充，`tools/graphics/qwen_local_image.py`，免费，占共享 GPU）；**第 4、5、6 课都没新生成插图** |
| 音乐 | Pixabay 抓取 403；六门课都**不加背景音乐** |
| 语音识别 | **没有**（`transcriber` 未装，`dashscope_asr` 需公网 URL）：字幕逐字时间是估计值，必须如实告知 |
| **Bash 沙箱** | **启动失败**：`apply-seccomp: write /proc/self/setgroups ... Permission denied`。用户选择了“在沙箱外逐条确认”，所以每条 Bash 都先试沙箱、失败后带 `dangerouslyDisableSandbox: true` 重试，并说明原因。不要擅自绕过更多限制。 |
| 等待后台任务 | 前台 `sleep` 被禁用；启动渲染用 `nohup … &`，再用 `until ! kill -0 <真实进程PID>; do sleep 30; done` + `run_in_background` 等。**启动它的外壳先退出会给出“完成”通知，不代表渲染结束**，要核对日志和 `final.mp4`。 |

`.env` 里有 DashScope 等密钥，**不要读出或打印**。

---

## 4. 系列设定（新课必须沿用）

- **角色与比喻**：医生 + 一排病房 + 记录板 + “地址纸条是抄来的，病房还在原处”。第 3 课起医生用两张静态姿态图（持纸、指向），后三课**直接复制复用**，不再生图：`assets/images/doctor_holding_note.png`、`doctor_pointing.png`、`references/ref_doctor.png`、`assets/images/schoollogo.png`、`references/ZCOOLKuaiLe-Regular.ttf`（都在 `projects/c-struct-parameters-cn/` 里可复制）。
- **术语**：只讲 **值传递 / 地址传递**；取地址符 `&` 称“取地址符”；`->` 称“箭头：顺着地址找成员”；`'\0'` 称“终点牌”。**禁用词**：传值规则、引用传递、管理员、工作人员、维修员（各阶段脚本里有全文搜索检查）。
- **配音**：Cherry；不加音乐；段间 0.7 秒；每课末尾两道预测题，问句后**真实静默 3 秒**（拼接时插入静音，不靠 TTS 标点），板上三点倒数，答案在静默后才出现。
- **画面规范**：1920×1080、30fps；暖白底 `#FBFBF8`；墨 `#17202B`；红 `#B42318`（写入）；绿 `#126442`（结果）；黄 `#F1C84A`（重点圈线）；学校 logo 左上深蓝底板（哈尔滨信息工程学院）；字幕在 y=900..1040；标题 x≥420 避开 logo。一段旁白一块白板，板间 0.4 秒淡变。
- **字形陷阱（实测过）**：手写体（ZCOOL）里 **`0`、`o`、`O`、`c`、`C` 和单个大写字母都是方块**；`〇` 与字母同板像 `o`（第 4 课用户指出）。做法：代码词、符号、零一律**等宽字体叠写**（`write(font="mono")`，格子值置空）；小写 a p l e t h i 正常；字幕里单个 c、o 字符指定拉丁字体；第 6 课干脆让旁白不含英文。
- **每课结构**：8–9 段（≤600 字/段，每段一个动作）；开场就有对照代码；回扣上一课；一个“错写法”（只画叉或只编译，不运行）；末段两道预测题 + 三句回顾。
- **例子**：全部用 `gcc -std=c11 -Wall -Wextra -Wpedantic -Werror` 编译、真实运行，输出存 `validation/example-output.txt`；单词/成员名避开 o、c（apple、tea、hi、id、age、v）。

---

## 5. 流水线与门（照第 6 课的做法）

阶段顺序：`research → proposal(门) → script(门) → scene_plan(门) → assets(门) → edit(含样片，用户审) → compose(用户审) → publish(门)`。检查点由 `lib/checkpoint.py` 的 `write_checkpoint(...)` 写：门控阶段先 `awaiting_human`，用户口令后再写 `completed`（`human_approval_required=True, human_approved=True`）。决策记录 `decision_log.json` 只追加。校验用 `schemas.artifacts.validate_artifact`。

**开新课的具体做法**（以第 6 课项目 `projects/c-struct-parameters-cn` 为模板，脚本在其 `scripts/`）：

1. **建项目**：`init_project('c-xxx-cn', title=..., pipeline_type='animated-explainer', style_playbook='clean-professional')`（`from lib.checkpoint import init_project`）；同时 `mkdir -p code validation scripts assets/images assets/captions review references artifacts`（**漏 `assets/captions` 会让字幕脚本报错**）；复制医生图、校标、字体、定妆图。
2. **调研 + 实测例子**：WebSearch/WebFetch 查现有教程缺什么（只看到摘要的来源要标注）；写 `code/xxx_demo.c`（含 `-Werror` 能过的写法：演示“改不到”的函数要在函数里打印参数，否则报 `unused-but-set-parameter`；输入类例子用管道 `printf '…' | ./demo`）和一个**只编译不运行**的错写法例子；输出存 `validation/`。**网上说法要用实测核对**（第 6 课推翻了一个流传说法）。
3. **提案**：复制上一课 `scripts/plan_stage.py`，整段重写研究部分（≥3 个现有内容、≥3 个带来源数据点、≥5 个来源、≥3 个角度），改提案文字与决策；运行得到 `research` completed、`proposal` awaiting_human。**停下等“提案通过”**。
4. **脚本**：复制上一课 `build_script.py`（含全部数据 + 自审 + 审阅页 + 检查点），改各段旁白与画面提示。**写完立刻对账时长**：按 `字数 × 0.21 秒 + 6 秒静默 + 段间 0.7 秒` 与提案目标核对，偏短就补“讲清道理”的句子，别堆内容；检查：旁白里点名的数字、成员、字母与实测逐一对照；相邻画面提示间隔 ≤10 秒；问句各只出现一次；无冲突词。产出 `script.json`、`script_review.json`、`teaching_examples.json`、`script-review.html`。**停下等“脚本通过”**。
5. **场景计划**：复制 `build_scene_plan.py`，改各块版面与事件。**每个事件带旁白锚点 `anchor_phrase`，事件必须按旁白先后顺序写**（找不到就停下改计划，不放宽查找）。运行时它会把 `script` 检查点标为 completed。**脚本里的决策编号要唯一且可重跑**（第 6 课曾重复 d10；现在场景计划脚本是“先删本阶段旧条目再追加 d11”）。**停下等“场景计划通过”**。
6. **素材**：先复制 `gen_tts.py`、`make_captions.py`、`sample_voice.py`、`finish_assets.py`（`sed 's/旧PID/新PID/g'`）；先跑 `sample_voice.py`（样音，含最难一句），**等“样音通过”**，再跑 `gen_tts.py`（批量配音 + 拼总轨 + loudnorm −16 LUFS）→ `make_captions.py`（字幕估计时间）→ `finish_assets.py`（素材清单与检查点；改段 id、问句段名、费用字典）。**停下等“素材通过”**。
7. **剪辑**：`build_edit.py` = `_build_head.py` + `_body_helpers.py` + `_body_boards.py` + `_build_tail.py`（`cat` 拼接；**改源文件，不要改拼接产物**）。写完先 `render_stills.py <秒…>` 渲染关键帧，用 `ffmpeg xstack` 拼 2×2 大图用 Read 逐张看，修版面，再 `render_sample.py <名> <起点> 30` 出 30 秒样片，写 `edit` 检查点，**等“样片通过，开始合成”**。
8. **合成**：`nohup .venv/bin/python projects/<课>/scripts/render_final.py > $CLAUDE_JOB_DIR/tmp/final.log 2>&1 &`，后台等**真实进程**；完成后自己核对：`ffprobe`（分辨率/帧率/编码/时长）、`ebur128`（≈−16 LUFS）、`silencedetect=n=-40dB:d=1.2`（只应有两处问答停顿 + 结尾收尾静音，位置对 `narration_timeline.json` 的 `answer_not_before`）、`blackdetect`、抽 15 帧拼图看；写 `render_report.json`、`final_review.json` 和 `compose` 检查点。**等“成片通过，进入发布阶段”**。
9. **发布**：`publish_prep.py`（缩略图取帧要**画完且没淡出**，先看图再导出；SRT；章节；元数据）→ `finish_publish.py`（`ExportBundle`，`platform=generic, visibility=private`，写 `publish` awaiting_human）。**等“发布通过”**，然后写 `publish` completed、更新记忆、把经验补进做课文档并本地提交。

**脚本文件作用速查**（第 6 课 `scripts/` 目录）

| 文件 | 作用 |
|---|---|
| `plan_stage.py` | 调研简报 + 提案 + 决策记录 + research/proposal 检查点 |
| `build_script.py` | 脚本 JSON、自审、教学例子映射、审阅页、script 检查点（并把 proposal 标为已批准） |
| `build_scene_plan.py` | 场景计划（含锚点）、审阅页、scene_plan 检查点 |
| `sample_voice.py` / `gen_tts.py` / `make_captions.py` / `finish_assets.py` | 样音 / 批量配音 / 字幕 / 素材清单 |
| `_build_head.py`（字幕分页、`Finder` 锚点查找、`Board` 白板构造）、`_body_helpers.py`（`cell/setv/dim/zero/endmark/ring/mono…`）、`_body_boards.py`（本课各块白板）、`_build_tail.py`（`edit_decisions`、`render_props`、logo 叠层） | 拼成 `build_edit.py` |
| `render_stills.py` / `render_sample.py` / `render_final.py` | 单帧 / 样片 / 整片渲染 |
| `publish_prep.py` / `finish_publish.py` | 缩略图 + SRT + 章节元数据 / 导出包 + publish 检查点 |
| `_newB.py` | 第 6 课临时文件（场景计划各块数据的来源），可忽略 |

白板元素（`remotion-composer/src/components/WhiteboardScene.tsx`，**不要改仓库代码**，只改数据）：`write`、`stroke`（rect/line/arrow/circle/underline）、`array`、`code`（逐行写 + 荧光笔）、`image`、`memory`（格子：`id,name,value,x,y,w,h,addr,from,copyDur,sets,dimAt,until,small`；箭头 `arrows`）。第 6 课新增的 `card2()`/`card3()` 在 `_body_boards.py` 里（带两栏的卡、带数组成员的卡，`from` 实现复印）。

---

## 6. 精选经验（完整版见 playbook）

- **时长对账**：语速实测 0.205–0.22 秒/字（含停顿）；第 4、5 课脚本偏短（提案 400–420 秒，成片 327–356 秒），第 6 课按“提案秒数反推字数”后落在目标内（预估 375.8，实测 388.8）。
- **旁白与画面逐一对照**：第 4 课旁白说“后面的 p、l、e 还在”，实际只剩 l、e，画画面时才发现，重配了一段。
- **一次性标注要给 `until`**，否则残留在板上；整行混排（手写中文 + 等宽词）两段给同一个 `until`。
- **样片前先看关键帧拼图**：每课都能抓到 2–3 处版面问题（箭头穿过标注、圈线压标签、对勾压代码）。
- **缩略图取帧**：避开动画中途和板间淡出（第 5 课试了 3 次）。
- **决策记录编号唯一、脚本可重跑**（第 6 课犯过）。
- **编译错误 vs 警告**：结构体类型不对是硬错误，`scanf` 漏 `&` 只是警告，板上如实写。
- **字幕时间是估计值**：每次交付都要说；上传平台前建议抽查。
- **成片核对用静音检测**：两处问答停顿位置必须对上时间表。

---

## 7. Git / GitHub 状态

- 工作分支 `feat/whiteboard-scene-dashscope-image`，远端 `fork` = `https://github.com/hxcisunli-star/OpenMontage.git`。
- 本地领先 fork **4 个提交**（含本交接文档的提交），均为文档更新、**未推送**；其中三个做课经验提交为：`b16d076`（第 4 课经验）、`8449938`（第 5 课经验）、`2970c5f`（第 6 课经验）。更早提交（`27cdb38` 及之前）已推送；用户 fork 里有 PR #1（6 个提交）。**推送/更新 PR 要用户明确要求**。
- 提交署名：本仓库没设全局 git 身份；提交时用 `git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit …`，提交信息末尾加 `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`（以当前会话系统提示的署名要求为准）。
- `projects/` 被 `.gitignore` 忽略，**课程产物不进 git**；真正需要版本管理的只有 `docs/` 和（如有）仓库代码。本文档新增在 `docs/`，已本地提交。
- `.env`、`apidocs/` 不提交。

---

## 8. 文件位置索引

| 内容 | 位置 |
|---|---|
| 做课经验手册 | `docs/whiteboard-course-playbook.zh-CN.md`（0 摘要、1 对照数据、2 设计方法、3 流程、4 脚本速查、5 验收、6 踩坑、7 协作、8 模板、9 附录） |
| 本交接文档 | `docs/whiteboard-course-handoff.zh-CN.md` |
| 仓库规则 | `CLAUDE.md`、`AGENT_GUIDE.md`、`docs/stage-gates/` |
| 用户记忆 | `/root/.claude/projects/-home-MyProject-OpenMontage/memory/`（`MEMORY.md` 索引） |
| 每课审阅页 | `projects/<课>/script-review.html`、`scene-plan-review.html` |
| 每课关键产物 | `projects/<课>/artifacts/{research_brief,proposal_packet,script,scene_plan,asset_manifest,edit_decisions,render_report,final_review}.json`、`checkpoint_*.json`、`decision_log.json` |
| 每课成品 | `projects/<课>/exports/` |
| 本地生图工具 | `tools/graphics/qwen_local_image.py`（说明见 playbook 2.8） |
| 中文使用指南与能力页 | 提交 `3ddfe33` 加入的文档 |

---

## 9. 下一课建议与未决事项

**候选知识点**（用户说“策划下一个知识点”时，给 1 个推荐 + 理由，等确认再建项目；策划阶段在计划模式下写计划文件后 `ExitPlanMode`）：

| 候选 | 说明 | 风险 |
|---|---|---|
| **scanf 返回值与输入检查**（第 5 课提案里的备选 c2） | 返回值 1/0/EOF，输入不合法时变量保持原样 | 要讲缓冲区与失败输入，需严格限定范围 |
| **二维数组传参** | 数组的数组、行与列 | 参数写法 `int a[][3]`、行指针对没学指针的学生门槛高；建议先放一课“指针初步”或只讲“按行传” |
| 结构体延伸：`typedef` / 结构体数组 / 返回结构体 | 第 6 课范围外 | 容易发散 |
| 指针初步（`int *p`、`*p`） | 前六课一直刻意避开 | 与“只讲值传递/地址传递”的术语约束要协调 |

**未决/待办**
- 无进行中的课程；下一课选题待用户确认。
- playbook 里个别“三门课/四门课”旧表述未改（描述当时事实）。
- 未做：语音识别核对字幕、动效化故事画面、局部重渲染流程在后几课没再用到（第 1 课有）。
- 第 5 课脚本偏短，用户按“接受”处理；第 6 课已修正。

---

## 10. 给新会话的建议开场语（可直接贴给用户）

> 我已读完 `AGENT_GUIDE.md`、做课经验文档和交接文档：6 门课都已发布（本地打包）。接着做第 7 课吗？我的推荐是《……》（理由……）。你确认选题后我先建项目、联网调研、实测例子、写提案，然后停在提案门等你批准。
