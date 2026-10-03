"""Local build, verification and release packaging; never installs or publishes."""
import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'dependencies.lock.json').read_text(encoding='utf-8'))
VENDOR = ROOT / 'vendor'
TOOLS = ROOT / 'dist' / 'overlay' / 'tools'
BUILD = ROOT / 'build'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args, cwd=ROOT, env=None, log=None, check=True):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    output = result.stdout + result.stderr
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        Path(log).write_bytes(output)
    if check and result.returncode:
        raise RuntimeError(f'{args[0]} exited {result.returncode}:\n' +
                           output.decode('utf-8', errors='replace')[-2500:])
    return result


def exe(depth):
    return TOOLS / f'x264_64-{depth}bit.exe'


def payload(depth):
    runtime = LOCK['ffmpeg']['runtime_executables'] + LOCK['ffmpeg']['runtime_dlls']
    return [exe(depth), *(TOOLS / name for name in runtime)]


def hashes(depth):
    return {p.name: sha(p) for p in payload(depth)}


def ffmpeg():
    return VENDOR / 'ffmpeg' / 'bin' / 'ffmpeg.exe'


def ffprobe(path):
    result = run([VENDOR / 'ffmpeg' / 'bin' / 'ffprobe.exe', '-v', 'error',
                  '-show_streams', '-show_format', '-of', 'json', path])
    return json.loads(result.stdout)


def doctor():
    git = shutil.which('git')
    configured_bash = os.environ.get('MARUKO_BASH')
    git_bash = Path(git).resolve().parent.parent / 'bin' / 'bash.exe' if git else None
    discovered_bash = str(git_bash) if git_bash and git_bash.is_file() else shutil.which('bash')
    if not (configured_bash or discovered_bash):
        raise RuntimeError('Install Git Bash or set MARUKO_BASH to its executable.')
    bash = Path(configured_bash or discovered_bash).resolve()
    configured_chain = os.environ.get('MARUKO_TOOLCHAIN')
    gcc = shutil.which('gcc')
    if not (configured_chain or gcc):
        raise RuntimeError('Install MinGW-w64 on PATH or set MARUKO_TOOLCHAIN to its bin directory.')
    chain = Path(configured_chain).resolve() if configured_chain else Path(gcc).resolve().parent
    if not bash.is_file():
        raise RuntimeError('Set MARUKO_BASH to the Git Bash executable.')
    target = run([chain / 'gcc.exe', '-dumpmachine']).stdout.decode().strip()
    if target != 'x86_64-w64-mingw32':
        raise RuntimeError(f'A Windows x64 MinGW-w64 toolchain is required; found {target}.')
    for name, flag in [('gcc.exe', '-dumpversion'), ('nasm.exe', '-v'),
                       ('mingw32-make.exe', '--version')]:
        text = run([chain / name, flag]).stdout.decode(errors='replace')
        print(f'{name}: {text.splitlines()[0]}', flush=True)
    for name in ['git', 'tar']:
        if not shutil.which(name):
            raise RuntimeError(f'{name} is required on PATH.')
    print(f'Python: {sys.executable}\nGit Bash: {bash}\nToolchain: {chain}', flush=True)
    return bash, chain


