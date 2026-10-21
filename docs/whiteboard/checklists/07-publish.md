# 阶段清单 · 发布与复盘（publish）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**口令**：发布通过 → 复盘 → 提交

**开始前先 Read**：
- `.claude/skills/exercise-design/SKILL.md` —— 写 make_exercises.py 之前读
- `.claude/skills/lesson-fact-check/SKILL.md` —— 写简介与练习前后各查一遍
- `docs/whiteboard/retro-template.md` —— 发布通过之后写复盘，把教训分流

**本阶段做什么**：
1. 练习：`make_exercises.py` + `run_exercises.sh`；缩略图与简介：先 `python3 docs/whiteboard_thumb_check.py projects/<课程> --list` 选 `THUMB_T`，再 `publish_prep.py`（不合格会停）→ `finish_publish.py`。
2. 封面：`docs/whiteboard_cover_maker.py` 的 LESSONS 加一行再运行；`docs/whiteboard_prepend_cover.py projects/<课程> --seconds 2`；`PYTHONPATH=. .venv/bin/python docs/whiteboard_release_pack.py`。
3. 写 publish 检查点 awaiting_human，停下等“发布通过”；用户说了之后：`docs/whiteboard_gate.py approve <项目> publish "<用户原话>"`。
4. 复盘：按模板写 `docs/whiteboard/retro/NN.md`，每条教训分流（检查／清单／叙述）并更新登记表，跑 `whiteboard_registry.py coverage`、`render`、`check`。
5. 等用户说“提交”再提交（提交后自动推 fork；同时在 `projects/` 里提交本课文本源的快照，本机库不推送）。

**产出**：exports/；成品文件夹；复盘一页

**已由脚本拦下**（先跑，红了就改，不要放宽阈值）：
- **[E61]** 缩略图取“该块最后一项写完之后、淡出之前”的一帧：python3 docs/whiteboard_thumb_check.py projects/<课程> --list 看每块的合格时间，THUMB_T 取其中之一，publish_prep.py 不合格会直接停；取完仍要看图（不要写到一半）；改默认取帧时间后 grep 核对；最后一行直到旁白末尾才写完时，取最晚且仍在淡出之前的一帧。 —— 第 21、27、40 课确有出错（第 27 课第一次取 162.5 秒最后一行没写完，改 164.2 秒） 〔第 9、17、21、23、27、33、38 课；脚本：`docs/whiteboard_thumb_check.py（新课的 publish_prep.py 已接入）`〕
- **[E70]** 用户明令“试验品、不属于课程”的项目：项目目录放 EXPERIMENT.md（gate status 不把它数成课、不当最近发布）；不往 docs/whiteboard_cover_maker.py 的 LESSONS 加行、不跑 docs/whiteboard_release_pack.py（它会清空重建课程成品文件夹）；封面徽章、标题、简介首行、练习、文件名都标注；已批准的成片不动；成品放 projects/试验品_技术测试/。 —— 第一个试验品一通过发布门，旧版 status 就写“已发布 44 课”（回测 t_gate_experiment 复现并拦住） 〔脚本：`docs/whiteboard_gate.py`〕

**要人判断**（逐条过一遍）：
- **[E62]** 封面：课名、缩略图字等一切手写体文字不能含小写 c/o（不能写 switch）；“第 N 课”标签按文字宽度自动加宽；封面代码行不超过约 30 个字符，含双引号要转义；出图后一定看一眼。 〔第 21、29、31 课；拟做成脚本：cover_maker 加字形检查（可选）〕
- **[E63]** 练习与验证程序要在 -Werror 下编译：演示“改不到”的函数里打印该参数（否则 set but not used）；sizeof 数组形参用 int *arr 的正确写法；丢掉 fscanf 的返回值会编译不过；文件只留用到的函数（unused-function 先看原文再删，不放宽选项），写完逐个编译；只编译的例子里别留没用的函数。 〔第 15、20、28、38、39 课〕
- **[E64]** 练习说明要写清运行提醒：需要输入的怎么送；故意少写 break 或抄满的练习写清编译选项（-Wall、-Wextra，不加 -Werror）；只能用特定参数运行的程序写明；ASan 报泄漏时重定向的 stdout 可能丢行，答案要写明，板上只放 SUMMARY 一行；泄漏练习把其余的卡整串还掉，只留要演示的那一张；课里已演示的错误练习放不下时要明说。 〔第 15、31、32、35、39、40 课〕
- **[E65]** 练习答案的“怎么改”只贴改的那个函数或 case 块，不贴整份程序；练习保持一个文件，不拆成题目和答案两个文件（用户 2026-10-19 决定）；每题标用途，答案不泄露到题面。 〔第 42 课〕
- **[E66]** 写练习前读 exercise-design；写简介与练习前后各跑一次 lesson-fact-check。
- **[E75]** 板上写“回答太长、末尾有表情没画”这类标注，要对每一处所引的那一遍实跑逐条核对（同一例子两遍实跑可能不一样）；简介或旁白引官方文档的计费或保存说法，只写到页面写的那个用法。 —— K8 答案旁的小注只对两遍实跑中的一遍成立；OpenAI 页面只对 previous_response_id 串联写了计费，视频旁白说得更宽（用户选保留，简介已写窄）
