# 阶段清单 · 合成与核对（compose）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**口令**：成片通过，进入发布阶段

**本阶段做什么**：
1. 先 `python3 tools/video/remote_cpu_render.py probe` 并看输出。
2. 用 `nohup .venv/bin/python projects/<课程>/scripts/render_final.py > 日志 2>&1 &` 渲整课；渲完先备份 `renders/render.log`。
3. 核对：ffprobe、ebur128、silencedetect d=1.3 对问答时间线、blackdetect、freezedetect、4 秒一帧拼图加问答帧；6 张静帧远程对本机；K3/K6 本机对照 PSNR。
4. 改 `finish_compose.py` 的数字后另起一条命令运行，写 compose 检查点；停下等“成片通过，进入发布阶段”。

**产出**：renders/final.mp4；render_report.json；final_review.json

**要人判断**（逐条过一遍）：
- **[E53]** 渲染前先 python3 tools/video/remote_cpu_render.py probe 并看输出（通道、free_bytes 是否低于 min_free_bytes）；通道断开先告诉用户再决定，没有渲染机就在核对里如实写明、不编对照；渲染机故障后先 probe 再用真实小作业复测，整课大作业成功才算恢复；提交后读日志报 job log unavailable 时客户端会自动回退本机（约 30 分钟），先停下重试一次远程；render_result.json 的 backend 字段是请求值，不是实际后端；样片阶段连接超时回退本机要如实告诉用户。 〔第 23、31、32、35 课；拟做成脚本：docs/whiteboard_verify.py 里先 probe（第二批 9）〕
- **[E56]** 本机对照渲染（K3、K6）：启动前先告诉用户那是对照、整课已走远程；先备份远程分块、成片与 render.log；用 nohup 放后台，等待用 until grep；比较 PSNR 前把两边时间戳统一成 N/30（setpts=N/30/TB），否则末尾会显示成 29–40 dB 的假象；对照后恢复备份并逐字节核对；本机对照跑得太快、没有输出确认行时，删掉输出目录重渲再比。 〔第 20、21、22、24、32、40、41 课；拟做成脚本：docs/whiteboard_verify.py 的本机对照子命令（第二批 9）〕
- **[E57]** 整课远程渲染一结束，先备份 renders/render.log 与输出日志（之后跑静帧会把它覆盖，分段计时就没了）。 —— 第 42 课的整课分段计时被后来的静帧覆盖，只剩总耗时；第 43 课做到了 〔第 42、43 课；拟做成脚本：docs/whiteboard_verify.py 先备份（第二批 9）〕
- **[E58]** 成片核对：按 4 秒一帧加问答时刻帧逐张看完全部拼图再下“正常”的结论；结尾单独取最后几秒的帧确认最后一句写完；整课渲染后的 4 秒帧才看得出相邻文字贴在同一行；logo、字幕、字形都要看，问答时答案不早于 answer_not_before。 〔第 16、30、40 课；拟做成脚本：docs/whiteboard_verify.py（第二批 9）〕
- **[E59]** freezedetect 在稀疏白板上会报近似静止，要对照帧确认只有小字写入，并如实写进核对。 〔第 33 课〕
- **[E60]** 已说“成片通过”后才发现缺陷：如实说明、修复、重渲、按 4 秒一帧加问答帧重新核对，发布前请用户重新审看并再说“发布通过”；要重渲已批准的成片先告知用户（第 40 课 K2、K6）。 〔第 16 课〕

**已是模板或工具的默认做法**（知道即可，别改掉）：
- **[E54]** 整课、样片、关键帧默认自动走远程渲染机（失败自动回退本机）；REMOTE_MIN_PART=30、STILLS_LOCAL_MAX=60 已内置，不用加参数；小任务（≤60 张静帧）走本机更快；慢的时候看 remote timing 里的 fetched 与 install 分开判断。 〔第 18 课；脚本：`docs/whiteboard_render.py`〕
- **[E55]** 分块渲染工具已处理 Remotion 超时与拼接内存：不要用 video_compose 默认的 600 秒超时；拼接时每个片段独立 -i（同一输入多次 trim 会缓存已解码帧、被系统杀掉）。 〔脚本：`docs/whiteboard_render.py`〕
