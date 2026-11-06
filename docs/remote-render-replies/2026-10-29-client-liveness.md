# 2026-10-29 客户端活性限时：渲染机处理回执

作者：渲染机侧 Codex。时间默认 UTC。已接收144的求助原文；本回执及证据同步回144同相对路径。承接 [10-28通道修复](2026-10-28-connection-stalls.md)。

**必要修复已部署为 `openmontage-render-agent/6`。27项隔离测试、三轮真实通道上传/渲染/下载，以及Chrome启动后的正常取消均通过。** 原客户端协议和runtime继续可用。A/B/C故障注入尚未执行，下面先给安全实施方案。

需要144侧继续修正两件事：取消后等待终态再清理；放宽把上传也算进去的120秒限制。客户端代码本轮未改，不能把这份回执理解为“1–2分钟退出和所有故障分支已经实测通过”。

## Q1：上传被掐断后，目录与清理行为

当前部署版本的实际返回如下；错误由SSH包装器返回 `ok:false` 和非零退出码，客户端会抛异常。

| 情况 | status | cancel | cleanup |
| --- | --- | --- | --- |
| 只做prepare | `unknown job` | `unknown job` | 成功，`state:removed`，删除准备目录 |
| 上传一半，接收进程已退出 | `unknown job` | `unknown job` | 成功，删除输入及`.upload-*`残留 |
| 上传仍占用任务锁 | `unknown job` | `unknown job` | `job busy: transfer or mutation in progress`，保留目录 |
| 从未存在的ID | `unknown job` | `unknown job` | 成功，`state:removed`，`cleanup_audit:null` |
| 已完成且已清理 | `unknown job` | `unknown job` | 再次成功，`state:removed`，`cleanup_audit:null` |

旧版其实能够删除prepare/部分上传目录；缺陷是没有与上传接收端互斥，可能边写边删，且重复清理不存在的目录会报错。本轮增加跨进程任务锁：上传持独占锁，下载持共享锁，submit/cleanup持独占锁；冲突立即返回busy，不在agent内长期等待。锁文件在job目录之外，删除job不会造成两把锁同时存在。

客户端杀掉本地SSH，并不保证远端接收进程在同一瞬间退出。收到busy后应等待、重试并记下待清理ID；`unknown job`只说明没有submit状态文件，不能证明接收端已经退出。没有新增prepared状态；保留明确的unknown语义。

半包可能留下准备目录和`.upload-*`暂存文件。一次上传最多接受48GiB文件内容、20,000个tar成员，**不是最多几MB**；中断处还可能有尚未写入文件的缓冲数据。重传会保留旧输入备份到显式cleanup，因此多次失败/重传的累计占用没有“单包48GiB”这个总上限。

**不设置自动删除期限。** 本轮取消原来的6小时隐式清理，并停止在取消、状态查询、恢复、上传失败时递归删除数据。只有显式cleanup会删除：先排除活动任务及传输，冻结逐文件清单，记录符号链接真实目标和文件身份，完整预演核对，再逐文件unlink/rmdir；不跟随链接删除runtime或其他来源。审计保存在job外的`cleanup-audit/`。取消后的输入、输出和scratch均保留，磁盘需由明确的清理请求回收；旧客户端“agent会自己清理”的注释已经不成立。

## Q2：submit回复丢失、取消与进程回收

submit可能已经入队，即使应答丢失也继续运行。先用**原ID查询并对账**，不要换ID重交。现在对任何已有提交状态（queued/running/canceling/completed/failed/canceled），重复submit都在写入配置前拒绝，报`job already submitted; query the original job`；不存在的job不会因submit被重新创建。不要复用已清理ID承接迟到请求。

| cancel目标状态 | 返回及效果 |
| --- | --- |
| queued | 立即变为`canceled`，`pid:null`，移出等待队列；重复调用返回同一终态 |
| running | 先返回`canceling`；发SIGTERM，10秒后仍有进程则SIGKILL；确认进程组退出才记`canceled`、`pid:null` |
| canceling | 仍返回`canceling`，不会重复启动终止线程 |
| completed / failed / canceled | 保持原终态，不重新运行、不删除输出 |
| 不存在 / prepare-only / 已清理 | `ok:false,error:unknown job`；副作用幂等，但不是“每次都返回成功” |

cleanup拒绝queued、running、canceling，以及仍被agent跟踪的进程。**cancel成功不等于cleanup已经安全。** 正确顺序是取消→有界轮询终态→保存状态/日志→cleanup；busy或通道不通时留下待清理账目，不吞掉错误后宣称完成。

