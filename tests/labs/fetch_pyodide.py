"""为 Node 集成测试获取已校验的 Pyodide；不运行包管理器或安装脚本。"""

import argparse
import base64
import hashlib
import hmac
import json
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).resolve().parents[2] / ".pyodide-integration")
    args = parser.parse_args()
    metadata = json.loads(fetch("https://registry.npmjs.org/pyodide/0.27.7"))
    dist = metadata["dist"]
    data = fetch(dist["tarball"])
    actual = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")
    if not hmac.compare_digest(actual, dist["integrity"]):
        raise ValueError("Pyodide integrity 校验失败")
    args.out.mkdir(parents=True, exist_ok=False)
    archive = args.out / "pyodide.tgz"
    archive.write_bytes(data)
    with tarfile.open(archive) as package:
        members = package.getmembers()
        names = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or "\\" in member.name
                    or not path.parts or path.parts[0] != "package"
                    or not (member.isfile() or member.isdir())
                    or path in names):
                raise ValueError("不安全的 Pyodide 归档路径")
            names.add(path)
        for member in members:
            target = args.out.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.extractfile(member) as source, target.open("xb") as output:
                    output.write(source.read())
    (args.out / "VERIFIED.json").write_text(json.dumps({
        "package": "pyodide", "version": metadata["version"], "integrity": actual,
        "archive_sha256": hashlib.sha256(data).hexdigest(),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"pyodide {metadata['version']}: sha512 integrity 通过；安全解包完成")


if __name__ == "__main__":
    main()
