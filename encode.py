#!/usr/bin/env python3
"""Single/batch video encoding, using Maruko-style separate audio/video/mux stages."""
from __future__ import annotations

import argparse
from fractions import Fraction
import glob
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import threading
import uuid

ROOT = Path(__file__).resolve().parent
EXTENSIONS = {'.mp4', '.mkv', '.mov', '.avi', '.flv', '.webm', '.ts', '.m2ts', '.m4v', '.wmv'}
DEFAULTS = {
    'tools_dir': '',
    'ffprobe': '',
    'encoder': 'x265', 'bit_depth': 10, 'audio': 'copy', 'container': 'mp4',
    'profiles': {
        'x265': {'params': ['--crf', '23', '--preset', 'slow', '--ref', '6', '-b', '6',
                           '-I', '60', '-i', '1', '--scenecut', '40', '--deblock', '-1:-1',
                           '--qcomp', '0.7', '--weightb', '--b-intra', '--rd', '3',
                           '--psy-rd', '2.0', '--psy-rdoq', '0', '--aq-mode', '4',
                           '--aq-strength', '0.8', '--cbqpoffs', '-2', '--crqpoffs', '-2', '--no-sao']},
        'svt-av1': {'params': ['-crf', '28', '-preset', '5', '-svtav1-params',
                               'tune=0:keyint=120:irefresh-type=2']},
    },
}


def load_config(path: Path) -> dict:
    data = json.loads(json.dumps(DEFAULTS))
    # The checked-in template supplies portable defaults; the user's file wins.
    template = ROOT / 'config.example.json'
    for source in dict.fromkeys((template, Path(path))):
        if not source.exists():
            continue
        custom = json.loads(source.read_text(encoding='utf-8-sig'))
        for key, value in custom.items():
            if key == 'profiles':
                for name, profile in value.items():
                    data['profiles'].setdefault(name, {}).update(profile)
            else:
                data[key] = value
    data['profiles'].pop('x264', None)
    return data


