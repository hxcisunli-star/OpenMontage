# 互动图（立体图）：写法和查法

2026-11-24 起，电子书可以把选定的静态图“立起来”，变成能动手的立体图（3D）。这份文件写给以后每一门课（智能体课、电子电工基础、计算机组成原理……）：每条原则后面都跟着“查法”，不靠自觉。想法借自 Livebook、Every Joule、Designed to Scale、Electronics 101 四个项目（只借想法，没有用它们一行代码；设计依据见 `projects/_ebook/review/research-20261124/DESIGN-NOTES.md`）。版式规则仍以 `STYLE.md` 为准。

## 一、它是什么
- 章节 JSON 里的一个块：`{"t": "fig3d", "scene": "<场景名>", "records": [记录 id…]}`。
- 页面上先是这些记录原来的静态图（`show()` 画的，一字不差），外面包一层 `div.fig3d`，再附一段场景数据（JSON）。
- `assets/fig3d.js`（three.js 加部件包加场景，构建时用本机的 esbuild 打成一个普通脚本）在读者的浏览器里把它换成立体图：
  - 宽屏：静态图换成立体图，右上角“看原图”可以换回去；
  - 窄屏（小于 760 像素）或“减少动态效果”：静态图不动，多一个“打开立体图”按钮，全屏打开；
  - 没有脚本、没有 WebGL：就是原来的静态书页。
- 页面里不调用任何模型，不联网；离线双击打开（`file://`）也能看。

## 二、原则和查法
| # | 原则 | 查法 |
|---|---|---|
| 1 | **书还是书**：立体图只换图，不换正文；兜底就是原来的静态图，标记和口径照旧 | 整站检查 `fig3d-fallback`：每个 `div.fig3d` 的 `.fig3d-static` 里恰好是 `data-records` 列的那几张 `figure.show`；单元测试 `test_fallback_is_exactly_the_static_figures…` 逐字节比 `show()` |
| 2 | **画出来的每样东西都对回一条记录**：每块积木、每张纸条、每次请求都带记录 id（`rid`） | 适配函数（`fig3d_build.py`）只读记录字段，对不上就让构建失败；`fig3d-fallback` 检查数据里的 `rid` 全在本块的记录里、本块的记录全被用到；浏览器里 `__EBOOK_FIG3D__.instances[i].api.items()` 逐件列出 `rid`，检查脚本核对 |
| 3 | **算出来的、摆出来的标“示意”**：先后顺序、请求本身的宽度、按前提推出来的拆分；**原图的口径和限定说明一句不少**：图注沿用记录自己的标记和口径，原 `show` 块下面那句 `after`（“这只代表……不能推出……”）也显示在立体图的图注里；谁判的结果照记录说（例：“两个 AI 模型分别标注”，不能写成“程序判”） | 场景数据的 `note` 写明哪些是示意；读数条每个数带“实测／示意”小标；`data.afters`、`data.caps` 由构建从静态图同一套函数取 |
| 4 | **一个记忆锚一种画法，全书不变**（智能体课：答案塔、词元积木、纸条摞、重试时间轴） | 场景登记在 `fig3d/scenes.json`（名字、收哪些记录、锚的一句话）；整站检查 `fig3d-scenes` 拦未登记的场景和不收的记录种类 |
| 5 | **先猜再看，不判对错**：猜可以跳过；量出来以后和猜的并排放；**揭晓前画面上不能先露答案**（例：答案塔的塔底文字要等积木落下才出现） | 部件 `ui.guess`；文字固定写“猜的和量的并排放在这里，不判对错”；截图核对“猜之前”的画面 |
| 6 | **分步走，每步说“这一步变了什么”，顶上的读数条跟着变**；←/→ 翻步，步号点能点，能重放 | 部件 `ui.stepper`、`ui.changed`、`ui.readout`；浏览器检查翻到最后一步再核对 |
| 7 | **选项带一句预告**：每档告诉读者选了它会看到什么（例：每个电阻档的按钮上写着这一档的 τ，换电容时跟着变） | `ui.choices` 的 `subs()`（每个选项上的一行）或 `preview`（选中项下面一行）；真实输入检查点一个档位后核对 |
| 8 | **颜色只取 `book.css` 的变量**，深色模式跟着变；三种颜色的用途不变（红＝实测、黄＝当前一步和示意、深蓝＝按钮和选中项） | 场景里不写死颜色（唯一例外：答案的十种淡色，与第 3 课静态图同一套）；浏览器检查点页面的 ◐ 按钮，立体图的颜色跟着变 |
| 9 | **中文标签是 DOM 文字**，不是 3D 字：清楚、能选中、读屏能读；画布本身 `aria-hidden`；**标签不压物件、不互相压**，颜色和记号要有图例 | `core/labels.js`；`test_our_fig3d_code_has_no_urls_and_no_innerhtml` 也禁 `innerHTML`；全尺寸截图逐张看（这次 Antigravity 看图挑出的大多是这一条） |
| 10 | **视角有限度**：只能转一个小角度、缩放有上下限，一键回正；点过画面以后 ←/→ 直接翻步 | 浏览器检查：拖动后角度变了但没超限；“⟲”回到原位；真实输入检查：点画布再按 →，步数加一 |
| 11 | **不联网、不调模型**：包里唯一像网址的字样是 XML 命名空间名 | 整站检查 `fig3d-script`；构建时 `build_bundle` 也查；我们自己的源码里只允许 SVG 命名空间这一处 |
| 12 | **只有有立体图的页加载 `fig3d.js`**，手机默认看静态图 | 整站检查 `fig3d-script`；浏览器检查 390 宽不横滚、“打开立体图”能用 |
| 13 | **省电**：只在有变化时画一帧，滚出屏幕就停 | `core/stage.js` 按需渲染加 IntersectionObserver；浏览器检查里记的帧率是软件渲染的数，不代表真显卡 |

