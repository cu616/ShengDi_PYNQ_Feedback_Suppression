"""Muted, bounded ADAU1761 PLL check for the 100 MHz / 2048 PL frame clock.

This is a clock-compatibility check only. It does not route or play audio.
Run from the board directory containing matching audio_bringup.bit/.hwh.
"""

import fcntl
import os
import time
from pathlib import Path

from pynq import MMIO, Overlay
from pynq.overlays.base import BaseOverlay


BIT = Path.cwd() / "audio_bringup.bit"
assert BIT.is_file() and BIT.with_suffix(".hwh").is_file()
I2C_SLAVE = 0x0703
CODEC_ADDR = 0x3B
PLL_50MHZ = bytes.fromhex("000000002801")  # 10 MHz MCLK, X=1, R=5, integer, PLLEN=1
PLL_STOCK_48K = bytes.fromhex("0271023c2103")
PLL_STOCK_WRITE = bytes.fromhex("0271023c2101")  # Lock bit is read-only.


def write_codec(fd, address, data):
    payload = address.to_bytes(2, "big") + bytes(data)
    assert os.write(fd, payload) == len(payload)


def read_codec(fd, address, count):
    assert os.write(fd, address.to_bytes(2, "big")) == 2
    data = os.read(fd, count)
    assert len(data) == count
    return data


fd = None
try:
    # Silence the stock codec output before any clock transition.
    fd = os.open("/dev/i2c-1", os.O_RDWR)
    fcntl.ioctl(fd, I2C_SLAVE, CODEC_ADDR)
    for address, value in ((0x401C, 0), (0x401E, 0), (0x4023, 0xE5), (0x4024, 0xE5)):
        write_codec(fd, address, [value])

    Overlay(str(BIT), download=True)
    gpio = MMIO(0x41200000, 0x1000)
    gpio.write(0x0, 0)
    gpio.write(0x4, 0)
    assert gpio.read(0x0) == 0

    write_codec(fd, 0x4000, [0x0E])  # Disable core while retaining PLL source.
    write_codec(fd, 0x4002, PLL_50MHZ)  # One continuous six-byte write.
    deadline = time.monotonic() + 2.0
    pll = read_codec(fd, 0x4002, 6)
    while not (pll[5] & 0x02) and time.monotonic() < deadline:
        time.sleep(0.01)
        pll = read_codec(fd, 0x4002, 6)
    assert pll[5] & 0x02, "ADAU1761 PLL did not lock within 2 s"
    write_codec(fd, 0x4000, [0x0F])
    assert read_codec(fd, 0x4000, 1) == b"\x0f"
    assert gpio.read(0x0) == 0
    print("PLL_50MHZ_LOCKED", pll.hex(), "mute", gpio.read(0x0) == 0)
finally:
    if fd is not None:
        os.close(fd)
    base = BaseOverlay("base.bit")
    print("STOCK_BASE_RESTORED")
    # BaseOverlay configures the stock codec. Verify rather than assume.
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
