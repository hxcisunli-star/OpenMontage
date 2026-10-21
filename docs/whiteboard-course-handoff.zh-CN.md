# 白板课程项目交接（续作指南）

> 目的：新开一个 Claude Code 会话，读完本文就能接着做下一课。写于 2026-10-19（第 43 课发布、经验沉淀方案第一批之后）。事实来自本机文件、检查点和提交记录；没测过的地方直接写“未测”。
> 旧版全文（含逐课“做下一课要注意”、43 课长表、历史路线）在 `docs/whiteboard/archive/handoff-full-20261019.zh-CN.md`；逐课章节在 `docs/whiteboard/archive/playbook-2.12-2.48-per-lesson.zh-CN.md`。

## 0. 新会话开场三步（照做）

1. 读 `CLAUDE.md` → `AGENT_GUIDE.md`（仓库规定：回应任何用户消息之前先读，它决定第一步做什么）。
2. 读入口 skill `.claude/skills/whiteboard-lesson/SKILL.md`，再读当前阶段的清单 `docs/whiteboard/checklists/*.md`；协议规则 `.claude/rules/whiteboard-protocol.md` 会自动载入。
3. 跑 `.venv/bin/python docs/whiteboard_gate.py status`（从各课检查点算出现在哪课、哪一门、等什么口令）；没有进行中的课程时，告诉用户你已接手，下一课由用户另定。

记忆在 `/root/.claude/projects/-home-MyProject-OpenMontage/memory/`（`MEMORY.md` 是索引）；与本文冲突时，**以本文和仓库文件为准**，并更新记忆。

## 1. 现状

用户是中文 C 语言教师，在做“老师边讲边画”白板风格教学视频：OpenMontage `animated-explainer` 管道 + Remotion `explainer-teacher` 模板 + DashScope Cherry 配音，不加背景音乐，带学校 logo，每课成片开头有约 2 秒封面，发布包含“课后练习”，**全部本地打包、未上传任何平台**。

- **43 门课全部已发布**（第 1–43 课），没有进行中的课程；补漏路线 v2 与综合案例三部曲（叫号机 → 病历册 → 门诊系统）已走完，**没有已定的下一课**，由用户另定（用户说“继续策划下一课”或直接给题目再开始）。
- 渲染：分块渲染 + 多进程；默认自动走远程渲染机（整课约 155–225 秒），失败自动回退本机（整课约 27 分钟起）；**每次渲染前先 `python3 tools/video/remote_cpu_render.py probe` 并看输出**；故障记录见 `docs/remote-render-incident-20261015-job-log-unavailable.zh-CN.md`。
- 2026-10-19 起项目里有五个来自 OpenMAIC 的改编教学设计 skill（`backward-design`、`plain-language-review`、`lesson-fact-check`、`exercise-design`、`spiral-series-check`，见做课手册 2.49），还没在真实课里试用，下一课是首次试用。
- 2026-10-19 起经验按“登记表 + 阶段清单 + 复盘”沉淀，不再往多处各写一遍（见第 7 节）；重复出现的教训已做成脚本（口令助手、缩略图检查、成片核对器、回扣提取器、单一词表与脚本检查、一键建课），回测见 `docs/whiteboard_backtest.py`。**老课体检**（每块板最后一项笔迹有没有写完就淡出）：`docs/whiteboard/old-lessons-last-item-report.zh-CN.md`，只出报告，是否重渲由用户定。

## 2. 43 课一览

成片秒数不含 2 秒封面片头（43 课的发布版都带该片头）；项目目录都在 `projects/`；状态都是“发布已通过（本地打包，未上传）”。每课的选题、实测、教训在 `docs/whiteboard/archive/` 对应章节。

