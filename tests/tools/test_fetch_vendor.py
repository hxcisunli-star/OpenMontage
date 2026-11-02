"""Small untrusted archives exercise fetching offline; the real download is opt-in."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import os
import shutil
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("fetch_vendor", ROOT / "docs/whiteboard/ebook/fetch_vendor.py")
vendor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vendor)


def archive(path, files=(), special=()):
    with tarfile.open(path, "w:gz") as output:
        for name, data in files:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            output.addfile(info, io.BytesIO(data))
        for info in special:
            output.addfile(info)
    return path


def integrity(path):
    return "sha512-" + base64.b64encode(hashlib.sha512(path.read_bytes()).digest()).decode()


@pytest.mark.parametrize("name", ["../escape", "package/../../escape", "/absolute", "C:/escape", "package/..\\escape"])
def test_extract_refuses_unsafe_paths_before_writing(tmp_path, name):
    source = archive(tmp_path / "bad.tgz", [("package/safe", b"safe"), (name, b"bad")])
    destination = tmp_path / "unpacked"
    with pytest.raises(ValueError, match="unsafe archive path"):
        vendor.safe_extract(source, destination)
    assert list(destination.iterdir()) == []
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.FIFOTYPE])
def test_extract_refuses_links_and_devices(tmp_path, kind):
    member = tarfile.TarInfo("package/link")
    member.type = kind
    member.linkname = "../../escape"
    source = archive(tmp_path / "bad.tgz", special=[member])
    with pytest.raises(ValueError, match="unsafe archive member type"):
        vendor.safe_extract(source, tmp_path / "unpacked")


def test_extract_requires_empty_directory_and_rejects_duplicate_members(tmp_path):
    source = archive(tmp_path / "ok.tgz", [("package/a", b"abc")])
    destination = tmp_path / "unpacked"
    vendor.safe_extract(source, destination)
    assert (destination / "package/a").read_bytes() == b"abc"
    with pytest.raises(ValueError, match="empty directory"):
        vendor.safe_extract(source, destination)
    source = archive(tmp_path / "duplicate.tgz", [("package/a", b"a"), ("package/./a", b"b")])
    with pytest.raises(ValueError, match="duplicate"):
        vendor.safe_extract(source, tmp_path / "duplicate")


def test_extract_enforces_size_limit(tmp_path, monkeypatch):
    source = archive(tmp_path / "large.tgz", [("package/a", b"abcd")])
    monkeypatch.setattr(vendor, "MAX_EXTRACTED_BYTES", 3)
    with pytest.raises(ValueError, match="size limit"):
        vendor.safe_extract(source, tmp_path / "unpacked")


@pytest.mark.parametrize("bad", ["sha512-AAAA", "sha512-?", "sha256-AAAA", "", None])
def test_integrity_mismatch_is_rejected(tmp_path, bad):
    source = archive(tmp_path / "ok.tgz", [("package/a", b"a")])
    with pytest.raises(ValueError, match="integrity"):
        vendor.verify_integrity(source, bad)
    vendor.verify_integrity(source, integrity(source))


@pytest.fixture
def registry(tmp_path, monkeypatch):
    archives = {}
    pins = {}
    for name, pin in vendor.PINS.items():
        names = (["min/vs/" + item for item in vendor.MONACO_FILES] + ["LICENSE"]
                 if name == "monaco-editor" else list(vendor.PYODIDE_FILES))
        files = [("package/" + item, (name + ":" + item).encode()) for item in names]
        files += [("package/unneeded.js", b"throw new Error('must never execute');"),
                  ("package/package.json", b'{"license":"MPL-2.0"}')]
        source = archive(tmp_path / (name + ".tgz"), files)
        archives[name] = source
        pins[name] = {"version": pin["version"], "integrity": integrity(source)}
    monkeypatch.setattr(vendor, "PINS", pins)
    calls = []

    def download(url, destination, limit=vendor.MAX_ARCHIVE_BYTES):
        calls.append(url)
        for name, pin in pins.items():
            if url == f"https://registry.npmjs.org/{name}/{pin['version']}":
                destination.write_text(json.dumps({"name": name, "version": pin["version"], "dist": {
                    "integrity": pin["integrity"], "tarball": f"https://registry.npmjs.org/{name}.tgz"}}))
                return
            if url == f"https://registry.npmjs.org/{name}.tgz":
                shutil.copyfile(archives[name], destination)
                return
        raise AssertionError("unexpected download")

    monkeypatch.setattr(vendor, "download", download)
    return {"archives": archives, "calls": calls, "pins": pins}


def test_pruning_manifest_and_existing_vendor_are_verified(tmp_path, registry):
    output = tmp_path / "vendor"
    vendor.fetch_vendor(output)
    assert len(registry["calls"]) == 4
    expected = {"monaco/vs/" + name for name in vendor.MONACO_FILES}
    expected.update("pyodide/" + name for name in vendor.PYODIDE_FILES)
    expected.update({"monaco/LICENSE", "pyodide/LICENSE"})
    actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    assert actual == expected | {"MANIFEST.sha256", "VERSIONS.json"}
    lines = (output / "MANIFEST.sha256").read_text().splitlines()
    assert [line.split("  ", 1)[1] for line in lines] == sorted(expected)
    for line in lines:
        digest, name = line.split("  ", 1)
        assert digest == hashlib.sha256((output / name).read_bytes()).hexdigest()
    assert json.loads((output / "VERSIONS.json").read_text()) == registry["pins"]
    assert (output / "pyodide/LICENSE").read_text().startswith("Mozilla Public License")
    vendor.verify_vendor(output)
    vendor.fetch_vendor(output)
    assert len(registry["calls"]) == 4
    (output / "monaco/vs/loader.js").write_text("damaged")
    with pytest.raises(ValueError, match="manifest mismatch"):
        vendor.fetch_vendor(output)


@pytest.mark.parametrize("damage", ["content", "missing", "extra", "manifest", "versions", "symlink"])
def test_reverification_detects_tampering(tmp_path, registry, damage):
    output = tmp_path / "vendor"
    vendor.fetch_vendor(output)
    if damage == "content":
        (output / "pyodide/pyodide.js").write_bytes(b"corrupt")
    elif damage == "missing":
        (output / "monaco/LICENSE").unlink()
    elif damage == "extra":
        (output / "extra.js").write_bytes(b"extra")
    elif damage == "manifest":
        (output / "MANIFEST.sha256").write_text("../../escape\n")
    elif damage == "versions":
        (output / "VERSIONS.json").write_text("{}")
    else:
        (output / "link").symlink_to(output / "monaco/LICENSE")
    with pytest.raises(ValueError):
        vendor.verify_vendor(output)


def test_force_reproduces_manifest_and_failure_preserves_old_vendor(tmp_path, registry):
    output = tmp_path / "vendor"
    vendor.fetch_vendor(output)
    manifest = (output / "MANIFEST.sha256").read_bytes()
    (output / "obsolete").write_bytes(b"old")
    vendor.fetch_vendor(output, force=True)
    assert not (output / "obsolete").exists()
    assert (output / "MANIFEST.sha256").read_bytes() == manifest
    registry["archives"]["pyodide"].write_bytes(b"tampered archive")
    with pytest.raises(ValueError, match="integrity mismatch"):
        vendor.fetch_vendor(output, force=True)
    assert (output / "MANIFEST.sha256").read_bytes() == manifest
    vendor.verify_vendor(output)
    assert sorted(p.name for p in tmp_path.glob(".fetch-vendor-*")) == []


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://registry.npmjs.org/a", "https://example.invalid/a"])
def test_download_rejects_non_registry_urls(tmp_path, url):
    with pytest.raises(ValueError, match="only npm registry"):
        vendor.download(url, tmp_path / "download")
    assert not (tmp_path / "download").exists()


@pytest.mark.skipif(os.environ.get("FETCH_VENDOR_ONLINE") != "1", reason="set FETCH_VENDOR_ONLINE=1 to download real npm archives")
def test_online_fetch_is_reproducible(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    vendor.fetch_vendor(first)
    vendor.fetch_vendor(second)
    vendor.verify_vendor(first)
    vendor.verify_vendor(second)
    assert (first / "MANIFEST.sha256").read_bytes() == (second / "MANIFEST.sha256").read_bytes()
    delivered = ROOT / "projects/_ebook/vendor/MANIFEST.sha256"
    if delivered.exists():
        assert (first / "MANIFEST.sha256").read_bytes() == delivered.read_bytes()
