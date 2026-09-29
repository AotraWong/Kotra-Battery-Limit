#!/usr/bin/env python3
"""Kotra Battery Limit — native Qt window and KDE system tray."""
from cli import BilingualParser
import json
import subprocess
from pathlib import Path
import shutil
import sys
from app_logging import logger, configure_logging, log_exception
from native_tray import MenuTrayIcon
import i18n

from PySide6.QtCore import QLockFile, QProcess, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QCursor, QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFormLayout, QHBoxLayout, QLabel, QMenu, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QSystemTrayIcon, QVBoxLayout, QWidget,
)
from battery_backend import Snapshot, read_snapshot, format_power
from about_dialog import AboutDialog, VERSION, get_log_path

ROOT = Path(__file__).resolve().parent
STATUS = {'Charging': '正在充电', 'Discharging': '使用电池', 'Not charging': '未在充电',
          'Full': '已充满', 'Unknown': '状态未知'}


def battery_icon(level=75):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#8996a8'), 4))
    painter.drawRoundedRect(5, 17, 49, 30, 5, 5)
    painter.fillRect(57, 26, 4, 12, QColor('#8996a8'))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor('#e89a47' if level < 20 else '#46b59a'))
    painter.drawRoundedRect(10, 22, max(2, int(39 * level / 100)), 20, 2, 2)
    painter.end()
    return QIcon(pixmap)


