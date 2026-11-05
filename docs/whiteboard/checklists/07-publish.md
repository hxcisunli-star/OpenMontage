# 阶段清单 · 发布与复盘（publish）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**口令**：发布通过 → 复盘 → 提交

**开始前先 Read**：
- `.claude/skills/exercise-design/SKILL.md` —— 写 make_exercises.py 之前读
- `.claude/skills/lesson-fact-check/SKILL.md` —— 写简介与练习前后各查一遍
- `docs/whiteboard/retro-template.md` —— 发布通过之后写复盘，把教训分流

**本阶段做什么**：
1. 练习：`make_exercises.py` + `run_exercises.sh`；缩略图与简介：先 `python3 docs/whiteboard_thumb_check.py projects/<课程> --list` 选 `THUMB_T`，再 `publish_prep.py`（不合格会停）→ `finish_publish.py --no-checkpoint`（只导出，检查点最后才写，E134）。链式命令先 `set -o pipefail`（E133）。
2. 封面：`docs/whiteboard_cover_maker.py` 的 LESSONS 加一行再运行（只对本课调用 make()，别用课号参数：它会连同号的 C 篇一起重建）；`docs/whiteboard_prepend_cover.py projects/<课程> --seconds 2`；`scripts/sync_description_chapters.py`（简介章节时间对齐）。
3. 电子书章：`code/assemble_chapter.py` → `build_site.py --link-media` → `check_site.py`（全过）→ 真浏览器看页内小实验与每张新图 → `build_site.py --link-media --export projects/<课程>/exports/ebook`。
4. 发布前交叉复审（E132）：两家各自独立两轮，处置表存 `validation/research/publish_review/`；已批准旁白里的问题单列交用户定（E136）。
5. 成品包与审阅：`PYTHONPATH=. .venv/bin/python docs/whiteboard_release_pack.py --series agent`；审阅页（`code/build_publish_page.py`）发布后，`scripts/write_publish_checkpoint.py` 写 publish 检查点 awaiting_human，停下等“发布通过”；用户说了之后：`docs/whiteboard_gate.py approve <项目> publish "<用户原话>"`。
6. 复盘：按模板写 `docs/whiteboard/retro/NN.md`，每条教训分流（检查／清单／叙述）并更新登记表，跑 `whiteboard_registry.py coverage`、`render`、`check`。
7. 等用户说“提交”再提交（提交后自动推 fork；同时在 `projects/` 里提交本课文本源的快照，本机库不推送）。

**产出**：exports/；成品文件夹；复盘一页

**已由脚本拦下**（先跑，红了就改，不要放宽阈值）：
- **[E61]** 缩略图取“该块最后一项写完之后、淡出之前”的一帧：python3 docs/whiteboard_thumb_check.py projects/<课程> --list 看每块的合格时间，THUMB_T 取其中之一，publish_prep.py 不合格会直接停；取完仍要看图（不要写到一半）；改默认取帧时间后 grep 核对；最后一行直到旁白末尾才写完时，取最晚且仍在淡出之前的一帧。 —— 第 21、27、40 课确有出错（第 27 课第一次取 162.5 秒最后一行没写完，改 164.2 秒） 〔第 9、17、21、23、27、33、38 课；脚本：`docs/whiteboard_thumb_check.py（新课的 publish_prep.py 已接入）`〕
- **[E70]** 用户明令“试验品、不属于课程”的项目：项目目录放 EXPERIMENT.md（gate status 不把它数成课、不当最近发布）；不往 docs/whiteboard_cover_maker.py 的 LESSONS 加行、不跑 docs/whiteboard_release_pack.py（它会清空重建课程成品文件夹）；封面徽章、标题、简介首行、练习、文件名都标注；已批准的成片不动；成品放 projects/试验品_技术测试/。 —— 第一个试验品一通过发布门，旧版 status 就写“已发布 44 课”（回测 t_gate_experiment 复现并拦住） 〔脚本：`docs/whiteboard_gate.py`〕
- **[E82]** 封面与成品包按系列取名与角色：C 篇仍是医生与“C语言白板课”（封面逐字节不变，回测核对）；新系列用老师加 AI 小搭档、系列名作右上角标识、成品文件夹叫“<系列名>_成品”。系列名由用户定，没定时封面与成品包明确报错，不用占位；每个系列的成品包只清空重建自己的文件夹。建课脚手架会提醒系列名还没定。 〔脚本：`docs/whiteboard_cover_maker.py、docs/whiteboard_release_pack.py、docs/whiteboard/series.yaml`〕
- **[E129]** 电子书一章里，没有展示的记录，它的 id 不能是某条已展示记录 id 的子串（整站检查在证据抽屉里按子串找记录 id，子串会让没展示的记录被当成展示了）；build_site.py 构建时直接拦，给两个 id 起名时别让一个包含另一个。 —— 第 3 课把温度 1.0、1.5 两行的记录命名成 ROWS_name_qw_hi，而 ROWS_name_qw 没展示，整站检查报“证据记录集合不符”，靠改名才过。 〔脚本：`docs/whiteboard/ebook/build_site.py`〕
- **[E130]** 章里的来源卡（fact 块）把说法清单里的“适用范围”逐字渲染给读者；说法清单（claims_used.json）是工作记录，里面有工具名、审稿编号、禁说编号时，章要用一份读者版（说法不变，适用范围改写，例：claims_book.json），build_site.py 构建时拦下带“Codex、WebFetch、Antigravity、提案、评审、读者测试、N 加数字、托管”等字样的来源卡。 —— 第 3 课发布前复审，Codex 把“来源卡里写着我与 Codex 各重取一次、我用 WebFetch 读到同一段、提案评审意见 2”报成阻断项：学生会看到制作过程的内部记录。 〔脚本：`docs/whiteboard/ebook/build_site.py`〕
- **[E139]** 电子书平台每加一类新图，都要有测试：每种记录能渲、文字被转义、脚注标签对（实测、示意、引文）、诚实规则当规则测（橙色只在这一次选中的词元上、停止符永不“被选中”、示意图不盖实测章）、行图文字带“共几种”。第 3 课的七种图在 tests/tools/test_ebook_blocks_l3.py，第 2 课的在 test_ebook_blocks_records.py。 —— 第 3 课给共用平台加了七种图和三处构建检查，第 1、2 章页面逐字节不变，是用构建前后对比和这些测试保证的。 〔脚本：`tests/tools/test_ebook_blocks_l3.py`〕

