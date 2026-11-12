#!/bin/bash
# build_edit.py = _build_head.py + _body_helpers.py + _body_boards.py + _build_tail.py (edit the parts, then re-run this)
# then docs/whiteboard_last_item_check.py: every board's last handwriting item must finish >= 0.6 s before the fade (it fails the build otherwise;
# the first run failing is normal - move the last item earlier and re-run)
cd "$(dirname "$0")" && cat _build_head.py <(echo) _body_helpers.py <(echo) _body_boards.py <(echo) _build_tail.py > build_edit.py
cd ../../.. && PYTHONPATH=. .venv/bin/python projects/__PID__/scripts/build_edit.py && python3 docs/whiteboard_last_item_check.py projects/__PID__
