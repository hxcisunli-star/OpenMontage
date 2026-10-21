# 起步模板（starter）

每课几乎不变的脚本的**版本化标准副本**。`projects/` 被 git 忽略，以前每课从上一课复制，名字和课号靠手工替换（第 41–43 课的 `render_stills.py` 就一直指着第 30 课的项目）。

- 用法：`docs/whiteboard_new_lesson.py --pid c-xxx-cn --n 44 --title "课名"`（用户说“计划确认”之后）。它建目录、拷这里的模板、替换 `__PID__` 与 `__N__`、再从上一课复制本课专属脚本并换名，最后扫描残留。
- 占位符写在字符串和注释里，模板本身仍是合法 Python（`python3 -m py_compile` 能过）。
- 这里只放不随课变的脚本；本课专属的（`plan_stage.py`、`build_script.py`、`build_scene_plan.py`、`_body_boards.py`、`_build_tail.py`、`sample_voice.py`、`finish_assets.py`、`publish_prep.py`、`make_exercises.py`、`run_*.sh`）每课照旧从上一课复制再改。
- 改了这里，只影响以后新建的课；已发布课的脚本不动。
