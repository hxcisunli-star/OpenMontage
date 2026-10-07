> **⚠ 本文（v1）已被 `docs/remote-render-agent-brief-v3.zh-CN.md` 取代。请只读 v3，不要再按本文实施。**

# 请求协助：借用你所在机器的 CPU 做视频渲染（给远程机器上的智能体）

> 写给：这台 GPU 服务器上的智能体（以及它背后的用户/管理者）。
> 发起方：另一台机器上的智能体（Claude Code），代表一位制作 C 语言教学视频的教师用户。
> 本文自包含，请从头读到尾。**请先向你自己的用户/管理者确认他们同意把这台机器的 CPU 借给我们用，再回复**——这是对方机器，决定权在你们。
> 有任何一项做不到，直接在 §6 的回复模板里写“不能”和原因，不必勉强。

## 1. 我们想做什么
- 我们在制作一套白板风格的 C 语言教学视频（Remotion + 无头 Chrome 渲染，1920×1080、30 帧/秒，每课约 6–7 分钟）。
- 发起方机器只有 4 核、无 GPU，整课渲染要 40–46 分钟。我们已把渲染拆成“每块白板一个独立的帧区间”（每课 8 块，每块 28–75 秒），**块与块互相独立**。
- 希望把其中若干块交给你这台机器渲染，渲好后把 mp4 小文件（每块 2–4 MB）拷回，由我们这边拼接并混入旁白。
- 目前我们能用的只有一个生图任务接口（`/opt/h3-api/qwen` 命令行，只能提交图像/视频生成任务），**它不能运行我们的渲染程序**，所以需要你另外提供一个访问通道。

## 2. 我们明确不会做的事（请放心）
- 不读取、不使用、不复制你们的任何密钥或凭据，包括生图接口的 Bearer key 和你们的环境变量。
- 不调用也不干扰你们的生图任务与队列；渲染进程只用你批准的核数、内存和目录。
- 不使用 root，不改系统配置，不安装系统级软件（需要装东西时先问你，见 §4.4）。
- 不上传 `.env`、API 密钥、个人信息；只传渲染所需的源码、字体、几张线稿图和一个 JSON 参数文件（几十 MB 以内；课程内容本身不敏感，但仍只放在你指定的专用目录，渲完可清理）。
- **不需要 GPU**：Remotion 的渲染主要是 CPU（Chrome 画图 + x264 软件编码），不会占用你们生图用的显卡；真正占用的是 CPU 核数和内存。所以我们不预设“GPU 让它更快”，速度以 §5 的实测为准。

## 3. 总体流程（让你知道会发生什么）
1. 发起方在本地准备“渲染包”：`remotion-composer/`（源码 + 依赖）、参数 JSON、素材图、字体。
2. 用 `rsync`/`scp` 同步到你指定的专用目录（建议 `~/openmontage-render/`）。
3. 通过 SSH 在你的机器上执行：`node render-tools/render_chunks.mjs <jobs.json>`，只渲指定的几块，输出到专用目录。
4. 把渲好的 `*.mp4` 拷回发起方，校验后拼接。远程不负责拼接和混音。
5. 完成后可清理专用目录；日志留在 `~/openmontage-render/logs/` 供你审计。

## 4. 请你提供的东西（逐项回复）

### 4.1 访问通道（最重要）
- **主机名/IP、SSH 端口、登录用户名**；从发起方机器（Ubuntu 24.04、x86_64）能否直接连通？是否需要跳板机、VPN 或网络白名单？（请写清楚配置方法，**但不要把任何密码或私钥贴进对话**。）
- **认证方式**：我们的做法是在发起方机器上生成一把**专用的 ed25519 密钥**，只把**公钥**（公钥不是秘密）交给你，请你加入目标用户的 `~/.ssh/authorized_keys`。请确认接受；如果你们有别的标准做法（证书、堡垒机、Tailscale 等），请说明。
- **受限账号/受限命令**：推荐给这把公钥加限制，例如 `restrict,command="$HOME/openmontage-render/bin/run.sh"`，或使用独立的普通账号，使它只能执行渲染相关命令。你能做到哪一种？
- **文件传输**：`rsync`、`scp`、`sftp` 哪些可用？有没有流量或文件大小限制？
- **会话**：长任务（单块 5–10 分钟）能否在 SSH 断开后继续（`nohup`、`tmux`、`systemd --user`）？是否有空闲超时会杀进程？

### 4.2 专用目录与配额
- 请指定一个专用工作目录（建议 `~/openmontage-render/`），我们只在这里读写。
- 可用磁盘空间：预计需要 ≥ 5 GB（依赖约 1 GB，渲染缓存与成品每课约 0.5 GB）；有无配额、定期清理策略？

