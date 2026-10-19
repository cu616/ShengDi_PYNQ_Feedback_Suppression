"""Prepared open-loop experiment. Import defines functions; never auto-plays.

On-site operator must confirm speaker setup and local microphone-data storage.
Uses matching audio_calibrate.bit/.hwh. Does not upload recordings.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

import numpy as np
from pynq import MMIO, Overlay
from pynq.overlays.base import BaseOverlay

FRAMES = 32768
# 阅读主线：参数检查→静音/配置→限时激励→静音读RAM→恢复→本地保存。
# RATE来自自定义100MHz/2048分频，不是官方录音常见的48000 Hz。
RATE = 48828.125


def expected_reference(seed_variant, shift):
    # PS重建与RTL相同的xorshift32序列，逐字核对采回的实际DAC参考。
    state = 0x6D2B79F5 if seed_variant else 1
    words = np.empty(FRAMES, dtype=np.int32)
    for n in range(FRAMES):
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        value = state & 0xFFFFFF
        # 低24位先解释为补码，再算术右移；不能按无符号数缩放。
        if value & 0x800000:
            value -= 0x1000000
        words[n] = value >> shift
    return words


def open_loop_capture(output_path, fixture_id, seed_variant=0, shift=4, hp_volume=40,
                      speaker_confirmed=False, local_capture_confirmed=False):
    """Emit one <=0.672 s known waveform, capture paired frames, restore stock.

    Speaker must be in the fixed fixture, headphones removed, immediate power
    disconnect available. No ADC signal is sent to DAC by this RTL.
    Files remain on board. Use seed 0 for training, seed 1 for validation.
    """
    if speaker_confirmed is not True or local_capture_confirmed is not True:
        # 文件导入不发声，调用时才执行；两个True需现场操作者实际确认。
        raise ValueError("confirm speaker setup and local microphone-data storage first")
    if not isinstance(fixture_id, str) or not fixture_id.strip():
        raise ValueError("record a fixture identity for the fixed geometry/gain/wiring")
    if seed_variant not in (0, 1) or not isinstance(shift, int) or not 4 <= shift <= 10:
        raise ValueError("seed must be 0/1 and shift an integer 4..10")
    if not isinstance(hp_volume, int) or not 10 <= hp_volume <= 40:
        raise ValueError("hp_volume must be integer 10..40")
    output_path = Path(output_path)
    if output_path.suffix != ".npz" or output_path.exists() or not output_path.parent.is_dir():
        raise ValueError("choose a new .npz path in an existing board directory")
    bit = Path(__file__).resolve().with_name("audio_calibrate.bit")
    if not bit.is_file() or not bit.with_suffix(".hwh").is_file():
        raise FileNotFoundError("matching bit/hwh required")
    fd, control, raw = None, None, None
    cleanup_errors = []

    def write_reg(addr, data):
        # Codec用两字节大端I2C寄存器地址；与PL的MMIO控制是两条不同通路。
        payload = addr.to_bytes(2, "big") + bytes(data)
        if os.write(fd, payload) != len(payload):
            raise IOError("short I2C write")

    def read_reg(addr, count):
        if os.write(fd, addr.to_bytes(2, "big")) != 2:
            raise IOError("short I2C address write")
        value = os.read(fd, count)
        if len(value) != count:
            raise IOError("short I2C read")
        return value

    def mute_codec():
        for addr, value in ((0x401C, 0), (0x401E, 0), (0x4023, 0xE5), (0x4024, 0xE5)):
            write_reg(addr, [value])

    def set_pll(payload):
        # 配置后轮询锁定位，超时拒绝继续；结束需恢复官方base对应的PLL参数。
        write_reg(0x4000, [0x0E])
        write_reg(0x4002, bytes.fromhex(payload))
        deadline = time.monotonic() + 2
        value = read_reg(0x4002, 6)
        while not (value[5] & 2) and time.monotonic() < deadline:
            time.sleep(0.01)
            value = read_reg(0x4002, 6)
        if not (value[5] & 2):
            raise RuntimeError("Codec PLL lock timeout")
        write_reg(0x4000, [0x0F])
        return value

    def cleanup_step(name, action):
        try:
            action()
        except Exception as exc:
            cleanup_errors.append(name + ": " + str(exc))

    try:
        fd = os.open("/dev/i2c-1", os.O_RDWR)
        fcntl.ioctl(fd, 0x0703, 0x3B)
        mute_codec()
        overlay = Overlay(str(bit), download=True)
        # Read addresses from this overlay's matching HWH, not old GPIO handles.
        control = MMIO(overlay.ip_dict["audio_control"]["phys_addr"], 0x1000)
        samples = MMIO(overlay.ip_dict["audio_samples"]["phys_addr"], 0x1000)
        command = MMIO(overlay.ip_dict["audio_calibrate_cmd"]["phys_addr"], 0x1000)
        control.write(0, 0)
        control.write(4, 0)
        # AXI GPIO通道1：+0为数据，+4为方向，方向写0表示输出。
        command.write(0, 0)
        command.write(4, 0)
        set_pll("000000002801")
        for addr, value in ((0x400A, 1), (0x400B, 7), (0x400C, 1), (0x400D, 7)):
            write_reg(addr, [value])
        for addr in (0x40F2, 0x40F3, 0x40F5, 0x40F6):
            if read_reg(addr, 1) != b"\x01":
                raise RuntimeError("unexpected codec route/power at %04x" % addr)
        hp = (hp_volume << 2) | 3
        for addr, value in ((0x401C, 0x21), (0x401E, 0x41), (0x4023, hp), (0x4024, hp)):
            write_reg(addr, [value])
        start = time.monotonic()
        control.write(0, 1 | (shift << 1) | (seed_variant << 8))
        # bit0启动；bits4:1为算术右移量；bit8选择训练/验证种子。
        deadline = start + 2
        status = command.read(8)
        while not (status & 1) and time.monotonic() < deadline:
            time.sleep(0.002)
            status = command.read(8)
        # Always mute before slow PS readback. RTL separately bounds emitted frames.
        mute_codec()
        elapsed = time.monotonic() - start
        if (status & (1 << 17)) or not (status & 1) or ((status >> 1) & 0xFFFF) != FRAMES:
            # status[17]非法配置，[16:1]捕获数量，[0]完成；三项都必须正确。
            raise RuntimeError("capture incomplete or configuration rejected: %08x" % status)
        raw = np.empty((FRAMES, 2), dtype=np.int64)
        # 此时已经静音。PS逐地址读RAM较慢，读回时间不属于发声时长。
        for i in range(FRAMES):
            command.write(0, i)
            raw[i, 0] = samples.read(0) & 0xFFFFFF
            raw[i, 1] = samples.read(8) & 0xFFFFFF
        raw[raw >= 0x800000] -= 0x1000000
        # GPIO取出的低24位是无符号码，减2^24恢复负数的补码解释。
        if not np.array_equal(raw[:, 0], expected_reference(seed_variant, shift)):
            raise RuntimeError("captured DAC reference differs from expected sequence; reject alignment")
    finally:
        # 正常完成和异常均走恢复；任一步失败会记录，其他恢复步骤仍尝试执行。
        # Attempt every recovery step even if a preceding I2C/MMIO operation fails.
        if control is not None:
            cleanup_step("PL mute", lambda: control.write(0, 0))
        if fd is not None:
            cleanup_step("Codec mute", mute_codec)
            cleanup_step("I2C close", lambda: os.close(fd))
            fd = None
        cleanup_step("stock overlay", lambda: BaseOverlay("base.bit"))
        try:
            fd = os.open("/dev/i2c-1", os.O_RDWR)
            fcntl.ioctl(fd, 0x0703, 0x3B)
            restored = set_pll("0271023c2101")
            mute_codec()
            if restored.hex() != "0271023c2103":
                raise RuntimeError("unexpected stock PLL readback")
            print("STOCK_PLL_READBACK", restored.hex())
        except Exception as exc:
            cleanup_errors.append("stock PLL/mute: " + str(exc))
        finally:
            if fd is not None:
                cleanup_step("restoration I2C close", lambda: os.close(fd))
        if cleanup_errors:
            print("RESTORE_ERRORS", cleanup_errors)
        else:
            print("STOCK_BASE_RESTORED_AND_CODEC_MUTED")
    if cleanup_errors:
        # 恢复失败不保存成功数据；原始采集异常也会在finally后继续向外抛出。
        raise RuntimeError("restoration failed; do not run another audio test")
    metadata = {"schema_version": 1, "capture_id": str(uuid.uuid4()), "source": "board",
                "forward_path_open": True, "alignment": "same_i2s_frame", "dropped_frames": 0,
                "reference_sequence_verified": True, "seed_variant": seed_variant, "fixture_id": fixture_id,
                "shift": shift, "hp_volume": hp_volume, "frames": FRAMES,
                "sound_seconds_nominal": FRAMES / RATE, "completion_poll_seconds": elapsed,
                "bit_sha256": hashlib.sha256(bit.read_bytes()).hexdigest()}
    mic = raw[:, 1] / 2**23
    # PCM/2^23转为满幅单位。std对应去直流RMS，下面的峰值则包含直流分量。
    metadata["mic_rms_dbfs"] = float(20 * np.log10(max(float(np.std(mic)), 2**-23)))
    metadata["mic_peak_dbfs"] = float(20 * np.log10(max(float(np.max(np.abs(mic))), 2**-23)))
    metadata["mic_full_scale_samples"] = int(np.count_nonzero((raw[:, 1] <= -2**23) | (raw[:, 1] >= 2**23-1)))
    # Exclusive creation prevents overwriting a previous calibration capture.
    with output_path.open("xb") as stream:
        np.savez_compressed(stream, reference=raw[:, 0] / 2**23,
                            microphone=raw[:, 1] / 2**23, sample_rate_hz=RATE,
                            metadata_json=json.dumps(metadata))
    print("LOCAL_CAPTURE_SAVED", str(output_path), "FRAMES", FRAMES)
    print({k: metadata[k] for k in ("mic_rms_dbfs", "mic_peak_dbfs", "mic_full_scale_samples", "reference_sequence_verified")})
    print("NO_DATA_UPLOADED")
    return metadata


print("OPEN_LOOP_CAPTURE_READY; no sound until explicitly calling open_loop_capture")
