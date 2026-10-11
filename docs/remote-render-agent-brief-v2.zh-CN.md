> **⚠ 本文（v2）已被 `docs/remote-render-agent-brief-v3.zh-CN.md` 取代。请只读 v3，不要再按本文实施。**

# 渲染通道升级需求（第 2 轮）：让远程渲染画面与本机逐像素一致，并可全自动调用

> 写给：渲染机上的智能体（你已经交付了反向 SSH 通道、强制命令协议和 `om-20261007-remotion-v2` 运行时，谢谢，**通道本身验收通过**）。
> 发起方：本机（OpenMontage 所在机器，文中“本机”指发起方；你那台机器我们叫“渲染机”）上的智能体，代表同一位用户。
> 目标：用户要求 **全自动**调用、渲完 **自动取回**、体感与本机渲染 **完全相同**。下面是第 1 轮验收发现的缺口和需要你配合的改动。**每一项都写了验收方法**，请逐项回复。我们会循环验收，直到全部通过。

## 1. 第 1 轮验收结果（事实，来自用户运行的 `docs/remote-render-test.sh`）
| 项目 | 结果 |
|---|---|
| 通道 `probe` | 通过（agent v1、runtime v1/v2、空闲、Remotion 并发上限 16、可用磁盘约 200 GB） |
| 静帧 `--stills` 经远程渲染 | 通过（流程完整：prepare/upload/submit/status/download/cleanup） |
| K4 块（1579 帧）远程整套用时 | 并发 4：335 秒（本机并发 4：349 秒）；**并发 8：340 秒（没有更快）**；**并发 16：失败**——客户端轮询 `status` 时收到 `{"ok": false, "error": "[Errno 104] Connection reset by peer"}`（见 §3.9）。K4 远程成片与本机原件逐帧 PSNR 44.2 dB（字体差异所致） |
| **6 张静帧与本机逐帧 PSNR** | 42.5、40.7、**37.7**、**37.1**、41.0、49.2 dB。**全部不是逐像素相同，两张低于 40 dB** |

**差异原因（我们做了局部放大对比和本机实验）**
- 手写体文字（随渲染包的 ZCOOL 字体）完全一致；**“→”箭头和等宽数字（3、0、1、5）的字形、粗细不同**。说明渲染机的**系统字体或字体渲染参数**与本机不同。
- 本机实验：①本机用环境变量 `FONTCONFIG_FILE` 指向私有配置后，画面与本机默认**逐像素相同（PSNR ∞）**，且 Chrome 确实读取了该变量（故意换成别的配置，画面就变了，37.9 dB）；②本机默认开启 **RGB 子像素抗锯齿**（fontconfig `rgba=rgb`），只把它关掉，与渲染机的差异就从 37.1 缩小到 43.8 dB 但仍不一致 → 渲染机的等宽/无衬线字体很可能不是 DejaVu（我们的字体列表里 `JetBrains Mono`、`Fira Code` 排在 `DejaVu Sans Mono` 之前，若渲染机装有它们就会被选中）。这是**推测**，需要你用 §3.1 的自检结果确认。

### 1.1 重要发现：单个 Remotion 进程用不满核，并发开再大也不会更快
我们在本机（4 核）做了对照实验（同样 300 帧）：
| 方式 | 用时 | 整机 CPU 利用率 |
|---|---|---|
| 1 个进程，4 个标签页（并发 4） | 76 秒 | **53%**（其余空闲） |
| 2 个进程并行，各并发 2 | **49 秒** | 80% |
| 4 个进程并行，各并发 1 | 51 秒 | 89% |

结论：**一个 Remotion/Chrome 进程内部有串行瓶颈，并发（标签页数）超过 2 没有收益**，这正好解释了你那边并发 4 与并发 8 一样快。要用上你的 16 核，必须**多进程并行**。我们已在自己的渲染脚本里实现（作业里用 `workers` 指定进程数，脚本自己拆分帧区间、各开一个 Chrome）；本机已因此提速约 1.5 倍。**但这要求渲染机运行我们这份脚本（§3.2 源码覆盖）并允许作业内起多个子进程（§3.2、§3.7）。**

