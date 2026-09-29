"""Presentation-only translation; Chinese source text remains editable in widgets.

Each widget retains its original text so switching languages is lossless. A new
text assigned by the application replaces the stored source at the next refresh.
"""
import re
import weakref
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QPushButton, QPlainTextEdit, QWidget, QSystemTrayIcon

LANGUAGE = 'zh'
TRANSLATIONS = {
    '启动、阈值操作、授权结果和退出会立即写入日志；重复状态不刷屏。': 'Startup, threshold changes, authentication results and exit are logged immediately; repeated states are suppressed.',
    '日志尚未生成，请重启程序；若仍无日志，请检查日志目录权限。': 'No log yet. Restart the app; if it is still missing, check the log directory permissions.',
    '低于开始阈值时允许充电，高于停止阈值时停止。\n选择预设后点击“应用”。': 'Charging is allowed below the start threshold and stops above the end threshold.\nSelect a preset, then click Apply.',
    '正在充电': 'Charging', '使用电池': 'On battery', '未充电': 'Not charging', '未在充电': 'Not charging',
    '已充满': 'Full', '状态未知': 'Unknown',
    '正在读取电池…': 'Reading battery…', '电池功率：正在读取…': 'Battery power: reading…',
    '开始充电阈值': 'Start charging below', '停止充电阈值': 'Stop charging above',
    '低于开始阈值时允许充电，高于停止阈值时停止。\n出行选项设定 100 / 100 表示解除上限、允许充满。\n选择预设后点击“应用”。':
        'Charging is allowed below the start threshold and stops above the end threshold.\nTravel sets 100 / 100 to remove the limit and allow a full charge.\nSelect a preset, then click Apply.',
    '读取当前设置': 'Read current settings', '正在应用…': 'Applying…', '应用': 'Apply',
    '关于与诊断 · Kotra Battery Limit': 'About & Diagnostics · Kotra Battery Limit',
    '关于与诊断': 'About & Diagnostics', '正在读取…': 'Reading…', '打开主页面': 'Open main window', '退出': 'Quit',
    '请在系统授权窗口中确认此次更改…': 'Confirm this change in the system authentication dialog…',
    '日常 80%': 'Daily 80%', '长插电 60%': 'Plugged in 60%', '出行 100%': 'Travel 100%',
    '日常：75–80%': 'Daily: 75–80%', '长插电：55–60%': 'Plugged in: 55–60%', '出行：允许充满': 'Travel: full charge',
    '演示模式：不会修改系统。': 'Demo mode: no system changes.',
    '点击应用时，系统会请求管理员授权。': 'Applying changes requires administrator authentication.',
    '开始阈值必须小于停止阈值；100 / 100 表示允许充满。': 'Start must be below end; 100 / 100 allows a full charge.',
    '当前生效：允许充满（100%）': 'Active: full charge allowed (100%)',
    '演示设置已应用；系统未修改。': 'Demo settings applied; the system was not modified.',
    '未找到 pkexec，请安装 polkit 并启用桌面认证代理。': 'pkexec was not found. Install polkit and enable a desktop authentication agent.',
    '程序已在运行，请从系统托盘打开。': 'The app is already running. Open it from the system tray.',
    ' · 演示': ' · Demo',
    '电池端净功率，不是充电器总输出功率。\n来源：': 'Net battery power, not total charger output.\nSource: ',
    '无法读取电池或充电阈值': 'Cannot read battery or charging thresholds',
    '电池功率：不可用': 'Battery power: unavailable', '电池功率：0.0 W': 'Battery power: 0.0 W',
    '电池数据读取失败': 'Failed to read battery data', '当前阈值不可用': 'Current thresholds unavailable',
    '电池接口不可用': 'Battery interface unavailable',
    'Kotra Battery Limit：电池接口不可用': 'Kotra Battery Limit: battery interface unavailable',
    '无法启动系统授权：': 'Cannot start authentication: ',
    '请确认 Asahi 内核提供 macsmc-battery 的两个 threshold 文件。\n': 'Check that the Asahi kernel exposes both macsmc-battery threshold files.\n',
    '设置完成，内核接受：': 'Applied; kernel accepted: ',
    '助手返回结果无法解析，请核对当前生效阈值。': 'Cannot parse the helper response. Check the active thresholds.',
    '授权已取消或未获允许。': 'Authentication was cancelled or denied.',
    '应用失败：': 'Apply failed: ', '助手异常退出，请检查当前阈值。': 'The helper exited unexpectedly. Check the current thresholds.',
    '版本': 'Version', '作者': 'Author', '许可证': 'License',
    'GNU GPL v3（见项目 LICENSE）': 'GNU GPL v3 (see project LICENSE)',
    'PySide6 / Qt 为第三方依赖，适用其各自许可证。': 'PySide6 / Qt are third-party dependencies under their respective licenses.',
    '电量：energy_now / energy_full → charge_now / charge_full → capacity': 'Battery level: energy_now / energy_full → charge_now / charge_full → capacity',
    '功率：power_now（µW → W）；回退 voltage_now × current_now': 'Power: power_now (µW → W); fallback: voltage_now × current_now',
    '功率为电池端净功率，正值充电、负值放电，不是充电器总输出。': 'Net battery power: positive means charging, negative means discharging; not total charger output.',
    '状态：status': 'Status: status', '阈值：charge_control_start_threshold / charge_control_end_threshold': 'Thresholds: charge_control_start_threshold / charge_control_end_threshold',
    '主窗口每 5 秒刷新；本页打开时或点击“刷新诊断”更新。': 'The main window refreshes every 5 seconds. Reopen this page or click Refresh diagnostics to update it.',
    '许可证 · GNU GPL v3': 'License · GNU GPL v3', '关闭': 'Close', '刷新诊断': 'Refresh diagnostics',
    '查看许可证': 'View license', '打开日志': 'Open log',
    '后台启动时记录标准输出和错误；前台调试输出到终端。': 'Background mode logs stdout and stderr; foreground mode writes to the terminal.',
    '已请求系统默认应用打开。': 'Requested opening with the system default application.',
    '无法打开，请检查系统默认应用设置。': 'Cannot open. Check your default application settings.',
    '日志尚未生成。普通后台启动后会创建日志；前台调试输出到终端。\n': 'No log file yet. Background startup creates it; foreground output goes to the terminal.\n',
    '演示（不读取硬件）': 'Demo (no hardware access)', '真实电池': 'Live battery',
    '当前电量来源：': 'Current level source: ', '当前功率来源：': 'Current power source: ',
    '内核原始 capacity：': 'Raw kernel capacity: ', '当前电量：': 'Current level: ',
    '当前状态：': 'Current status: ', '当前阈值：': 'Current thresholds: ',
    '电量来源：': 'Level source: ', '当前生效：': 'Active: ',
    '运行模式：': 'Mode: ', '系统：': 'System: ', '电池接口：': 'Battery interface: ',
    '日志路径：': 'Log path: ', '读取失败：': 'Read failed: ', '无法读取许可证：': 'Cannot read license: ',
    '内核 capacity': 'Kernel capacity', '不可用': 'Unavailable', '演示数据': 'Demo data',
    '剩余能量 / 当前满充能量': 'Remaining energy / current full energy',
    '剩余电荷 / 当前满充电荷': 'Remaining charge / current full charge',
    'voltage_now × current_now（估算）': 'voltage_now × current_now (estimated)',
    '充电功率：': 'Charging power: ', '放电功率：': 'Discharging power: ',
    '没有可用的电量读数。': 'No valid battery level reading.',
}
_PATTERN = re.compile('|'.join(re.escape(k) for k in sorted(TRANSLATIONS, key=len, reverse=True)))
_sources = weakref.WeakKeyDictionary()


