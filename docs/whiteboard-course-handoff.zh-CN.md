# 白板课程项目交接文档（C 语言系列，已做完 15 课）

> 目的：新开一个 Claude Code 会话，读完本文档就能接着做下一课，不用重新摸索。
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

用户是中文 C 语言教师，在做一套“老师边讲边画”的白板风格教学视频，用 OpenMontage（`animated-explainer` 管道 + Remotion + DashScope Cherry 配音）逐课生产。**26 门课全部已发布（本地打包，未上传任何平台）**，没有进行中的课程；补漏路线 17–21 已走完，第 22–26 课（动态数组与 realloc、二分查找、比名字、读入会失败、先读一整行再分析）是路线之后新增的课；下一课由用户另定（候选见 playbook 9.3： 返回值与输入检查、`char *` 与字符串库函数、链表反转与尾指针、联合体与枚举）。**第 16 课起渲染流程已改进：分块渲染 + 多进程并行（本机整课 27 分钟，旧法 40+）+ 渲染前检查 + 关键帧总览 + 字体确定性 +（待对方升级后）远程 CPU/GPU 渲染（见第 5 节与 playbook 4.4）。**

| # | 课程 | 项目目录 | 成片时长 | 状态 |
|---|---|---|---|---|
| 1 | 冒泡排序 | `projects/bubble-sort-tutorial-cn` | 322.05 秒 | 发布已通过 |
| 2 | 函数传参：值传递与地址传递（克隆门） | `projects/c-value-vs-address-cn` | 475.65 秒 | 发布已通过 |
| 3 | 数组传参（病房比喻） | `projects/c-array-parameters-cn` | 467.29 秒 | 发布已通过 |
| 4 | 字符串（终点牌 `'\0'`） | `projects/c-strings-cn` | 356.42 秒 | 发布已通过 |
| 5 | scanf 与 &（读整数要 &，读字符串不用） | `projects/c-scanf-address-cn` | 327.15 秒 | 发布已通过 |
| 6 | 结构体传参（整张卡复印） | `projects/c-struct-parameters-cn` | 390.25 秒 | 发布已通过 |
| 7 | 指针初步（地址纸条是个变量，两个星号两个意思） | `projects/c-pointer-basics-cn` | 400.43 秒（加 2 秒片头后 402.45 秒） | 发布已通过 |
| 8 | 指针与数组（数组名是地址，函数数不出长度） | `projects/c-pointer-array-cn` | 397.31 秒（加 2 秒片头后 399.33 秒） | 发布已通过 |
| 9 | 函数返回值（带回来的是抄来的，不能交回局部地址） | `projects/c-function-return-cn` | 394.26 秒（加 2 秒片头后 396.28 秒） | 发布已通过 |
| 10 | 二维数组传参（列数为什么不能省） | `projects/c-two-dim-array-cn` | 389.61 秒（加 2 秒片头后 391.63 秒） | 发布已通过 |
| 11 | 动态内存分配（向医院申请病房，申请—检查—使用—归还） | `projects/c-dynamic-memory-cn` | 383.02 秒（加 2 秒片头后 385.04 秒） | 发布已通过 |
| 12 | 链表初识（数组要挪，病历卡不用挪：卡上多一栏纸条、头纸条、头插） | `projects/c-linked-list-intro-cn` | 394.39 秒（加 2 秒片头后 396.41 秒） | 发布已通过 |
| 13 | 动态链表（函数里申请一张卡并交回、交回新的头纸条、先存下一张再整串归还） | `projects/c-dynamic-list-cn` | 404.54 秒（加 2 秒片头后 406.57 秒） | 发布已通过 |
| 14 | 删除一张卡（病人出院：停在前一张、先绕过再还、删第一张交回新头） | `projects/c-list-delete-cn` | 397.99 秒（加 2 秒片头后 400.02 秒） | 发布已通过 |
| 15 | 按顺序插入（新卡该排哪：停在前一张、先连后面再改前面、三种位置） | `projects/c-list-insert-cn` | 396.54 秒（加 2 秒片头后 398.57 秒） | 发布已通过 |
| 16 | 递归（函数自己叫自己：一层层问一层层答、到头了就停、等它回来再接着做） | `projects/c-recursion-cn` | 376.73 秒（加 2 秒片头后 378.75 秒） | 发布已通过 |
| 17 | 变量的一生（局部、全局、static：病房看得见多远、能活多久） | `projects/c-variable-life-cn` | 362.67 秒（加 2 秒片头后 364.69 秒） | 发布已通过（本地打包，未上传） |
| 18 | 栈（一摞卡：只在最上面放和拿、后放的先拿；括号配对） | `projects/c-stack-cn` | 392.90 秒（加 2 秒片头后 394.92 秒） | 发布已通过（本地打包，未上传） |
| 19 | 结构体数组与 typedef（一排卡交给函数是地址、一张按值是复印；起别名只是多一个名字） | `projects/c-typedef-array-cn` | 410.17 秒（加 2 秒片头后 412.19 秒） | 发布已通过（本地打包，未上传） |
| 20 | 文件读写（打开、检查、读写、关闭；读的循环看读到几个；写会先清空、追加、关闭送出小篮子） | `projects/c-file-io-cn` | 391.13 秒（加 2 秒片头后 393.15 秒） | 发布已通过（本地打包，未上传） |
| 21 | 函数指针与回调（函数的名字就是地址；回调；同一个排序只换比较函数；标准库里现成的排序函数与固定模板） | `projects/c-func-ptr-cn` | 369.70 秒（加 2 秒片头后 371.72 秒） | 发布已通过（本地打包，未上传） |
| 22 | 动态数组与 realloc（容量与张数；满了用 realloc 换更大的房间；临时纸条接住并检查；旧纸条作废；翻倍） | `projects/c-realloc-cn` | 384.57 秒（加 2 秒片头后 386.59 秒） | 发布已通过（本地打包，未上传） |
| 23 | 二分查找（折半：左、右、中三个下标，每次扔掉没用的一半；必须先排好序；边界加一减一；最坏次数 15→4、1000→10、一百万→20；现成的 bsearch） | `projects/c-bsearch-cn` | 377.30 秒（加 2 秒片头后 379.32 秒） | 发布已通过（本地打包，未上传） |
| 24 | 比名字（等号比的是地址；strcmp 逐格比、返回负数零正数、零才是一样；终点牌编码零所以短的在前；strcpy 数组不能直接赋值、连终点牌一起抄、目的地字数加一格） | `projects/c-strcmp-cn` | 395.20 秒（加 2 秒片头后 397.22 秒） | 发布已通过（本地打包，未上传） |
| 25 | 读入会失败（scanf 交回一读到、零读不懂、负一没有字了；读不懂的字留在小篮子里；清掉这一行；没有输入了就收手；先放初值再检查） | `projects/c-scanf-check-cn` | 374.73 秒（加 2 秒片头后 376.75 秒） | 发布已通过（本地打包，未上传） |
| 26 | 先读一整行再分析（fgets 把整行读进数组、换行也进来、没有输入交回空纸条；sscanf 在数组里分析；读不懂整行扔掉不用清篮子；行太长只读一部分；用“数字加一个字符”探尾巴） | `projects/c-fgets-line-cn` | 392.40 秒（加 2 秒片头后 394.42 秒） | 发布已通过（本地打包，未上传） |

