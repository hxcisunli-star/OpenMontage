"""Change the live paste setting, preserving the YAML's comments and layout."""
import argparse
import json
import os
import stat
import tempfile
from pathlib import Path

import yaml

from labs import lab_config

ROOT = Path(__file__).resolve().parents[3]


def _entry(node, key):
    matches = [(k, v) for k, v in node.value if k.value == key]
    if len(matches) > 1:
        raise ValueError(f"YAML 字段重复：{key}")
    return matches[0] if matches else None


def edit_yaml(text, blocked):
    data = yaml.safe_load(text)
    lab_config(data)
    tree = yaml.compose(text)
    if not isinstance(tree, yaml.MappingNode):
        raise ValueError("books.yaml 必须是对象")
    newline = "\r\n" if "\r\n" in text else "\n"
    value = "true" if blocked else "false"
    entry = _entry(tree, "labs")
    if entry:
        key, labs = entry
        if labs.start_mark.index < key.end_mark.index:
            raise ValueError("labs 使用了 YAML 别名，请改成独立的配置段")
        setting = _entry(labs, "block_paste")
        if setting:
            _, scalar = setting
            if scalar.start_mark.index < key.end_mark.index:
                raise ValueError("block_paste 使用了 YAML 别名，请改成独立的布尔值")
            # Scalar tokens exclude explicit YAML tags and anchors.
            tokens = [t for t in yaml.scan(text) if isinstance(t, yaml.ScalarToken)
                      and scalar.start_mark.index <= t.start_mark.index < scalar.end_mark.index]
            if len(tokens) != 1:
                raise ValueError("无法保留 block_paste 的 YAML 排版")
            token = tokens[0]
            updated = text[:token.start_mark.index] + value + text[token.end_mark.index:]
        elif labs.flow_style:
            at = labs.end_mark.index - 1
            prefix = ", " if labs.value else ""
            updated = text[:at] + prefix + f"block_paste: {value}" + text[at:]
        else:
            # Insert before the first child; surrounding comments remain byte-for-byte.
            first_key = labs.value[0][0]
            at = first_key.start_mark.index - first_key.start_mark.column
            indent = " " * first_key.start_mark.column
            updated = text[:at] + f"{indent}block_paste: {value}{newline}" + text[at:]
    elif tree.flow_style:
        at = tree.end_mark.index - 1
        prefix = ", " if tree.value else ""
        updated = text[:at] + prefix + f"labs: {{block_paste: {value}}}" + text[at:]
    else:
        at = tree.end_mark.index
        # A document end marker must stay after the inserted configuration.
        # At EOF, a new trailing newline can change a block scalar's value.
        if at == len(text) and not text.endswith("\n"):
            first_key = tree.value[0][0]
            at = first_key.start_mark.index - first_key.start_mark.column
        prefix = newline if at and text[at - 1] != "\n" else ""
        updated = text[:at] + prefix + f"labs:{newline}  block_paste: {value}{newline}" + text[at:]
    expected = dict(data, labs=dict(data.get("labs", {}), block_paste=blocked))
    if yaml.safe_load(updated) != expected:
        raise ValueError("无法仅修改 labs.block_paste 并保留 YAML 内容（请检查别名或合并键）")
    return updated


def _stage(path, content):
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, stat.S_IMODE(path.stat().st_mode))
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return temp


def atomic_write(changes):
    """Stage every file first; roll back earlier replacements on a write failure."""
    staged, backups, replaced = {}, {}, []
    try:
        for path, content in changes:
            original = path.read_bytes()
            if original != content:
                backups[path] = _stage(path, original)
                staged[path] = _stage(path, content)
        for path, temp in staged.items():
            os.replace(temp, path)
            replaced.append(path)
    except BaseException:
        for path in reversed(replaced):
            os.replace(backups[path], path)
        raise
    finally:
        for temp in (*staged.values(), *backups.values()):
            temp.unlink(missing_ok=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="查看或设置页内练习的粘贴开关")
    ap.add_argument("--paste", choices=("block", "allow"))
    ap.add_argument("--site-dir", type=Path, default=ROOT / "projects/_ebook/site")
    ap.add_argument("--yaml", type=Path, default=ROOT / "projects/_ebook/books.yaml")
    ap.add_argument("--no-yaml", action="store_true", help="只修改站点配置")
    args = ap.parse_args(argv)
    config_path = args.site_dir / "assets/lab-config.json"
    try:
        if not config_path.is_file():
            raise ValueError("站点配置 assets/lab-config.json 不存在，请先构建含练习的站点")
        current = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(current, dict) or type(current.get("block_paste")) is not bool:
            raise ValueError("站点配置 block_paste 必须是布尔值")
        text = None
        if not args.no_yaml:
            if not args.yaml.is_file():
                raise ValueError("books.yaml 不存在，请用 --yaml 指定文件，或使用 --no-yaml")
            text = args.yaml.read_bytes().decode("utf-8")
            lab_config(yaml.safe_load(text))
        blocked = current["block_paste"] if args.paste is None else args.paste == "block"
        if args.paste is not None:
            changes = []
            if text is not None:
                changes.append((args.yaml, edit_yaml(text, blocked).encode("utf-8")))
            content = (json.dumps({"block_paste": blocked}) + "\n").encode("utf-8")
            changes.append((config_path, content))
            atomic_write(changes)
        print("粘贴：禁止" if blocked else "粘贴：允许")
    except (OSError, ValueError, yaml.YAMLError) as error:
        ap.error(str(error))


if __name__ == "__main__":
    main()
