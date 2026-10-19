"""Capture 4096 contiguous ADC frames without enabling the DAC.

Requires matching audio_capture.bit/.hwh in this directory. Prints summary
statistics only; no PCM or private voice recording is saved or uploaded.
"""

import fcntl
import os
import time
from pathlib import Path

import numpy as np
from pynq import MMIO, Overlay
from pynq.overlays.base import BaseOverlay


def capture_stats(label="ambient"):
    assert label in ("ambient", "quiet", "phone", "tone")
    bit = Path(__file__).resolve().with_name("audio_capture.bit")
    assert bit.is_file() and bit.with_suffix(".hwh").is_file()

    def write_reg(fd, addr, data):
        payload = addr.to_bytes(2, "big") + bytes(data)
        assert os.write(fd, payload) == len(payload)

    def read_reg(fd, addr, length):
        assert os.write(fd, addr.to_bytes(2, "big")) == 2
        value = os.read(fd, length)
        assert len(value) == length
        return value

    fd = None
    control = None
    command = None
    try:
        fd = os.open("/dev/i2c-1", os.O_RDWR)
        fcntl.ioctl(fd, 0x0703, 0x3B)
        for addr, val in ((0x401C, 0), (0x401E, 0),
                          (0x4023, 0xE5), (0x4024, 0xE5)):
            write_reg(fd, addr, [val])
        Overlay(str(bit), download=True)
        control = MMIO(0x41200000, 0x1000)
        samples = MMIO(0x41210000, 0x1000)
        command = MMIO(0x41220000, 0x1000)
        control.write(0, 0)
        command.write(0, 0)
        assert control.read(0) == 0
        write_reg(fd, 0x4000, [0x0E])
        write_reg(fd, 0x4002, bytes.fromhex("000000002801"))
        deadline = time.monotonic() + 2
        pll = read_reg(fd, 0x4002, 6)
        while not (pll[5] & 2) and time.monotonic() < deadline:
            time.sleep(0.01)
            pll = read_reg(fd, 0x4002, 6)
        assert pll[5] & 2, "codec PLL did not lock"
        write_reg(fd, 0x4000, [0x0F])
        for addr, val in ((0x400A, 1), (0x400B, 7),
                          (0x400C, 1), (0x400D, 7)):
            write_reg(fd, addr, [val])
        assert read_reg(fd, 0x40F2, 1) == b"\x01"
        assert read_reg(fd, 0x40F3, 1) == b"\x01"

        command.write(0, 1 << 16)
        deadline = time.monotonic() + 2
        while not (command.read(8) & 1) and time.monotonic() < deadline:
            time.sleep(0.001)
        status = command.read(8)
        assert status & 1, "PL capture did not finish in 2 seconds"
        count = (status >> 1) & 0x1FFF
        assert count == 4096, "unexpected capture count: %d" % count
        assert control.read(0) == 0, "DAC control must remain muted"
        raw = np.empty((count, 2), dtype=np.int64)
        for idx in range(count):
            command.write(0, (1 << 16) | idx)
            raw[idx, 0] = samples.read(0) & 0xFFFFFF
            raw[idx, 1] = samples.read(8) & 0xFFFFFF
        raw[raw >= 0x800000] -= 0x1000000
        centered = raw - raw.mean(axis=0)
        rms = np.sqrt(np.mean(centered * centered, axis=0))
        rms_dbfs = 20 * np.log10(np.maximum(rms, 1) / (2**23))
        peak_dbfs = 20 * np.log10(np.maximum(np.abs(raw).max(axis=0), 1) / (2**23))
        window = np.hanning(count)
        spectrum = np.abs(np.fft.rfft(centered[:, 0] * window))
        freqs = np.fft.rfftfreq(count, d=1 / 48828.125)
        band = (freqs >= 100) & (freqs <= 5000)
        dominant_hz = float(freqs[band][np.argmax(spectrum[band])])
        result = {
            "label": label, "frames": count, "dac_muted": control.read(0) == 0,
            "pl_frames_total_at_readback": control.read(8),
            "rms_dbfs": [round(float(x), 2) for x in rms_dbfs],
            "peak_dbfs": [round(float(x), 2) for x in peak_dbfs],
            "dominant_hz_left_100_5000": round(dominant_hz, 1),
        }
        print(result)
        return result
    finally:
        if command is not None:
            command.write(0, 0)
        if control is not None:
            control.write(0, 0)
            print("PL_CONTROL_MUTED", control.read(0) == 0)
        if fd is not None:
            try:
                for addr, val in ((0x401C, 0), (0x401E, 0),
                                  (0x4023, 0xE5), (0x4024, 0xE5)):
                    write_reg(fd, addr, [val])
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
                deadline = time.monotonic() + 2
                restored = read_reg(fd, 0x4002, 6)
                while not (restored[5] & 2) and time.monotonic() < deadline:
                    time.sleep(0.01)
                    restored = read_reg(fd, 0x4002, 6)
                write_reg(fd, 0x4000, [0x0F])
            print("STOCK_PLL_READBACK", restored.hex())
            assert restored == bytes.fromhex("0271023c2103")
        finally:
            os.close(fd)


print("MUTED_CAPTURE_READY (call capture_stats('ambient'|'quiet'|'phone'|'tone'))")