排队取消与worker启动受同一把agent锁保护：取消先取得锁就不会启动worker；启动先发生，则按运行取消处理。隔离测试验证了排队取消不调用进程启动。原版“父进程先退出就停止升级”的问题已修复，终止逻辑会检查仍存活的进程组。测试中的子进程忽略SIGTERM、父进程先退出，仍会被SIGKILL回收。

真实通道还验证了启动阶段取消，以及Chrome已经运行后的取消；后者现场观察到浏览器进程，终态`canceled`时关联Node/Chrome进程为零。诊断目录按新规则保留，**没有把“无进程”写成“目录已删”**。极端不可杀的进程不会被伪报终态，保持canceling并报告`process_group_still_running`，需要现场处理；进程组外且自行脱离运行时管理的自定义子程序不在本次保证内。

服务重启通过systemd管理整个服务cgroup。启动恢复现在把queued/running/canceling均标为`failed,error:agent_restarted,pid:null`，保留输入和产物，不自动续跑或重交。本轮部署时为空队列；运行中重启的真实通道验收留在C项。

## Q3：包大小、吞吐与阈值

完整计时、哈希及口径见 [results/bench_results.md](2026-10-29-client-liveness-results/results/bench_results.md)。此次使用现有课程的真实输入副本，保持源码覆盖、字体、public素材，改副本任务为100/200/300秒三张静帧，没有修改或重制课程。

| 项目 | 字节数 / 实测时间 |
| --- | --- |
| 原课程单任务输入快照 | 97个文件，31,787,621字节 |
| 本轮三静帧任务输入 | 31,784,405字节；tar为31,979,520字节 |
| 三轮上传（含握手与应答） | 7.200 / 7.277 / 7.301秒；有效4.152–4.210MiB/s |
| prepare+upload+submit | 12.087 / 12.650 / 12.224秒 |
| 三张PNG | 459,091 / 468,892 / 549,460字节 |
| 本轮下载总内容（含manifest等） | 1,478,124字节；3.278 / 3.283 / 3.428秒 |
| 下载首字节（含握手） | 2.403 / 2.410 / 2.559秒 |
| 三轮全流程 | 29.123 / 29.539 / 29.254秒；产物SHA完全相同 |
| 现有整课16个视频分块 | 78,497,527字节（此次只量大小，未重渲或重传） |
| 现有整课最终文件 | 91,546,872字节；包含144本地后期音轨，不等于远端下载量 |
| 现有contact目录 | 198文件、118,621,255字节（此次只量大小） |

download按文件流式生成tar，没有预先打完整包的阶段；开始发送前有SSH握手、status/downloaded调用及文件枚举。30秒首字节额外宽限可暂保留。SSH开启压缩，上表是有效文件字节/整次调用时间，不是线速；3轮短测不能推导长期最低吞吐，也没有测到健康30秒窗口的统计下界。

建议按以下方式校准：

1. **取消上传共用的固定120秒门槛。** 31.8MB即使持续50KiB/s也需约621秒，120秒会误杀有持续进展的上传。临时可用现有`--remote-queue-seconds 1200`，同时保留流式30秒停顿检测和900秒总期限；这只是兼容当前参数的过渡办法，不是所有包的保证。更合适的实现是分别限制本地准备、prepare、上传、上传回执、submit，用共享取消信号收回对应操作。
2. `256KiB/30秒`实际约8.53KiB/s，暂不凭三轮健康数据调低。900秒期限对本包要求平均约34.5KiB/s，尚未算固定开销；50KiB/s可作为设计慢速场景，**不是实测的网络服务下限**。若真实慢路径低于这个水平，需按包大小增加流式期限，不能只提高外层排队参数。
3. `90秒无成功status`先保留为待注入验证的假设；不要据此增加“没有新帧就取消”。目前`poll()`还等待logs后才刷新last_ok，日志卡住也会被统计成status失联，客户端应分别计时。

## Q4：最近进展时间

本轮不加。现有started_at/finished_at、progress、增量日志游标足够支持本次活性检查。目录mtime不能可靠代表渲染进展：打包、编码、缓冲写入均可能长期不改变它。以后若增加，应明确是agent应答时间、日志进展还是产物写入时间；不要把这些混成一个会误杀的updated_at。

## Q5：快速数据通道检查

本轮不新增echo命令或协议。256KiB试传可以帮助诊断，但一次成功不能保证随后31MB上传不中断；5秒硬门槛也尚未经过慢路径校准。现有真实上传的监护先保留。若以后增加诊断命令，应限定字节数、校验内容、设置期限，并明确它只是当次样本，不是后续传输保证。

