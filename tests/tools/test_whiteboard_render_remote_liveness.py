"""run_remote (docs/whiteboard_render.py) must not wait for ever on a render agent that stops answering, and must not leave jobs behind: a stuck queue phase, a silent status poll and a
failing channel all end in "failed" (the caller then renders locally) within the limits; a job that is given up is aborted and retired (cancel -> final state -> cleanup); a job that cannot be
cleaned goes into the pending-cleanup ledger; nothing is submitted after the job was abandoned; an unclear submit answer is settled by asking about the ORIGINAL id; the healthy path completes.
The client is a fake that answers like agent/6; nothing touches the network."""
from __future__ import annotations

import importlib
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "docs"))
sys.path.insert(0, str(ROOT))
wr = importlib.import_module("whiteboard_render")
from tools.video.remote_cpu_render import RemoteRenderError  # noqa: E402


class FakeClient:
    """Every call can be made to hang (until `release` is set or the caller aborts), fail with a message, or answer."""
    CALL_DEADLINE = 1
    REPLY_TIMEOUT = 0

    def __init__(self, *, hang=(), fail=None, script=None, retire_result=None):
        self.hang, self.fail, self.script = set(hang), dict(fail or {}), list(script or [])
        self.retire_result = retire_result
        self.release = threading.Event()
        self.calls = []

    @staticmethod
    def upload_deadline(size):
        return 1.0

    def _call(self, name, job_id, abort=None):
        self.calls.append((name, job_id))
        if name in self.hang:
            end = time.monotonic() + 30
            while not self.release.is_set() and time.monotonic() < end:
                if abort is not None and abort.is_set():
                    raise RemoteRenderError(f"aborted by the caller: {name}")
                time.sleep(0.02)
        if name in self.fail:
            raise RemoteRenderError(self.fail[name])

    def prepare(self, job_id, abort=None): self._call("prepare", job_id, abort); return {"ok": True}
    def upload(self, job_id, src, abort=None): self._call("upload", job_id, abort); return {"ok": True}
    def submit(self, job_id, runtime, abort=None): self._call("submit", job_id, abort); return {"ok": True}
    def logs(self, job_id, offset=None, abort=None): self._call("logs", job_id, abort); return {"ok": True, "log": "", "next": 0}
    def download(self, job_id, dest, abort=None): self._call("download", job_id, abort); return {"ok": True}

    def status(self, job_id, abort=None):
        self._call("status", job_id, abort)
        state = self.script.pop(0) if len(self.script) > 1 else (self.script[0] if self.script else "running")
        if state == "UNKNOWN":
            raise RemoteRenderError("unknown job")
        return {"ok": True, "state": state}

    def retire(self, job_id, cancel=True):
        self.calls.append(("retire", job_id, cancel))
        return self.retire_result or {"cleaned": True, "state": "canceled", "note": ""}

    def sweep(self, ledger, log=print):
        self.calls.append(("sweep",))
        return 0


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(wr, "build_remote_input", lambda dest, props, pub, spec: dest.mkdir(parents=True))
    monkeypatch.setattr(wr, "composer_hash", lambda: "h")
    monkeypatch.setattr(wr, "QUEUE_STAGE_SLACK", 0)
    proj = tmp_path / "proj"
    (proj / "renders").mkdir(parents=True)
    args = SimpleNamespace(remote_runtime="rt", remote_timeout=60, remote_poll_seconds=0.2, remote_queue_seconds=None, remote_silent_seconds=1.5)
    group = {"id": "j1", "chunks": [], "stills": [], "outputs": [], "expected": {}}
    installed = []

    def run(client, **over):
        for k, v in over.items():
            setattr(args, k, v)
        backend = {"client": client, "features": {"log_offset"}, "tabs": 2, "workers": 4, "render": {}}
        t0 = time.monotonic()
        failed = wr.run_remote(proj, args, backend, tmp_path / "props.json", tmp_path / "public", [group], installed.append, tmp_path)
        return failed, time.monotonic() - t0

    def ledger():
        f = proj / "renders" / "remote_pending_cleanup.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    return SimpleNamespace(run=run, installed=installed, proj=proj, ledger=ledger)


def calls_named(client, name):
    return [c for c in client.calls if c[0] == name]


def test_healthy_job_completes_is_installed_and_cleaned_without_a_cancel(env):
    client = FakeClient(script=["queued", "running", "completed"])
    failed, _ = env.run(client)
    assert failed == set() and len(env.installed) == 1 and env.installed[0]["rendered_by"] == "remote"
    assert [c[2] for c in calls_named(client, "retire")] == [False]      # finished normally: cleanup only, no cancel
    assert env.ledger() == {}


