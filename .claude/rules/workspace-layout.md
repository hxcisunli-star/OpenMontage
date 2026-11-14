# 文件存放规范（始终生效）

用户 2026-11-04 定。起因：`/home/MyProject` 根目录被 `codex-ws-*`、`ag-ws-*`、`backup-*`、`*-probe` 弄乱，十月留下的工作区该删没删；硬盘有限。机密规矩（工作区不得有 `.env`、密钥）见 `/root/.claude/CLAUDE.md`，这里不重复。

1. **`/home/MyProject` 根目录只放**：`OpenMontage`、`openhands-team`、`openhands-harness2`、`_scratch` 和用户自己放的东西。会话**不得**在根目录新建文件夹或文件。
2. **临时工作区、备份、探针、一次性脚本**一律放 `/home/MyProject/_scratch/<工具或用途>-<课>-<名>/`（例 `_scratch/codex-ws-l3-fact`），**建的时候就写 `WHY.md`**：谁建的、为什么、什么时候可以删。以后清理不用考古。派 Codex 用 `/root/.claude/scripts/codex/launch_codex*.sh <工作区名>`，它在 `_scratch/<工作区名>/` 里跑。
3. **成果去向**：被采纳的进项目目录；任务书、原始返回、中间版本存到该课 `projects/<课>/validation/<来源>/`；归属不明或跨课的存到 `projects/_<工具>_ws_archive/`（已有 `_codex_ws_archive`、`_agy_ws_archive`、`_hf_pilot_archive`，各带 `README.md` 和逐文件对账的 `MANIFEST.tsv`）。存完核对（哈希）后按名字删工作区，不留"以后再说"。
4. **备份**：只在做不可逆或大改动前建，因为 `projects/` 不进 git，备份是唯一的后悔药。**改动验证通过就立即删**，不留到课结束。
5. **清理时点**：每个门放行后，清掉自己建的 `_scratch/` 条目；`_scratch/` 里超过 3 天没动的条目算孤儿，开新阶段先清。别人的条目不确定就先看它的 `WHY.md`，没有 `WHY.md` 的问用户。
6. **硬盘有限**：派活工作区只拷任务要读的文件，用 `INDEX.md` 列清单，不要把整个项目拷进去；浏览器 profile／缓存、`node_modules`、渲染中间块用完就删。
7. **自动检查**：每次新开、恢复、清空、压缩上下文时，**用户级** `~/.claude/settings.json` 的 SessionStart 钩子会跑本仓库的 `docs/workspace_audit.py`（只读，从不删东西），对所有项目的会话都生效。干净时没有任何输出；出现名单就按上面几条处理。手动查：`.venv/bin/python docs/workspace_audit.py`。钩子用绝对路径指向本仓库的脚本和 `.venv`，这两样搬走或删除时它会静默失效，要同步改。
8. 以上是**目录卫生**，不改白板课口令与门控（`whiteboard-protocol.md`）。