每个项目的成品在 `exports/`（`video/output.mp4`、`video/subtitles.srt`、`thumbnails/thumbnail.png` + `thumbnails/cover.png` + `cover_1280x720.jpg`、`metadata/*`）。`output.mp4` 是“带 2 秒封面片头”的发布版（`docs/whiteboard_prepend_cover.py` 生成，字幕与章节已后移 2 秒，并嵌入封面图）；原始成片和原始字幕仍是 `renders/final.mp4`、`assets/subtitles.srt`，没有改动。15 课的成品统一收集在 `projects/C语言白板课_成品/第NN课_课名/`（`.mp4`、`.srt`、`_封面.png`、`_简介.txt`；第 11 课起另有 `_课后练习.txt`（第 12–15 课同样有））+ `目录.txt` + 同名 zip，由 `docs/whiteboard_release_pack.py` 重建。

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
7. **剪辑**：`build_edit.py` = `_build_head.py` + `_body_helpers.py` + `_body_boards.py` + `_build_tail.py`（`cat` 拼接；**改源文件，不要改拼接产物**）。写完先跑 `docs/whiteboard_lint.py`（`build_edit.py` 末尾已调用）和 `docs/whiteboard_render.py projects/<课> --contact` 看每块的关键帧（也可 `render_stills.py <秒…>` 渲单帧），用 `ffmpeg xstack` 拼 2×2 大图用 Read 逐张看，修版面，再 `render_sample.py <名> <起点> 30` 出 30 秒样片，写 `edit` 检查点，**等“样片通过，开始合成”**。
8. **合成**（第 16 课起 `render_final.py` 转调分块渲染：只重渲指纹变了的块，详见 playbook 4.4；`render_final_full.py` 是旧整片版）：`nohup .venv/bin/python projects/<课>/scripts/render_final.py > $CLAUDE_JOB_DIR/tmp/final.log 2>&1 &`，后台等**真实进程**；完成后自己核对：`ffprobe`（分辨率/帧率/编码/时长）、`ebur128`（≈−16 LUFS）、`silencedetect=n=-40dB:d=1.2`（只应有两处问答停顿 + 结尾收尾静音，位置对 `narration_timeline.json` 的 `answer_not_before`）、`blackdetect`、抽 15 帧拼图看；写 `render_report.json`、`final_review.json` 和 `compose` 检查点。**等“成片通过，进入发布阶段”**。
9. **发布**：`publish_prep.py`（缩略图取帧要**画完且没淡出**，先看图再导出；SRT；章节；元数据）→ `finish_publish.py`（`ExportBundle`，`platform=generic, visibility=private`）→ 课后练习（第 11 课起：`code/exercises/*.c` 实测，`scripts/make_exercises.py` 生成 `exports/metadata/exercises.txt`，打包脚本会复制）→ 封面（`docs/whiteboard_cover_maker.py` 在 `LESSONS` 加一行，再运行 `... 7` 这样只出该课；带“第 N 课”序号）→ **成片开头加 2 秒封面**（`docs/whiteboard_prepend_cover.py projects/<课>`，第 7 课起必做，不重渲染，详见做课手册“片头封面规则”）→ `docs/whiteboard_release_pack.py` 重建成品文件夹和 zip → 写 `publish` awaiting_human。**等“发布通过”**，然后写 `publish` completed、更新记忆、把经验补进做课文档；提交与推送等用户说“提交”“推送到 fork”再做。

