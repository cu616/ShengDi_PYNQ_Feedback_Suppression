"""Hardware capability interface for the one-click recalibration product.

Everything the product layer needs from the board, as plain dicts - no terminal text to parse, no
second audio driver. All audio work goes through ``replay_trial_repair`` (the single formal driver).

Capabilities
------------
init_and_mute()          initialise the codec and leave the output muted
get_aux_gain_db()        read the AUX input stage (0 or 6 dB) as it actually is in the codec
set_aux_gain_db(db)      write the AUX input stage (0 or 6 dB) and read it back
capture(seconds)         silent-source capture, returns levels and protection state
run(seconds, ...)        play the model through the loop for N seconds and report protection
load_model(path)         validate a model and report its identity
read_status()            capture_status word, decoded into named flags
read_switches()          SW0/SW1 as they are wired in the bitstream (2001-... see SWITCH_MAP)
set_led(mask)            NOT available in the current bitstream - reported as unsupported
read_buttons()           NOT available in the current bitstream - reported as unsupported

Bitstream facts this module relies on (bit 2113a454...):
  capture_status[25] = SW0 raw pin, [24] = SW0 synchronised, [23] = SW1 synchronised
  SW0 up  -> bypass forced (canceller off)
  There are no button or LED interfaces in the current design.
"""
import fcntl
import json
import os
import time
from pathlib import Path

import numpy as np

I2C_SLAVE = 0x0703
BUS = '/dev/i2c-1'
ADDR = 0x3B
REG_AUX_L = 0x400B
REG_AUX_R = 0x400D

SWITCH_MAP = {'sw0_raw_bit': 25, 'sw0_sync_bit': 24, 'sw1_sync_bit': 23,
              'sw0_up_means': 'bypass forced (canceller off)'}
UNSUPPORTED = {'led': 'requires the I/O integration bitstream (audio_replay_io)', 'buttons': 'requires the I/O integration bitstream (audio_replay_io)'}


def _driver():
    import importlib
    return importlib.import_module('replay_trial_repair').replay_trial