class BatteryWindow(QWidget):
    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.demo_snapshot = Snapshot(76, 'Charging', 75, 80, power_watts=18.5, power_source='演示数据')
        self.snapshot = None
        self.busy = False
        self.dirty = False
        self.initialized = False
        self.about_dialog = None
        self.last_logged_state = None
        self.last_logged_message = None
        self.setWindowTitle('Kotra Battery Limit' + (' · 演示' if demo else ''))
        self.setWindowIcon(battery_icon())
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        heading = QLabel('Kotra Battery Limit')
        heading.setStyleSheet('font-size: 23px; font-weight: 600;')
        layout.addWidget(heading)
        self.state_label = QLabel('正在读取电池…')
        layout.addWidget(self.state_label)
        self.power_label = QLabel('电池功率：正在读取…')
        layout.addWidget(self.power_label)
        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setMinimumHeight(24)
        layout.addWidget(self.meter)
        self.actual_label = QLabel()
        layout.addWidget(self.actual_label)
        form = QFormLayout()
        self.start = QSpinBox()
        self.end = QSpinBox()
        for spin in (self.start, self.end):
            spin.setRange(0, 100)
            spin.setSuffix(' %')
            spin.valueChanged.connect(self.edited)
        self.start.setValue(75)
        self.end.setValue(80)
        form.addRow('开始充电阈值', self.start)
        form.addRow('停止充电阈值', self.end)
        layout.addLayout(form)
        presets = QHBoxLayout()
        self.preset_buttons = []
        for label, start, end in [('日常 80%', 75, 80), ('长插电 60%', 55, 60), ('出行 100%', 100, 100)]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, s=start, e=end: self.select_preset(s, e))
            presets.addWidget(button)
            self.preset_buttons.append(button)
        controls = QVBoxLayout()
        controls.setSpacing(8)
        layout.addLayout(controls)
        controls.addLayout(presets)
        tip = QLabel('低于开始阈值时允许充电，高于停止阈值时停止。\n选择预设后点击“应用”。')
        tip.setWordWrap(True)
        controls.addWidget(tip)
        self.message = QLabel('演示模式：不会修改系统。' if demo else '点击应用时，系统会请求管理员授权。')
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        controls.addWidget(self.message)
        actions = QHBoxLayout()
        self.reload_button = QPushButton('读取当前设置')
        self.reload_button.clicked.connect(self.reload)
        actions.addWidget(self.reload_button)
        self.apply_button = QPushButton('应用')
        self.apply_button.clicked.connect(self.apply)
        actions.addWidget(self.apply_button)
        controls.addLayout(actions)
        about_button = QPushButton("关于与诊断")
        about_button.clicked.connect(self.show_about)
        footer = QHBoxLayout()
        footer.addWidget(about_button)
        self.language_button = QPushButton('English / 中文')
        self.language_button.clicked.connect(self.toggle_language)
        footer.addWidget(self.language_button)
        layout.addLayout(footer)
        self.tray = MenuTrayIcon(battery_icon(), self)
        menu = QMenu(self)
        self.tray_status = menu.addAction('正在读取…')
        self.tray_status.setEnabled(False)
        menu.addSeparator()
        menu.addAction('打开主页面', self.show_window)
        for label, start, end in [('日常：75–80%', 75, 80), ('长插电：55–60%', 55, 60), ('出行：允许充满', 100, 100)]:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, s=start, e=end: self.tray_preset(s, e))
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction('关于与诊断', self.show_about)
        menu.addAction('退出', self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.activated)
        self.tray.show()
        self.process = QProcess(self)
        self.process.finished.connect(self.applied)
        self.process.errorOccurred.connect(self.process_error)
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)

    def set_message(self, text):
        if text != self.last_logged_message:
            logger.info("%s / %s", i18n.english(text), text)
            self.last_logged_message = text
        self.message.setText(text)
        i18n.retranslate(self)

    def toggle_language(self):
        i18n.set_language('en' if i18n.LANGUAGE == 'zh' else 'zh')
        i18n.retranslate(self)

    def show_about(self):
        if self.about_dialog is None:
            self.about_dialog = AboutDialog(self)
        self.about_dialog.refresh()
        self.about_dialog.showNormal()
        self.about_dialog.raise_()
        self.about_dialog.activateWindow()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def activated(self, reason):
        # Right-click is handled by Qt; left-click opens the same menu.
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            menu = self.tray.contextMenu()
            if menu is not None:
                menu.popup(QCursor.pos())

    def select_preset(self, start, end):
        if not self.busy:
            self.start.setValue(start)
            self.end.setValue(end)

    def tray_preset(self, start, end):
        self.show_window()
        self.select_preset(start, end)

    def edited(self):
        self.dirty = True
        if hasattr(self, 'apply_button'):
            self.update_controls()

    def update_controls(self):
        valid = self.start.value() < self.end.value() or self.start.value() == self.end.value() == 100
        self.apply_button.setEnabled(not self.busy and self.snapshot is not None and valid)
        self.apply_button.setText('正在应用…' if self.busy else '应用')
        for widget in [self.start, self.end, self.reload_button, *self.preset_buttons]:
            widget.setEnabled(not self.busy)
        self.apply_button.setToolTip('开始阈值必须小于停止阈值；100 / 100 表示允许充满。' if not valid else '')
        i18n.retranslate(self)

    def refresh(self):
        if self.busy:
            return
        try:
            snapshot = self.demo_snapshot if self.demo else read_snapshot()
            self.snapshot = snapshot
            state = (snapshot.status, snapshot.start, snapshot.end)
            if state != self.last_logged_state:
                logger.info('Battery state / 电池状态: status=%s, level=%.1f%%, power=%s W, thresholds=%s/%s, demo=%s', snapshot.status, snapshot.capacity, snapshot.power_watts, snapshot.start, snapshot.end, self.demo)
                self.last_logged_state = state
                self.last_logged_message = None
            text = f'{snapshot.capacity:.1f}% · {STATUS.get(snapshot.status, snapshot.status)}'
            self.state_label.setText(text)
            power_text = format_power(snapshot.power_watts)
            self.power_label.setText(power_text)
            self.power_label.setToolTip(f'电池端净功率，不是充电器总输出功率。\n来源：{snapshot.power_source}')
            self.meter.setValue(round(snapshot.capacity))
            self.meter.setFormat(f'{snapshot.capacity:.1f}%')
            detail = f'电量来源：{snapshot.source}'
            if snapshot.raw_capacity is not None:
                detail += f'\n内核原始 capacity：{snapshot.raw_capacity}%'
            self.state_label.setToolTip(detail)
            self.meter.setToolTip(detail)
            actual = ('当前生效：允许充满（100%）' if snapshot.start == snapshot.end == 100
                      else f'当前生效：{snapshot.start}% → {snapshot.end}%')
            self.actual_label.setText(actual)
            self.tray_status.setText(text + ' | ' + power_text + ' | ' + actual)
            self.tray.setToolTip('Kotra Battery Limit\n' + text + '\n' + power_text + '\n' + actual + '\n' + detail)
            self.tray.setIcon(battery_icon(snapshot.capacity))
            if not self.initialized or not self.dirty:
                for spin, value in [(self.start, snapshot.start), (self.end, snapshot.end)]:
                    spin.blockSignals(True)
                    spin.setValue(value)
                    spin.blockSignals(False)
                self.dirty = False
                self.initialized = True
        except (OSError, ValueError) as exc:
            self.snapshot = None
            self.last_logged_state = None
            self.state_label.setText('无法读取电池或充电阈值')
            self.power_label.setText('电池功率：不可用')
            self.power_label.setToolTip('电池数据读取失败')
            self.actual_label.setText('当前阈值不可用')
            self.tray_status.setText('电池接口不可用')
            self.tray.setToolTip('Kotra Battery Limit：电池接口不可用')
            self.set_message(f'请确认 Asahi 内核提供 macsmc-battery 的两个 threshold 文件。\n{exc}')
        self.update_controls()

    def reload(self):
        self.dirty = False
        self.refresh()

    def apply(self):
        if self.busy or self.snapshot is None or not (self.start.value() < self.end.value() or self.start.value() == self.end.value() == 100):
            return
        logger.info('Apply requested / 请求应用阈值: %s/%s, demo=%s', self.start.value(), self.end.value(), self.demo)
        if self.demo:
            self.demo_snapshot = Snapshot(76, 'Charging', self.start.value(), self.end.value(), power_watts=18.5, power_source='演示数据')
            self.dirty = False
            self.refresh()
            self.set_message('演示设置已应用；系统未修改。')
            return
        pkexec = shutil.which('pkexec')
        if not pkexec:
            self.set_message('未找到 pkexec，请安装 polkit 并启用桌面认证代理。')
            return
        self.busy = True
        self.update_controls()
        self.set_message('请在系统授权窗口中确认此次更改…')
        # Isolated Python ignores PYTHONPATH, user site packages and local imports.
        self.process.start(pkexec, ['/usr/bin/python3', '-I', str(ROOT / 'threshold_helper.py'),
                                    str(self.start.value()), str(self.end.value())])

    def process_error(self, error):
        logger.error('Authentication process error / 授权进程错误: %s; %s', error, self.process.errorString())
        if error == QProcess.ProcessError.FailedToStart:
            self.busy = False
            self.set_message('无法启动系统授权：' + self.process.errorString())
            self.refresh()

    def applied(self, exit_code, exit_status):
        self.busy = False
        output = bytes(self.process.readAllStandardOutput()).decode(errors='replace')
        errors = bytes(self.process.readAllStandardError()).decode(errors='replace').strip()
        logger.log(20 if exit_code == 0 else 30, 'Helper finished / 助手结束: exit=%s, status=%s, stdout=%s, stderr=%s', exit_code, exit_status, output.strip(), errors)
        if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            try:
                result = json.loads(output)
                self.set_message(f'设置完成，内核接受：{result["start"]}% / {result["end"]}%。')
                self.dirty = False
            except (ValueError, KeyError, TypeError):
                self.set_message('助手返回结果无法解析，请核对当前生效阈值。')
        elif exit_code in (126, 127):
            self.set_message('授权已取消或未获允许。' + ('\n' + errors if errors else ''))
        else:
            self.set_message('应用失败：' + (errors or '助手异常退出，请检查当前阈值。'))
        self.refresh()

    def quit_app(self):
        if self.busy:
            self.show_window()
            return
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self.busy or QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
        else:
            event.accept()
            QApplication.instance().quit()