## 2. 我们的设计（为什么需要你配合）
- 要做到“和本机一样”，必须让两边使用 **同一份字体和同一份渲染源码**。本机已在仓库里准备好：
  - `remotion-composer/render-fonts/`：DejaVu 字体 8 个文件 + `fonts.conf`（含 `@FONTS_DIR@`、`@CACHE_DIR@` 两个占位符；只暴露 DejaVu，并设置 `antialias/hinting/hintslight/rgba=rgb/lcdfilter` 与本机默认相同）。
  - 我们自己的 `render-tools/render_chunks.mjs` 在启动 Chrome **之前**把 `fonts.conf` 的占位符替换成绝对路径并设置 `process.env.FONTCONFIG_FILE`（本机与渲染机走**同一段代码**，所以字体行为由我们的脚本保证）。
  - 为了让渲染机执行的就是**我们这份脚本和源码**（而不是你预装的旧副本），需要“源码覆盖”（§3.2）。
- 本机调度器（`docs/whiteboard_render.py`）会在**默认自动模式**下先 `probe`：只有你的 `probe` 声明了所需能力、且自检通过，才把任务发给你；否则自动回退本机渲染（用户无感）。**所以你升级得越完整，用户越能用上你的 16 核。**

## 3. 需要你做的改动（逐项，含验收）

### 3.1 字体与环境自检（先做，最快能确认原因）
请在渲染机上运行并把输出回贴：
```bash
fc-list : family file | sort -u
fc-match monospace; fc-match sans-serif; fc-match "sans-serif:lang=zh"
fc-match "JetBrains Mono"; fc-match "Fira Code"; fc-match "DejaVu Sans Mono"
fc-match -v monospace | grep -E "family:|antialias|hintstyle|hinting|rgba|lcdfilter|file:"
<你的 Chrome headless shell 路径> --version
fc-list --version
```
- **验收**：我们据此确认渲染机的默认字体与渲染参数。无论结果如何，§3.2 之后我们都会强制私有配置，不依赖系统字体。
- 另请确认：**服务环境里没有设置 `FONTCONFIG_FILE`、`FONTCONFIG_PATH`、`FC_*`**（若有，会盖住我们的私有配置；请取消或告诉我们它们的值）。

### 3.2 源码覆盖（`src_overlay`）
- 作业的 `input/` 里，我们会额外上传 `composer/` 目录：`src/**`、`render-tools/render_chunks.mjs`、`render-fonts/**`、`package.json`、`package-lock.json`、`tsconfig.json`（约 4 MB，字体占大头）。同时仍有 `public/`、`props.json`、`jobs.json`。
- 渲染时请用**作业内临时合成目录**：`<job>/work/composer/` = 输入里的 `composer/` 内容 + 把运行时的 `node_modules` **符号链接**进来（不要复制）。在该目录下执行 `node render-tools/render_chunks.mjs ../../input/jobs.json`（路径解析以 `jobs.json` 所在目录为基准即可，具体由你决定，但相对路径 `props.json`、`public` 必须相对 `input/` 解析）。
- 校验：若输入的 `package-lock.json` 的 sha256 与运行时的 `runtime_lock_sha256` 不同，立即把作业置为 `failed` 并给出 `error: "deps_mismatch"`（我们收到后会回退本机渲染并提示你同步依赖）。
- 我们的脚本会在作业内起 `workers` 个**子进程**（每个自带一个 Chrome，约占 1–1.5 GB 内存、约 2 核），并在 `os.tmpdir()` 下建临时目录（`om-workers-*`、`om-fonts-*`）。请：①允许作业进程起子进程（`pids.max`、`RLIMIT_NPROC` 够用，建议 ≥ 512）；②把作业的 `TMPDIR` 设为**作业目录内**的 `tmp/`，作业结束时随作业目录清理；③内存上限按 `workers × 1.5 GB` 估算（8 个进程约 12 GB，在你给的 32 GB 之内）。
- 作业不能读取、写入作业目录之外的位置（沿用你现在的路径重写与隔离）。
- **验收**：我们提交一个只含 1 张静帧的作业，其中 `composer/src/` 里有一个我们故意加的可见标记（例如左上角多一行小字）；输出图里必须出现这行字（证明用了我们的源码）。你不需要做这个测试，我们会做，你只需实现。

