import unittest
from unittest.mock import patch
import threshold_helper as helper
from battery_backend import read_snapshot, format_power
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


class MacsmcSysfs(FakeSysfs):
    """Coupled thresholds: start writes ignored; disabled limits read 100/100."""
    def __truediv__(self, name):
        owner = self
        class File:
            def read_text(self):
                return str(owner.values[name])
            def write_text(self, text):
                value = int(text)
                if (name, value) == owner.fail:
                    owner.fail = None
                    raise OSError('simulated write failure')
                owner.writes.append((name, value))
                if name == helper.END:
                    owner.values = {helper.END: value, helper.START: 100 if value == 100 else value - 5}
        return File()


class ThresholdTests(unittest.TestCase):
    def test_macsmc_full_charge_and_return(self):
        for target in [(95, 100), (100, 100)]:
            fs = MacsmcSysfs(55, 60)
            self.assertEqual(helper.apply_thresholds(*target, path=fs), (100, 100))
            self.assertEqual(helper.apply_thresholds(100, 100, path=fs), (100, 100))
            self.assertEqual(helper.apply_thresholds(75, 80, path=fs), (75, 80))
            self.assertEqual(helper.apply_thresholds(55, 60, path=fs), (55, 60))

    def test_macsmc_failure_preserves_full_charge(self):
        fs = MacsmcSysfs(100, 100, fail=(helper.END, 80))
        with self.assertRaises(RuntimeError):
            helper.apply_thresholds(75, 80, path=fs)
        self.assertEqual(helper.read_pair(fs), (100, 100))

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

    def test_power_readings(self):
        cases = [
            ({'power_now': '28999000'}, 28.999, '充电功率：29.0 W'),
            ({'power_now': '-7464000'}, -7.464, '放电功率：7.5 W'),
            ({'power_now': '0', 'voltage_now': '12000000', 'current_now': '2000000'}, 0, '电池功率：0.0 W'),
            ({'voltage_now': '12000000', 'current_now': '2000000'}, 24, '充电功率：24.0 W'),
            ({'power_now': 'bad', 'voltage_now': '12000000', 'current_now': '-500000'}, -6, '放电功率：6.0 W'),
            ({'voltage_now': '0', 'current_now': '2000000'}, None, '电池功率：不可用'),
            ({'voltage_now': '12000000'}, None, '电池功率：不可用'),
            ({'power_now': 'bad'}, None, '电池功率：不可用'),
            ({}, None, '电池功率：不可用'),
        ]
        for extra, expected, label in cases:
            with self.subTest(extra=extra), TemporaryDirectory() as folder:
                path = Path(folder)
                for name, value in {'capacity': '76', 'status': 'Unknown', helper.START: '75', helper.END: '80', **extra}.items():
                    (path/name).write_text(value)
                state = read_snapshot(path)
                self.assertEqual(state.power_watts, expected)
                self.assertEqual(format_power(state.power_watts), label)
                self.assertEqual(state.capacity, 76)

    def test_missing_interface(self):
        with TemporaryDirectory() as folder:
            with self.assertRaises((OSError, ValueError)):
                read_snapshot(Path(folder))


if __name__ == '__main__':
    unittest.main()
