#!/usr/bin/env python3
"""Batch image generation, contact sheets, and candidate picking."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


from project_paths import ROOT, P
DEFAULT_PROJECT = str(P)
ASPECT_SIZES = {
    "16:9": (1408, 768),
    "1:1": (1024, 1024),
    "3:2": (1264, 848),
    "9:16": (768, 1376),
    "4:3": (1200, 900),
    "3:4": (900, 1200),
}
SIZE_ARGS = {"1:1": "1024x1024", "3:2": "1792x1024"}
IMAGE_RE = re.compile(r"^(?P<id>[^/]+)_c(?P<call>\d+)_(?P<item>\d+)\.png$")


class MissingReference(Exception):
    def __init__(self, ref: str, path: Path, anchor: bool = False):
        self.ref = ref
        self.path = path
        self.anchor = anchor
        kind = "anchor" if anchor else "reference"
        super().__init__(f"{kind} {ref} not found at {path}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_component(value: str, label: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_specs(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        raise ValueError(f"invalid specs file: {path}")
    specs = []
    seen = set()
    for item in data["assets"]:
        if not isinstance(item, dict):
            raise ValueError("each asset must be an object")
        asset_id = safe_component(str(item.get("id", "")), "asset id")
        if asset_id in seen:
            raise ValueError(f"duplicate asset id: {asset_id}")
        seen.add(asset_id)
        if "name" not in item or "prompt" not in item:
            raise ValueError(f"asset {asset_id} needs name and prompt")
        spec = dict(item)
        spec["id"] = asset_id
        spec["name"] = safe_component(str(spec["name"]), "asset name")
        spec["refs"] = list(spec.get("refs") or [])
        spec["candidates"] = max(1, int(spec.get("candidates", 1)))
        spec["order"] = int(spec.get("order", 0))
        spec["aspect"] = str(spec.get("aspect", "16:9"))
        spec["mode"] = str(spec.get("mode", "generate"))
        specs.append(spec)
    return sorted(specs, key=lambda item: (item["order"], item["id"]))


def resolve_specs_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path.resolve()
    return (ROOT / path).resolve()


def resolve_project(value: str | None) -> Path:
    value = value or DEFAULT_PROJECT
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    # Running the script from out/ makes --project ws_proj naturally mean out/ws_proj.
    if Path.cwd().resolve() == SCRIPT_DIR.resolve():
        return (Path.cwd() / path).resolve()
    return (ROOT / path).resolve()


def image_dirs(project: Path) -> dict[str, Path]:
    images = project / "assets" / "images"
    return {
        "images": images,
        "raw": images / "raw",
        "cand": images / "cand",
        "records": images / "records",
        "sheets": images / "sheets",
    }


def ensure_dirs(project: Path) -> dict[str, Path]:
    dirs = image_dirs(project)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, sep, value = line.partition("=")
        if not sep:
            continue
        name = name.strip()
        if name not in {"MODELINK_API_KEY", "MODELINK_BASE_URL"}:
            continue
        values[name] = value.strip().strip("'\"")
    return values


def load_credentials() -> tuple[str, str]:
    values = parse_env_file(ROOT / ".env")
    values.update(parse_env_file(ROOT / "crosscheck.env"))
    for name in ("MODELINK_API_KEY", "MODELINK_BASE_URL"):
        if name in os.environ:
            values[name] = os.environ[name]
    key = values.get("MODELINK_API_KEY")
    base = values.get("MODELINK_BASE_URL")
    if not key or not base:
        raise RuntimeError("credentials not found")
    return key, base


def redact_error(error: BaseException, base: str | None = None, key: str | None = None) -> str:
    text = str(error)
    for secret in (key, base):
        if secret:
            text = text.replace(secret, "<REDACTED>")
    text = re.sub(r"https?://[^\s'\"<>]+", "<URL>", text)
    return text[:1000]


def import_key_image():
    docs = ROOT / "docs"
    if str(docs) not in sys.path:
        sys.path.insert(0, str(docs))
    try:
        from whiteboard_pose_tool import key_image
    except ImportError as error:
        raise RuntimeError(f"cannot import docs/whiteboard_pose_tool.py: {error}") from error
    return key_image


def placeholder_reference(project: Path, ref: str) -> Path:
    from PIL import Image, ImageDraw

    folder = project / "assets" / "images" / ".dry_refs"
    folder.mkdir(parents=True, exist_ok=True)
    stem = Path(ref).stem or "reference"
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", stem)
    path = folder / f"{stem}.png"
    if path.exists():
        return path
    image = Image.new("RGBA", (768, 1024), (242, 242, 238, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((220, 130, 548, 895), fill=(215, 231, 246, 255), outline=(17, 24, 39, 255), width=5)
    draw.ellipse((290, 210, 478, 398), fill=(245, 210, 170, 255), outline=(17, 24, 39, 255), width=5)
    draw.line((292, 450, 470, 450), fill=(17, 24, 39, 255), width=22)
    draw.line((292, 450, 220, 670), fill=(17, 24, 39, 255), width=18)
    draw.line((470, 450, 555, 625), fill=(17, 24, 39, 255), width=18)
    draw.line((325, 895, 285, 1000), fill=(17, 24, 39, 255), width=22)
    draw.line((420, 895, 480, 1000), fill=(17, 24, 39, 255), width=22)
    image.save(path, format="PNG")
    return path


def resolve_references(
    spec: dict[str, Any], project: Path, dry_run: bool
) -> tuple[list[Path], list[dict[str, str]]]:
    paths: list[Path] = []
    metadata: list[dict[str, str]] = []
    dirs = image_dirs(project)
    for raw_ref in spec.get("refs", []):
        ref = str(raw_ref)
        if ref.startswith("@"):
            anchor_name = safe_component(ref[1:], "anchor name")
            path = dirs["images"] / f"{anchor_name}.png"
            if not path.exists():
                raise MissingReference(ref, path, anchor=True)
        else:
            path = (ROOT / ref).resolve()
            if not path.exists():
                if not dry_run:
                    raise MissingReference(ref, path)
                path = placeholder_reference(project, ref)
        paths.append(path)
        metadata.append({"ref": ref, "sha256": sha256_file(path)})
    return paths, metadata


def image_dimensions(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as image:
        return image.width, image.height


def save_image_bytes(data: bytes, path: Path) -> tuple[int, int, int]:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(data)) as image:
        image.load()
        image.save(path, format="PNG")
        width, height = image.size
    return width, height, path.stat().st_size


def object_value(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def response_bytes(item: Any) -> bytes:
    encoded = object_value(item, "b64_json")
    if encoded:
        return base64.b64decode(encoded)
    url = object_value(item, "url")
    if url:
        with urllib.request.urlopen(url, timeout=300) as response:
            return response.read()
    raise ValueError("image response contained neither b64_json nor url")


def make_placeholder(spec: dict[str, Any], call_no: int, item_no: int) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    width, height = ASPECT_SIZES.get(spec["aspect"], ASPECT_SIZES["16:9"])
    bg = str(spec.get("bg", "card"))
    if bg == "green":
        background = (0, 255, 0, 255)
    elif bg == "magenta":
        background = (255, 0, 255, 255)
    else:
        background = (248, 248, 244, 255)
    image = Image.new("RGBA", (width, height), background)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", max(14, min(width, height) // 18))
    except OSError:
        font = ImageFont.load_default()
    label = f"{spec['id']} c{call_no}_{item_no}"
    if bg in {"green", "magenta"}:
        cx = width // 2
        head_r = max(18, min(width, height) // 10)
        head_y = max(head_r + 20, height // 4)
        torso_w = max(42, width // 5)
        torso_top = head_y + head_r + 18
        torso_bottom = min(height - 35, torso_top + max(80, height // 3))
        ink = (24, 44, 68, 255)
        shirt = (226, 202, 155, 255)
        draw.ellipse((cx - head_r, head_y - head_r, cx + head_r, head_y + head_r), fill=(245, 210, 170, 255), outline=ink, width=max(2, width // 170))
        draw.rectangle((cx - torso_w, torso_top, cx + torso_w, torso_bottom), fill=shirt, outline=ink, width=max(2, width // 170))
        arm_w = max(5, width // 34)
        draw.line((cx - torso_w, torso_top + 25, cx - torso_w - width // 8, torso_top + height // 7), fill=ink, width=arm_w)
        draw.line((cx + torso_w, torso_top + 45, cx + torso_w + width // 9, torso_top + height // 18), fill=ink, width=arm_w)
        draw.line((cx - width // 16, torso_bottom, cx - width // 7, height - 18), fill=ink, width=arm_w)
        draw.line((cx + width // 16, torso_bottom, cx + width // 5, height - 35), fill=ink, width=arm_w)
        draw.text((12, 12), label, fill=ink, font=font)
    else:
        margin = max(24, min(width, height) // 8)
        draw.rounded_rectangle((margin, margin * 2, width - margin, height - margin), radius=max(8, margin // 3), fill=(205, 235, 250, 255), outline=(9, 51, 68, 255), width=max(3, width // 160))
        draw.rectangle((margin * 2, height // 2, width - margin * 2, height // 2 + max(18, height // 20)), fill=(28, 54, 83, 255))
        draw.text((margin * 2, margin), label, fill=(17, 24, 39, 255), font=font)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def append_record(path: Path, spec: dict[str, Any], run: dict[str, Any]) -> None:
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = load_json(path)
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing.update({"id": spec["id"], "name": spec["name"], "kind": spec.get("kind")})
    runs = existing.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append(run)
    existing["runs"] = runs
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def existing_candidates(dirs: dict[str, Path], asset_id: str) -> bool:
    return any(dirs["cand"].glob(f"{asset_id}_c*_*.png"))


def api_kwargs(spec: dict[str, Any], with_refs: bool) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    # Edit requests follow their first reference, including generate requests with anchors.
    if spec["mode"] == "generate" and not with_refs:
        aspect = spec["aspect"]
        if aspect in SIZE_ARGS:
            kwargs["size"] = SIZE_ARGS[aspect]
        elif aspect != "16:9":
            kwargs["extra_body"] = {"aspect_ratio": aspect}
    return kwargs


def call_once(client: Any, model: str, spec: dict[str, Any], refs: list[Path]) -> list[bytes]:
    prompt = str(spec["prompt"])
    if spec["mode"] == "edit" or refs:
        with ExitStack() as stack:
            files = [stack.enter_context(path.open("rb")) for path in refs]
            response = client.images.edit(model=model, image=files, prompt=prompt)
    else:
        kwargs = api_kwargs(spec, False)
        response = client.images.generate(model=model, prompt=prompt, n=1, **kwargs)
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    if not data:
        raise ValueError("image response contained no data")
    return [response_bytes(item) for item in data]


def call_with_retries(
    client: Any,
    model: str,
    spec: dict[str, Any],
    refs: list[Path],
    base: str,
    key: str,
) -> tuple[list[bytes], list[str]]:
    errors: list[str] = []
    for attempt in range(3):
        try:
            return call_once(client, model, spec, refs), errors
        except Exception as error:
            errors.append(redact_error(error, base, key))
            if attempt < 2:
                time.sleep(2**attempt)
    return [], errors


def run_asset(
    spec: dict[str, Any],
    project: Path,
    model: str,
    fallback_model: str | None,
    dry_run: bool,
    force: bool,
    client: Any = None,
    base: str = "",
    key: str = "",
) -> dict[str, Any]:
    dirs = ensure_dirs(project)
    asset_id = spec["id"]
    record_path = dirs["records"] / f"{asset_id}.json"
    if not force and existing_candidates(dirs, asset_id):
        message = f"SKIP {asset_id}: candidates already exist (use --force to regenerate)"
        print(message, flush=True)
        return {"id": asset_id, "status": "skipped", "message": message}

    run: dict[str, Any] = {
        "started_at": iso_now(),
        "model": model,
        "mode": spec["mode"],
        "prompt": str(spec["prompt"]),
        "prompt_sha256": sha256_bytes(str(spec["prompt"]).encode("utf-8")),
        "references": [],
        "aspect": spec["aspect"],
        "results": [],
        "errors": [],
        "fallback_used": False,
    }
    try:
        refs, reference_metadata = resolve_references(spec, project, dry_run)
        run["references"] = reference_metadata
    except MissingReference as error:
        message = str(error)
        run["status"] = "skipped"
        run["errors"] = [message]
        append_record(record_path, spec, run)
        print(f"SKIP {asset_id}: {message}", flush=True)
        return {"id": asset_id, "status": "skipped", "message": message}

    key_image = import_key_image()
    for call_no in range(1, int(spec["candidates"]) + 1):
        started = time.monotonic()
        images: list[bytes] = []
        chosen_model = model
        if dry_run:
            images = [make_placeholder(spec, call_no, item_no) for item_no in (1,)]
        else:
            images, errors = call_with_retries(client, model, spec, refs, base, key)
            if errors:
                run["errors"].extend({"call": call_no, "model": model, "message": error} for error in errors)
            if not images and fallback_model and fallback_model != model:
                fallback_images, fallback_errors = call_with_retries(client, fallback_model, spec, refs, base, key)
                if fallback_errors:
                    run["errors"].extend({"call": call_no, "model": fallback_model, "message": error} for error in fallback_errors)
                if fallback_images:
                    images = fallback_images
                    chosen_model = fallback_model
                    run["fallback_used"] = True
        if not images:
            run["errors"].append({"call": call_no, "message": "generation failed after retries"})
            continue

        for item_no, data in enumerate(images, start=1):
            raw_path = dirs["raw"] / f"{asset_id}_c{call_no}_{item_no}.png"
            cand_path = dirs["cand"] / f"{asset_id}_c{call_no}_{item_no}.png"
            try:
                width, height, _ = save_image_bytes(data, raw_path)
                if spec.get("bg") in {"green", "magenta"}:
                    key_image(str(raw_path), str(cand_path), str(spec["bg"]))
                    cand_width, cand_height = image_dimensions(cand_path)
                else:
                    cand_width, cand_height, _ = save_image_bytes(raw_path.read_bytes(), cand_path)
            except (Exception, SystemExit) as error:
                run["errors"].append(
                    {
                        "call": call_no,
                        "item": item_no,
                        "message": redact_error(error, base, key),
                    }
                )
                continue
            elapsed = round(time.monotonic() - started, 3)
            run["results"].append(
                {
                    "raw_file": str(raw_path.relative_to(project)),
                    "file": str(cand_path.relative_to(project)),
                    "width": cand_width,
                    "height": cand_height,
                    "raw_width": width,
                    "raw_height": height,
                    "bytes": cand_path.stat().st_size,
                    "sha256": sha256_file(cand_path),
                    "seconds": elapsed,
                    "model": chosen_model,
                }
            )
    run["status"] = "ok" if run["results"] else "failed"
    run["finished_at"] = iso_now()
    append_record(record_path, spec, run)
    print(f"{asset_id}: {run['status']} ({len(run['results'])} candidate(s))", flush=True)
    return {"id": asset_id, "status": run["status"], "results": len(run["results"])}


def run_generation(args: argparse.Namespace, project: Path) -> int:
    specs_path = resolve_specs_path(args.specs[0]) if len(args.specs) == 1 else None
    if specs_path is None:
        # The CLI accepts multiple files; combine their assets in order.
        specs: list[dict[str, Any]] = []
        for value in args.specs:
            specs.extend(load_specs(resolve_specs_path(value)))
        specs.sort(key=lambda item: (item["order"], item["id"]))
    else:
        specs = load_specs(specs_path)
    if args.only:
        wanted = set(args.only)
        specs = [spec for spec in specs if spec["id"] in wanted]
    if not args.dry_run:
        key, base = load_credentials()
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError(f"openai package unavailable: {error}") from error
        client = OpenAI(api_key=key, base_url=base, timeout=400)
    else:
        key, base, client = "", "", None

    results = []
    for order in sorted({spec["order"] for spec in specs}):
        group = [spec for spec in specs if spec["order"] == order]
        with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as executor:
            futures = {
                executor.submit(
                    run_asset,
                    spec,
                    project,
                    args.model,
                    args.fallback_model,
                    args.dry_run,
                    args.force,
                    client,
                    base,
                    key,
                ): spec["id"]
                for spec in group
            }
            for future in as_completed(futures):
                results.append(future.result())
    failed = sum(item.get("status") == "failed" for item in results)
    skipped = sum(item.get("status") == "skipped" for item in results)
    print(f"gen complete: {len(results)} asset(s), {failed} failed, {skipped} skipped")
    return 1 if failed else 0


def load_font(size: int):
    from PIL import ImageFont

    for name in (
        "DejaVuSansMono.ttf",
        "LiberationMono-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def checkerboard(size: tuple[int, int]):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", size, (248, 248, 248))
    draw = ImageDraw.Draw(image)
    tile = max(8, min(size) // 18)
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, min(x + tile - 1, size[0] - 1), min(y + tile - 1, size[1] - 1)), fill=(224, 224, 224))
    return image


def candidate_files(dirs: dict[str, Path], ids: set[str] | None) -> list[tuple[Path, str, int, int]]:
    found = []
    for path in dirs["cand"].glob("*.png"):
        match = IMAGE_RE.match(path.name)
        if not match:
            continue
        asset_id = match.group("id")
        if ids and asset_id not in ids:
            continue
        found.append((path, asset_id, int(match.group("call")), int(match.group("item"))))
    return sorted(found, key=lambda item: (item[1], item[2], item[3]))


def make_sheets(args: argparse.Namespace, project: Path) -> int:
    from PIL import Image, ImageDraw

    dirs = ensure_dirs(project)
    ids = set(args.ids) if args.ids else None
    files = candidate_files(dirs, ids)
    cols = max(1, int(args.cols))
    for old in dirs["sheets"].glob("sheet_*.png"):
        old.unlink()
    if not files:
        print("sheet: no candidates found")
        return 0
    label_font = load_font(20)
    cell_width = 480
    label_height = 34
    for sheet_no, start in enumerate(range(0, len(files), 12), start=1):
        chunk = files[start : start + 12]
        rows = (len(chunk) + cols - 1) // cols
        cell_info = []
        for path, asset_id, call_no, item_no in chunk:
            with Image.open(path) as source:
                source = source.convert("RGBA")
                scale = min(1.0, cell_width / source.width)
                size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
                cell_info.append((path, asset_id, call_no, item_no, source.copy(), size))
        row_heights = []
        for row in range(rows):
            row_items = cell_info[row * cols : (row + 1) * cols]
            row_heights.append(max(item[5][1] for item in row_items) + label_height)
        sheet = Image.new("RGB", (cols * cell_width, sum(row_heights)), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        y = 0
        for row, row_height in enumerate(row_heights):
            for col, item in enumerate(cell_info[row * cols : (row + 1) * cols]):
                path, asset_id, call_no, item_no, source, size = item
                x = col * cell_width
                canvas = checkerboard((size[0], size[1]))
                source.thumbnail(size, Image.Resampling.LANCZOS)
                canvas.paste(source, (0, 0), source)
                sheet.paste(canvas, (x + (cell_width - size[0]) // 2, y))
                width, height = image_dimensions(path)
                label = f"{asset_id} c{call_no}_{item_no} {width}x{height}"
                draw.text((x + 8, y + row_height - label_height + 5), label, fill=(17, 24, 39), font=label_font)
            y += row_height
        out = dirs["sheets"] / f"sheet_{sheet_no}.png"
        sheet.save(out, format="PNG")
        print(f"sheet: {out}")
    return 0


def spec_name_from_record(dirs: dict[str, Path], asset_id: str) -> str:
    path = dirs["records"] / f"{asset_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"record not found for {asset_id}: run gen first")
    data = load_json(path)
    name = data.get("name") if isinstance(data, dict) else None
    if not name:
        raise ValueError(f"record for {asset_id} has no asset name")
    return safe_component(str(name), "asset name")


def pick_candidate(args: argparse.Namespace, project: Path) -> int:
    from PIL import Image

    dirs = ensure_dirs(project)
    asset_id = safe_component(args.id, "asset id")
    match = re.fullmatch(r"c(\d+)_(\d+)", args.candidate)
    if not match:
        raise ValueError("candidate must look like c1_1")
    source = dirs["cand"] / f"{asset_id}_{args.candidate}.png"
    if not source.exists():
        raise FileNotFoundError(f"candidate not found: {source}")
    name = spec_name_from_record(dirs, asset_id)
    destination = dirs["images"] / f"{name}.png"
    with Image.open(source) as image:
        selected = image.convert("RGBA")
        if args.flip:
            selected = selected.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        selected.save(destination, format="PNG")
    picked_path = dirs["images"] / "picked.json"
    picked: dict[str, Any] = {"picks": []}
    if picked_path.exists():
        try:
            loaded = load_json(picked_path)
            if isinstance(loaded, dict):
                picked = loaded
        except (OSError, json.JSONDecodeError):
            picked = {"picks": []}
    if not isinstance(picked.get("picks"), list):
        picked["picks"] = []
    picked["picks"].append(
        {
            "user": os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
            "id": asset_id,
            "candidate": args.candidate,
            "file": str(destination.relative_to(project)),
            "flipped": bool(args.flip),
            "time": iso_now(),
        }
    )
    picked_path.write_text(json.dumps(picked, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"pick: {source} -> {destination} (flip={bool(args.flip)})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("gen")
    gen.add_argument("--project", dest="project_after", default=None)
    gen.add_argument("--specs", nargs="+", default=[str(SCRIPT_DIR / "scene_data/images.json")])
    gen.add_argument("--only", nargs="+")
    gen.add_argument("--dry-run", action="store_true")
    gen.add_argument("--force", action="store_true")
    gen.add_argument("--workers", type=int, default=3)
    gen.add_argument("--model", default="google/gemini-3-pro-image")
    gen.add_argument("--fallback-model", default="google/gemini-nano-banana-2.1")

    sheet = sub.add_parser("sheet")
    sheet.add_argument("--project", dest="project_after", default=None)
    sheet.add_argument("--ids", nargs="+")
    sheet.add_argument("--cols", type=int, default=4)

    pick = sub.add_parser("pick")
    pick.add_argument("--project", dest="project_after", default=None)
    pick.add_argument("id")
    pick.add_argument("candidate")
    pick.add_argument("--flip", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    project_arg = getattr(args, "project_after", None) or args.project
    project = resolve_project(project_arg)
    try:
        if args.command == "gen":
            return run_generation(args, project)
        if args.command == "sheet":
            return make_sheets(args, project)
        if args.command == "pick":
            return pick_candidate(args, project)
        parser.error(f"unknown command: {args.command}")
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
