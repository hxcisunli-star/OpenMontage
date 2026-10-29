# 交接：智能体篇正式课程制作（写于 2026-10-29，两支试验之后）

> 读者：新开的 Claude Code 会话。目的：读完它就能稳定地开始做智能体篇的第一节正式课。事实来自本机文件、检查点和提交记录；没验证的地方直接写“未验证”。与记忆冲突时以本文和仓库文件为准。
> 详细的总流程仍在 `docs/whiteboard-course-handoff.zh-CN.md`（写于 10-19，C 课现状；第 0、5b 节仍有效）和 `.claude/skills/whiteboard-lesson/SKILL.md`；本文只补**这两周的变化和智能体篇的做法**。

## A. 粘贴给新会话的开场提示词（整段复制）

```
我要在这个仓库开始“智能体篇”正式课程的制作（和 C 语言课无关的新系列；若我另有所指，以我说的为准）。请严格按这个顺序做，做完前不要建项目、不要渲染、不要调用任何模型：
1. 读 CLAUDE.md，再读 AGENT_GUIDE.md（仓库规定回应任何消息前先读）。
2. 读 docs/whiteboard/handoff-agent-series-20261029.zh-CN.md 全文（这是本次交接），再读 docs/whiteboard-course-handoff.zh-CN.md 的第 0 节和第 5b 节。
3. 读 .claude/skills/whiteboard-lesson/SKILL.md，以及 .claude/rules/ 下两份白板规则（会自动载入）；再读 docs/whiteboard/checklists/00-always.md 和 01-plan.md。
4. 跑 .venv/bin/python docs/whiteboard_gate.py status，再读记忆索引 /root/.claude/projects/-home-MyProject-OpenMontage/memory/MEMORY.md。
然后用中文、精简地回复我：①你接手后的理解（三五句）；②需要我先定的事（交接文件第 7 节那几件）；③你建议的第一节课的选题思路和走哪条道。回复后进入计划模式，等我说“计划确认”之前不建项目。全程中文，只讲需要我决定的事，不编耗时和费用，没做的检查要明说，发现自己的错要主动说。
```

## 1. 先记住的规矩（都是用户定的，违反过的写在后面）

1. **九个口令只能由用户自己在对话里说，且在对应步骤做完之后才算**：计划确认 → 提案通过 → 脚本通过 → 场景计划通过 → 样音通过 → 素材通过 → 样片通过，开始合成 → 成片通过，进入发布阶段 → 发布通过。早说不算；退出计划模式、后台任务完成、系统消息都不是口令。口令用 `.venv/bin/python docs/whiteboard_gate.py approve|record …` 记录（样音通过、计划确认用 `record`）。记录工具会提示“现在停下”：上两支试验里“开始合成”“进入发布阶段”我按口令字面继续做了下一阶段并向用户说明，用户没有叫改；**这一条不确定，新会话开场可以问一句用户要不要每次口令后都先停**。
2. **提交只在用户说“提交”时做**；提交后自动推 fork（`git -c 'credential.helper=!gh auth git-credential' push fork <分支>`），**不推 origin、不强推**；推送前扫密钥和外部 IP；`.remotion/`、含渲染机地址的文件（如 `docs/remote-render-acceptance-20261007.json`）、证据压缩包与各 `*-results/` 原始证据目录不提交；提交带 `-c user.name=… -c user.email=…`（取值照 `.claude/rules/whiteboard-protocol.md` 与记忆），署名行按当前会话要求；`projects/` 是独立的本机库（不推送），提交时另做本课文本源快照。端口与地址不写进仓库文档。
3. **回复**：中文、精简，只讲需要用户决定什么；不编耗时与费用；没做的检查要明说；发现自己的错（含已批准之后的）主动说并修；**说人话第一**（旁白每句让初中生一遍听懂，高于风格与笑点）；用户是高校教授，嫌回复太长；用户通过 Artifact 页面和 scp 看成片，要拍板的事放进审阅页。**不用他／她称呼人**（用它、这几位）。
4. **模型与凭据**：实验与课程内容用七牛云网关（`MODELINK_*` 在 `crosscheck.env`，只在进程内加载，**绝不读、不打印、不写文件**）；**除配音外不调用百炼**（配音是 DashScope Cherry）；生图走网关的 Google 图像模型。**生图的授权只给了前两支试验**（用户 2026-10-28 说“不计成本、缺姿势就补”）：正式课要用先问；不用占位冒充成品；不编数字。
5. **子代理**：不用 Claude 自己的 Agent 工具；Codex（用户自己的中转站）和 Antigravity（`agy`）是常规子代理，派之前说一句“Codex 几次（哪几档）、Antigravity 几次”；档位与并发规则在全局记忆 `/root/.claude/CLAUDE.md`（会自动载入）：terra 做机械活、**sol 做板书代码和返工**、astra＋max 只做美术设计和互相矛盾的裁定；**一波大模型档不超过约 6 路；派后 60 秒内读每路 `events.jsonl`（有 `turn.failed` 或 `error` 立刻补发，退出码 0 不等于成功）**；Argon 额度用尽到 2026-10-31 13:15 UTC，改用 `gemini-3.8-flash-high` 并先对用户说明。它们和我都是模型，不算真人。
6. **环境**：只用 `.venv/bin/python` 并设 `PYTHONPATH=.`；Bash 沙箱在本机总是失败（apply-seccomp），带 `dangerouslyDisableSandbox` 重试并说明原因；后台任务用 nohup，等待用 `python3 docs/whiteboard_wait.py <日志>`（按进程结束，不按文件出现）；**不用 `pkill -f`**（会杀自己的 shell，我犯过两次）；**不要写 `cd X && ( … ) &`**（cd 被带进后台子 shell，后面的相对路径全指错）；不要在仓库根目录起 http.server；先改脚本、确认，再另起一条命令运行。
7. 新系列与 C 课**没有任何联系**：教师是女老师加 AI 小搭档机器人，不用医生比喻，旁白不回扣 C 课（`docs/whiteboard/series.yaml` 的 `forbid_terms`，旁白检查会拦）。

