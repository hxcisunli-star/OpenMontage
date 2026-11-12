# 2026-10-28 连接卡顿：渲染机处理回执

作者：渲染机侧 Codex。时间均为 UTC。原求助文档已从 144 接收到渲染机，本文同步写回 144 的同相对路径。

## 处理结果

**CPU 渲染通道已恢复并完成端到端验收。** 直连 SSH 的传输路径反复退化：小请求能返回，文件上传却停顿。13:42 单纯重连后曾短暂恢复，随后复发；关闭两端 IPQoS 的对照也失败，已回退。14:04:42 将渲染专用隧道接入已有 `intl-net` 按需代理，实际选中 JP-HY2；随后连续上传、真实渲染、轮询、日志读取、下载及 manifest 校验通过。

定位范围是**直连 TCP 传输路径**，没有证据进一步指认某家运营商、路由器或具体丢包设备。没有把一次 `probe` 成功当成修好。

144 继续使用原客户端、原回环入口及原 runtime，调用参数无需更改。H3 隧道、GPU 服务、CPU 渲染 agent 均未重启；没有修改课程、素材、客户端源码或审批状态。

## 一、证据与验收

| 检查 | 结果 |
| --- | --- |
| 原直连：同一个 1 MiB 随机文件 | 上传 40 秒超时，之前 `probe` 4.508 秒成功 |
| 仅重连直连 | 同文件 4.944 秒成功；继续验收后，约 5.6 MB 素材上传再次 60 秒超时 |
| 两端 IPQoS=none 对照 | 首次 1 MiB 上传仍 40 秒超时，改动已回退 |
| 故障时发送端 TCP | `cwnd=1`、`backoff=4`、重传累计 47 段、Send-Q 54648 字节，估算发送速率 17340 bps |
| 改用代理后：连续三次 1 MiB 上传 | 3.602 / 2.744 / 2.760 秒，全部成功 |
| 单帧 | 全流程 21.856 秒，通过下载 SHA 校验 |
| 54 秒样片，65 workers × 2 tabs | 全流程 48.508 秒，通过下载 SHA 校验 |
| 190 张静帧 | 全流程 44.151 秒，通过下载 SHA 校验 |
| 重复 54 秒样片 | 全流程 53.072 秒，通过下载 SHA 校验 |

代理路径第一轮验收共 47 次协议调用，零失败；加上双任务排队补验共 60 次成功调用。计时含 prepare/upload/submit/轮询/logs/download/校验；测试强制远程执行，没有本地回退。使用既有冻结白板自测包，在回复目录下隔离输出，**不是《让AI自己拿主意，值吗？》课程的重新制作或整片验收**。

补充的双提交排队检查、完整解码及重复样片像素一致性见 [bench_results.md](2026-10-28-connection-stalls-results/proxied/results/bench_results.md)。原始证据包括 `before.json`、`after-reconnect.json`、`verification.jsonl`、`qos-none/verification.jsonl`、`proxied/verification.jsonl` 和 `proxied/media-checks.json`；失败证据保留。

## 二、按求助 §5 逐项回答

### 1. CPU / GPU 负载与推荐 worker

`other_gpu_jobs_running=true` 仅表示 NVIDIA 上存在计算进程，不等于 GPU 正在忙，更不等于 CPU 被占满。现场 H3 三个 worker 和 Qwen 常驻，四卡抽样利用率均为 0%。本地 Unix socket probe 实测约 0.156–0.259 秒，空闲 CPU 多次为 0–2%。

也确实捕获到其他交互会话中一个短时 Python 进程，在 13:50 的一秒采样中占约 64 个逻辑 CPU，随后自然退出；没有干预该会话。这证明负载会波动，不能据此追认 12:11–13:20 的全部高负载来源。故障上传复现时不需要渲染排队，CPU 高负载不足以解释本次传输停顿。

维持 `CPUQuota=9600%`、总 65 workers、最多 1 个运行 job、每 worker 2 tabs。96 核配额是上限，不是独占预留；`Nice=10` 会让其他普通优先级任务先获得 CPU，不能保证任意时刻的吞吐。本次两个 65-worker 样片均通过，没有降低画质或迁 GPU。

### 2. 反向隧道及恢复

原本的 9.9 天会话确实存在：渲染机旧 PID 3536324。当天故障窗口内没有自动重连，也没有 `remote port forwarding failed` 日志。未发现“新隧道和旧监听抢端口”的证据；实际复现的是已建立连接的吞吐退化。

最终运行方式为 `intl-net run -- ssh` 加 HTTP CONNECT ProxyCommand。代理地址和认证只由 `intl-net` 注入进程环境，helper 不读取认证目录、不打印代理 URL；仍使用原账号、公钥及固定 known_hosts，未关闭主机校验。

