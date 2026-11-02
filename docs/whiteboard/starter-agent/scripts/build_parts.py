"""Assemble board fragments without executing them; natural numeric section order."""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--section', help='only assemble one section, e.g. s2')
    parser.add_argument('--assemble-only', action='store_true', help='assemble and compile; do not execute board or checks')
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    boards = []
    for path in folder.glob('_board_s*.py'):
        match = re.fullmatch(r'_board_s([1-9][0-9]*)\.py', path.name)
        if not match:
            parser.error('板书文件名必须是 _board_s正整数.py：' + path.name)
        boards.append((int(match.group(1)), path))
    boards.sort(key=lambda item: item[0])
    if args.section:
        if not re.fullmatch(r's[1-9][0-9]*', args.section):
            parser.error('段号必须是 s正整数，例如 s2')
        boards = [(n, p) for n, p in boards if p.stem == '_board_' + args.section]
    if not boards:
        parser.error('没有找到板书文件 _board_s*.py；请先由作者创建板书' + (f'（{args.section}）' if args.section else ''))
    parts = [folder / '_build_head.py', folder / '_body_helpers.py']
    parts += [p for _, p in boards]
    parts += [folder / '_build_tail.py']
    for path in parts:
        if not path.is_file():
            parser.error('缺少拼接零件：' + path.name)
    text = '\n\n'.join(p.read_text(encoding='utf-8').rstrip() for p in parts) + '\n'
    target = folder / ('build_one_' + args.section + '.py' if args.section else 'build_edit.py')
    compile(text, str(target), 'exec')
    target.write_text(text, encoding='utf-8')
    print('已拼接并通过编译：' + target.name, flush=True)
    print('板书顺序：' + ', '.join(p.name for _, p in boards), flush=True)
    if args.assemble_only:
        return 0
    # _build_tail.py executes the original lint and now propagates failures.
    from project_paths import ROOT, P
    env = dict(os.environ, OPENMONTAGE_ROOT=str(ROOT), PYTHONPATH=str(ROOT))
    subprocess.check_call([sys.executable, str(target)], cwd=ROOT, env=env)
    subprocess.check_call([sys.executable, str(ROOT / 'docs/whiteboard_last_item_check.py'), str(P)], cwd=ROOT, env=env)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
