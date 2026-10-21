# 阶段清单 · 素材（配音）（assets）

> 由 `docs/whiteboard_registry.py render` 从 `docs/whiteboard/lessons-learned.yaml` 生成，**不要手改**；要改规则，改登记表再重新运行并提交。

**口令**：样音通过 → 素材通过

**本阶段做什么**：
1. 跑 `sample_voice.py` 出样音（含最难一句），停下等“样音通过”；用户说了之后：`docs/whiteboard_gate.py record <项目> sample "<用户原话>"`（没有检查点，只追加记录）。
2. 跑 `gen_tts.py`（批量配音 + 拼总轨 + loudnorm −16 LUFS）→ `make_captions.py` → `finish_assets.py`；写 assets 检查点 awaiting_human，停下等“素材通过”；用户说了之后：`docs/whiteboard_gate.py approve <项目> assets "<用户原话>"`。
3. 配音还没生成完、核对还没做完之前用户说的口令不算。

**产出**：assets/audio/narration_timeline.json；captions.json；asset_manifest.json

**已是模板或工具的默认做法**（知道即可，别改掉）：
- **[E37]** 配音脚本已处理：WAV 头时长不可信（ffmpeg 重封装再量）、单次 ≤600 字、问句处切段并插入真实静默 3 秒、按段给问句计数（两个段都有问句也不报错）；首次读超时重跑即可（缓存的段不会重生成）。 〔脚本：`projects/<课程>/scripts/gen_tts.py`〕