保活及恢复参数：`ConnectTimeout=15`、`ServerAliveInterval=30`、`ServerAliveCountMax=3`、`ExitOnForwardFailure=yes`、systemd `Restart=always` / `RestartSec=10`。断开后重新运行 `intl-net`，由其启动探测选择节点。**SSH 保活不是上传进度超时**，不能用它代替客户端的整体操作期限。

本次只在确认 agent 无 running/queued 后重建渲染隧道。没有手工杀掉 144 的无关 sshd；144 的 IPQoS 试验配置已完整恢复原 SHA。代理组件不可用时，这条通道仍会受影响；未实测强制切换到备用 VLESS 节点。

### 3. SSH 并发限制

11:30–13:30 日志中有 86 次渲染账号认证成功，未见 `MaxStartups`/throttling/drop connection 记录。渲染端 `MaxStartups=10:30:100`，专用渲染账号 `MaxSessions=1`；后者限制同一 SSH 连接上的并行 session，不是“整台机器最多一条 SSH 连接”。

三次卡住前的最后一组认证时间分别为 12:12:02/06、12:46:31/36、13:11:57–13:12:03。相应目录只有准备痕迹，没有已提交的状态文件，符合 prepare/upload 阶段失败。当前资料不足以重建当时每一个客户端调用。

### 4. 客户端被终止后的作业

原三次失败对应：

- `om-988872a22f-stills-1793189518102`
- `om-988872a22f-sample-1793191584020`
- `om-988872a22f-sample-1793193112945`

接手时三者均为空目录，无 `state/status.json`、运行作业或残留 Chrome；没有重新提交这些请求，也没有删除这些目录。

语义要区分：上传未结束通常只留下准备目录；**已经 submit 成功的渲染不会因为 SSH 或客户端退出自动取消**，必须用原 job_id 调用 `cancel` 并核验终态。取消运行任务先 SIGTERM，10 秒后仍存在则 SIGKILL。只有 prepare 的目录目前没有可供 `status/cancel` 使用的状态记录。不要把杀客户端当成取消远端任务。

### 5. 快速存活检查及可观测性

已有回环端口可以直接做 TCP 连接并读取 `SSH-2.0-` 横幅，设置 5 秒期限，不需要完整 SSH 握手。它只能证明当时转发能到 sshd，**不能证明后续上传正常或 agent 可用**。本次故障前的三次横幅检查均约 0.8–1.0 秒通过，随后上传仍失败。

没有增加新公网健康接口或 `probe` 字段。agent uptime、SSH 丢连接次数属于不同进程，直接塞进现有 probe 也不能预测上传是否会停顿。建议客户端在发起操作前打印 job_id、阶段名，上传期间打印累计字节及最近进展时间；状态与日志分别记录调用耗时和超时原因。

### 6. 超时、重试与连接复用

现客户端并非全部没有期限：`request()` 已有每次 120 秒期限及重试，`probe()` 是 30 秒 × 最多 2 次。**upload/download 的流式读写没有整体期限**，本次长时间无输出的关键缺口在这里。

建议由 144 客户端维护方落实以下改动；本次遵守目录边界，没有修改其源码：

- 握手 `ConnectTimeout=10–15` 秒；轻量 probe 总期限 10–15 秒。5 秒可作为提示性快检，但健康路径也曾需 4.5 秒，不宜仅凭一次 5 秒失败判定作业失败。
- prepare/submit/status 单次 15–30 秒；只读查询在总期限内最多重试 2 次，间隔约 2 秒。轮询 3–5 秒足够。
- 给**整个上传/下载流程**加监护，包括 tar 写入 stdin 的阶段；不能只给最后的 `communicate()` 加 timeout。先按无字节进展 30 秒、总期限结合包大小设置，并在超时后收回子进程组。
- 在 prepare 前持久化并打印 job_id。submit 返回不明时先查询原 ID；确认原任务未运行后再决定重试或本地回退，避免重复渲染。完成或失败需保存原状态证据。
- 不建议“120 秒没有帧进度就自动取消”：排队、打包和编码都可能没有帧计数变化。结合状态、日志游标、容量及持续时间判断。
- 可以试串行 ControlMaster/ControlPersist 减少握手，但 `MaxSessions=1` 下不能在同一连接并行做 upload/status。复用不能修复底层传输退化，先完成上述期限和对账机制。

## 三、v3 模板补充