**要人判断**（逐条过一遍）：
- **[E62]** 封面：课名、缩略图字等一切手写体文字不能含小写 c/o（不能写 switch）；“第 N 课”标签按文字宽度自动加宽；封面代码行不超过约 30 个字符，含双引号要转义；出图后一定看一眼。 〔第 21、29、31 课；拟做成脚本：cover_maker 加字形检查（可选）〕
- **[E63]** 练习与验证程序要在 -Werror 下编译：演示“改不到”的函数里打印该参数（否则 set but not used）；sizeof 数组形参用 int *arr 的正确写法；丢掉 fscanf 的返回值会编译不过；文件只留用到的函数（unused-function 先看原文再删，不放宽选项），写完逐个编译；只编译的例子里别留没用的函数。 〔第 15、20、28、38、39 课〕
- **[E64]** 练习说明要写清运行提醒：需要输入的怎么送；故意少写 break 或抄满的练习写清编译选项（-Wall、-Wextra，不加 -Werror）；只能用特定参数运行的程序写明；ASan 报泄漏时重定向的 stdout 可能丢行，答案要写明，板上只放 SUMMARY 一行；泄漏练习把其余的卡整串还掉，只留要演示的那一张；课里已演示的错误练习放不下时要明说。 〔第 15、31、32、35、39、40 课〕
- **[E65]** 练习答案的“怎么改”只贴改的那个函数或 case 块，不贴整份程序；练习保持一个文件，不拆成题目和答案两个文件（用户 2026-10-19 决定）；每题标用途，答案不泄露到题面。 〔第 42 课〕
- **[E66]** 写练习前读 exercise-design；写简介与练习前后各跑一次 lesson-fact-check。
- **[E75]** 板上写“回答太长、末尾有表情没画”这类标注，要对每一处所引的那一遍实跑逐条核对（同一例子两遍实跑可能不一样）；简介或旁白引官方文档的计费或保存说法，只写到页面写的那个用法。 —— K8 答案旁的小注只对两遍实跑中的一遍成立；OpenAI 页面只对 previous_response_id 串联写了计费，视频旁白说得更宽（用户选保留，简介已写窄）
- **[E96]** 简介里的实测数字从归档的原始记录读出并用断言核对旁白；断言要带“不能为空”的检查（例如先断言匹配到了东西），名单和归档里的真实名称对不上时断言会空过。引来源原话要重新打开原页逐字核对，只用页面写到的范围。 —— 整理文件夹的重要文件，我写成“合同.docx”，真实是“合同_final.docx”，按我的名单“想删重要文件 0 回”会变成空检查；断言先拦到了另一处名字不对，顺着查出来
- **[E97]** 发布后跑 python3 docs/whiteboard_timeline.py projects/<项目>（项目前的工作用 --since 补），把每道口令的“生产”和“等用户”小时数写进复盘的数字存档；不要拿口令间隔当生产时间。 —— 上一支试验的口令间隔 5.4 小时里等用户占 3.20 小时，生产只有 2.51 小时；本课口令内生产 4.70 小时、等用户 1.13 小时 〔脚本：`docs/whiteboard_timeline.py`〕
- **[E101]** 简介、练习、电子书里带“每次、总是、一定、全靠、必然”的句子，逐条对着本课自己的实测数据核：数据里有重复就不能写“每次不同”，十遍都一样才能写“一字不差”；新加的提示框、括号解释也算，写完对一遍各节“视频里没讲”的标记和旁白（不要写“和视频一一对应”而那一节视频没讲）。 —— 第 1 课：电子书“想一想”和练习五参考讲法写“起名字每次不同”，自己的数据是十遍 5 种名字（一个出现 5 次）；发布前复审才发现。复审后我新写的提示框又说“把聊天软件拆开”和视频一一对应，那一节自己标着视频没讲，Codex 复核才抓到。
- **[E102]** 派复审（子智能体）读电子书、练习、简介时，材料给真实渲染出来的页面文字和成品包里的文件，不给自己拼的摘要；复审说“页面里有怪东西”，先打开真实页面或原帧再信；角色遮挡类警告看全尺寸帧（313 秒那条盖住的是飞进装配图的小卡片，不是搭档）。 —— 第 1 课五路复审里至少 4 条是材料伪影：原始 JSON、图注少半句、成片 416.73 秒（脚本旧估算，实测 371.32 秒）、f10 纸条没画（取帧点选早了）。没有逐条回原文核对就改，会改错地方。
- **[E103]** 电子书的取帧点（seek）要落在旁白那句话说完、画面事件已经画出来之后，不取句子开头；取完看一眼这一帧是否真有说明里写的东西（改帧后重截并更新 alt）。 —— 第 1 课 f10 取在 346 秒，旁白“比如刚才那张纸条”的“纸条”格在 349 秒才画出来，图与说明不符；视频本身是对的，只改取帧点和重截，不重渲。
- **[E104]** 改电子书章节的“替换表”（assemble_chapter.py 的 EDITS／UNDO）后：连跑两次，关键句数量不变；再用旧导出对新页面做文字 diff，差异必须恰好等于计划里的改动。整站检查（check_site）只看结构，抓不到措辞回退。修改一句已经追加进存储文本的话，先在 UNDO 里把旧追加句还原成词干，再套新措辞。 —— 第 1 课：给替换表加“新文本已在页面里就跳过”的规则后，早先被删掉的一句话悄悄回到了书里，check_site 29 项全过；后来改措辞又差点叠出两份。是文字 diff 和连跑两次的计数抓到的。
- **[E105]** 重跑 finish_publish.py 后，exports/metadata/description.txt 末尾“章节时间轴”下的章节行是没加封面偏移的旧时间（差 2 秒），而 chapters.txt 和 metadata.json 是已偏移的；成品包用后两者，不受影响，但这份 description.txt 要改成与 chapters.txt 一致。拟让 whiteboard_prepend_cover.py 顺带改写这一份（改共用工具要先跑回测）。 —— 第 1 课重跑导出后发现 description.txt 里是 1:22，视频里实际在 1:24；之前这份文件章节行是空的，没人发现。 〔脚本：`docs/whiteboard_prepend_cover.py`〕
- **[E108]** 书、简介、图注、结果文件里写“人工标注／人工逐条读／人工设计／真人”之前，核对到底是谁做的：AI 模型做的就写“AI 模型”，并写明几路、互相看没看、有没有真人。阴性结论里“其余的都……”这类概括，在那些组标完之前不能写成结论；标完后回头 grep 所有出处（结果文件、书、记忆、简介）逐处更正，旧文保留并追加更正。 —— 第 1 课书里写“人工逐条标注”，实际是 Claude 一路读；结果文件写“换一个模型都说不存在或无法确认”，写那句时 Qwen 其他设置还没标，补标后 Qwen 默认思考 30 个里有 1 个编造。是补标后回读才发现。
- **[E113]** 旁白变了、章节起点移动之后：先把 exports/metadata/metadata.json 的 chapters 和 chapters_original 换成 publish_meta.json 里新的未平移章节，再跑 whiteboard_prepend_cover.py（它沿用已有的 chapters_original，不读 publish_meta.json）；refresh_exports（或手改 description.txt 章节行）要在拼接之后；最后核对 chapters.txt 的时间＝段起点取整＋2 秒、首条仍是 0:00。 —— 第 2 课选 B 后第四章节从 292 秒移到 294 秒；若不手动同步，成品里的章节时间会悄悄用旧值（与 E105 同一类，这次的源头是 chapters_original）。 〔脚本：`docs/whiteboard_prepend_cover.py`〕
- **[E114]** 派审稿子智能体时，材料里要带上审稿人核数据要用的**原始文件**，不只给汇总（records.json）：原始调用记录、对照表、完整文本等；审稿人写“不确定／没有记录／材料里没有”，先查是不是我没给，回原始数据核一遍再判，不当成问题也不当成通过。 —— 第 2 课第 3 次复核给 Codex 的材料只有汇总记录，它把 19 段分词对照、120 份总数等于输入加输出、三段文字的字符数判成“不确定”，回原始数据全部成立；第 1 课也出过同一类（给它漏了记录，审稿人说没记录）。
- **[E132]** 发布前交叉复审（电子书、简介、练习、旁白）的做法：两家模型各自独立（Codex 可联网可跑命令，另给原始记录；Antigravity 只读文件），材料给真实渲染出来的页面文字、成品包里的文件、records 和说法清单，不给自己拼的摘要；第一轮之后改，第二轮只给“改了哪里＋改前写的是什么”，不给对方结论，并要求扫同类问题（返回表当分布、公式极限当真实行为、“说法不一”、没写每个模型各几遍、通用化的字段含义、内部工作痕迹，包括任务书措辞）；已批准的旁白里的问题单列交用户定，不静默改（见 E136）。复审结果存 validation/research/publish_review/，写处置表。 —— 第 3 课两轮共 32 条发现，阻断项 3 个都成立（来源卡工作记录、公式极限说成服务行为、练习里“怎么抽都是它”）；第二轮又查出第一轮改漏的同类句（练习五、练习一的“三十遍”）。Codex 另用脚本现算 46 格版本数、finish_reason、七张候选表，全部一致。
- **[E133]** 链式命令先写 set -o pipefail：cmd 后面接 | tail 再 && 下一步，会吞掉 cmd 的失败（管道的退出码是 tail 的），后面的步骤照样用旧文件跑完。改了脚本后，要核对新内容真的出现在导出里（grep 一句新话），不能只看没报错。 —— 第 3 课 publish_prep.py 的断言失败被 | tail 吞掉，finish_publish 导出了旧简介，我是最后 grep 新句子才发现，重做了导出和封面拼接。
- **[E137]** 官方引文卡上每一句话，都要在它标的存档页里逐字找到（脚本里用归一化空白后的子串断言）；一张卡引了两个存档页（英文原句在英文页、中文原句在中文页）时，两个编号都写，并在书里说明“存档 A… 是我们存档那几页的编号”；存档日期与重取核对日期如果不是同一天，两个日期都写。 —— 第 3 课谷歌云那张卡的英文句其实在英文页存档 A61，却标在中文页 A62 下；存档是 11 月 3 日取的，11 月 4 日重取核对，书里原先只写了 11 月 4 日。

**已是模板或工具的默认做法**（知道即可，别改掉）：
- **[E134]** 智能体篇起步模板的发布件：finish_publish.py 加了 --no-checkpoint（只导出，不写检查点；检查点由 write_publish_checkpoint.py 在复审、导出电子书、建成品包之后才写，读 validation/publish_export_log.json 和 review/publish/checkpoint_notes.json，要求整站检查通过）；sync_description_chapters.py 把简介末尾章节时间按 chapters.txt 对齐并断言三个文件一致（E105 的自动化）。不要改掉。 —— 第 3 课发布阶段这三件事都是现场补的脚本；写检查点太早会让用户读到“等你审”而复审还没做完，章节时间不对齐在第 2 课就出过。 〔脚本：`docs/whiteboard/starter-agent/scripts/`〕
- **[E138]** approvals.jsonl 里有托管的 start、halt、stop 事件行（没有 stage 和 gate），whiteboard_timeline.py 已跳过它们；同一道口令记录两次（旁白返工后重说成片口令）会各出一行，看时间表时知道第二行是返工。 —— 第 3 课写复盘时 whiteboard_timeline.py 遇托管事件行抛 KeyError。 〔脚本：`docs/whiteboard_timeline.py`〕
