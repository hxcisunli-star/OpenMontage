# 页内代码练习（lab）接口合同

一个章页里的“练习”：Monaco 编辑器（VS Code 的编辑器内核）＋浏览器里的 Python（Pyodide，Python 3.12，放在 Web Worker 里）。**服务器不运行学习者的代码。** 本文件是冻结的合同：各部分（构建、样式、前端控制器、运行线程、防线、服务器、检查脚本）分头开发，只按本文件对接，互不修改对方的文件。合同有歧义或有错，不要自行偏离：写进 `out/QUESTIONS.md`，写明你采用的解释。

## 0. 文件归属（每个文件只有一个负责人）
| 文件（仓库相对路径） | 负责 |
|---|---|
| `docs/whiteboard/ebook/fetch_vendor.py`、`docs/whiteboard/ebook/serve.mjs`、`tests/tools/test_ebook_server.py`、`tests/tools/test_fetch_vendor.py`、`projects/_ebook/vendor/**` | T1 |
| `docs/whiteboard/ebook/labs.py`（新）、`docs/whiteboard/ebook/blocks.py`、`docs/whiteboard/ebook/build_site.py`、`docs/whiteboard/ebook/book.css`（只在末尾追加练习样式）、`docs/whiteboard/ebook/set_labs.py`（新）、`docs/whiteboard/ebook/LAB-AUTHORING.md`（新）、`projects/agent-what-is-llm-cn/code/assemble_chapter.py`、`projects/agent-what-is-llm-cn/code/lab_section.json`（新）、`tests/tools/test_lab_build.py`、`tests/tools/test_set_labs.py` | T2 |
| `docs/whiteboard/ebook/lab-runner.py`、`docs/whiteboard/ebook/lab-worker.js`、`docs/whiteboard/ebook/lab-guard.js`、`tests/labs/test_lab_runner.py`、`tests/labs/test_lab_guard.mjs` | T3 |
| `docs/whiteboard/ebook/lab-core.js`、`docs/whiteboard/ebook/lab.js`、`tests/labs/test_lab_core.mjs` | T4 |
| `projects/_ebook/site_check/out/check_site.py`、`projects/_ebook/site_check/out/test_check_site.py`、`projects/_ebook/site_check/mutate_real.py` | T5 |

## 1. 章节源里的练习块（T2 校验并渲染）
放在 `sections[].blocks[]` 里，块类型字段叫 `t`（和现有块一致）：
```json
{"t": "lab", "id": "s2-u01-draw", "title": "用代码抽一次签", "goal": "一句话说明练什么",
 "starter": "起始代码（Python 源码字符串）", "prelude": "", "tests": [{"id": "three-lines", "name": "输出 3 行", "code": "assert ..."}],
 "hints": ["提示一", "提示二"], "solution": "", "timeout": 10, "seed": null, "optional": true}
```
- 必填：`id`（全站唯一，正则 `^[a-z0-9]+(-[a-z0-9]+)*$`）、`title`、`goal`、`starter`（非空）、`tests`（至少 1 项，每项 `id`（同一练习内唯一，同 id 正则）、`name`（给学生看的检查名）、`code`（Python 断言代码）。
- 选填及默认：`prelude` `""`（在学生代码之前、同一个全新命名空间里先执行的 Python；它的输出被丢弃；用来放“假模型”函数之类）；`hints` `[]`；`solution` `""`；`timeout` `10`（整数 1–10，秒）；`seed` `null`（整数或 null，运行学生代码前 `random.seed(seed)`）；`optional` `true`（显示“选做，视频里没有”标签）。
- **未知字段、缺必填字段、类型不对、id 重复，构建时都抛 `ValueError("lab <id>: <原因>")`。**
- 检查代码（`tests[].code`）在学生运行后的环境里执行，可用名字：`USER_CODE`（学生代码字符串）、`STDOUT`（学生代码的标准输出，字符串，已按上限截断）、`NS`（学生代码跑完后的命名空间 dict）、`RUN_WITH_SEED(seed)`（在**全新**命名空间里先跑 `prelude`、再 `random.seed(seed)`、再跑学生代码，返回这次的标准输出字符串；学生代码报错则抛出同样的异常）。`AssertionError` 的消息就是显示给学生的失败原因；其他异常显示为“检查代码出错：<类型>: <消息>”。

