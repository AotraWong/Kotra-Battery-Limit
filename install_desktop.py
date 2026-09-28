#!/usr/bin/env python3
"""Optional per-user application menu and login launcher registration."""
import argparse
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--autostart', action='store_true', help='同时启用登录后运行')
parser.add_argument('--uninstall', action='store_true', help='删除菜单和自启动入口，保留源代码')
args = parser.parse_args()
root = Path(__file__).resolve().parent
apps = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'applications'
auto = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'autostart'
name = 'asahi-battery-limit.desktop'
if args.uninstall:
    for directory in (apps, auto):
        (directory/name).unlink(missing_ok=True)
else:
    # Desktop Exec quoting is not shell quoting. Escape reserved characters and %.
    def quote(value):
        value = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
        return '"' + value + '"'
    command = '/usr/bin/python3 ' + quote(root/'app.py')
    def install(directory, tray=False):
        directory.mkdir(parents=True, exist_ok=True)
        text = '[Desktop Entry]\nType=Application\nName=Kotra Battery Limit\nComment=Asahi 电池充电阈值\nIcon=battery\nTerminal=false\nCategories=Settings;HardwareSettings;\nExec=' + command + (' --tray' if tray else '') + '\n'
        (directory/name).write_text(text)
        print(directory/name)
    install(apps)
    if args.autostart:
        install(auto, tray=True)
