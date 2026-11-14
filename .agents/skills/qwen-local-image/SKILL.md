---
name: qwen-local-image
description: Local Qwen-Image-2.1 on the GPU server (free, async job API) — text-to-image and reference-image editing for character-consistent line-art scenes. A supplement to dashscope_image, not a replacement.
---

# Qwen-Image-2.1 (local GPU)

Tool: `qwen_local_image` (provider `qwen_local`). It calls the installed CLI (`QWEN_LOCAL_CLI`, default `/opt/h3-api/qwen`), which loads the Bearer key from its own protected environment. Never put that key in `.env`, code, logs or Git. Service notes: `apidocs/QWEN_IMAGE_API_GUIDE.md`.

## When to use it
- Use for: free/offline generation, character-consistent scenes (1-4 reference images), clean black line art.
- Prefer `dashscope_image` (default in our lessons) when you need speed, or when an action composition keeps failing here.
- Measured on this server (1536x1536, 40 steps): text-to-image ~45 s, edit with 1-2 references ~65-95 s. The GPU is shared (one job at a time, max 4 unfinished): submit sequentially.

## Usage
```python
from tools.graphics.qwen_local_image import QwenLocalImage
QwenLocalImage().execute({
    "prompt": "<style prefix> 场景：图1中的小明躺在床上，图2中的医生俯身做手术。画面中只有这两个人。",
    "negative_prompt": "阴影，灰色填充，彩色，文字，字母，数字，水印",
    "image_paths": ["ref_xiaoming.png", "ref_doctor.png"],   # first image sets the canvas
    "resolution": 1536, "steps": 40, "seed": 415, "output_path": "scene.png",
})
```
- No `image_paths` -> `text_to_image` (aspect_ratio 1:1 / 16:9 / 9:16). With references -> `image_edit`; `aspect_ratio` is ignored (the first image decides).
- Prompt tips that worked: repeat the same style prefix; say who is in each picture ("图1中的小明", "图2中的医生"); state the exact number of people ("画面中只有这两个人"); for signs/paper say "只画三条横线，没有任何文字".
- Output is an opaque PNG: key the white background to alpha with the project's `postprocess_images.py` before placing it on the whiteboard.
- Always inspect every image. The service reports `quality_review=not_performed`; reference images do not guarantee identity, especially with several people.

## Idempotency and retries
The request id is a hash of the whole input plus the bytes of each reference, saved to `<output>.qwen_job.json` before submitting. Running the same input again reuses the finished file (or replays the same job); to get a new image change `seed` or `request_version`. Never invent a new id to retry a `needs_attention` job — contact the GPU server maintainer.

| Status / error | What the tool does |
| --- | --- |
| queued / running | polls every 5 s until `timeout_seconds` (default 900); on timeout the ledger keeps the job id, run the same input again to keep waiting |
| completed | downloads (CLI verifies SHA-256), checks the PNG decodes |
| failed / canceled / needs_attention | returns an error, keeps the ledger, no automatic resubmission |
| HTTP 429 | waits 10 s, retries with the same id and content |