## 2. 页面 DOM（T2 生成，T4 绑定，T5 检查）
每个练习渲染成下面的结构（`{id}` 是练习 id，`{root}` 是该页到 `assets/` 的相对路径，章页是 `../../assets/`）。**文本一律转义**；`<script type="application/json">` 里的 `</` 必须写成 `<\/`。
```html
<section class="lab" id="lab-{id}" data-lab-id="{id}" data-lab-state="idle" data-paste-guard="allow" data-assets-root="{root}">
  <header class="lab-head"><span class="lab-tag">选做，视频里没有</span><h3 class="lab-title">{title}</h3><span class="lab-done" id="lab-{id}-done" hidden>已完成 ✓</span></header>
  <p class="lab-goal">{goal}</p>
  <script type="application/json" class="lab-spec">{规范化后的块 JSON，不含 solution 以外的任何东西都要有；见下}</script>
  <div class="lab-preview" id="lab-{id}-preview"><pre class="lab-starter"><code>{starter}</code></pre>
    <div class="lab-actions"><button type="button" class="lab-btn lab-btn-main" id="lab-{id}-start" data-action="start">开始练习</button></div></div>
  <p class="lab-note" id="lab-{id}-note" hidden></p>
  <div class="lab-work" id="lab-{id}-work" hidden>
    <div class="lab-bar">
      <button type="button" class="lab-btn lab-btn-main" id="lab-{id}-run" data-action="run" title="Ctrl+Enter">运行</button>
      <button type="button" class="lab-btn" id="lab-{id}-check" data-action="check">运行并检查</button>
      <button type="button" class="lab-btn" id="lab-{id}-stop" data-action="stop" hidden>停止</button>
      <button type="button" class="lab-btn" id="lab-{id}-reset" data-action="reset">重置</button>
      <button type="button" class="lab-btn" id="lab-{id}-hint" data-action="hint" hidden>提示</button>
      <span class="lab-status" id="lab-{id}-status" role="status" aria-live="polite"></span>
    </div>
    <div class="lab-editor" id="lab-{id}-editor" data-editor-for="{id}"></div>
    <div class="lab-toast" id="lab-{id}-toast" role="status" hidden></div>
    <div class="lab-hints" id="lab-{id}-hints"></div>
    <pre class="lab-out" id="lab-{id}-stdout" aria-label="输出"></pre>
    <pre class="lab-err" id="lab-{id}-error" hidden></pre>
    <ul class="lab-checks" id="lab-{id}-checks"></ul>
    <div class="lab-solution-wrap"><button type="button" class="lab-btn" id="lab-{id}-solution-btn" data-action="solution" hidden>参考写法</button>
      <div class="lab-solution" id="lab-{id}-solution" hidden><pre><code></code></pre></div></div>
  </div>
</section>
```
- `.lab-spec` 里放：`{"id","title","goal","starter","prelude","tests":[{"id","name","code"}],"hints","solution","timeout","seed","optional"}`（全部字段，补齐默认值）。
- `data-lab-state` 取值：`idle`（还没点开始）｜`loading`｜`ready`｜`running`｜`offline`（`file:` 协议，不能运行）｜`narrow`（窗口宽度小于 600 像素）｜`error`（加载失败，可重试）。T4 负责改它；T2 只写初始值 `idle`。
- `data-paste-guard` 取值 `allow`｜`block`，由 T4 按配置文件改；T2 写初始值 `allow`。
- 含练习的章页在 `</body>` 前依次加载（都带 `defer`，路径用 `{root}`）：`lab-guard.js`、`lab-core.js`、`lab.js`；**不含练习的页面不得加载它们**。页面里不放 Monaco 和 Pyodide 的任何引用（由 `lab.js` 点“开始练习”后按需加载）。
- 检查清单项（T4 生成）：`<li data-check-id="{id}" data-passed="true|false"><span class="lab-check-mark">✓|✗</span> {name}<span class="lab-check-msg">：{message}</span></li>`（`message` 为空时不写冒号和该 span）。