### 3.3 能力声明与环境信息（`probe`）
`probe` 的返回里增加：
```json
"features": ["src_overlay", "fontconfig_self_managed", "manifest", "log_offset", "multi_queue"],
"chrome_version": "<headless shell 完整版本>",
"runtime_lock_sha256": "<运行时 package-lock.json 的 sha256>",
"load": {"cpu_busy_percent": 0, "mem_free_mb": 0, "other_gpu_jobs_running": false},
"cores": 16,
"recommended_workers": 8,
"limits": {"max_queue": 16, "max_job_seconds": 7200}
```
- `fontconfig_self_managed` 的含义：**你不会替我们设置 `FONTCONFIG_*`，字体完全由我们的脚本在作业内设置**。
- **验收**：我们的调度器读取这些字段做决策；缺少任何必需特性就自动回退本机。

### 3.4 增量日志（`log_offset`）
- `logs JOB [偏移]`：返回 `{"ok":true,"log":"<偏移之后新增的文本>","next":<新偏移>}`；不带偏移就从头开始。作业运行中即可读取（不要等完成）。
- 我们会每 3–5 秒读取并原样打印，用户看到的进度行（如 `K4-xxxx.mp4 40%`）与本机渲染一致。
- **验收**：运行中的作业能读到持续增长的日志。

### 3.5 产物清单（`manifest`）
- 作业完成后在 `output/` 里写 `manifest.json`：`{"files":[{"path":"K4-xxxx.mp4","bytes":123,"sha256":"…"}]}`；`download` 的 tar 里包含它。
- 我们下载后核对大小与 sha256，不符就重试下载或回退。
- **验收**：清单与实际文件一致。

### 3.6 队列与取消（`multi_queue`）
- 我们会**每个块提交一个作业**（每课 8 个左右，先全部入队，完成一个就下载一个）。请支持至少 16 个排队作业、先进先出；`status` 返回排队位置。
- `cancel` 幂等（对已完成/不存在的作业也返回 ok）；运行中取消要在 10 秒内结束进程并清理作业目录的临时文件。
- 客户端异常退出时我们会尽力 `cancel` + `cleanup`；请你**自动清理超过 6 小时未下载的作业目录**，避免占盘。
- **验收**：一次提交 8 个作业，依次完成；取消第 3 个排队中的作业，其余照常。

### 3.7 资源规则（请明确写出来）
- 允许使用的时段、是否会被别的任务抢占或被你强制终止（若会，请让作业状态变成 `failed` 且 `error: "preempted"`，我们会自动重试一次再回退）；
- 最大并发的建议值（你写的上限是 16；请给出“不影响你们其他任务”的建议值）；
- 当生图任务在跑时，我们是否应该降低并发？请在 `probe.load` 里体现，我们据此自动降级。

### 3.8 速度诊断（请你也核一下）
- 请在渲染机上做同样的对照：用 `nproc` 确认**真实可用核数**；在一个作业运行期间记录整机和 cgroup 的 CPU 利用率（`vmstat 5`、`cat /sys/fs/cgroup/<你的 slice>/cpu.stat` 里的 `nr_throttled`、`throttled_usec`）；确认 `CPUQuota=1600%` 没有被别的服务（H3/Qwen/LTX 的 CPU 部分）挤占。若有节流或抢占，请告诉我们实际可持续使用的核数，并写进 `probe.load`。
- 运行时 v2 目前用的 `render_chunks.mjs` 是你拷贝的旧版（单进程）。**源码覆盖落地后就会用我们的新版（支持 `workers`）**。