**渲染工艺改进（2026-10-07，第 16 课起；用户嫌“改一处就要整片重渲”，确认方案后实现）**

| 工具 | 作用 |
|---|---|
| `docs/whiteboard_lint.py <项目>` | 渲染前检查：等宽字体里的中文/全角（方块字）、手写体里的 0 与大写字母、`null`（`until: None`）、内存图竖箭头间隙 < 88、问答静默里提前出现的内容；错误退出码为 1。`build_edit.py` 末尾已调用 |
| `docs/whiteboard_render.py <项目> --final` | 分块 + 多进程渲染：每块白板一个帧区间，拆成并行部件，按指纹缓存到 `renders/chunks/`，只重渲变了的块，`concat -c copy` 拼接并一次混旁白；`--plan` 看哪些块过期与将用的后端，`--force K4` 强制，`--only K1,K5` 只渲指定板，`--out` 指定输出，`--keep-old` 保留旧缓存，`--sample 起 止` 出样片，`--local` / `--remote-cpu` / `--workers` / `--render-profile` 控制后端 |
| `… --stills 秒…` / `… --contact [块…]` | 单帧一次打包渲多张（约 0.7 秒/张，旧法约 5 秒）；`--contact` 出每块关键时刻的缩略总览 `renders/contact/K#.png` |
| `remotion-composer/render-tools/render_chunks.mjs` | 上面两个工具的 Node 端（打包一次，渲多段多帧） |

