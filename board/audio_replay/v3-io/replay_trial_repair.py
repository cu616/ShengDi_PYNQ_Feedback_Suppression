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

# Overlay reuse for the product path: prepare() downloads the bitstream once, then the capture
# stages reuse it. A stale cache from a different bitstream is never used.
_OVERLAY_CACHE = {"overlay": None, "bit": None}
from residual_tools import load_candidate
from closed_tools import trial_parameters
import replay_tools
from replay_tools import verify_replay

FRAMES = 16384
# Tap count of the shipped audio_replay.bit. A model with fewer coefficients is loaded
# zero-padded up to this count (see load path); the evidence records both numbers so a
# padded 256-tap model is never reported as a trained 512-tap model.
HARDWARE_TAPS = 512
# Wait between unmuting the codec and arming, so the unmute pop decays before the run starts
# (observed 2026-10-28: a "du" from the speaker railed the ADC on the first frames).
CODEC_SETTLE_SECONDS = 0.25


def decode_counts(packed_word, gain_word, mix_word):
    """Unpack the clip words. packed = {residual[31:16], prediction[15:0]}."""
    packed = int(packed_word) & 0xFFFFFFFF
    return [packed & 0xFFFF, (packed >> 16) & 0xFFFF,
            int(gain_word) & 0xFFFFFFFF, int(mix_word) & 0xFFFFFFFF]


# capture_status bit that reports the independent input full-scale detector (audio-replay v3).
INPUT_CLIP_BIT = 22

# The bitstream this driver is written against (audio-replay v3). A driver and a bitstream from
# different versions may both run, but their semantics differ (v2 stops on a pre-gain residual
# overflow and has no bit22), so evidence from a mixed pair would mean nothing. Refuse BEFORE
# arming: no overlay download, no sound.
EXPECTED_BIT_SHA256 = "322350656986d91f25a63735f87e5b0b9cc2f7ea977356ce9e988014648e738e"
EXPECTED_HWH_SHA256 = "bbe1eb4935b0931f8af259ef5140d9d1fa2dbe144f82c765f158652aa741b728"