## 3. 粘贴开关与配置文件
- `books.yaml` 顶层 `labs: {block_paste: false}`（默认 `false` = 允许粘贴）。`build_site.py`（T2）写出 `assets/lab-config.json`，内容恰为 `{"block_paste": false}`（JSON，一个布尔字段；运行时忽略未知字段）。
- `python docs/whiteboard/ebook/set_labs.py --paste block|allow [--site-dir DIR] [--yaml FILE] [--no-yaml]`（T2）：默认站点目录 `projects/_ebook/site`，默认 yaml `projects/_ebook/books.yaml`；先校验，再用“临时文件＋`os.replace`”原子地同时改 yaml 和 `<site-dir>/assets/lab-config.json`；打印当前状态（`粘贴：允许` 或 `粘贴：禁止`）；yaml 里没有 `labs` 段就加上，不破坏其他内容和注释。不带 `--paste` 只打印当前状态。
- 服务器对 `/assets/lab-config.json` 固定加 `Cache-Control: no-store`（T1）。`lab.js` 每次点“开始练习”时 `fetch(..., {cache: "no-store"})` 读它；**读不到、解析失败或不是布尔值一律按“允许”处理**。

## 4. 依赖（T1）
- 源目录 `projects/_ebook/vendor/`（不进外层仓库），`build_site.py` 原样复制到站点 `assets/vendor/`。固定结构：
```
assets/vendor/MANIFEST.sha256        每行 "<sha256十六进制>  <相对 vendor/ 的 posix 路径>"，按路径字典序；不含自身和 VERSIONS.json
assets/vendor/VERSIONS.json          {"monaco-editor": {"version": "...", "integrity": "sha512-..."}, "pyodide": {"version": "...", "integrity": "sha512-..."}}
assets/vendor/monaco/LICENSE         MIT
assets/vendor/monaco/vs/loader.js
assets/vendor/monaco/vs/editor/editor.main.js  editor.main.css  editor.main.nls.js
assets/vendor/monaco/vs/base/worker/workerMain.js
assets/vendor/monaco/vs/base/browser/ui/codicons/codicon/codicon.ttf
assets/vendor/monaco/vs/basic-languages/python/python.js   （其他语言可裁掉；以实际能加载 Python 高亮为准）
assets/vendor/pyodide/LICENSE        MPL-2.0
assets/vendor/pyodide/pyodide.js  pyodide.asm.js  pyodide.asm.wasm  python_stdlib.zip  pyodide-lock.json
```
  Monaco 取 npm 包 `monaco-editor` 的 `min/vs`（AMD 构建），Pyodide 取 npm 包 `pyodide`（0.27 系列，Python 3.12）。两者都用 npm 注册表元数据里的 `dist.integrity`（sha512）校验。裁剪后总大小控制在约 25 MB 以内。
- `python docs/whiteboard/ebook/fetch_vendor.py [--out projects/_ebook/vendor] [--force]`：下载→校验→在新的空临时目录里安全解包（拒绝绝对路径和 `..`）→按清单复制→写 `MANIFEST.sha256`、`VERSIONS.json`、许可证→最后重新校验。**不要用 `npm install`（会跑安装脚本）**，用注册表元数据加直接下载 tarball。

