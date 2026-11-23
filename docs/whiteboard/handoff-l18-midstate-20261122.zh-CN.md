# 第 18 课现状交接（做到工具阶段一半；2026-11-22 UTC）

用法：新会话先读 `docs/whiteboard/handoff-l18-20261121.zh-CN.md`（A 段是全自动开场话，含用户原话），**再读本文件**——本文件写的是上一个会话做到哪、留下了什么。用户定了第 18 课换到新会话做（一课一个会话的惯例），所以上一个会话在工具阶段中途停下。

## 1 不要重做的事
- 项目 `projects/agent-think-first-cn/` 已建（`project.json` 课名代定《叫它一步一步想，有用吗？》），**不要重建项目**。
- 托管 `D20261122T054255` 已开、终点“发布通过”，`allow-override` 已记（`approvals.jsonl` 前两行）。**不要重开托管**。
- 计划门（计划确认）已 `record-by-review`：评审裁决 `projects/agent-think-first-cn/review/gate-review-plan-1.json`（pass，0 blocking、15 条 minor，2026-11-22 06:39 UTC），记录在 `approvals.jsonl` 第三行。下一个门是“提案通过”，在正式实验与分析之后。
- **对外请求（中转服务）至今 0 次**，预算文件 `validation/real_runs/budget.json` 还没建；计数器从 0 开始（总上限 390：列模型 1、探测 12、试跑 24、正式 320、补发储备 R 30）。

## 2 计划与冻结材料
- 计划 v3：`/root/.claude/plans/l18-plan.md`（副本 `validation/research/plan_stage/l18-plan-v3.md`；v1、v2 也在那里）。红队两轮处置 `CHANGES_r1.md`、`CHANGES_r2.md`，原始返回 `redteam_r1/`、`redteam_r2/`（各带 MANIFEST）。
- 验证闸门：`validation/lesson_gate_s3_u03.md`（断言 G-S3-U03-01…07；04 两路盲审 ENTAILED 已封存 verified；02、03、05、06 大纲说得比原文宽，列待用户项；07 等正式实验的词元做证据）。盲审 `projects/roadmap-agent-engineer/review/claims/audit-blind-30.json`（本机 terra）、`audit-blind-31.json`（Antigravity hydrogen）。存档 A199–A201，下一个存档号 A202。
- **冻结判定规则** `validation/l18_decision_rule.md`，sha256 `1970f71c9e69f0f6fee21896a71b1456e4effeb64506dbc82e773f2a72f6ef25`＝计划第 0、6、9 节与附录 A 原文＋“计划门后增改”13 条（P1–P6、P9–P14）。**先前发给复审对话的 `8e77de0f…` 作废**（那一版漏了第 0、6、9 节）。开跑前副本 `validation/l18_decision_rule.as-written-before-first-call.md`。
- 受保护清单 `validation/protected_hashes.json`（4 个文件：判定规则、`prompts_l18_candidate.json` `365d874d…`、`research/plan_stage/candidates_l18.json` `a9f8e1eb…`、`code/money_scan_l18.py` `0e821534…`）。`plan_changes.md` 只追加，不在清单里。
- 仓库外副本 `/home/MyProject/_scratch/frozen-l18/`（同上 4 个文件＋WHY.md）。
- `code/l9_fixture.py`＝第 9 课原件逐字拷贝（`fixture_hash()`＝`728d106d…129e`，不许改）。

## 3 plan_changes P1–P14（`validation/plan_changes.md`）
| 号 | 是什么 | 状态 |
|---|---|---|
| P1 | 补回第 9 课“格式为主”分支：某格格式不合规 ≥ 有效槽一半 → 先报格式、再报去掉记号后的数；探测“抽得到”含去掉记号重判 | 冻结 |
| P2 | 预测题一改问选数题 Q-H（A 对 B）；题二仍是排队题 Q-M（C 对 D）；s1 回扣第 9 课不报分数 | 冻结 |
| P3 | 试跑资格加一条：4 份里有截断或空答卷就不合格 | 冻结 |
| P4 | A.7 四处写定；`reasoning_content` 进白名单，落盘前过脱敏与金额扫描 | 冻结 |
| P5 | A.3 照搬第 9 课第 0–6 条；样例改 `***答案：7***`；名字题不当单位 | 冻结 |
| P6 | 归类名统一“更多／分不出／更少” | 冻结 |
| P7 | 第 9 课两处“写了关闭还有草稿”（第一个模型日期题十次两次、第二个模型日期题十次七次）照原话写；N3 若入选，提案里注明关思考那边可能有开关异常 | 带到提案、脚本 |
| P8 | 带到后面阶段的 minor 清单（见第 5 节） | 带走 |
| P9 | 名字题另外人名：N1＝乙丙丁戊己，N5＝乙丙（Q-M 沿用第 9 课） | 冻结 |
| P10 | 金额扫描英文货币词加边界（数学草稿的 adjacent、percent 不再误拦）；核对：自检 19 拦 12 放、旧课 753 份 0 命中、第 9 课 379 份只剩 LaTeX 的 `$` 1 份、两万随机串只会更少拦 | **复审对话已同意用于真实请求** |
| P11 | 典型记录跳过原文因金额命中没落盘的槽 | 冻结 |
| P12 | “长输出槽”＝有一次尝试截断或超时；停机②连续 3 个长输出槽，停机③正式阶段截断＋超时尝试累计 16 | 冻结 |
| P13 | 格式为主时两边一起改用去掉记号后的比例 | 冻结 |
| P14 | 写 STOP 时另一条线在途请求照常记录、判分，之后不再发 | 冻结 |

