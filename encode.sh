#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$#" -eq 0 ]; then
    exec sh "$root/scripts/run-python.sh" "$root/gui.py"
else
    exec sh "$root/scripts/run-python.sh" "$root/encode.py" "$@"
fi
