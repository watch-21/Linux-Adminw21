#!/bin/bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$ROOT"
for file in ./*.sh backend/*.sh lib/*.sh modules/*.sh tests/*.sh;do bash -n "$file";done
for test in tests/test_*.sh;do bash "$test";done
python3 -m compileall -q gui backend
if command -v shellcheck >/dev/null;then shellcheck -x ./*.sh backend/*.sh lib/*.sh modules/*.sh tests/*.sh;else echo 'SKIP: ShellCheck unavailable';fi
if command -v ruff >/dev/null;then ruff check gui backend tests/*.py;else echo 'SKIP: Ruff unavailable';fi
QT_QPA_PLATFORM=offscreen python3 -m pytest -q