## 5. 运行线程与 Python 运行器（T3）
- `lab-worker.js`：经典 Worker（不是 module），由 `lab.js` 以 `new Worker(<assets>/lab-worker.js)` 创建。收到 `init` 后 `importScripts` 加载 Pyodide、`loadPyodide({indexURL})`，再 `fetch` 取 `runnerURL`（即 `lab-runner.py`）并 `runPython` 载入；之后每条 `run` 消息调用运行器。**学生代码和检查代码都在 Pyodide 里跑，绝不 `eval`/`new Function` 任何学生输入。**
- 消息（`reqId` 字符串，主线程生成，回复原样带回；旧的或未知的 `reqId` 由主线程丢弃）：
  - 主→Worker：`{"type":"init","reqId":"…","indexURL":"<pyodide 目录的绝对 URL，以 / 结尾>","runnerURL":"<lab-runner.py 的绝对 URL>"}`；`{"type":"run","reqId":"…","mode":"run"|"check","code":"…","prelude":"…","tests":[{"id","name","code"}],"seed":null|整数}`。
  - Worker→主：`{"type":"init-ok","reqId":"…","pythonVersion":"3.12.x"}`；`{"type":"init-error","reqId":"…","message":"…"}`；`{"type":"run-result","reqId":"…","ok":true|false,"stdout":"…","stderr":"…","truncated":true|false,"durationMs":数字,"error":null|{"type":"SyntaxError","message":"…","lineno":整数或null,"colno":整数或null,"hintZh":"…","traceback":"…"},"checks":[{"id","name","passed":true|false,"message":"…"}]}`。
  - 超时和“停止”：主线程 `worker.terminate()`，下次运行时重建 Worker（Worker 本身不处理）。
- `lab-runner.py`（纯 Python 3.12，**只用标准库，必须能在本机 CPython 3.12 下直接 import 并测试**，不依赖 `js`/`pyodide` 模块）。对外函数 `run_request(mode, code, prelude, tests, seed) -> dict`，返回的 dict 就是上面 `run-result` 里除 `type`、`reqId` 以外的字段。语义：
  1. 每次调用都用**全新**命名空间 `{"__name__": "__main__"}`；先 `compile(code, "<练习>", "exec")`，`SyntaxError`/`IndentationError` 直接返回 `error`（`lineno`、`colno` 取自异常，1 起算）并**不执行**。
  2. 先在命名空间里执行 `prelude`（输出丢弃，出错按内部错误返回 `error.type="PreludeError"`）；`seed` 不为 null 时 `random.seed(seed)`；然后执行学生代码，标准输出和标准错误分别捕获。`input()` 被替换成抛 `RuntimeError("页内练习不支持 input() 输入：请直接把值写进变量")` 的函数。
  3. 输出上限：标准输出和标准错误**各**最多保留 200 行或 16384 个字符（先到为准），超出部分丢弃，`truncated=true`，并在保留文本末尾加一行 `……输出太长，已截断`。
  4. 学生代码运行时异常：只保留文件名为 `<练习>` 的栈帧，`error.lineno` 取最内层学生代码行号；`traceback` 是过滤后的 Python 风格文本（不含 Pyodide/运行器内部帧）。
  5. `hintZh`（中文提示，一两句，不超过 60 个字）至少覆盖：全角标点（如 `（）：，“”`，指出第几行第几列、改成哪个半角字符）、`IndentationError`/`unexpected indent`/`expected an indented block`、`NameError`（名字没定义，检查拼写或是否先赋值）、`TypeError`、`ZeroDivisionError`、`IndexError`、`KeyError`、`ValueError`、`ModuleNotFoundError`（“这个练习只能用 Python 自带的库”）、`AttributeError`、`RecursionError`、`SyntaxError: '(' was never closed` 一类括号不配对、`input()` 的上面那条错误。其余给一句通用提示。
  6. `mode == "check"`：学生代码无错时，逐个执行 `tests[].code`（`exec` 在一个包含 `USER_CODE/STDOUT/NS/RUN_WITH_SEED` 的新字典里），收集 `checks`；`AssertionError` → `passed=false`、`message=str(e)`；其他异常 → `passed=false`、`message="检查代码出错：类型: 消息"`。学生代码有错时不跑检查，`checks=[]`。`ok` 在“`mode=="run"` 且学生代码无错”或“`mode=="check"` 且全部检查通过”时为 `true`。`mode=="run"` 时 `checks=[]`。
  7. 学生代码里的 `time.sleep`、死循环由主线程超时处理，运行器不做超时；`sys.setrecursionlimit` 保持默认。

