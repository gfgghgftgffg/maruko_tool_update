#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
project_root="$PWD"
bit_depth="${1:-8}"
case "$bit_depth" in 8|10) ;; *) echo 'Supported depths: 8, 10' >&2; exit 2;; esac
export PATH="$project_root/vendor/ffmpeg/bin:$(cygpath -u "$MARUKO_TOOLCHAIN"):$PATH"
mkdir -p build/logs dist/overlay/tools
cd vendor/l-smash
./configure --target-os=mingw --extra-ldflags=-static > "$project_root/build/logs/lsmash-configure.log" 2>&1
# The upstream single-command dependency recipe exceeds Windows command limits.
mingw32-make -j8 -o .depend lib "SHELL=$MARUKO_MAKE_SHELL" > "$project_root/build/logs/lsmash-build.log" 2>&1
cd ../x264
./configure --host=x86_64-w64-mingw32 --enable-static --bit-depth="$bit_depth" \
  --disable-avs --disable-ffms --disable-gpac --disable-audio --disable-opencl \
  --extra-cflags=-I../l-smash --extra-cflags=-I../ffmpeg/include \
  --extra-ldflags=-static-libgcc --extra-ldflags=-L../l-smash \
  --extra-ldflags=-L../ffmpeg/lib > "$project_root/build/logs/x264-$bit_depth-configure.log" 2>&1
mingw32-make -j8 "SHELL=$MARUKO_MAKE_SHELL" > "$project_root/build/logs/x264-$bit_depth-build.log" 2>&1
cp x264.exe "$project_root/dist/overlay/tools/x264_64-${bit_depth}bit.exe"
