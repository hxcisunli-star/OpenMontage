import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SOURCE = Path(__file__).resolve().parents[2] / "docs/whiteboard/ebook"
sys.path.insert(0, str(SOURCE))
import set_labs


@pytest.fixture
def files(tmp_path):
    config = tmp_path / "site/assets/lab-config.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"block_paste": false}\n')
    books = tmp_path / "books.yaml"
    books.write_text('# 保留标题\nseries:\n  name: 书 # 保留注释\nbooks: []\n', encoding="utf-8")
    return config, books


def args(files):
    config, books = files
    return ["--site-dir", str(config.parents[1]), "--yaml", str(books)]


def test_add_labs_preserves_existing_text(files, capsys):
    config, books = files
    before = books.read_bytes()
    set_labs.main(args(files) + ["--paste", "block"])
    assert capsys.readouterr().out == "粘贴：禁止\n"
    assert books.read_bytes() == before + b"labs:\n  block_paste: true\n"
    assert json.loads(config.read_text()) == {"block_paste": True}


@pytest.mark.parametrize("text", [
    'series: 书\nlabs: # 开关\n  block_paste: false  # 保留\n  other: 5\nbooks: []\n',
    '"labs":\n    "block_paste" : false # 注释\nbooks: []\n',
    'labs: {block_paste: false, other: [1, 2]} # 保留\n',
    'labs:\r\n  block_paste: false # 保留\r\nbooks: []\r\n',
    'labs:\n  block_paste: !!bool false # 显式标签\n',
])
def test_existing_value_preserves_comments_and_layout(text):
    assert set_labs.edit_yaml(text, True) == text.replace("false", "true")


@pytest.mark.parametrize("text", [
    'books: []', 'books: []\n...\n', '---\nbooks: []\n...\n# 尾注释\n',
    'books: []\r\n', 'labs: {} # 空段\nbooks: []\n', 'labs: {other: 1}\nbooks: []\n',
    'labs:\n  # 段内注释\n  other: 1 # 字段注释\nbooks: []\n',
    '{books: []}', '{}', 'labs: {# 注释\n}\n',
    'description: |\n  第一行\n  最后一行',
])
def test_various_valid_yaml_layouts(text):
    updated = set_labs.edit_yaml(text, True)
    expected = yaml.safe_load(text)
    expected.setdefault("labs", {})["block_paste"] = True
    assert yaml.safe_load(updated) == expected
    assert set_labs.edit_yaml(updated, True) == updated
    for line in text.splitlines():
        if "#" in line:
            assert line.split("#", 1)[1] in updated
    if "\r\n" in text:
        assert "\n" not in updated.replace("\r\n", "")


def test_toggle_and_repeat_is_idempotent(files, capsys, monkeypatch):
    config, books = files
    set_labs.main(args(files) + ["--paste", "block"])
    before = (config.read_bytes(), books.read_bytes(), config.stat().st_ino, books.stat().st_ino)

    def unexpected(*_):
        pytest.fail("unchanged content must not be replaced")

    with monkeypatch.context() as context:
        context.setattr(set_labs.os, "replace", unexpected)
        set_labs.main(args(files) + ["--paste", "block"])
    assert before == (config.read_bytes(), books.read_bytes(), config.stat().st_ino, books.stat().st_ino)
    set_labs.main(args(files) + ["--paste", "allow"])
    assert json.loads(config.read_text()) == {"block_paste": False}
    assert yaml.safe_load(books.read_text())["labs"]["block_paste"] is False
    assert capsys.readouterr().out.endswith("粘贴：允许\n")


def test_atomic_replace_stages_both_files(files, monkeypatch):
    config, books = files
    books.chmod(0o640)
    previous = {path: path.read_bytes() for path in files}
    real_replace = os.replace
    calls = []

    def replace(source, dest):
        source, dest = Path(source), Path(dest)
        assert source.parent == dest.parent and source.suffix == ".tmp"
        if not calls:
            assert len(list(books.parent.glob(".*.tmp"))) == 2
            assert len(list(config.parent.glob(".*.tmp"))) == 2
            assert all(path.read_bytes() == value for path, value in previous.items())
            assert json.loads(next(p for p in config.parent.glob(".*.tmp") if p.read_bytes() != previous[config]).read_bytes()) == {"block_paste": True}
        calls.append(dest)
        real_replace(source, dest)

    monkeypatch.setattr(set_labs.os, "replace", replace)
    set_labs.main(args(files) + ["--paste", "block"])
    assert calls == [books, config]
    assert books.stat().st_mode & 0o777 == 0o640
    assert not list(books.parent.glob(".*.tmp")) and not list(config.parent.glob(".*.tmp"))


