# 阶段清单 · 合成与核对（compose）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**口令**：成片通过，进入发布阶段

**本阶段做什么**：
1. 先 `.venv/bin/python docs/whiteboard_verify.py probe` 并看输出。
2. 用 `nohup .venv/bin/python projects/<课程>/scripts/render_final.py > 日志 2>&1 &` 渲整课，`python3 docs/whiteboard_wait.py 日志` 等它结束。
3. 立刻 `.venv/bin/python docs/whiteboard_verify.py verify projects/<课程> --render-log 日志`（先备份 render.log，再量 ffprobe、响度、静音对问答时间线、黑帧、静止、md5，生成 4 秒一帧拼图和问答帧拼图）；**逐张看拼图**。
4. 独立对照：`docs/whiteboard_verify.py stills projects/<课程>`（6 张静帧远程对本机逐字节相同）；`nohup … docs/whiteboard_verify.py local-ref projects/<课程> > 日志2 2>&1 &`（K3/K6 本机对照 PSNR，先告诉用户这是对照）。
5. 看完写 `validation/compose-notes.json`，运行 `scripts/finish_compose.py`（读实测，不手填数字；写 compose 检查点 awaiting_human），停下等“成片通过，进入发布阶段”；用户说了之后：`docs/whiteboard_gate.py approve <项目> compose "<用户原话>"`。

**产出**：renders/final.mp4；render_report.json；final_review.json

**已由脚本拦下**（先跑，红了就改，不要放宽阈值）：
- **[E93]** 渲染机客户端有活性限时与清理（2026-10-29，agent/6 起渲染机不再自动清理）：控制请求单次 30 秒、含重试总共 75 秒（prepare、submit 只试一次），probe 总共 20 秒；上传每 30 秒至少走 256 KB 否则掐断，总期限随包大小（60 秒加大小除以 32 KiB/s，限 120 到 3600 秒，设计值不是实测下限），写完最后一字节就停止没流量检测、只等回复；排队分阶段计时（准备、上传、提交各有截止），--remote-queue-seconds 只是可选上限；渲染中 90 秒没有一次成功的状态应答才放弃（--remote-silent-seconds），日志读不到只提示，不按没有新帧取消；任务号启动时先打印并记入 renders/remote_jobs.log。放弃的任务：abort 信号结束阻塞的调用、不再 submit、submit 应答不明先按原任务号查 status 对账；然后 retire = cancel、等终态、cleanup（busy 重试），先记进 renders/remote_pending_cleanup.json（含属主进程号）再清理，清不掉的留在账本里，下一次渲染开头 sweep，属主进程还活着的不扫。超时则回本机渲染，--remote-cpu 报错退出（正式制作里别默认用）。测试 tests/tools/test_remote_cpu_render_liveness.py 与 test_whiteboard_render_remote_liveness.py（34 个，假进程）。真实停顿下的验证待正式制作中的真实任务（用户决定不单独约故障注入）；渲染机一侧见 docs/remote-render-support-request-20261029-client-liveness.zh-CN.md 与回执 docs/remote-render-replies/2026-10-29-client-liveness.md。 —— 2026-10-28 下午连接停顿，样片、关键帧、整片无声卡住 29、15、6 分钟：上传下载没有整体期限、读状态每次最长 120 秒还重试 4 次；第一版客户端又有缺陷（上传写完后 30 秒没流量就杀 ssh、放弃后还继续 submit、cancel 后立刻 cleanup 被拒、日志卡住被当成状态失联），渲染机回执逐条指出；agent/6 撤掉 6 小时隐式清理后，漏清的任务号会无限占盘 〔脚本：`tools/video/remote_cpu_render.py、docs/whiteboard_render.py`〕
- **[E94]** 成片核对里“意外静音”不过时不许手改测量结果：先把实测数字和位置告诉用户，用户决定保留才用 whiteboard_verify.py verify --allow-silence 起 止 原因 登记那一段（起止要与实测相差不超过 0.3 秒、不超过 2.5 秒，对不上就报错）；原因和用户的决定写进成片核对报告，检查点脚本把它从“结尾静音”里排除；其余检查照旧。 —— 金句后一段 1.295 秒的停顿比门槛 1.3 秒只差 0.005 秒，停顿在已批准的配音里；没有登记例外的办法就写不出合成检查点。我加例外功能时第一次漏了把它从结尾静音里排除，报告把结尾静音写成 2.8 秒，发现后已修 〔脚本：`docs/whiteboard_verify.py、docs/whiteboard_finish_compose.py`〕
- **[E95]** 渲染规划（--plan、--final）对板上每个字符串查是不是媒体文件名；超过 255 字节的串（SVG 路径、长文字）不是文件名，要跳过并容错 OSError。出样片和关键帧不走这段，所以整片规划才会崩，整片渲染前先跑一次 --plan。 —— 第 6 块的长虚线路径串让 media_hashes 抛 File name too long，--plan 和 --final 都崩；样片和关键帧都正常，所以到整片才发现 〔脚本：`docs/whiteboard_render.py`〕
- **[E135]** whiteboard_verify.py local-ref 不写 --boards 时，默认比 K3、K6（有 K6 的课）；只有四块板的课比 K3 和最后一块，并打印选了哪几块。不要再靠记住写 --boards K3,K4。 —— 第 3 课 local-ref 默认 K3、K6，本课没有 K6，K3 渲了约 10 分钟后报“no matching chunk file”，只能再跑一遍 K3,K4。 〔脚本：`docs/whiteboard_verify.py`〕
- **[E146]** 成片检查点里“整条配音由谁确认”按 approvals.jsonl 里素材门的 by 来写：评审放行写“没有真人从头试听整条配音（素材门由评审放行）”，用户亲口放行才写“由用户试听确认”；汇报只写“评审放行”，不写“用户听过”。 —— 第 4 课成片门第 1 次评审 fail：工具里写死了“由用户在素材阶段试听确认”，而样音、素材两门都是评审放行；检查点按指纹锁定，不改就永久留在记录里。 〔脚本：`docs/whiteboard_finish_compose.py`〕

