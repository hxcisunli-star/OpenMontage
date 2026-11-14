# 写一个页内练习

在章源 `sections[].blocks[]` 中加入 `t: "lab"`。必填 `id`、`title`、`goal`、非空 `starter`、非空 `tests`；练习 id 全站唯一，只用小写字母、数字和单个连字符。每项检查恰有 `id`、`name`、`code`，检查 id 在本练习内唯一。未知字段或类型错误会让构建失败。

选填：`prelude: ""`、`hints: []`、`solution: ""`、`timeout: 10`（整数 1–10 秒）、`seed: null`（或整数）、`optional: true`（显示“选做，视频里没有”）。标题、目标、代码和提示都是字符串；`hints` 是字符串数组。块的完整示例见 `projects/agent-what-is-llm-cn/code/lab_section.json`。

检查代码在学生代码成功运行后逐项执行，可用 `USER_CODE`（源码）、`STDOUT`（已截断的输出）、`NS`（学生命名空间）、`RUN_WITH_SEED(seed)`（新环境里先跑 prelude，再设置种子、运行学生代码并返回输出）。每项检查有独立字典。推荐检查行为，别限定变量名、空格或某一种写法。例如：

```python
assert len(STDOUT.splitlines()) == 3, "请让循环重复三次，每次只 print 一行。"
```

消息应说清楚哪一步没做到，并给下一步方向。断言失败的消息会直接显示；其他异常显示“检查代码出错：类型: 消息”，这通常需要作者修检查。随机练习要用种子检查可复现性和变化，避免要求每次运行都必须不同。

需要假模型时，把函数放在 `prelude`，不要要求学生访问服务。例如 `prelude` 的源码可以是：

```python
def fake_model(question):
    return "这是我们手写的玩具回答：" + question
```

学生起始代码写 `print(fake_model("你好"))`；检查可写 `assert "玩具回答" in STDOUT, "请调用 fake_model 并输出返回值。"`。每次运行都是新命名空间，prelude 输出会丢弃；写清楚这是玩具模拟，不代表模型内部的真实做法。

本地预览：先准备依赖（`python docs/whiteboard/ebook/fetch_vendor.py`），再运行 `python docs/whiteboard/ebook/build_site.py`，用 `node docs/whiteboard/ebook/serve.mjs` 启动预览服务并打开对应章页。点“开始练习”才加载编辑器和 Python；直接双击文件不能运行，窗口宽度至少 600 像素。第 1 章需先运行 `python projects/agent-what-is-llm-cn/code/assemble_chapter.py` 合入样板小节。

用 `python docs/whiteboard/ebook/set_labs.py --paste block` 禁止粘贴，`--paste allow` 允许，不带 `--paste` 查看站点当前状态；`--no-yaml` 只改当前站点，下次构建以 YAML 为准。先构建含练习的站点再用开关脚本。不要使用 `input()`、外部网络或第三方 Python 库；输出最多各 200 行或 16384 字符。提示逐条给，参考写法留给学生试过之后看；不要加入未经核对的新事实或数字来源。
