# 阶段清单 · 剪辑与样片（edit）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**口令**：样片通过，开始合成

**本阶段做什么**：
1. 改 `_body_boards.py` 等源文件，运行 `bash scripts/rebuild_edit.sh`（拼接 build_edit.py、跑 lint，并跑 last_item_check：每块最后一项要在淡出前 0.6 秒写完，首次不过是常态，把最后一项提前再跑）。
2. 出样片之前量真实排版：`.venv/bin/python docs/whiteboard_layout_check.py projects/<课程> --stills 6`（本机几分钟；见 E67）：ERROR 必须改，WARN 对着标注图判断。
3. 用 `docs/whiteboard_render.py projects/<课程> --contact` 看每块关键帧；出样片（`--sample 起 止`）。
4. 写 edit 检查点 awaiting_human，停下等“样片通过，开始合成”；用户说了之后：`docs/whiteboard_gate.py approve <项目> edit "<用户原话>"`。

**产出**：edit_decisions.json；render_props.json；样片

**已由脚本拦下**（先跑，红了就改，不要放宽阈值）：
- **[E38]** 手写体里没有 0、o、c、C、大写字母和单个拉丁字母：命令、文件名、代码、数字、零、终点牌一律用等宽字体叠写；写完先跑 lint；字幕里单个 c、o 字符指定拉丁字体。 —— 手写体字库里这些字是方块或像别的字母；第 4、16 课栽过 〔第 4、16、18、22、23、25、32 课；脚本：`docs/whiteboard_lint.py`〕
- **[E39]** 等宽字体里不能写中文和全角符号（含“→”）：标签（手写）与数值（等宽）分开写；等宽里只用半角 = + 等符号；计划里的汉字数字放不进等宽，板上改成阿拉伯数字并写进偏离说明。 〔第 16、33、39 课；脚本：`docs/whiteboard_lint.py`〕
- **[E40]** 手写体里不要混写拉丁字母或文件名（如 list.txt 拆成手写加等宽）；lint 拦不住，要看关键帧总览。 〔第 40 课；脚本：`docs/whiteboard_lint.py（WARN：手写体里文件名、函数调用、长英文单词与中文混写）`〕
- **[E41]** 内存单元格的 name 只用拉丁字母（p、q、age）；中文说明另写 write。 〔脚本：`docs/whiteboard_lint.py（WARN）`〕
- **[E42]** 板上元素里不能有 null 值（until=None 会被渲染器当 0，箭头和小格消失）；没有 until 就不写这个键。 〔脚本：`docs/whiteboard_lint.py`〕
- **[E50]** 每块白板最后一项笔迹要在淡出前写完（余量 ≥0.6 秒）；剪辑阶段首次不过是常态，把最后一项提前再跑；结尾三句回顾提前触发，余量别只剩零点二秒。 —— 以这个脚本回测所有课：第 1–40 课里 30 课至少有一块板在淡出开始后才写完（20 课超过半秒，324 块里 51 块），抽看的 3 个淡出前一帧最后一行都只写了一半；第 41–43 课最小余量 +0.65、+0.82、+1.19 秒；逐课清单见 docs/whiteboard/old-lessons-last-item-report.zh-CN.md 〔共 11 课，首见第 12 课；脚本：`docs/whiteboard_last_item_check.py（起步模板的 rebuild_edit.sh 已并入，不合格即让构建失败）`〕
- **[E51]** 渲染前先跑 docs/whiteboard_lint.py（build_edit.py 末尾已调用），再用 whiteboard_render.py --contact 看每块关键帧，之后才 --final；改一块只重渲一块。 —— 第 16 课渲完才发现方块字，整片重渲 〔第 16 课；脚本：`docs/whiteboard_lint.py`〕
- **[E67]** 出样片之前量真实排版：`.venv/bin/python docs/whiteboard_layout_check.py projects/<课程> --stills 6`（本机、几分钟）。它在浏览器里量每个板书的真实盒子：叠字、文字被板边裁掉、压到字幕条或校徽、描边从中间穿过文字、内存格装不下自己的值、手写体或等宽体缺字（豆腐块）。ERROR 必须改，WARN 对着标注图判断；退出码 2 表示没量全，不算通过。whiteboard_lint 里的重叠警告只是估算。 —— 估算只认 write 一种板书、按字数算宽度（手写体实际比估的宽），代码板、内存格、图片、字幕条、校徽都不看；探针第一版也曾因字体没加载完而把手写字量窄，是靠把盒子画在真实静帧上才发现的。 〔脚本：`docs/whiteboard_layout_check.py`〕
- **[E78]** 改合成器（remotion-composer/src）前后各渲一套固定样本静帧并逐字节比较：.venv/bin/python docs/whiteboard_baseline_stills.py render <标签>，再 compare ref <标签>（参考集 projects/_baseline/ref：5 课 226 张，含每块首帧末帧、笔迹/图片/数组交换/内存复制进行到一半的帧）。先确认未改的代码连渲两遍逐字节相同；故意改变旧课画法就先用旧代码渲新参考集并写明。新字段必须可选，默认路径不加任何节点或属性（连“无变换的包装层”也不加）；新字段样例的静帧远程通道（不加 --allow-drift）要与本机逐字节相同。 —— 226 张静帧在合成器改动前后逐字节相同；样例 15 帧本机与远程逐字节相同；合成器缓存哈希只变一次（88799d85bb9b…） 〔脚本：`docs/whiteboard_baseline_stills.py（慢回测 t_composer_baseline_slow）`〕
- **[E79]** 角色不得盖住内容：探针给每张图输出 32×32 的不透明网格，规则按真实不透明像素量被盖的比例——文字 ≥3% 警告、≥15% 报错；便条、气泡、方块被盖 ≥10% 警告、≥25% 报错。便条要落在角色身旁，不是身后。under-character 的任何警告都要看全尺寸帧再下结论，不再当作“外框含透明角”的误报略过。内容完全相同的两项重叠（便条副本滑出原件）只报警告；重叠区完全落在更靠前一层的不透明块里不算撞字；镜头放大时不查出界。 —— 试点 s6：机器人站在落地的便条前面遮住了内容，上一轮把两条警告当误报放过，用户在对照视频里发现；新规则在未修的版本上报 5 个 ERROR，修后 0。探针改动后：三个进程同时重建打包缓存会互踩（每次改了 probe/index.tsx 之后的第一次三进程运行都失败），现在先起第一个进程、等它 bundle ok 再起其余，启动即死的进程自动再试一次；半透明的块（荧光笔 45%）不算遮挡 〔脚本：`docs/whiteboard_layout_check.py（remotion-composer/probe 与 docs/whiteboard_layout_rules.py 的 under-character 规则）`〕
- **[E86]** 代码上色：code 项可选 lang（"c" 或 "py"），合成器内置分词器（不装库）按关键字、类型、数字、字符串、注释、预处理、函数名上色，配色 kw=#9D174D、type=#0B5CAD、num=#92400E、str=#166534、com=#5B6472、pre=#6D28D9、fn=#0A645D（纸面底色上对比度最低 5.77、45% 荧光笔上最低 4.79）；不写 lang 时输出与以前逐字节相同（改合成器前后比较基线静帧，E78）；Board.code(…, lang=) 起步模板与试点都带；lint 校验 lang 取值，对比度检查按时间判断：只有同时在场（重叠超过 0.3 秒）的最上层色块才算盖住文字。运行结果面板用 kit 的 result_panel（行可标 cmd/good/bad 三种颜色）。 —— 代码多的课单色等宽字难读；第一版 lint 的对比度检查不看时间，把已经消失的色块也算成遮挡，误报 〔脚本：`remotion-composer/src/components/WhiteboardScene.tsx、docs/whiteboard_lint.py`〕