def _file_sha256(path):
    """sha256 of a file, or None when it cannot be read. Never raises."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except Exception:
        return None


def verify_paired_bitstream(bit_path):
    """Refuse to run when the bit/hwh next to this driver is not the declared pair.

    Pure enough to test without hardware: it only reads the two files.
    """
    bit_path = Path(bit_path)
    hwh_path = bit_path.with_suffix(".hwh")
    if not bit_path.is_file() or not hwh_path.is_file():
        raise FileNotFoundError("matching bit/hwh required")
    for path, expected, label in ((bit_path, EXPECTED_BIT_SHA256, "bitstream"),
                                  (hwh_path, EXPECTED_HWH_SHA256, "hwh")):
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != expected:
            raise RuntimeError(
                "%s does not match this driver: expected %s, got %s. Driver and bitstream must be "
                "released together (docs/contracts/audio-replay-v3.md); refusing to start."
                % (label, expected, got))


def runtime_stop(status, clip_word, gain_word, mix_word):
    """Decide whether one poll of the run should stop the sound, and why.

    Pure function so the semantics can be checked without hardware.

    Two different things are kept apart on purpose (captain 2026-10-28):
      * INPUT OVERLOAD IS A STOP CONDITION. capture_status bit22 is the only counter that can see
        an overloaded microphone when the prediction is zero, because the residual then equals the
        microphone and can never overflow. It stops the run and is reported as "input_clip".
      * A PRE-GAIN RESIDUAL OVERFLOW IS NOT. The packed word is {residual[31:16],
        prediction[15:0]}; the wide residual may exceed the old 24-bit rail while the post-gain
        output is still representable, so its half of the word only keeps counting and is read and
        reported after the run.
    Prediction saturation, post-gain saturation and mix saturation keep their existing stop path.
    """
    if int(status or 0) >> INPUT_CLIP_BIT & 1:
        return "input_clip"
    if int(clip_word or 0) & 0xFFFF:      # prediction half only
        return "guard"
    if int(gain_word or 0) or int(mix_word or 0):
        return "guard"
    return None

# 阅读主线：参数检查→静音/配置→限时闭环→静音读RAM→恢复→本地保存。
# RATE来自自定义100MHz/2048分频，不是官方录音常见的48000 Hz。
RATE = 48828.125


def replay_trial(output_path, fixture_id, model_path, source_pcm16, bypass=False, zero_coeff=False,
                 gain_db=-36.0, seconds=0.5, hp_volume=40,
                 speaker_confirmed=False, local_capture_confirmed=False, before_start=None, direct_only=False,
                 reuse_overlay=False,
                 restore_stock=True):
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
    verify_paired_bitstream(bit)
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
    # Identity is resolved BEFORE anything can fail, so a capture-save failure still leaves a
    # complete version record next to the trial (C check: save failure must keep the identity).
    identity = dict(
        package_version="audio-replay-v3",
        driver_sha256=_file_sha256(__file__),
        bit_sha256=_file_sha256(bit),
        hwh_sha256=_file_sha256(bit.with_suffix(".hwh")),
        model_sha256=_file_sha256(model_path),
        # The checker is part of the identity: a capture verified by a different replay_tools is
        # not the same evidence (C 2026-10-27, "complete version hashes").
        replay_tools_sha256=_file_sha256(replay_tools.__file__),
        coefficients_sha256=hashlib.sha256(coefficients.astype("<i4").tobytes()).hexdigest(),
        source_pcm16_sha256=hashlib.sha256(source_pcm16.tobytes()).hexdigest(),
    )
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

    def check_pll(stage, expected_hex, actual_hex):
        """Same validation for load and restore: 6 bytes, first five match, PLLEN+LOCK set.

        The raw six-byte readback is always reported. Extra reserved bits are a note, not a pass and not
        a field mismatch. The written configuration is the specified value, never the observed bits.
        """
        actual = actual_hex.lower()
        if len(actual) != 12:
            raise RuntimeError("PLL_BAD_LENGTH stage=%s actual=%s" % (stage, actual_hex))
        first_five_ok = actual[:10] == expected_hex[:10].lower()
        last = int(actual[10:12], 16)
        if not first_five_ok or (last & 0x03) != 0x03:
            d = getattr(set_pll, "last", {})
            raise RuntimeError(
                "PLL_CONFIG_MISMATCH stage=%s expected=%s actual=%s first_five_ok=%s pll_enabled=%d "
                "pll_locked=%d clock_control=0x%02X elapsed=%.3fs"
                % (stage, expected_hex, actual_hex, first_five_ok, last & 1, (last >> 1) & 1,
                   d.get("clock_control_on", 0), d.get("elapsed_s", 0.0)))
        if actual != expected_hex.lower():
            print("PLL_CONFIG_NOTE stage=%s readback %s differs from %s only in reserved bits 0x%02X"
                  % (stage, actual_hex, expected_hex, last & ~0x03))
        return actual

    def set_pll(payload, stage="unknown"):
        started = time.monotonic()
        write_reg(0x4000, [0x0E])
        clock_off = read_reg(0x4000, 1)[0]
        write_reg(0x4002, bytes.fromhex(payload))
        deadline = started + 2
        value = read_reg(0x4002, 6)
        while not (value[5] & 2) and time.monotonic() < deadline:
            time.sleep(0.01)
            value = read_reg(0x4002, 6)
        elapsed = time.monotonic() - started
        if not (value[5] & 2):
            raise RuntimeError(
                "PLL_LOCK_TIMEOUT stage=%s requested=%s actual=%s pll_enabled=%d pll_locked=%d "
                "clock_control=0x%02X elapsed=%.3fs"
                % (stage, payload, value.hex(), value[5] & 1, (value[5] >> 1) & 1, clock_off, elapsed))
        write_reg(0x4000, [0x0F])
        set_pll.last = {"stage": stage, "requested": payload, "actual": value.hex(),
                        "clock_control_on": read_reg(0x4000, 1)[0], "elapsed_s": round(elapsed, 4)}
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
        global _OVERLAY_CACHE
        cached = _OVERLAY_CACHE.get("overlay")
        if reuse_overlay and cached is not None and _OVERLAY_CACHE.get("bit") == str(bit):
            overlay = cached
        else:
            overlay = Overlay(str(bit), download=True)
            _OVERLAY_CACHE["overlay"], _OVERLAY_CACHE["bit"] = overlay, str(bit)
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
        pll_readback = set_pll("000000002801", stage="load_50MHz").hex()
        check_pll("load_50MHz", "000000002803", pll_readback)
        # Trial copy: AUX input gain 0 dB (0x07 -> 0x05), other fields preserved; read back and record.
        for addr, value in ((0x400A, 1), (0x400B, 0x05), (0x400C, 1), (0x400D, 0x05)):
            write_reg(addr, [value])
        aux_readback = {addr: read_reg(addr, 1)[0] for addr in (0x400B, 0x400D)}
        if any((v & 0x07) != 0x05 for v in aux_readback.values()):
            raise RuntimeError("AUX_GAIN_MISMATCH expected 0x05, read %s"
                               % {hex(k): hex(v) for k, v in aux_readback.items()})
        print("AUX_INPUT_GAIN 0x400B=0x%02X 0x400D=0x%02X (0 dB)"
              % (aux_readback[0x400B], aux_readback[0x400D]))
        for addr in (0x40F2, 0x40F3, 0x40F5, 0x40F6):
            if read_reg(addr, 1) != b"\x01":
                raise RuntimeError("unexpected codec route/power at %04x" % addr)
        # Batch operator starts ONLY after configuration is ready, while still muted.
        if before_start is not None and before_start() is not True:
            raise RuntimeError("operator cancelled before audio start")
        hp = (hp_volume << 2) | 3
        for addr, value in ((0x401C, 0x21), (0x401E, 0x41), (0x4023, hp), (0x4024, hp)):
            write_reg(addr, [value])
        # Codec unmute produces an audible pop: on 2026-10-28 the operator heard a "du" from the
        # speaker and the microphone hit the ADC rail for a few milliseconds at the very first
        # frames, which trips the input-full-scale stop before any program material arrives.
        # Let the pop decay BEFORE the run starts, so the protection counters never latch on a
        # startup transient. This moves no threshold and relaxes nothing: the arm point moves, the
        # protection stays exactly as strict as before.
        time.sleep(CODEC_SETTLE_SECONDS)
        # Cancellation boundary (C 26685ac): the product may cancel during initialisation, before this
        # call unmutes and arms. Check right here, after the last unmute and immediately before the arm
        # write, so a cancelled request can never leave the loop armed.
        if before_start is not None and not before_start():
            raise RuntimeError("cancelled_before_start")
        start = time.monotonic()
        control.write(0, 1 | (int(bypass) << 1) | (gain_q12 << 16))
        armed = True
        deadline = start + budget / RATE + 2
        status = command.read(8)
        # Stop on config/protocol fault, on input full scale, on prediction/post-gain/mix
        # saturation. A pre-gain residual overflow alone never stops the run (see runtime_stop).
        while time.monotonic() < deadline:
            status = command.read(8)
            if status & (1 | (3 << 17)):
                break
            reason = runtime_stop(status, int(clips.read(0)), clips.read(8), source_len.read(8))
            if reason is not None:
                stop_reason = reason
                break
            time.sleep(0.002)
        # Stop the sound first, then freeze the capture and read every counter AFTER the run.
        control.write(0, 0)
        mute_codec()
        elapsed = time.monotonic() - start
        status = command.read(8)
        completed = runtime.read(8)
        clip_word, gain_word, mix_word = clips.read(0), clips.read(8), source_len.read(8)
        counts = decode_counts(clip_word, gain_word, mix_word)
        if stop_reason is None:
            # Re-check here as well: an input full-scale event in the last polling interval must
            # not be lost just because the loop exited on the deadline or on `done`.
            if int(status or 0) >> INPUT_CLIP_BIT & 1:
                stop_reason = "input_clip"
            elif status & (3 << 17):
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
        if not restore_stock:
            # prepared-capture mode: keep our bitstream and codec configuration resident
            if control is not None:
                cleanup_step("PL mute", lambda: control.write(0, 0))
            if fd is not None:
                cleanup_step("Codec mute", mute_codec)
                cleanup_step("I2C close", lambda: os.close(fd))
                fd = None
        else:
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
            # capture_status bit22 is the independent input full-scale sticky flag added with the
            # wide-residual change. It is the ONLY counter that can see an overloaded microphone
            # when the prediction is zero (the residual then equals the microphone and can never
            # overflow); the residual counter must not be used for that. A trial with this set is
            # rejected for field evidence rather than being allowed a quiet reinterpretation.
            input_full_scale_seen=bool(int(status or 0) >> 22 & 1),
            sound_seconds_nominal=budget / RATE, completion_poll_seconds=elapsed,
            prediction_saturations=counts[0], residual_saturations=counts[1],
            gain_saturations=counts[2], mix_saturations=counts[3],
            clip_counts_raw=[int(clip_word), int(gain_word), int(mix_word)],
            early_stop=bool(stop_reason is not None),
            stop_reason=(stop_reason or "completed"),
            source_frames=int(len(source_pcm16)),
            source_end_frame_exclusive=int(source_pcm16.shape[0]),
            source_schedule_verified=bool(source_loaded_ok),
            **identity,
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
        **identity,
        # The two v3 status facts a save failure must not swallow.
        capture_status=int(status or 0),
        input_full_scale_seen=bool(int(status or 0) >> INPUT_CLIP_BIT & 1),
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
        coefficient_status=int(coeff_status_word))
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
    if stop_reason == "input_clip":
        raise RuntimeError('input full scale (capture_status bit22) stopped playback; the microphone '
                           'hit the ADC rail, so this trial carries no usable input evidence; '
                           'reduce the level or move the source back and repeat')
    if error is not None:
        raise error
    if not recovery_ok:
        raise RuntimeError("restoration failed; do not run another audio test")
    return metadata


print("REPLAY_TRIAL_READY; import does not play; call replay_trial manually")
