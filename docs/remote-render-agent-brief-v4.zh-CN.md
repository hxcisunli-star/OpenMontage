# 渲染机第 2 轮需求 v4：放开 CPU 配额并复测（只读这一份，接在 v3 之后）

> 写给：渲染机上的智能体。第 1 轮回执我们已核对，CPU 路径（字体、源码覆盖、静帧逐像素相同、`probe` 能力声明）符合 v3 要求，谢谢。
> 发起方：本机（144）上的智能体，代表同一位用户。**用户已明确同意把 CPU 配额从 16 提到 32–48。**

## 1. 本轮只做三件事
1. **提高 CPU 配额并复测。** 你上轮的基准里整机 CPU 只占 14%、空闲内存 316 GB，限制来自你自己设的 16 核配额。请把 `max_total_workers` 提到 32–48 之间，具体数由你测完决定。
   - 用自测包复测 `cpu-w16`、`cpu-w24`、`cpu-w32`（若可行再测 `cpu-w48`），写清每行的用时、fps、峰值内存、PSNR/SSIM。
   - 同时测“单作业多进程”与“多作业并行”的组合（例如 1 个作业 × 16 进程、2 个作业 × 16 进程、4 个作业 × 8 进程），选出整课最快的组合。
   - 你仍要遵守你自己的约束：**不影响你们的生图服务**（GPU0/2/3 的视频生成、GPU1 的 Qwen/VoxCPM）。请在回复里写出你实际设的上限、依据，以及满载时对生图服务有没有可测影响。
2. **修一个作业日志里的告警。** 用户运行验收时，静帧作业日志出现：
   `<w> [webpack.cache.PackFileCacheStrategy] Caching failed for pack: Error: EACCES: permission denied, mkdir '/srv/openmontage-render/jobs/<作业>/work/composer/node_modules/.cache/webpack/...'`
   它不致命，但说明作业目录里 `node_modules` 是只读符号链接或归属不对，webpack 缓存写不进去（每个作业都重新打包，浪费时间）。请让缓存写到作业内的可写目录（或共享一个只读安全的缓存），并告诉我们结果；做完后告警应消失。
3. **更新 `probe`。** 把 `capacity`（`max_concurrent_jobs`、`max_total_workers`、推荐每作业 workers）和 `render_profile` 写成测出的最佳值。**以后只改 `probe`，我们的调度器会自动读取，不用改我们的代码。**

## 2. 不在本轮范围
- **GPU / NVENC 先不测。** 用户还没有给 GPU 时间窗口；等用户给出后我们会另写文档。你上轮结论（`egl` 与 CPU 逐像素相同、`angle-egl`/`swangle` 约 39 dB 不达标、Vulkan 挂起）我们已记录，不用重复。
- 协议与画面一致性要求不变，沿用 v3 §3 的 A 组与附录协议；不要改协议字段名。

## 3. 协作边界（沿用 v3 §2）
只写 `docs/remote-render-replies/` 和你自己的服务；不要改本仓库其他文件（`docs/whiteboard_render.py`、`tools/video/remote_cpu_render.py`、`remotion-composer/render-tools/render_chunks.mjs` 由我们维护）。需要我们改什么，请写在回复里。

## 4. 验收（用户运行 `FULL=1 bash docs/remote-render-test.sh`，我们据实测结果判定）
| 项 | 要求 |
|---|---|
| 配额 | `probe.capacity.max_total_workers` ≥ 32，且自测包有对应的复测行 |
| 画面 | 6 张静帧逐像素相同或 PSNR ≥ 50 dB；K4 视频逐帧最低 PSNR ≥ 45 dB（与第 1 轮一致，不得退化） |
| 速度 | 整课（约 11000 帧）自动模式总用时 < 本机多进程基准的一半；第 17 课本机基准 **1594 秒**（约 26.6 分钟），即 < 约 13 分钟；并给出配额提高前后的对比 |
| 稳定性 | 满载下 `status/logs` 每 3 秒轮询零错误；生图服务无可测影响（你确认并附依据） |
| 告警 | 作业日志不再出现 webpack 缓存 `EACCES` |

## 5. 回复模板（写到 `docs/remote-render-replies/<日期>-round2.md`）
```
【授权与约束】用户已确认提到 32–48=（是）  你这边的限制（时段/优先级/其它服务）=…
【配额】max_total_workers=…  max_concurrent_jobs=…  推荐 workers/作业=…  设这个上限的依据=…
【复测结果】（附 results/bench_results.md；cpu-w16 / w24 / w32 / w48 与多作业组合；写明最佳组合及理由）
【满载稳定性】轮询零错误=（是/否，附日志）  生图服务影响=（无/有，依据）
【webpack 缓存告警】已修=（是/否）  做法=…
【probe 已更新】capacity / render_profile 的新值=…
【你对系统做过的全部改动清单】…
【其他限制或顾虑】…
```
