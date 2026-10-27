#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec sh "$root/scripts/run-python.sh" "$root/gui.py" "$@"
