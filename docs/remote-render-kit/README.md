# OpenMontage 远程渲染自测包（给渲染机上的智能体）

这个目录让你**自己**把渲染调到最快、并自己证明画面与参考机一致，不用等我们来回传话。

## 你需要什么
- Node ≥ 18，以及与 `input/composer/package-lock.json` 相同依赖的 `node_modules`（你现有运行时的就行，`--node-modules` 指向它）。
- 系统 `ffmpeg` / `ffprobe`，且带 `psnr` 与 `ssim` 滤镜（`ffmpeg -filters | grep -E " psnr | ssim "`）。Remotion 自带的 ffmpeg 没有这两个滤镜，不能用于对比。
- Python 3（标准库即可）。GPU 数据来自 `nvidia-smi`（没有也能跑）。

## 怎么用
```bash
python3 bench.py --node-modules /你的运行时/node_modules --stills-only      # 先跑静帧：几分钟，看画面是否一致
python3 bench.py --node-modules /你的运行时/node_modules                    # 完整矩阵，结果在 results/bench_results.md
python3 bench.py --node-modules ... --matrix my_matrix.json                 # 自己加配置（格式见 bench.py 里的 DEFAULT_MATRIX）
```
每一行配置会：渲 6 张参考静帧并逐张对比（PSNR/SSIM）→ 渲 300 帧视频（K4 板，含等宽行、箭头、数字）并对比 → 记录用时、帧率、CPU/GPU 利用率、显存、最小可用内存 → 给出 PASS/FAIL。

## 判定标准
| 路径 | 静帧 | 视频 |
|---|---|---|
| CPU 路径（`gl` 为空/`swangle`/`swiftshader`，无硬件编码） | PSNR ≥ 50 dB（`inf` = 逐像素相同） | 最低 PSNR ≥ 45 dB |
| GPU 路径（其他 `gl`，或 NVENC） | PSNR ≥ 45 dB 且 SSIM ≥ 0.995 | 最低 PSNR ≥ 42 dB 且平均 ≥ 45 dB |

## 你可以调的东西（作业 `jobs.json` 的 `render` 字段，白名单，缺省 = Remotion 默认）
`gl`（`null/angle/egl/swiftshader/vulkan/angle-egl/swangle`）、`chromeMode`（`headless-shell/chrome-for-testing`）、`hardwareAcceleration`（`disabled/if-possible/required`，Linux 上是 NVENC，需配合 `videoBitrate`，不能用 crf）、`videoBitrate`、`x264Preset`、`jpegQuality`、`restartEvery`（处理多少个部件后重启浏览器，防 ANGLE 内存增长）。另有 `workers`（并行进程数）与 `concurrency`（每进程标签页数；本机实测超过 2 无收益）。
**环境层面的东西由你决定**（驱动、EGL/Vulkan 配置、`CUDA_VISIBLE_DEVICES`、显存预算、cgroup、`TMPDIR`……），不需要改我们的代码。

## 画面一致性的前提（不要改）
- 字体：我们的 `render_chunks.mjs` 在启动 Chrome 前用 `render-fonts/fonts.conf` 设置私有 `FONTCONFIG_FILE`（只含 DejaVu）。**你的服务环境里不能设置 `FONTCONFIG_FILE` / `FONTCONFIG_PATH` / `FC_*`。**
- 参考环境见 `REFERENCE_ENV.txt`。

## 做完之后
把最佳配置写进你的 `probe`：
```json
"render_profile": {"gl": "...", "chromeMode": "...", "tabs": 2, "hardwareAcceleration": "disabled", "videoBitrate": null, "x264Preset": null, "jpegQuality": null, "restartEvery": null},
"capacity": {"max_concurrent_jobs": 2, "max_total_workers": 16, "recommended_workers_per_job": 8}
```
我们的调度器会读取它并随每个作业下发。回复写到 `docs/remote-render-replies/<日期>-roundN.md`：附 `bench_results.md`、`probe` 输出、你改过的系统设置清单。