def prepare():
    VENDOR.mkdir(exist_ok=True)
    for key, folder in [('x264', 'x264'), ('lsmash', 'l-smash')]:
        dep, dest = LOCK[key], VENDOR / folder
        if not dest.exists():
            run(['git', 'clone', dep['url'], dest])
            run(['git', 'checkout', '--detach', dep['commit']], cwd=dest)
        current = run(['git', 'rev-parse', 'HEAD'], cwd=dest).stdout.decode().strip()
        if current != dep['commit']:
            raise RuntimeError(f'{folder}: checkout differs from lock; preserve changes before updating.')
    dep = LOCK['ffmpeg']
    if not (VENDOR / 'ffmpeg').exists():
        cache = ROOT / '.cache'
        cache.mkdir(exist_ok=True)
        archive = cache / f'ffmpeg-{dep["version"]}-shared.7z'
        if not archive.exists():
            request = urllib.request.Request(dep['url'], headers={'User-Agent': 'maruko_tool_update'})
            with urllib.request.urlopen(request, timeout=30) as response, archive.open('wb') as out:
                shutil.copyfileobj(response, out)
        if sha(archive) != dep['sha256']:
            raise RuntimeError('FFmpeg archive SHA256 mismatch; remove the failed cache and retry.')
        listing = run(['tar', '-tf', archive]).stdout.decode().splitlines()
        for name in listing:
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or path.parts[0] != dep['archive_root']:
                raise RuntimeError('Unexpected archive path.')
        unpack = cache / 'unpack'
        unpack.mkdir(exist_ok=True)
        run(['tar', '-xf', archive, '-C', unpack])
        (unpack / dep['archive_root']).rename(VENDOR / 'ffmpeg')
    version = run([ffmpeg(), '-version']).stdout.decode(errors='replace').splitlines()[0]
    if f'version {dep["version"]}' not in version:
        raise RuntimeError('FFmpeg vendor version differs from lock.')
    for name in dep['runtime_executables'] + dep['runtime_dlls']:
        if not (VENDOR / 'ffmpeg' / 'bin' / name).is_file():
            raise RuntimeError(f'Missing runtime dependency: {name}')
    for patch in sorted((ROOT / 'patches').glob('*.patch')):
        args = ['git', 'apply', '--check', patch]
        result = run(args, cwd=VENDOR / 'x264', check=False)
        if result.returncode == 0:
            run(['git', 'apply', patch], cwd=VENDOR / 'x264')
        elif run(['git', 'apply', '--reverse', '--check', patch], cwd=VENDOR / 'x264', check=False).returncode:
            raise RuntimeError(f'Patch cannot be applied or confirmed: {patch.name}')
    print('Pinned sources, FFmpeg development package and patches ready.', flush=True)


def build(depth):
    bash, chain = doctor()
    prepare()
    buffer = ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.GetShortPathNameW(str(bash), buffer, len(buffer)):
        raise RuntimeError('Cannot determine make-compatible Git Bash path.')
    shell = buffer.value.replace('\\', '/')
    if ' ' in shell:
        raise RuntimeError('GNU make needs a Bash path without spaces; use a suitable MARUKO_BASH path.')
    env = dict(os.environ, MARUKO_TOOLCHAIN=str(chain), MARUKO_MAKE_SHELL=shell)
    run([bash, ROOT / 'scripts' / 'build.sh', depth], env=env, log=BUILD / 'logs' / 'build-driver.log')
    for name in LOCK['ffmpeg']['runtime_executables'] + LOCK['ffmpeg']['runtime_dlls']:
        shutil.copy2(VENDOR / 'ffmpeg' / 'bin' / name, TOOLS / name)
    print(run([exe(depth), '--version']).stdout.decode(errors='replace'), flush=True)


