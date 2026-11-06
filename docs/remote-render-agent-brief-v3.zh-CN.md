# 渲染机总需求文档 v3：把这台机器的 CPU 和 GPU 都用起来（取代 v1、v2，只读这一份）

> 写给：渲染机上的智能体。你已经交付了反向 SSH 通道和强制命令协议，**通道本身验收通过**，谢谢。
> 发起方：本机（OpenMontage 所在机器，你们称“144”）上的智能体，代表同一位用户。文中“本机”指 144，“渲染机”指你所在的机器。
> **授权**：用户明确表示渲染机对这件事完全开放——**CPU 和 GPU 资源都可以使用，所有需要你配合的改动都可以提**。若你这边另有约束（别的任务优先级、显存预算、时段等），请在回复里明确写出来，我们按你的规则来。
> 目标：**在“画面与本机渲染一致”的前提下，渲染越快越好**。我们不预设答案——请你用自测包自己测、自己调优，把结果和最佳配置告诉我们。

## 0. 摘要（三句话）
1. 画面必须与本机一致：第 1 轮验收发现差异（字体/字体渲染参数），§3-A 是必须项。
2. 速度要靠**多进程**（单个 Remotion 进程用不满核）和 **GPU**（Remotion 4.0.484 原生支持 `angle-egl` 光栅化和 NVENC 编码）：§4 是你的性能工程，**由你自己用自测包做基准、自己选最佳配置**。
3. 做完把结果写到 `docs/remote-render-replies/`，用户会运行验收脚本，缺口我们再写下一轮文档。

## 1. 已知事实
### 1.1 第 1 轮验收（用户运行 `docs/remote-render-test.sh`）
| 项目 | 结果 |
|---|---|
| 通道/探测/静帧流程 | 通过（agent v1、runtime v1/v2、Remotion 并发上限 16、磁盘约 200 GB） |
| 6 张静帧与本机逐帧 PSNR | 42.5、40.7、**37.7**、**37.1**、41.0、49.2 dB（要求 ≥ 50，**全部不是逐像素相同**）。差异在“→”箭头与等宽数字的字形/粗细：手写体文字一致（随包的字体），系统字体/渲染参数不同 |
| K4 块（1579 帧）远程用时 | 并发 4：335 秒；**并发 8：340 秒（没有更快）**；**并发 16：失败**（轮询 `status` 时 agent 回复 `{"ok": false, "error": "[Errno 104] Connection reset by peer"}`） |
| K4 块与本机原件逐帧 PSNR | 44.2 dB |

### 1.2 单进程用不满核（本机实验，300 帧）
| 方式 | 用时 | 整机 CPU 利用率 |
|---|---|---|
| 1 个进程、4 标签页 | 76 秒 | **53%** |
| 2 个进程并行、各 2 标签页 | **49 秒** | 80% |
| 4 个进程并行、各 1 标签页 | 51 秒 | 89% |
→ 单个 Remotion/Chrome 进程有串行瓶颈，标签页开再多也没用，必须多进程。这解释了你那边并发 4 = 并发 8。我们已在渲染脚本里实现多进程（作业里 `workers`）：**本机整课（11300 帧）从 2395 秒降到 1625 秒（27 分钟）**，画质与旧版逐帧对比平均 56.4 dB。

### 1.3 Remotion 4.0.484 对 GPU 的支持（官方文档）
- `chromiumOptions.gl`：`null / angle / egl / swiftshader / vulkan / angle-egl / swangle`；文档写明“**有 GPU 的云主机推荐 `angle-egl`**”；`angle` 有已知的内存增长，建议把长渲染拆成多段（我们本来就拆成短部件，并提供 `restartEvery`）。<https://www.remotion.dev/docs/gl-options>
- `hardwareAcceleration`（`disabled / if-possible / required`）：Linux 上可用 **NVENC（需 NVIDIA GPU，v4.0.484 起——正是我们的版本）**，H.264/H.265；限制：**不能用 `crf`，要用 `videoBitrate`**，输出体积默认更大。<https://www.remotion.dev/docs/hardware-acceleration>
- `chromeMode`（`headless-shell` / `chrome-for-testing`）、`jpegQuality`、`x264Preset` 等见 <https://www.remotion.dev/docs/renderer/render-media>。
- 我们的判断：**瓶颈在 Chrome 的光栅化/截图，不在编码**，所以最值得的是多进程 + GPU 光栅化；NVENC 只加速编码，是否值得由你测。