## 三、加一张立体图（步骤）
1. **挑图**：记录本身就有“多遍、多步、多张”结构的图最合适（十遍回答、几次重发、一摞消息）。只有一个数的图不要做成立体图。
2. **先写一页纸**（放进该课的计划或 `validation/`）：用哪几条记录、每条记录的哪个字段画成什么；哪些是实测，哪些是示意；读者要猜什么、动什么、最后看到什么。**图需要一个记录里没有的数，就把图改小，不去编这个数。**
3. **用现成场景**：在章节 JSON 里把**相邻的**几个 `show` 块换成一个 `fig3d` 块（段落不挪位置）：
   ```json
   {"t": "fig3d", "scene": "answer-tower", "records": ["ROWS_hi_name_ds", "ROWS_hi_name_qw"],
    "refs": [], "title": "答案塔：起名字，拨温度", "after": {"ROWS_hi_name_qw": "原来那张图下面的一句话"}, "opts": {}}
   ```
   - `records`：本块的记录，静态兜底就画它们，顺序就是原来的顺序；
   - `refs`：场景还要用、但在本页**别处**已经有静态图的记录（构建和整站检查都核对它们真的在页上）；
   - `after`：原来 `show` 块的 `after`，原样搬过来；`opts`：场景自己的选项（例：纸条摞的 `links`）。
4. **要新场景**：
   1. 在 `fig3d/scenes.json` 登记（名字、收哪些记录种类、锚的一句话）；
   2. 在 `fig3d_build.py` 写适配函数，加进 `ADAPTERS`：只读记录字段；对不上就 `raise ValueError`；画出来的每件东西带 `rid`；在 `note` 里写清哪些是示意；
   3. 写 `fig3d/scenes/<名字>.js`（见第四节）；
   4. 在 `tests/tools/test_ebook_fig3d.py` 加用例：真记录能过、坏记录被拒。
5. **试点**：别动真站点。用 `build_site.py --site-dir <临时目录> --chapters-dir <复制的章节>` 构建；`check_site.py --site <临时目录> --repo . --chapters-dir <复制的章节>` 整站检查；`tests/tools/test_ebook_*.py`；浏览器检查（`projects/_ebook/review/research-20261124/tools/` 的 `f3gates.cjs`：没有脚本、没有 WebGL、减少动态、手机、深色、`file://`、真服务器的 CSP 都会走一遍）。
6. **截图**：电脑、手机、深色各一张，全尺寸逐张看；软件渲染下先确认画面真的画出来了（检查脚本用 `probePixels()`）。