| 项 | 本次结论 |
| --- | --- |
| 授权与约束 | 用户授权故障处理；只改渲染通道与指定回复目录，GPU 分工和 9600% 配额不变 |
| A1 字体 | 沿用既有隔离环境；静帧成功，未重新做全部字体专项测试 |
| A2 源码覆盖 | 实际返回 `source_overlay=true`；lock SHA 匹配；TasksMax 65536，不改 runtime |
| A3 probe | 沿用 agent/5 协议与 v6 容量配置；完整结果附后，未新增字段 |
| A4/A5/A6 | offset 日志、manifest 实测通过；队列上限 16、运行并发 1；取消/6 小时自动保留机制未改，本次未做取消故障注入 |
| A7 | 本轮解决连接/上传停顿；未重跑旧 A7 故障注入或满载 10 分钟专项 |
| B3/B4 | CPU 渲染，gl=null、hardwareAcceleration=disabled；未启用 Chrome GPU 或 NVENC |
| B5 | 总 65 workers、单 job、2 tabs；没有新增 CPU 独占预留 |
| B6 | 见本轮 bench_results；本轮不是重新选择容量配置的性能调优 |

## 四、全部改动清单

渲染机：

1. 新增 `remote_render/ssh_http_proxy.py`，安装到 `/opt/openmontage-render/ssh_http_proxy.py`，root:root 0755。二进制双向传输/EOF、代理认证及错误脱敏测试通过。
2. 更新源模板及 `/etc/systemd/system/openmontage-render-tunnel.service`，接入 `intl-net` 与 helper；增加用户 bus/runtime 环境及代理状态目录写权限，保持其他沙箱约束。安装前 systemd 校验通过，安装后源/运行文件 SHA 一致。最终 tunnel PID 2026153；agent PID 2307 未变。
3. 原始直连 unit 备份：`/etc/systemd/system/openmontage-render-tunnel.service.bak-20261028T135714Z`；IPQoS 试验 unit 另有 `...bak-20261028T140442Z`，后者不是推荐恢复目标。
4. 新增 helper 测试与本轮隔离验收脚本/证据，保存求助原文及回执副本；更新 `SERVER_144_OPERATIONS.md`、`remote_render/README.md` 和 `PROJECT_HANDOFF.md` 索引。

144：

1. 只在 `docs/remote-render-replies/` 新增回执、隔离输入、验收脚本、日志、下载结果及 bench_results。
2. 对渲染专用 SSH 配置短暂测试 IPQoS，经过 `sshd -t`、限定账号有效配置检查和 reload；试验失败后恢复原文件，SHA 为 `7ebab3f034a0b79f215a8418a7a92c599bbf4facd339805558caa589b7449b1d`，无最终内容改动。备份为 `/etc/ssh/sshd_config.d/61-openmontage-render.conf.bak-20261028T135657Z`。
3. 未修改其他仓库文件，未调用 cleanup，未提交或推送 Git。

部署 SHA：helper `015e27ef8869e8d8e3beb9c4c3f711785a6a6f3a53ed5d08295d6bccfe6fa6cf`；unit `41b488d91e8f7ce353f3bec0b8d47345d465781a2c8d2a797657271b6a1a4d6b`。

## 五、完整最终 probe

```json
{
  "ok": true,
  "agent": "openmontage-render-agent/5",
  "socket": "/run/openmontage-render/agent.sock",
  "root": "/srv/openmontage-render",
  "node": "/usr/bin/node",
  "runtimes": [
    "om-20261007-remotion-v1",
    "om-20261007-remotion-v2"
  ],
  "running": [],
  "queued": 0,
  "features": [
    "src_overlay",
    "fontconfig_self_managed",
    "manifest",
    "log_offset",
    "multi_queue"
  ],
  "chrome_version": "Google Chrome for Testing 143.0.7499.4",
  "runtime_lock_sha256": "6fe7b19a85562ef0e927a0d196265ffd203059fa97ad9c69d54f5198b65f65d2",
  "render_profile": {
    "gl": null,
    "chromeMode": "headless-shell",
    "tabs": 2,
    "hardwareAcceleration": "disabled",
    "videoBitrate": null,
    "x264Preset": null,
    "jpegQuality": null,
    "restartEvery": null
  },
  "capacity": {
    "max_concurrent_jobs": 1,
    "max_total_workers": 65,
    "recommended_workers_per_job": 65
  },
  "load": {
    "cpu_busy_percent": 0,
    "mem_free_mb": 132895,
    "gpu_busy_percent": 0,
    "other_gpu_jobs_running": true,
    "active_workers": 0
  },
  "limits": {
    "max_queue": 16,
    "max_job_seconds": 28800,
    "cpu_quota_cores": 96.0
  },
  "runtime_settings": {
    "tmp_mode": "disk",
    "ffmpeg_threads": "auto"
  },
  "max_concurrent": 1,
  "max_concurrency": 16,
  "free_bytes": 410295959552,
  "min_free_bytes": 107374182400
}
```

## 后续边界

可以在原课程继续进行既有审批范围内的远程关键帧和样片复测。该课程的整片合成、内容质量验收和客户端源码的超时改造仍由 144 侧继续处理；本回执没有代替其制作审批。代理路径已经过持续实际传输和渲染验证，未验证数天持续运行或强制代理故障切换。
