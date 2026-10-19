"""Paste this function into a dedicated Jupyter cell, then call probe_level(label).

No audio output or recording file. The result is a nonuniform PS sample of the
latest PL frame, useful for a rough quiet/speech comparison only.
"""

import fcntl
import math
import os
import time
from pathlib import Path

from pynq import MMIO, Overlay
from pynq.overlays.base import BaseOverlay


def probe_level(label, seconds=2.0):
    assert label in ("quiet", "speech")
    assert 0.5 <= seconds <= 5.0
    bit = Path.cwd() / "audio_probe" / "audio_probe.bit"
    assert bit.is_file() and bit.with_suffix(".hwh").is_file()

    def write_reg(fd, addr, data):
        payload = addr.to_bytes(2, "big") + bytes(data)
        assert os.write(fd, payload) == len(payload)

    def read_reg(fd, addr, count):
        assert os.write(fd, addr.to_bytes(2, "big")) == 2
        data = os.read(fd, count)
        assert len(data) == count
        return data

    def signed24(word):
        word &= 0xFFFFFF
        return word - 0x1000000 if word & 0x800000 else word

    fd = None
    try:
        fd = os.open("/dev/i2c-1", os.O_RDWR)
        fcntl.ioctl(fd, 0x0703, 0x3B)
        for addr, value in ((0x401C, 0), (0x401E, 0),
                            (0x4023, 0xE5), (0x4024, 0xE5)):
            write_reg(fd, addr, [value])
        Overlay(str(bit), download=True)
        control = MMIO(0x41200000, 0x1000)
        samples = MMIO(0x41210000, 0x1000)
        control.write(0, 0)
        control.write(4, 0)
        assert control.read(0) == 0
        write_reg(fd, 0x4000, [0x0E])
        write_reg(fd, 0x4002, bytes.fromhex("000000002801"))
        deadline = time.monotonic() + 2.0
        pll = read_reg(fd, 0x4002, 6)
        while not (pll[5] & 2) and time.monotonic() < deadline:
            time.sleep(0.01)
            pll = read_reg(fd, 0x4002, 6)
        assert pll[5] & 2, "PLL did not lock"
        write_reg(fd, 0x4000, [0x0F])
        for addr, value in ((0x400A, 1), (0x400B, 7),
                            (0x400C, 1), (0x400D, 7)):
            write_reg(fd, addr, [value])

        before = control.read(8)
        count = 0
        sums = [0, 0]
        squares = [0, 0]
        lows = [8388607, 8388607]
        highs = [-8388608, -8388608]
        start = time.monotonic()
        while time.monotonic() - start < seconds:
            values = (signed24(samples.read(0)), signed24(samples.read(8)))
            for ch, value in enumerate(values):
                sums[ch] += value
                squares[ch] += value * value
                lows[ch] = min(lows[ch], value)
                highs[ch] = max(highs[ch], value)
            count += 1
            time.sleep(0.0005)
        elapsed = time.monotonic() - start
        after = control.read(8)
        assert control.read(0) == 0 and after > before and count > 100
        rms = [math.sqrt(max(0, squares[ch] / count - (sums[ch] / count) ** 2))
               for ch in (0, 1)]
        result = {"label": label, "muted": True, "seconds": round(elapsed, 3),
                  "reads": count, "frames": after - before,
                  "rms_dbfs": [round(20 * math.log10(max(x, 1) / 8388608), 2)
                               for x in rms], "min": lows, "max": highs}
        print(result)
        return result
    finally:
        if fd is not None:
            os.close(fd)
        BaseOverlay("base.bit")
        print("STOCK_BASE_RESTORED")
        fd = os.open("/dev/i2c-1", os.O_RDWR)
        try:
            fcntl.ioctl(fd, 0x0703, 0x3B)
            restored = read_reg(fd, 0x4002, 6)
            if restored != bytes.fromhex("0271023c2103"):
                write_reg(fd, 0x4000, [0x0E])
                write_reg(fd, 0x4002, bytes.fromhex("0271023c2101"))
                deadline = time.monotonic() + 2.0
                restored = read_reg(fd, 0x4002, 6)
                while not (restored[5] & 2) and time.monotonic() < deadline:
                    time.sleep(0.01)
                    restored = read_reg(fd, 0x4002, 6)
                write_reg(fd, 0x4000, [0x0F])
            print("STOCK_PLL_READBACK", restored.hex())
            assert restored == bytes.fromhex("0271023c2103")
        finally:
            os.close(fd)