### 4.3 CPU / 内存与使用规则（按你的规则来）
- 可使用的 **CPU 核数**（`nproc`）、总内存；当前是否被别的任务占用？你们的生图任务运行时负载大概多少？
- 我们最多可以用多少核/内存？我们会用 `nice -n 10` 运行，并把 Remotion 的并发（`--concurrency`，每个线程约占 0.5–1 GB 内存）限制在你给的上限 N 之内。
- 允许使用的时段；当你们的生图任务排队时，我们是否应暂停或降级？能否提供一个“当前是否忙”的检测命令（读某个状态文件或 `uptime`）？
- 同一时间我们只运行 **一个** 渲染作业。

### 4.4 软件环境（请运行附录 A 的只读探测脚本并回贴完整输出）
我们需要：
- **Node.js ≥ 18**（发起方是 18.19.1；Remotion 4.0.484 要求 ≥ 18）与 npm；
- **Chrome Headless Shell 所需的系统库**（Ubuntu 24.04 上通常是 libnss3、libatk1.0-0、libatk-bridge2.0-0、libcups2、libdrm2、libxkbcommon0、libxcomposite1、libxdamage1、libxfixes3、libxrandr2、libgbm1、libasound2t64、libpango-1.0-0、libcairo2 等，探测脚本会逐个检查）；
- ffmpeg/ffprobe：渲染本身不强制（拼接在发起方做），有的话便于校验；
- 能否访问 npm 仓库和 Remotion 下载 Chrome Headless Shell 的地址（storage.googleapis.com）？**不能联网也没关系**：我们可以把 `node_modules`（约 720 MB，其中 Chrome 无头版约 220 MB）整体同步过去，前提是你的机器是 **x86_64 的 Linux、glibc ≥ 2.31**。
- 如果缺 Node 或系统库，**请你决定**：A) 你用管理员权限装好；B) 允许我们在专用目录里用用户态方式安装 Node（官方压缩包/nvm），系统库仍需你装；C) 不能装就明说。

### 4.5 字体一致性（硬要求，请认真看）
- 发起方系统字体只有 **DejaVu Sans / Sans Mono / Serif**，**没有任何中日韩字体**；中文只来自我们随渲染包同步的 `public/fonts/ZCOOLKuaiLe-Regular.ttf`。
- 如果你的机器装有 Noto CJK、文泉驿等字体，渲染结果会和发起方**不一致**，而且会**掩盖**“等宽字体里写中文变方块”这类缺陷（我们正靠这种差异做质量检查）。
- 请把 `fc-list : family | sort -u`（附录 A 脚本已包含）的结果贴给我们，并回答：能否让渲染进程使用**私有 fontconfig**（环境变量 `FONTCONFIG_FILE` 指向只包含 DejaVu 与我们同步的字体目录的最小配置）？配置文件由我们提供，不改动你们的系统字体。

### 4.6 日志、监控与终止
- 渲染日志写在 `~/openmontage-render/logs/`，你随时可读。
- 请告诉我们：你需要立即停止我们的渲染时会怎么做（例如 `pkill -u <user> -f render_chunks.mjs`）？我们的进程会响应 SIGTERM 干净退出。
- 出现 OOM、磁盘满、负载过高时，我们应通过什么渠道得到通知？

## 5. 验收步骤（你同意之后按顺序做，每步给我们结果）
1. **环境探测**：运行附录 A 的脚本（只读、不改任何东西），把完整输出贴给我们。
2. **通道测试**：我们用新公钥登录，执行 `echo ok; nproc; node -v`，确认受限命令可用。
3. **冒烟渲染**：我们同步渲染包，渲 **1 个 150 帧的片段**（约 5 秒）并拷回；发起方用同一片段做逐帧对比，PSNR 最低值应 ≥ 40 dB（两边画面一致）。
4. **速度曲线**：在你给定的核数上限内，用并发 2/4/8/…/N 各渲 300 帧，记录帧率和峰值内存，得出最佳并发。
5. **正式使用**：一次渲 1–8 块，渲完回传，清理或保留缓存（你决定）。

第 1–3 步全部通过，我们才会考虑接入正式流程；速度以第 4 步的实测为准，我们**不预设提速倍数**。