def test_a_queue_phase_past_its_deadline_is_abandoned_aborted_and_retired(env, capsys):
    client = FakeClient(hang={"upload"})                                 # upload budget: 1 s + 0 s reply + 0 slack
    try:
        failed, took = env.run(client)
    finally:
        client.release.set()
    assert failed == {"j1"} and took < 8
    out = capsys.readouterr().out
    assert "preparing j1 (om-" in out and "stuck at upload" in out
    assert [c[2] for c in calls_named(client, "retire")] == [True]
    assert not calls_named(client, "submit")                             # abandoned in the upload phase: never submitted
    assert env.ledger() == {}
    log = (env.proj / "renders" / "remote_jobs.log").read_text(encoding="utf-8")
    assert "preparing" in log and "stuck at upload" in log and "retired" in log


def test_nothing_is_submitted_after_the_job_was_abandoned(env):
    client = FakeClient(hang={"prepare"})
    try:
        failed, _ = env.run(client)
        client.release.set()
        time.sleep(0.3)                                                  # let the stuck thread come back
    finally:
        client.release.set()
    assert failed == {"j1"} and not calls_named(client, "upload") and not calls_named(client, "submit")


def test_the_optional_cap_on_queueing_abandons_a_slow_job(env, capsys):
    client = FakeClient(hang={"upload"})
    client.upload_deadline = staticmethod(lambda size: 100.0)            # the phase deadline alone would wait 100 s
    try:
        failed, took = env.run(client, remote_queue_seconds=1.0)
    finally:
        client.release.set()
    assert failed == {"j1"} and took < 8 and "not queued within 1s" in capsys.readouterr().out


def test_an_unclear_submit_answer_is_settled_by_asking_about_the_original_id(env, capsys):
    client = FakeClient(fail={"submit": "timed out after 30s: submit"}, script=["queued", "running", "completed"])
    failed, _ = env.run(client)
    assert failed == set() and len(env.installed) == 1                    # the job had been queued: carry on, no second submit
    assert len(calls_named(client, "submit")) == 1
    assert "submit answer was unclear" in (env.proj / "renders" / "remote_jobs.log").read_text(encoding="utf-8")


def test_an_unclear_submit_answer_and_an_unknown_job_means_it_was_not_queued(env, capsys):
    client = FakeClient(fail={"submit": "timed out after 30s: submit"}, script=["UNKNOWN"])
    failed, _ = env.run(client)
    assert failed == {"j1"} and "could not queue j1 (stage submit)" in capsys.readouterr().out
    assert len(calls_named(client, "submit")) == 1 and [c[2] for c in calls_named(client, "retire")] == [True]


def test_an_unclear_submit_answer_and_a_failed_job_is_a_failure(env):
    client = FakeClient(fail={"submit": "timed out after 30s: submit"}, script=["failed"])
    failed, _ = env.run(client)
    assert failed == {"j1"}


def test_status_that_stops_answering_is_given_up_after_the_silence_limit(env, capsys):
    client = FakeClient(hang={"status"})
    try:
        failed, took = env.run(client)
    finally:
        client.release.set()
    assert failed == {"j1"} and took < 8
    assert "no answer from the render agent" in capsys.readouterr().out
    assert [c[2] for c in calls_named(client, "retire")] == [True]


def test_logs_that_hang_never_cancel_a_job_whose_status_answers(env):
    client = FakeClient(hang={"logs"}, script=["running", "running", "running", "completed"])
    try:
        failed, took = env.run(client)
    finally:
        client.release.set()
    assert failed == set() and len(env.installed) == 1 and took < 8


def test_channel_that_keeps_failing_is_given_up(env, capsys):
    client = FakeClient(fail={"status": "timed out after 30s: status"})
    failed, took = env.run(client)
    assert failed == {"j1"} and took < 8
    assert "channel problem" in capsys.readouterr().out


def test_prepare_that_fails_is_reported_with_its_stage_and_retired(env, capsys):
    client = FakeClient(fail={"prepare": "timed out after 30s: prepare"})
    failed, _ = env.run(client)
    assert failed == {"j1"}
    assert "could not queue j1 (stage prepare)" in capsys.readouterr().out and [c[2] for c in calls_named(client, "retire")] == [True]


def test_a_job_that_cannot_be_cleaned_stays_in_the_ledger_and_is_reported(env, capsys):
    client = FakeClient(fail={"prepare": "timed out after 30s: prepare"}, retire_result={"cleaned": False, "state": "canceling", "note": "cleanup still busy: job busy"})
    failed, _ = env.run(client)
    assert failed == {"j1"}
    entries = env.ledger()
    assert len(entries) == 1 and "busy" in next(iter(entries.values()))["reason"]
    out = capsys.readouterr().out
    assert "is not cleaned up yet" in out and "not cleaned up on the render machine yet" in out


def test_the_next_run_sweeps_the_ledger(env):
    ledger_file = env.proj / "renders" / "remote_pending_cleanup.json"
    ledger_file.write_text(json.dumps({"om-old-job": {"since": "2026-10-28T00:00:00", "reason": "cleanup busy", "pid": 1}}), encoding="utf-8")
    client = FakeClient(script=["queued", "running", "completed"])
    env.run(client)
    assert calls_named(client, "sweep")