def save_config(path: Path, data: dict) -> None:
    """Atomic settings save; never leave half-written JSON after interruption."""
    fd, name = tempfile.mkstemp(prefix=path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def executable(value: str | Path | None, *fallbacks: str | Path) -> str:
    for candidate in ((value, *fallbacks) if value else fallbacks):
        if not candidate:
            continue
        candidate = os.path.expandvars(str(candidate))
        p = Path(candidate).expanduser()
        if p.is_file():
            return str(p.resolve())
        found = shutil.which(candidate)
        if found:
            return found
    raise ValueError('找不到程序：' + ', '.join(str(x) for x in (value, *fallbacks) if x))


def config_executable(value):
    """Configured paths are relative to the project, not the launcher's cwd."""
    if not value:
        return None
    value = os.path.expandvars(str(value))
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    if '/' in value or '\\' in value:
        return str(ROOT / path)
    return value


def resolve_paths(cfg: dict, args) -> dict:
    """Shared GUI/CLI tool discovery, including this repository's build outputs."""
    directories = []
    if cfg.get('tools_dir'):
        tools = Path(os.path.expandvars(cfg['tools_dir'])).expanduser()
        directories.append(tools if tools.is_absolute() else ROOT / tools)
    directories += [ROOT / 'tools', ROOT / 'dist' / 'overlay' / 'tools',
                    ROOT / 'vendor' / 'ffmpeg' / 'bin']

    def find(option, *names, preferred=()):
        override = getattr(args, option, None)
        configured = config_executable(cfg.get(option))
        return executable(override or configured, *preferred,
                          *(directory / name for directory in directories for name in names), *names)

    ffmpeg = find('ffmpeg', 'ffmpeg.exe', 'ffmpeg')
    paths = {'ffmpeg': ffmpeg, 'ffprobe': find('ffprobe', 'ffprobe.exe', 'ffprobe',
             preferred=(Path(ffmpeg).with_name('ffprobe.exe'), Path(ffmpeg).with_name('ffprobe')))}
    if args.encoder == 'x265':
        names = ('x265_64-%sbit[gcc].exe' % args.bit_depth, 'x265')
        paths['encoder'] = executable(getattr(args, 'encoder_path', None) or
            config_executable(cfg['profiles']['x265'].get('path')),
            *(directory / name for directory in directories for name in names), 'x265')
        paths['mp4box'] = find('mp4box', 'MP4Box.exe', 'MP4Box')
    return paths


def collect_inputs(values: list[str], recursive: bool) -> list[Path]:
    found = []
    for value in values:
        literal = Path(value).expanduser()
        matches = [literal] if literal.exists() else [Path(p) for p in glob.glob(value, recursive=recursive)]
        if not matches:
            raise ValueError('输入不存在或通配符没有匹配：' + value)
        for p in matches:
            if p.is_dir():
                found.extend(q.resolve() for q in (p.rglob('*') if recursive else p.iterdir())
                             if q.is_file() and q.suffix.lower() in EXTENSIONS)
            elif p.is_file():
                found.append(p.resolve())
    result = list(dict.fromkeys(sorted(found, key=lambda p: str(p).lower())))
    if not result:
        raise ValueError('没有找到视频文件。')
    return result


def probe(ffprobe: str, path: Path) -> dict:
    result = subprocess.run([ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                            capture_output=True, check=True)
    return json.loads(result.stdout)


def frame_rate(stream: dict, override: str | None) -> str:
    rate = Fraction(override or stream.get('avg_frame_rate', '0/1'))
    if rate <= 0 or rate > 1000:
        raise ValueError('无法确定帧率，请使用 --fps，例如 --fps 24000/1001。')
    nominal = Fraction(stream.get('r_frame_rate', '0/1'))
    if not override and nominal > 0 and abs(float(nominal - rate)) > 0.05:
        raise ValueError('检测到可能的可变帧率；此管道按恒定帧率工作，请用 --fps 明确目标帧率。')
    return str(rate.numerator) + '/' + str(rate.denominator)


def check_params(params: list, encoder: str) -> list[str]:
    if not isinstance(params, list) or not all(isinstance(x, str) for x in params):
        raise ValueError('params 必须是 JSON 字符串数组。')
    # The script owns input/output/mapping. Never execute a shell or command string.
    if encoder not in ('x265', 'svt-av1'):
        raise ValueError('只支持 x265 和 SVT-AV1。')
    reserved = {'-o', '--output', '--input', '--y4m', '--demuxer', '-progress', '-stats_period'}
    if encoder == 'svt-av1':
        reserved |= {'-i', '-map', '-y', '-n', '-f', '-vf', '-af', '-filter_complex', '-c:v', '-vcodec',
                     '-an', '-vn', '-sn', '-pix_fmt', '-r', '-fps_mode', '-t', '-to', '-ss', '-frames:v'}
    else:
        reserved |= {'--frames', '--seek', '--fps', '--input-res', '--input-depth', '--output-depth'}
    for token in params:
        if token.split('=', 1)[0] in reserved:
            raise ValueError('输入、输出、帧率及位深由脚本管理，请勿在 params 中设置：' + token)
    return params


def seekable_av1_params(params: list[str], fps: str) -> list[str]:
    """Closed GOP is mandatory: forward frames in IVF lose random-access indexing."""
    result = []
    options = []
    i = 0
    while i < len(params):
        if params[i] == '-svtav1-params':
            if i + 1 >= len(params):
                raise ValueError('-svtav1-params 缺少值。')
            options.extend(params[i + 1].split(':'))
            i += 2
        else:
            result.append(params[i])
            i += 1
    max_gop = max(1, round(float(Fraction(fps)) * 4))
    keyints = [x.split('=', 1)[1] for x in options if x.startswith('keyint=')]
    if keyints:
        try:
            keyint = int(keyints[-1])
        except ValueError:
            raise ValueError('AV1 keyint 请填写正整数帧数。') from None
        if not 1 <= keyint <= max_gop:
            raise ValueError('为保证快进，AV1 keyint 需在 1 到 %s 帧之间；请自行修改参数。' % max_gop)
    else:
        options.append('keyint=' + str(max_gop))
    options = [x for x in options if x and x.split('=', 1)[0] != 'irefresh-type']
    options.append('irefresh-type=2')
    return result + ['-svtav1-params', ':'.join(options)]


class EncodingCancelled(Exception):
    pass


class Runner:
    def __init__(self, log: Path, dry_run: bool = False, progress=None, cancel=None, duration=0):
        self.log = log
        self.dry_run = dry_run
        self.progress = progress
        self.cancel = cancel
        self.duration = duration
        self.commands: list[list[str]] = []

    def read_progress(self, stream):
        with self.log.open('ab') as out:
            for line in iter(stream.readline, b''):
                out.write(line)
                if self.progress and self.duration and line.startswith(b'out_time_us='):
                    try:
                        seconds = int(line.split(b'=', 1)[1]) / 1_000_000
                        self.progress({'type': 'progress', 'value': min(99, max(0, seconds / self.duration * 100))})
                    except ValueError:
                        pass
        stream.close()

    def wait(self, child):
        while True:
            if self.cancel is not None and self.cancel.is_set():
                raise EncodingCancelled('已取消压制。')
            try:
                return child.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass

    def record(self, args: list[str]) -> None:
        self.commands.append(args)
        line = subprocess.list2cmdline(args)
        with self.log.open('ab') as out:
            out.write(('\n$ ' + line + '\n').encode('utf-8'))
        if self.dry_run:
            print(line)

    @staticmethod
    def stop(process: subprocess.Popen | None) -> None:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()

    def run(self, args: list[str]) -> None:
        self.record(args)
        if self.dry_run:
            return
        child = None
        try:
            with self.log.open('ab') as out:
                track = self.progress is not None and 'libsvtav1' in args
                command = args[:1] + ['-progress', 'pipe:1', '-stats_period', '0.3'] + args[1:] if track else args
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE if track else out, stderr=out)
                reader = None
                if track:
                    reader = threading.Thread(target=self.read_progress, args=(child.stdout,), daemon=True)
                    reader.start()
                if self.wait(child) != 0:
                    raise RuntimeError(Path(args[0]).name + ' 执行失败，详见日志。')
                if reader:
                    reader.join()
        finally:
            self.stop(child)

    def pipe(self, decoder_args: list[str], encoder_args: list[str]) -> None:
        self.record(decoder_args)
        self.record(encoder_args)
        if self.dry_run:
            return
        decoder = encoder = None
        try:
            with self.log.open('ab') as out:
                track = self.progress is not None
                command = decoder_args[:1] + ['-progress', 'pipe:2', '-stats_period', '0.3'] + decoder_args[1:] if track else decoder_args
                decoder = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE if track else out)
                reader = None
                if track:
                    reader = threading.Thread(target=self.read_progress, args=(decoder.stderr,), daemon=True)
                    reader.start()
                encoder = subprocess.Popen(encoder_args, stdin=decoder.stdout, stdout=out, stderr=out)
                decoder.stdout.close()
                encoder_status = self.wait(encoder)
                if encoder_status:
                    raise RuntimeError('编码器失败（退出码 %s），详见日志。' % encoder_status)
                decoder_status = self.wait(decoder)
                if reader:
                    reader.join()
                if decoder_status:
                    raise RuntimeError('FFmpeg 解码失败（退出码 %s），详见日志。' % decoder_status)
        finally:
            if decoder is not None and decoder.stdout is not None:
                decoder.stdout.close()
            self.stop(encoder)
            self.stop(decoder)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：python encode.py "D:/视频/*.mp4" --encoder svt-av1\n'
               '参数在 config.json 的 profiles 中修改；x265 使用独立程序参数，SVT 使用 FFmpeg 参数。')
    p.add_argument('inputs', nargs='+', help='视频文件、目录或通配符；可一次传多个')
    p.add_argument('--config', type=Path, default=ROOT / 'config.json')
    p.add_argument('--encoder', choices=['x265', 'svt-av1'])
    p.add_argument('--encoder-path', help='覆盖 x265 独立编码器路径；SVT 使用 FFmpeg 内置库')
    p.add_argument('--ffmpeg')
    p.add_argument('--ffprobe')
    p.add_argument('--mp4box')
    p.add_argument('--params-file', type=Path, help='JSON 字符串数组，完整替换当前编码器的参数')
    p.add_argument('--bit-depth', type=int, choices=[8, 10])
    p.add_argument('--audio', choices=['copy', 'aac', 'none'], help='第一条音轨：复制、转 AAC 或不保留')
    p.add_argument('--audio-bitrate', default='192k')
    p.add_argument('--container', choices=['mp4', 'mkv'])
    p.add_argument('--output-dir', type=Path, help='默认每个输入目录下的 encoded 子目录')
    p.add_argument('--recursive', action='store_true')
    p.add_argument('--fps', help='目标恒定帧率，如 24000/1001；默认使用源平均帧率')
    p.add_argument('--vf', help='FFmpeg 视频滤镜，例如 scale=1280:-2')
    p.add_argument('--overwrite', action='store_true', help='明确允许覆盖既有输出；永不覆盖输入')
    p.add_argument('--keep-temp', action='store_true', help='成功也保留中间文件；失败始终保留')
    p.add_argument('--dry-run', action='store_true', help='探测输入并展示命令，不编码')
    return p