def test_second_replace_failure_rolls_back(files, monkeypatch, capsys):
    config, books = files
    previous = {path: path.read_bytes() for path in files}
    real_replace = os.replace
    failed = False

    def replace(source, dest):
        nonlocal failed
        if Path(dest) == config and not failed:
            failed = True
            raise OSError("模拟配置替换失败")
        real_replace(source, dest)

    monkeypatch.setattr(set_labs.os, "replace", replace)
    with pytest.raises(SystemExit) as error:
        set_labs.main(args(files) + ["--paste", "block"])
    assert error.value.code == 2
    assert "模拟配置替换失败" in capsys.readouterr().err
    assert all(path.read_bytes() == value for path, value in previous.items())
    assert not list(books.parent.glob(".*.tmp")) and not list(config.parent.glob(".*.tmp"))


def test_staging_failure_leaves_both_unchanged(files, monkeypatch):
    config, books = files
    previous = {path: path.read_bytes() for path in files}
    original = set_labs._stage

    def stage(path, content):
        if path == config:
            raise OSError("模拟暂存失败")
        return original(path, content)

    monkeypatch.setattr(set_labs, "_stage", stage)
    with pytest.raises(SystemExit):
        set_labs.main(args(files) + ["--paste", "block"])
    assert all(path.read_bytes() == value for path, value in previous.items())
    assert not list(books.parent.glob(".*.tmp"))


def test_missing_site_file_clear_error(files, capsys):
    config, books = files
    config.unlink()
    previous = books.read_bytes()
    with pytest.raises(SystemExit) as error:
        set_labs.main(args(files) + ["--paste", "block"])
    assert error.value.code == 2
    assert "assets/lab-config.json 不存在" in capsys.readouterr().err
    assert books.read_bytes() == previous
    assert not config.exists()


def test_no_yaml(files, capsys):
    config, books = files
    books.write_text("broken: [")
    previous = books.read_bytes()
    set_labs.main(args(files) + ["--paste", "block", "--no-yaml"])
    assert books.read_bytes() == previous
    assert json.loads(config.read_text()) == {"block_paste": True}
    books.unlink()
    set_labs.main(args(files) + ["--paste", "allow", "--no-yaml"])
    assert not books.exists()
    assert capsys.readouterr().out == "粘贴：禁止\n粘贴：允许\n"


def test_read_only_without_paste(files, monkeypatch, capsys):
    config, books = files
    config.write_text('{"block_paste": true}')
    previous = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in files}

    def no_write(*_):
        pytest.fail("read-only invocation attempted to write")

    monkeypatch.setattr(set_labs, "atomic_write", no_write)
    set_labs.main(args(files))
    assert capsys.readouterr().out == "粘贴：禁止\n"
    assert all((path.read_bytes(), path.stat().st_mtime_ns) == value for path, value in previous.items())


@pytest.mark.parametrize("content", ['[]', '{', '{"block_paste": "false"}', '{}', '{"block_paste": 0}'])
def test_invalid_live_config(files, content, capsys):
    config, books = files
    config.write_text(content)
    before = books.read_bytes()
    with pytest.raises(SystemExit):
        set_labs.main(args(files) + ["--paste", "block"])
    assert config.read_text() == content and books.read_bytes() == before
    assert capsys.readouterr().err


@pytest.mark.parametrize("text", [
    'broken: [', '[]', 'labs: null', 'labs: false', 'labs:\n  block_paste: "false"',
    'labs:\n  block_paste: 1', 'labs: {}\nlabs: {}\n', 'labs: {block_paste: false, block_paste: false}',
    'defaults: &defaults {block_paste: false}\nlabs: *defaults\n',
    'labs: &labs {block_paste: false}\nother: *labs\n',
])
def test_invalid_or_shared_yaml_never_changes_files(files, text):
    config, books = files
    books.write_text(text)
    before = config.read_bytes()
    with pytest.raises(SystemExit):
        set_labs.main(args(files) + ["--paste", "block"])
    assert config.read_bytes() == before and books.read_text() == text


def test_missing_yaml(files, capsys):
    config, books = files
    books.unlink()
    with pytest.raises(SystemExit):
        set_labs.main(args(files) + ["--paste", "block"])
    assert "books.yaml 不存在" in capsys.readouterr().err
    assert json.loads(config.read_text()) == {"block_paste": False}


def test_cli_entrypoint(files):
    result = subprocess.run([sys.executable, "-B", str(SOURCE / "set_labs.py"), *args(files), "--paste", "block"],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "粘贴：禁止\n"