## 6. 粘贴防线（T3，`lab-guard.js`）
UMD：浏览器里挂 `globalThis.LabGuard`，Node 里 `module.exports`（要能 `createRequire` 加载做 `node --test`）。无外部依赖。导出：
- `isPasteKey(e)`：`e` 是 `{type, key, code, ctrlKey, metaKey, shiftKey, altKey, isComposing}`。Ctrl/Cmd+V、Ctrl/Cmd+Shift+V、Shift+Insert → `true`；组词期间（`isComposing`）、AltGr 组合、没有修饰键的 `v`、Ctrl+C/X → `false`。
- `isPasteInputType(inputType)`：`insertFromPaste`、`insertFromPasteAsQuotation`、`insertFromDrop` → `true`，其余（含 `insertCompositionText`、`insertText`、`historyUndo`、`historyRedo`）→ `false`。
- `install(root, opts) -> {dispose()}`：`opts = {isBlocked: () => boolean, editor: Monaco 编辑器实例或 null, onBlocked: (kind) => void}`。**`isBlocked()` 在安装时为 `false` 就什么监听器都不装**（`dispose` 仍可调用）。为 `true` 时：在 `root` 上用捕获阶段监听 `paste`、`drop`、`dragover`（阻止默认）、`keydown`（`isPasteKey`）、`beforeinput`（`isPasteInputType`）、编辑器区域的 `contextmenu`；命中就 `preventDefault()`+`stopPropagation()`，并 `onBlocked("paste"|"drop"|"key"|"input"|"contextmenu")`。`.lab-starter`、`.lab-hints`、`.lab-solution` 里的 `copy`/`cut`/`dragstart` 也拦；编辑器里和输出区的复制、剪切不拦。`opts.editor` 给了就再挂 `editor.onDidPaste(() => { editor.trigger("lab-guard", "undo", null); onBlocked("paste"); })` 作兜底。中文输入法组词期间（`compositionstart`…`compositionend`）不拦任何东西。
- 纯函数、无副作用，便于 Node 单测（测试用最小的假 DOM 事件对象）。

