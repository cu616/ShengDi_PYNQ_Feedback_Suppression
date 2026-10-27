"""Bounded closed-loop experiment. Import defines functions; never auto-plays.

On-site operator must confirm speaker setup and local microphone-data storage.
Uses matching audio_replay.bit/.hwh. Does not upload recordings.
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
from residual_tools import load_candidate
from closed_tools import trial_parameters
from replay_tools import verify_replay

FRAMES = 16384
# Tap count of the shipped audio_replay.bit. A model with fewer coefficients is loaded
# zero-padded up to this count (see load path); the evidence records both numbers so a
# padded 256-tap model is never reported as a trained 512-tap model.
HARDWARE_TAPS = 512


def decode_counts(packed_word, gain_word, mix_word):
    """Unpack the clip words. packed = {residual[31:16], prediction[15:0]}."""
    packed = int(packed_word) & 0xFFFFFFFF
    return [packed & 0xFFFF, (packed >> 16) & 0xFFFF,
            int(gain_word) & 0xFFFFFFFF, int(mix_word) & 0xFFFFFFFF]

# 阅读主线：参数检查→静音/配置→限时闭环→静音读RAM→恢复→本地保存。
# RATE来自自定义100MHz/2048分频，不是官方录音常见的48000 Hz。
RATE = 48828.125


def replay_trial(output_path, fixture_id, model_path, source_pcm16, bypass=False, zero_coeff=False,
                 gain_db=-36.0, seconds=0.5, hp_volume=40,
                 speaker_confirmed=False, local_capture_confirmed=False, before_start=None, direct_only=False):
    """One MANUALLY triggered closed-loop trial. No automated gain sweep.

    No headphones. Fixed speaker fixture; operator can cut power immediately.
    Both modes share the same gain, limiter and two-frame digital schedule.
    """
    if speaker_confirmed is not True or local_capture_confirmed is not True:
        raise ValueError("confirm speaker setup and local storage; remove headphones")
    if before_start is not None and not callable(before_start):
        raise ValueError("before_start must be callable or None")
    if type(bypass) is not bool or type(zero_coeff) is not bool:
        raise ValueError("bypass/zero_coeff must be bool")
    gain_q12, budget = trial_parameters(gain_db, seconds)
    if type(direct_only) is not bool:
        raise ValueError("direct_only must be bool")
    if direct_only:
        gain_q12 = 0
    source_pcm16 = np.asarray(source_pcm16)
    if (source_pcm16.ndim != 1 or source_pcm16.dtype.kind not in 'iu' or
            not 1 <= len(source_pcm16) <= 131072 or
            np.any(source_pcm16 < -32768) or np.any(source_pcm16 > 32767) or
            budget < len(source_pcm16)+2):
        raise ValueError("invalid source PCM16 or insufficient duration")
    source_pcm16 = source_pcm16.astype('<i2')
    if not isinstance(hp_volume, int) or not 10 <= hp_volume <= 40:
        raise ValueError("hp_volume must be 10..40 and match calibration")
    output_path = Path(output_path)
    if output_path.suffix != ".npz" or output_path.exists() or not output_path.parent.is_dir():
        raise ValueError("choose a NEW .npz path in an existing board directory")
    bit = Path(__file__).resolve().with_name("audio_replay.bit")
    if not bit.is_file() or not bit.with_suffix(".hwh").is_file():
        raise FileNotFoundError("matching bit/hwh required")
    model, coefficients = load_candidate(model_path, fixture_id, hp_volume, RATE)
    logical_taps = int(len(coefficients))
    if len(coefficients) < HARDWARE_TAPS:
        # The 512-tap RTL only sets `fresh` after exactly HARDWARE_TAPS coefficients, so a
        # 256-tap model must be zero-padded. Zero taps change nothing mathematically; the
        # evidence keeps logical_taps/loaded_taps so the padding stays visible.
        coefficients = np.concatenate(
            [coefficients, np.zeros(HARDWARE_TAPS - len(coefficients), dtype=np.int64)])
    if zero_coeff:
        coefficients = np.zeros(len(coefficients), dtype=np.int64)
    fd, control, raw = None, None, None
    cleanup_errors, salvage_errors = [], []
    armed, stop_reason, error, save_error = False, None, None, None
    completed, count, first, elapsed = 0, 0, 0, 0.0
    status, clip_word, gain_word, mix_word = 0, 0, 0, 0
    counts = [0, 0, 0, 0]
    source_loaded_ok = False
    coeff_status_word = 0

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

    def read_ring(first_index, frame_count):
        """Read the capture ring chronologically; returns int64 [frames, 4]."""
        out = np.empty((frame_count, 4), dtype=np.int64)
        for i in range(frame_count):
            address = (first_index + i) % FRAMES
            command.write(0, address)
            command.read(0)
            out[i, 0] = samples.read(0) & 0xFFFFFF
            out[i, 1] = samples.read(8) & 0xFFFFFF
            command.write(0, (1 << 16) | address)
            command.read(0)
            out[i, 2] = samples.read(0) & 0xFFFFFF
            out[i, 3] = samples.read(8) & 0xFFFFFF
        out[out >= 0x800000] -= 0x1000000
        return out

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
        source = MMIO(overlay.ip_dict["audio_source"]["phys_addr"], 0x1000)
        source_len = MMIO(overlay.ip_dict["audio_source_length"]["phys_addr"], 0x1000)
        if source.read(8) >> 24 != 0x52:
            raise RuntimeError("replay ABI mismatch")
        source.write(4, 0)
        source_len.write(4, 0)
        source_len.write(0, len(source_pcm16))
        source_word = 1 << 17
        source.write(0, source_word)
        source.read(8)
        for sample in source_pcm16:
            source_word = ((source_word ^ (1 << 16)) & 0x30000) | (int(sample) & 0xffff)
            source.write(0, source_word)
        loaded = source.read(8)
        if (loaded & 0x3ffff) != len(source_pcm16) or loaded & (1 << 18) or not loaded & (1 << 19):
            raise RuntimeError("source load incomplete: %08x" % loaded)
        # Verified from the ABI readback, not from the requested duration.
        source_loaded_ok = True
        coeff = MMIO(overlay.ip_dict["audio_coefficients"]["phys_addr"], 0x1000)
        coeff.write(0, 0)
        coeff.write(4, 0)
        coeff_word = 1 << 25
        coeff.write(0, coeff_word)
        for value in coefficients:
            if not (coeff.read(8) & 1):
                raise RuntimeError("coefficient loader not ready")
            coeff_word = ((coeff_word ^ (1 << 24)) & 0x03000000) | (int(value) & 0xFFFFFF)
            coeff.write(0, coeff_word)
        coeff_status = coeff.read(8)
        coeff_status_word = int(coeff_status)
        if ((coeff_status >> 4) & 0xFFFF) != len(coefficients) or (coeff_status & 0xE) != 0xA:
            raise RuntimeError("coefficient load rejected: %08x" % coeff_status)
        runtime = MMIO(overlay.ip_dict["audio_runtime"]["phys_addr"], 0x1000)
        clips = MMIO(overlay.ip_dict["audio_clips"]["phys_addr"], 0x1000)
        runtime.write(4, 0)
        runtime.write(0, budget)
        pll_readback = set_pll("000000002801").hex()
        if pll_readback != "000000002803":
            raise RuntimeError("unexpected 50 MHz PLL readback")
        for addr, value in ((0x400A, 1), (0x400B, 7), (0x400C, 1), (0x400D, 7)):
            write_reg(addr, [value])
        for addr in (0x40F2, 0x40F3, 0x40F5, 0x40F6):
            if read_reg(addr, 1) != b"\x01":
                raise RuntimeError("unexpected codec route/power at %04x" % addr)
        # Batch operator starts ONLY after configuration is ready, while still muted.
        if before_start is not None and before_start() is not True:
            raise RuntimeError("operator cancelled before audio start")
        hp = (hp_volume << 2) | 3
        for addr, value in ((0x401C, 0x21), (0x401E, 0x41), (0x4023, hp), (0x4024, hp)):
            write_reg(addr, [value])
        start = time.monotonic()
        control.write(0, 1 | (int(bypass) << 1) | (gain_q12 << 16))
        armed = True
        deadline = start + budget / RATE + 2
        status = command.read(8)
        # Stop on config/protocol fault. Saturation is counted, NEVER called ASG.
        while not (status & (1 | (3 << 17))) and time.monotonic() < deadline:
            # Captain 2026-10-27: a pre-gain residual overflow is diagnostic only. The wide residual
            # may exceed the old 24-bit rail while the post-gain output is still representable, so
            # stopping on it interrupts a run that could have continued. The packed word is
            # {residual[31:16], prediction[15:0]}, so only the prediction half stops the run here;
            # post-gain (gain_word) and mix (mix_word) overflow still stop it, and the residual count
            # is still read and reported after the run.
            if (int(clips.read(0)) & 0xFFFF) or clips.read(8) or source_len.read(8):
                stop_reason = "guard"
                break
            time.sleep(0.002)
            status = command.read(8)
        # Stop the sound first, then freeze the capture and read every counter AFTER the run.
        control.write(0, 0)
        mute_codec()
        elapsed = time.monotonic() - start
        status = command.read(8)
        completed = runtime.read(8)
        clip_word, gain_word, mix_word = clips.read(0), clips.read(8), source_len.read(8)
        counts = decode_counts(clip_word, gain_word, mix_word)
        if stop_reason is None:
            if status & (3 << 17):
                stop_reason = "fault"
            elif not status & 1 or completed != budget:
                stop_reason = "incomplete"
        count = min(FRAMES, completed)
        first = completed - count
        raw = read_ring(first, count)
    except BaseException as exc:
        # Any failure after arming must still yield evidence: stop sound, freeze, read back.
        error = exc
        if armed and control is not None:
            for attempt in (lambda: control.write(0, 0), mute_codec):
                try:
                    attempt()
                except Exception:
                    pass
            try:
                if stop_reason is None:
                    stop_reason = "exception"
                status = command.read(8)
                completed = runtime.read(8)
                clip_word, gain_word, mix_word = clips.read(0), clips.read(8), source_len.read(8)
                counts = decode_counts(clip_word, gain_word, mix_word)
                count = min(FRAMES, completed)
                first = completed - count
                if raw is None:
                    raw = read_ring(first, count)
            except Exception as salvage_error:
                salvage_errors.append(str(salvage_error))
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

    # ---- one evidence path, used by every outcome (C: a-replay-evidence-v2) ----
    recovery_ok = not cleanup_errors
    metadata = None
    if armed:
        count = min(FRAMES, max(int(completed or 0), 0))
        first = max(int(completed or 0) - count, 0)
        mic = (raw[:, 1] / 2**23) if raw is not None and len(raw) else np.zeros(0)
        checks = {}
        if stop_reason is None and raw is not None and len(raw) > len(coefficients):
            try:
                checks = verify_replay(raw, coefficients, bypass, gain_q12, source_pcm16, first)
            except Exception as exc:
                checks = {"verification_skipped": str(exc)}
        metadata = dict(
            schema_version=1, artifact_kind="replay_trial", capture_id=str(uuid.uuid4()),
            driver_evidence_version="a-replay-evidence-v2", source="board",
            forward_path_open=direct_only, fixture_id=fixture_id, bypass=bypass,
            zero_coeff=zero_coeff, gain_q12=gain_q12,
            gain_db_actual=(float(20 * np.log10(gain_q12 / 4096)) if gain_q12 else None),
            hp_volume=hp_volume, sample_rate_hz=RATE, pll_readback=pll_readback,
            frames=count, completed_frames=int(completed or 0), first_frame=first,
            capture_status=status,
            sound_seconds_nominal=budget / RATE, completion_poll_seconds=elapsed,
            prediction_saturations=counts[0], residual_saturations=counts[1],
            gain_saturations=counts[2], mix_saturations=counts[3],
            clip_counts_raw=[int(clip_word), int(gain_word), int(mix_word)],
            early_stop=bool(stop_reason is not None),
            stop_reason=(stop_reason or "completed"),
            source_frames=int(len(source_pcm16)),
            source_end_frame_exclusive=int(source_pcm16.shape[0]),
            source_schedule_verified=bool(source_loaded_ok),
            source_pcm16_sha256=hashlib.sha256(source_pcm16.tobytes()).hexdigest(),
            bit_sha256=hashlib.sha256(bit.read_bytes()).hexdigest(),
            model_sha256=hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
            coefficients_sha256=hashlib.sha256(coefficients.astype("<i4").tobytes()).hexdigest(),
            logical_taps=int(logical_taps), loaded_taps=int(len(coefficients)),
            coefficient_status=int(coeff_status_word),
            zero_padded=bool(len(coefficients) > int(logical_taps)),
            verification=checks,
            interpretation="bounded closed loop; NOT measured MSG/ASG")
        if len(mic):
            metadata["mic_rms_dbfs"] = float(20 * np.log10(max(float(np.std(mic)), 2**-23)))
            metadata["mic_peak_dbfs"] = float(20 * np.log10(max(float(np.max(np.abs(mic))), 2**-23)))
            metadata["mic_full_scale_samples"] = int(np.count_nonzero(
                (raw[:, 1] <= -2**23) | (raw[:, 1] >= 2**23 - 1)))
        try:
            with output_path.open("xb") as stream:
                np.savez_compressed(stream,
                                    reference=(raw[:, 0] / 2**23) if raw is not None else np.zeros(0),
                                    microphone=mic,
                                    prediction_pcm=(raw[:, 2] if raw is not None else np.zeros(0)),
                                    residual_pcm=(raw[:, 3] if raw is not None else np.zeros(0)),
                                    coefficients_q20=coefficients,
                                    source_pcm16=source_pcm16,
                                    sample_rate_hz=RATE,
                                    metadata_json=json.dumps(metadata))
            print("LOCAL_CAPTURE_SAVED", str(output_path), "FRAMES", count)
            if "mic_rms_dbfs" in metadata:
                print({k: metadata[k] for k in ("mic_rms_dbfs", "mic_peak_dbfs",
                                                "mic_full_scale_samples")})
            print("CLOSED_VERIFICATION", checks)
            print("STOP_REASON", metadata["stop_reason"], "early_stop", metadata["early_stop"])
            print("NO_DATA_UPLOADED")
        except Exception as exc:
            save_error = str(exc)
            print("CAPTURE_SAVE_FAILED", save_error)

    status_path = output_path.with_suffix(".status.json")
    status_payload = dict(
        schema_version=1, driver_evidence_version="a-replay-evidence-v2",
        capture=str(output_path), fixture_id=fixture_id,
        recovery_ok=bool(recovery_ok), cleanup_errors=list(cleanup_errors),
        salvage_errors=list(salvage_errors), save_error=save_error,
        stop_reason=(stop_reason or "completed"),
        error=(str(error) if error is not None else None),
        armed=bool(armed),
        completed_frames=int(completed or 0), frames=int(count or 0), first_frame=int(first or 0),
        source_end_frame_exclusive=int(source_pcm16.shape[0]),
        source_schedule_verified=bool(source_loaded_ok),
        clip_counts_raw=[int(clip_word), int(gain_word), int(mix_word)],
        prediction_saturations=int(counts[0]), residual_saturations=int(counts[1]),
        gain_saturations=int(counts[2]), mix_saturations=int(counts[3]),
        logical_taps=int(logical_taps), loaded_taps=int(len(coefficients)),
        coefficient_status=int(coeff_status_word), bit_sha256=hashlib.sha256(bit.read_bytes()).hexdigest())
    try:
        status_path.write_text(json.dumps(status_payload, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        print("STATUS_SAVED", str(status_path))
    except Exception as exc:
        print("STATUS_SAVE_FAILED", str(exc))

    if save_error is not None:
        raise RuntimeError("capture save failed: " + save_error)
    if stop_reason == "guard":
        raise RuntimeError('runtime saturation guard stopped playback; packed_prediction_residual=%d '
                           'gain=%d mix=%d; no further gain authorized'
                           % (int(clip_word), int(gain_word), int(mix_word)))
    if error is not None:
        raise error
    if not recovery_ok:
        raise RuntimeError("restoration failed; do not run another audio test")
    return metadata


print("REPLAY_TRIAL_READY; import does not play; call replay_trial manually")
