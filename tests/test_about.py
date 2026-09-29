import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit
from app import BatteryWindow
from about_dialog import get_log_path, GITHUB_URL


class AboutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = BatteryWindow(demo=True)
        self.window.show_about()
        self.dialog = self.window.about_dialog

    def tearDown(self):
        self.window.timer.stop()
        self.window.tray.hide()
        self.dialog.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_diagnostics_and_reuse(self):
        text = self.dialog.diagnostics.toPlainText()
        self.assertIn('演示（不读取硬件）', text)
        self.assertIn('当前电量来源：演示数据', text)
        self.assertIn('power_now', text)
        self.window.show_about()
        self.assertIs(self.window.about_dialog, self.dialog)

    def test_log_actions(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp}), patch('about_dialog.QDesktopServices.openUrl', return_value=True) as open_url:
            self.dialog.open_log()
            open_url.assert_not_called()
            self.assertIn('尚未生成', self.dialog.feedback.text())
            path = get_log_path()
            path.parent.mkdir(parents=True)
            path.write_text('test')
            self.dialog.open_log()
            self.assertEqual(open_url.call_args.args[0].toLocalFile(), str(path))
            open_url.return_value = False
            self.dialog.open_log()
            self.assertIn('无法打开', self.dialog.feedback.text())
            self.dialog.open_url(QUrl(GITHUB_URL))
            self.assertEqual(open_url.call_args.args[0].toString(), GITHUB_URL)

    def test_license_view(self):
        self.dialog.show_license()
        viewers = self.dialog.findChildren(QDialog)
        self.assertTrue(viewers)
        self.assertIn('GNU GENERAL PUBLIC LICENSE', viewers[-1].findChild(QPlainTextEdit).toPlainText())
        viewers[-1].close()

    def test_read_failure(self):
        self.window.demo = False
        with patch('about_dialog.read_snapshot', side_effect=OSError('test unavailable')):
            self.dialog.refresh()
        self.assertIn('读取失败：test unavailable', self.dialog.diagnostics.toPlainText())
