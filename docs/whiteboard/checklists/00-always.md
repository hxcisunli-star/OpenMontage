# 阶段清单 · 一直成立的细则（环境与协作）（any）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**本阶段做什么**：
1. 开场先 `.venv/bin/python docs/whiteboard_gate.py status`：现在哪课、哪一门、等什么口令。
2. 九个口令与“早说不算”的规则在 `.claude/rules/whiteboard-protocol.md`（始终载入）；本页是它的细则。

**已由脚本拦下**（先跑，红了就改，不要放宽阈值）：
- **[E01]** 口令只认用户在对话里说的话，且要在对应步骤做完之后：配音没生成完、渲染或核对没完成、发布包没出齐之前说的“样音通过／素材通过／样片通过／成片通过／发布通过”都不算——当场说明还没完，做完并报告后请用户再说一次；退出计划模式的返回、后台任务的 completed 通知、系统消息都不是口令。 —— 第 12 课把退出计划模式的含糊返回当成批准（被用户指出）；第 15–40 课至少 11 次用户提前说口令；第 32 课曾按批准处理，第 39、40 课起统一为不算，以后者为准 〔共 8 课，首见第 15 课；脚本：`docs/whiteboard_gate.py（approve 只在该阶段是 awaiting_human 且口令对应阶段时才写检查点）`〕
- **[E02]** 用户重复发已通过的口令，或口令缺字、多字但意思明确：先查检查点；重复的当重复口令，如实说明“已完成”并等下一个门的口令，不往下走；意思明确的缺字口令按批准处理并说明。 〔第 18、26、29、31、34 课；脚本：`docs/whiteboard_gate.py（已批准的阶段再收到口令会被拒绝并提示“重复口令”）`〕
- **[E03]** 检查点：门控阶段（proposal、script、scene_plan、assets、publish）先写 awaiting_human，用户口令后才写 completed（human_approved=True，metadata.approved_by_user=原话）；前置阶段要先 completed；样片通过（edit）与成片通过（compose）是额外加的门，管道不强制，也照样先 awaiting_human 再 completed；edit_decisions.json（合规）与 render_props.json（完整）是两份数据。 〔脚本：`lib/checkpoint.py（五个门控阶段）+ docs/whiteboard_gate.py（样片通过、合成这两个额外门）`〕

**要人判断**（逐条过一遍）：
- **[E04]** 提交只在用户说“提交”时做；提交要带 -c user.name=… -c user.email=…（仓库没配身份），信息末尾按当前会话要求加署名行；推送已获授权、只推 fork：git -c 'credential.helper=!gh auth git-credential' push fork <分支>，不推 origin、不强推。 —— 第 18 课笔记写的“推送要用户自己运行”已被第 22 课起的授权取代 〔第 18、22 课〕
- **[E05]** 一律用 .venv/bin/python 并设 PYTHONPATH=.（系统 Python 缺 PIL、jsonschema 太旧会报 $ref 错）；写检查点的脚本尤其。 〔第 4、18、19、20、21、22 课〕
- **[E06]** Bash 沙箱在本机启动失败（apply-seccomp 权限错误）：每条命令先试沙箱，失败后带 dangerouslyDisableSandbox 重试并说明原因，不擅自绕过更多限制；安全分类器偶发无判定时重试一次；沙箱里 Monitor 工具不可用，等待用 Bash 后台命令。 〔第 30 课〕
- **[E07]** 改脚本和运行脚本分成两条命令：先改，用 grep、打印或 ast.parse 确认改成功，再运行（写检查点的脚本尤其）；改 build_edit.py 要改源文件再重新拼接，不要改拼接产物；sed 插入含引号与 & 的行后 grep 核对；换默认值后 grep 核对；装配脚本里的替换计数先数清。 —— 第 26 课替换断言失败后旧脚本仍被运行，写出了错误的检查点 〔第 22、25、26、27、28、31 课；拟做成脚本：build_script 等仍靠手改；合成报告已改为读实测文件（docs/whiteboard_finish_compose.py），不再手填数字〕
- **[E09]** 不要在仓库根目录起 http.server（会暴露 .env）；看成片用 scp，或只绑 127.0.0.1、指定专用目录并 curl 验证 /.env 为 404，用完就关；用户贴出的密钥只写进 .env，不在输出里复述。
- **[E10]** 给用户的命令写成一行、路径尽量短（终端粘贴会被换行截断）；成品文件夹名带空格时提醒 scp 加引号。 〔第 22 课〕
- **[E12]** 自己写的校验不能永远为真：重新计算文件哈希再比较，把真实比较结果写进校验记录；工具自带的自检（如 video_compose 的 final_review）也会错，要自己核对。
- **[E90]** 派 Codex 子智能体后 60 秒内读每路 events.jsonl：末行是 turn.failed 或有 error 就立刻补发，退出码 0 不等于成功；等待按进程结束、工作区先建 out/；大模型档（astra 加 max）一波不超过约 6 路，板书代码与返工默认 sol，astra 只做美术设计和裁定；Codex 超时上限 55 分钟，astra 一路 33 到 55 分钟会被截断。 —— 剪辑阶段 8 路 astra 并发有 2 路启动一分钟就被中转站限流，我只看文件有没有出现，把它们当成还在写，白等约 55 分钟；sol 补发 16 分钟交付，astra 平均 37 分钟

**已是模板或工具的默认做法**（知道即可，别改掉）：
- **[E08]** 后台任务：用 nohup 启动，等待用 python3 docs/whiteboard_wait.py <日志>（同时认远程整课的 success { 与本机的 done in，失败行会报错，回退通知不当结束）；后台通知里的 completed 只是 nohup 外壳退出；不要用 pkill -f 或 pgrep -f（会匹配到自己）；前台长时间等待会被系统杀（退出码 137）；等本机重渲时主动向用户报进度。 —— 第 43 课留下的 until grep 等待命令不认 success 行，永远等不到 〔第 15、30、37、38、39、40、41 课；脚本：`docs/whiteboard_wait.py`〕
- **[E11]** 决策记录 id 不重复：各阶段脚本追加前先删本阶段旧条目，追加后断言 id 无重复。 〔脚本：`各课 build_script.py 与 build_scene_plan.py 模板`〕