| # | 课程 | 项目目录 | 成片秒数 |
|---|---|---|---|
| 1 | 冒泡排序 | `projects/bubble-sort-tutorial-cn` | 322.05 |
| 2 | 函数传参：值传递与地址传递 | `projects/c-value-vs-address-cn` | 475.65 |
| 3 | 数组传参 | `projects/c-array-parameters-cn` | 467.29 |
| 4 | 字符串 | `projects/c-strings-cn` | 356.42 |
| 5 | scanf 与 & | `projects/c-scanf-address-cn` | 327.15 |
| 6 | 结构体传参 | `projects/c-struct-parameters-cn` | 390.25 |
| 7 | 指针初步 | `projects/c-pointer-basics-cn` | 400.43 |
| 8 | 指针与数组 | `projects/c-pointer-array-cn` | 397.31 |
| 9 | 函数返回值 | `projects/c-function-return-cn` | 394.26 |
| 10 | 二维数组传参 | `projects/c-two-dim-array-cn` | 389.61 |
| 11 | 动态内存分配 | `projects/c-dynamic-memory-cn` | 383.02 |
| 12 | 链表初识 | `projects/c-linked-list-intro-cn` | 394.39 |
| 13 | 动态链表 | `projects/c-dynamic-list-cn` | 404.54 |
| 14 | 删除一张卡 | `projects/c-list-delete-cn` | 397.99 |
| 15 | 按顺序插入 | `projects/c-list-insert-cn` | 396.54 |
| 16 | 递归 | `projects/c-recursion-cn` | 376.73 |
| 17 | 变量的一生 | `projects/c-variable-life-cn` | 362.67 |
| 18 | 栈 | `projects/c-stack-cn` | 392.90 |
| 19 | 结构体数组与 typedef | `projects/c-typedef-array-cn` | 410.17 |
| 20 | 文件读写 | `projects/c-file-io-cn` | 391.13 |
| 21 | 函数指针与回调 | `projects/c-func-ptr-cn` | 369.70 |
| 22 | 动态数组与 realloc | `projects/c-realloc-cn` | 384.57 |
| 23 | 二分查找 | `projects/c-bsearch-cn` | 377.30 |
| 24 | 比名字 | `projects/c-strcmp-cn` | 395.20 |
| 25 | 读入会失败 | `projects/c-scanf-check-cn` | 374.73 |
| 26 | 先读一整行再分析 | `projects/c-fgets-line-cn` | 392.40 |
| 27 | 队列 | `projects/c-queue-cn` | 388.50 |
| 28 | 链表反转 | `projects/c-reverse-list-cn` | 394.80 |
| 29 | 头文件与多文件 | `projects/c-multifile-cn` | 375.30 |
| 30 | 宏 | `projects/c-macro-cn` | 396.90 |
| 31 | 枚举与多路选择 | `projects/c-enum-switch-cn` | 401.30 |
| 32 | 字符串的边界 | `projects/c-string-bound-cn` | 410.17 |
| 33 | `char *` 与字符串字面量 | `projects/c-literal-cn` | 382.90 |
| 34 | 二级指针 | `projects/c-ptr-to-ptr-cn` | 381.47 |
| 35 | 合并有序链 | `projects/c-merge-cn` | 373.60 |
| 36 | 插入排序 | `projects/c-insertion-sort-cn` | 386.50 |
| 37 | 二叉查找树 | `projects/c-bst-cn` | 368.10 |
| 38 | 联合体 | `projects/c-union-cn` | 381.70 |
| 39 | 位运算 | `projects/c-bits-cn` | 417.13 |
| 40 | 命令行参数 | `projects/c-argv-cn` | 400.80 |
| 41 | 门诊叫号机 | `projects/c-caller-cn` | 377.53 |
| 42 | 病历册 | `projects/c-record-cn` | 399.20 |
| 43 | 门诊系统 | `projects/c-clinic-cn` | 414.97 |

## 3. 用户与协作规则（违反过会被指出）

**九个口令**（用户自己在对话里说，且在对应步骤做完之后才算；没收到不进入下一阶段；细则见 `.claude/rules/whiteboard-protocol.md`）：

