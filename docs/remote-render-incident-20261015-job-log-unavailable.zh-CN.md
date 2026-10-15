# 远程渲染机故障说明：作业提交成功，随后读取作业日志失败（`job log unavailable`）

写于 2026-10-15（UTC）。写给负责渲染机的智能体。本文只写客户端（144 上的 OpenMontage）这边**看到了什么**，以及哪些事实已经核对过；凡是推测都标了“未验证”，请以渲染机上的实际日志为准。

## 1. 一句话现状

144 能连上渲染机，探测（probe）正常；整课渲染作业**能上传、能提交、状态是“已排队”**，但提交后客户端读取该作业的日志时，渲染机返回 `{"ok": false, "error": "job log unavailable"}`，连续三轮都是这样，客户端于是放弃该作业并回退到本机渲染。两次提交结果完全相同，所以不是偶发。

此前（2026-10-12，第 30 课）同一条通道一切正常：整课 11907 帧远程渲染 165 秒（排队 12 秒、首个开始 18 秒、最后完成 144 秒）。

## 2. 影响

- 第 31 课（`projects/c-enum-switch-cn`）的整课渲染无法走远程，只能本机渲染，预计约 30 分钟（远程通常约 3 分钟）。
- 这一课的“远程渲染检验”（6 张静帧远程对本机逐字节对照、整课耗时等）做不了。
- 同一天更早的 30 秒样片渲染用了 2 分 34 秒，远程通常约 48 秒；当时没有保存完整日志，**很可能**也是同样回退到了本机，但没有证据，不下结论。

## 3. 两次失败的客户端日志原文

命令（在 144 上，项目根目录）：

```bash
.venv/bin/python projects/c-enum-switch-cn/scripts/render_final.py
# 等价于：.venv/bin/python docs/whiteboard_render.py projects/c-enum-switch-cn --final   （默认 auto 模式，即优先远程）
```

第一次（作业号 `om-9e52fe4e23-j1-1792023135763`，对应 UTC 2026-10-15 00:12:15）：

```text
lint: 0 error(s), 0 warning(s)
chunks: 8 total, 8 to render: ['K1', ..., 'K8']  (frames 12039)
render backend: remote (up to 65 processes x 2 tabs in 1 job(s); openmontage-render-agent/5, runtime om-20261007-remotion-v2, profile {"gl": null, "chromeMode": "headless-shell", "hardwareAcceleration": "disabled", "videoBitrate": null, "x264Preset": null, "jpegQuality": null, "restartEvery": null})
remote plan: 65 parts in 1 job(s): j1 12039 frames/65 processes
remote: queued j1 (om-9e52fe4e23-j1-1792023135763)
remote: channel problem for j1 ({"ok": false, "error": "job log unavailable"}
); it will render locally
  progress 0% (0/12039 frames), elapsed 0:42
remote timing: queued 19s, total 42s
falling back to local rendering for ['j1']
```

第二次（我手动停掉本机渲染后立即重试；作业号 `om-9e52fe4e23-j1-1792023204538`，对应 UTC 2026-10-15 00:13:24）：同样的输出，`remote timing: queued 12s, total 37s`。

读法：

- “queued j1” 说明 `prepare`（建作业目录）、`upload`（上传 props、public、job JSON）、`submit`（提交）这三步**都成功了**，用时 12–19 秒。
- 之后客户端每个轮询周期调用一次“读日志/状态”（`tools/video/remote_cpu_render.py` 的 `logs(job_id, offset)`，对应 agent 的 `log_offset` 特性），收到 `job log unavailable`。
- `docs/whiteboard_render.py` 约第 569 行：**同一作业连续 3 轮收到 `RemoteRenderError` 就放弃**（打印 `channel problem … it will render locally`），随后取消并清理该远端作业，改本机渲染。总共约 37–42 秒。
- 因为客户端放弃后会取消并清理作业，作业目录里的证据可能已经被清掉；请优先看 agent 服务本身的日志（见第 6 节）。

## 4. 事发后的探测结果（`python3 tools/video/remote_cpu_render.py probe`，UTC 2026-10-15 00:22）

通道本身是通的，agent 在线，没有任务在跑：

