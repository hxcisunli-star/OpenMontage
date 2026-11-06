# OpenMontage 本地 CPU 渲染通道

更新日期：2026-10-07

本通道让 144 服务器上的 OpenMontage 把 Remotion CPU 渲染任务送到本机执行。144 不需要访问本机公网地址；本机主动建立反向 SSH，144 只看到自己的回环地址。

## 架构和边界

```text
OpenMontage（144）
  127.0.0.1:<回环端口>
      │ 144 上的 omrender-tunnel 反向 SSH
      ▼
本机 127.0.0.1:22 / openmontage-render
      │ 强制命令 + Unix socket
      ▼
openmontage-render-agent.service
      │ 单任务队列，Remotion concurrency 由 job 指定
      ▼
/srv/openmontage-render/runtime/om-20261007-remotion-v2
```

- `<回环端口>` 是 144 的回环端口，仅供本机 CPU 渲染；现有 H3 API `<H3端口>` 不变。
- 本机只开放专用 `openmontage-render` 账号。它不能取得交互 shell、端口转发、TTY、代理转发或访问本机项目、模型、GPU、图库和生产输出目录。
- 144 侧的 `omrender-tunnel` 只能建立 `127.0.0.1:<回环端口>` 这一条远程转发；不使用 `<渲染机公网地址>`。
- 输入通过安全 tar 上传到每个 job 的 `input`，输出从该 job 的 `output` 下载。所有路径由 agent 重写到 job 根目录内。

## 配置（不在仓库里）

回环端口、身份文件、known_hosts 文件的路径**没有内置默认值**，按环境变量读取：`OPENMONTAGE_RENDER_PORT`、`OPENMONTAGE_RENDER_IDENTITY`、`OPENMONTAGE_RENDER_KNOWN_HOSTS`。环境里没有时，客户端和渲染调度会读仓库根目录里不被 git 跟踪的 `.env`；两处都没有就报“未设置”，自动模式随即回退本机渲染并打印原因。新机器照此在本机的 `.env` 里填这三项即可，值不要写进仓库文档。

## 日常调用

在 144 上先确认通道：

```bash
cd /home/MyProject/OpenMontage
python3 tools/video/remote_cpu_render.py probe
```

白板课程仍由现有脚本准备素材和 props，增加 `--remote-cpu` 即把实际 Remotion 阶段交给本机：

```bash
# 先做一个或多个首帧/静帧验证
python3 docs/whiteboard_render.py projects/bubble-sort-tutorial-cn \
  --stills 2.5 --remote-cpu

# 通过 lint 后渲染所有缺失 chunk，并合成 final.mp4
python3 docs/whiteboard_render.py projects/bubble-sort-tutorial-cn \
  --final --remote-cpu
```

默认运行时是 `om-20261007-remotion-v2`。如需明确指定版本：

```bash
python3 docs/whiteboard_render.py projects/bubble-sort-tutorial-cn \
  --final --remote-cpu --remote-runtime om-20261007-remotion-v2
```

脚本会先把 props 中的媒体路径改为 staging 后的相对路径，再上传 `props.json`、`public/` 和 job JSON。完成后下载输出、复制到项目 `renders/`，并清理远端 job。失败时保留本地 staging 目录中的日志线索；远端 job 只有在成功收尾时自动清理。

## 手工排障命令

`remote_cpu_render.py` 的身份文件和主机信任文件默认位于 144 的 root SSH 目录，路径只记录在脚本默认值中，不把密钥写入项目：

```bash
python3 tools/video/remote_cpu_render.py probe
python3 tools/video/remote_cpu_render.py status JOB_ID
python3 tools/video/remote_cpu_render.py logs JOB_ID
python3 tools/video/remote_cpu_render.py cancel JOB_ID
python3 tools/video/remote_cpu_render.py download JOB_ID /tmp/openmontage-render-output
python3 tools/video/remote_cpu_render.py cleanup JOB_ID
```

取消后先查 `status`，确认状态为 `canceled` 或 `failed` 再清理。agent 当前一次只运行一个 job，后续 job 会排队；单个 job 的 Remotion `concurrency` 上限为 16，默认由白板脚本传入 4。磁盘低于 100 GiB 时新 job 会拒绝启动。

## 运行时和浏览器

当前默认 runtime：

`/srv/openmontage-render/runtime/om-20261007-remotion-v2/remotion-composer`

本机 glibc 为 2.31，runtime 自带的 Chromium 需要更高 glibc。因此运行时统一通过服务环境变量使用本机 Playwright 的兼容 headless shell：

`/opt/openmontage-render/browser/chrome-headless-shell-linux64/chrome-headless-shell`

v1 也已应用相同的 browser executable 补丁，但新任务统一使用 v2。运行时目录和浏览器目录归 `openmontage-render` 服务使用，不从本机项目树读取依赖。

## 活性限时与清理（2026-10-29 起）
2026-10-28 下午连接停顿时，样片、关键帧、整片都无声卡住过 29、15、6 分钟：上传和下载没有整体期限，读状态每次最长 120 秒还重试 4 次。现在每一步都有时限，超时就报错，`docs/whiteboard_render.py` 放弃该任务并回退本机渲染（`--remote-cpu` 则报错退出、不回退；正式制作里别默认用它）。数值依据渲染机的回执（`docs/remote-render-replies/2026-10-28-connection-stalls.md` 第二节第 6 项、`2026-10-29-client-liveness.md` 的“144 客户端待改项”）。