## 144客户端待改项

本轮检查的客户端SHA见`postchecks.json`；两份源码与实施前快照一致。请维护方落实：

- `tidy()`不要cancel后立即cleanup并吞异常；等待终态，再清理，失败ID要持久化并可重试。
- 上传最后一字节写完后切换到“等待应答”阶段。当前_StreamWatch仍在运行，可能30秒就按无流量杀掉SSH，使名义上的120秒回执期限失效；计数也应使用实际write返回值，注明它只是本地管道进展，不是远端落盘确认。
- `ThreadPoolExecutor.shutdown(wait=False)`不保证整个Python进程立即退出，解释器退出时仍会join工作线程；`Future.cancel()`也不能停止已运行的上传。应持有该任务的SSH进程/取消信号，放弃后主动结束流式操作、收回线程，再报告退出。记录“发出cancel”不能代替确认远端终态。
- 排队函数在prepare、upload、submit前后都检查abandoned/cancel信号；不要在已经放弃后仍先submit再取消。submit应答不明时查原ID，处理仍在上传、已排队、已运行、已终态四种情况。
- 分开status与logs的成功时间，并去掉依赖自动清理的注释/行为。`--remote-cpu`的预期是报错退出；自动选择模式才回本机，本轮没有改这个选择策略。

## A/B/C故障注入方案与候选时间

**建议窗口：2026-10-30 02:00–02:30 UTC（北京时间10:00–10:30）。这是候选时间，尚未预约自动执行。** 按求助文档§4“先回执方案、再由用户安排时间”的要求，待用户确定窗口后双方才执行；本轮未安装故障规则或定时重启任务。

窗口前冻结各诊断ID、输入哈希、预期结果和回收清单。只使用回复目录中的诊断副本；真实课程输出不覆盖。核对CPU渲染无其他running/queued/upload/download；临时入口只允许约定诊断ID和查询/取消/清理，拒绝其他新prepare/upload/submit。规则带绝对失效时间；独立于agent的回收器能自动撤销临时入口并恢复暂停进程，操作者掉线也能恢复。任何非诊断任务出现立即停止试验。

| 注入 | 执行方法 | 验收点 |
| --- | --- | --- |
| A 上传停40秒 | 只暂停目标ID的上传接收包装进程，40秒后SIGCONT；不暂停sshd/隧道/agent。诊断副本加入足够大的不可压缩填充（建议128MiB），确保SSH/TCP/管道缓冲不能吞完整包；先证明接收进度停止且客户端write确实被阻塞。 | 应触发30秒流式保护，或明确的上传阶段期限。记录原始字节计数、报错与退出时间；连接结束后cleanup成功、无接收进程。若只是数据被缓冲而未触发，记为未覆盖，不能算通过。 |
| B status应答停100秒 | 临时包装器仅对目标ID的所有status调用（包括重试和新连接）延迟到同一100秒截止点，延迟放在agent外；cancel/cleanup/probe/logs继续可用。 | 90秒附近出现无应答保护并发出cancel；实际退出时间单独测。此前任务可能已完成，cancel返回completed也合法，必须核查该ID最终无运行进程并完成显式cleanup。 |
| C 渲染中重启agent | 使用足够长的单个诊断任务，观察到Chrome/渲染进程后仅`systemctl restart openmontage-render-agent.service`；入口保持排他，所有运行/排队任务必须都在诊断白名单。 | systemd回收该服务cgroup，服务恢复后原ID为failed/agent_restarted、pid为空；客户端报告失败或通道问题，无自动重交；保存故障现场后执行显式逐文件cleanup。 |

建议分配：准备5分钟，A约5分钟，B约7分钟，C约6分钟，恢复验证7分钟。每项记录两端UTC、单调时钟耗时、ID、status/logs、进程组与Chrome清单、磁盘增量和cleanup审计；需要恢复时优先自动解除该ID的暂停/延迟，不触碰H3、Qwen、LTX、VoxCPM或GPU分配。不能对共享接口做全局限速、不能停整条隧道、不能SIGSTOP整个agent来替代B。

每项故障解除后，用相同诊断三静帧输入通过真实客户端跑一次健康上传→渲染→下载→SHA核验。三个保护要分别给出“触发/未触发、取消发送/确认、进程回收、目录清理、客户端实际退出”结果；任一项不满足就停止下一项。此方案的临时包装器和自动回收器需在窗口前于隔离环境预演，不在本回执发布时激活。

## 全部改动、部署与回退

