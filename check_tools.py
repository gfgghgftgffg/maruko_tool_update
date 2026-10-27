#!/usr/bin/env python3
"""Inspect external encoder paths and optionally run a short synthetic encode."""
import argparse
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile

import encode


def inspect_tools(cfg, encoders, bit_depth, smoke=False):
    results = []
    cache = {}

    def run(command):
        key = tuple(command)
        if key not in cache:
            process = subprocess.run(command, capture_output=True, timeout=30)
            output = (process.stdout + process.stderr).decode('utf-8', errors='replace')
            if process.returncode:
                raise RuntimeError(Path(command[0]).name + ': ' + output[-1200:])
            cache[key] = output
        return cache[key]

    for encoder in encoders:
        result = {'encoder': encoder, 'bit_depth': bit_depth, 'paths': {}, 'versions': {}, 'ok': False}
        results.append(result)
        try:
            args = encode.build_parser().parse_args(['fixture.mkv', '--encoder', encoder,
                                                    '--bit-depth', str(bit_depth)])
            args.audio, args.container = cfg['audio'], cfg['container']
            paths = encode.resolve_paths(cfg, args)
            result['paths'] = paths
            for name, path in paths.items():
                flag = '--version' if name == 'encoder' else '-version'
                version = run([path, flag])
                result['versions'][name] = next((line for line in version.splitlines() if line.strip()), '')
            if encoder == 'svt-av1':
                if 'libsvtav1' not in run([paths['ffmpeg'], '-hide_banner', '-encoders']):
                    raise RuntimeError('所选 FFmpeg 不包含 libsvtav1。')
            if smoke:
                # Uses the actual configured CRF/options and verifies the output depth.
                with tempfile.TemporaryDirectory(prefix='maruko-tools-') as tmp:
                    source = Path(tmp) / 'fixture.mkv'
                    run([paths['ffmpeg'], '-v', 'error', '-nostdin', '-y', '-f', 'lavfi',
                         '-i', 'testsrc2=size=160x90:rate=30', '-t', '0.4', '-c:v', 'ffv1', str(source)])
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        encode.encode_one(source, Path(tmp) / ('output.' + args.container), args, cfg, paths)
                result['smoke'] = 'passed'
            result['ok'] = True
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError, KeyError) as exc:
            result['error'] = str(exc)
    return results


def format_report(results):
    lines = []
    for result in results:
        name = 'AV1' if result['encoder'] == 'svt-av1' else 'x265'
        lines.append(f"{name} {result['bit_depth']}bit: {'通过' if result['ok'] else '失败'}")
        for tool, path in result['paths'].items():
            lines.append(f'  {tool}: {path}')
            if result['versions'].get(tool):
                lines.append('    ' + result['versions'][tool])
        if result.get('smoke'):
            lines.append('  短片编码、输出格式与位深检查通过')
        if result.get('error'):
            lines.append('  ' + result['error'])
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=encode.ROOT / 'config.json')
    parser.add_argument('--encoder', choices=['x265', 'svt-av1', 'all'], default='all')
    parser.add_argument('--bit-depth', type=int, choices=[8, 10])
    parser.add_argument('--smoke', action='store_true', help='使用配置中的参数编码短测试片，检查位深与参数兼容性')
    args = parser.parse_args(argv)
    try:
        cfg = encode.load_config(args.config)
        encoders = ['x265', 'svt-av1'] if args.encoder == 'all' else [args.encoder]
        results = inspect_tools(cfg, encoders, args.bit_depth or cfg['bit_depth'], args.smoke)
        print(format_report(results))
        return 0 if all(result['ok'] for result in results) else 1
    except (ValueError, OSError) as exc:
        print('错误：' + str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