## 7. 前端控制器（T4，`lab-core.js` ＋ `lab.js`）
- `lab-core.js`（UMD，`globalThis.LabCore`，纯函数，Node 可测）：`hashString(s)`（FNV-1a 32 位，8 位十六进制）、`draftKey(id)` = `"ebook.lab.v1." + id`、`readDraft(raw, starterHash)`（`raw` 是 localStorage 字符串，返回 `{code, passed}` 或 `null`；哈希不符返回 `null`）、`serializeDraft({starterHash, code, passed, updatedAt})`、`normalizeConfig(obj)`（返回 `{block_paste: boolean}`，任何异常输入都返回 `{block_paste:false}`）、`classifyEnv({protocol, innerWidth, hasWorker, hasWasm})`（返回 `"ok"|"offline"|"narrow"|"unsupported"`；`file:` → `offline`；宽度小于 600 → `narrow`）、`truncateForDisplay` 之类 T4 自定的辅助。
- `lab.js`：页面加载后为每个 `section.lab` 初始化；按 §2 的状态值改 `data-lab-state`；点“开始练习”才加载 Monaco 和 Python；**页面级单例运行环境**（同页多个练习共用一个 Worker，运行请求串行排队；点之前零网络请求）。
  - 加载：状态文字依次 `正在加载编辑器 (1/2)…`、`正在启动 Python (2/2)…`；失败 → `data-lab-state="error"`，`.lab-note` 显示 `加载失败：<原因>`，“开始练习”变成“重试”，起始代码预览仍显示。窄屏 → `.lab-note`：`屏幕太窄，请在电脑上或把窗口拉宽后练习`；`file:` → `离线打开不能运行代码，请用在线地址练习`；两种情况都不加载任何东西，预览保留，开始按钮隐藏。
  - Monaco：AMD 加载 `<assets>/vendor/monaco/vs/loader.js`，`require.config({paths:{vs:…}})`，`window.MonacoEnvironment = {getWorkerUrl: () => <assets>/vendor/monaco/vs/base/worker/workerMain.js 的绝对 URL}`（**不用 `blob:`**），同时加载 `editor.main.css`。**先把 `.lab-work` 的 `hidden` 去掉，再 `monaco.editor.create`**。选项：`language:"python"`、`fontSize:15`、`tabSize:4`、`insertSpaces:true`、`minimap:{enabled:false}`、`automaticLayout:true`、`scrollBeyondLastLine:false`、`ariaLabel:"Python 代码编辑器"`；配置要求拦截时再加 `contextmenu:false`、`dragAndDrop:false`、`dropIntoEditor:{enabled:false}`。主题跟随站点：`<html data-theme="dark">` 或（没设置且系统偏好深色）用 `vs-dark`，否则 `vs`；用 `MutationObserver` 监听 `data-theme` 实时切换。`Ctrl/Cmd+Enter` 绑定为“运行”。
  - 配置：点“开始练习”时 `fetch(<assets>/lab-config.json, {cache:"no-store"})` → `LabCore.normalizeConfig`；据此设置 `data-paste-guard` 并（要拦时）调用 `LabGuard.install(workEl, {isBlocked, editor, onBlocked: showToast})`。重新点开会重新读。`showToast` 在 `.lab-toast` 显示 `这里需要手敲输入` 约 2 秒后隐藏。**允许状态下不调用 `install`，不改任何 Monaco 选项。**
  - 运行：`运行`（`mode:"run"`）和 `运行并检查`（`mode:"check"`）；运行中 `data-lab-state="running"`，显示“停止”（`hidden` 去掉）、禁用运行按钮，状态文字 `运行中…`；`timeout` 秒（取 `.lab-spec` 的值）内没收到结果 → `worker.terminate()`、丢弃 Worker、状态文字 `已超时（N 秒），代码已停止`，回到 `ready`；“停止”同理，文字 `已停止`。下次运行自动重建 Worker。
  - 结果：标准输出写入 `#lab-{id}-stdout`（`textContent`），`truncated` 时不额外处理（运行器已加行）；`error` 非空 → `#lab-{id}-error` 显示 `hintZh`（空则显示 `message`）加一行 `第 N 行`，并 `monaco.editor.setModelMarkers` 在 `lineno`（有 `colno` 用它）标红，消息为 `hintZh || message`；用户再编辑就清掉标记。检查清单按 §2 渲染；全部通过 → 存 `passed:true`、显示 `.lab-done`、状态文字 `全部通过 ✓`。
  - 提示与参考写法：`hints` 非空时显示“提示 (k/N)”按钮，每点一次在 `.lab-hints` 里追加一条；检查失败累计 2 次，或提示点完，才显示“参考写法”按钮，点开把 `solution` 以 `textContent` 放进只读 `<code>`。`solution` 为空则不显示按钮。
  - 草稿：每次编辑后（节流 500 ms）`localStorage[draftKey(id)] = serializeDraft(...)`（全部 `try/catch`，存不了也能正常使用）；起始代码哈希不符就用新起始代码。“重置”第一次点把按钮文字变成 `确认重置？`，3 秒内再点才恢复起始代码、清输出、清标记、清除 `passed`；3 秒后文字自动还原。
  - 测试钩子：`window.__EBOOK_LABS__ = {instances: Map}`，每个练习 id 对应 `{getState(), getCode(), setCode(text), run(), check(), stop(), reset(skipConfirm), refreshConfig(), whenState(state, timeoutMs)}`（`whenState` 返回 Promise，状态到达时 resolve，超时 reject）。
  - 可访问性：按钮有可读文字，状态区 `aria-live="polite"`，失败用文字“✗”而非只靠颜色，焦点样式不去掉。
