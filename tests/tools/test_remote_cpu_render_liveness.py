"""Liveness limits of the render machine client (tools/video/remote_cpu_render.py): a link that stops moving must end in a RemoteRenderError within the limits, never hang.
The "ssh" here is a local Python process (a stub that sleeps, drips bytes or answers at once), so nothing touches the network."""
from __future__ import annotations

import json
import sys
import threading
import time

import pytest

from tools.video.remote_cpu_render import CleanupLedger, RemoteRenderClient, RemoteRenderError


class StubClient(RemoteRenderClient):
    """Client whose ssh command is `python -c <script>`; the real class constants are shortened so the tests take seconds."""
    CALL_TIMEOUT = 2
    CALL_DEADLINE = 6
    PROBE_TIMEOUT = 1
    PROBE_DEADLINE = 3
    STALL_WINDOW = 2
    STALL_MIN_BYTES = 1000
    STALL_GRACE = 1
    STREAM_DEADLINE = 8
    REPLY_TIMEOUT = 2

    def __init__(self, script: str) -> None:
        self.script = script
        self.identity = self.known_hosts = ""
        self.port = "0"
        self.host = "127.0.0.1"

    def _base(self) -> list[str]:
        return [sys.executable, "-c", self.script, "--"]


SLEEP = "import time; time.sleep(60)"
OK_JSON = "import sys, json; print(json.dumps({'ok': True, 'state': 'running'}))"


def test_request_returns_the_answer_of_a_healthy_link():
    assert StubClient(OK_JSON).request("status job1")["state"] == "running"


def test_request_gives_up_within_the_deadline_when_nothing_answers():
    t0 = time.monotonic()
    with pytest.raises(RemoteRenderError, match="timed out"):
        StubClient(SLEEP).request("status job1")          # read-only: 3 tries of 2 s with 2 s pauses would be 10 s, the deadline cuts it at 6 s
    assert time.monotonic() - t0 < 9


def test_probe_budget_is_short():
    t0 = time.monotonic()
    with pytest.raises(RemoteRenderError):
        StubClient(SLEEP).probe()
    assert time.monotonic() - t0 < 5


def test_submit_is_tried_once_only():
    t0 = time.monotonic()
    with pytest.raises(RemoteRenderError, match="timed out"):
        StubClient(SLEEP).request("submit job1 rt")
    assert time.monotonic() - t0 < 4.5                     # one try of 2 s, no retry (a retry could submit twice)