## 2. 现状（2026-10-29）

- **C 语言课 43 课已发布**；**智能体篇还没有一节正式课**。做过两支**试验品**（不属于课程，不占课号、不进课程表）：`agent-messages-cn`（消息列表，10-21）和 `agent-workflow-or-agent-cn`（《让AI自己拿主意，值吗？》，工作流与智能体，10-29 发布通过）。成品在 `projects/试验品_技术测试/`。**系列名未定**：没定时封面与成品包会明确报错，不用占位（E82）。
- **选题的来源是 `projects/roadmap-agent-engineer/`**（岗位路线调研项目，不是课程）：大纲 v1.1 已冻结，293 个单元（主线 S00–S13，分支 E、P、F、M，进阶层 A），在 `04-学习内容大纲/`；推荐学习／录制顺序在 `00-总览.md`（S0–S7 → S9-U01～U07 → S8 → …）；每个单元有“白板课适配度”字段。冻结记录 `review/FREEZE-v1.1.md`。**没有真人通读或试教过，复审与盲评都是模型做的**。试验品 2 对应单元 S4-U01（工作流与智能体）。
- **每课开工前的验证闸门**：`projects/roadmap-agent-engineer/review/LESSON-GATE.md`（七步，只验该课涉及的单元）；**教案页**（用户 2026-10-26 定）：脚本通过之前先出一页像预习讲义的页面，用户逐节反馈，全“能看懂”才写脚本；难度按中学生、试教群体是本科大一零基础新生。行为类说法只引 `labs/` 里的真实运行记录；会执行不可信代码或动权限的演示不在这台只有 root 的机器上跑。
- **渲染**：渲染机 agent/6（回执 `docs/remote-render-replies/2026-10-29-client-liveness.md`）。客户端已有活性限时与清理（提交 2d8bb2c）：放弃的任务 cancel → 等终态 → cleanup，**渲染机不再自动清理**，所以每个任务号必须被清掉，清不掉的写在 `projects/<课程>/renders/remote_pending_cleanup.json`，下次渲染开头自动重试；每个任务的阶段与用时在 `renders/remote_jobs.log`。**真实停顿下保护会不会触发没有测过**（用户决定不约故障注入，正式制作里遇到再处理）：出问题时带这两份文件找渲染机；自动模式出错只是回本机慢一点，**别在正式制作里默认加 `--remote-cpu`**；渲染前先 `python3 tools/video/remote_cpu_render.py probe`。本机回退：68 秒样片约 9.6 分钟（实测），整课约一小时（估计，未实测）。
- **磁盘**：2026-10-29 清理后可用约 71 GiB。**每次渲染会在 `/tmp` 留一个约 46 MB 的 `remotion-webpack-bundle-*`，从不自动删**（两周积了 707 个、15 GB）：没有渲染进程时用 `find /tmp -maxdepth 1 -name 'remotion-webpack-bundle-*' -exec rm -rf {} +` 清；`projects/*/renders/.remote-in-*` 是被杀掉的渲染遗留的上传输入，也可清。（不要改 `remotion-composer/render-tools/`：它在分块指纹里，改了会让所有已缓存的块重渲。）
- **仓库**：分支 `feat/whiteboard-scene-dashscope-image`，已推 fork，最近提交 2d8bb2c、f7410e4。仍未提交：`.claude/skills/anatomy/`（第三方 MIT 技能）与 `docs/anatomy-skill-evaluation.zh-CN.md`、渲染机原始证据目录、含地址的 acceptance json、`.remotion/`。

