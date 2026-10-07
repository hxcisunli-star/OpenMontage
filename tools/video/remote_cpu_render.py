#!/usr/bin/env python3
"""144-side client for the forced local OpenMontage render account."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import time
from pathlib import Path


class RemoteRenderError(RuntimeError):
    pass


# Messages that mean "the connection hiccuped", not "the request is wrong".  Safe to retry for idempotent requests.
TRANSIENT = ("connection reset", "connection refused", "connection closed", "timed out", "broken pipe", "kex_exchange",
             "no route to host", "temporarily unavailable", "ssh: connect")
IDEMPOTENT = {"probe", "status", "logs", "cancel", "cleanup"}


class RemoteRenderClient:
    def __init__(self, *, identity: str, known_hosts: str, port: int = 17865, host: str = "127.0.0.1") -> None:
        self.identity = str(Path(identity).expanduser())
        self.known_hosts = str(Path(known_hosts).expanduser())
        self.port = str(port)
        self.host = host

    def _base(self) -> list[str]:
        return [
            "/usr/bin/ssh", "-p", self.port, "-i", self.identity,
            "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4",
            "-o", "Compression=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={self.known_hosts}",
            "-o", "HostKeyAlias=openmontage-local-render",
            f"openmontage-render@{self.host}",
        ]

    @staticmethod
    def _json_output(data: bytes) -> dict:
        try:
            value = json.loads(data.decode("utf-8").strip().splitlines()[-1])
        except (ValueError, IndexError, UnicodeDecodeError) as exc:
            raise RemoteRenderError("local render endpoint returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise RemoteRenderError("local render endpoint returned a non-object")
        if not value.get("ok", False):
            raise RemoteRenderError(str(value.get("error", "remote render request failed")))
        return value

    def request(self, command: str, *, timeout: float = 120, attempts: int | None = None) -> dict:
        """One protocol request.  Idempotent requests (probe/status/logs/cancel/cleanup) are retried with backoff on transient errors."""
        if attempts is None:
            attempts = 4 if command.split(" ", 1)[0] in IDEMPOTENT else 1
        last: RemoteRenderError | None = None
        for attempt in range(attempts):
            if attempt:
                time.sleep(min(2 ** attempt, 10))
            try:
                result = subprocess.run(self._base() + [command], capture_output=True, check=False, timeout=timeout)
                if result.returncode:
                    raise RemoteRenderError(result.stderr.decode("utf-8", "replace")[-500:] or result.stdout.decode("utf-8", "replace")[-500:])
                return self._json_output(result.stdout)
            except subprocess.TimeoutExpired as exc:
                last = RemoteRenderError(f"timed out after {timeout}s: {command.split(' ', 1)[0]}")
                last.__cause__ = exc
            except RemoteRenderError as exc:
                last = exc
                if not any(t in str(exc).lower() for t in TRANSIENT):
                    raise
        assert last is not None
        raise last

    def probe(self) -> dict:
        return self.request("probe", timeout=30, attempts=2)

    def prepare(self, job_id: str) -> dict:
        return self.request(f"prepare {job_id}")

    def upload(self, job_id: str, source: Path) -> dict:
        source = source.resolve()
        if not source.is_dir() or source.is_symlink():
            raise RemoteRenderError("upload source must be a directory")
        process = subprocess.Popen(self._base() + [f"upload {job_id}"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert process.stdin is not None
        try:
            with tarfile.open(fileobj=process.stdin, mode="w|", dereference=True) as archive:
                for path in sorted(source.rglob("*")):
                    if path.is_symlink():
                        raise RemoteRenderError(f"upload source contains a symlink: {path}")
                    archive.add(path, arcname=path.relative_to(source).as_posix(), recursive=False)
        except Exception:
            process.kill()
            process.wait()
            raise
        process.stdin.close()
        process.stdin = None
        stdout, stderr = process.communicate()
        if process.returncode:
            raise RemoteRenderError(stderr.decode("utf-8", "replace")[-500:] or stdout.decode("utf-8", "replace")[-500:])
        return self._json_output(stdout)

    def submit(self, job_id: str, runtime_id: str) -> dict:
        return self.request(f"submit {job_id} {runtime_id}")

    def status(self, job_id: str) -> dict:
        return self.request(f"status {job_id}")

    def cancel(self, job_id: str) -> dict:
        return self.request(f"cancel {job_id}")

    def cleanup(self, job_id: str) -> dict:
        return self.request(f"cleanup {job_id}")

    def logs(self, job_id: str, offset: int | None = None) -> dict:
        """Whole log, or (when the agent advertises `log_offset`) only the text after `offset`; the reply then carries `next`."""
        return self.request(f"logs {job_id}" + ("" if offset is None else f" {int(offset)}"))

    def download(self, job_id: str, destination: Path) -> dict:
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(self._base() + [f"download {job_id}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert process.stdout is not None
        total = 0
        try:
            with tarfile.open(fileobj=process.stdout, mode="r|*") as archive:
                for member in archive:
                    path = Path(member.name)
                    if path.is_absolute() or ".." in path.parts or not member.isfile():
                        raise RemoteRenderError("remote archive contains an unsafe member")
                    target = (destination / path).resolve(strict=False)
                    if destination not in target.parents:
                        raise RemoteRenderError("remote archive escapes destination")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(member)
                    if source is None:
                        raise RemoteRenderError("remote archive member has no data")
                    with target.open("wb") as output:
                        while True:
                            block = source.read(1024 * 1024)
                            if not block:
                                break
                            total += len(block)
                            output.write(block)
        except tarfile.TarError as exc:
            process.kill()
            process.wait()
            raise RemoteRenderError("invalid remote output archive") from exc
        _, stderr = process.communicate()
        if process.returncode:
            raise RemoteRenderError(stderr.decode("utf-8", "replace")[-500:])
        self._verify_manifest(destination)
        return {"ok": True, "job_id": job_id, "bytes": total, "destination": str(destination)}

    @staticmethod
    def _verify_manifest(destination: Path) -> None:
        """If the agent shipped output/manifest.json ({"files":[{"path","bytes","sha256"}]}), every file must match it."""
        manifest = destination / "manifest.json"
        if not manifest.is_file():
            return
        try:
            files = json.loads(manifest.read_text(encoding="utf-8"))["files"]
        except (ValueError, KeyError) as exc:
            raise RemoteRenderError("remote manifest.json is unreadable") from exc
        for entry in files:
            target = (destination / entry["path"]).resolve(strict=False)
            if destination not in target.parents or not target.is_file():
                raise RemoteRenderError(f"manifest file missing or unsafe: {entry['path']}")
            digest = hashlib.sha256()
            with target.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            if target.stat().st_size != entry.get("bytes", target.stat().st_size) or digest.hexdigest() != entry.get("sha256", digest.hexdigest()):
                raise RemoteRenderError(f"downloaded file does not match remote manifest: {entry['path']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", default=os.environ.get("OPENMONTAGE_RENDER_IDENTITY", "/root/.ssh/openmontage_render_local"))
    parser.add_argument("--known-hosts", default=os.environ.get("OPENMONTAGE_RENDER_KNOWN_HOSTS", "/root/.ssh/openmontage_render_known_hosts"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OPENMONTAGE_RENDER_PORT", "17865")))
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("probe")
    for name in ("prepare", "status", "cancel", "cleanup", "logs"):
        p = sub.add_parser(name)
        p.add_argument("job_id")
        if name == "logs":
            p.add_argument("offset", nargs="?", type=int, default=None)
    p = sub.add_parser("upload"); p.add_argument("job_id"); p.add_argument("source", type=Path)
    p = sub.add_parser("submit"); p.add_argument("job_id"); p.add_argument("runtime_id")
    p = sub.add_parser("download"); p.add_argument("job_id"); p.add_argument("destination", type=Path)
    args = parser.parse_args()
    client = RemoteRenderClient(identity=args.identity, known_hosts=args.known_hosts, port=args.port)
    try:
        if args.operation == "probe": result = client.probe()
        elif args.operation == "prepare": result = client.prepare(args.job_id)
        elif args.operation == "upload": result = client.upload(args.job_id, args.source)
        elif args.operation == "submit": result = client.submit(args.job_id, args.runtime_id)
        elif args.operation == "status": result = client.status(args.job_id)
        elif args.operation == "cancel": result = client.cancel(args.job_id)
        elif args.operation == "cleanup": result = client.cleanup(args.job_id)
        elif args.operation == "logs": result = client.logs(args.job_id, args.offset)
        else: result = client.download(args.job_id, args.destination)
    except RemoteRenderError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