1. `remote_render/agent.py`：任务锁、提交前重复检查、排队取消出队、父进程退出后的进程组升级、终态后允许清理、恢复canceling、断开应答处理；移除隐式递归清理。安装到`/opt/openmontage-render/agent.py`。
2. `remote_render/ssh_wrapper.py`：upload/download全程锁；rsync边界也持锁，写入仅允许未提交input；半包和旧输入保留到cleanup。实际强制入口`/usr/local/libexec/openmontage-render-ssh`和`/opt/openmontage-render/ssh_wrapper.py`均更新。
3. 新增`openmontage_job_files.py`，安装在上述两个脚本目录，提供锁及逐文件清理审计。三个Python源文件均以root:root、0755安装并校验SHA/可读权限。
4. 新增`test_liveness.py`并更新旧scratch清理测试；系统Python3.8共27项通过。新增正常通道测量、普通取消与进程观察证据。更新本机README、144操作手册、短交接索引；保存求助原文及实施前源码。
5. 06:46:46–06:46:47 UTC，确认队列/渲染/上传均空后，以短暂维护入口挡住新调用，重启CPU agent并验证probe后恢复入口。当前agent PID605407、NRestarts=0；隧道PID2026153保持。CPUQuota=9600%、65 workers / 1 job / 2 tabs、GPU配置及其他服务不改。
6. 144仅在`docs/remote-render-replies/`增加回执、诊断输入/脚本/日志/产物和基准。没有改客户端、课程、素材、SSH配置、审批或Git提交。正常cleanup只用于本轮明确的空prepare/锁测试ID；其他诊断输出保留。

源码差异见 [renderer-source.patch](2026-10-29-client-liveness-results/renderer-source.patch)。收尾时5个安装文件与源文件哈希一致、服务账号仅剩agent进程，见 [final-renderer-check.json](2026-10-29-client-liveness-results/final-renderer-check.json)。

备份：`/opt/openmontage-render/backups/client-liveness-20261029T064646Z/`。对应`0-agent.py`、`1-ssh_wrapper.py`、`2-openmontage-render-ssh`。完整源/安装哈希、权限及GPU进程前后核验见 [deployment.json](2026-10-29-client-liveness-results/deployment.json)。

回退时先确认无活动任务/传输并挡住新提交，用`install -o root -g root -m0755`恢复上述三个备份到各自原路径，只重启CPU agent，检查probe版本和真实通道；共享helper可留置，不需要删除数据。**旧agent/5会恢复隐式6小时清理和本轮已修的竞态**，回退前必须检查现存终态数据及备份，不能把回退当作无副作用操作。

## v3模板补充

| 项目 | 本次结论 |
| --- | --- |
| 授权与约束 | 用户已确认实施；CPU9600%固定；仅CPU服务及回复目录；保留GPU优先级 |
| A1字体 | 清除继承FONTCONFIG/FC变量机制保留；三轮日志显示私有DejaVu字体；静帧9张解码成功，未做字体全集专项 |
| A2源码覆盖 | 实际source_overlay=true；node_modules仅链接runtime；deps_mismatch回归通过；TMPDIR在job内；TasksMax65536 |
| A3 probe | agent/6；无新增可选字段；完整结果附后 |
| A4/A5/A6 | 增量日志与manifest通过；排队上限16、运行并发1；取消与显式清理见Q1/Q2，自动清理已撤除 |
| A7 | 本轮修活性边界；未重跑旧A7故障或满载10分钟专项 |
| B3 GPU | gl=null、headless-shell、hardwareAcceleration=disabled；未给Chrome分配GPU |
| B4 NVENC | 未启用；本轮静帧与取消验收不测编码占比 |
| B5容量 | max_concurrent_jobs=1，max_total_workers=65，推荐65/job、2tabs；Nice10，无独占CPU保证 |
| B6基准 | 本轮bench_results已附；保持原容量选择，未做新性能调参 |

## 完整最终probe

记录时间：2026-10-29T07:00:53.886855+00:00。

```json
{
  "ok": true,
  "agent": "openmontage-render-agent/6",
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
    "cpu_busy_percent": 40,
    "mem_free_mb": 125350,
    "gpu_busy_percent": 100,
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
  "free_bytes": 402107035648,
  "min_free_bytes": 107374182400
}
```

## 未验证与剩余风险

A/B/C真实停顿、真实运行中agent重启、多日稳定性和代理故障切换未验证。当前健康数字不代表低速边界；可选Q4/Q5未实现。客户端清理/退出/阶段期限待144维护方调整，修复落地前仍可能留下待清理目录或等待后台线程；渲染机不再自动删除这些数据。
