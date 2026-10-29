#!/usr/bin/env python3
"""144-side client for the forced local OpenMontage render account."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import threading
import time
from pathlib import Path


class RemoteRenderError(RuntimeError):
    pass


_REPO_ENV = Path(__file__).resolve().parents[2] / ".env"


def render_setting(name: str) -> str:
    """Channel settings (port, key file paths) come from the environment, else from the repo's untracked .env.
    The repository carries no built-in values for them."""
    value = os.environ.get(name)
    if not value and _REPO_ENV.is_file():
        for line in _REPO_ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            key, sep, rest = line.partition("=")
            if sep and key.strip() == name:
                value = rest.strip().strip("'\"")
                break
    if not value:
        raise RemoteRenderError(f"{name} is not set (put it in the environment or in the repo's untracked .env)")
    return value


# Messages that mean "the connection hiccuped", not "the request is wrong".  Safe to retry for idempotent requests.
TRANSIENT = ("connection reset", "connection refused", "connection closed", "timed out", "broken pipe", "kex_exchange",
             "no route to host", "temporarily unavailable", "ssh: connect")
IDEMPOTENT = {"probe", "status", "logs", "cancel", "cleanup"}


class _StreamWatch:
    """Liveness guard of one upload or download: a link that still accepts a few bytes now and then is not "alive".  A background thread kills `process` (the ssh) when
    (a) fewer than `min_bytes` moved in the last `window` seconds (`grace` extra seconds before the very first byte), or (b) the stream ran longer than `deadline` seconds.
    The blocked read or write then fails at once; `reason` tells why, so the caller can raise a clear error instead of waiting for ever (2026-10-28: a stalled upload sat 29 minutes)."""

    def __init__(self, process, *, label: str, window: float, min_bytes: int, deadline: float, grace: float = 0.0, abort: threading.Event | None = None) -> None:
        self.process, self.label, self.window, self.min_bytes, self.deadline, self.grace, self.abort = process, label, window, min_bytes, deadline, grace, abort
        self.t0 = time.monotonic()
        self.moved = 0
        self.reason: str | None = None
        self._samples: list[tuple[float, int]] = [(self.t0, 0)]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"stream-watch-{label}", daemon=True)
        self._thread.start()

    def add(self, n: int) -> None:
        self.moved += n

    def _kill(self, reason: str) -> None:
        self.reason = reason
        try:
            self.process.kill()
        except OSError:
            pass

    def _run(self) -> None:
        while not self._stop.wait(0.25):
            now = time.monotonic()
            self._samples.append((now, self.moved))
            if self.abort is not None and self.abort.is_set():
                return self._kill("aborted by the caller")
            if now - self.t0 > self.deadline:
                return self._kill(f"{self.label} took longer than {self.deadline:.0f}s in total")
            if now - self.t0 < self.window + (self.grace if self.moved == 0 else 0.0):
                continue
            past = [m for t, m in self._samples if t <= now - self.window]
            self._samples = [(t, m) for t, m in self._samples if t >= now - self.window - 1.0] or self._samples[-1:]
            if past and self.moved - past[-1] < self.min_bytes:
                return self._kill(f"{self.label} moved only {self.moved - past[-1]} bytes in the last {self.window:.0f}s (needs {self.min_bytes})")

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(2)


class _CountingWriter:
    def __init__(self, raw, watch: _StreamWatch) -> None:
        self._raw, self._watch = raw, watch

    def write(self, data) -> int:
        n = self._raw.write(data)
        self._watch.add(n if isinstance(n, int) else len(data))   # what the local pipe accepted: progress of the link as seen from here, not a confirmation that the render machine stored it
        return n

    def flush(self) -> None:
        self._raw.flush()


class _CountingReader:
    def __init__(self, raw, watch: _StreamWatch) -> None:
        self._raw, self._watch = raw, watch

    def read(self, size: int = -1) -> bytes:
        data = self._raw.read(size)
        self._watch.add(len(data))
        return data


TERMINAL = {"canceled", "completed", "failed", "unknown"}   # "unknown" = the render agent has no such job (never submitted, or already cleaned)


class CleanupLedger:
    """Jobs whose cleanup could not be finished (a busy upload lock, a cancel that did not reach a final state, a dead channel).  Since agent/6 the render machine no longer removes
    old jobs by itself (the 6 h implicit cleanup was dropped, and one upload may hold up to 48 GiB), so every job id the client has touched is either cleaned or written here and retried
    by the next run (`sweep`).  One json file {job id: {"reason", "since"}}; written atomically."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def pending(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(self, job_id: str, reason: str) -> None:
        with self._lock:
            data = self.pending()
            entry = data.setdefault(job_id, {"since": time.strftime("%Y-%m-%dT%H:%M:%S")})
            entry["reason"], entry["pid"] = reason[:300], os.getpid()   # the process that owns the job: a sweep must not retire a job another live render still uses
            self._write(data)

    @staticmethod
    def owner_alive(entry: dict) -> bool:
        pid = entry.get("pid")
        if not isinstance(pid, int) or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def remove(self, job_id: str) -> None:
        with self._lock:
            data = self.pending()
            if data.pop(job_id, None) is not None:
                self._write(data)


