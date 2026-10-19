"""Paste into a dedicated PYNQ notebook cell for supervised, bounded playback.

Requires an on-site operator with the powered speaker at low volume and a
physical power cutoff. This is direct pass-through, NOT feedback suppression.
"""

import fcntl
import os
import time
from pathlib import Path

from pynq import MMIO, Overlay
from pynq.overlays.base import BaseOverlay


def bounded_passthrough(seconds=2.0, shift=6, hp_volume=30):
    assert 0.25 <= seconds <= 2.0
    assert 4 <= shift <= 7
    assert 10 <= hp_volume <= 57
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

    fd = None
    control = None
    start = None
    try:
        fd = os.open("/dev/i2c-1", os.O_RDWR)
        fcntl.ioctl(fd, 0x0703, 0x3B)
        # Keep both codec and PL outputs muted during overlay/PLL transitions.
        for addr, value in ((0x401C, 0), (0x401E, 0),
                            (0x4023, 0xE5), (0x4024, 0xE5)):
            write_reg(fd, addr, [value])
        Overlay(str(bit), download=True)
        control = MMIO(0x41200000, 0x1000)
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
        assert read_reg(fd, 0x40F2, 1) == b"\x01"
        assert read_reg(fd, 0x40F3, 1) == b"\x01"

        # ADAU1761 R29/R30: hp_volume 57 = 0 dB, one dB per step.
        # The previous volume 10 plus PL shift 6 attenuated ~83 dB in total.
        hp_register = (hp_volume << 2) | 3
        for addr, value in ((0x401C, 0x21), (0x401E, 0x41),
                            (0x4023, hp_register), (0x4024, hp_register)):
            write_reg(fd, addr, [value])
        before = control.read(8)
        start = time.monotonic()
        enable = 1 | (shift << 1)
        print({"hp_volume": hp_volume, "hp_db": hp_volume - 57,
               "pl_shift": shift, "pl_db_approx": round(-6.0206 * shift, 2)})
        control.write(0, enable)
        assert control.read(0) == enable
        time.sleep(seconds)
        control.write(0, 0)
        after = control.read(8)
        print({"planned_seconds": seconds,
               "elapsed_seconds": round(time.monotonic() - start, 3),
               "frames": after - before, "muted_at_end": control.read(0) == 0})
    finally:
        try:
            if control is not None:
                control.write(0, 0)
                print("PL_CONTROL_MUTED", control.read(0) == 0)
        finally:
            if fd is not None:
                try:
                    for addr, value in ((0x401C, 0), (0x401E, 0),
                                        (0x4023, 0xE5), (0x4024, 0xE5)):
                        write_reg(fd, addr, [value])
                finally:
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
