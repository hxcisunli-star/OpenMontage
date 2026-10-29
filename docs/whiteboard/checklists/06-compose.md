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

**要人判断**（逐条过一遍）：
- **[E53]** 渲染前先 .venv/bin/python docs/whiteboard_verify.py probe 并看输出（通道、free_bytes 是否低于 min_free_bytes）；通道断开先告诉用户再决定，没有渲染机就在核对里如实写明、不编对照；渲染机故障后先 probe 再用真实小作业复测，整课大作业成功才算恢复；提交后读日志报 job log unavailable 时客户端会自动回退本机（约 30 分钟），先停下重试一次远程；render_result.json 的 backend 字段是请求值，不是实际后端（verify 的 --render-log 从作业日志里认真实后端）；样片阶段连接超时回退本机要如实告诉用户。 〔第 23、31、32、35 课〕
- **[E58]** 成片核对：verify 量完（ffprobe、响度、静音对问答时间线、黑帧、静止、md5）并生成拼图后，人要逐张看完 renders/review_dense/sheet_*.png（每 4 秒一帧）和 renders/review_cues/sheet.png（问答时刻与结尾），再下“正常”的结论；结尾单独看最后几秒的帧确认最后一句写完；整课渲染后的 4 秒帧才看得出相邻文字贴在同一行；logo、字幕、字形都要看，问答时答案不早于 answer_not_before；看完写 validation/compose-notes.json，再跑 docs/whiteboard_finish_compose.py（报告全部来自实测）。 〔第 16、30、40 课〕
- **[E59]** freezedetect 在稀疏白板上会报近似静止，要对照帧确认只有小字写入，并如实写进核对。 〔第 33 课〕
- **[E60]** 已说“成片通过”后才发现缺陷：如实说明、修复、重渲、按 4 秒一帧加问答帧重新核对，发布前请用户重新审看并再说“发布通过”；要重渲已批准的成片先告知用户（第 40 课 K2、K6）。 〔第 16 课〕

**已是模板或工具的默认做法**（知道即可，别改掉）：
- **[E54]** 整课、样片、关键帧默认自动走远程渲染机（失败自动回退本机）；REMOTE_MIN_PART=30、STILLS_LOCAL_MAX=60 已内置，不用加参数；小任务（≤60 张静帧）走本机更快；慢的时候看 remote timing 里的 fetched 与 install 分开判断。 〔第 18 课；脚本：`docs/whiteboard_render.py`〕
- **[E55]** 分块渲染工具已处理 Remotion 超时与拼接内存：不要用 video_compose 默认的 600 秒超时；拼接时每个片段独立 -i（同一输入多次 trim 会缓存已解码帧、被系统杀掉）。 〔脚本：`docs/whiteboard_render.py`〕
- **[E56]** 本机对照渲染（K3、K6）：启动前先告诉用户那是对照、整课已走远程；然后 nohup .venv/bin/python docs/whiteboard_verify.py local-ref projects/<课程> > 日志 2>&1 &，用 python3 docs/whiteboard_wait.py 日志 等待——它自己备份远程分块、本机重渲、把两边时间戳统一成 N/30 再算 PSNR、还原备份并逐文件 md5 核对（阈值最低 45 dB），结果写进 validation/local-ref.json。 〔第 20、21、22、24、32、40、41 课；脚本：`docs/whiteboard_verify.py local-ref`〕
- **[E57]** 整课远程渲染一结束，立刻跑 .venv/bin/python docs/whiteboard_verify.py verify projects/<课程> --render-log <渲染作业的日志>——它第一步就把 renders/render.log 等备份到 renders/log_backup/（之后跑静帧会把它覆盖，分段计时就没了），再做全部机械核对。 —— 第 42 课的整课分段计时被后来的静帧覆盖，只剩总耗时；第 43 课做到了 〔第 42、43 课；脚本：`docs/whiteboard_verify.py verify`〕
