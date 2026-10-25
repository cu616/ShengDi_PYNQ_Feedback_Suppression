"""Continuous live amplification run: one overlay load, one arm, operator stop, fail-safe mute.

Differences from replay_trial:
  * a single arm covers the whole run (no per-segment re-arm, no overlay reload);
  * the run state is polled into a timeline so protection events have a time stamp;
  * an operator stop file and SIGINT both disarm and mute, and the evidence is still saved;
  * any fault or saturation counter disarms, mutes, and records the reason.

The hardware bound is the PL parameter MAX_RUN_FRAMES (currently 488281 frames = 10.0 s).
Requests beyond that raise a clear error instead of silently truncating; the 60 s target
needs the contract change described in docs/contracts/audio-replay-v2-draft.md.
"""
import hashlib
import json
import math
import os
import signal
import time
from pathlib import Path

import numpy as np
from pynq import MMIO, Overlay

RATE = 48828.125
FRAMES = 16384
HARDWARE_TAPS = 512
PL_MAX_RUN_FRAMES = 3000000         # v2 contract ceiling; the actual limit is read from the HWH
PL_MAX_RUN_FRAMES_V1 = 488281       # v1 bitstreams reject anything larger
PLL_PAYLOAD = "000000002801"
PLL_EXPECTED = "000000002803"


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode_counts(packed, gain_word, mix_word):
    """prediction and residual share one 32-bit word as two 16-bit fields.

    gain and mix are each a full 32-bit counter and must NOT be masked to 16 bits.
    """
    return [int(packed) & 0xFFFF, (int(packed) >> 16) & 0xFFFF,
            int(gain_word) & 0xFFFFFFFF, int(mix_word) & 0xFFFFFFFF]


def pl_max_run_frames(hwh_path):
    """Read the MAX_RUN_FRAMES parameter of the bitstream that is actually configured."""
    try:
        blob = Path(hwh_path).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    marker = 'NAME="MAX_RUN_FRAMES" VALUE="'
    index = blob.find(marker)
    if index < 0:
        return None
    start = index + len(marker)
    end = blob.find('"', start)
    try:
        return int(blob[start:end])
    except ValueError:
        return None