class RemoteRenderClient:
    # Liveness limits (2026-10-29, after the connection stalls of 2026-10-28; the numbers follow the render agent's advice in docs/remote-render-replies/2026-10-28-connection-stalls.md).
    # A call that does not answer in time fails with RemoteRenderError instead of waiting for ever; the callers (docs/whiteboard_render.py) then fall back to the local render.
    CONNECT_TIMEOUT = 15            # ssh handshake
    ALIVE_INTERVAL, ALIVE_COUNT = 10, 3      # ssh notices a dead link after about 30 s
    CALL_TIMEOUT = 30               # one control request: prepare / submit / status / logs / cancel / cleanup
    CALL_DEADLINE = 75              # wall-clock budget of one request including its retries (read-only requests are retried twice, 2 s apart)
    PROBE_TIMEOUT, PROBE_DEADLINE = 10, 20   # a healthy probe took 3-5 s
    STALL_WINDOW = 30               # a stream (upload / download) must move STALL_MIN_BYTES in every STALL_WINDOW seconds
    STALL_MIN_BYTES = 256 * 1024
    STALL_GRACE = 30                # download only: extra seconds before the first byte (the agent packs the output first)
    STREAM_DEADLINE = 900           # one whole download
    UPLOAD_MIN_RATE = 32 * 1024     # design value, NOT a measured floor: an upload may take up to 60 s + size / UPLOAD_MIN_RATE, between 120 s and 3600 s (healthy: 31.8 MB in 7.2 s)
    UPLOAD_DEADLINE_MIN, UPLOAD_DEADLINE_MAX = 120, 3600
    REPLY_TIMEOUT = 120             # after the last byte of an upload: the agent unpacks it and answers
    RETIRE_WAIT = 40                # retire(): how long to wait for a cancelled job to reach a final state (the agent: SIGTERM, SIGKILL after 10 s)
    BUSY_RETRIES, BUSY_PAUSE = 3, 5  # retire(): cleanup answers "busy" while an upload or download still holds the job lock

    @classmethod
    def upload_deadline(cls, size: int) -> float:
        return float(max(cls.UPLOAD_DEADLINE_MIN, min(cls.UPLOAD_DEADLINE_MAX, 60 + size / cls.UPLOAD_MIN_RATE)))

    def __init__(self, *, identity: str | None = None, known_hosts: str | None = None, port: int | str | None = None, host: str = "127.0.0.1") -> None:
        self.identity = str(Path(identity or render_setting("OPENMONTAGE_RENDER_IDENTITY")).expanduser())
        self.known_hosts = str(Path(known_hosts or render_setting("OPENMONTAGE_RENDER_KNOWN_HOSTS")).expanduser())
        self.port = str(port or render_setting("OPENMONTAGE_RENDER_PORT"))
        self.host = host

    def _base(self) -> list[str]:
        return [
            "/usr/bin/ssh", "-p", self.port, "-i", self.identity,
            "-o", "BatchMode=yes", "-o", f"ConnectTimeout={self.CONNECT_TIMEOUT}", "-o", f"ServerAliveInterval={self.ALIVE_INTERVAL}", "-o", f"ServerAliveCountMax={self.ALIVE_COUNT}",
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

    def request(self, command: str, *, timeout: float | None = None, attempts: int | None = None, deadline: float | None = None, abort: threading.Event | None = None) -> dict:
        """One protocol request.  Each try is limited to `timeout` seconds and the whole request (tries and pauses) to `deadline` seconds; a request that does not answer
        in time raises RemoteRenderError.  Idempotent requests (probe/status/logs/cancel/cleanup) are retried (twice, 2 s apart) on transient errors; the others are tried once."""
        name = command.split(" ", 1)[0]
        if timeout is None:
            timeout = self.PROBE_TIMEOUT if name == "probe" else self.CALL_TIMEOUT
        if deadline is None:
            deadline = self.PROBE_DEADLINE if name == "probe" else self.CALL_DEADLINE
        if attempts is None:
            attempts = 3 if name in IDEMPOTENT else 1
        start = time.monotonic()
        last: RemoteRenderError | None = None
        for attempt in range(attempts):
            if abort is not None and abort.is_set():
                raise RemoteRenderError(f"aborted by the caller: {name}")
            if attempt:
                if deadline - (time.monotonic() - start) <= 3:
                    break
                time.sleep(2)
            per_try = min(timeout, deadline - (time.monotonic() - start))
            if per_try <= 0:
                break
            try:
                result = subprocess.run(self._base() + [command], capture_output=True, check=False, timeout=per_try)
                if result.returncode:
                    raise RemoteRenderError(result.stderr.decode("utf-8", "replace")[-500:] or result.stdout.decode("utf-8", "replace")[-500:])
                return self._json_output(result.stdout)
            except subprocess.TimeoutExpired as exc:
                last = RemoteRenderError(f"timed out after {per_try:.0f}s: {name}")
                last.__cause__ = exc
            except RemoteRenderError as exc:
                last = exc
                if not any(t in str(exc).lower() for t in TRANSIENT):
                    raise
        if last is None:
            last = RemoteRenderError(f"timed out: {name} (no time left in the {deadline:.0f}s budget)")
        raise last

    @staticmethod
    def _communicate(process, timeout: float, abort: threading.Event | None, what: str):
        """process.communicate() in 1 s slices: an abort kills the process, the deadline raises RemoteRenderError("timed out: ...")."""
        end = time.monotonic() + timeout
        while True:
            if abort is not None and abort.is_set():
                process.kill()
                process.communicate()
                raise RemoteRenderError(f"aborted by the caller: {what}")
            remaining = end - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.communicate()
                raise RemoteRenderError(f"timed out: {what} (no end within {timeout:.0f}s)")
            try:
                return process.communicate(timeout=min(1.0, remaining))
            except subprocess.TimeoutExpired:
                continue

    def probe(self) -> dict:
        return self.request("probe")

    def prepare(self, job_id: str, abort: threading.Event | None = None) -> dict:
        return self.request(f"prepare {job_id}", abort=abort)

    def upload(self, job_id: str, source: Path, abort: threading.Event | None = None) -> dict:
        source = source.resolve()
        if not source.is_dir() or source.is_symlink():
            raise RemoteRenderError("upload source must be a directory")
        size = sum(p.stat().st_size for p in source.rglob("*") if p.is_file() and not p.is_symlink())
        if abort is not None and abort.is_set():
            raise RemoteRenderError("aborted by the caller: upload")
        process = subprocess.Popen(self._base() + [f"upload {job_id}"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert process.stdin is not None
        watch = _StreamWatch(process, label="upload", window=self.STALL_WINDOW, min_bytes=self.STALL_MIN_BYTES, deadline=self.upload_deadline(size), abort=abort)
        try:
            try:
                with tarfile.open(fileobj=_CountingWriter(process.stdin, watch), mode="w|", dereference=True) as archive:
                    for path in sorted(source.rglob("*")):
                        if path.is_symlink():
                            raise RemoteRenderError(f"upload source contains a symlink: {path}")
                        archive.add(path, arcname=path.relative_to(source).as_posix(), recursive=False)
            except Exception as exc:
                process.kill()
                process.wait()
                if watch.reason:   # the watchdog killed the ssh: the write that was blocked failed
                    raise RemoteRenderError(f"upload stalled: {watch.reason}") from exc
                raise
            watch.stop()   # the last byte is written: from here on only REPLY_TIMEOUT counts (the agent unpacks the package and answers; no bytes move meanwhile)
            if watch.reason:
                process.kill()
                process.wait()
                raise RemoteRenderError(f"upload stalled: {watch.reason}")
            try:
                process.stdin.close()
            except OSError:
                pass
            process.stdin = None
            stdout, stderr = self._communicate(process, self.REPLY_TIMEOUT, abort, "upload reply")
            if process.returncode:
                raise RemoteRenderError(stderr.decode("utf-8", "replace")[-500:] or stdout.decode("utf-8", "replace")[-500:])
            return self._json_output(stdout)
        finally:
            watch.stop()

    def submit(self, job_id: str, runtime_id: str, abort: threading.Event | None = None) -> dict:
        return self.request(f"submit {job_id} {runtime_id}", abort=abort)

    def status(self, job_id: str, abort: threading.Event | None = None) -> dict:
        return self.request(f"status {job_id}", abort=abort)

    def cancel(self, job_id: str, abort: threading.Event | None = None) -> dict:
        return self.request(f"cancel {job_id}", abort=abort)

    def cleanup(self, job_id: str, abort: threading.Event | None = None) -> dict:
        return self.request(f"cleanup {job_id}", abort=abort)

    def logs(self, job_id: str, offset: int | None = None, abort: threading.Event | None = None) -> dict:
        """Whole log, or (when the agent advertises `log_offset`) only the text after `offset`; the reply then carries `next`."""
        return self.request(f"logs {job_id}" + ("" if offset is None else f" {int(offset)}"), abort=abort)

    def download(self, job_id: str, destination: Path, abort: threading.Event | None = None) -> dict:
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(self._base() + [f"download {job_id}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert process.stdout is not None
        watch = _StreamWatch(process, label="download", window=self.STALL_WINDOW, min_bytes=self.STALL_MIN_BYTES, deadline=self.STREAM_DEADLINE, grace=self.STALL_GRACE, abort=abort)
        total = 0
        try:
            try:
                with tarfile.open(fileobj=_CountingReader(process.stdout, watch), mode="r|*") as archive:
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
            except (tarfile.TarError, OSError, ValueError) as exc:
                process.kill()
                process.wait()
                if watch.reason:   # the watchdog killed the ssh: the read that was blocked ended early
                    raise RemoteRenderError(f"download stalled: {watch.reason}") from exc
                if isinstance(exc, tarfile.TarError):
                    raise RemoteRenderError("invalid remote output archive") from exc
                raise
            watch.stop()   # the archive is complete: only the end of the ssh process is awaited now
            if watch.reason:
                raise RemoteRenderError(f"download stalled: {watch.reason}")
            _, stderr = self._communicate(process, 60, abort, "download end")
            if process.returncode:
                raise RemoteRenderError(stderr.decode("utf-8", "replace")[-500:])
            self._verify_manifest(destination)
            return {"ok": True, "job_id": job_id, "bytes": total, "destination": str(destination)}
        finally:
            watch.stop()

    def retire(self, job_id: str, *, cancel: bool = True) -> dict:
        """Take a job off the render machine for good: cancel it (unless it finished normally: cancel=False), wait for a final state, then cleanup.
        Since agent/6 nothing else removes it.  cancel on a running job answers "canceling" (SIGTERM, SIGKILL after 10 s), and cleanup refuses a job that is not final or whose upload or download
        still holds the lock ("busy"), so the order matters.  Returns {"cleaned": bool, "state": last known state, "note": why not}; the caller writes a job that is not cleaned into a CleanupLedger."""
        state: str | None = None
        if cancel:
            try:
                state = self.cancel(job_id).get("state")
            except RemoteRenderError as exc:
                if "unknown job" in str(exc).lower():
                    state = "unknown"
                else:
                    return {"cleaned": False, "state": None, "note": f"cancel failed: {str(exc)[:160]}"}
            end = time.monotonic() + self.RETIRE_WAIT
            while state not in TERMINAL:
                if time.monotonic() > end:
                    return {"cleaned": False, "state": state, "note": f"not in a final state {self.RETIRE_WAIT}s after cancel"}
                time.sleep(2)
                try:
                    state = self.status(job_id).get("state")
                except RemoteRenderError as exc:
                    if "unknown job" in str(exc).lower():
                        state = "unknown"
                    # any other error: the channel hiccuped, ask again until the time is up
        note = ""
        for attempt in range(self.BUSY_RETRIES):
            try:
                self.cleanup(job_id)
                return {"cleaned": True, "state": state, "note": ""}
            except RemoteRenderError as exc:
                note = str(exc)[:160]
                if "busy" not in note.lower():
                    return {"cleaned": False, "state": state, "note": f"cleanup failed: {note}"}
                if attempt + 1 < self.BUSY_RETRIES:
                    time.sleep(self.BUSY_PAUSE)
        return {"cleaned": False, "state": state, "note": f"cleanup still busy: {note}"}

    def sweep(self, ledger: CleanupLedger, log=print) -> int:
        """Retry the cleanup of every job in the ledger; returns how many are still pending."""
        for job_id, entry in list(ledger.pending().items()):
            if ledger.owner_alive(entry):   # an earlier or parallel render process of this project that is still running owns it
                log(f"remote: job {job_id} belongs to a render that is still running (pid {entry.get('pid')}); left alone")
                continue
            res = self.retire(job_id)
            if res["cleaned"]:
                ledger.remove(job_id)
                log(f"remote: cleaned up earlier job {job_id}")
            else:
                log(f"remote: job {job_id} is still not cleaned up ({res['note']})")
        return len(ledger.pending())

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
    parser.add_argument("--identity", default=None, help="default: OPENMONTAGE_RENDER_IDENTITY")
    parser.add_argument("--known-hosts", default=None, help="default: OPENMONTAGE_RENDER_KNOWN_HOSTS")
    parser.add_argument("--port", type=int, default=None, help="default: OPENMONTAGE_RENDER_PORT")
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
    p = sub.add_parser("retire", help="cancel (unless --no-cancel), wait for a final state, cleanup"); p.add_argument("job_id"); p.add_argument("--no-cancel", action="store_true")
    p = sub.add_parser("sweep", help="retry the cleanup of every job in a pending-cleanup ledger (projects/<lesson>/renders/remote_pending_cleanup.json)"); p.add_argument("ledger", type=Path)
    args = parser.parse_args()
    try:
        client = RemoteRenderClient(identity=args.identity, known_hosts=args.known_hosts, port=args.port)
        if args.operation == "probe": result = client.probe()
        elif args.operation == "prepare": result = client.prepare(args.job_id)
        elif args.operation == "upload": result = client.upload(args.job_id, args.source)
        elif args.operation == "submit": result = client.submit(args.job_id, args.runtime_id)
        elif args.operation == "status": result = client.status(args.job_id)
        elif args.operation == "cancel": result = client.cancel(args.job_id)
        elif args.operation == "cleanup": result = client.cleanup(args.job_id)
        elif args.operation == "logs": result = client.logs(args.job_id, args.offset)
        elif args.operation == "retire": result = client.retire(args.job_id, cancel=not args.no_cancel)
        elif args.operation == "sweep":
            ledger = CleanupLedger(args.ledger)
            result = {"ok": True, "still_pending": client.sweep(ledger), "ledger": str(args.ledger)}
        else: result = client.download(args.job_id, args.destination)
    except RemoteRenderError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