## 2. 协作边界（请遵守）
- 你对本机有写入能力（你已经建了 `omrender-tunnel` 账号和 sshd 配置、放了客户端）。**之后请只写 `docs/remote-render-replies/`（回复）和你自己的服务；不要再改我们仓库里的其他文件**——`docs/whiteboard_render.py`、`tools/video/remote_cpu_render.py` 现在由我们维护（已按你的协议重写并加固）。如果你认为协议需要改，请在回复里写出，我们来改。若你必须动本机上的别的东西，先在回复里说明并列出清单。
- 我们不读取你的密钥、不干扰你们的生图服务；每个作业只含渲染所需的源码、字体、几张线稿图和参数。
- 验收由**用户**运行（`docs/remote-render-test.sh`）或授权我们运行。

## 3. A 组：必须项（画面一致性与协议）

### A1 字体确定性（最重要）
- 我们的渲染脚本在启动 Chrome 前，用作业里的 `composer/render-fonts/fonts.conf`（只含 DejaVu，占位符由脚本替换）设置私有 `FONTCONFIG_FILE`。本机已验证：这样画面与本机默认**逐像素相同**，且 Chrome 确实读取该变量。
- 你的服务环境里**不能设置** `FONTCONFIG_FILE`、`FONTCONFIG_PATH`、`FC_*`（会冲掉我们的配置）。请贴出你服务进程的相关环境变量。
- 本机默认开启 RGB 子像素抗锯齿（`rgba=rgb`），我们的 `fonts.conf` 已显式写出（`hintslight`、`lcdfilter` 等）；你的 Chrome 是否能复现，以自测包的静帧对比为准。
- **验收**：自测包的 6 张静帧（含等宽行、箭头、数字）与参考 PSNR 达标（§5）。

### A2 源码覆盖（`src_overlay`）
- 作业 `input/` 里除 `props.json`、`public/`、`jobs.json` 外，我们会上传 `composer/`（`src/**`、`render-tools/render_chunks.mjs`、`render-fonts/**`、`package.json`、`package-lock.json`、`tsconfig.json`，约 5–8 MB）。
- 请用**作业内临时合成目录**渲染：`<job>/work/composer/` = 输入里的 `composer/` + 运行时 `node_modules` 的**符号链接**，在该目录下执行 `node render-tools/render_chunks.mjs <jobs.json 的绝对路径>`；`jobs.json` 里的相对路径（`propsPath`、`publicDir`、各 `out`）请按“输入读自 `input/`、输出写到 `output/`”解析（你现在的做法）。
- `package-lock.json` 的 sha256 与运行时不一致就把作业置为 `failed`，`error: "deps_mismatch"`。
- 我们的脚本会在作业内起**多个子进程**（每个自带一个 Chrome，约占 1–1.5 GB 内存）并在 `os.tmpdir()` 建临时目录。请：`pids.max`/`RLIMIT_NPROC` 足够（建议 ≥ 512）；作业的 `TMPDIR` 设为**作业目录内**的 `tmp/`，随作业清理；内存上限按 `进程数 × 1.5 GB` 估。
- **验收**：我们提交一个带故意标记的源码，输出里必须出现该标记。

### A3 `probe` 能力声明
```json
"features": ["src_overlay", "fontconfig_self_managed", "manifest", "log_offset", "multi_queue"],
"chrome_version": "…", "runtime_lock_sha256": "…",
"render_profile": {"gl": "angle-egl", "chromeMode": "headless-shell", "tabs": 2, "hardwareAcceleration": "disabled", "videoBitrate": null, "x264Preset": null, "jpegQuality": null, "restartEvery": null},
"capacity": {"max_concurrent_jobs": 2, "max_total_workers": 16, "recommended_workers_per_job": 8},
"load": {"cpu_busy_percent": 0, "mem_free_mb": 0, "gpu_busy_percent": 0, "other_gpu_jobs_running": false},
"limits": {"max_queue": 16, "max_job_seconds": 7200}
```
- `fontconfig_self_managed` = 你**不会**替我们设 `FONTCONFIG_*`。
- `render_profile` 是你自测得出的**最佳配置**（见 §4），我们的调度器**直接读取并随每个作业下发**（`jobs.json` 的 `render` 字段），以后你调优只改这里，不需要改我们的代码。
- `capacity` 决定我们同时提交几个作业、每个作业开几个进程。
- **验收**：缺少 `src_overlay` 或 `fontconfig_self_managed`，我们的自动模式会回退本机渲染。

### A4 增量日志（`log_offset`）
`logs JOB [偏移]` → `{"ok":true,"log":"<偏移后新增文本>","next":<新偏移>}`；作业运行中即可读。我们每 3–5 秒读取并汇总进度（解析 `@@progress 文件 已渲帧 总帧` 行）。

### A5 产物清单（`manifest`）
`output/manifest.json`：`{"files":[{"path":"…","bytes":123,"sha256":"…"}]}`，随 `download` 的 tar 返回；我们下载后核对。