| 环节 | 限制 | 在哪里改 |
|---|---|---|
| ssh 握手 | 15 秒；ServerAlive 10 秒×3，约 30 秒发现断链 | `RemoteRenderClient.CONNECT_TIMEOUT`、`ALIVE_*` |
| 探测 `probe` | 单次 10 秒，总共 20 秒 | `PROBE_TIMEOUT`、`PROBE_DEADLINE` |
| 控制请求（prepare、submit、status、logs、cancel、cleanup） | 单次 30 秒，含重试总共 75 秒；只读请求最多再试两次、间隔 2 秒；prepare 和 submit 只试一次（重试可能重复提交） | `CALL_TIMEOUT`、`CALL_DEADLINE` |
| 上传 | 每 30 秒至少要走 256 KB，否则杀掉 ssh 报 `stalled`；总期限随包大小：60 秒 + 大小÷32 KiB/s，限在 120–3600 秒（**32 KiB/s 是设计值，不是实测下限**；健康时 31.8 MB 约 7 秒）；**最后一个字节写完就停止“没流量”检测**，之后只等回复，最多 120 秒 | `STALL_*`、`UPLOAD_*`、`REPLY_TIMEOUT` |
| 下载 | 同样每 30 秒至少 256 KB，第一个字节前多给 30 秒；一次最长 900 秒 | `STALL_*`、`STREAM_DEADLINE` |
| 排队（准备、上传、提交） | **分阶段**各有截止时间（准备、提交各约 80 秒，上传 = 上传总期限 + 回复 + 10 秒），哪一阶段超了就放弃；`--remote-queue-seconds` 可选，给了就再加一道整体上限；启动时先打印并记下任务号（`remote: preparing … (任务号)`，同时写进 `projects/<课程>/renders/remote_jobs.log`） | `QUEUE_STAGE_SLACK`、`--remote-queue-seconds` |
| 渲染中 | 90 秒内没有一次成功的**状态**应答，就放弃；日志读不到只提示、不取消；**不按“没有新帧”取消** | `--remote-silent-seconds` |
| 放弃后 | 每个任务有 `abort` 信号：上传、下载和重试循环看到就立刻结束；放弃后**不再 submit**；submit 应答不明时先按**原任务号**查 `status`：已排队、运行中、已完成就当作已排队继续，终态失败或 unknown 才算失败，绝不换号重交 | |

**渲染机不再自动清理（agent/6 起）。**原来的 6 小时隐式清理已撤除，一次上传最多可占 48 GiB，所以每个任务号都必须由客户端显式清掉：
- 放弃或失败的任务：`retire` = `cancel` → 等到终态（canceled、completed、failed 或 unknown job，最多约 40 秒）→ `cleanup`；`cleanup` 遇到 `busy`（上传或下载还占着锁）重试 3 次、间隔 5 秒。正常完成并装好之后只做 `cleanup`，不 cancel。
- **先记账再清理**：任务号一出生就写进 `projects/<课程>/renders/remote_pending_cleanup.json`（含属主进程号），清理成功才删；清不掉的留在里面，结束时会打印。下一次渲染开头在后台 `sweep`（对账本里的号重试），**属主进程还活着的任务不扫**（别的渲染正在用）。
- 手工：`python3 tools/video/remote_cpu_render.py retire <任务号>`（加 `--no-cancel` 表示已正常完成）、`sweep <账本文件>`；也可以单独 `cancel`、`cleanup`。

测试：`.venv/bin/python -m pytest tests/tools/test_remote_cpu_render_liveness.py tests/tools/test_whiteboard_render_remote_liveness.py`（假进程和按 agent/6 回答的假客户端，不联网，34 个）。限制与渲染机一侧的配合事项见 `docs/remote-render-support-request-20261029-client-liveness.zh-CN.md`。**真实停顿下的保护还没有在真实通道里测过**（用户决定不单独约故障注入，改为正式制作中的真实任务检测）。

## 服务检查

本机执行：

```bash
systemctl is-active openmontage-render-agent.service openmontage-render-tunnel.service
ss -ltn 'sport = :22'
```

144 执行：

```bash
ss -ltn 'sport = :<回环端口>'
python3 tools/video/remote_cpu_render.py probe
```

只重启本通道时依次重启 `openmontage-render-agent.service` 和 `openmontage-render-tunnel.service`；不要为此停止 H3、Qwen、LTX 或修改 <H3端口>。agent 重启会把当时的 `queued/running` job 标为 `failed: agent_restarted`，因此生产渲染前应确认没有活动 job。

## 验收记录

- 2026-10-07，150 帧 Remotion smoke 通过：1920×1080、H.264、5 秒；输出 SHA-256 为 `a66068045f964b498f8e0ca88947ec83e6f024c4c2f91e2fd74a10d3acd65954`。远端 job 已清理。
- 同日，真实 `bubble-sort-tutorial-cn` 静帧通过远端通道，144 输出 `projects/bubble-sort-tutorial-cn/renders/stills/t00025.png`，1920×1080 RGB，SHA-256 为 `7c7734e2434b447fa45d6dd9ed0476b41dd9a844b3212ab965030fdfbd31c53`。job 已清理。
- 静帧运行仍有既有的 `clean-professional` style playbook 路径 warning，但未阻止产物生成。当前 `bubble-sort-tutorial-cn` 的 `--final --plan` 被项目既有 lint 拦截（12 个 K1-K7 error、1 个 warning）；通道不会绕过 lint。完整课程 final 尚未在该通道跑完，不能把 smoke/静帧验收当成整片质量验收。

详细的账号、端口和主机指纹归本地项目 `SERVER_144_OPERATIONS.md`；这里不保存任何私钥、API key 或认证值。
