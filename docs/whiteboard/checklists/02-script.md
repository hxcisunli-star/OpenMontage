# 阶段清单 · 脚本（script）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**口令**：脚本通过

**开始前先 Read**：
- `.claude/skills/plain-language-review/SKILL.md` —— 通俗度统计过关之后、请用户审阅之前做人工核对
- `.claude/skills/lesson-fact-check/SKILL.md` —— 挑高风险断言逐条查证，出三类报告

**本阶段做什么**：
1. 复制上一课 `build_script.py`，先改项目名与课号并 grep 核对，再另起一条命令运行（改与运行分开）。
2. 写 8 段旁白（每段 ≤600 字，三处真实静默各 3 秒，问答在本课指定的段），对账时长。
3. 断言过关（句长、英文与数字、难词、锚点间隔）后，跑 plain-language-review 与 lesson-fact-check，结论写进请用户审阅的回复。
4. 写 `script-review.html` 与 script 检查点 awaiting_human，停下等“脚本通过”。

**产出**：script.json；script_review.json；teaching_examples.json；script-review.html

**已由脚本拦下**（先跑，红了就改，不要放宽阈值）：
- **[E27]** 旁白里没有英文字母与阿拉伯数字，数字说汉字；命令、文件名、函数名、typedef 之类只写在板上的等宽字体，旁白用中文说法（typedef 说“起别名”）。 〔第 19、20 课；脚本：`projects/<课程>/scripts/build_script.py（ascii_words、digits 断言）`〕
- **[E28]** 旁白不用难词与禁词（预处理器、展开、栈、调用栈、基准情形、堆、折半、一大堆、静态链表、命名空间、单元测试、断言……），自检拦下就换词（“折半”说“每次扔掉一半”，“一大堆”说“很多很多行”）；本课要教的新词要从难词表里去掉，但仍限制次数并检查大白话；教材里一词多义的词不用；检查口径别把否定说明算命中。 —— 词表在每课 build_script.py 里各存一份，第 38→41 课每课手工多加 5–7 个词 〔第 16、30、34、37、41、42 课；脚本：`projects/<课程>/scripts/build_script.py（FORB、JARGON 断言）`；拟做成脚本：单一词表 wordlist.yaml + docs/whiteboard_script_lint.py（第二批 11）〕
- **[E29]** 通俗度断言：平均句长 ≤24 字、最长句 ≤50 字；超了按句号拆句，不改字数。 〔第 36 课；脚本：`projects/<课程>/scripts/build_script.py（avg_sentence_chars、max_sentence_chars 断言）`〕
- **[E31]** 相邻画面提示间隔不超过 10 秒，超过要把长事件拆成两条。 〔第 33、34、36、39 课；脚本：`projects/<课程>/scripts/build_script.py（max_cue_gap_seconds 断言）`〕

**要人判断**（逐条过一遍）：
- **[E30]** 写完首稿立刻对账时长：字数 × 0.238 秒/字 + 三次 3 秒静默 + 段间 0.7 秒（历史上实测比预估短 1–9%）；预估低于约 390 秒就补“讲清道理”的句子（为什么、怎么想），偏长就删不新增东西的句子，不凑字。 —— 13 课的首稿偏短或偏长 〔共 9 课，首见第 15 课；拟做成脚本：字数预算表（docs/whiteboard_script_lint.py，第二批 11）〕
- **[E32]** 引用别课内容前，对那一课项目的 script.json 找到原话再写，课号与措辞都要对（传地址是第 2 课；第 22 课原话是“有时原地变大，有时搬到新的地方”，不能写成“长大就是搬家”）。 〔第 17、43 课；拟做成脚本：docs/whiteboard_callbacks.py + lesson-fact-check（第二批 10）〕
- **[E33]** 脚本写完、通俗度断言过关后，请用户说“脚本通过”之前：跑 plain-language-review 与 lesson-fact-check，把结论写进回复；已批准的内容有错先问用户（全部改／只改已确认的／保留），不静默改。
