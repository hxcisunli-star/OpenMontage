# 阶段清单 · 脚本（script）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**口令**：脚本通过

**开始前先 Read**：
- `.claude/skills/plain-language-review/SKILL.md` —— 通俗度统计过关之后、请用户审阅之前做人工核对
- `.claude/skills/lesson-fact-check/SKILL.md` —— 挑高风险断言逐条查证，出三类报告

**本阶段做什么**：
1. 复制上一课 `build_script.py`，先改项目名与课号并 grep 核对，再另起一条命令运行（改与运行分开）。
2. 写 8 段旁白（每段 ≤600 字，三处真实静默各 3 秒，问答在本课指定的段），对账时长。
3. 断言过关后跑 `.venv/bin/python docs/whiteboard_script_lint.py projects/<课程> --allow 本课新词`（英文数字、难词、句长、锚点间隔、字数预算）和 `python3 docs/whiteboard_callbacks.py projects/<课程>`（回扣原话），再跑 plain-language-review 与 lesson-fact-check，结论写进请用户审阅的回复。
4. 写 `script-review.html` 与 script 检查点 awaiting_human，停下等“脚本通过”；用户说了之后：`docs/whiteboard_gate.py approve <项目> script "<用户原话>"`。

**产出**：script.json；script_review.json；teaching_examples.json；script-review.html

**已由脚本拦下**（先跑，红了就改，不要放宽阈值）：
- **[E27]** 旁白里没有英文字母与阿拉伯数字，数字说汉字；命令、文件名、函数名、typedef 之类只写在板上的等宽字体，旁白用中文说法（typedef 说“起别名”）。 〔第 19、20 课；脚本：`docs/whiteboard_script_lint.py（并且 build_script.py 里仍有 ascii_words、digits 断言）`〕
- **[E28]** 旁白不用难词与禁词（预处理器、展开、栈、调用栈、基准情形、堆、折半、一大堆、静态链表、命名空间、单元测试、断言……），自检拦下就换词（“折半”说“每次扔掉一半”，“一大堆”说“很多很多行”）；本课要教的新词要从难词表里去掉，但仍限制次数并检查大白话；教材里一词多义的词不用；检查口径别把否定说明算命中。 —— 词表原来在每课 build_script.py 里各存一份，第 38→41 课每课手工多加 5–7 个词；现在 142 个词只存一份，每词有 from 与 allow_in 〔第 16、30、34、37、41、42 课；脚本：`docs/whiteboard_script_lint.py + docs/whiteboard/wordlist.yaml（单一词表；新课 build_script.py 读它，NEW_TERMS 写本课新词）`〕
- **[E29]** 通俗度断言：平均句长 ≤24 字、最长句 ≤50 字；超了按句号拆句，不改字数。 〔第 36 课；脚本：`docs/whiteboard_script_lint.py（平均句长、最长句断言）`〕
- **[E30]** 写完首稿立刻对账时长：字数 × 0.238 秒/字 + 三次 3 秒静默 + 段间 0.7 秒（历史上实测比预估短 1–9%）；预估低于约 390 秒就补“讲清道理”的句子（为什么、怎么想），偏长就删不新增东西的句子，不凑字。 —— 13 课的首稿偏短或偏长 〔共 9 课，首见第 15 课；脚本：`docs/whiteboard_script_lint.py（打印字数预算；预估时长出 360–480 秒报错，偏离提案目标 8% 提醒）`〕
- **[E31]** 相邻画面提示间隔不超过 10 秒，超过要把长事件拆成两条。 〔第 33、34、36、39 课；脚本：`docs/whiteboard_script_lint.py（相邻提示间隔断言）`〕
- **[E73]** 新系列：难词表与课号按系列分开（wordlist.yaml 的 series_terms，项目名 agent- 开头为智能体篇）。（旧版本里的“回扣工具把后一个系列的裸‘第N课’当成 C 篇课号”只对写在脱钩之前的试验课成立，见 E81。） 〔脚本：`docs/whiteboard_script_lint.py、docs/whiteboard_callbacks.py、docs/whiteboard_new_lesson.py`〕
- **[E81]** 新系列与 C 课没有任何联系：旁白里不得出现 C 课的身份词（series.yaml 的 forbid_terms：C语言、医生、病历、病房、门诊、克隆门、结构体），不回扣、不用 C 课的比喻；旁白里的“第N课”指本系列自己的课（回扣工具按系列解析，找不到的课号会标出来）。试验课 agent-messages-cn（项目里有 EXPERIMENT.md）写在脱钩之前，仍按 C 课解析、不受禁用词约束。 —— 试验课用“第二课的克隆门”“结构体数组”回扣 C 课，用户明确：以后的课程与 C 语言课没有任何联系，教师不再是医生 〔脚本：`docs/whiteboard_script_lint.py、docs/whiteboard_callbacks.py、docs/whiteboard/series.yaml`〕

**要人判断**（逐条过一遍）：
- **[E32]** 引用别课内容前，对那一课项目的 script.json 找到原话再写，课号与措辞都要对（传地址是第 2 课；第 22 课原话是“有时原地变大，有时搬到新的地方”，不能写成“长大就是搬家”）。辅助：python3 docs/whiteboard_callbacks.py projects/<课程> 列出每处“第N课”和那一课最像的句子（要人看，并跑 lesson-fact-check）。 〔第 17、43 课〕
- **[E33]** 脚本写完、通俗度断言过关后，请用户说“脚本通过”之前：跑 plain-language-review 与 lesson-fact-check，把结论写进回复；已批准的内容有错先问用户（全部改／只改已确认的／保留），不静默改。
- **[E74]** 复制来的 build_script、finish_assets 等脚本，运行前 grep 写死的数字、日期、读音清单（响度、样音批准日期）和写已批准文件的语句（提案、提案检查点、脚本检查点），改成读实测；新课脚本不得再写已批准阶段的文件。 —— 本次逮到过：复制来的 build_script 会覆盖已批准的提案与提案检查点，finish_assets 带着第 43 课的响度数字与样音日期 〔拟做成脚本：whiteboard_new_lesson.py 扫描复制来的脚本里的写死数字与写已批准文件的语句〕
- **[E88]** 审稿类每类上限一轮：事实核对（两路）、红队、读者测试各一轮；之后只复核改过的句子，不再整稿重来。读者测试的残留疑问若与上一轮相同，说明已改不动，写进取舍交给用户，不开新一轮。 —— 试验课脚本阶段事实核对 2 轮、红队 2 轮、读者测试 3 轮，第二三轮大多重复第一轮已改完的意见；脚本阶段 2.3 小时、其中一次白等约 48 分钟