| 口令 | 对应阶段 | 之前给用户看什么 |
|---|---|---|
| 计划确认 | 策划（计划模式） | 候选对比、推荐路线、需要拍板的点 |
| 提案通过 | proposal | 概念对比、选定方案、术语与命名确认 |
| 脚本通过 | script | 段落表、字数与估时、实测输出、通俗度与事实核对结论 |
| 场景计划通过 | scene_plan | 场景表、版面与风险 |
| 样音通过 | assets（样音） | 样音文件 |
| 素材通过 | assets | 配音清单、费用估价、未验证项 |
| 样片通过，开始合成 | edit | 样片 |
| 成片通过，进入发布阶段 | compose | 成片与核对结果 |
| 发布通过 | publish | 导出包、待确认项 |

- **全程中文、回复精简**：嫌长就做成表，重点放“需要你决定什么”。
- **诚信与独立核对**：不用占位物冒充成品；费用只写“工具占位估价，真实以账单为准”；交付前自己用 `ffprobe`、`ebur128`、`silencedetect`、`blackdetect`、抽帧核对，不信工具自检；做不到的检查（无语音识别）明说并给替代证据；发现自己的错（含已批准之后的）主动说并修。
- **不编造**：不确定的来源、模型、耗时直说；只看到搜索摘要的来源标明“未打开原页”。
- **审批后发现问题**：小改、只重做受影响的部分、告知用户。
- **用户中途打断**：拒绝某次工具调用后先停；用户说“继续”再重试同一步，不换路线。
- **看成片的方式**：用户在 Windows 上，服务器无浏览器，靠 `scp` 取文件（端口和地址见用户记忆，**不写进仓库文档**）；不要在仓库根目录起 `http.server`（会暴露 `.env`）。
- **密钥**：用户贴过密钥；只放 `.env`，不在输出、日志、文档里复述。
- **保留商用方案**：新增本地方案只做补充，不改旧工具；评分设保守值。
- **Git**：见第 8 节。

## 4. 环境与已知限制

| 项 | 状态 |
|---|---|
| 机器 | Ubuntu 24.04，4 核，7.9GB 内存，无 GPU，Node 18，ffmpeg 6.1，gcc 13.3，GNU diffutils 3.10 |
| Python | 只用 `.venv/bin/python` 并设 `PYTHONPATH=.`（系统 Python 缺 PIL，jsonschema 太旧会报 `$ref` 错） |
| 渲染 | 只能用 Remotion（HyperFrames 需要 Node 22，Ink Theater 只跑在 HyperFrames 上，均不可用）；本机分块多进程整课约 27 分钟，默认走远程渲染机 |
| 配音 | DashScope `qwen3-tts-flash`，音色 Cherry，`language_type=Chinese`；单次 ≤600 字；WAV 头时长不可信（脚本已处理）；实测约 0.232–0.245 秒/字（含停顿与静默），预估按 0.238 |
| 生图 | `dashscope_image`（商用，默认）与 `qwen_local_image`（本地补充，免费）；第 4 课起复用第 3 课的医生姿态图，不再生图 |
| 音乐 | Pixabay 抓取 403；所有课都不加背景音乐 |
| 语音识别 | **没有**（`transcriber` 未装，`dashscope_asr` 需公网 URL）：字幕逐字时间是估计值，必须如实告知 |
| Bash 沙箱 | 启动失败（`apply-seccomp … Permission denied`）：每条命令先试沙箱，失败后带 `dangerouslyDisableSandbox` 重试并说明原因，不擅自绕过更多限制 |
| 等待后台任务 | 前台 `sleep` 被禁用；用 `nohup` 启动，等待用 `until grep` 日志放后台（远程整课的结束行是 `success`，本机是 `done in`），后台通知的 completed 只是外壳退出 |

`.env` 里有 DashScope 等密钥，**不要读出或打印**。

## 5. 系列设定（新课必须沿用）