## 4 工具阶段做到哪
- 接口：`code/INTERFACE_l18.md`（第 0 节列了与第 17 课录制器相反的 11 处，每处都要有“旧行为没了”的测试，E249）。
- 工作区生成器：`code/make_tools_ws_l18.py <t1|t2|t3|t1b|r1|r2|r3|f1|f2|f3>`；扫描 `code/scan_ws.py <工作区>`，**扫描不过不派**（建工作区、扫描、派活写成一条 && 命令）。工作区里中转服务的环境变量名换成 `RELAY_API_KEY_ENV`、`RELAY_BASE_URL_ENV`，凭据文件名 `credentials.env`；**交回的代码放进项目前要换回**（`MODELINK_API_KEY`、`MODELINK_BASE_URL`、`crosscheck.env`）。第 9 课 `test_l9_record.py`（含 127.0.0.10）、第 17 课 `test_analyze_l17.py`（含合成密钥形状）会被扫描拦下，已从工作区清单里拿掉。
- 任务书都在 `validation/research/tools_stage/tasks/`：`TASK_T1.md`（录制器）、`TASK_T2.md`（判分、选题、比较、分析）、`TASK_T3.md`（学生起步脚本 `think_steps.py` 与页内练习 `compare_counts.py`，要 `l18_judge.py` 先有）、`TASK_T1B.md`（整合、补测试、假服务整路演练、真套接字检查）、`TASK_R1–R3.md`＋`REVIEW_COMMON.md`（codexbox 独立复审）。F1–F3（按复审修）的任务书还没写。
- **T1、T2**：2026-11-22 派出（本机 Codex `gpt-6.1-sol`＋xhigh 各 1 次），都已交回、存档、放进 `code/`，见第 4.1 节。
- 还没做：T3、T1B、R1–R3、F1–F3；假服务整路演练（`rehearsal_l18.py`）；真套接字检查（`real_socket_check_l18.py`）。
- **第一次真实请求之前必须做完**（复审对话 2026-11-22 要求）：假服务整路演练（含一份英文草稿里有 adjacent 的回答——断言不被拦、正文落盘；一份带 `$5` 的——断言拦下、原文不落盘；以及 TASK_T1B 第 3 条列的各条停机支线），真套接字检查，计数器从 0 开始。**出现 STOP 先发消息给复审对话。**
- 之后按计划第 10 节：列模型 1 → 探测 12（决策）→ 试跑 24 → 选题（`select_pilot_l18.py`）→ 冻结新题与顺序表 → 正式 320 → 分析与典型记录 → 提案。