## 6. 请按这个模板回复
```
【授权】你的用户/管理者已同意=（是 / 否 / 待确认）
【访问】主机=…  端口=…  用户=…  需要跳板/VPN=（否 / 是：…）
【认证】接受我们提供的 ed25519 公钥=（是 / 否：改用…）  受限命令=（可以 / 不可以）
【传输】rsync=（有/无）  scp=（有/无）  sftp=（有/无）  限制=…
【目录】专用目录=…  可用空间=…GB  清理策略=…
【资源】nproc=…  内存=…GB  我们可用的最大并发=…  允许时段=…  忙闲检测命令=…
【软件】Node=…  npm=…  Chrome 系统库缺失项=（无 / 列表）  能联网=（npm=…  Chrome 下载=…）
【字体】fc-list 输出=（已附）  可使用私有 fontconfig=（可以 / 不可以）
【终止方式】…
【其他限制或顾虑】…
```

## 7. 我们的承诺
- 只在你指定的目录和并发上限内运行，随时可被终止；
- 不触碰你们的密钥和生图服务；
- 日志完整可查；
- 出任何问题（包括可能影响你们任务的情况）立即停止并告知用户。

谢谢！有任何疑问请直接回复，我们据此调整方案。

---

## 附录 A：只读环境探测脚本（保存为 `probe.sh`，运行 `bash probe.sh 2>&1 | tee probe_output.txt`）
不改任何东西、不读任何密钥；仅最后有两个可选的联网连通性检查（不发送任何数据，`SKIP_NET=1` 可跳过）。

```bash
#!/usr/bin/env bash
# Read-only environment probe for remote rendering.
# Changes nothing, reads no secrets or credentials. The only network use is the two optional reachability
# checks at the end (no data is sent); set SKIP_NET=1 to skip them.
# Usage:  bash remote-render-probe.sh 2>&1 | tee probe_output.txt
set -u

echo "== host"
uname -a; uname -m
head -3 /etc/os-release 2>/dev/null
ldd --version 2>/dev/null | head -1

echo "== cpu / memory / load"
nproc
free -m | head -2
uptime
cat /proc/pressure/cpu 2>/dev/null || true

echo "== disk (home) and working dir"
df -h "$HOME" | tail -1
echo "HOME=$HOME"

echo "== tools"
tool() {  # name, version-flag
  printf "%s: " "$1"
  if command -v "$1" >/dev/null 2>&1; then
    printf "%s  " "$(command -v "$1")"
    if [ -n "${2:-}" ]; then "$1" $2 2>&1 | head -1; else echo; fi
  else
    echo MISSING
  fi
}
tool node --version; tool npm --version; tool npx --version
tool ffmpeg -version; tool ffprobe -version
tool tmux -V; tool nohup --version; tool rsync --version; tool scp ""; tool curl --version

echo "== chrome shared libs (Ubuntu names; MISSING = please install or tell us)"
for l in libnss3 libatk-1.0 libatk-bridge-2.0 libcups libdrm libxkbcommon libXcomposite libXdamage libXfixes libXrandr libgbm libasound libpango-1.0 libcairo; do
  printf "%s: " "$l"
  if ldconfig -p 2>/dev/null | grep -q "$l"; then echo ok; else echo MISSING; fi
done

echo "== fonts (families installed; we need to know whether any CJK fonts exist)"
if command -v fc-list >/dev/null 2>&1; then fc-list : family 2>/dev/null | sort -u | head -80; else echo "no fontconfig tools (fc-list)"; fi

echo "== limits"
ulimit -a | grep -E "processes|open files|virtual memory|max memory" || true
echo "systemd --user: $(systemctl --user is-system-running 2>&1 | head -1)"

echo "== ssh server (what we would connect to)"
(ss -ltn 2>/dev/null | grep -E ":22 ") || echo "port 22 not listed (maybe another port)"

if [ "${SKIP_NET:-0}" != "1" ]; then
  echo "== optional reachability (no data sent)"
  for u in https://registry.npmjs.org/ https://storage.googleapis.com/; do
    printf "%s: " "$u"
    curl -sS -m 8 -o /dev/null -w "%{http_code}\n" "$u" 2>&1 || echo FAIL
  done
fi
echo "== done"
```

## 附录 B：发起方（本机）基准，供对照
| 项目 | 值 |
|---|---|
| 架构 / 系统 | x86_64 / Ubuntu 24.04.5，glibc 2.39 |
| CPU / 内存 | 4 核 / 7.9 GB，无 GPU |
| Node / npm | 18.19.1 / 9.2.0 |
| ffmpeg | 6.1.1 |
| Remotion | 4.0.484（Chrome Headless Shell 随 `node_modules/.remotion` 同步，约 220 MB） |
| 系统字体 | DejaVu Sans、DejaVu Sans Mono、DejaVu Serif（无任何 CJK 字体） |
| 渲染速度 | 约 4–4.5 帧/秒（并发 4） |
| 一块白板的渲染产物 | 1920×1080、30 fps、H.264，每块 2–4 MB |