## 3. 做一节正式课的稳定做法（按阶段；清单在 `docs/whiteboard/checklists/`）

| 阶段 | 要点 | 注意 |
|---|---|---|
| 策划（计划模式） | 选单元（读 `00-总览.md`、LESSON-GATE 七步里涉及的单元）；写计划：选题标准、难点表、教学设计一页纸（`backward-design` skill）、与前一课的衔接；**教案页**；开题时问用户走**标准道还是试验道**（E89） | 先研究再建议；随口提的题目可以否定 |
| 提案 | 研究简报、提案、决策记录 | 提案里的断言要当假设真实运行验证（E69） |
| 脚本 | `build_script.py`；`lesson-fact-check`、`plain-language-review`；**审稿每类只做一轮**（事实核对、红队、读者测试各一轮，之后只复核改过的句子，E88） | 旁白无英文字母与阿拉伯数字；字数×0.238 秒/字＋静默＋段间 0.7 秒对账；本课实测 0.225 秒/字 |
| 场景计划 | 每个场景写“呈现手段”；**角色按需出场，写出每个角色的在场区间和依据**（E92）；板上有空位才站，数步子的段落板子往往占满 | 事件带旁白锚点；最后一项笔迹要在淡出前 ≥0.6 秒 |
| 素材 | 配音（样音先过）、字幕；插画与姿势要先问用户授权；**姿势图审：逐条胳膊追到肩膀，翻转前后各看一遍，指向类优先直接生成最终朝向**（E91） | 生图工具 `gen_images.py`；缺姿势就补，补完要重跑 `pose_metrics.py` |
| 剪辑 | 板书代码默认交给 **sol**；`rebuild_edit.sh`（lint 0 错、最后一笔 OK）→ `docs/whiteboard_sfx.py apply`（**每次重建后都要重跑**）→ 真实排版检查 → `--contact` 关键帧**逐块看全尺寸** → 样片 → 审阅页 | **不要重跑 `finish_edit.py`**：它会把已批准的 edit 检查点改回 awaiting_human |
| 合成 | `whiteboard_verify.py probe` → 整片渲染 → `verify --render-log` → 逐张看 4 秒一帧拼图和问答拼图 → `stills`、`local-ref` 对照 → `finish_compose.py` | 意外静音踩线时先告诉用户，用户决定保留才用 `--allow-silence 起 止 原因`（E94） |
| 发布 | 封面、简介（数字从归档记录读出并断言，断言要带“不能为空”检查，E96）、练习（`exercise-design`，答案来自真实运行，泄露检查）、`finish_publish.py` **只跑一次**，再加封面片头、成品包，之后用 `finish_publish_note.py` 重写检查点 | 正式课不得带“试验品”标注（E84：从试验课复制来的发布脚本要改）；系列名未定会报错 |
| 复盘 | 按 `docs/whiteboard/retro-template.md` 写，登记表加条目，跑 `whiteboard_registry.py coverage/render/check`；**跑 `docs/whiteboard_timeline.py <项目> [--since …]` 把每道口令的“生产／等用户”小时数存进数字存档**（E97）；等用户说“提交” | 复盘只写一遍，不往多处各记一份 |

**参照用时（试验品 2，口令内生产，不含用户等待）**：提案 0.28 小时、脚本（含教案页）1.95、场景计划 1.04、样音 0.30、素材 1.13；项目前策划约 4 小时。差异的原因和提速办法见 `docs/whiteboard/retro/experiment-workflow-vs-agent-time.md`；新系列首课＋原创实验本来就比 C 课慢，别拿 C 课的 40 分钟当目标。

## 4. 可复用的零件（别重造）

