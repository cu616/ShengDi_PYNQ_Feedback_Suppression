"""Bounded PL TX activity probe with codec and physical SDATA output muted.

Run from the board's base/audio directory after placing matching audio_diag
.bit/.hwh and this script in base/audio/audio_diag/. No recording is saved.
This is diagnostic evidence, not audible playback or feedback suppression.
"""

import fcntl
import os
import time
from pathlib import Path

from pynq import MMIO, Overlay
from pynq.overlays.base import BaseOverlay


BIT = Path(__file__).resolve().with_name("audio_diag.bit")
assert BIT.is_file() and BIT.with_suffix(".hwh").is_file()
PLL_50 = bytes.fromhex("000000002801")
PLL_STOCK = bytes.fromhex("0271023c2103")


def wr(fd, address, data):
    payload = address.to_bytes(2, "big") + bytes(data)
    assert os.write(fd, payload) == len(payload)


def rd(fd, address, size):
    assert os.write(fd, address.to_bytes(2, "big")) == 2
    data = os.read(fd, size)
    assert len(data) == size
    return data


fd = None
control = None
try:
    fd = os.open("/dev/i2c-1", os.O_RDWR)
    fcntl.ioctl(fd, 0x0703, 0x3B)
    for address, value in ((0x401C, 0), (0x401E, 0),
                           (0x4023, 0xE5), (0x4024, 0xE5)):
        wr(fd, address, [value])

    Overlay(str(BIT), download=True)
    control = MMIO(0x41200000, 0x1000)
    samples = MMIO(0x41210000, 0x1000)
    tx = MMIO(0x41220000, 0x1000)
    control.write(0, 0)
    control.write(4, 0)
    assert control.read(0) == 0

    wr(fd, 0x4000, [0x0E])
    wr(fd, 0x4002, PLL_50)
    deadline = time.monotonic() + 2.0
    pll = rd(fd, 0x4002, 6)
    while not (pll[5] & 2) and time.monotonic() < deadline:
        time.sleep(0.01)
        pll = rd(fd, 0x4002, 6)
    assert pll[5] & 2, "PLL did not lock"
    wr(fd, 0x4000, [0x0F])
    for address, value in ((0x400A, 1), (0x400B, 7),
                           (0x400C, 1), (0x400D, 7)):
        wr(fd, address, [value])

    before_frames = control.read(8)
    before_tx = tx.read(0)
    before_ones = tx.read(8)
    # Enable frame path, shift six, force the physical SDATA output pin low.
    command = 1 | (6 << 1) | (1 << 4)
    control.write(0, command)
    assert control.read(0) == command
    time.sleep(1.0)
    control.write(0, 0)
    frames = control.read(8) - before_frames
    nonzero = tx.read(0) - before_tx
    ones = tx.read(8) - before_ones
    print({"physical_sdata_forced_low": True, "codec_output_muted": True,
           "control_mute_readback": control.read(0) == 0,
           "frames": frames, "tx_nonzero_frames": nonzero,
           "serializer_one_edges": ones,
           "rx_snapshot": [samples.read(0) & 0xFFFFFF,
                           samples.read(8) & 0xFFFFFF]})
    assert frames > 0 and nonzero > 0 and ones > 0
finally:
    if control is not None:
        control.write(0, 0)
        print("PL_CONTROL_MUTED", control.read(0) == 0)
    if fd is not None:
        try:
            for address, value in ((0x401C, 0), (0x401E, 0),
                                   (0x4023, 0xE5), (0x4024, 0xE5)):
                wr(fd, address, [value])
        finally:
            os.close(fd)
    BaseOverlay("base.bit")
    print("STOCK_BASE_RESTORED")
    fd = os.open("/dev/i2c-1", os.O_RDWR)
    try:
        fcntl.ioctl(fd, 0x0703, 0x3B)
        restored = rd(fd, 0x4002, 6)
        if restored != PLL_STOCK:
            wr(fd, 0x4000, [0x0E])
            wr(fd, 0x4002, bytes.fromhex("0271023c2101"))
            deadline = time.monotonic() + 2.0
            restored = rd(fd, 0x4002, 6)
            while not (restored[5] & 2) and time.monotonic() < deadline:
                time.sleep(0.01)
                restored = rd(fd, 0x4002, 6)
            wr(fd, 0x4000, [0x0F])
        print("STOCK_PLL_READBACK", restored.hex())
        assert restored == PLL_STOCK
    finally:
        os.close(fd)