- **我们自己写的 JS（`lab.js`、`lab-core.js`、`lab-guard.js`、`lab-worker.js`）里，任何位置（含注释和字符串）都不得出现 `http://`、`https://` 字样**（全站检查脚本会把它当外部请求）；绝对 URL 一律用 `new URL(相对路径, location.href)` 运行时算出。所有来自学生代码、报错、检查消息的文本只能用 `textContent`，**禁止 `innerHTML`**。

## 8. 服务器（T1，`serve.mjs`）
- MIME 表加 `.wasm → application/wasm`、`.zip → application/zip`、`.mjs → text/javascript; charset=utf-8`；`.py` 已有。
- CSP 改为：`default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`。如果真实原型证明 Monaco 还需要别的（如 `worker-src blob:`），只增加实际需要的，并写进报告。
- `/assets/lab-config.json` 加 `Cache-Control: no-store`；`/assets/vendor/` 下的文件加 `Cache-Control: public, max-age=86400`；其余保持现状。

## 9. 检查脚本新规则（T5，`check_site.py`）
- `vendor-pinned`：站点有 `assets/vendor/` 时，`MANIFEST.sha256` 存在，列出的每个文件存在且哈希相符，目录里的其他文件（除 `MANIFEST.sha256`、`VERSIONS.json`）都在清单里，`monaco/LICENSE`、`pyodide/LICENSE` 在，`VERSIONS.json` 可解析且有两个包的 `version` 和 `integrity`。没有 `assets/vendor/` 且没有任何含练习的页面时通过（“无练习，跳过”）。
- `labs`：对每个含 `section.lab` 的页面——§2 的元素和 id 齐全、`data-lab-state="idle"`、`data-paste-guard="allow"`、`.lab-spec` 是合法 JSON 且字段齐全并与 DOM 的 id 一致、全站练习 id 唯一、`tests` 非空；页面按顺序用 `<script defer src>` 加载 `lab-guard.js`、`lab-core.js`、`lab.js`，且**不含练习的页面不加载它们**；`assets/` 下 `lab.js lab-core.js lab-guard.js lab-worker.js lab-runner.py lab-config.json` 都在，`lab-config.json` 恰是只含布尔 `block_paste` 的对象；这四个 JS 里没有 `http://`/`https://` 字样、没有 `innerHTML`；页面里没有 Monaco/Pyodide 的直接引用。
- 文本类扫描规则（`no-external-load` 的 JS 外部请求检测、`no-claude-runtime`、`no-secret-or-path`、`no-experiment-labels`）**排除 `assets/vendor/`**，其余规则不变。`CHECK_IDS` 加 `vendor-pinned`、`labs`。
- 每条新规则至少一个反例测试，另加“不空过”测试；`mutate_real.py` 加至少 3 个破坏用例。

## 10. 通用约束
纯 ES2019、无构建工具、无第三方库（Monaco 和 Pyodide 除外，且只经 `lab.js` 加载）；界面文字全部中文（见上面引号里的原文，不要改字）；站点所有链接保持相对路径；不引入任何外部网络请求；Python 只用标准库、兼容 3.12；注释少而精，风格贴近同目录现有代码；不留 TODO、占位或假实现。