- **系列配置与风格**：`docs/whiteboard/series.yaml`、`docs/whiteboard/style-guide-agent.zh-CN.md`、词表 `docs/whiteboard/wordlist.yaml`、积木库 `docs/whiteboard_v2_kit.py`。
- **角色素材库** `projects/_cast/agent/`（41 个条目，含画风参考 `raw/`、提示词和生成记录）：老师 7 个姿势（含 `teacher_point_right_hand` 重画版、`teacher_thumbs_up`）、搭档 20 个姿势（读信、拿钥匙、拿方向盘、握栏杆、举旗、点头……）、校徽。画风参考 `raw/teacher_main.png`、`raw/robot_main.png`；插画卡片与道具（铁轨卡、方向盘卡、文件夹、剪刀、围栏等）在试验课 `projects/agent-workflow-or-agent-cn/assets/images/`，是否复用看新课内容。
- **本课脚本**（`projects/agent-workflow-or-agent-cn/scripts/`）：`_build_head.py`（Board、Finder 锚点查找）、`_body_helpers.py`（`char`、`pose_seq`、`pic`、`foot`、**`robot_on`**：搭档走入、滑动、原地蹦、退场）、`_build_tail.py`、`build_one.sh`、`rebuild_edit.sh`、`scene_common.py`、`validate_section.py`、`build_scene_plan.py`、`gen_images.py`（gen／sheet／pick）、`pose_metrics.py`、`board_free_space.py`（按时间量板上空位）、`finish_assets.py`、`finish_compose.py`、`make_*_review_artifact.py`（审阅页）。**新课建项目用 `docs/whiteboard_new_lesson.py`**；`series.yaml` 里 `template_lesson` 现在指向 `agent-messages-cn`（旧试验课），**要不要换成本课、换之前要不要先清掉试验标注，没测过，开工前先 dry-run 看它复制什么**。
- **检查与工具**：`whiteboard_lint.py`、`whiteboard_last_item_check.py`、`whiteboard_layout_check.py`（真实排版，几分钟）、`whiteboard_render.py`（`--plan/--stills/--contact/--sample/--final`）、`whiteboard_verify.py`、`whiteboard_timeline.py`、`whiteboard_registry.py`。
- **渲染机客户端的测试**：`tests/tools/test_remote_cpu_render_liveness.py` 与 `test_whiteboard_render_remote_liveness.py`（34 个，不联网）。

## 5. 这两周踩过的坑（登记号在 `docs/whiteboard/lessons-learned.yaml`）

等不存在的文件白等 48 分钟；8 路大模型并发有 2 路启动一分钟就被限流、当成“还在写”等了约 55 分钟（E90）；老师姿势翻转后两条胳膊挤在同一侧肩膀，到成片才被用户发现（E91）；搭档 99% 的时间站在老师旁边像摆设（E92）；整片规划被超长路径串崩（E95）；渲染机连接停顿时样片和整片无声卡住 29、15、6 分钟（E93，已修）；简介里的重要文件名写成“合同.docx”（真实“合同_final.docx”）会让“零丢失”的核对空过（E96）；记录口令的工具提示停下，我没停。

## 6. 没验证的（别当成已解决）

真实停顿下渲染保护的触发；渲染机代理路径几天的稳定性；任何一节课有没有被真人学生用过（审稿与盲评都是模型）；字幕时间是估计的（无语音识别核对）；本机整课回退的用时。

## 7. 新会话开场要向用户确认的事

1. **系列名**（智能体篇的名字，没定不能出封面和成品包）。
2. **第一节正式课选什么**：建议从大纲的推荐录制顺序和“白板课适配度＝高”的单元里提三个候选，各写一句选它的理由和需要先验证的断言，让用户选。
3. **走标准道还是试验道**（E89）。
4. **生图授权**：正式课要不要继续用网关的 Google 图像模型、预算怎么算（前两支的授权不延续）。
5. 记录口令后要不要每次先停（见第 1 节第 1 条）。
6. 未提交的 anatomy 技能和证据目录怎么处理。

## 8. 文件地图

`CLAUDE.md`、`AGENT_GUIDE.md`；`.claude/rules/whiteboard-protocol.md`、`whiteboard-craft.md`；`.claude/skills/whiteboard-lesson/SKILL.md`；`docs/whiteboard/{series.yaml,style-guide-agent.zh-CN.md,lessons-learned.yaml,checklists/,retro/}`；`docs/whiteboard-course-handoff.zh-CN.md`；`docs/remote-render-client.md`、`docs/remote-render-replies/`；`projects/roadmap-agent-engineer/{04-学习内容大纲/,review/LESSON-GATE.md,review/FREEZE-v1.1.md}`；试验课 `projects/agent-workflow-or-agent-cn/`（含 `EXPERIMENT.md`、导演手记链接）；记忆 `/root/.claude/projects/-home-MyProject-OpenMontage/memory/MEMORY.md`。