def encode_one(source: Path, destination: Path, args, cfg: dict, paths: dict) -> dict:
    if destination.resolve() == source.resolve():
        raise ValueError('输出不能覆盖输入。')
    if destination.exists() and not args.overwrite:
        print('跳过已有输出：' + str(destination))
        return {'input': str(source), 'output': str(destination), 'status': 'skipped'}
    info = probe(paths['ffprobe'], source)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'
                  and not s.get('disposition', {}).get('attached_pic')), None)
    if video is None:
        raise ValueError('输入没有可编码的视频流。')
    # Do not silently turn HDR into incorrectly tagged SDR via the Y4M pipeline.
    if video.get('color_transfer') in ('smpte2084', 'arib-std-b67'):
        raise ValueError('当前脚本不处理 HDR 元数据；请先明确 HDR 保留或色调映射方案。')
    fps = frame_rate(video, args.fps)
    # GPAC 0.5.1 accepts a decimal, but parses a rational such as 30000/1001 as 30000.
    mp4box_fps = format(float(Fraction(fps)), '.12g')
    has_audio = args.audio != 'none' and any(s['codec_type'] == 'audio' for s in info['streams'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    logs = destination.parent / 'logs'
    logs.mkdir(exist_ok=True)
    job = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    log = logs / (destination.stem + '-' + job + '.log')
    work = Path(tempfile.mkdtemp(prefix='.encode-' + job + '-', dir=destination.parent))
    duration = float(video.get('duration') or info.get('format', {}).get('duration') or 0)
    progress = getattr(args, 'progress', None)
    runner = Runner(log, args.dry_run, progress, getattr(args, 'cancel', None), duration)
    report = {'input': str(source), 'output': str(destination), 'encoder': args.encoder,
              'fps': fps, 'bit_depth': args.bit_depth, 'audio': args.audio if has_audio else 'none',
              'log': str(log), 'work_dir': str(work), 'status': 'running', 'commands': runner.commands}
    report_path = log.with_suffix('.json')
    start = time.monotonic()
    try:
        ff = [paths['ffmpeg'], '-hide_banner', '-nostdin', '-y']
        # M4A preserves compressed audio packets without an ADTS round trip.
        audio = work / ('audio.m4a' if args.container == 'mp4' else 'audio.mka')
        if has_audio:
            print('  [1/3] 音轨提取' + (' / AAC 转码' if args.audio == 'aac' else '（不重编码）'))
            audio_params = ['-c:a', 'copy'] if args.audio == 'copy' else ['-c:a', 'aac', '-b:a', args.audio_bitrate]
            runner.run(ff + ['-i', str(source), '-map', '0:a:0', '-vn', '-sn', '-dn',
                             *audio_params, str(audio)])
        print('  [2/3] 视频编码；实时日志：' + str(log))
        pix_fmt = 'yuv420p10le' if args.bit_depth == 10 else 'yuv420p'
        decode = ff + ['-i', str(source), '-map', '0:' + str(video['index']), '-an', '-sn', '-dn']
        if args.vf:
            decode += ['-vf', args.vf]
        decode += ['-pix_fmt', pix_fmt, '-r', fps, '-fps_mode', 'cfr']
        params = cfg['profiles'][args.encoder]['params']
        if args.encoder == 'x265':
            encoded = work / 'video.hevc'
            decode += ['-strict', '-1', '-f', 'yuv4mpegpipe', '-']
            runner.pipe(decode, [paths['encoder'], '--y4m', *params, '-o', str(encoded), '-'])
        else:
            encoded = work / 'video.ivf'
            params = seekable_av1_params(params, fps)
            runner.run(decode + ['-c:v', 'libsvtav1', *params, '-f', 'ivf', str(encoded)])
        print('  [3/3] 封装 ' + args.container.upper())
        if progress:
            progress({'type': 'stage', 'text': '正在封装并检查输出…'})
        staged = work / ('finished.' + args.container)
        if args.encoder == 'x265' and args.container == 'mp4':
            mux = [paths['mp4box'], '-fps', mp4box_fps, '-add', str(encoded) + '#trackID=1:name=']
            if has_audio:
                mux += ['-add', str(audio) + '#trackID=1:name=']
            runner.run(mux + ['-new', str(staged)])
        else:
            if args.encoder == 'x265':
                # Give HEVC B-frames correct DTS/PTS before remuxing to MKV.
                wrapped = work / 'video.mp4'
                runner.run([paths['mp4box'], '-fps', mp4box_fps, '-add', str(encoded), '-new', str(wrapped)])
                encoded = wrapped
            mux = ff + ['-i', str(encoded)]
            if has_audio:
                mux += ['-i', str(audio)]
            mux += ['-map', '0:v:0'] + (['-map', '1:a:0'] if has_audio else [])
            mux += ['-c', 'copy']
            if args.container == 'mp4':
                mux += ['-movflags', '+faststart']
            runner.run(mux + [str(staged)])
        if not args.dry_run:
            verified = probe(paths['ffprobe'], staged)
            v = next(s for s in verified['streams'] if s['codec_type'] == 'video')
            expected = {'x265': 'hevc', 'svt-av1': 'av1'}[args.encoder]
            if v['codec_name'] != expected:
                raise RuntimeError('输出编码格式检查失败。')
            expected_pix_fmt = 'yuv420p10le' if args.bit_depth == 10 else 'yuv420p'
            if v.get('pix_fmt') != expected_pix_fmt:
                raise RuntimeError('输出位深检查失败；请确认所选独立编码器的位深。')
            actual_rate = Fraction(v.get('avg_frame_rate', '0/1'))
            if abs(float(actual_rate / Fraction(fps)) - 1) > 0.001:
                raise RuntimeError('输出帧率异常：%s，目标 %s。' % (actual_rate, fps))
            if (not args.fps and video.get('nb_frames') and v.get('nb_frames')
                    and int(video['nb_frames']) != int(v['nb_frames'])):
                raise RuntimeError('输出帧数与输入不一致。')
            source_duration = float(video.get('duration') or info.get('format', {}).get('duration') or 0)
            output_duration = float(v.get('duration') or verified.get('format', {}).get('duration') or 0)
            if source_duration and abs(output_duration - source_duration) > max(0.2, 2 / float(Fraction(fps))):
                raise RuntimeError('输出视频时长异常：源 %.3f 秒，输出 %.3f 秒。' % (source_duration, output_duration))
            if args.encoder == 'svt-av1' and output_duration > 8:
                seek = output_duration / 2
                result = subprocess.run([paths['ffprobe'], '-v', 'error', '-select_streams', 'v:0',
                    '-read_intervals', str(seek) + '%+#1', '-show_packets',
                    '-show_entries', 'packet=pts_time,flags', '-of', 'json', str(staged)],
                    capture_output=True, check=True, timeout=30)
                packets = json.loads(result.stdout).get('packets', [])
                if not packets or abs(float(packets[0].get('pts_time', -100)) - seek) > 6:
                    raise RuntimeError('输出随机访问检查失败：中段没有可用的关键帧索引。')
            if sum(s['codec_type'] == 'audio' for s in verified['streams']) != int(has_audio):
                raise RuntimeError('输出音轨数量检查失败。')
            report['source_bytes'] = source.stat().st_size
            report['output_bytes'] = staged.stat().st_size
            report['size_ratio'] = round(report['output_bytes'] / report['source_bytes'], 4)
            if report['size_ratio'] >= 1:
                report['warning'] = '输出比源文件大；CRF 不保证体积缩小，可提高 CRF 后重试。'
                print('  警告：' + report['warning'])
            if args.overwrite:
                os.replace(staged, destination)
            else:
                # Atomic no-clobber publication on the same filesystem (also safe on POSIX).
                os.link(staged, destination)
                staged.unlink()
        if progress:
            progress({'type': 'progress', 'value': 100})
        report['status'] = 'dry-run' if args.dry_run else 'ok'
        if not args.keep_temp:
            shutil.rmtree(work)
        print(('  命令预览完成（未编码）：' if args.dry_run else '  完成：') + str(destination))
    except BaseException as exc:
        report['status'] = 'cancelled' if isinstance(exc, (KeyboardInterrupt, EncodingCancelled)) else 'failed'
        report['error'] = str(exc)
        print('  临时文件保留：' + str(work), file=sys.stderr)
        raise
    finally:
        report['seconds'] = round(time.monotonic() - start, 3)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        for name in ('encoder', 'bit_depth', 'audio', 'container'):
            if getattr(args, name) is None:
                setattr(args, name, cfg[name])
        if args.encoder not in DEFAULTS['profiles'] or args.bit_depth not in (8, 10):
            raise ValueError('不支持的 encoder 或 bit_depth 配置。')
        if args.audio not in ('copy', 'aac', 'none') or args.container not in ('mp4', 'mkv'):
            raise ValueError('audio 或 container 配置不正确。')
        if args.encoder_path and args.encoder == 'svt-av1':
            raise ValueError('SVT-AV1 通过 FFmpeg 的 libsvtav1 调用；请用 --ffmpeg 选择构建。')
        params = cfg['profiles'][args.encoder]['params']
        if args.params_file:
            params = json.loads(args.params_file.read_text(encoding='utf-8-sig'))
        cfg['profiles'][args.encoder]['params'] = check_params(params, args.encoder)
        paths = resolve_paths(cfg, args)
        inputs = collect_inputs(args.inputs, args.recursive)
        # Snapshot inputs before creating outputs; never include our output tree when traversing a source directory.
        outdir = args.output_dir.resolve() if args.output_dir else None
        if outdir:
            inputs = [p for p in inputs if not p.is_relative_to(outdir)]
        inputs = [p for p in inputs if not any(part == 'encoded' or part.startswith('.encode-') for part in p.parts)]
        if not inputs:
            raise ValueError('没有输入文件（输出目录及 encoded 子目录会被排除）。')
        jobs = []
        for source in inputs:
            parent = outdir or source.parent / 'encoded'
            jobs.append((source, parent / (source.stem + '_' + args.encoder + '.' + args.container)))
        destinations = [str(dst).casefold() for _, dst in jobs]
        if len(set(destinations)) != len(destinations):
            raise ValueError('多个输入会产生同名输出，请分开运行或使用不同输出目录。')
        failures = 0
        for n, (source, destination) in enumerate(jobs, 1):
            print('[%s/%s] %s' % (n, len(jobs), source), flush=True)
            try:
                encode_one(source, destination, args, cfg, paths)
            except KeyboardInterrupt:
                print('\n已取消，子进程已停止。', file=sys.stderr)
                return 130
            except Exception as exc:
                failures += 1
                print('失败：%s\n原因：%s' % (source, exc), file=sys.stderr)
        print('结束：%s 个任务，%s 个失败（已有输出默认跳过）。' % (len(jobs), failures))
        return 1 if failures else 0
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError, TypeError, ZeroDivisionError) as exc:
        print('错误：' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