**要人判断**（逐条过一遍）：
- **[E43]** 箭头：一摞卡等竖向连接用短的手绘 stroke 箭头，memory 竖箭头两格间隙要 ≥88 px（lint 会拦）；指向卡的箭头别穿过它的 next 格（让出发格在目标卡正上或正下）；纸条放在大病房左边、箭头水平指向目标床；自指回环线的起止点靠边，避开正中上方的名字。 〔第 18 课〕
- **[E44]** 版面间距：带 name 的单元格离上方标题 ≥60 px；带 addr 的格子下方 60 px 内不放说明；small=True 的单元格宽度至少 215；等宽字一行最多约 60 个字符（字宽按 0.6 倍字号算）；长代码行先算宽度，别碰到右列；上下两行卡要给小格留位（卡串下移、问答区放右栏）。 〔第 15、24、28 课〕
- **[E45]** 强调单元格用 box() 红框，圈只用于数字或短词（圈半径比单元格大会压外框）。
- **[E46]** memory 单元格的 from（复制值）只在创建时生效：接收值的单元格推迟到复制发生的时刻再创建，创建时写 from。
- **[E47]** 同类版面先用已有的辅助：括号串逐字写、固定间距；树用固定坐标表与 cardc/edge/stub/pathbox；一排开关用 switches/bitname/placenum/flash 与 Slot；数组类板用 Arr/Hand/Sorted 记录当前写入项。 〔第 18、36、37、39 课〕
- **[E48]** 板标题只用中文，不带方括号等英文符号；代码放等宽字体。
- **[E52]** 取单帧与取样帧：取帧时间用锚点时间 + 书写时长之后、板结束前 0.5 秒之前；关键帧总览是缩略图，疑似缺内容时先单取同一时刻的静帧核对；静帧时间点要小于成片总长；按帧号取样用 select='not(mod(n,120))'，不用 fps 滤镜；测远程静帧写 docs/whiteboard_render.py <项目> --remote-cpu --stills <秒...>（选项放在 --stills 之前）。 〔第 7、24、27、37 课〕
- **[E68]** 真实排版检查按“有意”处理、所以不会报的：红“×”划掉某个值或整个框、画在文字上的短标记和整行划线、指向用的笔形指针、箭头尖落在标签上、别的条目画的强调框切到字（和故意圈词的框一模一样）；它也看不到动画过程中的瞬间重叠（只量“画完”的采样帧）。这些要靠出样片后看 --contact 的关键帧总览。
- **[E71]** 白板课中间插图片序列片段（frame_seq）：块内事件时间从各自起点算，后一块用 Board.relist 以已画完的样子同序重列（笔画抖动取决于笔画序号）；白板块自带约 0.33 秒淡入，后一块要比片段提前 0.4 秒开始、叠在片段末尾（画面相同）；片段背景取前一块白板的末帧（去掉字幕与校标，笔先移出板外），结尾淡入后一块的参考图；接缝用真实合成的像素差量（字幕条与校标除外）；后一块的 cut 带 clip_sha，缓存才认得新片段；真实排版检查看不进片段里面，另看静帧与 HyperFrames check。 —— 本次 s4 的片段：第一接缝 0 像素不同，叠化区只有笔不同；没有叠化时后一块会在片段后淡入一次 〔拟做成脚本：项目里的 clip_bg_still.py、join_check.py、finish_edit.py 通用化成 docs/ 工具（第二次用图片序列片段时做）〕
- **[E85]** 音效默认只开答案揭晓叮声（--cues light，第二轮裁定；pop 与 whoosh 默认关，--cues all 打开；背景音乐仍不加）。一条命令 docs/whiteboard_sfx.py apply <项目>（build 之后、渲染之前，样片与成片都带）：混音、核对静默与响度、把 render_props.json 的旁白指向 narration_sfx.wav（原路径记在 audio.narration.src_plain，apply --undo 撤销，audio 不进板书块指纹）。底层 cues/mix/check 从板书数据推提示点——便条、气泡、方块出现 pop，飞行起点前 15 毫秒 whoosh-short，答案揭晓后 0.3 秒 chime，项目可带可选字段 sfx 点名素材（合成器忽略它）；电平相对旁白语音 RMS（pop 与 whoosh −18 dB，chime −16 dB）；先混进旁白再渲染（合成器只放一条旁白轨），换音轨出有/无两版不用重渲；素材在 docs/whiteboard/sfx/（Pixabay 许可，CREDITS.md）。硬规则：问答静默（题目读完到 answer_not_before 的 3 秒）里不得有任何提示点，跨进去的截断淡出；混音后峰值要不高于 −1 dBFS（AAC 会过冲），落在旁白峰值上的提示点自动退让；80 毫秒内同名的提示点合并，否则叠成双倍音量；超出本块结束时间的项目（为插片段截短的板书）不发声；混完用 check 核对静默段与整体响度和无音效版一致。 —— 试点实测：58 个提示点，三段静默混前后完全一致、整体响度 −16.3 LUFS 不变；第一版峰值到 −0.2 dBFS（旁白本身 −1.5），有两个提示点落在旁白峰值上；261.15 秒有两个同刻的 pop；为插片段截短的 s7 里被截掉项目的 whoosh 仍会在片段播放时响。默认只开叮声的理由：旁白是主通道、板上有字，没有信息量的声音（每张便条一个 pop）是多余材料（多媒体学习的一致性原则），叮声标出“静默结束、现在公布答案”；我听不了，所以取保守默认，全量版成片留给用户听 〔脚本：`docs/whiteboard_sfx.py`〕
- **[E87]** 第二轮 kit 手段（只用现有字段，不动合成器）：char(…, idle=True) 呼吸摆动；quiz_card 加 ring 预测题卡与三段圆弧倒计时（最后一段在答案揭晓前 0.4 秒消失）；split_panels 加 mark_ok/mark_bad 对错分屏与对勾红叉；result_panel 运行结果面板；token_meter 词元计数条（历史越摞越高、红色上限线、最旧便条滑出）；lanes 加 lane_msg 时序图；curve 曲线图（不进手段清单：试点没用到、没在课里验证过，首次使用必须过排版检查并看全尺寸帧）。用法与参数见 kit 文件里各函数的说明与风格指南第 7 节；手段清单见 series.yaml。做完先跑测得的排版检查，警告看全尺寸帧。计数条越线的部分会顶到上方标题，底边要留余量；浅色面板上的灰字用 PANEL["title"] 色。 —— 第二试点 s1–s8 里用过除曲线图外的各项（结果面板、时序图、题卡与圆环在 s2，红叉与哎呀、对错分屏、计数条在 s7，题卡与圆环在 s8，微动在多个场景）；曲线图只有 kit 函数和回测，试点没有场景用到，没在课里验证过。计数条第一版越线处压到标题（底边改到 760），浅色面板上的灰便条字看不清（改用面板标题色） 〔脚本：`docs/whiteboard_v2_kit.py`〕

