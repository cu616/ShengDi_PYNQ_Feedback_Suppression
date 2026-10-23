"""Live amplification entry: external speech -> microphone -> PL -> speaker.

Why this exists: the replay driver runs ONE bounded trial and reloads the bitstream for
every call, which is useless for speaking into the microphone. This module loads the
overlay once, loads the model once, then runs several back-to-back windows so a person
can talk and the audience hears the speaker.

Path: the PL already implements it. With a one-frame silent source the mixer becomes
    played[n] = gain(residual[n-2]),  residual = mic - Hhat*played   (bypass=False)
    played[n] = gain(mic[n-2])                                        (bypass=True)
i.e. bypass is plain public-address gain and cancel is the same gain with feedback
cancellation. Both modes share gain, limiter and the two-frame schedule.

Import defines functions only; nothing plays until live_pa() is called.
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

FRAMES = 16384
RATE = 48828.125
MAX_RUN_SECONDS = 9.5      # PL frame_limit ceiling is 488281 frames
CODEC_ADDRESS = 0x3B


def live_pa(fixture_id, model_path, bypass=False, gain_db=-12.0, seconds=8.0, bursts=3,
            gap_seconds=0.25, hp_volume=40, speaker_confirmed=False,
            local_capture_confirmed=False, output_dir=None, stop_on_saturation=True,
            before_burst=None, label="live"):
    """Speak into the microphone while this runs; the speaker reproduces it.

    seconds is per window (PL allows at most 9.5 s per run); bursts windows run back to
    back with a short gap. During the gap the codec is muted, so expect a tiny click.
    """
    if speaker_confirmed is not True or local_capture_confirmed is not True:
        raise ValueError("confirm speaker setup and local storage; remove headphones")
    if type(bypass) is not bool:
        raise ValueError("bypass must be bool")
    if not isinstance(bursts, int) or not 1 <= bursts <= 20:
        raise ValueError("bursts must be 1..20")
    if not 1.0 <= seconds <= MAX_RUN_SECONDS:
        raise ValueError("seconds must be 1.0..9.5")
    if not 10 <= hp_volume <= 40:
        raise ValueError("hp_volume must be 10..40 and match calibration")
    gain_q12, budget = trial_parameters(gain_db, seconds)
    source_frames = 1                      # silent single frame; keeps config_ok true
    if budget < source_frames + 2:
        raise ValueError("window too short for the source schedule")

    model, coefficients = load_candidate(model_path, fixture_id, hp_volume, RATE)
    bit = Path(__file__).resolve().with_name("audio_replay.bit")
    if not bit.is_file() or not bit.with_suffix(".hwh").is_file():
        raise FileNotFoundError("matching bit/hwh required")
    if output_dir is not None:
        output_dir = Path(output_dir)
        if not output_dir.is_dir():
            raise ValueError("output_dir must be an existing board directory")

    fd, control = None, None
    cleanup_errors = []
    results = []

    def write_reg(addr, data):
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

    def unmute_codec():
        hp = (hp_volume << 2) | 3
        for addr, value in ((0x401C, 0x21), (0x401E, 0x41), (0x4023, hp), (0x4024, hp)):
            write_reg(addr, [value])

    def set_pll(payload):
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

    def read_ring(command, samples, runtime, first, count):
        raw = np.empty((count, 4), dtype=np.int64)
        for i in range(count):
            address = (first + i) % FRAMES
            command.write(0, address)
            command.read(0)
            raw[i, 0] = samples.read(0) & 0xFFFFFF
            raw[i, 1] = samples.read(8) & 0xFFFFFF
            command.write(0, (1 << 16) | address)
            command.read(0)
            raw[i, 2] = samples.read(0) & 0xFFFFFF
            raw[i, 3] = samples.read(8) & 0xFFFFFF
        raw[raw >= 0x800000] -= 0x1000000
        return raw

    try:
        fd = os.open("/dev/i2c-1", os.O_RDWR)
        fcntl.ioctl(fd, 0x0703, CODEC_ADDRESS)
        mute_codec()
        overlay = Overlay(str(bit), download=True)
        control = MMIO(overlay.ip_dict["audio_control"]["phys_addr"], 0x1000)
        samples = MMIO(overlay.ip_dict["audio_samples"]["phys_addr"], 0x1000)
        command = MMIO(overlay.ip_dict["audio_calibrate_cmd"]["phys_addr"], 0x1000)
        source = MMIO(overlay.ip_dict["audio_source"]["phys_addr"], 0x1000)
        source_len = MMIO(overlay.ip_dict["audio_source_length"]["phys_addr"], 0x1000)
        coeff = MMIO(overlay.ip_dict["audio_coefficients"]["phys_addr"], 0x1000)
        runtime = MMIO(overlay.ip_dict["audio_runtime"]["phys_addr"], 0x1000)
        clips = MMIO(overlay.ip_dict["audio_clips"]["phys_addr"], 0x1000)
        for mmio in (control, command, source, coeff, runtime):
            mmio.write(0, 0)
            mmio.write(4, 0)
        if source.read(8) >> 24 != 0x52:
            raise RuntimeError("replay ABI mismatch")

        # one silent frame so the source schedule stays valid
        source_len.write(0, source_frames)
        source_word = 1 << 17
        source.write(0, source_word)
        source.read(8)
        source_word = ((source_word ^ (1 << 16)) & 0x30000) | 0
        source.write(0, source_word)
        loaded = source.read(8)
        if (loaded & 0x3FFFF) != source_frames:
            raise RuntimeError("source load incomplete: %08x" % loaded)

        coeff_word = 1 << 25
        coeff.write(0, coeff_word)
        for value in coefficients:
            if not (coeff.read(8) & 1):
                raise RuntimeError("coefficient loader not ready")
            coeff_word = ((coeff_word ^ (1 << 24)) & 0x03000000) | (int(value) & 0xFFFFFF)
            coeff.write(0, coeff_word)
        coeff_status = coeff.read(8)
        if ((coeff_status >> 4) & 0xFFFF) != len(coefficients) or (coeff_status & 0xE) != 0xA:
            raise RuntimeError("coefficient load rejected: %08x" % coeff_status)

        pll_readback = set_pll("000000002801").hex()
        if pll_readback != "000000002803":
            raise RuntimeError("unexpected 50 MHz PLL readback")
        for addr, value in ((0x400A, 1), (0x400B, 7), (0x400C, 1), (0x400D, 7)):
            write_reg(addr, [value])
        for addr in (0x40F2, 0x40F3, 0x40F5, 0x40F6):
            if read_reg(addr, 1) != b"\x01":
                raise RuntimeError("unexpected codec route/power at %04x" % addr)

        control_word = 1 | (int(bypass) << 1) | (gain_q12 << 16)
        for index in range(1, bursts + 1):
            if before_burst is not None and before_burst(index) is not True:
                break
            runtime.write(0, budget)
            mute_codec()
            time.sleep(0.05)
            unmute_codec()
            control.write(0, control_word)
            started = time.monotonic()
            deadline = started + budget / RATE + 2.0
            status = command.read(8)
            tripped = False
            while not (status & (1 | (3 << 17))) and time.monotonic() < deadline:
                counts = (clips.read(0), clips.read(8))
                if stop_on_saturation and any(counts):
                    tripped = True
                    break
                time.sleep(0.002)
                status = command.read(8)
            control.write(0, 0)
            mute_codec()
            elapsed = time.monotonic() - started
            status_after = command.read(8)
            completed = runtime.read(8)
            clip_word, gain_clips = clips.read(0), clips.read(8)
            count = min(FRAMES, completed)
            first = completed - count
            raw = read_ring(command, samples, runtime, first, count) if count else None

            entry = dict(burst=index, bypass=bypass, gain_q12=gain_q12,
                         gain_db=float(20 * np.log10(gain_q12 / 4096)) if gain_q12 else None,
                         seconds=seconds, elapsed_s=round(elapsed, 3),
                         completed_frames=completed, frames=count, first_frame=first,
                         status="%08x" % status, status_after="%08x" % status_after,
                         guard_tripped=tripped,
                         prediction_saturations=int(clip_word & 0xFFFF),
                         residual_saturations=int(clip_word >> 16),
                         gain_saturations=int(gain_clips))
            if raw is not None and count >= 512:
                mic = raw[:, 1] / 2 ** 23
                entry["mic_rms_dbfs"] = float(20 * np.log10(max(float(np.std(mic)), 2 ** -23)))
                entry["mic_peak_dbfs"] = float(20 * np.log10(max(float(np.max(np.abs(mic))), 2 ** -23)))
                if output_dir is not None:
                    meta = dict(schema_version=1, artifact_kind="live_pa", capture_id=str(uuid.uuid4()),
                                fixture_id=fixture_id, bypass=bypass, gain_q12=gain_q12,
                                hp_volume=hp_volume, sample_rate_hz=RATE, burst=index,
                                model_sha256=hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
                                bit_sha256=hashlib.sha256(bit.read_bytes()).hexdigest(),
                                interpretation="live microphone-to-speaker window; NOT MSG/ASG")
                    meta.update({k: entry[k] for k in
                                 ("completed_frames", "frames", "first_frame", "guard_tripped",
                                  "prediction_saturations", "residual_saturations",
                                  "mic_rms_dbfs", "mic_peak_dbfs")})
                    path = output_dir / ("%s_%02d_b%s_g%s.npz" % (
                        label, index, "1" if bypass else "0", gain_q12))
                    with path.open("xb") as stream:
                        np.savez_compressed(stream, reference=raw[:, 0] / 2 ** 23,
                                            microphone=raw[:, 1] / 2 ** 23,
                                            prediction_pcm=raw[:, 2], residual_pcm=raw[:, 3],
                                            coefficients_q20=coefficients,
                                            sample_rate_hz=RATE,
                                            metadata_json=json.dumps(meta))
                    entry["capture"] = str(path)
            results.append(entry)
            print(json.dumps(entry, ensure_ascii=False), flush=True)
            if tripped and stop_on_saturation:
                print("GUARD_TRIPPED_STOPPING", flush=True)
                break
            if index < bursts:
                time.sleep(gap_seconds)
    finally:
        if control is not None:
            cleanup_step("PL mute", lambda: control.write(0, 0))
        if fd is not None:
            cleanup_step("Codec mute", mute_codec)
        cleanup_step("stock overlay", lambda: BaseOverlay("base.bit"))
        try:
            if fd is None:
                fd = os.open("/dev/i2c-1", os.O_RDWR)
                fcntl.ioctl(fd, 0x0703, CODEC_ADDRESS)
            restored = set_pll("0271023c2101")
            mute_codec()
            if restored.hex() != "0271023c2103":
                raise RuntimeError("unexpected stock PLL readback")
            print("STOCK_PLL_READBACK", restored.hex())
        except Exception as exc:
            cleanup_errors.append("stock PLL/mute: " + str(exc))
        finally:
            if fd is not None:
                cleanup_step("I2C close", lambda: os.close(fd))
                fd = None
        if cleanup_errors:
            print("RESTORE_ERRORS", cleanup_errors)
        else:
            print("STOCK_BASE_RESTORED_AND_CODEC_MUTED")
    if cleanup_errors:
        raise RuntimeError("restoration failed; do not run another audio test")
    summary = dict(fixture_id=fixture_id, bypass=bypass, gain_db=gain_db, bursts=len(results),
                   model=Path(model_path).name, bit_sha256=hashlib.sha256(bit.read_bytes()).hexdigest(),
                   windows=results)
    return summary


print("LIVE_PA_READY; import does not play; call live_pa manually")