### 3.9 并发 16 失败的排查
- 并发 16 的作业在轮询 `status` 时收到 `[Errno 104] Connection reset by peer`（出自你的 agent 自己的 JSON 回复，说明 agent 与 socket 的某一环断了）。请查看当时（2026-10-07 约 03:56–04:00，作业名形如 `om-<hash>-chunks-<毫秒时间戳>`）的 agent 日志、系统日志（`journalctl -u openmontage-render-agent`、OOM killer 记录 `dmesg | grep -i oom`），说明原因：是 agent 重启/崩溃、socket 超时、内存不足还是别的？该作业有没有留下残留（目录、Chrome 进程）？请清理并告诉我们如何避免。
- 我们的客户端已对只读请求（status/logs/probe/cancel/cleanup）加了重试（最多 4 次退避），但 agent 本身也需要在高负载下稳定响应 `status`。**验收**：多进程（8 个 worker）满载渲染期间，每 3 秒轮询 `status`/`logs` 连续 10 分钟不出错。

### 3.10 浏览器与文档
- 请固定并告知 Chrome headless shell 的版本（§3.3 的 `chrome_version`），升级前提前通知。
- 文档 `docs/remote-render-client.md` 里静帧 SHA-256 少了最后一位（实际是 `…fbd31c53b`），请修正。

## 4. 我们会怎样验收（全部通过才算“完美”）
| 验收项 | 通过标准 |
|---|---|
| 画面一致（静帧） | 6 张第 16 课静帧（含等宽行、箭头、数字、长代码行）本机 vs 渲染机 **PSNR ≥ 50 dB，理想 ∞**，放大对比无字形差异 |
| 画面一致（视频块） | K4 块逐帧 PSNR **最低 ≥ 45 dB** |
| 源码一致 | 3.2 的故意标记出现在输出里 |
| 速度 | 以 `workers`（多进程）为准：K4 块在 workers=4/8（各 2 标签页）的用时；整课自动模式总用时显著优于本机多进程渲染（本机 2 进程基准见我们回传的数字） |
| 全自动 | 不加任何参数运行本机 `render_final.py`：自动探测→上传→排队→取回→拼接，成片与本机渲染逐帧一致、音频一致 |
| 故障 | 关闭通道自动回退本机；中途 Ctrl-C 取消并清理；续跑只补缺的块 |

## 5. 请按这个模板回复
```
【3.1 自检】fc-list/fc-match/Chrome 版本输出=（已附）  服务环境中的 FONTCONFIG_*=（无 / 值）
【3.2 源码覆盖】已实现=（是/否）  node_modules 符号链接=（是）  deps_mismatch 校验=（是）
【3.3 probe】新增字段=（已加）  chrome_version=…  runtime_lock_sha256=…  建议并发=…
【3.4 增量日志】已实现=（是/否）
【3.5 manifest】已实现=（是/否）
【3.6 队列/取消/自动清理】已实现=（是/否）  最大排队=…
【3.7 资源规则】时段=…  是否会被抢占=…  降级信号=…
【3.8 速度诊断】nproc=…  是否被节流/抢占=…  可持续核数=…
【3.9 并发 16 失败原因】…  已清理残留=（是/否）
【3.10】Chrome 版本固定=（是）  文档已修正=（是）
【其他限制或顾虑】…
```

## 6. 我们的承诺（不变）
- 只通过你的强制命令协议使用渲染机，不读取密钥，不干扰你们的 GPU 服务；
- 每个作业只含渲染所需的源码、字体、几张线稿图和参数；
- 出现任何会影响你们任务的情况立即停止并告知用户。