**已是模板或工具的默认做法**（知道即可，别改掉）：
- **[E49]** 学校 logo 是白色线稿，放深蓝圆角底板，标题右移避让；代码块乱序书写时未写的行保留高度（模板已内置，不要改掉）。 〔脚本：`projects/<课程>/scripts/_build_tail.py 与 _body_helpers.py`〕
- **[E72]** 非白板块不加载手写字体：夹在白板课里的图片序列块已内置 useWbFont()，字幕不会变方块（补丁已保留，缓存哈希 67f5d852… 变为 8e7636c3…，只影响以后重渲染旧课）。 〔脚本：`remotion-composer/src/Explainer.tsx（FrameSequenceScene 调用 useWbFont）`〕
- **[E77]** 合成器的可选字段（都不写就和以前画得一模一样）：layer:"top"（顶层笔画盖在图片与文字上；顶层手写与图片，图片最后画，角色站最前）、笔画的 fill/fillOpacity/shadow/width:0 与新形状 path（自带路径，box 只供工具用）、手写/图片/笔画的 move 关键帧（dx/dy/scale/sy/rot，缺的字段沿用上一个键，帧间缓动）+ 静态 rot + origin（一组里各部分用同样的键与同一原点）、图片的 radius/border/shadow、板级 camera（缩放≥1，网格一起缩放）。便条、气泡、柱子、方块、角色、飞行副本用 docs/whiteboard_v2_kit.py（slip/sticky/bubble/bar/block/char/fly/highlight）。飞行的便条副本：放顶层、字瞬间出现（instant）、起飞前 0.1 秒才出现，否则起飞瞬间两份字叠在一起（普通层）或原件的字被盖掉而副本的字还没写出（顶层但逐字写）。镜头只推近、不平移：平移会把标题推到固定的校徽下面；推近后左右的内容要还在画面里。 —— 试点 s4 的便条飞行与镜头各返工两次，都是起飞/平移的静帧才看出来；Board 的新参数有回测（t_board_v2），试点项目的 Board 与起步模板是同一份代码 〔脚本：`remotion-composer/src/components/WhiteboardScene.tsx、docs/whiteboard_v2_kit.py、起步模板 docs/whiteboard/starter/scripts/_build_head.py 的 Board`〕
