# 阶段清单 · 场景计划（scene）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**口令**：场景计划通过

**本阶段做什么**：
1. 复制 `build_scene_plan.py`，改各块版面与事件；每个事件带 `anchor_phrase`，事件按旁白先后顺序写，找不到锚点就停下改计划，不放宽查找。
2. 改静默表与 `MIN_AFTER`（按本课问答所在段）。
3. 运行（会把 script 检查点标为 completed），写 scene_plan 检查点 awaiting_human，停下等“场景计划通过”；用户说了之后：`docs/whiteboard_gate.py approve <项目> scene_plan "<用户原话>"`。

**产出**：scene_plan.json；scene-plan-review.html

**要人判断**（逐条过一遍）：
- **[E34]** 每个画面事件带旁白锚点，事件按旁白先后顺序写，后续锚点必须在主锚点之后；锚点被前一个锚点消耗后用 A(S, …) 单独重找；逐张演示先打印各锚点的实际时间，按它们逐步定时，不要按整段平均分配。 〔第 25、28 课〕
- **[E35]** build_scene_plan.py 的静默表与 MIN_AFTER 按本课问答所在段改（问答在哪几段就是哪几段，不总是 s3 与 s8）；样音也不一定在 s2。 〔第 41、43 课；拟做成脚本：从 script.json 的 quiz_pauses 自动生成（可选）〕
- **[E36]** 只出现一段时间的画面（结果行、中间态、问号、框）都要写擦除时间 until，指向它的箭头也设同样的 until；框和单元格自己带 until，不要拿底色矩形去盖；“先填问号再写字母”的小格用 until 去掉问号。 〔第 32、34 课〕