### 4.1 T1、T2 交回（2026-11-22 UTC）
- **T2**（判分、选题、比较、分析）：`l18_judge.py`、`select_pilot_l18.py`、`a5_reference_l18.py`、`a5_matrices_l18.out`（59 组合成矩阵）、`analyze_l18.py` 与 5 个测试文件、`NOTES_T2_l18.md`。它报 377 个测试全过；主持在工作区和项目里各重跑一次，都是 377 passed。存档 `validation/research/tools_stage/t2/`（17 个文件，MANIFEST 逐一核过哈希）。`select_pilot_l18.py` 里的占位环境变量名已换回。
- **T1**（录制器）：`l18_fixture.py`、`l18_record.py`、`make_send_list_l18.py`、`fake_think_server_l18.py` 与 4 个测试文件、`NOTES_T1_l18.md`。它报 245 过、1 跳（Codex 沙箱不能开套接字）；主持在工作区重跑 246 passed。存档 `validation/research/tools_stage/t1/`（15 个文件，哈希已核）。`l18_record.py`、`test_l18_record.py`、`NOTES_T1_l18.md` 里的占位名已换回（`MODELINK_API_KEY`、`MODELINK_BASE_URL`、`crosscheck.env`）。
- 两路的工作区里冻结文件（判定规则、纸条、候选题、受保护清单、`money_scan_l18.py`、`l9_fixture.py`）都与原件逐字节相同。
- **两路放在一起第一次跑（项目 `code/` 里，用真的 `l18_judge`）：622 passed、1 failed**。不过的是 `test_l18_record.py::GeneratedTests::test_only_four_judge_calls_and_raw_answer_grading`：真的 `strip_rejudge` 内部会再调一次 `judge_answer`，测试却断言 `judge_answer` 只被调用一次（T1 写测试时用的是替身）。这是对接问题，留给 T1B 第 1 条处理（改测试的计数口径，或让录制器只经一个入口判分），录制器的判分结果本身没错。
- 两份 NOTES 里写定、要新会话复核的几处：
  - T2：两个模型里有一个“比不了”时，预测题揭晓说“这一次比不了”，优先于“两个模型不一样”（A.6 两句的先后没写，T2 这样定）。
  - T2：`has_process` 按接口用“答案行之前有非空行”，不沿用第 9 课的“非空行多于 1”。
  - T2：`analyze_l18.py` 默认不读原始目录，要显式传 `raw_dir`。
  - T1：凭据“环境变量优先，环境没设才读 0600 的 `crosscheck.env`”，照第 17 课；判定规则 6.9 只写了环境变量。
  - T1：`selected_l18.json` 接受 `{"selected":[…]}` 等三种写法；T2 写的是 `{"selected":[…], "ranking":…}`，对得上。
  - T1：进程在“预占成功、记录未写”之间崩溃时，保守保留计数并写 STOP，不自动重发。
- 下一步：用 `make_tools_ws_l18.py t1b` 派整合（TASK_T1B 已写好，含复审对话要求的 adjacent 不拦、`$5` 必拦两条），同时派 T3（要 `l18_judge.py`，已在）；整合过了再派 R1–R3（codexbox）复审、写 F1–F3 任务书修。

## 5 计划门 minor 带到后面阶段的（P8 及复审对话的清单）
- **工具阶段（3 条）**：E228 逐文件原子写；E240 写前比对受保护清单；E249 从第 9、17 课拷来的专用测试删掉或改掉。
- **提案阶段（4 条，另加 P7 的 N3 风险说明）**：Q02 换成整句（含 sufficiently large）；“九条”改“十条”；WHERETO 补 T（例如“预测题四个选项、练习分两档”）；`lesson_gate_s3_u03.md` 第 12 行“0 错 0 警”改成“0 错 1 警（随后补了原子，复跑 0 错 0 警）”。
- **脚本阶段（4 条，另加 P7 的两处原话）**：“要能检查的过程”标成我们的讲法（文档只写了思考关着时的退路）；第 9 课禁语“推理模型就是思考模式”并进禁语检查；s2“输出词元多了多少”改“变了多少”；旁白保留“一般来说”。
- **发布阶段（2 条）**：课名是主持代定、390 次总上限是复审对话代定，写进验收汇报“等你定的事”；验证闸门的大纲待用户项（02、03、05、06 说宽了；05、06 没带 [S-n]）也写进去。
- 复盘 `agent-18` 要记一条：第 17 课发布后小修时给 Codex 的任务书写了“不运行任何程序”（E209 又犯一次），Codex 读不了文件，改任务书后重跑才过。登记表下一个号 E274。

## 6 项目里其他现状
- `scripts/` 是从第 17 课整套拷来的，**都没改、没运行**；`build_script.py`、`build_scene_plan.py`、`plan_stage.py`、`make_exercises.py`、`run_exercises.sh`、`publish_prep.py`、`sample_voice.py` 里还有第 17 课的专用内容，到对应阶段再改。
- `code/` 里本课已有：`archive_text_l18.py`、`candidates_l18.py`（6 道候选题的穷举验算）、`make_prompts_l18.py`（生成冻结纸条，**不要再运行**，会覆盖受保护文件）、`scan_ws.py`、`l9_fixture.py`、`money_scan_l18.py`、`INTERFACE_l18.md`、`make_tools_ws_l18.py`。
- 平台（电子书 build_site／check_site）第 18 课没碰；以后有平台改动单独登记，不与第 18 课混在一起（复审对话要求）。

## 7 `_scratch/` 里属于第 18 课的目录
| 目录 | 是什么 | 能不能删 |
|---|---|---|
| `frozen-l18/` | 冻结材料的仓库外副本（计划 A.0 要求），带 WHY.md | **留到第 18 课发布后**，核对哈希再删 |
| `codex-ws-l18-tool-t1/`、`codex-ws-l18-tool-t2/` | T1、T2 的工作区 | 已存档到 `validation/research/tools_stage/t1/`、`t2/` 并核对哈希，**已删** |

此外第 18 课在 `_scratch/` 里没有别的目录；盲审工作区 `lessongate-l18-*`、红队工作区 `redteam-l18-*` 都已存档后删掉。