- **角色与比喻**：医生 + 一排病房 + 记录板 + “地址纸条是抄来的，病房还在原处”。医生用两张静态姿态图（持纸、指向），**直接复制复用**，不再生图：`assets/images/doctor_holding_note.png`、`doctor_pointing.png`、`references/ref_doctor.png`、`assets/images/schoollogo.png`、`references/ZCOOLKuaiLe-Regular.ttf`（都在 `projects/c-struct-parameters-cn/` 里，近课项目里也有）。
- **术语**：只讲**值传递 / 地址传递**；取地址符 `&` 称“取地址符”；`->` 称“箭头：顺着地址找成员”；`'\0'` 称“终点牌”。**禁用词**：传值规则、引用传递、管理员、工作人员、维修员；难词表在各课 `build_script.py`（FORB、JARGON）。
- **配音**：Cherry；不加音乐；段间 0.7 秒；每课一处中途预测加末段两道预测题，问句后**真实静默 3 秒**（拼接时插入静音，不靠 TTS 标点），板上三点倒数，答案在静默后才出现。
- **画面规范**：1920×1080、30fps；暖白底 `#FBFBF8`；墨 `#17202B`；红 `#B42318`（写入）；绿 `#126442`（结果）；黄 `#F1C84A`（重点圈线）；学校 logo 左上深蓝底板（哈尔滨信息工程学院）；字幕在 y=900..1040；标题 x≥420 避开 logo。一段旁白一块白板，板间 0.4 秒淡变。
- **字形陷阱（实测过）**：手写体（ZCOOL）里 `0`、`o`、`O`、`c`、`C` 和单个大写字母都是方块，`〇` 与字母同板像 `o`。做法：代码词、符号、零一律**等宽字体叠写**（`write(font="mono")`，格子值置空）；小写 a p l e t h i 正常；字幕里单个 c、o 字符指定拉丁字体；旁白里没有英文；等宽字体里没有中文和全角符号。
- **每课结构**：8 段（每段 ≤600 字、一个动作）；开场回扣上一课的悬念；一个“错写法”（只画叉或只编译，不运行）；一处中途预测、末段两道预测题（各留 3 秒静默）；末段三句回顾；课后练习随发布包。
- **例子**：全部用 `gcc -std=c11 -Wall -Wextra -Wpedantic -Werror` 编译、真实运行，输出存 `validation/`；单词与成员名避开 o、c（apple、tea、hi、id、age、v）。

## 6. 流水线与脚本速查

阶段顺序：`research → proposal(门) → script(门) → scene_plan(门) → assets(门) → edit(含样片，用户审) → compose(用户审) → publish(门)`。检查点由 `lib/checkpoint.py` 的 `write_checkpoint(...)` 写（用 `.venv/bin/python`）；决策记录 `decision_log.json` 只追加；校验用 `schemas.artifacts.validate_artifact`。**每个阶段做什么、命令、已知会出错的地方：`docs/whiteboard/checklists/`。**

每课 `projects/<课>/scripts/`（新课复制最近一课，先改项目名与课号、grep 核对，再运行）：

| 文件 | 作用 |
|---|---|
| `plan_stage.py` | 调研简报 + 提案 + 决策记录 + research/proposal 检查点 |
| `build_script.py` | 脚本 JSON、自检（通俗度、难词、锚点间隔）、教学例子映射、审阅页、script 检查点 |
| `build_scene_plan.py` | 场景计划（含旁白锚点）、审阅页、scene_plan 检查点；静默表与 `MIN_AFTER` 按本课问答所在段改 |
| `sample_voice.py` / `gen_tts.py` / `make_captions.py` / `finish_assets.py` | 样音 / 批量配音 / 字幕 / 素材清单与 assets 检查点 |
| `_build_head.py` + `_body_helpers.py` + `_body_boards.py` + `_build_tail.py` → `build_edit.py` | 用 `bash scripts/rebuild_edit.sh` 拼接并跑 lint；**改源文件，不改拼接产物** |
| `render_stills.py` / `render_final.py` | 单帧 / 整课分块渲染 |
| `finish_compose.py` | 写 render_report、final_review 与 compose 检查点（数字来自本课实测） |
| `run_validation.sh` / `run_exercises.sh` / `make_exercises.py` | 例子与练习的真实运行 / 练习文本 |
| `publish_prep.py` / `finish_publish.py` | 缩略图（`THUMB_T`）+ SRT + 章节元数据 / 导出包 + publish 检查点 |

