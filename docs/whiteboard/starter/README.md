# 起步模板（starter）

每课几乎不变的脚本的**版本化标准副本**。`projects/` 被 git 忽略，以前每课从上一课复制，名字和课号靠手工替换（第 41–43 课的 `render_stills.py` 就一直指着第 30 课的项目）。

- 用法：`docs/whiteboard_new_lesson.py --pid c-xxx-cn --n 44 --title "课名"`（用户说“计划确认”之后）。它建目录、拷这里的模板、替换 `__PID__` 与 `__N__`、再从上一课复制本课专属脚本并换名，最后扫描残留。
- 占位符写在字符串和注释里，模板本身仍是合法 Python（`python3 -m py_compile` 能过）。
- 这里只放不随课变的脚本；本课专属的（`plan_stage.py`、`build_script.py`、`build_scene_plan.py`、`_body_boards.py`、`_build_tail.py`、`sample_voice.py`、`finish_assets.py`、`publish_prep.py`、`make_exercises.py`、`run_*.sh`）每课照旧从上一课复制再改。
- 改了这里，只影响以后新建的课；已发布课的脚本不动。
- `_build_head.py` 的 `Board` 含新合成器的可选字段（未知字段透传、`move` 时间换算、路径形状不动笔、`camera`、`relist` 平移运动与镜头），并 import 新系列积木 `V2 = whiteboard_v2_kit`；回测 `t_board_v2` 以这份为准（试点项目里的副本是同一份代码）。`Board.code(…, lang="c" 或 "py")` 给代码上色；第二轮手段（题卡与圆环、对错分屏、计数条、时序图、角色微动）在 `docs/whiteboard_v2_kit.py`，用法见 `docs/whiteboard/style-guide-agent.zh-CN.md` 第 7 节；音效：build 之后跑 `docs/whiteboard_sfx.py apply projects/<课>`。
