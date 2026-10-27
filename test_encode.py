"""Run with the same Python as encode.py. Uses only synthetic, short video fixtures."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction

import encode


class UnitTests(unittest.TestCase):
    def test_fractional_fps(self):
        self.assertEqual(encode.frame_rate({'avg_frame_rate': '30000/1001', 'r_frame_rate': '30000/1001'}, None), '30000/1001')

    def test_vfr_requires_explicit_fps(self):
        with self.assertRaises(ValueError):
            encode.frame_rate({'avg_frame_rate': '25/1', 'r_frame_rate': '30/1'}, None)
        self.assertEqual(encode.frame_rate({'avg_frame_rate': '25/1'}, '24'), '24/1')

    def test_bad_fps(self):
        for rate in ('0', '-1', '1001', '0/0'):
            with self.assertRaises((ValueError, ZeroDivisionError)):
                encode.frame_rate({}, rate)

    def test_original_x265_params(self):
        self.assertIn('--no-sao', encode.check_params(encode.DEFAULTS['profiles']['x265']['params'], 'x265'))

    def test_reserved_output_options(self):
        for option in ('-o', '--output=bad.mp4', '--frames', '--fps'):
            with self.assertRaises(ValueError):
                encode.check_params([option], 'x265')
        with self.assertRaises(ValueError):
            encode.check_params(['-i'], 'svt-av1')

    def test_params_must_be_array_of_strings(self):
        for params in ('--crf 23', [23], None):
            with self.assertRaises(ValueError):
                encode.check_params(params, 'x265')

    def test_collect_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / '视频 & clip.mp4'
            p.touch()
            self.assertEqual(encode.collect_inputs([tmp, str(p)], False), [p.resolve()])

    def test_collect_missing_input(self):
        with self.assertRaises(ValueError):
            encode.collect_inputs(['this-directory-does-not-exist-349058/*.mp4'], False)

    def test_missing_config_uses_portable_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = encode.load_config(Path(tmp) / 'missing.json')
        template = json.loads((encode.ROOT / 'config.example.json').read_text(encoding='utf-8'))
        self.assertEqual(cfg['profiles'], template['profiles'])
        self.assertEqual(cfg['profiles']['svt-av1']['params'][2:4], ['-crf', '28'])
        self.assertEqual(cfg['tools_dir'], '')
        self.assertFalse(Path(tmp, 'missing.json').exists())

    def test_project_tool_discovery_and_overrides(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='项目 paths ') as tmp:
            root = Path(tmp)
            local = root / 'dist' / 'overlay' / 'tools'
            local.mkdir(parents=True)
            vendor = root / 'vendor' / 'ffmpeg' / 'bin'
            vendor.mkdir(parents=True)
            for name in ('ffmpeg.exe', 'x265_64-10bit[gcc].exe', 'MP4Box.exe'):
                (local / name).touch()
            (vendor / 'ffprobe.exe').touch()
            cfg = {'tools_dir': '', 'profiles': {'x265': {}}}
            args = encode.build_parser().parse_args(['clip.mp4', '--encoder', 'x265', '--bit-depth', '10'])
            with patch.object(encode, 'ROOT', root):
                paths = encode.resolve_paths(cfg, args)
                self.assertEqual(Path(paths['ffmpeg']), local / 'ffmpeg.exe')
                self.assertEqual(Path(paths['ffprobe']), vendor / 'ffprobe.exe')
                self.assertEqual(Path(paths['encoder']), local / 'x265_64-10bit[gcc].exe')
                override = root / 'custom ffmpeg.exe'
                override.touch()
                args.ffmpeg = str(override)
                self.assertEqual(Path(encode.resolve_paths(cfg, args)['ffmpeg']), override)

    def test_pipeline_encoder_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = encode.Runner(Path(tmp) / 'failure.log')
            with self.assertRaises(RuntimeError):
                runner.pipe([sys.executable, '-c', 'import sys; sys.stdout.buffer.write(b"x" * 1000000)'],
                            [sys.executable, '-c', 'raise SystemExit(7)'])

    def test_pipeline_decoder_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = encode.Runner(Path(tmp) / 'failure.log')
            with self.assertRaises(RuntimeError):
                runner.pipe([sys.executable, '-c', 'raise SystemExit(9)'],
                            [sys.executable, '-c', 'import sys; sys.stdin.buffer.read()'])


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = encode.load_config(encode.ROOT / 'config.json')
        options = encode.build_parser().parse_args(['fixture.mp4', '--encoder', 'svt-av1'])
        options.bit_depth = cls.cfg['bit_depth']
        paths = encode.resolve_paths(cls.cfg, options)
        cls.ffmpeg, cls.ffprobe = paths['ffmpeg'], paths['ffprobe']
        cls.root = encode.ROOT / 'build' / 'tests'
        cls.root.mkdir(parents=True, exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix='run-', dir=cls.root))
        cls.inputs = cls.root / '中文 & 空格输入'
        cls.inputs.mkdir()
        cls.source = cls.inputs / 'sample & 中文.mp4'
        cls.silent = cls.inputs / 'silent.mp4'
        cls.log = (cls.root / 'test-driver.log').open('wb')
        cls.cmd([cls.ffmpeg, '-hide_banner', '-nostdin', '-y', '-f', 'lavfi', '-i',
                 'testsrc2=size=320x180:rate=30000/1001', '-f', 'lavfi', '-i',
                 'sine=frequency=440:sample_rate=48000', '-t', '2.002', '-c:v', 'libx264',
                 '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', str(cls.source)])
        cls.cmd([cls.ffmpeg, '-hide_banner', '-nostdin', '-y', '-i', str(cls.source),
                 '-map', '0:v:0', '-c', 'copy', str(cls.silent)])
        cls.results = []

    @classmethod
    def tearDownClass(cls):
        (cls.root / 'results.json').write_text(json.dumps(cls.results, ensure_ascii=False, indent=2), encoding='utf-8')
        cls.log.close()
        print('\nVerification artifacts: ' + str(cls.root))

    @classmethod
    def cmd(cls, command, expected=0):
        env = dict(os.environ, PYTHONUTF8='1')
        result = subprocess.run(command, stdout=cls.log, stderr=cls.log, env=env, timeout=120)
        if result.returncode != expected:
            raise AssertionError('Unexpected exit %s (expected %s): %s; see %s' %
                                 (result.returncode, expected, command, cls.root / 'test-driver.log'))

    def run_script(self, inputs, *args, expected=0):
        self.cmd([sys.executable, str(encode.ROOT / 'encode.py'), *map(str, inputs), *map(str, args)], expected)

    def inspect(self, path, codec, depth, audio=True, audio_codec='aac'):
        result = subprocess.run([self.ffprobe, '-v', 'error', '-count_frames', '-show_streams', '-show_format',
                                 '-of', 'json', str(path)], capture_output=True, check=True)
        data = json.loads(result.stdout)
        video = next(s for s in data['streams'] if s['codec_type'] == 'video')
        self.assertEqual(video['codec_name'], codec)
        self.assertEqual(video['pix_fmt'], 'yuv420p10le' if depth == 10 else 'yuv420p')
        self.assertEqual(int(video['nb_read_frames']), 60)
        self.assertLess(abs(float(Fraction(video['avg_frame_rate']) - Fraction(30000, 1001))), 0.01)
        self.assertLess(abs(float(video.get('duration') or data['format']['duration']) - 2.002), 0.2)
        tracks = [s for s in data['streams'] if s['codec_type'] == 'audio']
        self.assertEqual(len(tracks), int(audio))
        if audio:
            self.assertEqual(tracks[0]['codec_name'], audio_codec)
        self.cmd([self.ffmpeg, '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', '-'])
        self.results.append({'output': str(path), 'codec': codec, 'depth': depth, 'frames': 60, 'passed': True})

    def audio_hash(self, path):
        data = subprocess.run([self.ffmpeg, '-v', 'error', '-nostdin', '-i', str(path),
                               '-map', '0:a:0', '-c:a', 'copy', '-f', 'adts', '-'],
                              capture_output=True, check=True).stdout
        return hashlib.sha256(data).hexdigest()

    def test_01_all_encoders_and_depths(self):
        for encoder, codec in (('x265', 'hevc'), ('svt-av1', 'av1')):
            for depth in (8, 10):
                with self.subTest(encoder=encoder, depth=depth):
                    out = self.root / (encoder + '-' + str(depth))
                    self.run_script([self.source], '--encoder', encoder, '--bit-depth', depth, '--output-dir', out)
                    dest = out / (self.source.stem + '_' + encoder + '.mp4')
                    self.inspect(dest, codec, depth)
                    self.assertEqual(self.audio_hash(self.source), self.audio_hash(dest))

    def test_02_batch_glob_and_silent_input(self):
        out = self.root / 'batch'
        self.run_script([str(self.inputs / '*.mp4')], '--encoder', 'svt-av1', '--output-dir', out)
        self.inspect(out / (self.source.stem + '_svt-av1.mp4'), 'av1', 10)
        self.inspect(out / 'silent_svt-av1.mp4', 'av1', 10, audio=False)

    def test_03_x265_mkv(self):
        out = self.root / 'mkv'
        self.run_script([self.source], '--encoder', 'x265', '--container', 'mkv', '--output-dir', out)
        self.inspect(out / (self.source.stem + '_x265.mkv'), 'hevc', 10)

    def test_04_audio_modes(self):
        for mode in ('aac', 'none'):
            out = self.root / ('audio-' + mode)
            self.run_script([self.source], '--encoder', 'svt-av1', '--audio', mode, '--output-dir', out)
            self.inspect(out / (self.source.stem + '_svt-av1.mp4'), 'av1', 10, audio=mode != 'none')

    def test_05_skip_existing_and_dry_run(self):
        out = self.root / 'skip'
        out.mkdir()
        dest = out / (self.source.stem + '_svt-av1.mp4')
        dest.write_bytes(b'never overwrite without permission')
        original = dest.read_bytes()
        self.run_script([self.source], '--encoder', 'svt-av1', '--output-dir', out)
        self.assertEqual(dest.read_bytes(), original)
        dry = self.root / 'dry-run'
        self.run_script([self.source], '--encoder', 'svt-av1', '--dry-run', '--output-dir', dry)
        self.assertFalse(list(dry.glob('*.mp4')))
        report = json.loads(next((dry / 'logs').glob('*.json')).read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'dry-run')

    def test_06_custom_params_and_failure_safety(self):
        params = self.root / 'params.json'
        params.write_text(json.dumps(['-crf', '30', '-preset', '6', '-svtav1-params', 'tune=0']), encoding='utf-8')
        out = self.root / 'custom'
        self.run_script([self.source], '--encoder', 'svt-av1', '--params-file', params, '--output-dir', out)
        self.inspect(out / (self.source.stem + '_svt-av1.mp4'), 'av1', 10)
        params.write_text(json.dumps(['-this-option-does-not-exist', '1']), encoding='utf-8')
        failed = self.root / 'failure'
        self.run_script([self.source], '--encoder', 'svt-av1', '--params-file', params, '--output-dir', failed, expected=1)
        self.assertFalse(list(failed.glob('*.mp4')))
        self.assertTrue(list(failed.glob('.encode-*')))
        self.assertEqual(json.loads(next((failed / 'logs').glob('*.json')).read_text(encoding='utf-8'))['status'], 'failed')

    def test_07_duplicate_output_rejected(self):
        other = self.root / 'other'
        other.mkdir()
        duplicate = other / self.source.name
        shutil.copy2(self.source, duplicate)
        self.run_script([self.source, duplicate], '--encoder', 'svt-av1', '--output-dir', self.root / 'collision', expected=2)

    def test_08_recursive_directory(self):
        folder = self.root / 'recursive'
        nested = folder / 'nested'
        nested.mkdir(parents=True)
        shutil.copy2(self.silent, nested / 'clip.mp4')
        self.run_script([folder], '--recursive', '--encoder', 'svt-av1')
        self.inspect(nested / 'encoded' / 'clip_svt-av1.mp4', 'av1', 10, audio=False)
        self.run_script([folder], '--recursive', '--encoder', 'svt-av1')
        self.assertFalse((nested / 'encoded' / 'encoded').exists())


    def test_09_av1_seek_and_progress(self):
        source = self.root / 'seek-source.mp4'
        self.cmd([self.ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                  'testsrc2=size=160x90:rate=30', '-t', '10', '-c:v', 'libx264',
                  '-preset', 'ultrafast', str(source)])
        args = encode.build_parser().parse_args([str(source), '--encoder', 'svt-av1'])
        args.bit_depth, args.audio, args.container = 10, 'copy', 'mp4'
        events = []
        args.progress = events.append
        destination = self.root / 'seek-fixed.mp4'
        cfg = encode.load_config(encode.ROOT / 'config.json')
        original_params = list(cfg['profiles']['svt-av1']['params'])
        report = encode.encode_one(source, destination, args, cfg,
                                   {'ffmpeg': self.ffmpeg, 'ffprobe': self.ffprobe})
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(original_params, cfg['profiles']['svt-av1']['params'])
        values = [e['value'] for e in events if e['type'] == 'progress']
        self.assertTrue(any(0 < x < 100 for x in values))
        self.assertEqual(values[-1], 100)
        packets = json.loads(subprocess.run([self.ffprobe, '-v', 'error', '-select_streams', 'v:0',
            '-show_packets', '-show_entries', 'packet=pts_time,flags', '-of', 'json', str(destination)],
            capture_output=True, check=True).stdout)['packets']
        keys = [float(p['pts_time']) for p in packets if 'K' in p['flags']]
        self.assertGreaterEqual(len(keys), 4)
        self.assertLessEqual(max(b-a for a, b in zip(keys, keys[1:])), 2.2)
        for position in ('3.5', '7.5', '9'):
            self.cmd([self.ffmpeg, '-v', 'error', '-xerror', '-ss', position, '-i', str(destination),
                      '-frames:v', '1', '-f', 'null', '-'])
        self.results.append({'output': str(destination), 'keyframes_seconds': keys,
                             'progress_events': len(values), 'seek_decode_passed': True})


    def test_10_gui_worker_batch_both_encoders(self):
        import gui
        import queue
        import threading
        from types import SimpleNamespace
        worker = SimpleNamespace(events=queue.Queue(), cancel=threading.Event())
        sources = [self.source, self.silent]
        output = self.root / 'gui-worker'
        jobs = [(s, output / (s.stem + '_' + enc + '.mp4'), enc)
                for s in sources for enc in ('x265', 'svt-av1')]
        gui.App.worker(worker, sources, jobs, self.cfg)
        events = []
        while not worker.events.empty():
            events.append(worker.events.get_nowait())
        self.assertFalse([e for e in events if e['type'] == 'error'])
        self.assertIn('完成 4 份', events[-1]['text'])
        job_events = [e for e in events if e['type'] == 'job']
        self.assertEqual(len(job_events), 4)
        self.assertIn('1/2 个视频', job_events[0]['text'])
        self.assertIn('2/2 个视频', job_events[-1]['text'])
        self.assertEqual(sum(e['type'] == 'progress' and e['value'] == 100 for e in events), 4)
        self.assertTrue(all(d.is_file() for _, d, _ in jobs))


if __name__ == '__main__':
    unittest.main(verbosity=2)