渲染与检查工具（都在 `docs/`，说明见做课手册 4.4）：`whiteboard_lint.py`（渲染前检查，含手写体混写拉丁字母警告）、`whiteboard_last_item_check.py`（最后一项笔迹写完时间，按渲染器算法；起步模板的 `rebuild_edit.sh` 已并入）、`whiteboard_thumb_check.py`（缩略图时间）、`whiteboard_script_lint.py`（旁白与脚本检查，词表 `docs/whiteboard/wordlist.yaml`）、`whiteboard_callbacks.py`（回扣原话核对）、`whiteboard_verify.py`（成片核对：`verify`、`probe`、`stills`、`local-ref`、`compare`）与 `whiteboard_finish_compose.py`（合成报告读实测）、`whiteboard_wait.py`（等后台任务）、`whiteboard_gate.py`（口令助手）、`whiteboard_new_lesson.py`（一键建课，模板在 `docs/whiteboard/starter/`）、`whiteboard_render.py`（`--final`、`--contact`、`--stills`、`--sample`，`--local` / `--remote-cpu`）、`whiteboard_cover_maker.py`、`whiteboard_prepend_cover.py`、`whiteboard_release_pack.py`。白板元素（`remotion-composer/src/components/WhiteboardScene.tsx`）**不要改仓库代码，只改数据**。

## 7. 经验怎么积累（2026-10-19 起）

- **一条教训只存一处**：`docs/whiteboard/lessons-learned.yaml`（登记表，每条有阶段、规则、级别〔检查／默认／清单／叙述〕、来源编号）；各阶段清单 `docs/whiteboard/checklists/*.md` 是它生成的视图，**不要手改**。
- **晋升规则**：每课“发布通过”后写复盘（`docs/whiteboard/retro-template.md` → `docs/whiteboard/retro/NN.md`，范例 `retro/43.md`），本课每条教训分流一次——能判对错的做成脚本或加进 lint；要人判断的在登记表加一条 `level: 清单`；只有来龙去脉的写“叙述”。同一条教训第二次出现还停在文字上，视为流程缺陷。
- **命令**（仓库根目录）：`.venv/bin/python docs/whiteboard_registry.py coverage`（要 0 条未映射）、`render`、`check`、`stats`（列出该升级成脚本的条目）。
- 手册、交接文档、记忆不再各记一遍：交接文档只更新“现状”与第 2 节的一行；记忆只写用户新给的偏好或权限。
- 第二批已做：口令时机、缩略图取帧、整课渲染后的备份与对照、成片核对的手工数字、词表各课各存一份都已做成脚本（登记表里升为“检查／默认”）；仍停在“清单”的多是要人判断的（编译提醒怎么写、版面间距等），`stats` 会列出还该升级的。**还没有用真实新课试过**：下一课按新流程做，复盘里统计旧教训被拦下几条、有没有同类重复。

## 8. Git / GitHub

- 工作分支 `feat/whiteboard-scene-dashscope-image`，远端 `fork` = `https://github.com/hxcisunli-star/OpenMontage.git`（用户自己的 fork，PR #1 在这里）；`origin` 是上游开源仓库，**不推、不强推**。
- **提交只在用户说“提交”时做；提交后自动推到 fork**（用户已授权）：`git -c 'credential.helper=!gh auth git-credential' push fork <分支>`；推送前扫密钥与外部 IP。
- 提交署名：本仓库没设全局 git 身份，用 `git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit …`，信息末尾加当前会话系统提示要求的署名行。
- `projects/` 被外层 `.gitignore` 忽略，课程产物不进外层 git；真正进 git 的是 `docs/`、`.claude/` 和仓库代码。**`projects/` 里另有一个只在本机的版本库**（2026-10-19 建，**不推送**；只跟踪每课的脚本、C 代码、验证输出、产物 JSON、检查点等文本，约 5000 个文件、67 MB，不含视频音频；说明见 `projects/README.md`）。提交用 `git -C projects -c user.name=… -c user.email=… commit …`；首个快照 2026-10-19 已做，之后每课做完，**在用户说“提交”时一起**给 `projects/` 提交一次快照；别在外层仓库根目录运行 `git clean -x`（会连这个库一起删）。
- 故意不提交的未跟踪文件：`.claude/skills/anatomy/`、`.remotion/`、`docs/anatomy-skill-evaluation.zh-CN.md`、`docs/remote-render-acceptance-20261007.json`（含渲染机公网地址）、`docs/remote-render-replies/round4-results/raw-evidence.tar.gz`。`.env`、`apidocs/` 不提交。
- `gh pr edit` 在本机报 GraphQL 错，改用 `gh api -X PATCH repos/hxcisunli-star/OpenMontage/pulls/1 -F body=@文件`。

