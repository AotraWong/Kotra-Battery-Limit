import unittest
from unittest.mock import patch
import threshold_helper as helper
from battery_backend import read_snapshot
from tempfile import TemporaryDirectory
from pathlib import Path


class FakeSysfs:
    """Reject inverted intermediate pairs, like a strict battery driver."""
    def __init__(self, start=75, end=80, fail=None, rounding=False):
        self.values = {helper.START: start, helper.END: end}
        self.writes = []
        self.fail = fail
        self.rounding = rounding

    def __truediv__(self, name):
        owner = self
        class File:
            def read_text(self):
                return str(owner.values[name])
            def write_text(self, text):
                value = int(text)
                if (name, value) == owner.fail:
                    owner.fail = None
                    raise OSError('simulated driver failure')
                values = dict(owner.values)
                values[name] = value // 5 * 5 if owner.rounding else value
                if values[helper.START] >= values[helper.END]:
                    raise OSError('inverted pair')
                owner.values = values
                owner.writes.append((name, value))
        return File()


class ThresholdTests(unittest.TestCase):
    def test_transitions(self):
        for old, new in [((75,80),(55,60)), ((55,60),(95,100)), ((75,80),(70,85)), ((75,80),(75,80)), ((75,80),(0,1))]:
            with self.subTest(old=old, new=new):
                fs = FakeSysfs(*old)
                self.assertEqual(helper.apply_thresholds(*new, path=fs), new)

    def test_invalid_input_never_writes(self):
        for pair in [(-1,80), (80,80), (90,80), (75,101)]:
            fs = FakeSysfs()
            with self.assertRaises(ValueError):
                helper.apply_thresholds(*pair, path=fs)
            self.assertEqual(fs.writes, [])

    def test_partial_failure_restores_previous_pair(self):
        fs = FakeSysfs(fail=(helper.END,60))
        with self.assertRaisesRegex(RuntimeError, '已尝试恢复'):
            helper.apply_thresholds(55,60,path=fs)
        self.assertEqual(helper.read_pair(fs), (75,80))

    def test_returns_driver_rounded_values(self):
        fs = FakeSysfs(rounding=True)
        self.assertEqual(helper.apply_thresholds(73,88,path=fs), (70,85))

    def test_read_realistic_fixture(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)
            for name,value in {'capacity':'76', 'status':'Not charging', helper.START:'75', helper.END:'80'}.items():
                (path/name).write_text(value+'\n')
            state = read_snapshot(path)
            self.assertEqual((state.capacity,state.start,state.end),(76,75,80))

    def test_percentage_sources(self):
        cases = [
            ({'energy_now': '31646400', 'energy_full': '41325000'}, 76.5793, '剩余能量'),
            ({'energy_now': '10', 'energy_full': '0', 'charge_now': '2700', 'charge_full': '3600'}, 75, '剩余电荷'),
            ({'energy_now': 'bad', 'energy_full': '100'}, 81, '内核'),
            ({'energy_now': '-1', 'energy_full': '100'}, 81, '内核'),
            ({'energy_now': '110', 'energy_full': '100'}, 100, '剩余能量'),
        ]
        for extra, expected, source in cases:
            with self.subTest(extra=extra), TemporaryDirectory() as folder:
                path = Path(folder)
                fields = {'capacity': '81', 'status': 'Discharging', helper.START: '55', helper.END: '60', **extra}
                for name, value in fields.items():
                    (path/name).write_text(value)
                state = read_snapshot(path)
                self.assertAlmostEqual(state.capacity, expected, places=4)
                self.assertTrue(state.source.startswith(source))
                self.assertEqual(state.raw_capacity, 81)

    def test_energy_without_raw_capacity(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)
            for name, value in {'energy_now': '3', 'energy_full': '4', 'status': 'Discharging', helper.START: '55', helper.END: '60'}.items():
                (path/name).write_text(value)
            self.assertEqual(read_snapshot(path).capacity, 75)

    def test_missing_interface(self):
        with TemporaryDirectory() as folder:
            with self.assertRaises((OSError, ValueError)):
                read_snapshot(Path(folder))


if __name__ == '__main__':
    unittest.main()
