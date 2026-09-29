import tempfile
import unittest
from pathlib import Path
from app_logging import configure_logging, logger
from app import BatteryWindow
from PySide6.QtWidgets import QApplication
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


class LoggingTests(unittest.TestCase):
    def test_events_flush_and_repeated_state_is_suppressed(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'app.log'
            configure_logging(path)
            window=BatteryWindow(demo=True)
            try:
                first=path.read_text()
                self.assertIn('Battery state / 电池状态', first)
                window.refresh()
                self.assertEqual(first, path.read_text())
                window.select_preset(100,100)
                window.apply()
                text=path.read_text()
                self.assertIn('Apply requested / 请求应用阈值: 100/100', text)
                self.assertIn('Demo settings applied', text)
                window.set_message('授权已取消或未获允许。')
                self.assertIn('Authentication was cancelled or denied.', path.read_text())
            finally:
                window.timer.stop()
                window.tray.hide()
                window.deleteLater()
                for handler in list(logger.handlers):
                    handler.close()
                    logger.removeHandler(handler)