def launch_background(arguments):
    """Detach before constructing QApplication and redirect diagnostics."""
    log_path = get_log_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('ab') as log:
            child = subprocess.Popen(
                [sys.executable, str(ROOT / 'app.py'), '--foreground', *arguments],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, close_fds=True,
            )
    except OSError as exc:
        print(f'Cannot start in background: {exc}. Use --foreground for diagnostics.\n无法后台启动：{exc}。可使用 --foreground 查看错误。', file=sys.stderr)
        return 1
    print(f'Background process started (PID {child.pid}). You can keep using this terminal. Log: {log_path}\n已启动后台进程（PID {child.pid}），可继续使用终端。日志：{log_path}')
    return 0


def main():
    parser = BilingualParser(description='Kotra Battery Limit', add_help=False)
    parser.add_argument('-h', '--help', action='help', help='Show help and exit / 显示帮助并退出')
    parser.add_argument('--tray', action='store_true', help='Start in the system tray / 启动到系统托盘')
    parser.add_argument('--demo', action='store_true', help='Demo UI without hardware access / 演示界面，不读写硬件')
    parser.add_argument('--smoke-test', action='store_true', help='Create the UI and exit without writing hardware / 创建界面后自动退出，不写硬件')
    parser.add_argument('--foreground', action='store_true', help='Run in the foreground for debugging / 在前台运行，便于调试')
    args = parser.parse_args()
    if not args.foreground and not args.smoke_test:
        return launch_background(sys.argv[1:])
    configure_logging(get_log_path())
    sys.excepthook = log_exception
    logger.info('Starting Kotra Battery Limit / 启动 Kotra Battery Limit: version=%s, demo=%s, tray=%s', VERSION, args.demo, args.tray)
    app = QApplication([sys.argv[0]])
    app.aboutToQuit.connect(lambda: logger.info('Application exiting / 程序退出'))
    app.setApplicationName('asahi-battery-limit')
    app.setApplicationDisplayName('Kotra Battery Limit')
    app.setApplicationVersion(VERSION)
    app.setQuitOnLastWindowClosed(False)
    i18n.load_language()
    lock = None
    if not args.demo and not args.smoke_test:
        runtime = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
        lock = QLockFile(str(Path(runtime) / 'asahi-battery-limit.lock'))
        if not lock.tryLock(100):
            logger.info('Already running / 程序已在运行')
            QMessageBox.information(None, 'Kotra Battery Limit', i18n.translate('程序已在运行，请从系统托盘打开。'))
            return 0
    window = BatteryWindow(demo=args.demo)
    if not args.tray or not QSystemTrayIcon.isSystemTrayAvailable():
        window.show()
    if args.smoke_test:
        QTimer.singleShot(200, app.quit)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
