#!/usr/bin/env python3
"""Small native Windows/macOS/Linux encoding UI."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import queue
import shlex
import sys
import threading
import os

# Some Windows Conda builds decode their compiled-in Tcl path with the wrong
# code page when the user directory is non-ASCII. Use Python's Unicode path.
if sys.platform == 'win32':
    for name, folder in (('TCL_LIBRARY', 'tcl8.6'), ('TK_LIBRARY', 'tk8.6')):
        library = Path(sys.prefix) / 'Library' / 'lib' / folder
        if library.is_dir():
            os.environ.setdefault(name, str(library))

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import encode
import check_tools

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    Base = TkinterDnD.Tk
except ImportError:
    DND_FILES = None
    Base = tk.Tk

CONFIG = encode.ROOT / 'config.json'


def parse_params(text, encoder):
    return encode.check_params(shlex.split(text), encoder)


class App(Base):
    def __init__(self):
        super().__init__()
        self.title('Maruko Encode')
        self.geometry('830x660')
        self.minsize(690, 600)
        self.cfg = encode.load_config(CONFIG)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        self.save_after = None
        self.editors = {}
        self.choices = {}
        self.inputs = tk.StringVar()
        ui = self.cfg.get('ui', {})
        self.files = list(ui.get('files', []))
        self.inputs.set(' | '.join(self.files))
        self.folder = tk.StringVar(value=ui.get('folder', ''))
        self.output = tk.StringVar(value=ui.get('output', ''))
        self.recursive = tk.BooleanVar(value=ui.get('recursive', False))
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text='视频压制', font=('', 19, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 12))
        self.path_row(frame, 1, '视频文件', self.inputs, self.pick_files, '拖入一个或多个视频；也可点击右侧选择', 'files')
        self.path_row(frame, 2, '批量文件夹', self.folder, self.pick_folder, '拖入文件夹，与上面的文件合并去重', 'folder')
        self.path_row(frame, 3, '输出目录', self.output, self.pick_output, '留空：每个源文件旁的 encoded 目录', 'output')
        ttk.Checkbutton(frame, text='批量时包含子文件夹', variable=self.recursive,
                        command=self.schedule_save).grid(row=4, column=1, sticky='w', pady=(0, 12))
        depth = self.cfg['bit_depth']
        for row, (key, title) in enumerate((('x265', f'x265 · {depth}bit'),
                                          ('svt-av1', f'AV1 · {depth}bit')), 5):
            box = ttk.LabelFrame(frame, padding=10)
            box.grid(row=row, column=0, columnspan=3, sticky='ew', pady=(0, 10))
            enabled = tk.BooleanVar(value=key in ui.get('encoders', [self.cfg['encoder']]))
            self.choices[key] = enabled
            ttk.Checkbutton(box, text=title, variable=enabled, command=self.schedule_save).pack(anchor='w')
            editor = tk.Text(box, height=4, wrap='word', undo=True, font=('TkFixedFont', 10))
            editor.pack(fill='x', pady=(6, 0))
            editor.insert('1.0', shlex.join(self.cfg['profiles'][key]['params']))
            editor.bind('<KeyRelease>', self.schedule_save)
            editor.bind('<<Paste>>', self.schedule_save)
            self.editors[key] = editor
        actions = ttk.Frame(frame)
        actions.grid(row=8, column=0, columnspan=3, sticky='ew', pady=12)
        self.start_button = ttk.Button(actions, text='开始压制', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(actions, text='取消', command=self.stop, state='disabled')
        self.stop_button.pack(side='left', padx=10)
        ttk.Button(actions, text='保存参数', command=lambda: self.save(True)).pack(side='left')
        ttk.Button(actions, text='工具设置', command=self.tool_settings).pack(side='left', padx=10)
        self.saved = tk.StringVar(value='')
        ttk.Label(actions, textvariable=self.saved).pack(side='right')
        self.status = tk.StringVar(value='等待开始')
        ttk.Label(frame, textvariable=self.status, wraplength=740).grid(row=9, column=0, columnspan=3, sticky='w')
        self.percent = tk.DoubleVar(value=0)
        self.bar = ttk.Progressbar(frame, variable=self.percent, maximum=100)
        self.bar.grid(row=10, column=0, columnspan=3, sticky='ew', pady=8)
        self.detail = tk.StringVar(value='0%')
        ttk.Label(frame, textvariable=self.detail, wraplength=740).grid(row=11, column=0, columnspan=3, sticky='w')
        if not DND_FILES:
            self.saved.set('拖放未安装；可用选择按钮。pip install -r requirements.txt')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.pump)

    def path_row(self, frame, row, label, variable, browse, hint, kind):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=(0, 10))
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=row, column=1, sticky='ew', pady=5)
        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=2, padx=(10, 0))
        ttk.Button(buttons, text='选择…', command=browse).pack(side='left')
        ttk.Button(buttons, text='清空', width=5,
                   command=(lambda: self.set_files([])) if kind == 'files' else lambda: variable.set('')).pack(side='left', padx=(5, 0))
        if kind == 'files':
            # File list is controlled by drag/drop or the multi-file dialog.
            entry.configure(state='readonly')
        else:
            variable.trace_add('write', self.schedule_save)
        if DND_FILES:
            entry.drop_target_register(DND_FILES)
            entry.dnd_bind('<<Drop>>', lambda event: self.drop(kind, event.data))
        entry.bind('<FocusIn>', lambda event: self.detail.set(hint))

    def set_files(self, paths):
        self.files = list(dict.fromkeys(str(Path(p)) for p in paths))
        self.inputs.set(' | '.join(self.files))
        self.schedule_save()

    def drop(self, kind, data):
        paths = self.tk.splitlist(data)
        if kind == 'files':
            if any(not Path(p).is_file() or Path(p).suffix.lower() not in encode.EXTENSIONS for p in paths):
                messagebox.showerror('输入错误', '第一行请拖视频文件；文件夹请拖到第二行。')
                return
            self.set_files(paths)
        elif len(paths) != 1 or not Path(paths[0]).is_dir():
            messagebox.showerror('输入错误', '此处请拖入一个文件夹。')
        else:
            (self.folder if kind == 'folder' else self.output).set(paths[0])
        return 'copy'

    def pick_files(self):
        paths = filedialog.askopenfilenames(title='选择视频', filetypes=[('视频', ' '.join('*' + x for x in sorted(encode.EXTENSIONS))), ('所有文件', '*')])
        if paths:
            self.set_files(paths)

    def pick_folder(self):
        path = filedialog.askdirectory(title='选择批量文件夹')
        if path:
            self.folder.set(path)

    def pick_output(self):
        path = filedialog.askdirectory(title='选择输出目录')
        if path:
            self.output.set(path)

    def schedule_save(self, *_):
        if self.save_after:
            self.after_cancel(self.save_after)
        self.save_after = self.after(600, self.save)

    def save(self, notify=False):
        self.save_after = None
        try:
            cfg = copy.deepcopy(self.cfg)
            for key, editor in self.editors.items():
                cfg['profiles'][key]['params'] = parse_params(editor.get('1.0', 'end').strip(), key)
            cfg['ui'] = {'files': self.files, 'folder': self.folder.get().strip(),
                         'output': self.output.get().strip(), 'recursive': self.recursive.get(),
                         'encoders': [k for k, v in self.choices.items() if v.get()]}
            if cfg['ui']['encoders']:
                cfg['encoder'] = cfg['ui']['encoders'][0]
            encode.save_config(CONFIG, cfg)
            self.cfg = cfg
            self.saved.set('已保存')
            return True
        except (ValueError, OSError) as exc:
            self.saved.set('未保存：' + str(exc))
            if notify:
                messagebox.showerror('参数无法保存', str(exc))
            return False

    def apply_tool_settings(self, values):
        previous = copy.deepcopy(self.cfg)
        for key in ('tools_dir', 'ffmpeg', 'ffprobe', 'mp4box'):
            self.cfg[key] = values[key].strip()
        self.cfg['profiles']['x265']['path'] = values['x265'].strip()
        if not self.save(True):
            self.cfg = previous
            return False
        return True

    def tool_settings(self):
        if self.running:
            messagebox.showinfo('工具设置', '请在压制结束后修改工具设置。')
            return
        window = tk.Toplevel(self)
        window.title('工具设置')
        window.transient(self)
        window.grab_set()
        window.geometry('760x430')
        body = ttk.Frame(window, padding=15)
        body.pack(fill='both', expand=True)
        body.columnconfigure(1, weight=1)
        variables = {}
        fields = [('tools_dir', '工具目录'), ('ffmpeg', 'FFmpeg'), ('ffprobe', 'ffprobe'),
                  ('x265', f"x265 {self.cfg['bit_depth']}bit"), ('mp4box', 'MP4Box')]
        for row, (key, label) in enumerate(fields):
            initial = self.cfg['profiles']['x265'].get('path', '') if key == 'x265' else self.cfg.get(key, '')
            variable = tk.StringVar(value=initial)
            variables[key] = variable
            ttk.Label(body, text=label).grid(row=row, column=0, sticky='w', padx=(0, 10))
            ttk.Entry(body, textvariable=variable).grid(row=row, column=1, sticky='ew', pady=4)
            def browse(k=key, v=variable):
                path = filedialog.askdirectory(parent=window) if k == 'tools_dir' else filedialog.askopenfilename(parent=window)
                if path:
                    v.set(path)
            ttk.Button(body, text='选择…', command=browse).grid(row=row, column=2, padx=(8, 0))
        ttk.Label(body, text='留空自动查找', foreground='#666666').grid(row=5, column=1, sticky='w', pady=5)
        result = tk.Text(body, height=8, wrap='word', state='disabled')
        result.grid(row=6, column=0, columnspan=3, sticky='nsew', pady=8)
        body.rowconfigure(6, weight=1)
        actions = ttk.Frame(body)
        actions.grid(row=7, column=0, columnspan=3, sticky='ew')
        def draft():
            cfg = copy.deepcopy(self.cfg)
            for key in ('tools_dir', 'ffmpeg', 'ffprobe', 'mp4box'):
                cfg[key] = variables[key].get().strip()
            cfg['profiles']['x265']['path'] = variables['x265'].get().strip()
            return cfg
        def check():
            cfg = draft()
            encoders = [k for k, v in self.choices.items() if v.get()] or [cfg['encoder']]
            check_button.configure(state='disabled')
            result.configure(state='normal')
            result.delete('1.0', 'end')
            result.insert('1.0', '检查中…')
            result.configure(state='disabled')
            def work():
                try:
                    report = check_tools.format_report(check_tools.inspect_tools(cfg, encoders, cfg['bit_depth']))
                except Exception as exc:
                    report = str(exc)
                self.events.put({'type': 'tools', 'window': window, 'result': result,
                                 'button': check_button, 'text': report})
            threading.Thread(target=work, daemon=True).start()
        def save():
            if self.apply_tool_settings({k: v.get() for k, v in variables.items()}):
                window.destroy()
        check_button = ttk.Button(actions, text='检查工具', command=check)
        check_button.pack(side='left')
        ttk.Button(actions, text='保存', command=save).pack(side='right')
        ttk.Button(actions, text='取消', command=window.destroy).pack(side='right', padx=8)
        return window

    def start(self):
        if self.running or not self.save(True):
            return
        cfg = copy.deepcopy(self.cfg)
        ui = cfg['ui']
        try:
            if not ui['encoders']:
                raise ValueError('请至少勾选一个编码器。')
            values = self.files + ([ui['folder']] if ui['folder'] else [])
            if not values:
                raise ValueError('请选择视频文件或批量文件夹。')
            sources = encode.collect_inputs(values, ui['recursive'])
            outdir = Path(ui['output']).expanduser().resolve() if ui['output'] else None
            sources = [p for p in sources if not (outdir and p.is_relative_to(outdir))
                       and not any(x == 'encoded' or x.startswith('.encode-') for x in p.parts)]
            if not sources:
                raise ValueError('没有可压制的视频（会排除输出目录）。')
            jobs = [(s, (outdir or s.parent / 'encoded') / (s.stem + '_' + enc + '.' + cfg['container']), enc)
                    for s in sources for enc in ui['encoders']]
            names = [str(d).casefold() for _, d, _ in jobs]
            if len(set(names)) != len(names):
                raise ValueError('存在同名输出，请把这些视频分开压制或选不同输出目录。')
        except (ValueError, OSError) as exc:
            messagebox.showerror('无法开始', str(exc))
            return
        self.running = True
        self.cancel.clear()
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.percent.set(0)
        threading.Thread(target=self.worker, args=(sources, jobs, cfg), daemon=True).start()

    def worker(self, sources, jobs, cfg):
        ok = skipped = failed = larger = 0
        cancelled = False
        try:
            for source, destination, encoder in jobs:
                if self.cancel.is_set():
                    cancelled = True
                    break
                self.events.put({'type': 'job', 'text': f'{sources.index(source)+1}/{len(sources)} 个视频 · {encoder} · {source.name}'})
                args = encode.build_parser().parse_args([str(source), '--encoder', encoder])
                for key in ('bit_depth', 'audio', 'container'):
                    setattr(args, key, cfg[key])
                args.progress = self.events.put
                args.cancel = self.cancel
                try:
                    paths = encode.resolve_paths(cfg, args)
                    report = encode.encode_one(source, destination, args, cfg, paths)
                    skipped += report['status'] == 'skipped'
                    ok += report['status'] == 'ok'
                    larger += report.get('size_ratio', 0) >= 1
                except encode.EncodingCancelled:
                    cancelled = True
                    break
                except Exception as exc:
                    failed += 1
                    self.events.put({'type': 'error', 'text': f'{source.name} / {encoder}: {exc}'})
        except Exception as exc:
            failed += 1
            self.events.put({'type': 'error', 'text': str(exc)})
        finally:
            summary = f'{"已取消" if cancelled else "结束"}：完成 {ok} 份，跳过 {skipped} 份，失败 {failed} 份'
            if larger:
                summary += f'；{larger} 份比原片大，可提高 CRF 后重试'
            self.events.put({'type': 'done', 'text': summary})

    def pump(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event['type']
                if kind == 'job':
                    self.status.set(event['text'])
                    self.percent.set(0)
                    self.detail.set('准备音轨与视频…')
                elif kind == 'progress':
                    self.percent.set(event['value'])
                    self.detail.set(f"{event['value']:.1f}%")
                elif kind == 'stage':
                    self.detail.set(event['text'])
                elif kind == 'error':
                    messagebox.showerror('压制失败', event['text'] + '\n详细命令和错误请查看输出目录的 logs。')
                elif kind == 'tools':
                    if event['window'].winfo_exists():
                        output = event['result']
                        output.configure(state='normal')
                        output.delete('1.0', 'end')
                        output.insert('1.0', event['text'])
                        output.configure(state='disabled')
                        event['button'].configure(state='normal')
                elif kind == 'done':
                    self.running = False
                    self.start_button.configure(state='normal')
                    self.stop_button.configure(state='disabled')
                    self.status.set(event['text'])
        except queue.Empty:
            pass
        self.after(100, self.pump)

    def stop(self):
        self.cancel.set()
        self.detail.set('正在取消…')

    def close(self):
        if self.running:
            if messagebox.askyesno('正在压制', '取消压制并在子进程停止后关闭？'):
                self.stop()
                self.after(100, self.close_when_stopped)
            return
        if self.save(True):
            self.destroy()
        elif messagebox.askyesno('参数未保存', '参数有误或无法写入。仍然关闭？'):
            self.destroy()

    def close_when_stopped(self):
        if self.running:
            self.after(100, self.close_when_stopped)
        else:
            self.close()


if __name__ == '__main__':
    app = App()
    if len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:]]
        app.set_files([str(p) for p in paths if p.is_file()])
        folders = [p for p in paths if p.is_dir()]
        if folders:
            app.folder.set(str(folders[0]))
    app.mainloop()