def live_run(output_path, fixture_id, model_path, gain_db, seconds, hp_volume=40,
             bypass=False, zero_coeff=False, speaker_confirmed=False,
             local_capture_confirmed=False, stop_file='/home/xilinx/stop_run',
             poll_seconds=0.02, label='run'):
    """Run one continuous session and write <output_path> plus <stem>.status.json."""
    out = Path(output_path)
    if out.suffix != '.npz':
        raise ValueError('output_path must end in .npz')
    if out.exists():
        raise ValueError('choose a NEW .npz path in an existing board directory')
    if not out.parent.is_dir():
        raise ValueError('output directory does not exist')
    bit = out.parent / 'audio_replay.bit'
    hwh = out.parent / 'audio_replay.hwh'
    limit = pl_max_run_frames(hwh)
    if limit is None:
        raise ValueError('cannot read MAX_RUN_FRAMES from %s; refusing to guess the PL limit' % hwh)
    if not math.isfinite(seconds) or not 0.2 <= seconds <= limit / RATE:
        raise ValueError('seconds must be in 0.2..%.3f on this bitstream (MAX_RUN_FRAMES=%d); '
                         '%.1f s needs a v2 bitstream' % (limit / RATE, limit, seconds))
    frames_requested = int(seconds * RATE)
    if frames_requested > limit:
        raise ValueError('requested %d frames exceeds this bitstream limit %d'
                         % (frames_requested, limit))
    gain_q12 = int(math.floor(4096 * 10 ** (gain_db / 20) + 0.5))
    if not 0 <= gain_q12 <= 32768:
        raise ValueError('gain out of range')

    model = json.loads(Path(model_path).read_text(encoding='utf-8'))
    q = np.asarray(model['coefficients_q20'], dtype=np.int64)
    if q.ndim != 1 or len(q) == 0 or len(q) > HARDWARE_TAPS:
        raise ValueError('model taps must be 1..%d' % HARDWARE_TAPS)
    logical_taps = int(len(q))
    coefficients = np.zeros(HARDWARE_TAPS, dtype=np.int64)
    coefficients[:logical_taps] = q
    if zero_coeff:
        coefficients[:] = 0

    source_word = 1 << 17          # one silent frame: the mixer becomes a pure feedback loop
    bit = out.parent / 'audio_replay.bit'
    hwh = out.parent / 'audio_replay.hwh'

    state = dict(
        driver_evidence_version='a-continuous-v1', mode='continuous',
        fixture_id=fixture_id, label=label, bypass=bool(bypass), zero_coeff=bool(zero_coeff),
        gain_db=float(gain_db), gain_q12=int(gain_q12), hp_volume=int(hp_volume),
        sample_rate_hz=RATE, frames_requested=int(frames_requested),
        seconds_requested=float(seconds), pl_max_run_frames=int(limit),
        pl_contract=('v2' if int(limit) > PL_MAX_RUN_FRAMES_V1 else 'v1'),
        model_file=Path(model_path).name, model_sha256=_sha256(model_path),
        logical_taps=logical_taps, loaded_taps=HARDWARE_TAPS,
        coefficients_sha256=hashlib.sha256(
            coefficients.astype('<i4').tobytes()).hexdigest(),
        bit_sha256=_sha256(bit) if bit.is_file() else None,
        hwh_sha256=_sha256(hwh) if hwh.is_file() else None,
        speaker_confirmed=bool(speaker_confirmed),
        local_capture_confirmed=bool(local_capture_confirmed),
        stop_file=stop_file, poll_seconds=float(poll_seconds),
        timeline=[], stop_reason=None, muted=None, recovered=None,
        cleanup_errors=[], salvage_errors=[])

    fd = None
    control = None
    armed = False
    completed = 0
    counts = [0, 0, 0, 0]
    raw = None
    status_word = 0
    interruption = {'raised': False}

    def _on_signal(signum, frame):
        interruption['raised'] = True
        state.setdefault('signals', []).append(int(signum))

    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[sig] = signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            pass

    def write_reg(addr, data):
        payload = addr.to_bytes(2, 'big') + bytes(data)
        if os.write(fd, payload) != len(payload):
            raise IOError('short I2C write')

    def read_reg(addr, count):
        if os.write(fd, addr.to_bytes(2, 'big')) != 2:
            raise IOError('short I2C address write')
        value = os.read(fd, count)
        if len(value) != count:
            raise IOError('short I2C read')
        return value

    def mute_codec():
        for addr, value in ((0x401C, 0), (0x401E, 0), (0x4023, 0xE5), (0x4024, 0xE5)):
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
            raise RuntimeError('Codec PLL lock timeout')
        write_reg(0x4000, [0x0F])
        return value

    def read_ring(first_index, frame_count):
        block = np.empty((frame_count, 4), dtype=np.int64)
        for i in range(frame_count):
            address = (first_index + i) % FRAMES
            command.write(0, address)
            command.read(0)
            block[i, 0] = samples.read(0) & 0xFFFFFF
            block[i, 1] = samples.read(8) & 0xFFFFFF
            command.write(0, (1 << 16) | address)
            command.read(0)
            block[i, 2] = samples.read(0) & 0xFFFFFF
            block[i, 3] = samples.read(8) & 0xFFFFFF
        block[block >= 0x800000] -= 0x1000000
        return block

    def cleanup(name, action):
        try:
            action()
        except Exception as exc:
            state['cleanup_errors'].append('%s: %s' % (name, str(exc)))

    def disarm_and_mute():
        """Stop the sound; every step is attempted even if a preceding one fails.

        Returns (disarm_ok, mute_ok). Neither is assumed: a failure is recorded and the
        caller must not report muted/recovered when the step did not succeed.
        """
        t0 = time.monotonic()
        disarm_ok = False
        mute_ok = False
        if control is not None:
            try:
                control.write(0, 0)
                disarm_ok = True
            except Exception as exc:
                state['cleanup_errors'].append('PL disarm: %s' % exc)
        state['t_disarm_ok'] = round(time.monotonic() - t0, 4)
        t1 = time.monotonic()
        if fd is not None:
            try:
                mute_codec()
                mute_ok = True
            except Exception as exc:
                state['cleanup_errors'].append('Codec mute: %s' % exc)
        state['t_mute_ok'] = round(time.monotonic() - t1, 4)
        return disarm_ok, mute_ok

    import fcntl
    try:
        fd = os.open('/dev/i2c-1', os.O_RDWR)
        fcntl.ioctl(fd, 0x0703, 0x3B)
        mute_codec()
        overlay = Overlay(str(bit), download=True)
        control = MMIO(overlay.ip_dict['audio_control']['phys_addr'], 0x1000)
        samples = MMIO(overlay.ip_dict['audio_samples']['phys_addr'], 0x1000)
        command = MMIO(overlay.ip_dict['audio_calibrate_cmd']['phys_addr'], 0x1000)
        control.write(0, 0)
        control.write(4, 0)
        command.write(0, 0)
        command.write(4, 0)
        source = MMIO(overlay.ip_dict['audio_source']['phys_addr'], 0x1000)
        source_len = MMIO(overlay.ip_dict['audio_source_length']['phys_addr'], 0x1000)
        if source.read(8) >> 24 != 0x52:
            raise RuntimeError('replay ABI mismatch')
        source.write(4, 0)
        source_len.write(4, 0)
        source_len.write(0, 1)
        source.write(0, source_word)
        source.read(8)
        # one silent frame: the loader accepts a word per toggle of bit16, bit17 stays set
        source_word = ((source_word ^ (1 << 16)) & 0x30000) | 0
        source.write(0, source_word)
        loaded = source.read(8)
        if (loaded & 0x3FFFF) != 1 or loaded & (1 << 18) or not loaded & (1 << 19):
            raise RuntimeError('source load incomplete: %08x' % loaded)
        coeff = MMIO(overlay.ip_dict['audio_coefficients']['phys_addr'], 0x1000)
        coeff.write(0, 0)
        coeff.write(4, 0)
        coeff_word = 1 << 25
        coeff.write(0, coeff_word)
        for value in coefficients:
            if not (coeff.read(8) & 1):
                raise RuntimeError('coefficient loader not ready')
            coeff_word = ((coeff_word ^ (1 << 24)) & 0x03000000) | (int(value) & 0xFFFFFF)
            coeff.write(0, coeff_word)
        coeff_status = coeff.read(8)
        state['coefficient_status'] = int(coeff_status)
        if ((coeff_status >> 4) & 0xFFFF) != HARDWARE_TAPS or (coeff_status & 0xE) != 0xA:
            raise RuntimeError('coefficient load rejected: %08x' % coeff_status)
        runtime = MMIO(overlay.ip_dict['audio_runtime']['phys_addr'], 0x1000)
        clips = MMIO(overlay.ip_dict['audio_clips']['phys_addr'], 0x1000)
        runtime.write(4, 0)
        runtime.write(0, frames_requested)
        pll_readback = set_pll(PLL_PAYLOAD).hex()
        if pll_readback != PLL_EXPECTED:
            raise RuntimeError('unexpected 50 MHz PLL readback')
        for addr, value in ((0x400A, 1), (0x400B, 7), (0x400C, 1), (0x400D, 7)):
            write_reg(addr, [value])
        for addr in (0x40F2, 0x40F3, 0x40F5, 0x40F6):
            if read_reg(addr, 1) != b'\x01':
                raise RuntimeError('unexpected codec route/power at %04x' % addr)

        if os.path.exists(stop_file):
            os.remove(stop_file)
        hp = (int(hp_volume) << 2) | 3
        for addr, value in ((0x401C, 0x21), (0x401E, 0x41), (0x4023, hp), (0x4024, hp)):
            write_reg(addr, [value])

        start = time.monotonic()
        control.write(0, 1 | (int(bypass) << 1) | (int(gain_q12) << 16))
        armed = True
        state['t_arm'] = start
        next_sample = start
        last_completed = -1
        while True:
            status_word = int(command.read(8))
            completed = int(runtime.read(8))
            word, gain_word, mix_word = int(clips.read(0)), int(clips.read(8)), int(source_len.read(8))
            counts = decode_counts(word, gain_word, mix_word)
            now = time.monotonic()
            if state.get('_last_loop') is not None:
                gap = now - state['_last_loop']
                if gap > state.get('max_poll_gap_s', 0.0):
                    state['max_poll_gap_s'] = round(gap, 4)
            state['_last_loop'] = now
            if now >= next_sample or completed != last_completed:
                state['timeline'].append([round(now - start, 3), completed,
                                          status_word, counts[0], counts[1], counts[2], counts[3]])
                next_sample = now + max(poll_seconds, 0.005)
                last_completed = completed
            if status_word & (1 | (3 << 17)):
                state['stop_reason'] = 'completed' if status_word & 1 else 'fault'
                break
            if any(counts):
                state['stop_reason'] = 'saturation'
                break
            if interruption['raised']:
                state['stop_reason'] = 'operator_signal'
                state['t_stop_request'] = round(now - start, 4)
                state['t_stop_detected'] = round(now - start, 4)
                break
            if stop_file and os.path.exists(stop_file):
                state['stop_reason'] = 'operator_stop_file'
                state['t_stop_request'] = round(now - start, 4)
                state['t_stop_detected'] = round(now - start, 4)
                break
            if now - start > seconds + 5:
                state['stop_reason'] = 'timeout'
                break
            time.sleep(max(poll_seconds, 0.002))

        disarm_ok, mute_ok = disarm_and_mute()
        state['t_cleanup_done'] = round(time.monotonic() - start, 4)
        state['disarm_ok'] = bool(disarm_ok)
        state['mute_ok'] = bool(mute_ok)
        state['muted'] = bool(mute_ok)
        if state.get('t_stop_request') is not None and state.get('t_disarm_ok') is not None:
            state['stop_latency_s'] = round(
                (state['t_cleanup_done'] - state['t_stop_request']), 4)
        elapsed = time.monotonic() - start
        state['elapsed_s'] = round(elapsed, 3)
        status_word = int(command.read(8))
        completed = int(runtime.read(8))
        word, gain_word, mix_word = int(clips.read(0)), int(clips.read(8)), int(source_len.read(8))
        counts = decode_counts(word, gain_word, mix_word)
        # a protection event is a fact even when the run also reached its frame count
        if any(counts) and state['stop_reason'] == 'completed':
            state['stop_reason'] = 'completed_with_protection'
        count = min(FRAMES, completed)
        first = completed - count
        raw = read_ring(first, count) if count > 0 else None
        state['first_frame'] = int(first)
        state['frames_completed'] = int(completed)
        state['status'] = int(status_word)
    except BaseException as exc:
        state['error'] = '%s: %s' % (type(exc).__name__, str(exc))
        if state['stop_reason'] is None:
            state['stop_reason'] = 'exception'
        if armed:
            disarm_ok, mute_ok = disarm_and_mute()
            state['disarm_ok'] = bool(disarm_ok)
            state['mute_ok'] = bool(mute_ok)
            state['muted'] = bool(mute_ok)
            try:
                status_word = int(command.read(8))
                completed = int(runtime.read(8))
                word, gain_word, mix_word = (int(clips.read(0)), int(clips.read(8)),
                                            int(source_len.read(8)))
                counts = decode_counts(word, gain_word, mix_word)
                count = min(FRAMES, completed)
                raw = read_ring(completed - count, count) if count > 0 else None
                state['frames_completed'] = int(completed)
                state['status'] = int(status_word)
            except Exception as exc2:
                state['salvage_errors'].append(str(exc2))
    finally:
        disarm_and_mute()
        if fd is not None:
            cleanup('close i2c', lambda: os.close(fd))
        for sig, handler in previous.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass

    state['status_decoded'] = dict(
        done=bool(int(state.get('status', 0)) & 1),
        config_rejected=bool(int(state.get('status', 0)) & (1 << 17)),
        fault=bool(int(state.get('status', 0)) & (1 << 18)),
        prediction_clip_seen=bool(int(state.get('status', 0)) & (1 << 19)),
        residual_clip_seen=bool(int(state.get('status', 0)) & (1 << 20)),
        gain_clip_seen=bool(int(state.get('status', 0)) & (1 << 21)))
    state['counts'] = dict(prediction=counts[0], residual=counts[1],
                           gain=counts[2], mix=counts[3])
    state['recovered'] = (bool(state.get('disarm_ok')) and bool(state.get('mute_ok'))
                          and (int(state.get('status', 0)) & (3 << 17)) == 0)

    if raw is not None:
        scale = float(2 ** 23)
        # Same channel mapping as the C-accepted replay_trial: page0-left = played (reference),
        # page0-right = microphone. Swapping these two was the live_run bug found on 2026-10-25.
        np.savez_compressed(
            out,
            microphone=raw[:, 1] / scale, reference=raw[:, 0] / scale,
            prediction_pcm=raw[:, 2].astype(np.int64), residual_pcm=raw[:, 3].astype(np.int64),
            metadata_json=np.array(json.dumps(state, ensure_ascii=False)))
        state['capture'] = str(out)
    side = out.with_suffix('.status.json')
    side.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    state['status_file'] = str(side)
    return state
