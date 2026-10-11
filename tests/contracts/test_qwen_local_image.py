"""Contract tests for the local Qwen-Image tool.

A fake CLI stands in for /opt/h3-api/qwen, so nothing here touches the network or
the GPU server. Run: pytest tests/contracts/test_qwen_local_image.py -v
"""

import json
import stat
import textwrap
from pathlib import Path

import pytest
from PIL import Image

from lib.scoring import score_provider
from tools.base_tool import ToolRuntime, ToolStatus
from tools.graphics.dashscope_image import DashscopeImage
from tools.graphics.qwen_local_image import QwenLocalImage

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

FAKE_CLI = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    from pathlib import Path
    S = Path(os.environ["FAKE_STATE"]); mode = os.environ.get("FAKE_MODE", "ok")
    a = sys.argv[1:]; cmd = a[0]
    with open(S / "calls.log", "a") as f:
        f.write(json.dumps(a) + "\\n")
    val = lambda k: a[a.index(k) + 1]
    if cmd == "submit":
        if mode == "429_once" and not (S / "seen429").exists():
            (S / "seen429").write_text("1"); sys.stderr.write("HTTP 429 Retry-After: 10\\n"); sys.exit(1)
        print(json.dumps({"id": "job" + val("--request-id")[-8:], "status": "queued"}))
    elif cmd == "get":
        n = int((S / "gets").read_text()) if (S / "gets").exists() else 0
        (S / "gets").write_text(str(n + 1))
        status = "running" if n < 1 else ("needs_attention" if mode == "needs_attention" else "completed")
        print(json.dumps({"id": val("--job"), "status": status,
                          "parameters": {"seed": 7, "width": 8, "height": 8}, "files": [{"sha256": "x"}]}))
    elif cmd == "download":
        import base64
        Path(val("--output")).write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
        print("{}")
    """
)


@pytest.fixture
def fake(tmp_path, monkeypatch):
    cli = tmp_path / "fake_qwen"
    cli.write_text(FAKE_CLI)
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("QWEN_LOCAL_CLI", str(cli))
    monkeypatch.setenv("FAKE_STATE", str(state))
    monkeypatch.setattr("time.sleep", lambda s: None)
    return state


def calls(state, cmd):
    log = state / "calls.log"
    rows = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    return [r for r in rows if r[0] == cmd]


def ref(tmp_path, name):
    p = tmp_path / name
    Image.new("RGB", (16, 16), "white").save(p)
    return str(p)


class TestContract:
    def test_attributes(self):
        tool = QwenLocalImage()
        assert tool.name == "qwen_local_image" and tool.capability == "image_generation"
        assert tool.provider == "qwen_local" and tool.runtime == ToolRuntime.LOCAL_GPU
        assert tool.estimate_cost({"prompt": "x"}) == 0.0
        assert tool.fallback == "dashscope_image"
        assert "prompt" in tool.input_schema["required"]
        for field in ("image_paths", "reference_images", "negative_prompt", "seed", "resolution", "aspect_ratio", "output_path"):
            assert field in tool.input_schema["properties"]

    def test_skill_exists(self):
        assert QwenLocalImage().agent_skills == ["qwen-local-image"]
        skill = PROJECT_ROOT / ".agents" / "skills" / "qwen-local-image" / "SKILL.md"
        assert skill.exists() and "QWEN_LOCAL_CLI" in skill.read_text(encoding="utf-8")

    def test_unavailable_without_cli(self, monkeypatch):
        monkeypatch.setenv("QWEN_LOCAL_CLI", "/nonexistent/qwen")
        tool = QwenLocalImage()
        assert tool.get_status() == ToolStatus.UNAVAILABLE
        assert tool.execute({"prompt": "x"}).success is False

    def test_does_not_outrank_commercial_default(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "dummy")
        ctx = {"prompt": "line art", "asset_type": "image"}
        assert score_provider(QwenLocalImage(), ctx).weighted_score < score_provider(DashscopeImage(), ctx).weighted_score


class TestExecution:
    def test_text_to_image_flow_and_ledger(self, fake, tmp_path):
        out = tmp_path / "a.png"
        r = QwenLocalImage().execute({"prompt": "cat", "negative_prompt": "text", "seed": 5, "aspect_ratio": "16:9", "output_path": str(out)})
        assert r.success, r.error
        assert out.exists() and r.cost_usd == 0.0
        submit = calls(fake, "submit")[0]
        assert "--aspect-ratio" in submit and "--image" not in submit and "text_to_image" in submit
        ledger = json.loads((tmp_path / "a.png.qwen_job.json").read_text())
        assert ledger["status"] == "completed" and ledger["request_id"].startswith("om-")
        assert not list(tmp_path.glob("*.prompt.txt"))

    def test_image_edit_with_references(self, fake, tmp_path):
        r = QwenLocalImage().execute({"prompt": "图1中的小明", "aspect_ratio": "16:9", "output_path": str(tmp_path / "b.png"),
                                      "image_paths": [ref(tmp_path, "r1.png"), ref(tmp_path, "r2.png")]})
        assert r.success, r.error
        submit = calls(fake, "submit")[0]
        assert "image_edit" in submit and "--image" in submit and submit.count("--reference") == 1 and "--aspect-ratio" not in submit
        assert any("aspect_ratio ignored" in n for n in r.data["notes"])

    def test_same_input_reuses_output_and_new_seed_regenerates(self, fake, tmp_path):
        tool, out = QwenLocalImage(), str(tmp_path / "c.png")
        assert tool.execute({"prompt": "cat", "seed": 1, "output_path": out}).success
        again = tool.execute({"prompt": "cat", "seed": 1, "output_path": out})
        assert again.success and again.data["reused_existing_output"] is True
        assert len(calls(fake, "submit")) == 1
        (fake / "gets").unlink()
        assert tool.execute({"prompt": "cat", "seed": 2, "output_path": out}).success
        ids = [c[c.index("--request-id") + 1] for c in calls(fake, "submit")]
        assert len(ids) == 2 and ids[0] != ids[1]

    def test_429_retries_with_same_request_id(self, fake, tmp_path, monkeypatch):
        monkeypatch.setenv("FAKE_MODE", "429_once")
        r = QwenLocalImage().execute({"prompt": "cat", "output_path": str(tmp_path / "d.png")})
        assert r.success, r.error
        ids = [c[c.index("--request-id") + 1] for c in calls(fake, "submit")]
        assert len(ids) == 2 and ids[0] == ids[1]

    def test_needs_attention_is_not_resubmitted(self, fake, tmp_path, monkeypatch):
        monkeypatch.setenv("FAKE_MODE", "needs_attention")
        r = QwenLocalImage().execute({"prompt": "cat", "output_path": str(tmp_path / "e.png")})
        assert r.success is False and "maintainer" in r.error
        assert len(calls(fake, "submit")) == 1
        assert json.loads((tmp_path / "e.png.qwen_job.json").read_text())["status"] == "needs_attention"

    def test_input_validation(self, fake, tmp_path):
        tool = QwenLocalImage()
        assert "At most 4" in tool.execute({"prompt": "x", "image_paths": [ref(tmp_path, f"{i}.png") for i in range(5)]}).error
        assert "not found" in tool.execute({"prompt": "x", "image_paths": [str(tmp_path / "missing.png")]}).error
        assert tool.execute({"prompt": "  "}).success is False
        assert not calls(fake, "submit")
