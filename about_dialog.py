"""About information and read-only diagnostics for Kotra Battery Limit."""
import os
import i18n
from pathlib import Path
import platform

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import Qt, QUrl, qVersion
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)
from battery_backend import BATTERY, format_power, read_snapshot

VERSION = 'Beta 1'
AUTHOR = 'AotraWong'
GITHUB_URL = 'https://github.com/aotrawong/kotra-battery-limit'
ROOT = Path(__file__).resolve().parent


def get_log_path():
    state_home = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
    return state_home / 'kotra-battery-limit' / 'app.log'


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('关于与诊断 · Kotra Battery Limit')
        self.resize(600, 600)
        layout = QVBoxLayout(self)
        title = QLabel('Kotra Battery Limit')
        title.setStyleSheet('font-size: 22px; font-weight: 600;')
        layout.addWidget(title)
        form = QFormLayout()
        form.addRow('版本', QLabel(VERSION))
        form.addRow('作者', QLabel(AUTHOR))
        form.addRow('许可证', QLabel('GNU GPL v3（见项目 LICENSE）'))
        github = QLabel(f'<a href="{GITHUB_URL}">{GITHUB_URL}</a>')
        github.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        github.linkActivated.connect(lambda _: self.open_url(QUrl(GITHUB_URL)))
        form.addRow('GitHub', github)
        layout.addLayout(form)
        notice = QLabel('PySide6 / Qt 为第三方依赖，适用其各自许可证。')
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        layout.addWidget(self.diagnostics)
        self.feedback = QLabel()
        self.feedback.setTextFormat(Qt.TextFormat.PlainText)
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        buttons = QHBoxLayout()
        for label, callback in [('刷新诊断', self.refresh), ('查看许可证', self.show_license),
                                ('打开日志', self.open_log), ('关闭', self.close)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        parent = self.parent()
        demo = bool(getattr(parent, 'demo', False))
        lines = [f'运行模式：{"演示（不读取硬件）" if demo else "真实电池"}',
                 f'Python：{platform.python_version()}  |  PySide6：{pyside_version}  |  Qt：{qVersion()}',
                 f'系统：{platform.system()} {platform.release()} ({platform.machine()})',
                 '', f'电池接口：{BATTERY}',
                 '电量：energy_now / energy_full → charge_now / charge_full → capacity',
                 '功率：power_now（µW → W）；回退 voltage_now × current_now',
                 '功率为电池端净功率，正值充电、负值放电，不是充电器总输出。',
                 '状态：status',
                 '阈值：charge_control_start_threshold / charge_control_end_threshold',
                 '主窗口每 5 秒刷新；本页打开时或点击“刷新诊断”更新。', '']
        try:
            snapshot = parent.demo_snapshot if demo else read_snapshot()
            lines.extend([f'当前电量：{snapshot.capacity:.1f}%',
                          f'当前电量来源：{"演示数据" if demo else snapshot.source}',
                          f'内核原始 capacity：{snapshot.raw_capacity if snapshot.raw_capacity is not None else "不可用"}',
                          f'当前状态：{snapshot.status}', format_power(snapshot.power_watts),
                          f'当前功率来源：{snapshot.power_source}',
                          f'当前阈值：{snapshot.start}% → {snapshot.end}%'])
        except (OSError, ValueError) as exc:
            lines.append(f'读取失败：{exc}')
        lines.extend(['', f'日志路径：{get_log_path()}',
                      '启动、阈值操作、授权结果和退出会立即写入日志；重复状态不刷屏。'])
        self.diagnostics.setPlainText('\n'.join(lines))
        i18n.retranslate(self)

    def set_feedback(self, text):
        self.feedback.setText(text)
        i18n.retranslate(self)

    def open_url(self, url):
        if QDesktopServices.openUrl(url):
            self.set_feedback('已请求系统默认应用打开。')
        else:
            self.set_feedback('无法打开，请检查系统默认应用设置。')

    def open_log(self):
        path = get_log_path()
        if not path.is_file():
            self.set_feedback(f'日志尚未生成，请重启程序；若仍无日志，请检查日志目录权限。\n{path}')
            return
        self.open_url(QUrl.fromLocalFile(str(path.resolve())))

    def show_license(self):
        try:
            text = (ROOT / 'LICENSE').read_text()
        except OSError as exc:
            self.set_feedback(f'无法读取许可证：{exc}')
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('许可证 · GNU GPL v3')
        dialog.resize(680, 520)
        layout = QVBoxLayout(dialog)
        viewer = QPlainTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(text)
        layout.addWidget(viewer)
        close = QPushButton('关闭')
        close.clicked.connect(dialog.close)
        layout.addWidget(close)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        i18n.retranslate(dialog)
        dialog.show()
