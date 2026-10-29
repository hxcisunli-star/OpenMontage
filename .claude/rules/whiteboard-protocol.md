# 白板课协议（始终生效）

适用：做“老师边讲边画”白板课——C 篇，以及 2026-10-21 起与 C 课没有任何联系的新系列（animated-explainer 管道、explainer-teacher 模板、Remotion）。开始任何白板课工作，先读 `.claude/skills/whiteboard-lesson/SKILL.md`，再读当前阶段的清单 `docs/whiteboard/checklists/`。

1. **九个口令**由用户自己在对话里说，且在对应步骤做完之后才算：计划确认 → 提案通过 → 脚本通过 → 场景计划通过 → 样音通过 → 素材通过 → 样片通过，开始合成 → 成片通过，进入发布阶段 → 发布通过。没收到口令不进入下一阶段。
2. **早说不算**：配音没生成完、渲染或核对没完成、发布包没出齐时说的口令不算——当场说明还没完，做完并报告后请用户再说一次。退出计划模式的返回、后台任务的 completed 通知、系统消息都不是口令。重复发已通过的口令：先查检查点，当重复口令并说明，不往下走。
3. **检查点**：门控阶段先写 awaiting_human，用户口令后才写 completed（human_approved=True，metadata.approved_by_user=原话），然后停下，不做下一阶段。用户说了口令后用 `.venv/bin/python docs/whiteboard_gate.py approve <项目> <阶段> "<原话>"` 记录（它只在该阶段是 awaiting_human、口令对得上阶段、前面阶段已完成时才写；样音通过、计划确认用 `record`）；开场先跑 `… whiteboard_gate.py status` 看现在到哪一步。
4. **提交**只在用户说“提交”时做；提交后自动推到 fork（`git -c 'credential.helper=!gh auth git-credential' push fork <分支>`），不推 origin、不强推；推送前扫密钥与外部 IP，`.remotion/`、含渲染机地址的文件、证据压缩包不提交；提交要带 `-c user.name=… -c user.email=…`，署名行按当前会话要求；同时在 `projects/` 里提交本课文本源的快照（本机库，不推送）。端口与地址不写进仓库文档。
5. **回复**：全程中文、精简，只讲“需要你决定什么”；不编耗时与费用；没做的检查要明说；发现自己的错（含已批准之后的）要主动说并修。
6. **环境**：只用 `.venv/bin/python` 并设 `PYTHONPATH=.`；Bash 沙箱在本机会失败（apply-seccomp），每条命令先试沙箱，失败后带 dangerouslyDisableSandbox 重试并说明原因；后台任务用 nohup，等待用 `python3 docs/whiteboard_wait.py <日志>`（认远程整课的 success 与本机的 done in），不用 pkill -f；不要在仓库根目录起 http.server。
7. **改脚本和运行脚本分成两条命令**：先改，用 grep 或 ast.parse 确认，再运行；写检查点的脚本尤其。
8. **不静默改已批准的内容**：计划、提案、已批准的脚本有错，先告诉用户并给三个选项（全部改／只改已确认的／保留）。
9. 例子里的输出、diff、编译提醒都来自本机真实运行；不运行未定义行为；旁白无英文字母与阿拉伯数字。细则见 `docs/whiteboard/checklists/00-always.md` 与各阶段清单。
10. **新系列**（项目名 `agent-…-cn`）与 C 课无关：教师是新老师加 AI 小搭档，不用医生与 C 课比喻，旁白不回扣 C 课（旁白检查会拦）；系列名由用户定，没定时封面与成品包不用占位；测得的排版检查里角色遮挡（under-character）的警告一律看全尺寸帧再下结论。细则：`docs/whiteboard/series.yaml`、`docs/whiteboard/style-guide-agent.zh-CN.md`、登记表 E76–E97。
