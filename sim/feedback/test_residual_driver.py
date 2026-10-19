"""Mock I2C/MMIO tests: no board connection and no audio emission."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


class ResidualDriverTests(unittest.TestCase):
    def execute(self, corrupt=False, restore_failure=False):
        events = []
        index = [0]
        address = [0]
        regs = {a: b"\x01" for a in (0x40F2, 0x40F3, 0x40F5, 0x40F6)}
        expected = []

        class FakeMMIO:
            def __init__(self, addr, size):
                self.addr = addr

            def write(self, offset, value):
                events.append(("mmio", self.addr, offset, value))
                if self.addr == 3 and offset == 0:
                    index[0] = value

            def read(self, offset):
                if self.addr == 3:
                    return ((512 << 1) | 1) if offset == 8 else index[0]
                if self.addr == 4:
                    return (256 << 4) | 0xB
                if self.addr == 2:
                    if index[0] & (1 << 16):
                        return 0 if offset == 0 else 1234
                    return ((int(expected[index[0]]) + int(corrupt)) & 0xFFFFFF) if offset == 0 else 1234
                return 0

        class FakeOverlay:
            def __init__(self, *args, **kwargs):
                events.append(("load",))
                self.ip_dict = {name: {"phys_addr": addr} for name, addr in
                                (("audio_control", 1), ("audio_samples", 2), ("audio_calibrate_cmd", 3), ("audio_coefficients", 4))}

        def restore(*args):
            events.append(("restore",))
            if restore_failure:
                raise RuntimeError("simulated overlay restore failure")

        def fake_write(fd, payload):
            address[0] = int.from_bytes(payload[:2], "big")
            if len(payload) > 2:
                value = payload[2:]
                if address[0] == 0x4002:
                    value = value[:-1] + bytes([value[-1] | 2])
                regs[address[0]] = value
            return len(payload)

        packages = {"pynq": types.ModuleType("pynq"),
                    "pynq.overlays": types.ModuleType("pynq.overlays"),
                    "pynq.overlays.base": types.ModuleType("pynq.overlays.base"),
                    "fcntl": types.ModuleType("fcntl")}
        tool_spec = importlib.util.spec_from_file_location("residual_tools", ROOT / "board/audio_residual/residual_tools.py")
        tool_module = importlib.util.module_from_spec(tool_spec)
        tool_spec.loader.exec_module(tool_module)
        packages["residual_tools"] = tool_module
        packages["pynq"].MMIO = FakeMMIO
        packages["pynq"].Overlay = FakeOverlay
        packages["pynq.overlays.base"].BaseOverlay = restore
        packages["fcntl"].ioctl = lambda *args: None
        temporary_root = ROOT / "tmp"
        temporary_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root, prefix="driver-test-") as d:
            work = Path(d)
            (work / "audio_residual.bit").write_bytes(b"mock-bit")
            (work / "audio_residual.hwh").write_bytes(b"mock-hwh")
            with patch.dict(sys.modules, packages):
                spec = importlib.util.spec_from_file_location("capture_under_test", ROOT / "board/audio_residual/open_loop_residual.py")
                driver = importlib.util.module_from_spec(spec)
                with contextlib.redirect_stdout(io.StringIO()):
                    spec.loader.exec_module(driver)
                self.assertEqual(events, [], "import must not touch hardware")
                driver.__file__ = str(work / "open_loop_residual.py")
                driver.FRAMES = 512
                model_path = work / "model.json"
                model_path.write_text(json.dumps(dict(taps=256, lag_first=1, coefficient_format="signed24_fraction20",
                    training_source="board",fixture_id="mock-fixture",hp_volume=40,sample_rate_hz=48828.125,
                    coefficients=[0.]*256,coefficients_q20=[0]*256,bias=0.)))
                expected.extend(driver.expected_reference(0, 4))
                with patch.object(driver.os, "open", return_value=100), \
                     patch.object(driver.os, "close"), \
                     patch.object(driver.os, "write", side_effect=fake_write), \
                     patch.object(driver.os, "read", side_effect=lambda fd, count: regs[address[0]][:count]), \
                     contextlib.redirect_stdout(io.StringIO()):
                    if corrupt or restore_failure:
                        with self.assertRaises(RuntimeError):
                            driver.open_loop_residual(work / "result.npz", "mock-fixture", model_path,
                                                     speaker_confirmed=True, local_capture_confirmed=True)
                        self.assertFalse((work / "result.npz").exists())
                    else:
                        driver.open_loop_residual(work / "result.npz", "mock-fixture", model_path,
                                                 speaker_confirmed=True, local_capture_confirmed=True)
                        with np.load(work / "result.npz", allow_pickle=False) as data:
                            np.testing.assert_array_equal(data["reference"] * 2**23, expected)
                            self.assertEqual(len(data["microphone"]), 512)
                            self.assertTrue(json.loads(str(data["metadata_json"]))["verification"]["bit_exact"])
                            np.testing.assert_array_equal(data["residual_pcm"], np.full(512,1234))
            self.assertIn(("restore",), events)
            self.assertEqual(regs[0x401C], b"\x00")
            self.assertEqual(regs[0x4023], b"\xe5")
            self.assertEqual(regs[0x4002].hex(), "0271023c2103")
            self.assertIn(("mmio", 1, 0, 0), events)

    def test_success_and_no_import_playback(self):
        self.execute()

    def test_corrupt_reference_restores_without_saving(self):
        self.execute(corrupt=True)

    def test_restore_failure_still_mutes_codec_and_restores_pll(self):
        self.execute(restore_failure=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