实测（第 16 课）：旧整片 2772 秒；分块单进程 2395 秒；**多进程 1625 秒（本机默认）**（逐帧对比旧版 PSNR 平均 55.3 dB、最低 47.3 dB，响度同）；缓存全命中 34 秒；改一个词只重渲一块共 6 分 27 秒。**每课新建时**：`render_final.py` / `render_stills.py` 照第 16 课那两个小文件复制（改项目名），`build_edit.py` 与 `_build_tail.py` 末尾的 lint 调用也要带上。限制：配音重生成使时间平移后面的块仍要重渲；改了 `remotion-composer/src` 或字体全部重渲；`render_sample.py` 仍是旧法。完成后抽帧改为 **4 秒一帧加每个问答时刻**，不再 28 帧稀疏抽样。详见 playbook 4.4。

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
- 第 14、15 课的做课经验提交已推送到 fork（PR #1，头提交 `0dc4155`）；之后的第 16 课与渲染工具改动**尚未提交**（见下）。早期状态：本地领先 fork **4 个提交**（含本交接文档的提交），均为文档更新、**未推送**；其中三个做课经验提交为：`b16d076`（第 4 课经验）、`8449938`（第 5 课经验）、`2970c5f`（第 6 课经验）。更早提交（`27cdb38` 及之前）已推送；用户 fork 里有 PR #1（6 个提交）。**推送/更新 PR 要用户明确要求**。
- 提交署名：本仓库没设全局 git 身份；提交时用 `git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit …`，提交信息末尾加 `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`（以当前会话系统提示的署名要求为准）。
- `projects/` 被 `.gitignore` 忽略，**课程产物不进 git**；真正需要版本管理的只有 `docs/` 和（如有）仓库代码。本文档新增在 `docs/`，已本地提交。
- `.env`、`apidocs/` 不提交。

---

## 8. 文件位置索引

| 内容 | 位置 |
|---|---|
| 做课经验手册 | `docs/whiteboard-course-playbook.zh-CN.md`（0 摘要、1 对照数据、2 设计方法、3 流程、4 脚本速查、5 验收、6 踩坑、7 协作、8 模板、9 附录） |
| 本交接文档 | `docs/whiteboard-course-handoff.zh-CN.md` |
| 渲染工具（第 16 课起） | `docs/whiteboard_render.py`、`docs/whiteboard_lint.py`、`remotion-composer/render-tools/render_chunks.mjs`、`remotion-composer/render-fonts/`（说明见 playbook 4.4） |
| 远程渲染（对方智能体配合） | 给对方的需求文档 **`docs/remote-render-agent-brief-v3.zh-CN.md`**（只读这份，取代 v1/v2）、自测包 `projects/_remote_kit/`（`docs/make_remote_kit.py` 生成）、回复目录 `docs/remote-render-replies/`、验收脚本 `docs/remote-render-test.sh`、客户端 `tools/video/remote_cpu_render.py`、对方的说明 `docs/remote-render-client.md` |
| 仓库规则 | `CLAUDE.md`、`AGENT_GUIDE.md`、`docs/stage-gates/` |
| 用户记忆 | `/root/.claude/projects/-home-MyProject-OpenMontage/memory/`（`MEMORY.md` 索引） |
| 每课审阅页 | `projects/<课>/script-review.html`、`scene-plan-review.html` |
| 每课关键产物 | `projects/<课>/artifacts/{research_brief,proposal_packet,script,scene_plan,asset_manifest,edit_decisions,render_report,final_review}.json`、`checkpoint_*.json`、`decision_log.json` |
| 每课成品 | `projects/<课>/exports/`；统一成品文件夹 `projects/C语言白板课_成品/` |
| 本地生图工具 | `tools/graphics/qwen_local_image.py`（说明见 playbook 2.8） |
| 中文使用指南与能力页 | 提交 `3ddfe33` 加入的文档 |