## 9. 文件位置索引

| 内容 | 位置 |
|---|---|
| 做课手册（原则、流程、工具速查、验收、踩坑表） | `docs/whiteboard-course-playbook.zh-CN.md` |
| 登记表、阶段清单、复盘模板与范例、归档 | `docs/whiteboard/`（`lessons-learned.yaml`、`checklists/`、`retro-template.md`、`retro/`、`archive/`）；工具 `docs/whiteboard_registry.py` |
| 入口 skill 与规则 | `.claude/skills/whiteboard-lesson/`、`.claude/rules/whiteboard-protocol.md`、`whiteboard-craft.md`；五个教学设计 skill 同在 `.claude/skills/` |
| 渲染工具 | `docs/whiteboard_render.py`、`docs/whiteboard_lint.py`、`docs/whiteboard_last_item_check.py`、`remotion-composer/render-tools/render_chunks.mjs`、`remotion-composer/render-fonts/` |
| 远程渲染 | 客户端 `tools/video/remote_cpu_render.py`；说明 `docs/remote-render-client.md`；给对方的需求文档 `docs/remote-render-agent-brief-v*.zh-CN.md`（版本号最大的最新）；回复 `docs/remote-render-replies/`；自测包 `projects/_remote_kit/` |
| 仓库规则 | `CLAUDE.md`、`AGENT_GUIDE.md`、`docs/stage-gates/` |
| 每课审阅页与关键产物 | `projects/<课>/script-review.html`、`scene-plan-review.html`；`artifacts/{research_brief,proposal_packet,script,scene_plan,asset_manifest,edit_decisions,render_report,final_review}.json`；`checkpoint_*.json`；`decision_log.json` |
| 每课成品 | `projects/<课>/exports/`（`video/output.mp4` 是带 2 秒封面片头的发布版）；统一成品文件夹 `projects/C语言白板课_成品/第NN课_课名/` + `目录.txt` + 同名 zip，由 `docs/whiteboard_release_pack.py` 重建 |
| 封面 | `docs/whiteboard_cover_maker.py`（`LESSONS` 加一行）、`docs/whiteboard_prepend_cover.py` |
| 本地生图工具 | `tools/graphics/qwen_local_image.py` |
| 用户记忆 | `/root/.claude/projects/-home-MyProject-OpenMontage/memory/`（`MEMORY.md` 索引） |

## 10. 下一课怎么开始

用户说“继续策划下一课”或给题目时：先读 `docs/whiteboard/checklists/01-plan.md` 与 `.claude/skills/backward-design/SKILL.md`，**在计划模式下先研究、不建项目**：选题四条标准（前置讲过没有／能否从最近一两课自然长出来／新东西只有一两个／核心结论能否实测）、难点表（难点 → 学生怎么想 → 讲法 → 实测证据）、通俗度目标、教学设计一页纸；用户随口提的题目只是想法，可以否定。写计划文件，用户在对话里说“计划确认”后才建项目，然后停在提案门。已做过的课见第 2 节；路线历史见 `docs/whiteboard/archive/playbook-9.3-roadmap-history.zh-CN.md`。

## 11. 给新会话的建议开场语（可直接贴给用户）

> 我已读完 `AGENT_GUIDE.md`、本交接文档和入口 skill：43 门课都已发布（本地打包），渲染默认走远程渲染机并带渲染前检查；经验已按“登记表 + 阶段清单 + 复盘”整理。路线 v2 与综合案例三部曲已走完，下一课由你另定，要我先研究并给计划吗？（我会先研究衔接、难点讲法和通俗度，你说“计划确认”后才建项目，然后停在提案门等你批准。）
