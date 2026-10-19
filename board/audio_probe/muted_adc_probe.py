"""Read bounded ADC snapshot statistics with the custom PL output hard muted.

Run on PYNQ-Z2 with audio_probe.bit and audio_probe.hwh beside this script.
No audio is played or saved. This does not demonstrate acoustic feedback suppression.
"""

import fcntl
import os
import time
from pathlib import Path

from pynq import MMIO, Overlay
from pynq.overlays.base import BaseOverlay


BIT = Path(__file__).resolve().with_name("audio_probe.bit")
assert BIT.is_file() and BIT.with_suffix(".hwh").is_file()
I2C_SLAVE = 0x0703
CODEC_ADDR = 0x3B
PLL_50MHZ = bytes.fromhex("000000002801")
PLL_STOCK_48K = bytes.fromhex("0271023c2103")
PLL_STOCK_WRITE = bytes.fromhex("0271023c2101")


def write_codec(fd, address, data):
    payload = address.to_bytes(2, "big") + bytes(data)
    assert os.write(fd, payload) == len(payload)


def read_codec(fd, address, count):
    assert os.write(fd, address.to_bytes(2, "big")) == 2
    data = os.read(fd, count)
    assert len(data) == count
    return data


def signed24(value):
    value &= 0xFFFFFF
    return value - 0x1000000 if value & 0x800000 else value


fd = None
try:
    fd = os.open("/dev/i2c-1", os.O_RDWR)
    fcntl.ioctl(fd, I2C_SLAVE, CODEC_ADDR)
    for address, value in ((0x401C, 0), (0x401E, 0), (0x4023, 0xE5), (0x4024, 0xE5)):
        write_codec(fd, address, [value])

    Overlay(str(BIT), download=True)
    control = MMIO(0x41200000, 0x1000)
    samples = MMIO(0x41210000, 0x1000)
    control.write(0x0, 0)
    control.write(0x4, 0)
    assert control.read(0x0) == 0

    write_codec(fd, 0x4000, [0x0E])
    write_codec(fd, 0x4002, PLL_50MHZ)
    deadline = time.monotonic() + 2.0
    pll = read_codec(fd, 0x4002, 6)
    while not (pll[5] & 0x02) and time.monotonic() < deadline:
        time.sleep(0.01)
        pll = read_codec(fd, 0x4002, 6)
    assert pll[5] & 0x02, "ADAU1761 PLL did not lock within 2 seconds"
    write_codec(fd, 0x4000, [0x0F])

    # Line-in routing matches the stock PYNQ AudioADAU1761 select_line_in path.
    for address, value in ((0x400A, 0x01), (0x400B, 0x07),
                           (0x400C, 0x01), (0x400D, 0x07)):
        write_codec(fd, address, [value])

    before = control.read(0x8)
    left, right = [], []
    for _ in range(100):
        left.append(signed24(samples.read(0x0)))
        right.append(signed24(samples.read(0x8)))
        time.sleep(0.01)
    after = control.read(0x8)
    assert control.read(0x0) == 0
    assert after > before, "PL frame counter did not advance"
    print({"muted": True, "pll": pll.hex(), "frames": after - before,
           "left_min": min(left), "left_max": max(left),
           "left_distinct": len(set(left)), "right_min": min(right),
           "right_max": max(right), "right_distinct": len(set(right))})
finally:
    if fd is not None:
        os.close(fd)
    BaseOverlay("base.bit")
    print("STOCK_BASE_RESTORED")
    fd = os.open("/dev/i2c-1", os.O_RDWR)
    try:
        fcntl.ioctl(fd, I2C_SLAVE, CODEC_ADDR)
        restored = read_codec(fd, 0x4002, 6)
        if restored != PLL_STOCK_48K:
            write_codec(fd, 0x4000, [0x0E])
            write_codec(fd, 0x4002, PLL_STOCK_WRITE)
            deadline = time.monotonic() + 2.0
            restored = read_codec(fd, 0x4002, 6)
            while not (restored[5] & 0x02) and time.monotonic() < deadline:
                time.sleep(0.01)
                restored = read_codec(fd, 0x4002, 6)
            write_codec(fd, 0x4000, [0x0F])
        print("STOCK_PLL_READBACK", restored.hex())
        assert restored == PLL_STOCK_48K
    finally:
        os.close(fd)