---

## 9. 下一课建议与未决事项

**策划下一课的做法**（用户说“策划下一个知识点”时）：先在计划模式下研究，不直接建项目；写计划文件，内容见 playbook 2.16：选题四条标准（前置讲过没有 / 能否从最近一两课长出来 / 新东西只有一两个 / 核心结论能否实测）、难点→学生怎么想→讲法→实测证据表、通俗度目标（平均句长 ≤24、最长 ≤50、旁白无英文字母与数字）；只见摘要的来源要标明，转述要对原文；用户批准计划后才建项目。用户随口提的题目只是想法，可以否定。

**已定路线**（用户 2026-10-05 批准）：

| 课 | 内容 | 回扣 |
|---|---|---|
| 13 动态链表（已发布） | 函数里申请一张卡并交回、交回新的头纸条、先存下一张再整串归还 | 第 2、9、11、12 课 |
| 14 删除一张卡（已发布） | 走路纸条停在前一张、先绕过再还、删第一张改头纸条（交回新头） | 第 2、11、12、13 课 |
| 15 按顺序插入（已发布） | 找位置（停在前一张）、先连后面再改前面、三种位置同一个函数 | 第 1、12、13、14 课 |
| 16 递归（已发布） | 函数里再叫自己（每叫一次出一位新医生）、到头了就停、等它回来再接着做 | 第 2、9、12–15 课 |
| 18 栈（已发布） | 栈＝一摞卡：放＝头插、拿＝删第一张、后放的先拿；括号配对（三种不配对、只数个数不行） | 第 13、14、16、17 课 |
| 26 先读一整行再分析（已发布） | 整行读进数组（换行与终点牌各占一格、没读到的格子不动）、空纸条＝没有输入、不看返回值旧内容当新输入、从数组里分析并看返回值、读不懂整行扔掉、行太长只读一部分且读成错数、12abc 用“数字加一个字符”探尾巴、编译器不一定提醒 | 第 4、11、20、22、25 课 |
| 25 读入会失败（已发布） | 读入函数交回读到了几个、一/零/负一三种含义、读不懂时变量不动所以先放初值、读不懂的字留在小篮子里、只重来会原地打转、清掉这一行、没有输入了就收手、清篮子循环也要认没有字了、编译器不一定提醒 | 第 5、11、17、20、22 课 |
| 24 比名字（已发布） | 等号比的是地址、字典顺序逐格比第一处不同说了算、strcmp 返回负零正且零才是一样、终点牌编码零所以短的排前面、按名字排与折半找、strcpy 复制名字、目的地字数加一格、没有提醒不等于没有错 | 第 4、8、19、21、23 课 |
| 23 二分查找（已发布） | 折半（看正中间，扔掉没用的一半）、左右中三个下标、必须先排好序、中间看过了要加一减一、找不到交回 -1、每多一倍的人最多只多看一次、bsearch 同一套路 | 第 1、11、15、19、21 课 |
| 22 动态数组与 realloc（已发布） | 容量与张数、realloc 扩容、旧纸条作废、临时纸条接住并检查（泄漏）、翻倍 998 对 9 | 第 9、11、19、20 课 |
| 21 函数指针与回调（已发布） | 函数也有地址（函数纸条）、回调、比较函数返回负数零正数、同一个排序换三种比法、qsort 固定模板 | 第 1、7、19、20 课 |
| 20 文件读写（已发布） | 文件纸条与四步（打开检查读写关闭，打不开给空纸条）、读的循环看读到几个、写会先清空与追加、关闭才把小篮子里的内容送进文件 | 第 5、11、17、19 课 |
| 19 结构体数组与 typedef（已发布） | 一排卡（下标加点）、整排交给函数是地址改得到、一张按值是复印、起别名只是多一个名字、结点里别名要等整句写完才有 | 第 3、6、12 课 |
| 17 变量的一生（已发布） | 大厅病房（全局）、加了静态的临时病房（static 局部）、“谁看得见”与“活多久”是两件事；一句话澄清函数前的 static | 第 2、9、11、16 课 |