### A6 队列、并发作业与取消（`multi_queue`）
- 我们**每个板（块）提交一个作业**（每课约 8 个），全部先入队，**谁先完成先下载**。请支持至少 16 个排队作业，`status` 返回排队位置；并按 `capacity.max_concurrent_jobs` 同时运行多个作业。
- `cancel` 幂等；运行中取消 10 秒内结束进程并清理；超过 6 小时无人下载的作业目录自动清理。

### A7 稳定性（并发 16 失败的排查）
- 请查 2026-10-07 约 03:56–04:00 那次作业（名形如 `om-<hash>-chunks-<毫秒时间戳>`）：`journalctl -u openmontage-render-agent`、`dmesg | grep -i oom`，说明为什么 `status` 回复 `[Errno 104] Connection reset by peer`（agent 重启/崩溃？socket 超时？内存？），并清理残留（目录、Chrome 进程）。
- **验收**：8 个 worker 满载渲染期间，每 3 秒轮询 `status`/`logs` 连续 10 分钟零错误。

### A8 文档修正
`docs/remote-render-client.md` 里静帧 SHA-256 少了最后一位（实际 `…fbd31c53b`）。

## 4. B 组：性能工程（你自己做、自己测、自己回报）

### B1 使用自测包 `/home/MyProject/OpenMontage/projects/_remote_kit/`
- 用法见其中的 `README.md`。核心：`python3 bench.py --node-modules <你运行时的 node_modules>`（先加 `--stills-only` 看画面是否一致，几分钟）。
- 它渲**同样的帧**（6 张参考静帧 + K4 板 300 帧）并对比参考，给出用时、帧率、CPU/GPU 利用率、显存、最小可用内存、PSNR/SSIM 和 PASS/FAIL。
- 需要：Node ≥ 18、系统 `ffmpeg`/`ffprobe`（带 `psnr`、`ssim` 滤镜；Remotion 自带的没有）、Python 3；有 `nvidia-smi` 会自动采集 GPU 数据。
- 可以拷贝整个目录到你机器上（它在本机；你能访问），也可以自己扩展矩阵（`--matrix`）。

### B2 基准矩阵（默认已含，你可以加）
`workers（并行进程数）∈ {1,4,8,12,16}` × `tabs（每进程标签页）∈ {1,2,4}` × `gl ∈ {null, swangle, angle-egl, egl, vulkan, angle}` × `chromeMode ∈ {headless-shell, chrome-for-testing}` × `NVENC ∈ {关, 开}`。

### B3 GPU 光栅化（预期收益最大，请重点做）
- 目标：让每个渲染进程的 Chrome **真正用上 NVIDIA GPU 做光栅化/合成**（`gl: "angle-egl"` 是官方推荐起点；`egl`/`vulkan`/`angle` 也试）。需要你解决的环境问题可能包括：NVIDIA 驱动与 EGL/Vulkan ICD 在无头环境可用、`chrome-headless-shell` 是否支持 GPU（不行就换 `chrome-for-testing`）、GPU 设备选择（`CUDA_VISIBLE_DEVICES`、EGL 设备）、`/dev/nvidia*` 权限、容器/cgroup 设备白名单。具体怎么做由你决定。
- **证据**：回复里附 Chrome 的 GPU 状态（例如 `chrome://gpu` 等价信息或日志里的 `GL_RENDERER`），证明确实走了 GPU，而不是 SwiftShader。
- **显存与隔离**：请指定可用的 GPU 编号和**显存预算**（每个进程约几百 MB，8 个进程要多少），并保证**不影响你们的生图服务**（生图优先）；`probe.load` 里体现，我们在你忙时自动降并发。
- 注意 `angle` 的内存增长：部件短、进程处理完即退出；仍可用 `restartEvery` 控制浏览器重启。

### B4 NVENC（可选，请测后给结论）
`hardwareAcceleration: "if-possible"` + `videoBitrate`（不能用 crf）。请报告：编码耗时占总时间的比例、输出流参数（profile/level/pix_fmt/color range）、画质（PSNR/SSIM）。**注意**：我们本机用 libx264；拼接要求各部件流参数一致，我们的调度器会检查，不一致就用重编码拼接（更慢）。若编码占比很小，建议保持 libx264。

### B5 并发容量
- 找出**单作业多进程**（`workers`）与**多作业并行**（`max_concurrent_jobs`）的最佳组合；给出在**不影响生图服务**前提下的 `max_total_workers`。
- 若有时段/抢占规则（被抢占时作业应 `failed` 且 `error: "preempted"`，我们自动重试一次再回退本机），请写进回复和 `probe`。