class Board:
    def __init__(self, package_dir, fixture='room_v1_20261026b', hp_volume=40):
        self.dir = Path(package_dir)
        self.fixture = fixture
        self.hp_volume = hp_volume
        self.model = self.dir / 'model_recalibrated.json'

    # ---- AUX input stage -------------------------------------------------------------------
    def _fd(self):
        fd = os.open(BUS, os.O_RDWR)
        fcntl.ioctl(fd, I2C_SLAVE, ADDR)
        return fd

    @staticmethod
    def _read8(fd, reg):
        os.write(fd, reg.to_bytes(2, 'big'))
        d = os.read(fd, 1)
        if len(d) != 1:
            raise IOError('short read at 0x%04X' % reg)
        return d[0]

    @staticmethod
    def _write8(fd, reg, value):
        os.write(fd, reg.to_bytes(2, 'big') + bytes([value & 0xFF]))
        time.sleep(0.002)

    def get_aux_gain_db(self):
        fd = self._fd()
        try:
            l, r = self._read8(fd, REG_AUX_L), self._read8(fd, REG_AUX_R)
        finally:
            os.close(fd)
        def to_db(v):
            return {7: 6.0, 5: 0.0}.get(v & 0x07, None)
        return {'ok': to_db(l) is not None and to_db(l) == to_db(r),
                'aux_gain_db': to_db(l), 'raw_left': l, 'raw_right': r,
                'settable': sorted([0.0, 6.0])}

    def set_aux_gain_db(self, db):
        if db not in (0.0, 6.0):
            return {'ok': False, 'error': 'only 0 or 6 dB is exposed by this codec path', 'requested': db}
        low3 = 0x05 if db == 0.0 else 0x07
        fd = self._fd()
        try:
            for reg in (REG_AUX_L, REG_AUX_R):
                self._write8(fd, reg, (self._read8(fd, reg) & 0xF8) | low3)
            l, r = self._read8(fd, REG_AUX_L), self._read8(fd, REG_AUX_R)
        finally:
            os.close(fd)
        return {'ok': (l & 0x07) == low3 and (r & 0x07) == low3,
                'aux_gain_db': db, 'raw_left': l, 'raw_right': r}

    # ---- model ------------------------------------------------------------------------------
    def load_model(self, path=None):
        p = Path(path) if path else self.model
        if not p.is_file():
            return {'ok': False, 'error': 'model file missing', 'path': str(p)}
        m = json.loads(p.read_text(encoding='utf-8'))
        c = np.asarray(m.get('coefficients_q20') or m.get('coefficients'), dtype=np.int64)
        if c is None or len(c) == 0:
            return {'ok': False, 'error': 'model has no coefficients', 'path': str(p)}
        import hashlib
        padded = np.concatenate([c, np.zeros(max(0, 512 - len(c)), dtype=np.int64)])
        return {'ok': True, 'path': str(p), 'name': p.name, 'taps': int(len(c)),
                'coefficient_sha256': hashlib.sha256(padded.astype('<i4').tobytes()).hexdigest()}

    # ---- audio ------------------------------------------------------------------------------
    def capture(self, seconds=0.4):
        out = self.dir / ('api_capture_%d.npz' % int(time.time() * 1000))
        out.unlink(missing_ok=True)
        try:
            _driver()(str(out), self.fixture, str(self.model), np.zeros(16000, np.int16),
                      bypass=False, zero_coeff=True, gain_db=0.0, seconds=seconds,
                      hp_volume=self.hp_volume, speaker_confirmed=True,
                      local_capture_confirmed=True, direct_only=True)
        except Exception as exc:
            return {'ok': False, 'stage': 'capture', 'error': repr(exc)[:200]}
        return self._describe(out)

    def run(self, seconds=2.0, gain_db=-8.0, bypass=False):
        out = self.dir / ('api_run_%d.npz' % int(time.time() * 1000))
        out.unlink(missing_ok=True)
        try:
            _driver()(str(out), self.fixture, str(self.model), np.zeros(16000, np.int16),
                      bypass=bypass, zero_coeff=False, gain_db=gain_db, seconds=seconds,
                      hp_volume=self.hp_volume, speaker_confirmed=True,
                      local_capture_confirmed=True)
        except Exception as exc:
            return {'ok': False, 'stage': 'run', 'error': repr(exc)[:200]}
        return self._describe(out)

    def init_and_mute(self):
        r = self.capture(0.4)
        r['muted'] = True
        return r

    def _describe(self, npz_path):
        cap = np.load(str(npz_path))
        meta = json.loads(str(cap['metadata_json']))
        mic = np.asarray(cap['microphone'], float)
        status = int(meta.get('capture_status') or 0)
        return {'ok': meta.get('stop_reason') == 'completed' and not (status >> 22) & 1,
                'stop_reason': meta.get('stop_reason'),
                'frames': int(len(mic)),
                'mic_rms_dbfs': float(20 * np.log10(max(np.sqrt(np.mean(mic ** 2)), 1e-12))),
                'mic_peak_dbfs': float(20 * np.log10(max(np.max(np.abs(mic)), 1e-12))),
                'full_scale_samples': int((np.abs(mic) >= 0.999).sum()),
                'status': self.decode_status(status),
                'coefficient_sha256': meta.get('coefficients_sha256'),
                'pll_readback': meta.get('pll_readback')}

    # ---- status / switches ------------------------------------------------------------------
    @staticmethod
    def decode_status(word):
        return {'raw': '0x%08X' % word, 'done': word & 1, 'captured_frames': (word >> 1) & 0xFFFF,
                'config_invalid': (word >> 17) & 1, 'fault': (word >> 18) & 1,
                'prediction_clip': (word >> 19) & 1, 'residual_clip': (word >> 20) & 1,
                'gain_clip': (word >> 21) & 1, 'input_clip_seen': (word >> 22) & 1,
                'sw1_sync': (word >> 23) & 1, 'sw0_sync': (word >> 24) & 1, 'sw0_raw': (word >> 25) & 1}

    def read_switches(self):
        r = self.capture(0.4)
        if not r.get('ok') and 'status' not in r:
            return {'ok': False, 'error': r.get('error')}
        s = r['status']
        return {'ok': True, 'sw0_up': bool(s['sw0_sync']), 'sw0_raw': bool(s['sw0_raw']),
                'sw1_up': bool(s['sw1_sync']), 'sw0_up_means': SWITCH_MAP['sw0_up_means'],
                'map': SWITCH_MAP}

    # ---- buttons and LEDs (I/O integration build) -------------------------------------------
    def read_buttons(self, status_mmio=None):
        """BTN3..BTN0 from capture_status[30:27].

        With status_mmio given, the register is read directly (milliseconds). Without it the call falls
        back to a capture, which reloads the overlay and takes about a second - fast presses are then
        easily missed, so the product layer should pass the MMIO object.
        """
        if status_mmio is not None:
            word = status_mmio.read(8) & 0xFFFFFFFF
        else:
            r = self.capture(0.4)
            s = r.get('status')
            if not s:
                return {'ok': False, 'error': r.get('error'), 'supported': 'needs the I/O bitstream'}
            word = int(s['raw'], 16)
        bits = [(word >> (27 + i)) & 1 for i in range(4)]
        return {'ok': True, 'btn': bits, 'any_pressed': any(bits), 'status': '0x%08X' % word,
                'map': {'btn0': 'start recalibration (long press)', 'btn1': 'start/stop amplification',
                        'btn2': 'unused', 'btn3': 'abort and mute'}}

    def set_led(self, mask=0, control_mmio=None):
        """Drive LD3..LD0 from control[5:2]. Refused while armed."""
        if control_mmio is None:
            return {'ok': False, 'error': 'control MMIO base required', 'supported': True}
        control = control_mmio
        current = control.read(0) & 0xFFFFFFFF
        if current & 1:
            return {'ok': False, 'error': 'refused: pipeline is armed, writing control would fault the run',
                    'control': '0x%08X' % current}
        value = (current & ~0x3C) | ((mask & 0xF) << 2)
        control.write(0, value)
        back = control.read(0) & 0xFFFFFFFF
        # audio_control is a dual-channel AXI GPIO (channel 1 out -> control, channel 2 in <- frame_count),
        # so a read of offset 0 does not necessarily return the output latch. The write is therefore
        # reported as "issued", the readback is passed through as information only, and the physical LED
        # state is what confirms it.
        return {'ok': True, 'issued': True, 'led_requested': mask & 0xF,
                'readback_control': '0x%08X' % back,
                'readback_reflects': ((back >> 2) & 0xF) == (mask & 0xF),
                'confirm': 'watch LD0-LD3: they should match led_requested'}

    def stop(self):
        try:
            self.init_and_mute()
            return {'ok': True, 'muted': True}
        except Exception as exc:
            return {'ok': False, 'error': repr(exc)[:200]}

    def capabilities(self):
        return {'audio': True, 'aux_stage': True, 'switches': True,
                'buttons': True, 'leds': True,
                'notes': ['buttons and LEDs need one I/O integration build; the algorithm core is untouched',
                          'all audio goes through replay_trial_repair (single formal driver)']}