**补漏路线**（用户 2026-10-06 确认；每课仍要先在计划模式研究、你批准计划后才建项目）：

| 课 | 内容 | 回扣 / 注意 |
|---|---|---|
| 17 变量的一生（局部、全局、static）（已发布） | 三种病房：临时病房、医院病房、大厅病房；static 局部是“记得住的临时病房”；三者活多久 | 第 2、9、11 课；补第 9 课推迟的 static |
| 18 栈（链表头插删头做栈，括号配对）（已发布） | 后进先出、放上去/拿下来；几乎只是给第 13、14 课起名字 | 旁白说“叠起来的卡”，术语要小心 |
| 19 结构体数组与 typedef（已发布） | 结构体数组、typedef 只是起别名；解决“看别人代码看不懂 typedef struct” | 第 3、6 课 |
| 20 文件读写（已发布） | 打开与关闭、写与读、打开失败要检查；用第 19 课的病历卡名单存盘 | 第 5、11、19 课 |
| 21 函数指针与回调（qsort 给名单排序）（已发布） | 函数名也是地址、把函数交给别的函数 | 第 1、7、19 课；抽象度最高 |

之后候选：动态数组 realloc、`char *` 与字符串库函数、scanf 返回值与输入检查、二分查找、链表反转与尾指针、共用体与枚举、给前十课补课后练习（等 16–21 做完再定）。

做下一课要注意（来自第 26 课）：**修改脚本和运行脚本不要串在同一条命令里**（第 26 课 finish_compose 的替换断言失败后旧脚本仍被运行，写出了错误的检查点，已改对重跑；先改、用 grep 或打印确认改成功，再运行）；研究报告 sources 至少 5 条；装配脚本里替换计数先数清、替换整行后检查逗号；编译提醒随函数与优化选项变化（fgets 与 scanf 同样 -O0 没有、-O1/-O2 有，sscanf 全都没有），课里只陈述现象；用户口令偶尔多一个字时意思明确按批准处理并说明；本课整课 182 秒（比上一课慢约 20 秒，原因未查），样片与关键帧都走远程，其余同下。
做下一课要注意（来自第 25 课）：首稿按字数反推时长，历史上实测比预估短 5–9%，预估低于约 390 秒就补讲清道理的句子；事件的后续锚点必须在主锚点之后出现（先写标题事件再逐步写）；编译提醒随优化选项变化且方向不固定（第 24 课 -O0 有、-O2 没有；第 25 课 -O0 没有、-O2 有），课里只陈述现象；用 sed 插入含引号与 & 的代码行容易误加反斜杠，插入后 grep 核对并看封面；手写体里“第二十课”写汉字（lint 会拦含零）；本课整课 159 秒、样片与关键帧都走远程，其余同下。
做下一课要注意（来自第 24 课）：编译器提醒会随优化选项变化（-O0 有、-O2 -Wall 没有），课里只陈述现象不下原因；测远程静帧要写 `docs/whiteboard_render.py <项目> --remote-cpu --stills <秒...>`（auto 模式 60 张以内走本机，选项要放在 `--stills` 之前）；`--force` 只接受一个值，本机对照用 `--final --local --only K3,K6 --force K3,K6`，对照前先告诉用户并备份远程分块与成片，对照后恢复并逐字节核对；取样帧用 `select='not(mod(n,120))'` 按帧号取，别用 fps 滤镜（时间标签有偏差）；mono 字宽按 0.6 倍字号算框位置；写完板书看最后几秒，别让句子写在最后一个短语上被淡出吃掉；样片这次走远程 54 秒，通道平时可用；其余同下。
做下一课要注意（来自第 23 课）：样片阶段远程通道可能连接超时并自动回退本机（第 23 课 218 秒），要如实告诉用户，整课阶段通道通常已恢复（177 秒）；练习里的“错误”先实测确认真的出错；手写体里的零与大写字母写完先跑 lint；缩略图取板书写完的那一帧并 grep 核对默认值；其余同下。
做下一课要注意（来自第 22 课）：补漏路线之后的课由用户指定或我按四条标准选题；首稿按字数反推时长，偏短先补讲清道理的句子；检查工具类的报告要先试不同开关组合再决定怎么讲（泄漏报告只在单开地址检查时出现）；手写体里大写字母会出方块字，等宽写 NULL；换默认值后要 grep 核对；成品文件夹名带空格时提醒用户 scp 加引号；整课仍默认走远程（第 22 课 216 秒，比第 21 课慢约 40 秒，原因未查）；启动本机对照渲染前先告诉用户那是对照并先备份远程分块；提交只在用户说“提交”时做，**推送已获用户授权**（用 `git -c 'credential.helper=!gh auth git-credential' push fork <分支>`，只推 fork，不推 origin，不强推）；写检查点用 `.venv/bin/python`。