## 四、场景模块的写法
```js
export default {
  name: 'answer-tower',                       // 与 scenes.json 的键一致（构建会核对）
  camera: { yaw, pitch, radius, target, fov, viewHeight },
  create(ctx) {                               // ctx: stage, parts, ui, panel, below, readout, data, reduced, where, setCaption(rids)
    // 用 parts 搭物件、用 ui 搭面板；返回给“重来”按钮和测试用的接口
    return { reset() {}, state() {}, items() {}, step(d) {} /* 有分步时 */ };
  },
};
```
- `stage`：`root`（往里加物件）、`labels.add(物件或坐标, 文字)`、`anim.tween()`、`frame()`（换取景）、`invalidate()`、`pickables`。
- `parts`：`block`（积木、纸条、盒子、芯片）、`paper`、`cylinder`（可半透明）、`wire`（导线或管道，带流动光点）、`axis`（刻度尺和时间轴）、`floor`、`shadow`、`dot`、`pickable`（悬停提示、点击、沿一条轴拖：例 `scenes/rc-charge.js` 的读数游标，和同功能的滑杆配对，键盘和读屏用滑杆）。
- `ui`：`choices`（档位，带预告）、`slider`、`readout`、`changed`、`guess`、`stepper`、`button`。曲线面板用 DOM 的 SVG 画（例：`scenes/rc-charge.js`，阈值线加上一次的影子）。
- 所有文字用 `textContent`；不写网址；动画都走 `stage.anim`（减少动态效果时它直接跳到终点）。

## 五、现有场景的一页纸
| 场景 | 收的记录 | 画什么 | 实测 | 示意 |
|---|---|---|---|---|
| 答案塔 `answer-tower` | `towers`（每种回答几遍）、`rows`（每一遍是第几种回答） | 一遍一块积木，同样的回答垒成一座塔；可换问题、模型、温度档 | 块数、塔数；`rows` 的遍序 | `towers` 没有遍序，落下的先后是示意 |
| 词元积木 `token-blocks` | `usage`（小票上的 prompt_tokens） | 小票上的数摆成积木：灰的包装、彩色的内容 | 小票上的总数 | 包装和内容的拆分：按“单个字母 a 占 1 个词元”的前提推算 |
| 纸条摞 `note-stack` | `stack` 加 `grids`（抽掉、换掉一张，看十遍结果）；`window`（钉住、只寄最近几条、撕下） | 每条消息一张纸条；结果每遍一块小方块 | 纸条上的字、每格十遍的判定 | 纸条怎么摆；`window` 记录本身就是示意 |
| 重试时间轴 `retry-timeline` | `sequence`（本机模拟的发送记录）、一条 `callpanel`（脚本的规矩） | 两条轨道，请求飞过去、回信飞回来，等待画成轴上的空档 | （记录本身是本机模拟，标示意） | 请求本身在轴上占的宽度 |
| RC 充电 `rc-charge`（演示，不进书） | 无（公式） | 电池、电阻、电容、开关、带光点的回路；电压曲线 | — | 全部按公式算 |
| 取指·译码·执行 `fetch-decode`（演示，不进书） | 无（构建时把三条指令真跑一遍） | 内存、PC、IR、控制器、寄存器、ALU、总线 | — | 玩具机器的教学模型 |

演示页：`python docs/whiteboard/ebook/fig3d_build.py demo <输出目录>`，它也是部件包的回归测试（`review/research-20261124/tools/demotest.cjs`）。

## 六、依赖和许可
- three.js 0.187.0（MIT），由 `fetch_vendor.py` 钉版本、用 npm 的 sha512 校验，不运行包里的任何脚本；只留 `build/three.module.js`、`build/three.core.js` 和 `LICENSE`，记进 `vendor/VERSIONS.json` 和 `MANIFEST.sha256`。
- 打包：`remotion-composer/node_modules/.bin/esbuild`（本机现成的 0.28.1，没有新装任何东西）。`fig3d.js` 开头是 three.js 的整段 MIT 许可证文字（整站检查 `fig3d-script` 要求它在）。
- 我们自己的代码（`fig3d/`、`fig3d_build.py`）是本仓库的一部分（AGPL-3.0）。
