"""Local Qwen-Image-2.1 generation through the GPU server's job API (CLI wrapper).

A supplement to the commercial providers (e.g. ``dashscope_image``), not a
replacement. The service is asynchronous: submit -> poll -> download. This tool
drives the installed CLI (``QWEN_LOCAL_CLI``, default ``/opt/h3-api/qwen``), which
loads the Bearer key from its own protected environment, so no secret is ever
read, logged or stored here.

Idempotency: the request id is derived from the full input (including the bytes
of every reference image) and written to ``<output>.qwen_job.json`` *before*
submitting. Re-running the same input replays the same job instead of
generating again; change ``seed`` or ``request_version`` for a new image.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

DEFAULT_CLI = "/opt/h3-api/qwen"
RESOLUTIONS = (1024, 1536, 2048)
STEPS = (25, 40)
ASPECT_RATIOS = ("1:1", "16:9", "9:16")
MAX_REFERENCES = 4
TERMINAL = ("completed", "failed", "canceled", "needs_attention")


class QwenLocalImage(BaseTool):
    name = "qwen_local_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "qwen_local"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []
    install_instructions = (
        "Needs the GPU server's Qwen-Image job API CLI (default /opt/h3-api/qwen).\n"
        "  Set QWEN_LOCAL_CLI to another path if it lives elsewhere.\n"
        "  The CLI loads its own credentials; never put the key in .env or the repo."
    )
    fallback = "dashscope_image"
    fallback_tools = ["dashscope_image"]
    agent_skills = ["qwen-local-image"]

    capabilities = ["generate_image", "text_to_image", "image_edit"]
    supports = {
        "reference_images": True,
        "aspect_ratio": True,
        "resolution": True,
        "negative_prompt": True,
        "seed": True,
    }
    best_for = [
        "free local generation (no per-image fee, no internet)",
        "character-consistent scenes from 1-4 reference images",
        "clean black line art with no stray text",
    ]
    not_good_for = [
        "fast turnaround (about 45-95 s per image, shared GPU)",
        "precise action composition without prompt iteration",
        "guaranteed identity in multi-person scenes (review every image)",
    ]
    # Scoring hints (lib/scoring.py). A free provider would otherwise out-rank the
    # commercial default by cost alone, silently changing image_selector's choice.
    # Latency is the measured median (45-93 s); quality is deliberately conservative
    # (conditional pass, every image needs review). Select this tool explicitly with
    # preferred_provider="qwen_local" or by calling it directly.
    latency_p50_seconds = 75.0
    quality_score = 0.35

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "UTF-8 prompt, max 8192 chars."},
            "negative_prompt": {"type": "string", "description": "Optional, max 8192 chars."},
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1-4 local reference images; the first sets the canvas. Switches to image_edit.",
            },
            "reference_images": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Alias of image_paths (same name as dashscope_image).",
            },
            "resolution": {"type": "integer", "enum": list(RESOLUTIONS), "default": 1536},
            "aspect_ratio": {
                "type": "string",
                "enum": list(ASPECT_RATIOS),
                "default": "1:1",
                "description": "Text-to-image only; ignored (and reported) for image_edit.",
            },
            "steps": {"type": "integer", "enum": list(STEPS), "default": 40},
            "seed": {"type": "integer", "minimum": 0},
            "request_version": {
                "type": "string",
                "default": "v1",
                "description": "Bump to force a new job for otherwise identical input.",
            },
            "timeout_seconds": {"type": "integer", "default": 900},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=False)
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = [
        "prompt", "negative_prompt", "image_paths", "resolution", "steps", "seed", "aspect_ratio", "request_version",
    ]
    side_effects = [
        "writes image file to output_path and a <output_path>.qwen_job.json ledger",
        "occupies the shared GPU1 of the GPU server for about one minute",
    ]
    user_visible_verification = [
        "Inspect the image: the service only checks file validity (quality_review=not_performed)",
    ]

    # ---- helpers ----
    def _cli(self) -> str:
        return os.environ.get("QWEN_LOCAL_CLI") or DEFAULT_CLI

    def get_status(self) -> ToolStatus:
        cli = self._cli()
        return ToolStatus.AVAILABLE if os.path.isfile(cli) and os.access(cli, os.X_OK) else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # local GPU, no per-image fee

    def _run(self, *args: str, timeout: int = 300) -> tuple[int, str, str]:
        r = subprocess.run([self._cli(), *args], capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr

    def _json(self, *args: str) -> dict[str, Any]:
        rc, out, err = self._run(*args)
        if rc != 0:
            raise RuntimeError(f"{args[0]} failed (rc={rc}): {(err or out).strip()[-400:]}")
        return json.loads(out)

    @staticmethod
    def _request_id(spec: dict[str, Any], refs: list[Path], output: Path) -> str:
        canon = dict(spec, refs=[hashlib.sha256(p.read_bytes()).hexdigest() for p in refs], output=str(output.resolve()))
        return "om-" + hashlib.sha256(json.dumps(canon, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:40]

    # ---- execution ----
    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error=f"Qwen CLI not found or not executable: {self._cli()}. {self.install_instructions}")

        notes: list[str] = []
        prompt = (inputs.get("prompt") or "").strip()
        negative = (inputs.get("negative_prompt") or "").strip()
        if not prompt or len(prompt) > 8192 or len(negative) > 8192:
            return ToolResult(success=False, error="prompt must be 1-8192 chars and negative_prompt at most 8192 chars.")
        raw_refs = inputs.get("image_paths") or inputs.get("reference_images") or (
            [inputs["image_path"]] if inputs.get("image_path") else [])
        refs = [Path(p) for p in raw_refs]
        if len(refs) > MAX_REFERENCES:
            return ToolResult(success=False, error=f"At most {MAX_REFERENCES} reference images are supported, got {len(refs)}.")
        missing = [str(p) for p in refs if not p.is_file()]
        if missing:
            return ToolResult(success=False, error=f"Reference image(s) not found: {missing}")

        resolution, steps = inputs.get("resolution", 1536), inputs.get("steps", 40)
        try:
            resolution = int(resolution)
        except (TypeError, ValueError):
            resolution = 0
        if resolution not in RESOLUTIONS:
            notes.append(f"resolution {inputs.get('resolution')!r} not supported; used 1536")
            resolution = 1536
        if steps not in STEPS:
            notes.append(f"steps {steps!r} not supported; used 40")
            steps = 40
        mode = "image_edit" if refs else "text_to_image"
        aspect = None
        if mode == "text_to_image":
            aspect = inputs.get("aspect_ratio") or "1:1"
            if aspect not in ASPECT_RATIOS:
                notes.append(f"aspect_ratio {aspect!r} not supported; used 1:1")
                aspect = "1:1"
        elif inputs.get("aspect_ratio"):
            notes.append("aspect_ratio ignored: image_edit follows the first reference image")
        seed = inputs.get("seed")

        output = Path(inputs.get("output_path", "qwen_local_image.png"))
        output.parent.mkdir(parents=True, exist_ok=True)
        spec = {"mode": mode, "prompt": prompt, "negative": negative, "resolution": resolution, "steps": steps,
                "aspect": aspect, "seed": seed, "version": inputs.get("request_version", "v1")}
        request_id = self._request_id(spec, refs, output)
        ledger_path = output.with_name(output.name + ".qwen_job.json")

        # Same input already produced this file: reuse it, no GPU, no network.
        if ledger_path.is_file() and output.is_file():
            prev = json.loads(ledger_path.read_text(encoding="utf-8"))
            if prev.get("request_id") == request_id and prev.get("status") == "completed":
                return self._result(prev, output, start, notes, reused=True)

        ledger: dict[str, Any] = {"request_id": request_id, "status": "submitting", "mode": mode, **spec,
                                  "references": [str(p) for p in refs], "submitted_at": time.time()}
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")  # persist before submit

        prompt_file = output.with_name(output.name + ".prompt.txt")
        neg_file = output.with_name(output.name + ".negative.txt")
        prompt_file.write_text(prompt, encoding="utf-8")
        cmd = ["submit", "--request-id", request_id, "--mode", mode, "--prompt-file", str(prompt_file),
               "--resolution", str(resolution), "--steps", str(steps)]
        if negative:
            neg_file.write_text(negative, encoding="utf-8")
            cmd += ["--negative-file", str(neg_file)]
        if seed is not None:
            cmd += ["--seed", str(int(seed))]
        if aspect:
            cmd += ["--aspect-ratio", aspect]
        if refs:
            cmd += ["--image", str(refs[0])] + [x for r in refs[1:] for x in ("--reference", str(r))]

        deadline = start + int(inputs.get("timeout_seconds", 900))
        try:
            job = self._submit(cmd, deadline)
            ledger.update(job_id=job["id"], status=job.get("status", "queued"))
            ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
            while job.get("status") not in TERMINAL:
                if time.time() > deadline:
                    return ToolResult(success=False, error=f"Timed out; job {ledger['job_id']} is still {job.get('status')}. "
                                      f"Run the same input again to keep waiting for it (ledger: {ledger_path}).")
                time.sleep(5)
                job = self._json("get", "--job", ledger["job_id"])
            ledger.update(status=job["status"], parameters=job.get("parameters"), files=job.get("files"))
            if job["status"] != "completed":
                ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
                hint = " Contact the GPU server maintainer; do not resubmit under a new id." if job["status"] == "needs_attention" else ""
                return ToolResult(success=False, error=f"Qwen job {ledger['job_id']} ended as {job['status']}.{hint}")
            self._json_or_text("download", "--job", ledger["job_id"], "--output", str(output))
            self._verify_png(output)
        except Exception as e:  # noqa: BLE001 - report, keep the ledger for a resume
            ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
            return ToolResult(success=False, error=f"Qwen local generation failed: {e}")
        finally:
            for f in (prompt_file, neg_file):
                f.unlink(missing_ok=True)

        ledger["seconds"] = round(time.time() - start, 1)
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
        return self._result(ledger, output, start, notes)

    def _submit(self, cmd: list[str], deadline: float) -> dict[str, Any]:
        while True:
            rc, out, err = self._run(*cmd)
            if rc == 0:
                return json.loads(out)
            text = (err or out)
            if "429" in text and time.time() < deadline:  # capacity full: wait, retry with the SAME id and content
                time.sleep(10)
                continue
            raise RuntimeError(f"submit failed (rc={rc}): {text.strip()[-400:]}")

    def _json_or_text(self, *args: str) -> None:
        rc, out, err = self._run(*args, timeout=600)
        if rc != 0:
            raise RuntimeError(f"{args[0]} failed (rc={rc}): {(err or out).strip()[-400:]}")

    @staticmethod
    def _verify_png(path: Path) -> None:
        from PIL import Image

        with Image.open(path) as im:
            im.verify()

    def _result(self, ledger: dict[str, Any], output: Path, start: float, notes: list[str], reused: bool = False) -> ToolResult:
        params = ledger.get("parameters") or {}
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": "Qwen-Image-2.1",
                "mode": ledger.get("mode"),
                "prompt": ledger.get("prompt"),
                "output": str(output),
                "request_id": ledger["request_id"],
                "job_id": ledger.get("job_id"),
                "resolution": ledger.get("resolution"),
                "steps": ledger.get("steps"),
                "seed": params.get("seed", ledger.get("seed")),
                "width": params.get("width"),
                "height": params.get("height"),
                "reused_existing_output": reused,
                "notes": notes,
                "cost_note": "local GPU, no per-image fee; occupies shared GPU1",
                "quality_review": "not_performed (inspect the image)",
            },
            artifacts=[str(output)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=ledger.get("seed"),
            model="Qwen-Image-2.1",
        )