**要人判断**（逐条过一遍）：
- **[E53]** 渲染前先 .venv/bin/python docs/whiteboard_verify.py probe 并看输出（通道、free_bytes 是否低于 min_free_bytes）；通道断开先告诉用户再决定，没有渲染机就在核对里如实写明、不编对照；渲染机故障后先 probe 再用真实小作业复测，整课大作业成功才算恢复；提交后读日志报 job log unavailable 时客户端会自动回退本机（约 30 分钟），先停下重试一次远程；render_result.json 的 backend 字段是请求值，不是实际后端（verify 的 --render-log 从作业日志里认真实后端）；样片阶段连接超时回退本机要如实告诉用户。 〔第 23、31、32、35 课〕
- **[E58]** 成片核对：verify 量完（ffprobe、响度、静音对问答时间线、黑帧、静止、md5）并生成拼图后，人要逐张看完 renders/review_dense/sheet_*.png（每 4 秒一帧）和 renders/review_cues/sheet.png（问答时刻与结尾），再下“正常”的结论；结尾单独看最后几秒的帧确认最后一句写完；整课渲染后的 4 秒帧才看得出相邻文字贴在同一行；logo、字幕、字形都要看，问答时答案不早于 answer_not_before；看完写 validation/compose-notes.json，再跑 docs/whiteboard_finish_compose.py（报告全部来自实测）。 〔第 16、30、40 课〕
- **[E59]** freezedetect 在稀疏白板上会报近似静止，要对照帧确认只有小字写入，并如实写进核对。 〔第 33 课〕
- **[E60]** 已说“成片通过”后才发现缺陷：如实说明、修复、重渲、按 4 秒一帧加问答帧重新核对，发布前请用户重新审看并再说“发布通过”；要重渲已批准的成片先告知用户（第 40 课 K2、K6）。 〔第 16 课〕
- **[E106]** 已通过的成片要改一块板书重渲时：先读 build_parts.py／_build_tail.py——build_one.sh 是部分构建，会把 whiteboard_scenes／edit_decisions／render_props 写成只剩一块；整片要用 rebuild_edit.sh 完整构建，并立刻比对没动的块的 JSON 逐字相同。构建会把 render_props 的旁白换回无音效版，必须再跑 whiteboard_sfx.py apply，并带上已通过那一档（--cues 与用户在样片页选的一致）。新加画面项后看三样：lint 警告数没有增加；whiteboard_sfx.py cues 没有多出不想要的声音（实心路径不透明度≥0.9 会被当成“便条出现”加一声弹出）；先用 --stills 抽几帧看版面。渲完：前面没动的段落用 ffmpeg psnr 逐帧比旧成片应全为无穷大，声音解码后逐采样比，差异只能在改动处。 —— 第 1 课 D12：第一版 backlog 写的是 build_one.sh（错的）；默认档重混会让 82 秒的声音和已通过成片不同（用户选的是全量档），是解码后逐采样比对才看出来；第一版槽二亮边用填色，让 lint 多一条对比度警告，改成只亮边又多出一声弹出，要把不透明度压到 0.9 以下。
- **[E112]** 核对笔记（compose-notes.json）里描述画面，逐项对着全尺寸关键帧写，不照事件表抄；新加的板书文字要在全尺寸帧上看有没有压到框线和卡片边；板上笔画和不透明的便条、卡片谁在上层，要看帧确认（笔画可能画在它们下面而不显示）。缩略联系表只能看整体，不能当这类核对的依据。 —— 第 2 课：K3 纸条上的红叉画在纸条图层下面，成片里一直看不到，而第一版核对笔记写成“红叉划掉纸条”；K4 新加的标签压在车厢外框线上，联系表看不出，全尺寸帧才看到。
- **[E136]** 已批准的旁白要改（用户在复审页选了 A）的完整链：备份到仓库外（检查点、approvals、决策记录、artifacts、scripts、code、配音、字幕、旧成片）→ 改作者文件（旁白、画面提示、数字登记、VERSION 与 NOTES）→ make_author_files.py → build_script.py（它会把脚本检查点写成 awaiting_human 并重写决策记录，跑完从备份恢复，再补一条决策和检查点 metadata 注记，gate status 仍是 approved）→ 画面提示相邻间隔不超过 10 秒，超了就给长句里加提示 → gen_tts.py 只重配被改的片段 → make_captions.py → ASSETS_REFRESH_ONLY=1 finish_assets.py → 改板书锚点和 scene_data（新句子要有画面事件，间隔不超过 9.5 秒）→ preflight_anchors.py → rebuild_edit.sh → whiteboard_sfx.py apply 全量 → 版面检查改动的块 → 渲染计划 → 整片远程渲染 → verify → stills → local-ref → 取全尺寸帧看改动处 → compose-notes 如实写“新旁白没人听过、没做样片、没再请 AI 复审” → finish_compose.py → 用户重说成片口令之后才写 publish 检查点。 —— 第 3 课、第 2 课都走过这条链；第 3 课的坑：build_script 覆盖检查点、数字登记要给新句子里的数字和“一个”类词登记或豁免、提示间隔超限、场景数据与板书的锚点两处都要改、local-ref 默认块。
- **[E143]** 托管时的材料：`renders/final.mp4`、`validation/compose-notes.json`、`renders/review_dense/sheet_*.png`（缺一拒绝），再用 --files 加 `renders/review_cues/`、verify／stills／local-ref 的日志与结果。Gemini 把成片切成 90 秒一段看并听；Codex 对着帧核 compose-notes 每一条（E112）；Opus 重跑 ffprobe／音量、亲自打开至少 5 张拼图或帧。配音语气、音色、动画节奏进“请你抽查”清单。 —— 托管放宽后成片门由评审放行；成片用户从没从头到尾看过时，评审通过不等于用户听过，要在结束时把最拿不准的时刻列给用户抽查。
- **[E157]** 合成核对除了 4 秒一帧的联系表，每块板的“最后一笔写完之后的一帧”都要打开全尺寸帧看：小字压框线、同一信息写两遍，在联系表里看不出。 —— 第 5 课 K3 约 300 秒“取页日期”小字压在引文卡下边框上、还和卡里的“A92 2026-11-06”重复，联系表和样片都没发现；我取全尺寸帧才看到，改成荧光标卡内日期、只重渲 K3（远程 96 秒）。
- **[E158]** 后台等待循环（until grep 日志里的结束标记）启动前，先删掉或换掉旧日志：被杀掉的旧运行会在日志里留下“结束”标记，等待循环会立刻提前结束。 —— 第 5 课等本机对照渲时，我杀掉了第一次的运行，它留在日志里的“localref rc=143”让新的等待循环立刻结束，我差点把没跑完的结果当成已完成；靠看进程和日志时间才发现。