def english(text):
    return _PATTERN.sub(lambda match: TRANSLATIONS[match.group()], text)


def translate(text):
    return _PATTERN.sub(lambda match: TRANSLATIONS[match.group()], text) if LANGUAGE == 'en' else text


def settings():
    return QSettings('AotraWong', 'Kotra Battery Limit')


def load_language():
    global LANGUAGE
    LANGUAGE = 'en' if settings().value('language', 'zh') == 'en' else 'zh'


def set_language(language, persist=True):
    global LANGUAGE
    LANGUAGE = 'en' if language == 'en' else 'zh'
    if persist:
        settings().setValue('language', LANGUAGE)


def retranslate(root):
    """Translate owned widget text, retaining exact Chinese text across toggles."""
    objects = [root, *root.findChildren(QWidget), *root.findChildren(QAction),
               *root.findChildren(QSystemTrayIcon)]
    for obj in objects:
        properties = []
        if isinstance(obj, (QLabel, QPushButton, QAction)):
            properties.append(('text', 'setText'))
        if isinstance(obj, QPlainTextEdit):
            properties.append(('toPlainText', 'setPlainText'))
        if isinstance(obj, QWidget):
            properties.append(('windowTitle', 'setWindowTitle'))
        if isinstance(obj, (QWidget, QAction, QSystemTrayIcon)):
            properties.append(('toolTip', 'setToolTip'))
        saved = _sources.setdefault(obj, {})
        for getter, setter in properties:
            current = getattr(obj, getter)()
            source, rendered = saved.get(getter, (current, current))
            if current != rendered:
                source = current
            updated = translate(source)
            if LANGUAGE == 'en' and getter == 'text' and isinstance(obj, (QPushButton, QAction)):
                updated = updated.replace('&', '&&')
            if current != updated:
                getattr(obj, setter)(updated)
            saved[getter] = (source, updated)
