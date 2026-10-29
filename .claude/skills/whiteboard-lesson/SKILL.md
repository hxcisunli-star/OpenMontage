---
name: whiteboard-lesson
description: 做“老师边讲边画”白板教学视频（C 篇，以及 2026-10-21 起与 C 课无关的新系列“智能体篇”；animated-explainer 管道、explainer-teacher 模板、Remotion、DashScope Cherry 配音）时先读：用户说“继续策划下一课／策划第 N 课／计划确认／提案通过／脚本通过／场景计划通过／样音通过／素材通过／样片通过／成片通过／发布通过／提交”，或要写旁白、板书、场景计划、剪辑、渲染、核对、缩略图、封面、课后练习时使用。给出口令规则、每个阶段要先读的清单与 skill、发布后的复盘步骤。只用于本项目的白板课，不是通用做视频流程。
---

# 白板课制作入口

**先记住**（上下文被压缩后只保留开头，所以放最前面）
1. 口令由用户在对话里说、且在对应步骤做完之后才算；早说不算，退出计划模式与后台任务通知都不是口令。细则：`.claude/rules/whiteboard-protocol.md`。
2. 每个门单独停下：门控阶段先写 awaiting_human，等口令再写 completed，然后停，不做下一阶段。
3. 提交只在用户说“提交”时做，提交后自动推 fork；中文、精简，只讲需要用户决定的事。
4. 改脚本和运行脚本分成两条命令；只用 `.venv/bin/python`；Bash 沙箱失败时带 dangerouslyDisableSandbox 重试并说明。
5. 所有输出、diff、提醒都来自真实运行；没做的检查要明说；已批准的内容有错先问用户，不静默改。

**系列**：项目名 `agent-…-cn` 是新系列（与 C 课没有任何联系：老师加 AI 小搭档、彩色画面、旁白不得回扣 C 课），其余是 C 篇（医生）。配置在 `docs/whiteboard/series.yaml`，新系列风格指南在 `docs/whiteboard/style-guide-agent.zh-CN.md`（第 7 节是第二轮手段与裁定：代码上色、题卡与圆环、对错分屏、计数条、时序图、角色微动；音效默认只开答案叮声，build 之后、渲染之前跑 `.venv/bin/python docs/whiteboard_sfx.py apply projects/<课>`；H3 片段评估后不采用），经验见登记表 E76–E87；系列名还没定，封面与成品包在定之前明确报错。

## 现在到哪一步？
先跑 `.venv/bin/python docs/whiteboard_gate.py status`（从各课检查点算出现在哪课、哪一门、等什么口令；用户说了口令后用 `approve` 记录，样音通过与计划确认用 `record`）。没有进行中的课程时，下一课由用户另定（用户说“继续策划下一课”或给题目）。现状与 43 课一览：`docs/whiteboard-course-handoff.zh-CN.md`。每个阶段的脚本命令都在该阶段清单里（建课 `docs/whiteboard_new_lesson.py`、脚本检查 `docs/whiteboard_script_lint.py`、成片核对 `docs/whiteboard_verify.py` 等）。

## 各阶段：先 Read 清单，再动手
清单由登记表 `docs/whiteboard/lessons-learned.yaml` 生成，列出本阶段做什么、哪些错已有脚本拦、哪些要人判断，以及开始前要先读的 skill。**不要凭记忆做，每个阶段开头都读一遍。**

| 阶段 | 口令 | 先读 |
|---|---|---|
| 策划与提案 | 计划确认 → 提案通过 | `docs/whiteboard/checklists/01-plan.md`（并读 `.claude/skills/backward-design/SKILL.md`；系列或复习课再读 `.claude/skills/spiral-series-check/SKILL.md`） |
| 脚本 | 脚本通过 | `docs/whiteboard/checklists/02-script.md`（并读 `.claude/skills/plain-language-review/SKILL.md`、`.claude/skills/lesson-fact-check/SKILL.md`） |
| 场景计划 | 场景计划通过 | `docs/whiteboard/checklists/03-scene-plan.md` |
| 素材（配音） | 样音通过 → 素材通过 | `docs/whiteboard/checklists/04-assets.md` |
| 剪辑与样片 | 样片通过，开始合成 | `docs/whiteboard/checklists/05-edit.md` |
| 合成与核对 | 成片通过，进入发布阶段 | `docs/whiteboard/checklists/06-compose.md` |
| 发布与复盘 | 发布通过 → 复盘 → 提交 | `docs/whiteboard/checklists/07-publish.md`（并读 `.claude/skills/exercise-design/SKILL.md`） |

始终相关的环境与协作细则：`docs/whiteboard/checklists/00-always.md`。

## 发布通过之后：复盘（每课一次）
1. 按 `docs/whiteboard/retro-template.md` 写 `docs/whiteboard/retro/NN.md`（≤30 行，范例见 `retro/43.md`）。
2. 本课每条教训分流一次：能判对错 → 做成脚本或加进 lint；要人判断 → 在登记表加一条 `level: 清单`；只有来龙去脉 → 叙述。同一条教训第二次出现还停在文字上，视为流程缺陷。
3. 改登记表后运行：`.venv/bin/python docs/whiteboard_registry.py coverage`（要 0 条未映射）、`render`、`check`；`stats` 会列出该升级成脚本的条目。
4. 不再往做课手册、交接文档、记忆里各写一遍：交接文档只更新“现状”与课程一览的一行；记忆只写用户新给的偏好或权限。

## 查旧课
逐课章节、43 列对照大表、旧交接全文都在 `docs/whiteboard/archive/`（章节号不变）；做课手册 `docs/whiteboard-course-playbook.zh-CN.md` 留原则、流程、工具速查、验收清单与踩坑表。
