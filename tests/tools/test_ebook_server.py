"""The ebook platform's static server (docs/whiteboard/ebook/serve.mjs): it may be reachable from outside, so these tests pin down what it must refuse and what it must still do.
Everything runs on 127.0.0.1 with a throw-away certificate, password and site folder in a temp directory; nothing of the real site or its credentials is touched."""
from __future__ import annotations

import base64
import http.client
import json
import os
import shutil
import socket
import ssl
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVE = Path(os.environ.get("EBOOK_SERVE") or ROOT / "docs/whiteboard/ebook/serve.mjs")     # EBOOK_SERVE: run the same tests against a damaged copy to see that they notice
pytestmark = pytest.mark.skipif(shutil.which("node") is None or shutil.which("openssl") is None, reason="needs node and openssl")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    base = tmp_path_factory.mktemp("ebook")
    site, outside, local = base / "site", base / "outside", base / "local"
    (site / "books").mkdir(parents=True)
    (site / "assets/vendor").mkdir(parents=True)
    (site / "assets/lab-config.json").write_text('{"block_paste": false}', encoding="utf-8")
    (site / "assets/vendor/runtime.wasm").write_bytes(bytes(range(256)) * 40)
    (site / "assets/vendor/stdlib.zip").write_bytes(b"zip fixture")
    (site / "module.mjs").write_text("export const value = 2;", encoding="utf-8")
    outside.mkdir()
    (site / "index.html").write_text("<html>shelf</html>", encoding="utf-8")
    (site / "books/page.html").write_text("<html>page</html>", encoding="utf-8")
    (site / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (site / "big.bin").write_bytes(bytes(range(256)) * 40)          # 10240 bytes
    (site / ".env").write_text("SECRET=1", encoding="utf-8")
    (site / "zero.txt").write_bytes(b"")                                       # an empty file used to crash the process (end = size - 1 = -1)
    with open(site / "large.bin", "wb") as f:
        f.truncate(30 * 1024 * 1024)                                           # sparse: a stream over it stays open while a client walks away
    (site / "alias.txt").symlink_to(site / ".env")                             # a plain name that points at a hidden file inside the site
    (site / 'q"uote.py').write_text("print(1)", encoding="utf-8")
    (site / "line\nbreak.py").write_text("print(2)", encoding="utf-8")
    (site / "课.py").write_text("print(3)", encoding="utf-8")
    (site / ".git").mkdir()
    (site / ".git/config").write_text("secret", encoding="utf-8")
    (site / "empty").mkdir()
    (outside / "secret.txt").write_text("OUTSIDE-SECRET", encoding="utf-8")
    (base / "secret.txt").write_text("PARENT-SECRET", encoding="utf-8")
    (site / "escape.txt").symlink_to(outside / "secret.txt")
    (site / "escdir").symlink_to(outside)
    port = free_port()
    cfg = local / "serve.json"
    out = subprocess.run(["node", str(SERVE), "init", "--config", str(cfg), "--root", str(site), "--host", "127.0.0.1", "--port", str(port), "--san-ip", "127.0.0.1"],
                         capture_output=True, text=True, check=True).stdout
    password = [l.split(": ", 1)[1] for l in out.splitlines() if l.startswith("password: ")][0]
    proc = subprocess.Popen(["node", str(SERVE), "run", "--config", str(cfg)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield {"port": port, "password": password, "cfg": cfg, "local": local, "site": site, "pid": proc.pid}
    proc.terminate()
    proc.wait(timeout=5)


def req(server, method="GET", path="/", auth=True, headers=None, password=None, raw_path=None, body=None):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    c = http.client.HTTPSConnection("127.0.0.1", server["port"], context=ctx, timeout=10)
    h = dict(headers or {})
    if auth:
        h["Authorization"] = "Basic " + base64.b64encode(f"reader:{password or server['password']}".encode()).decode()
    c.putrequest(method, raw_path or path, skip_accept_encoding=True)
    for k, v in h.items():
        c.putheader(k, v)
    c.endheaders(body)
    r = c.getresponse()
    data = r.read()
    out = (r.status, dict((k.lower(), v) for k, v in r.getheaders()), data)
    c.close()
    return out


def raw(server, request_line_and_headers: bytes):
    """Send bytes as they are (http.client would tidy a '..' path away) over TLS and return the status line."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    s = ctx.wrap_socket(socket.create_connection(("127.0.0.1", server["port"]), timeout=10))
    s.sendall(request_line_and_headers)
    data = b""
    try:
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
            if b"\r\n\r\n" in data and len(data) > 200:
                break
    except OSError:
        pass
    s.close()
    return data


def basic(server):
    return "Authorization: Basic " + base64.b64encode(f"reader:{server['password']}".encode()).decode()


def test_password_is_required_and_never_stored_in_clear(server):
    status, h, _ = req(server, auth=False)
    assert status == 401 and "basic" in h["www-authenticate"].lower()
    assert server["password"] not in server["cfg"].read_text(encoding="utf-8")
    assert json.loads(server["cfg"].read_text(encoding="utf-8"))["hash"]
    assert oct(server["cfg"].stat().st_mode & 0o777) == "0o600"


def test_serves_pages_and_head(server):
    assert req(server, path="/")[0] == 200 and b"shelf" in req(server, path="/")[2]
    assert req(server, path="/books/page.html")[2] == b"<html>page</html>"
    status, h, body = req(server, "HEAD", "/books/page.html")
    assert status == 200 and body == b"" and h["content-length"] == str(len(b"<html>page</html>"))


def test_only_get_and_head(server):
    for m in ("POST", "PUT", "DELETE"):
        status, h, _ = req(server, m, "/index.html", body=b"x" if m != "DELETE" else None, headers={"Content-Length": "1"} if m != "DELETE" else None)
        assert status == 405 and "GET" in h["allow"]


def test_range_requests_for_video_seeking(server):
    status, h, body = req(server, path="/big.bin", headers={"Range": "bytes=0-9"})
    assert status == 206 and body == bytes(range(10)) and h["content-range"] == "bytes 0-9/10240" and h["accept-ranges"] == "bytes"
    status, h, body = req(server, path="/big.bin", headers={"Range": "bytes=-5"})
    assert status == 206 and len(body) == 5 and h["content-range"] == "bytes 10235-10239/10240"
    status, h, body = req(server, path="/big.bin", headers={"Range": "bytes=10000-"})
    assert status == 206 and len(body) == 240
    assert req(server, path="/big.bin", headers={"Range": "bytes=20000-30000"})[0] == 416
    assert req(server, path="/big.bin", headers={"Range": "bytes=abc"})[0] == 416
    assert req(server, path="/big.bin")[0] == 200


def test_range_follows_rfc_7233_where_players_and_caches_depend_on_it(server):
    """2026-11-06 (found in the code review of the online-delivery work, then reproduced): HEAD never answers a Range; several ranges and an unknown unit are ignored (the whole file comes back);
    If-Range must match the date we sent, otherwise the whole file (a re-rendered video must never be completed with a piece of the new file)."""
    full = bytes(range(256)) * 40
    status, h, body = req(server, "HEAD", "/big.bin", headers={"Range": "bytes=0-9"})
    assert status == 200 and h["content-length"] == "10240" and "content-range" not in h and body == b""
    status, h, body = req(server, path="/big.bin", headers={"Range": "bytes=0-1,5-9"})
    assert status == 200 and body == full and "content-range" not in h
    status, h, body = req(server, path="/big.bin", headers={"Range": "items=0-5"})
    assert status == 200 and body == full
    modified = req(server, "HEAD", "/big.bin")[1]["last-modified"]
    etag = req(server, "HEAD", "/big.bin")[1]["etag"]
    status, h, body = req(server, path="/big.bin", headers={"Range": "bytes=0-9", "If-Range": modified})
    assert status == 206 and body == full[:10] and h["content-range"] == "bytes 0-9/10240"
    status, h, body = req(server, path="/big.bin", headers={"Range": "bytes=0-9", "If-Range": "Thu, 01 Jan 1970 00:00:00 GMT"})
    assert status == 200 and body == full
    status, h, body = req(server, path="/big.bin", headers={"Range": "bytes=0-9", "If-Range": etag})          # a weak ETag never matches an If-Range
    assert status == 200 and body == full


def test_if_none_match_takes_lists_and_star(server):
    etag = req(server, "HEAD", "/big.bin")[1]["etag"]
    assert req(server, path="/big.bin", headers={"If-None-Match": etag})[0] == 304
    assert req(server, path="/big.bin", headers={"If-None-Match": f'"zzz", {etag}'})[0] == 304
    assert req(server, path="/big.bin", headers={"If-None-Match": etag[2:]})[0] == 304          # weak comparison: W/ may be missing
    assert req(server, path="/big.bin", headers={"If-None-Match": "*"})[0] == 304
    assert req(server, path="/big.bin", headers={"If-None-Match": '"zzz"'})[0] == 200


def test_an_empty_file_is_served_and_does_not_take_the_process_down(server):
    status, h, body = req(server, path="/zero.txt")
    assert status == 200 and body == b"" and h["content-length"] == "0"
    assert req(server, "HEAD", "/zero.txt")[0] == 200
    assert req(server, path="/zero.txt", headers={"Range": "bytes=0-"})[0] == 416
    assert req(server, path="/index.html")[0] == 200                       # still alive


@pytest.mark.parametrize("name", ["q%22uote.py", "line%0Abreak.py", "%E8%AF%BE.py"])
def test_download_names_cannot_break_the_header_or_the_server(server, name):
    status, h, body = req(server, path=f"/{name}")
    assert status == 200 and body.startswith(b"print(")
    disp = h["content-disposition"]
    assert disp.startswith("attachment; filename=") and "\n" not in disp and "\r" not in disp and "filename*=UTF-8''" in disp
    assert req(server, path="/index.html")[0] == 200


def test_a_plain_name_cannot_alias_a_hidden_file(server):
    assert req(server, path="/alias.txt")[0] == 404
    assert req(server, path="/.env")[0] == 404


def test_a_malformed_request_target_answers_400_and_the_process_stays_up(server):
    data = raw(server, ("GET //[ HTTP/1.1\r\nHost: x\r\n" + basic(server) + "\r\nConnection: close\r\n\r\n").encode())
    assert b" 400 " in data.split(b"\r\n", 1)[0] or data == b""           # a parser that refuses it earlier closes the socket: also fine
    assert req(server, path="/index.html")[0] == 200


def test_a_request_with_a_body_we_do_not_read_closes_the_connection(server):
    status, h, _ = req(server, "POST", "/index.html", body=b"x", headers={"Content-Length": "1"})
    assert status == 405 and h.get("connection", "").lower() == "close"


def test_clients_that_walk_away_mid_video_do_not_leak_descriptors(server):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    fds = lambda: len(os.listdir(f"/proc/{server['pid']}/fd"))
    before = fds()
    for _ in range(30):
        c = http.client.HTTPSConnection("127.0.0.1", server["port"], context=ctx, timeout=10)
        c.request("GET", "/large.bin", headers={"Authorization": "Basic " + base64.b64encode(f"reader:{server['password']}".encode()).decode(), "Range": "bytes=0-"})
        c.getresponse().read(65536)
        c.sock.close()
    time.sleep(1.5)
    assert fds() <= before + 3, (before, fds())


@pytest.mark.parametrize("p", ["/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt", "/books/../../secret.txt", "/%2e%2e%2f%2e%2e%2fsecret.txt", "/books/..%5c..%5csecret.txt", "/%00", "/index.html%00.png"])
def test_path_traversal_is_refused(server, p):
    data = raw(server, f"GET {p} HTTP/1.1\r\nHost: x\r\n{basic(server)}\r\nConnection: close\r\n\r\n".encode())
    status = int(data.split(b" ", 2)[1]) if data.startswith(b"HTTP/") else 0
    assert status in (400, 404, 0) and b"PARENT-SECRET" not in data and b"OUTSIDE-SECRET" not in data


def test_dotfiles_symlink_escapes_and_directories(server):
    for p in ("/.env", "/.git/config", "/.git/", "/books/.hidden"):
        assert req(server, path=p)[0] == 404
    assert req(server, path="/escape.txt")[0] == 404          # a symlink to a file outside the site
    assert req(server, path="/escdir/secret.txt")[0] == 404    # a symlink to a folder outside the site
    status, _, body = req(server, path="/empty/")
    assert status == 404 and b"<a" not in body                 # no directory listing
    assert req(server, path="/books/")[0] == 404


def test_security_headers_and_robots(server):
    status, h, body = req(server, path="/robots.txt")
    assert status == 200 and b"Disallow: /" in body
    assert h["x-content-type-options"] == "nosniff" and h["referrer-policy"] == "no-referrer" and "noindex" in h["x-robots-tag"]
    assert "default-src 'self'" in h["content-security-policy"] and h["x-frame-options"] == "DENY"
    assert req(server, path="/index.html")[1]["cache-control"] == "no-cache"


def test_oversized_header_is_refused(server):
    data = raw(server, f"GET /index.html HTTP/1.1\r\nHost: x\r\nX-Big: {'a' * 20000}\r\n{basic(server)}\r\nConnection: close\r\n\r\n".encode())
    assert not data.startswith(b"HTTP/1.1 200")


def test_credentials_never_reach_the_log(server):
    req(server, path="/index.html")
    time.sleep(0.3)
    log = (server["local"] / "access.log").read_text(encoding="utf-8")
    assert "/index.html" in log and server["password"] not in log and "Basic" not in log and "Authorization" not in log



@pytest.mark.parametrize("path,mime", [
    ("/assets/vendor/runtime.wasm", "application/wasm"),
    ("/assets/vendor/stdlib.zip", "application/zip"),
    ("/module.mjs", "text/javascript; charset=utf-8"),
])
def test_lab_asset_mime(server, path, mime):
    status, headers, _ = req(server, path=path)
    assert status == 200 and headers["content-type"] == mime


def test_lab_csp_is_exact(server):
    expected = ("default-src 'self'; img-src 'self' data:; media-src 'self'; "
                "style-src 'self' 'unsafe-inline'; script-src 'self' 'wasm-unsafe-eval'; "
                "worker-src 'self'; font-src 'self'; connect-src 'self'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
    for path, auth in (("/", True), ("/missing", True), ("/", False)):
        csp = req(server, path=path, auth=auth)[1]["content-security-policy"]
        assert csp == expected
        assert "'unsafe-eval'" not in csp and "blob:" not in csp


@pytest.mark.parametrize("path", ["/assets/lab-config.json", "/assets/lab-config.json?v=2", "/assets/%6cab-config.json"])
def test_config_is_never_cached(server, path):
    status, headers, _ = req(server, path=path)
    assert status == 200 and headers["cache-control"] == "no-store"
    status, headers, body = req(server, path=path, headers={"If-None-Match": headers["etag"]})
    assert status == 304 and body == b"" and headers["cache-control"] == "no-store"


def test_vendor_cache_and_wasm_range(server):
    status, headers, _ = req(server, path="/assets/vendor/runtime.wasm")
    assert status == 200 and headers["cache-control"] == "public, max-age=86400"
    status, headers, body = req(server, path="/assets/vendor/runtime.wasm", headers={"Range": "bytes=5-14"})
    assert status == 206 and body == bytes(range(5, 15))
    assert headers["content-type"] == "application/wasm"
    assert headers["content-range"] == "bytes 5-14/10240"
    assert headers["cache-control"] == "public, max-age=86400"
    assert req(server, path="/module.mjs")[1]["cache-control"] == "private, max-age=3600"
    assert req(server, "HEAD", "/assets/vendor/stdlib.zip")[1]["cache-control"] == "public, max-age=86400"

def test_wrong_passwords_lock_the_source_then_even_the_right_one_waits(server):
    # last test of the module: it locks 127.0.0.1 for fifteen minutes
    for _ in range(5):
        assert req(server, path="/index.html", password="wrong-password")[0] == 401
    status, h, _ = req(server, path="/index.html")
    assert status == 429 and int(h["retry-after"]) > 0