def verify(depth, toolbox):
    paths = hashes(depth)
    work = BUILD / f'verify-{depth}'
    work.mkdir(parents=True, exist_ok=True)
    fixture = work / '\u6d4b\u8bd5\u7d20\u6750.mp4'
    runtime = TOOLS / 'ffmpeg.exe'
    version = run([runtime, '-version'], log=work / 'ffmpeg-version.log').stdout.decode(errors='replace')
    if f'version {LOCK["ffmpeg"]["version"]}' not in version:
        raise RuntimeError('Packaged FFmpeg version differs from lock.')
    run([runtime, '-hide_banner', '-nostdin', '-y', '-f', 'lavfi', '-i',
         'testsrc2=size=320x180:rate=30', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100',
         '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', fixture],
        log=work / 'fixture.log')
    base = ['--crf', '24', '--preset', '8', '-I', '300', '-r', '4', '-b', '3',
            '--me', 'umh', '-i', '1', '--scenecut', '60', '-f', '1:1', '--qcomp', '0.5',
            '--psy-rd', '0.3:0', '--aq-mode', '2', '--aq-strength', '0.8', '--frames', '60']
    cases, skipped = [], []
    report = {'schema': 1, 'status': 'failed', 'bit_depth': depth,
              'files': paths, 'cases': cases, 'skipped': skipped, 'ui_verified': False}
    env = dict(os.environ)
    if toolbox:
        env['PATH'] = str(toolbox / 'tools') + os.pathsep + env.get('PATH', '')
    expected = 'yuv420p' if depth == 8 else 'yuv420p10le'

    def encode(name, extra, width, height):
        output = work / f'{name}.mp4'
        run([exe(depth), *base, *extra, '-o', output, fixture], env=env, log=work / f'{name}.log')
        data = ffprobe(output)
        stream = next(s for s in data['streams'] if s['codec_type'] == 'video')
        if (stream['codec_name'], stream['pix_fmt'], stream['width'], stream['height'],
            int(stream['nb_frames'])) != ('h264', expected, width, height, 60):
            raise RuntimeError(f'{name}: unexpected codec, depth, dimensions or frame count.')
        cases.append({'name': name, 'passed': True})
        return output

    try:
        cases.append({'name': 'packaged-ffmpeg-version', 'passed': True})
        plain = encode('direct-input', [], 320, 180)
        encode('resize', ['--vf', 'resize:160,90,,,,lanczos'], 160, 90)
        if toolbox and (toolbox / 'tools' / 'VSFilter64.dll').is_file():
            subtitles = work / 'compatibility.srt'
            subtitles.write_text('1\n00:00:00,000 --> 00:00:02,000\nmaruko_tool_update\n', encoding='utf-8')
            burned = encode('subtitles', ['--sub', str(subtitles), '--vf', 'subtitles'], 320, 180)
            run([runtime, '-v', 'error', '-y', '-ss', '0.5', '-i', burned,
                 '-frames:v', '1', work / 'subtitle-check.png'])
        else:
            skipped.append('Original VSFilter64 subtitle integration; no toolbox provided.')
        audio = work / 'audio.aac'
        run([runtime, '-v', 'error', '-y', '-i', fixture, '-vn', '-sn', '-c:a', 'copy',
             '-map', '0:a:0', audio], log=work / 'audio.log')
        copied = ffprobe(audio)['streams'][0]
        if copied['codec_name'] != 'aac' or copied['sample_rate'] != '44100':
            raise RuntimeError('Packaged FFmpeg audio extraction failed validation.')
        cases.append({'name': 'packaged-ffmpeg-audio-copy', 'passed': True})
        converted = work / 'audio-converted.m4a'
        run([runtime, '-v', 'error', '-y', '-i', fixture, '-vn', '-sn', '-c:a', 'aac',
             '-b:a', '96k', '-ar', '48000', '-ac', '2', converted], log=work / 'audio-convert.log')
        stream = ffprobe(converted)['streams'][0]
        if (stream['codec_name'], stream['sample_rate'], stream['channels']) != ('aac', '48000', 2):
            raise RuntimeError('Packaged FFmpeg AAC conversion failed validation.')
        cases.append({'name': 'packaged-ffmpeg-audio-conversion', 'passed': True})
        if toolbox and (toolbox / 'tools' / 'MP4Box.exe').is_file():
            muxed = work / 'muxed.mp4'
            run([toolbox / 'tools' / 'MP4Box.exe', '-add', f'{plain}#trackID=1:name=',
                 '-add', f'{audio}#trackID=1:name=', '-new', muxed], log=work / 'mux.log')
            data = ffprobe(muxed)
            if [s['codec_name'] for s in data['streams']] != ['h264', 'aac']:
                raise RuntimeError('MP4Box output must contain H.264 and AAC.')
            if abs(float(data['format']['duration']) - 2) > 0.1:
                raise RuntimeError('Unexpected muxed duration.')
            cases.append({'name': 'external-audio-and-original-MP4Box', 'passed': True})
        else:
            skipped.append('Original MP4Box integration; no toolbox provided.')
        run([runtime, '-v', 'error', '-i', plain, '-f', 'null', '-'], log=work / 'decode.log')
        cases.append({'name': 'output-decodes', 'passed': True})
        report['status'] = 'passed'
    finally:
        (BUILD / f'verification-{depth}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


def package(depth):
    current = hashes(depth)
    report = json.loads((BUILD / f'verification-{depth}.json').read_text(encoding='utf-8'))
    if report['status'] != 'passed' or report['files'] != current:
        raise RuntimeError('Re-run verification: current EXE/DLL hashes are not covered by a passing report.')
    overlay = TOOLS.parent
    instructions = (ROOT / 'packaging' / 'README.md').read_text(encoding='utf-8')
    instructions += '\n## 本包实际覆盖文件\n\n'
    instructions += '\n'.join(f'- `tools/{path.name}`' for path in payload(depth)) + '\n'
    (overlay / 'README.md').write_text(instructions, encoding='utf-8')
    licenses = overlay / 'licenses'
    licenses.mkdir(exist_ok=True)
    for source, name in [(VENDOR / 'x264' / 'COPYING', 'COPYING-x264.txt'),
                         (VENDOR / 'ffmpeg' / 'LICENSE', 'LICENSE-FFmpeg.txt'),
                         (VENDOR / 'l-smash' / 'LICENSE', 'LICENSE-L-SMASH.txt')]:
        shutil.copy2(source, licenses / name)
    third_party = overlay / 'third-party'
    third_party.mkdir(exist_ok=True)
    shutil.copy2(VENDOR / 'ffmpeg' / 'README.txt', third_party / 'FFmpeg-build-info.txt')
    for patch in sorted((ROOT / 'patches').glob('*.patch')):
        shutil.copy2(patch, third_party / patch.name)
    manifest = {'project': 'maruko_tool_update', 'channel': 'candidate',
                'bit_depth': depth, 'dependencies': LOCK, 'files': current, 'verification': report,
                'patches': {p.name: sha(p) for p in sorted((ROOT / 'patches').glob('*.patch'))},
                'limitations': ['UI/batch/cancel not verified', 'FFMS and AviSynth disabled',
                                '7mod keyint auto not restored', 'not a complete original 7mod reproduction']}
    (overlay / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    version = LOCK['x264']['version'].replace('+', '_').replace('.', '_')
    name = (f'maruko_tool_update-x264-x64-{depth}bit-{version}'
            f'-ffmpeg-{LOCK["ffmpeg"]["version"]}-{dt.date.today():%Y%m%d}.zip')
    archive = ROOT / 'dist' / name
    files = [*payload(depth), overlay / 'README.md', overlay / 'manifest.json',
             *licenses.glob('*.txt'), *third_party.glob('*.txt'), *third_party.glob('*.patch')]
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as output:
        for path in sorted(files):
            output.write(path, path.relative_to(overlay))
    with zipfile.ZipFile(archive) as check:
        if check.testzip():
            raise RuntimeError('ZIP validation failed.')
    archive.with_suffix('.zip.sha256').write_text(f'{sha(archive)}  {archive.name}\n', encoding='ascii')
    print(f'Candidate ZIP: {archive}\nNo release was published.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'prepare', 'build', 'verify', 'package'])
    parser.add_argument('--bit-depth', type=int, choices=[8, 10], default=8)
    parser.add_argument('--toolbox', type=Path)
    args = parser.parse_args()
    if args.command in ['doctor', 'prepare']:
        globals()[args.command]()
    elif args.command == 'verify':
        verify(args.bit_depth, args.toolbox.resolve() if args.toolbox else None)
    else:
        globals()[args.command](args.bit_depth)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