**已是模板或工具的默认做法**（知道即可，别改掉）：
- **[E54]** 整课、样片、关键帧默认自动走远程渲染机（失败自动回退本机）；REMOTE_MIN_PART=30、STILLS_LOCAL_MAX=60 已内置，不用加参数；小任务（≤60 张静帧）走本机更快；慢的时候看 remote timing 里的 fetched 与 install 分开判断。 〔第 18 课；脚本：`docs/whiteboard_render.py`〕
- **[E55]** 分块渲染工具已处理 Remotion 超时与拼接内存：不要用 video_compose 默认的 600 秒超时；拼接时每个片段独立 -i（同一输入多次 trim 会缓存已解码帧、被系统杀掉）。 〔脚本：`docs/whiteboard_render.py`〕
- **[E56]** 本机对照渲染（K3、K6）：启动前先告诉用户那是对照、整课已走远程；然后 nohup .venv/bin/python docs/whiteboard_verify.py local-ref projects/<课程> > 日志 2>&1 &，用 python3 docs/whiteboard_wait.py 日志 等待——它自己备份远程分块、本机重渲、把两边时间戳统一成 N/30 再算 PSNR、还原备份并逐文件 md5 核对（阈值最低 45 dB），结果写进 validation/local-ref.json。 〔第 20、21、22、24、32、40、41 课；脚本：`docs/whiteboard_verify.py local-ref`〕
- **[E57]** 整课远程渲染一结束，立刻跑 .venv/bin/python docs/whiteboard_verify.py verify projects/<课程> --render-log <渲染作业的日志>——它第一步就把 renders/render.log 等备份到 renders/log_backup/（之后跑静帧会把它覆盖，分段计时就没了），再做全部机械核对。 —— 第 42 课的整课分段计时被后来的静帧覆盖，只剩总耗时；第 43 课做到了 〔第 42、43 课；脚本：`docs/whiteboard_verify.py verify`〕