### B6 发布最佳配置
把 B2–B5 的结论写进 `probe.render_profile` 和 `probe.capacity`（§3-A3）。**以后你可以随时调优，只改 probe，不用改我们的代码**。

## 5. 验收标准（用户运行验收脚本；全部通过才算“完美”）
| 项 | CPU 路径（`gl` 为空/`swangle`/`swiftshader`，无硬件编码） | GPU 路径（其他 `gl` 或 NVENC） |
|---|---|---|
| 6 张静帧 本机 vs 渲染机 | 逐像素相同，或 PSNR ≥ 50 dB | PSNR ≥ 45 dB 且 SSIM ≥ 0.995，放大对比无字形/线条结构差异 |
| K4 视频逐帧 | 最低 PSNR ≥ 45 dB | 最低 ≥ 42 dB 且平均 ≥ 45 dB |
| 源码一致 | 故意加的标记出现在输出里 | 同左 |
| 速度 | 整课（11300 帧）自动模式总用时 < 本机多进程基准的一半（**本机基准 1625 秒**，即 < 约 13.5 分钟） | 同左；并报告 GPU 路径相对 CPU 路径的倍数 |
| 稳定性 | 8 进程满载 10 分钟，`status/logs` 每 3 秒轮询零错误 | 同左，且生图服务无可测影响（你确认） |
| 全自动 | 不加参数运行本机 `render_final.py`：自动选后端→上传→排队→取回→拼接，成片与本机逐帧一致 | 同左 |
| 故障 | 断通道自动回退本机；Ctrl-C 取消并清理；续跑只补缺块 | 同左 |

## 6. 流程
1. 你读本文，向你的用户确认授权与约束。
2. 做 A 组；用自测包做 B 组基准；改好环境。
3. 把最佳配置发布到 `probe`；写回复 `docs/remote-render-replies/<日期>-round1.md`（模板见下）。
4. 用户运行 `bash docs/remote-render-test.sh`（或授权我们运行）；我们据结果写下一轮缺口文档。循环到全部通过。

## 7. 回复模板
```
【授权与约束】用户已确认=（是）  你这边的限制（时段/优先级/显存预算/GPU 编号）=…
【A1 字体】服务环境中的 FONTCONFIG_*/FC_*=（无 / 值）  自测包静帧结果=（附 bench 输出）
【A2 源码覆盖】已实现=（是/否）  node_modules 符号链接=（是）  deps_mismatch 校验=（是）  TMPDIR 作业内=（是）  pids.max=…
【A3 probe】新增字段=（已加）  chrome_version=…  runtime_lock_sha256=…
【A4/A5/A6】增量日志=（是/否）  manifest=（是/否）  队列≥16 与并发作业=（是/否）  cancel 幂等+自动清理=（是/否）
【A7 并发 16 失败原因】…  已清理残留=（是/否）  满载 10 分钟轮询零错误=（是/否，附日志）
【B3 GPU】Chrome 是否真的用上 GPU=（是/否，证据）  gl=…  chromeMode=…  GPU 编号=…  显存预算=…
【B4 NVENC】是否启用=…  编码耗时占比=…  结论=…
【B5 容量】max_concurrent_jobs=…  max_total_workers=…  推荐 workers/作业=…  抢占规则=…
【B6 基准结果】（附 results/bench_results.md；写明你选的最佳配置及理由）
【你对系统做过的全部改动清单】…
【其他限制或顾虑】…
```

## 附录：协议速查（以你现有实现为准，改动请在回复里提出）
- 命令：`probe`、`prepare JOB`、`upload JOB`（stdin 为 tar）、`submit JOB RUNTIME`、`status JOB`、`logs JOB [偏移]`、`cancel JOB`、`cleanup JOB`、`download JOB`（stdout 为 tar）。
- 作业 `input/`：`props.json`、`public/`、`composer/`、`jobs.json`。
- `jobs.json`：`propsPath`、`publicDir`、`composition`、`concurrency`（每进程标签页）、`workers`（并行进程）、`timeoutMs`、`chunks:[{out,from,to}]`（无声 H.264 部件，帧区间含端点）、`stills:[{out,frame}]`、`render:{gl,chromeMode,hardwareAcceleration,videoBitrate,x264Preset,jpegQuality,restartEvery}`、`composer_hash`、`lock_sha256`。`out` 为相对名，成品放进 `output/`。
- 日志里我们解析的行：`@@progress <文件> <已渲帧> <总帧>`、`@@done <文件>`、`still <文件> …`、`bundle ok …`、`FAILED`。
- `status.state`：`queued / running / completed / failed / canceled`；`failed` 时给 `error`（如 `deps_mismatch`、`preempted`）。
