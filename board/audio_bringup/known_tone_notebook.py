"""Paste into a PYNQ notebook, then call stock_tone() while someone listens.

Produces three short 1 kHz beeps through the official base overlay, with no
microphone input or recording. Used only to calibrate this fixed-volume speaker.
"""

import fcntl
import os
import time

import numpy as np
from pynq.overlays.base import BaseOverlay


def stock_tone(volume=45, amplitude_dbfs=-24):
    assert 30 <= volume <= 50
    assert -36 <= amplitude_dbfs <= -18
    base = BaseOverlay("base.bit")
    audio = base.audio
    audio.configure()
    audio.deselect_inputs()
    audio.set_volume(volume)

    rate = 48000
    t = np.arange(int(1.5 * rate), dtype=np.float64) / rate
    envelope = np.zeros_like(t)
    # Five-millisecond linear fades limit clicks at burst boundaries.
    for start in (0.20, 0.65, 1.10):
        region = (t >= start) & (t < start + 0.25)
        envelope[region] = np.minimum(
            np.clip((t[region] - start) / 0.005, 0, 1),
            np.clip((start + 0.25 - t[region]) / 0.005, 0, 1))
    magnitude = (2**23 - 1) * 10**(amplitude_dbfs / 20)
    mono = np.rint(envelope * magnitude * np.sin(2 * np.pi * 1000 * t)).astype(np.int32)
    audio.buffer = np.repeat(mono[:, None], 2, axis=1).reshape(-1)
    audio.sample_len = len(mono)

    began = time.monotonic()
    try:
        audio.play()
    finally:
        fd = os.open("/dev/i2c-1", os.O_RDWR)
        try:
            fcntl.ioctl(fd, 0x0703, 0x3B)
            for address, value in ((0x401C, 0), (0x401E, 0),
                                   (0x4023, 0xE5), (0x4024, 0xE5)):
                payload = address.to_bytes(2, "big") + bytes([value])
                assert os.write(fd, payload) == len(payload)
                assert os.write(fd, address.to_bytes(2, "big")) == 2
                assert os.read(fd, 1) == bytes([value])
        finally:
            os.close(fd)
    print({"pattern": "three 250-ms 1-kHz beeps", "frames": len(mono),
           "peak_sample": int(np.abs(mono).max()),
           "amplitude_dbfs": amplitude_dbfs, "codec_volume": volume,
           "codec_db_approx": volume - 57,
           "elapsed_seconds": round(time.monotonic() - began, 3),
           "output_muted_after": True})
