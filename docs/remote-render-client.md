# OpenMontage 本地 CPU 渲染通道

更新日期：2026-10-07

本通道让 144 服务器上的 OpenMontage 把 Remotion CPU 渲染任务送到本机执行。144 不需要访问本机公网地址；本机主动建立反向 SSH，144 只看到自己的回环地址。

## 架构和边界

```text
OpenMontage（144）
  127.0.0.1:17865
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

- `17865` 是 144 的回环端口，仅供本机 CPU 渲染；现有 H3 API `17864` 不变。
- 本机只开放专用 `openmontage-render` 账号。它不能取得交互 shell、端口转发、TTY、代理转发或访问本机项目、模型、GPU、图库和生产输出目录。
- 144 侧的 `omrender-tunnel` 只能建立 `127.0.0.1:17865` 这一条远程转发；不使用 `38.125.160.100`。
- 输入通过安全 tar 上传到每个 job 的 `input`，输出从该 job 的 `output` 下载。所有路径由 agent 重写到 job 根目录内。

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

## 服务检查

本机执行：

```bash
systemctl is-active openmontage-render-agent.service openmontage-render-tunnel.service
ss -ltn 'sport = :22'
```

144 执行：

```bash
ss -ltn 'sport = :17865'
python3 tools/video/remote_cpu_render.py probe
```

只重启本通道时依次重启 `openmontage-render-agent.service` 和 `openmontage-render-tunnel.service`；不要为此停止 H3、Qwen、LTX 或修改 17864。agent 重启会把当时的 `queued/running` job 标为 `failed: agent_restarted`，因此生产渲染前应确认没有活动 job。

## 验收记录

- 2026-10-07，150 帧 Remotion smoke 通过：1920×1080、H.264、5 秒；输出 SHA-256 为 `a66068045f964b498f8e0ca88947ec83e6f024c4c2f91e2fd74a10d3acd65954`。远端 job 已清理。
- 同日，真实 `bubble-sort-tutorial-cn` 静帧通过远端通道，144 输出 `projects/bubble-sort-tutorial-cn/renders/stills/t00025.png`，1920×1080 RGB，SHA-256 为 `7c7734e2434b447fa45d6dd9ed0476b41dd9a844b3212ab965030fdfbd31c53`。job 已清理。
- 静帧运行仍有既有的 `clean-professional` style playbook 路径 warning，但未阻止产物生成。当前 `bubble-sort-tutorial-cn` 的 `--final --plan` 被项目既有 lint 拦截（12 个 K1-K7 error、1 个 warning）；通道不会绕过 lint。完整课程 final 尚未在该通道跑完，不能把 smoke/静帧验收当成整片质量验收。

详细的账号、端口和主机指纹归本地项目 `SERVER_144_OPERATIONS.md`；这里不保存任何私钥、API key 或认证值。
