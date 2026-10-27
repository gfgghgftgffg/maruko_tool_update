"""Native UI and persistence tests (requires a desktop session)."""
import json
from pathlib import Path
import tempfile
import threading
import sys
import unittest
from unittest.mock import patch

import encode
import gui


class SettingsTests(unittest.TestCase):
    def test_av1_crf_unchanged(self):
        params = encode.load_config(encode.ROOT / 'config.example.json')['profiles']['svt-av1']['params']
        self.assertEqual(params[params.index('-crf') + 1], '28')
        safe = encode.seekable_av1_params(params, '30')
        self.assertEqual(safe[safe.index('-crf') + 1], '28')
        self.assertIn('keyint=60', safe[-1])
        self.assertIn('irefresh-type=2', safe[-1])

    def test_open_gop_cannot_disable_seek(self):
        safe = encode.seekable_av1_params(['-crf', '28', '-svtav1-params',
            'tune=0:irefresh-type=1:keyint=60'], '30')
        self.assertIn('irefresh-type=2', safe[-1])
        self.assertNotIn('irefresh-type=1', safe[-1])

    def test_long_gop_is_not_silently_changed(self):
        with self.assertRaises(ValueError):
            encode.seekable_av1_params(['-svtav1-params', 'keyint=999'], '30')

    def test_params_quotes_roundtrip(self):
        original = encode.load_config(encode.ROOT / 'config.json')['profiles']['x265']['params']
        import shlex
        self.assertEqual(gui.parse_params(shlex.join(original), 'x265'), original)

    def test_cancellation_stops_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            cancel = threading.Event()
            cancel.set()
            runner = encode.Runner(Path(tmp) / 'cancel.log', cancel=cancel)
            with self.assertRaises(encode.EncodingCancelled):
                runner.run([sys.executable, '-c', 'import time; time.sleep(30)'])

    def test_gui_drag_save_reload(self):
        with tempfile.TemporaryDirectory(prefix='界面 test ') as tmp:
            root = Path(tmp)
            config = root / 'config.json'
            encode.save_config(config, encode.load_config(encode.ROOT / 'config.example.json'))
            video = root / '中文 & test.mp4'
            video.touch()
            with patch.object(gui, 'CONFIG', config):
                app = gui.App()
                try:
                    app.update()
                    self.assertIsNotNone(gui.DND_FILES)
                    def texts(widget):
                        found = []
                        if 'text' in widget.keys():
                            found.append(str(widget.cget('text')))
                        for child in widget.winfo_children():
                            found.extend(texts(child))
                        return found
                    labels = texts(app)
                    self.assertIn('x265 · 10bit', labels)
                    self.assertFalse(any('你的' in label for label in labels))
                    settings_window = app.tool_settings()
                    app.update()
                    self.assertEqual(settings_window.title(), '工具设置')
                    settings_window.destroy()
                    previous_params = list(app.cfg['profiles']['svt-av1']['params'])
                    values = {'tools_dir': 'custom tools', 'ffmpeg': 'custom tools/ffmpeg',
                              'ffprobe': 'custom tools/ffprobe', 'mp4box': 'custom tools/MP4Box',
                              'x265': 'custom tools/x265-10bit'}
                    self.assertTrue(app.apply_tool_settings(values))
                    self.assertEqual(app.cfg['profiles']['svt-av1']['params'], previous_params)
                    app.drop('files', app.tk.call('format', '%s', app.tk.call('list', str(video))))
                    app.folder.set(str(root))
                    app.output.set(str(root / 'outputs'))
                    app.choices['x265'].set(True)
                    app.choices['svt-av1'].set(True)
                    self.assertTrue(app.save())
                    app.attributes('-topmost', True)
                    app.lift()
                    app.update()
                    import time
                    time.sleep(0.5)
                    app.update()
                    try:
                        from PIL import ImageGrab
                    except ImportError:
                        pass  # Screenshot is optional; not needed for UI assertions.
                    else:
                        ImageGrab.grab().crop((app.winfo_rootx(), app.winfo_rooty(),
                            app.winfo_rootx() + app.winfo_width(), app.winfo_rooty() + app.winfo_height())).save(
                            encode.ROOT / 'build' / 'ui-preview.png')
                finally:
                    app.destroy()
                saved = json.loads(config.read_text(encoding='utf-8'))
                self.assertEqual(saved['ui']['files'], [str(video)])
                self.assertEqual(saved['ui']['encoders'], ['x265', 'svt-av1'])
                self.assertEqual(saved['ffmpeg'], values['ffmpeg'])
                self.assertEqual(saved['profiles']['x265']['path'], values['x265'])
                reloaded = gui.App()
                try:
                    self.assertEqual(reloaded.files, [str(video)])
                    self.assertEqual(reloaded.output.get(), str(root / 'outputs'))
                    self.assertTrue(reloaded.choices['x265'].get())
                finally:
                    reloaded.destroy()


if __name__ == '__main__':
    unittest.main(verbosity=2)