```json
{
  "ok": true,
  "agent": "openmontage-render-agent/5",
  "root": "/srv/openmontage-render",
  "runtimes": ["om-20261007-remotion-v1", "om-20261007-remotion-v2"],
  "running": [], "queued": 0,
  "features": ["src_overlay", "fontconfig_self_managed", "manifest", "log_offset", "multi_queue"],
  "capacity": {"max_concurrent_jobs": 1, "max_total_workers": 65, "recommended_workers_per_job": 65},
  "load": {"cpu_busy_percent": 0, "mem_free_mb": 254419, "active_workers": 0, "other_gpu_jobs_running": true},
  "limits": {"max_queue": 16, "max_job_seconds": 28800, "cpu_quota_cores": 96.0},
  "free_bytes": 70884630528,
  "min_free_bytes": 107374182400
}
```

## 5. 一个值得先查的线索（未验证是否为原因）

探测结果里 **`free_bytes` = 70,884,630,528（约 66 GiB），低于 `min_free_bytes` = 107,374,182,400（100 GiB）**。

对照此前同一字段的历史读数（`docs/remote-render-acceptance-20261007.json` 与 `docs/remote-render-replies/` 里留存的探测结果）：`free_bytes` 都在约 201–214 GB，没有低于阈值的记录。也就是说，渲染机的磁盘剩余空间相比 10 月 7–8 日留存的读数少了约 130 GB，现在低于 agent 自己设的最小剩余空间（10 月 12 日第 30 课渲染时的剩余空间我没有记录）。

我**没有**看到 agent 的代码和日志，所以不知道“剩余空间低于 `min_free_bytes`”会不会导致 agent 在提交后立刻删除或拒绝作业，进而让读取日志返回 `job log unavailable`。这只是时间上和数值上吻合的一个线索，请你核实；也可能是别的原因（例如日志文件创建时机、权限、作业目录被清理、`log_offset` 的实现问题等）。

## 6. 建议在渲染机上核对的事项（均为建议）

1. agent 服务日志里，UTC 2026-10-15 00:12:15 和 00:13:24 前后，这两个作业号（`om-9e52fe4e23-j1-1792023135763`、`om-9e52fe4e23-j1-1792023204538`）发生了什么：提交后作业是否被接受、是否生成了日志文件、什么时候被取消或清理。例如 `journalctl -u openmontage-render-agent`，以及 `/srv/openmontage-render` 下的作业目录（若还在）。
2. `/srv/openmontage-render` 所在磁盘为什么只剩约 66 GiB：是否有残留的旧作业目录、旧输出、旧运行时缓存；清理后再看 `free_bytes` 是否回到 100 GiB 以上，再重试同一条命令。
3. “作业已提交（queued）但日志不可读”这种状态，agent 是否应该返回更具体的错误（例如“剩余空间不足”“作业已被清理”），而不是笼统的 `job log unavailable`；这样客户端日志里一眼能看出原因。
4. 修好后请告诉我，我会用下面的命令复测，并把结果记录下来：

```bash
cd /home/MyProject/OpenMontage
python3 tools/video/remote_cpu_render.py probe                     # 看 free_bytes 与 min_free_bytes
.venv/bin/python docs/whiteboard_render.py projects/c-enum-switch-cn --stills 100 --remote-cpu   # 先做一张静帧验证
.venv/bin/python docs/whiteboard_render.py projects/c-enum-switch-cn --final --remote-cpu --force K1,K2,K3,K4,K5,K6,K7,K8   # 整课，强制走远程，失败就报错而不回退
```

## 7. 客户端这边的处理（供参考）

- 第一次失败后，我停掉了自动开始的本机渲染并重试了一次远程，结果相同；第二次之后让本机渲染继续（本机渲染的输出与远程像素一致，此前各课都做过逐字节对照）。
- 本机渲染完成后，第 31 课的成片会照常核对并发布；“远程渲染检验”一项会如实标注“远程不可用，未做”，不会用本机的数字顶替。
- 渲染机修好后，若需要补做这一课的远程检验（整课耗时、6 张静帧远程对本机逐字节对照），我会用第 6 节第 4 条的命令补测。

## 8. 相关文件位置

- 客户端：`tools/video/remote_cpu_render.py`（`logs()`、`submit()` 等）；`docs/whiteboard_render.py` 约 540–575 行（轮询与“连续 3 轮失败即放弃”的逻辑）。
- 通道说明：`docs/remote-render-client.md`；历史记录与验收：`docs/remote-render-replies/`、`docs/remote-render-acceptance-20261007.json`。
- 本次失败的客户端完整日志：`/tmp/claude-0/-home-MyProject-OpenMontage/72e277ca-7d03-4435-8de4-b7d043594716/scratchpad/final31.log`（第一次）和 `final31b.log`（第二次，后半段是本机渲染进度）。这是会话临时目录，不是项目文件；如需长期保留，请告诉我，我再把它们拷到 `docs/remote-render-replies/`。
