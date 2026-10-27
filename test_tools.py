"""Tool configuration and POSIX-launcher tests; no user media is used."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_tools
import encode


class ToolTests(unittest.TestCase):
    def test_relative_configuration_is_project_relative(self):
        with tempfile.TemporaryDirectory(prefix='配置 test ') as tmp:
            with patch.object(encode, 'ROOT', Path(tmp)):
                self.assertEqual(encode.config_executable('custom tools/ffmpeg'), str(Path(tmp) / 'custom tools/ffmpeg'))
                self.assertEqual(encode.config_executable('ffmpeg'), 'ffmpeg')
                self.assertIsNone(encode.config_executable(''))

    def test_native_program_names_are_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = root / 'tools'
            tools.mkdir()
            for name in ('ffmpeg', 'ffprobe', 'x265', 'MP4Box'):
                (tools / name).touch()
            cfg = {'profiles': {'x265': {}}, 'tools_dir': ''}
            args = encode.build_parser().parse_args(['video.mp4', '--encoder', 'x265', '--bit-depth', '10'])
            with patch.object(encode, 'ROOT', root):
                paths = encode.resolve_paths(cfg, args)
            self.assertEqual(Path(paths['ffmpeg']), tools / 'ffmpeg')
            self.assertEqual(Path(paths['ffprobe']), tools / 'ffprobe')
            self.assertEqual(Path(paths['encoder']), tools / 'x265')
            self.assertEqual(Path(paths['mp4box']), tools / 'MP4Box')

    def test_missing_tool_is_reported(self):
        cfg = encode.load_config(encode.ROOT / 'config.example.json')
        with patch.object(encode, 'resolve_paths', side_effect=ValueError('missing x265')):
            result = check_tools.inspect_tools(cfg, ['x265'], 10)
        self.assertFalse(result[0]['ok'])
        self.assertIn('missing x265', check_tools.format_report(result))

    def test_ffmpeg_without_svt_is_rejected(self):
        cfg = encode.load_config(encode.ROOT / 'config.example.json')
        def run(command, **kwargs):
            output = b'FFmpeg version test' if '-version' in command else b'libx264 only'
            return subprocess.CompletedProcess(command, 0, output, b'')
        with patch.object(encode, 'resolve_paths', return_value={'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}), \
             patch.object(check_tools.subprocess, 'run', side_effect=run):
            result = check_tools.inspect_tools(cfg, ['svt-av1'], 10)
        self.assertFalse(result[0]['ok'])
        self.assertIn('libsvtav1', result[0]['error'])

    def test_no_experiment_folders_in_project(self):
        for name in ('jobs', 'compare_1080p', 'research'):
            self.assertFalse((encode.ROOT / name).exists(), name)
        self.assertFalse(list(encode.ROOT.glob('config.before-*.json')))

    def test_posix_launchers_preserve_paths_and_arguments(self):
        shell = shutil.which('sh')
        if os.name == 'nt':
            git = shutil.which('git')
            candidate = Path(git).resolve().parent.parent / 'bin' / 'bash.exe' if git else None
            shell = str(candidate) if candidate and candidate.is_file() else shutil.which('bash')
        if not shell:
            self.skipTest('POSIX shell is unavailable')
        with tempfile.TemporaryDirectory(prefix='启动 test ') as tmp:
            fake = Path(tmp) / 'fake python.sh'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding='utf-8')
            fake.chmod(0o755)
            env = dict(os.environ, MARUKO_PYTHON=fake.as_posix())
            extra = ['视频 & 空格.mp4', '--output-dir', 'output with spaces']
            for name, arguments, target in (
                ('start_gui.sh', extra, 'gui.py'), ('start_gui.command', extra, 'gui.py'),
                ('encode.sh', extra, 'encode.py'), ('encode.sh', [], 'gui.py')):
                with self.subTest(name=name, arguments=arguments):
                    result = subprocess.run([shell, str(encode.ROOT / name), *arguments],
                        cwd=tmp, env=env, capture_output=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
                    lines = result.stdout.decode('utf-8').splitlines()
                    self.assertTrue(lines[0].replace('\\', '/').endswith('/' + target), lines)
                    self.assertEqual(lines[1:], arguments)


if __name__ == '__main__':
    unittest.main(verbosity=2)
