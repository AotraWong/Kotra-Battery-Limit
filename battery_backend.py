"""Read-only battery access; writing is confined to the helper."""
from dataclasses import dataclass
from pathlib import Path

BATTERY = Path('/sys/class/power_supply/macsmc-battery')
START = 'charge_control_start_threshold'
END = 'charge_control_end_threshold'


@dataclass(frozen=True)
class Snapshot:
    capacity: float
    status: str
    start: int
    end: int
    source: str = '内核 capacity'
    raw_capacity: int | None = None
    power_watts: float | None = None
    power_source: str = '不可用'


def read_power(path):
    """macsmc signed battery power: positive into battery, negative out."""
    try:
        return int((path / 'power_now').read_text().strip()) / 1_000_000, 'power_now'
    except (OSError, ValueError):
        pass
    try:
        voltage = int((path / 'voltage_now').read_text().strip())
        current = int((path / 'current_now').read_text().strip())
        if voltage > 0:
            return voltage * current / 1_000_000_000_000, 'voltage_now × current_now（估算）'
    except (OSError, ValueError):
        pass
    return None, '不可用'


def format_power(watts):
    if watts is None:
        return '电池功率：不可用'
    if watts == 0:
        return '电池功率：0.0 W'
    return f'{"充电" if watts > 0 else "放电"}功率：{abs(watts):.1f} W'


def read_snapshot(path=BATTERY):
    def read(name):
        return (path / name).read_text().strip()
    # macsmc capacity can differ from the energy ratio exposed by UPower.
    # Prefer actual full capacity, never factory design capacity (battery health).
    raw = None
    try:
        raw = int(read('capacity'))
    except (OSError, ValueError):
        pass
    percentage = None
    source = '内核 capacity'
    for prefix, label in [('energy', '剩余能量 / 当前满充能量'),
                          ('charge', '剩余电荷 / 当前满充电荷')]:
        try:
            now, full = int(read(prefix + '_now')), int(read(prefix + '_full'))
            if now >= 0 and full > 0:
                percentage = min(100.0, now * 100.0 / full)
                source = label
                break
        except (OSError, ValueError):
            continue
    if percentage is None:
        if raw is None or not 0 <= raw <= 100:
            raise ValueError('没有可用的电量读数。')
        percentage = float(raw)
    power, power_source = read_power(path)
    return Snapshot(percentage, read('status'), int(read(START)), int(read(END)), source, raw, power, power_source)
