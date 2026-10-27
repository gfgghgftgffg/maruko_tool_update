#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -n "${MARUKO_PYTHON:-}" ]; then
    python=$MARUKO_PYTHON
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    python=$VIRTUAL_ENV/bin/python
elif [ -n "${CONDA_PREFIX:-}" ] && [ -x "$CONDA_PREFIX/bin/python" ]; then
    python=$CONDA_PREFIX/bin/python
elif [ -x "$root/.venv/bin/python" ]; then
    python=$root/.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
    python=python3
elif command -v python >/dev/null 2>&1; then
    python=python
else
    printf "%s\n" "Python 3.11+ is required. Set MARUKO_PYTHON to its executable." >&2
    exit 127
fi
exec "$python" "$@"