def test_upload_that_accepts_no_bytes_is_killed_by_the_watchdog(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    (src / "big.bin").write_bytes(b"x" * 4_000_000)       # more than a pipe holds: the writer blocks while the stub does not read
    t0 = time.monotonic()
    with pytest.raises(RemoteRenderError, match="upload stalled"):
        StubClient(SLEEP).upload("job1", src)
    assert time.monotonic() - t0 < 8


def test_upload_that_never_answers_after_the_last_byte_times_out(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    (src / "small.txt").write_text("hello")
    drain = "import sys, time; sys.stdin.buffer.read(); time.sleep(60)"      # reads everything, then says nothing
    t0 = time.monotonic()
    with pytest.raises(RemoteRenderError, match="upload reply"):
        StubClient(drain).upload("job1", src)
    assert time.monotonic() - t0 < 6


def test_upload_with_a_good_answer_succeeds(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    (src / "small.txt").write_text("hello")
    ok = "import sys, json; sys.stdin.buffer.read(); print(json.dumps({'ok': True}))"
    assert StubClient(ok).upload("job1", src)["ok"] is True


def test_download_that_sends_nothing_is_killed_by_the_watchdog(tmp_path):
    t0 = time.monotonic()
    with pytest.raises(RemoteRenderError, match="download stalled"):
        StubClient(SLEEP).download("job1", tmp_path / "out")
    assert time.monotonic() - t0 < 8


def test_download_that_drips_bytes_too_slowly_is_killed(tmp_path):
    import io
    import tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo("out.bin")
        info.size = 50_000
        tar.addfile(info, io.BytesIO(b"y" * 50_000))
    data = buf.getvalue()
    drip = ("import sys, time\n"
            f"data = {data!r}\n"
            "sys.stdout.buffer.write(data[:600]); sys.stdout.buffer.flush(); time.sleep(60)")     # 600 bytes, then silence
    t0 = time.monotonic()
    with pytest.raises(RemoteRenderError, match="download stalled"):
        StubClient(drip).download("job1", tmp_path / "out")
    assert time.monotonic() - t0 < 9


def test_download_of_a_good_archive_succeeds(tmp_path):
    import io
    import tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo("out.bin")
        info.size = 20_000
        tar.addfile(info, io.BytesIO(b"z" * 20_000))
    good = f"import sys\nsys.stdout.buffer.write({buf.getvalue()!r})"
    res = StubClient(good).download("job1", tmp_path / "out")
    assert res["bytes"] == 20_000 and (tmp_path / "out" / "out.bin").stat().st_size == 20_000


def test_a_slow_reply_after_the_last_byte_is_not_a_stall(tmp_path):
    """Regression (render agent, 2026-10-29): after the last upload byte no bytes move while the agent unpacks; only REPLY_TIMEOUT counts then, not the stall window."""
    src = tmp_path / "in"
    src.mkdir()
    (src / "small.txt").write_text("hello")
    slow = "import sys, json, time; sys.stdin.buffer.read(); time.sleep(3.5); print(json.dumps({'ok': True}))"     # STALL_WINDOW is 2 s, REPLY_TIMEOUT 2 s -> raise the latter for this test
    client = StubClient(slow)
    client.REPLY_TIMEOUT = 8
    assert client.upload("job1", src)["ok"] is True


def test_abort_ends_a_blocked_upload_at_once(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    (src / "big.bin").write_bytes(b"x" * 4_000_000)
    abort = threading.Event()
    threading.Timer(0.8, abort.set).start()
    t0 = time.monotonic()
    with pytest.raises(RemoteRenderError, match="aborted"):
        StubClient(SLEEP).upload("job1", src, abort=abort)
    assert time.monotonic() - t0 < 3


def test_abort_before_the_first_call_raises_without_running_anything():
    abort = threading.Event()
    abort.set()
    with pytest.raises(RemoteRenderError, match="aborted"):
        StubClient(SLEEP).request("status job1", abort=abort)


def test_upload_deadline_grows_with_the_package_but_stays_between_the_limits():
    c = RemoteRenderClient
    assert c.upload_deadline(1_000_000) == 120                       # small package: the minimum
    assert 600 < c.upload_deadline(31_800_000) < 1100                # the 31.8 MB lesson package at the design rate of 32 KiB/s
    assert c.upload_deadline(10 ** 12) == 3600                       # never longer than an hour


class ScriptedAgent(RemoteRenderClient):
    """Client whose control calls are answered by a script, to test retire()/sweep() against what agent/6 answers."""
    BUSY_PAUSE = 0.05
    RETIRE_WAIT = 3

    def __init__(self, answers):
        self.answers = answers       # {"cancel": [...], "status": [...], "cleanup": [...]}: each item a dict to return or a string error to raise
        self.calls = []

    def _next(self, name):
        self.calls.append(name)
        lst = self.answers.get(name, [])
        item = lst.pop(0) if len(lst) > 1 else (lst[0] if lst else {"ok": True})
        if isinstance(item, str):
            raise RemoteRenderError(item)
        return item

    def cancel(self, job_id, abort=None): return self._next("cancel")
    def status(self, job_id, abort=None): return self._next("status")
    def cleanup(self, job_id, abort=None): return self._next("cleanup")


def test_retire_waits_for_the_final_state_and_then_cleans(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    agent = ScriptedAgent({"cancel": [{"ok": True, "state": "canceling"}], "status": [{"state": "canceling"}, {"state": "canceled"}], "cleanup": [{"ok": True, "state": "removed"}]})
    res = agent.retire("j")
    assert res["cleaned"] and res["state"] == "canceled"
    assert agent.calls == ["cancel", "status", "status", "cleanup"]       # cleanup only after the final state


def test_retire_of_an_unknown_job_still_runs_cleanup(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    agent = ScriptedAgent({"cancel": ["unknown job"], "cleanup": [{"ok": True, "state": "removed"}]})
    assert agent.retire("j")["cleaned"] is True and agent.calls == ["cancel", "cleanup"]


def test_retire_retries_a_busy_cleanup_then_gives_up_with_a_note(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    agent = ScriptedAgent({"cancel": ["unknown job"], "cleanup": ["job busy: transfer or mutation in progress"]})
    res = agent.retire("j")
    assert res["cleaned"] is False and "busy" in res["note"] and agent.calls.count("cleanup") == agent.BUSY_RETRIES


def test_retire_does_not_clean_a_job_that_never_reaches_a_final_state(monkeypatch):
    clock = iter(range(0, 1000, 2))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    agent = ScriptedAgent({"cancel": [{"ok": True, "state": "canceling"}], "status": [{"state": "canceling"}]})
    res = agent.retire("j")
    assert res["cleaned"] is False and "final state" in res["note"] and "cleanup" not in agent.calls


def test_retire_of_a_completed_job_needs_no_cancel(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    agent = ScriptedAgent({"cleanup": [{"ok": True, "state": "removed"}]})
    assert agent.retire("j", cancel=False)["cleaned"] and agent.calls == ["cleanup"]


def _dead_pid():
    import subprocess
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def test_the_ledger_keeps_what_could_not_be_cleaned_and_sweep_retries_it(tmp_path, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    path = tmp_path / "remote_pending_cleanup.json"
    ledger = CleanupLedger(path)
    ledger.add("job-a", "cleanup busy")
    ledger.add("job-b", "channel down")
    assert set(json.loads(path.read_text(encoding="utf-8"))) == {"job-a", "job-b"}
    dead = _dead_pid()
    data = ledger.pending()
    for entry in data.values():                  # the render that owned them is gone (an earlier run)
        entry["pid"] = dead
    path.write_text(json.dumps(data), encoding="utf-8")
    agent = ScriptedAgent({"cancel": ["unknown job"], "cleanup": [{"ok": True, "state": "removed"}]})
    assert agent.sweep(ledger, log=lambda m: None) == 0 and ledger.pending() == {}
    ledger.add("job-c", "again")
    data = ledger.pending()
    data["job-c"]["pid"] = dead
    path.write_text(json.dumps(data), encoding="utf-8")
    stubborn = ScriptedAgent({"cancel": ["unknown job"], "cleanup": ["job busy: transfer or mutation in progress"]})
    assert stubborn.sweep(ledger, log=lambda m: None) == 1 and "job-c" in ledger.pending()


def test_sweep_leaves_a_job_alone_while_the_render_that_owns_it_is_still_running(tmp_path, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    ledger = CleanupLedger(tmp_path / "remote_pending_cleanup.json")
    ledger.add("job-live", "queueing")           # owner pid = this process, which is alive
    agent = ScriptedAgent({"cancel": ["unknown job"], "cleanup": [{"ok": True, "state": "removed"}]})
    assert agent.sweep(ledger, log=lambda m: None) == 1
    assert agent.calls == [] and "job-live" in ledger.pending()      # never cancelled, never cleaned: another live render is using it