做下一课要注意（来自第 21 课）：补漏路线已走完，下一课要先和用户商量；课里的每个“出错”都要先实验（比较函数用减法或只返回 0/1 在本机没有可见的错，所以只引 cppreference 的规则，不编“实测出错”）；先自己写再讲现成的函数，难的类型（`const void *`）只讲成固定模板；缩略图要避开末句写一半的时间点，封面代码行不超过约 30 个字符；整课仍默认走远程（第 21 课 175 秒）；启动本机对照渲染前先告诉用户那是对照，并先备份远程分块；写检查点用 `.venv/bin/python`。

做下一课要注意（来自第 20 课）：病历卡名单文件 `list.txt`（三行 1 6 / 2 4 / 3 8，编号 1 2 3、年龄 6 4 8）要留给第 21 课读出来排序；旁白里函数名一律用中文说法、英文只写在板上等宽字体；到没到末尾的循环多读一张只在最后一行有换行时出现（板上与练习只用有换行的文件）；直接丢掉 fscanf 返回值在 -Werror 下编译不过；整课仍默认走远程（第 20 课 167 秒）；启动本机对照渲染前先告诉用户那是 K3/K6 对照，并先备份远程分块；用户在配音还没生成完或渲染完成前说的“通过”不当批准；写检查点用 `.venv/bin/python`。

做下一课要注意（来自第 19 课）：病历卡例子（`struct card{int id;int age;}`，三张卡年龄 6 4 8）要留给第 20、21 课复用；旁白里 typedef 说“起别名”、不读英文；整课仍默认走远程渲染（第 19 课 175 秒，取回约 12 秒、装好约 3 秒）；用户在配音还没生成完时说的“素材通过”不当批准，等生成核对完再等一次口令；写检查点用 `.venv/bin/python`。

做下一课要注意（来自第 18 课）：整课与样片、关键帧默认自动走远程渲染机（agent/5，65 进程；失败自动回退本机），`REMOTE_MIN_PART=30`、`STILLS_LOCAL_MAX=60` 已内置，不用加参数；一摞/竖向排列的卡用短的手绘 stroke 箭头，不用 memory 竖箭头；括号字符串逐字写、固定间距；手写体里不能出现大写字母（`-Wall` 这类写成中文“常用的警告选项”，lint 会拦）；用户重复说了已处理的口令时，如实说明“已完成”并等下一个门的口令；写检查点要用 `.venv/bin/python`；提交要带 `-c user.name=… -c user.email=…`（仓库没配身份），推送要用户自己运行（本机无 GitHub 凭据）。

