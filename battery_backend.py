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
    return Snapshot(percentage, read('status'), int(read(START)), int(read(END)), source, raw)
