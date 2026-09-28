#!/usr/bin/python3
"""Standalone privileged helper: fixed sysfs target, no shell or local imports."""
import json
import os
from pathlib import Path
import sys

BATTERY = Path('/sys/class/power_supply/macsmc-battery')
START = 'charge_control_start_threshold'
END = 'charge_control_end_threshold'


def validate(start, end):
    if not 0 <= start < end <= 100:
        raise ValueError('阈值必须满足 0 ≤ 开始 < 停止 ≤ 100。')


def read_pair(path):
    return tuple(int((path / name).read_text().strip()) for name in (START, END))


def write_pair(path, start, end):
    """Order writes so moving disjoint ranges never inverts the pair."""
    old_start, _ = read_pair(path)
    # When lowering below the old start, lower start first; otherwise end first.
    values = [(END, end), (START, start)] if end > old_start else [(START, start), (END, end)]
    for name, value in values:
        current = int((path / name).read_text().strip())
        if current != value:
            (path / name).write_text(f'{value}\n')


def apply_thresholds(start, end, path=BATTERY):
    validate(start, end)
    previous = read_pair(path)
    try:
        write_pair(path, start, end)
        actual = read_pair(path)
        validate(*actual)
        return actual
    except (OSError, ValueError) as exc:
        try:
            write_pair(path, *previous)
            restored = read_pair(path)
            recovery = f'已尝试恢复，当前阈值为 {restored[0]}% / {restored[1]}%。'
        except (OSError, ValueError) as restore_error:
            recovery = f'恢复失败：{restore_error}。请检查实际阈值。'
        raise RuntimeError(f'设置失败：{exc}。{recovery}') from exc


def main():
    try:
        if len(sys.argv) != 3:
            raise ValueError('用法：threshold_helper.py START END')
        start, end = map(int, sys.argv[1:])
        validate(start, end)
        if os.geteuid() != 0:
            raise PermissionError('请通过 pkexec 授权执行。')
        actual = apply_thresholds(start, end)
        print(json.dumps({'start': actual[0], 'end': actual[1]}))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
