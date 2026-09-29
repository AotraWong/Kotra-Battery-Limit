import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from PySide6.QtCore import QSettings
import i18n
import app as main_app
from app import BatteryWindow


class LanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        i18n.set_language('zh', persist=False)
        self.window = BatteryWindow(demo=True)

    def tearDown(self):
        self.window.timer.stop()
        self.window.tray.hide()
        self.window.deleteLater()
        self.app.processEvents()
        i18n.set_language('zh', persist=False)

    def test_live_switch_preserves_edits_and_chinese(self):
        original = [w.text() for w in self.window.findChildren(QLabel)]
        self.window.select_preset(55, 60)
        with patch('i18n.settings'):
            self.window.language_button.click()
        self.assertEqual(self.window.apply_button.text(), 'Apply')
        self.assertEqual((self.window.start.value(), self.window.end.value()), (55, 60))
        self.window.refresh()
        self.assertEqual((self.window.start.value(), self.window.end.value()), (55, 60))
        self.assertIn('Charging power', self.window.tray.toolTip())
        self.window.show_about()
        dialog = self.window.about_dialog
        self.assertIn('About & Diagnostics', dialog.windowTitle())
        self.assertNotRegex(dialog.diagnostics.toPlainText(), r'[\u4e00-\u9fff]')
        for widget in self.window.findChildren(QLabel):
            self.assertNotRegex(widget.text(), r'[\u4e00-\u9fff]')
        self.window.apply()
        self.assertIn('Demo settings applied', self.window.message.text())
        with patch('i18n.settings'):
            self.window.language_button.click()
        self.assertEqual(self.window.apply_button.text(), '应用')
        self.assertIn('关于与诊断', dialog.windowTitle())
        self.assertTrue(all(text in [w.text() for w in self.window.findChildren(QLabel)] for text in original if '选择预设' in text))
        dialog.close()

    def test_settings_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=QSettings(str(Path(tmp)/'settings.ini'), QSettings.Format.IniFormat)
            with patch('i18n.settings', return_value=config):
                i18n.set_language('en')
                i18n.set_language('zh', persist=False)
                i18n.load_language()
                self.assertEqual(i18n.LANGUAGE, 'en')

    def test_background_output_order(self):
        with tempfile.TemporaryDirectory() as tmp, patch('app.get_log_path', return_value=Path(tmp)/'log'), patch('app.subprocess.Popen') as popen:
            popen.return_value.pid=123
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(main_app.launch_background([]), 0)
            text=stream.getvalue()
            self.assertLess(text.index('Background process started'), text.index('已启动后台进程'))
            popen.side_effect=OSError('test')
            stream=io.StringIO()
            with contextlib.redirect_stderr(stream):
                self.assertEqual(main_app.launch_background([]), 1)
            self.assertLess(stream.getvalue().index('Cannot start'), stream.getvalue().index('无法后台启动'))