做下一课要注意（来自第 17 课）：同一条 `printf` 里既调用改全局的函数又读该全局会打印旧值 0，先存结果再另起一句读；引用别课内容前对该课 `script.json`（传地址是第 2 课）；缩略图取板子写完的帧；纯说话语速约 0.224 秒/字，按 0.24 估会偏长约 7%；第 17 课整课 `--local` 分块多进程渲染 1594 秒，**整课远程实验还没做**（用户要自己运行 `! FULL=1 bash docs/remote-render-test.sh ...`，期间不改 `docs/whiteboard_render.py`、`render_chunks.mjs`、`tools/video/remote_cpu_render.py`）。

做下一课要注意（来自第 16 课）：先跑 lint，再用 `whiteboard_render.py --contact` 看每块关键帧，然后才 `--final`；成片抽帧按 4 秒一帧加问答帧；等宽字体里不能有中文，标签与数值分开写；已经被说“通过”的成片发现缺陷要如实说明、重做、请用户重新审；两个“叫不完”的递归版本只编译不运行；旁白不说“栈”“调用栈”“基准情形”。

做下一课要注意（来自第 15 课）：渲染完成前用户说的“样片通过”“成片通过”不当批准，核对后请用户再说一次；练习文件只留用到的函数（-Werror 会挡 unused-function）；s7 这类长代码行先算宽度（55 字符、字号 28 会碰到右列）；LeakSanitizer 演示要把其余的卡还掉；每个错法各测各的编译器提醒；语速短句稿按 0.24 秒/字估（连续两课只差 1.2%）；命令里不要用 pkill -f。候选路线：指向头纸条的指针（两个星号，第 13–15 课范围外）、链表反转、查找与计数、给前十课补课后练习（待用户定）。

其他候选：中间插入与删除（接第 12、13 课）；选择排序放到以后的“结构体数组与排序”（接不上指针线；同分学生先后顺序补上第 1 课的“稳定”）；scanf 返回值与输入检查（要讲缓冲区与失败输入，需严格限定范围）；`typedef` 与结构体数组；`char *` 已降级（见 playbook 2.14）。

**未决/待办**
- 无进行中的课程。
- **远程 CPU/GPU 渲染：进行中**——已把 v3 需求文档和自测包交付，等对方智能体按 v3 实现并写回复（`docs/remote-render-replies/`）；之后由用户运行 `docs/remote-render-test.sh`（我们自己运行会被权限检查拦下），按结果写下一轮缺口文档，循环到验收全部通过。在对方声明 `src_overlay` + `fontconfig_self_managed` 之前，调度器自动用本机渲染（用户无感）。
- 课后练习从第 11 课起做：是否给前十课补练习，待用户定。
- 第 12 课结尾第三句回顾比旁白晚约 2 秒写完，没有重做（已在核对报告里记录）；第 13 课结尾回顾已提前触发，401 秒前写完；第 14 课 395 秒前写完；第 15 课 392 秒前写完。
- playbook 里个别“三门课/四门课”旧表述未改（描述当时事实）。
- 未做：语音识别核对字幕、动效化故事画面。

---

## 10. 给新会话的建议开场语（可直接贴给用户）

> 我已读完 `AGENT_GUIDE.md`、做课经验文档和交接文档：26 门课都已发布（本地打包），渲染已改成分块渲染并默认走远程渲染机、带渲染前检查。补漏路线已走完且已加做第 22–26 课，下一课先和用户商量，要我先研究并给计划吗？（策划我会先研究衔接、难点讲法和通俗度，你批准计划后才建项目，然后停在提案门等你批准。）
