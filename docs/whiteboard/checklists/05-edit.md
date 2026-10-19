# 阶段清单 · 剪辑与样片（edit）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**口令**：样片通过，开始合成

**本阶段做什么**：
1. 改 `_body_boards.py` 等源文件，运行 `bash scripts/rebuild_edit.sh`（拼接 build_edit.py、跑 lint，并跑 last_item_check：每块最后一项要在淡出前 0.6 秒写完，首次不过是常态，把最后一项提前再跑）。
2. 用 `docs/whiteboard_render.py projects/<课程> --contact` 看每块关键帧；出样片（`--sample 起 止`）。
3. 写 edit 检查点 awaiting_human，停下等“样片通过，开始合成”；用户说了之后：`docs/whiteboard_gate.py approve <项目> edit "<用户原话>"`。

**产出**：edit_decisions.json；render_props.json；样片

**已由脚本拦下**（先跑，红了就改，不要放宽阈值）：
- **[E38]** 手写体里没有 0、o、c、C、大写字母和单个拉丁字母：命令、文件名、代码、数字、零、终点牌一律用等宽字体叠写；写完先跑 lint；字幕里单个 c、o 字符指定拉丁字体。 —— 手写体字库里这些字是方块或像别的字母；第 4、16 课栽过 〔第 4、16、18、22、23、25、32 课；脚本：`docs/whiteboard_lint.py`〕
- **[E39]** 等宽字体里不能写中文和全角符号（含“→”）：标签（手写）与数值（等宽）分开写；等宽里只用半角 = + 等符号；计划里的汉字数字放不进等宽，板上改成阿拉伯数字并写进偏离说明。 〔第 16、33、39 课；脚本：`docs/whiteboard_lint.py`〕
- **[E40]** 手写体里不要混写拉丁字母或文件名（如 list.txt 拆成手写加等宽）；lint 拦不住，要看关键帧总览。 〔第 40 课；脚本：`docs/whiteboard_lint.py（WARN：手写体里文件名、函数调用、长英文单词与中文混写）`〕
- **[E41]** 内存单元格的 name 只用拉丁字母（p、q、age）；中文说明另写 write。 〔脚本：`docs/whiteboard_lint.py（WARN）`〕
- **[E42]** 板上元素里不能有 null 值（until=None 会被渲染器当 0，箭头和小格消失）；没有 until 就不写这个键。 〔脚本：`docs/whiteboard_lint.py`〕
- **[E50]** 每块白板最后一项笔迹要在淡出前写完（余量 ≥0.6 秒）；剪辑阶段首次不过是常态，把最后一项提前再跑；结尾三句回顾提前触发，余量别只剩零点二秒。 —— 以这个脚本回测所有课：第 1–40 课里 30 课至少有一块板在淡出开始后才写完（20 课超过半秒，324 块里 51 块），抽看的 3 个淡出前一帧最后一行都只写了一半；第 41–43 课最小余量 +0.65、+0.82、+1.19 秒；逐课清单见 docs/whiteboard/old-lessons-last-item-report.zh-CN.md 〔共 11 课，首见第 12 课；脚本：`docs/whiteboard_last_item_check.py（起步模板的 rebuild_edit.sh 已并入，不合格即让构建失败）`〕
- **[E51]** 渲染前先跑 docs/whiteboard_lint.py（build_edit.py 末尾已调用），再用 whiteboard_render.py --contact 看每块关键帧，之后才 --final；改一块只重渲一块。 —— 第 16 课渲完才发现方块字，整片重渲 〔第 16 课；脚本：`docs/whiteboard_lint.py`〕

**要人判断**（逐条过一遍）：
- **[E43]** 箭头：一摞卡等竖向连接用短的手绘 stroke 箭头，memory 竖箭头两格间隙要 ≥88 px（lint 会拦）；指向卡的箭头别穿过它的 next 格（让出发格在目标卡正上或正下）；纸条放在大病房左边、箭头水平指向目标床；自指回环线的起止点靠边，避开正中上方的名字。 〔第 18 课〕
- **[E44]** 版面间距：带 name 的单元格离上方标题 ≥60 px；带 addr 的格子下方 60 px 内不放说明；small=True 的单元格宽度至少 215；等宽字一行最多约 60 个字符（字宽按 0.6 倍字号算）；长代码行先算宽度，别碰到右列；上下两行卡要给小格留位（卡串下移、问答区放右栏）。 〔第 15、24、28 课〕
- **[E45]** 强调单元格用 box() 红框，圈只用于数字或短词（圈半径比单元格大会压外框）。
- **[E46]** memory 单元格的 from（复制值）只在创建时生效：接收值的单元格推迟到复制发生的时刻再创建，创建时写 from。
- **[E47]** 同类版面先用已有的辅助：括号串逐字写、固定间距；树用固定坐标表与 cardc/edge/stub/pathbox；一排开关用 switches/bitname/placenum/flash 与 Slot；数组类板用 Arr/Hand/Sorted 记录当前写入项。 〔第 18、36、37、39 课〕
- **[E48]** 板标题只用中文，不带方括号等英文符号；代码放等宽字体。
- **[E52]** 取单帧与取样帧：取帧时间用锚点时间 + 书写时长之后、板结束前 0.5 秒之前；关键帧总览是缩略图，疑似缺内容时先单取同一时刻的静帧核对；静帧时间点要小于成片总长；按帧号取样用 select='not(mod(n,120))'，不用 fps 滤镜；测远程静帧写 docs/whiteboard_render.py <项目> --remote-cpu --stills <秒...>（选项放在 --stills 之前）。 〔第 7、24、27、37 课〕

**已是模板或工具的默认做法**（知道即可，别改掉）：
- **[E49]** 学校 logo 是白色线稿，放深蓝圆角底板，标题右移避让；代码块乱序书写时未写的行保留高度（模板已内置，不要改掉）。 〔脚本：`projects/<课程>/scripts/_build_tail.py 与 _body_helpers.py`〕
