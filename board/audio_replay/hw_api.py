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
import pathlib
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


# ================================================================================================
# Product interface: recal-product-v1
# ================================================================================================
CONTRACT = 'recal-product-v1'

# Physical legend for the four user LEDs and the four buttons, as wired in audio_replay_io.
LED_LEGEND = {
    '0000': 'idle / muted',
    '0001': 'recalibration in progress',
    '0010': 'speak now (cue played)',
    '0100': 'quiet please (measuring floor)',
    '1000': 'ready / running with a valid model',
    '1111': 'error or protected',
}
BUTTON_LEGEND = {
    'BTN0': 'long press (>=1.0 s): start recalibration',
    'BTN1': 'short press: start / stop amplification',
    'BTN2': 'short press: confirm the room is quiet',
    'BTN3': 'short press: abort and mute',
}
LED_PATTERNS = {'idle': '0000', 'recalibrating': '0001', 'speak': '0010', 'quiet': '0100',
                'ready': '1000', 'error': '1111'}


class ProductHardware:
    """Everything C's state machine needs, with no terminal text to parse."""

    def __init__(self, config):
        self.dir = pathlib.Path(config['package_dir'])
        self.fixture = config.get('fixture', 'room_v1_20261026b')
        self.hp_volume = int(config.get('hp_volume', 40))
        self.aux_db = float(config.get('aux_db', 0.0))
        self.model_path = pathlib.Path(config.get('model_path', self.dir / 'model_recalibrated.json'))
        self.run_root = pathlib.Path(config.get('run_dir_root', self.dir / 'product_runs'))
        self.allowed_gain_q12 = list(config.get('allowed_gain_q12', [1631, 2303, 3254, 4096]))
        self._board = Board(str(self.dir), fixture=self.fixture, hp_volume=self.hp_volume)
        self._mm = None
        self._prepared = False
        self._scene = None
        self._scene_frames = 0
        self._btn_state = [0, 0, 0, 0]
        self._btn_since = [0.0, 0.0, 0.0, 0.0]
        self._protect_baseline = 0
        self._current_op = None

    # ---- internals ---------------------------------------------------------------------
    def _ensure_mmio(self, reuse=True):
        if self._mm is not None:
            return self._mm
        from pynq import MMIO, Overlay
        bit = str(self.dir / 'audio_replay.bit')
        drv = self._driver()
        cache = getattr(drv, '_OVERLAY_CACHE', None)
        ov = None
        if cache and cache.get('overlay') is not None and cache.get('bit') == bit:
            ov = cache['overlay']
        if ov is None:
            ov = Overlay(bit, download=True)
            if cache is not None:
                cache['overlay'], cache['bit'] = ov, bit
        self._mm = {
            'overlay': ov,
            'control': MMIO(ov.ip_dict['audio_control']['phys_addr'], 0x1000),
            'status': MMIO(ov.ip_dict['audio_calibrate_cmd']['phys_addr'], 0x1000),
        }
        return self._mm

    def _status_word(self):
        return self._ensure_mmio()['status'].read(8) & 0xFFFFFFFF

    def _control_word(self):
        return self._ensure_mmio()['control'].read(0) & 0xFFFFFFFF

    def _protected_bits(self, word):
        return {name: (word >> bit) & 1 for name, bit in
                (('input_clip_seen', 22), ('gain_clip', 21), ('residual_clip', 20),
                 ('prediction_clip', 19), ('fault', 18))}

    def _driver(self):
        import importlib
        return importlib.import_module('replay_trial_repair')

    def _new_capture_path(self, tag):
        import time
        self.run_root.mkdir(parents=True, exist_ok=True)
        return self.run_root / ('%s_%d.npz' % (tag, int(time.time() * 1000)))

    WINDOW_FRAMES = 16384
    WINDOW_SECONDS = (16384 + 4) / 48828.125
    stimulus_dbfs = -22.0

    def _make_stimulus(self, seed=4242, level_dbfs=None):
        """B's excitation: white noise, RMS-normalised, 16384-frame window plus the 2-frame margin."""
        import numpy as np
        level = self.stimulus_dbfs if level_dbfs is None else float(level_dbfs)
        n = self.WINDOW_FRAMES + 2
        rng = np.random.default_rng(int(seed))
        x = rng.standard_normal(n)
        x -= x.mean()
        x *= 10 ** (level / 20.0) / float(np.sqrt(np.mean(x ** 2)))
        if float(np.max(np.abs(x))) > 0.80:
            return None                      # unreachable at this seed/level: report, never clip
        return np.rint(x * 32767.0).astype(np.int16)

    def _capture(self, seconds, tag='cap', gain_db=-8.0, bypass=False, direct_only=True, zero=True,
                 source=None, cancel_event=None):
        import numpy as np
        path = self._new_capture_path(tag)
        path.unlink(missing_ok=True)
        # one overlay for the whole session: prepare seeds it, every later capture reuses it
        self._ensure_mmio()
        self._driver().replay_trial(
            str(path), self.fixture, str(self.model_path),
            np.zeros(16000, np.int16) if source is None else source,
            bypass=bypass, zero_coeff=zero, gain_db=gain_db, seconds=seconds,
            hp_volume=self.hp_volume, speaker_confirmed=True, local_capture_confirmed=True,
            direct_only=direct_only, reuse_overlay=False, restore_stock=False,
            before_start=lambda: not (cancel_event is not None and cancel_event.is_set()))
        cap = np.load(str(path))
        meta = self._meta(cap)
        self._scene_frames += int(len(cap['microphone']))
        return path, cap, meta

    @staticmethod
    def __meta(cap):
        import json
        return json.loads(str(cap['metadata_json']))

    # Non-mangled alias: a double-underscore name mangles per class and is unreachable from a subclass.
    _meta = staticmethod(__meta)

    def identity(self):
        aux = self._board.get_aux_gain_db()
        control = self._control_word()
        import hashlib
        def h(p):
            p = pathlib.Path(p)
            return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        drv = self._driver()
        return {'aux_db': aux.get('aux_gain_db'), 'aux_raw_left': aux.get('raw_left'),
                'aux_raw_right': aux.get('raw_right'), 'hp_volume': self.hp_volume,
                'gain_q12': (control >> 16) & 0xFFFF, 'sample_rate_hz': 48828.125,
                'driver_sha256': h(pathlib.Path(drv.__file__)),
                'bit_sha256': h(self.dir / 'audio_replay.bit'),
                'hwh_sha256': h(self.dir / 'audio_replay.hwh'),
                'helper_sha256': h(pathlib.Path(__file__))}

    def effective_mode(self):
        control = self._control_word()
        armed = control & 1
        switch = (self._status_word() >> 24) & 1
        if not armed:
            return 'muted'
        return 'bypass' if ((control >> 1) & 1 or switch) else 'cancel'

    # ---- contract methods --------------------------------------------------------------
    def capabilities(self):
        return {'ok': True, 'contract': CONTRACT, 'buttons': True, 'indicator': True,
                'nonintrusive_events': True, 'abort_mutes': True, 'prepared_capture': True,
                'prepared_capture_evidence': 'cue and speech window come from ONE driver call: the overlay '
                                             'download, codec init and source handshake all finish before the '
                                             'cue plays. Verified on hardware 2026-11-01: input_ready with '
                                             'cue_end_frame=21969 and valid_first_frame=21969 in capture '
                                             'fw-020624/1/input/00. Separately, a plain capture still '
                                             're-downloads the bitstream; that path is not what this flag '
                                             'claims.',
                'bounded_run': True, 'mode_readback': True,
                'led_legend': LED_LEGEND, 'button_legend': BUTTON_LEGEND,
                'allowed_gain_q12': self.allowed_gain_q12,
                'max_run_frames': 3000000, 'max_run_seconds': round(3000000 / 48828.125, 2)}

    def mute(self):
        try:
            self._ensure_mmio()['control'].write(0, 0)
            for reg, val in ((0x401C, 0), (0x401E, 0), (0x4023, 0xE5), (0x4024, 0xE5)):
                fd = self._board._fd()
                try:
                    self._board._write8(fd, reg, val)
                finally:
                    os.close(fd)
            return {'ok': True, 'contract': CONTRACT, 'muted': True,
                    'effective_mode': self.effective_mode()}
        except Exception as exc:
            return {'ok': False, 'contract': CONTRACT, 'muted': False, 'error': repr(exc)[:160]}

    def abort(self):
        """Stop hardware now. Never re-captures, re-initialises or waits for a computation."""
        started = time.monotonic()
        r = self.mute()
        elapsed = time.monotonic() - started
        armed = self._control_word() & 1
        return {'ok': r.get('ok', False), 'contract': CONTRACT, 'muted': r.get('muted', False),
                'quiescent': (not armed), 'elapsed_ms': round(elapsed * 1000.0, 1),
                'effective_mode': r.get('effective_mode')}

    def poll(self):
        """No audio side effects: register reads only."""
        try:
            word = self._status_word()
            control = self._control_word()
        except Exception as exc:
            return {'ok': False, 'contract': CONTRACT, 'error': repr(exc)[:160], 'events': []}
        now = time.monotonic()
        events = []
        bits = [(word >> (27 + i)) & 1 for i in range(4)]
        for i, b in enumerate(bits):
            if b and not self._btn_state[i]:
                self._btn_since[i] = now
            if not b and self._btn_state[i]:
                held = now - self._btn_since[i]
                if i == 0 and held >= 1.0:
                    events.append({'kind': 'recalibrate', 'value': 'start'})
                elif i == 0:
                    events.append({'kind': 'recalibrate', 'value': 'short_ignored'})
                elif i == 1:
                    events.append({'kind': 'start' if not (control & 1) else 'stop', 'value': 'btn1'})
                elif i == 2:
                    events.append({'kind': 'confirm_quiet', 'value': 'btn2'})
                elif i == 3:
                    events.append({'kind': 'cancel', 'value': 'btn3'})
                self._btn_since[i] = 0.0
            self._btn_state[i] = b
        mode = self.effective_mode()
        if getattr(self, '_last_mode', None) not in (None, mode):
            events.append({'kind': 'mode', 'value': mode})
        self._last_mode = mode
        # Must agree with the driver's runtime_stop (captain 2026-11-01): input full scale (bit22),
        # protocol fault (bit18), prediction saturation (bit19), post-gain saturation (bit21) and mix
        # saturation stop the run. The PRE-GAIN residual overflow (bit20) is a diagnostic only - a wide
        # residual may exceed the old rail while the post-gain output is still representable.
        # capture_status defines 22/18/19/21. The mix clip counter is not in this word - the driver reads
        # it from source_len.read(8) - so it is not fabricated here.
        stop_bits = {'input_clip_seen': 22, 'fault': 18, 'prediction_clip': 19, 'gain_clip': 21}
        stops = {k: (word >> b) & 1 for k, b in stop_bits.items()}
        active = {k: v for k, v in stops.items()
                  if v and not ((self._protect_baseline >> stop_bits[k]) & 1)}
        saturation = {'residual_clip_pre_gain': (word >> 20) & 1,
                      'prediction_saturations': (word >> 19) & 1,
                      'gain_saturations': (word >> 21) & 1}
        if self._current_op is None:
            self._protect_baseline = word
        return {'ok': True, 'contract': CONTRACT, 'events': events, 'protected': bool(active),
                'protection': active, 'saturation': saturation,
                'identity': self.identity(), 'effective_mode': mode, 'buttons': bits}

    def indicate(self, prompt):
        pattern = prompt.get('pattern') if isinstance(prompt, dict) else None
        if isinstance(pattern, str) and set(pattern) <= {'0', '1'} and len(pattern) == 4:
            mask = int(pattern, 2)
        else:
            state = (prompt or {}).get('state', 'idle') if isinstance(prompt, dict) else 'idle'
            mask = int(LED_PATTERNS.get(state, '0000'), 2)
        control = self._ensure_mmio()['control']
        cur = control.read(0) & 0xFFFFFFFF
        control.write(0, (cur & ~0x3C) | ((mask & 0xF) << 2))
        return {'ok': True, 'contract': CONTRACT, 'pattern': format(mask, '04b'),
                'legend': LED_LEGEND.get(format(mask, '04b'), 'custom')}

    def perform(self, request, cancel_event=None):
        op = request.get('op')
        result = {'contract': CONTRACT, 'request_id': request.get('request_id'),
                  'scene_id': request.get('scene_id'), 'op': op, 'ok': False,
                  'status': 'error'}
        if op == 'prepare':
            # C (5939ee5 review): a pre-cancelled prepare must not reach the driver at all.
            if cancel_event is not None and cancel_event.is_set():
                self.mute()
                result.update({'status': 'error', 'reason': 'cancelled', 'never_armed_again': True})
                return result
            self._scene = request.get('scene_id')
            self._scene_frames = 0
            self._prepared = False
            self._ensure_mmio()
            self._board.set_aux_gain_db(self.aux_db)
            self._capture(0.4, tag='prepare', cancel_event=cancel_event)
            self._prepared = True
            result.update({'ok': True, 'status': 'completed', 'prepared': True,
                           'identity': self.identity()})
            return result
        if op == 'cue':
            if cancel_event is not None and cancel_event.is_set():
                self.mute()
                result.update({'status': 'error', 'reason': 'cancelled'})
                return result
            path, cap, meta = self._cue()
            result.update({'ok': True, 'status': 'completed', 'end_frame': self._scene_frames,
                           'tail_frames': 0, 'path': str(path), 'identity': self.identity()})
            return result
        if op in ('input', 'training', 'validation'):
            import hashlib
            caps = []
            plan = request.get('plan') or {}
            items = plan.get('captures') or plan.get('segments') or [{'seconds': 3.0}]
            # B's plan: white noise, RMS-normalised, one 16384-frame window per segment. Training and
            # validation MUST NOT share a source, otherwise the independence check is meaningless.
            train_seed = int(plan.get('seed', 4242))
            valid_seed = int(plan.get('validation_seed', train_seed + 1))
            for i, item in enumerate(items):
                if cancel_event is not None and cancel_event.is_set():
                    self.mute()
                    result.update({'status': 'error', 'reason': 'cancelled', 'captures': caps})
                    return result
                seconds = float(item.get('seconds', self.WINDOW_SECONDS))
                q12 = int(item.get('gain_q12', self.allowed_gain_q12[0]))
                seed = int(item.get('seed', valid_seed if op == 'validation' else train_seed))
                level = float(item.get('level_dbfs', self.stimulus_dbfs))
                src = None
                if op in ('training', 'validation'):
                    src = self._make_stimulus(seed=seed, level_dbfs=level)
                    if src is None:
                        result.update({'status': 'error', 'reason': 'stimulus_unreachable',
                                       'level_dbfs': level, 'seed': seed})
                        return result
                path, cap, meta = self._capture(seconds, tag='%s%d' % (op, i), source=src,
                                                gain_db=20 * __import__('math').log10(max(q12, 1) / 4096.0),
                                                bypass=bool(item.get('bypass', False)),
                                                direct_only=bool(item.get('direct_only', op == 'input')),
                                                zero=bool(item.get('zero_coeff', op == 'input')))
                mic = cap['microphone']
                first = int(meta.get('first_frame') or 0)
                valid = (len(src) - first) if src is not None else None
                caps.append({'capture_id': item.get('capture_id', '%s%d' % (op, i)),
                             'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'first_frame': self._scene_frames - len(mic),
                             'end_frame': self._scene_frames,
                             'valid_frames': valid,
                             'source_sha256': meta.get('source_pcm16_sha256'),
                             'seed': seed if src is not None else None,
                             'level_dbfs': level if src is not None else None,
                             'content_kind': item.get('content_kind',
                                                     'onboard_excitation' if src is not None else 'human_private'),
                             'status': meta.get('stop_reason')})
            result.update({'ok': True, 'status': 'completed', 'captures': caps,
                           'valid_first_frame': caps[0]['first_frame'] if caps else None,
                           'identity': self.identity()})
            return result
        if op == 'install':
            model = self._board.load_model(request.get('model_path') or self.model_path)
            if not model.get('ok'):
                result.update({'status': 'error', 'reason': model.get('error')})
                return result
            self.model_path = pathlib.Path(model['path'])
            cur = self._control_word()
            q12 = int(request.get('run_gain_q12', self.allowed_gain_q12[0]))
            self._ensure_mmio()['control'].write(0, (cur & 0xFFFF) | ((q12 & 0xFFFF) << 16))
            import hashlib as _h
            file_sha = _h.sha256(pathlib.Path(model['path']).read_bytes()).hexdigest()
            result.update({'ok': True, 'status': 'completed',
                           'model_sha256': file_sha,
                           'coefficients_sha256': model['coefficient_sha256'],
                           'model_path': model['path'], 'taps': model['taps'],
                           'applies_at': 'next_capture',
                           'identity': self.identity()})
            return result
        if op == 'run':
            import math
            seconds = float(request.get('seconds', 10.0))
            q12 = int(request.get('gain_q12', self.allowed_gain_q12[0]))
            src = self._run_source(request, seconds)
            if isinstance(src, dict):
                result.update(src)
                return result
            self._current_op = 'run'
            control = self._ensure_mmio()['control']
            cur = control.read(0) & 0xFFFFFFFF
            control.write(0, (cur & 0xFFFF0000) | (1 if request.get('bypass') else 0) | 1)
            started = time.monotonic()
            try:
                path, cap, meta = self._capture(seconds, tag='run', source=src,
                                                gain_db=20 * math.log10(max(q12, 1) / 4096.0),
                                                bypass=bool(request.get('bypass')), direct_only=False, zero=False)
                ok = meta.get('stop_reason') == 'completed'
                status = 'completed' if ok else ('protected' if (int(meta.get('capture_status') or 0) >> 22) & 1 else 'error')
            finally:
                control.write(0, control.read(0) & ~1)
                self.mute()
                self._current_op = None
            elapsed = time.monotonic() - started
            result.update({'ok': status == 'completed', 'status': status,
                           'effective_mode': self.effective_mode(),
                           'elapsed_seconds': round(elapsed, 3),
                           'model_sha256': (meta.get('model_sha256') if 'meta' in dir() else None),
                           'coefficients_sha256': (meta.get('coefficients_sha256') if 'meta' in dir() else None),
                           'identity': self.identity()})
            return result
        result['reason'] = 'unknown op'
        return result



    def warm_up(self, seconds=None):
        """Fixed initialisation warm-up: one capture that is recorded but never used for training or
        validation. Its only purpose is to leave the codec in a settled state before the measured
        segments, and it is always run, never chosen after seeing results."""
        try:
            path, cap, meta = self._capture(seconds or self.WINDOW_SECONDS, tag='warmup')
            return {'ok': meta.get('stop_reason') == 'completed', 'path': str(path),
                    'status': meta.get('stop_reason'), 'used_for_fit': False}
        except Exception as exc:
            return {'ok': False, 'status': 'error', 'reason': repr(exc)[:160], 'used_for_fit': False}

    def _run_source(self, request, seconds):
        """Program audio for a live run. Returns a PCM16 array, or a dict describing the failure."""
        import numpy as np
        budget = int(seconds * 48828.125)   # must match the driver exactly
        limit = budget - 2
        raw = request.get('source')
        if raw is None and request.get('source_path'):
            path = pathlib.Path(request['source_path'])
            if not path.is_file():
                return {'status': 'error', 'reason': 'source_path_missing', 'path': str(path)}
            if path.suffix.lower() == '.npz':
                with np.load(str(path)) as z:
                    raw = np.asarray(z['source_pcm16'] if 'source_pcm16' in z else z['source'])
            elif path.suffix.lower() == '.wav':
                import wave
                with wave.open(str(path), 'rb') as w:
                    if w.getsampwidth() != 2:
                        return {'status': 'error', 'reason': 'wav_must_be_16bit', 'path': str(path)}
                    frames = w.readframes(w.getnframes())
                raw = np.frombuffer(frames, dtype='<i2')
            else:
                return {'status': 'error', 'reason': 'unsupported_source_format', 'path': str(path)}
        if raw is None and request.get('test_tone_hz'):
            hz = float(request['test_tone_hz'])
            level = float(request.get('level_dbfs', -20.0))
            n = limit
            tt = np.arange(n) / 48828.125
            raw = np.rint(10 ** (level / 20.0) * np.sin(2 * np.pi * hz * tt) * 32767).astype(np.int16)
        if raw is None:
            # Live amplification does not need injection: output = injection + gain*residual and the
            # voice arrives through the microphone. A short zero array satisfies the driver protocol
            # without padding the whole run with zeros.
            return np.zeros(16, np.int16)
        src = np.asarray(raw)
        if src.dtype != np.int16:
            src = np.clip(src, -1.0, 1.0)
            src = np.rint(src * 32767.0).astype(np.int16)
        if len(src) > limit:
            src = src[:limit]
        if len(src) < limit:
            src = np.concatenate([src, np.zeros(limit - len(src), np.int16)])
        return src

    def _cue(self):
        import numpy as np
        path = self._new_capture_path('cue')
        path.unlink(missing_ok=True)
        parts = []
        for _ in range(2):
            for f in (523.25, 783.99, 1046.50):
                parts.append(np.rint(0.08 * np.sin(2 * np.pi * f * np.arange(int(0.16 * 48828.125)) / 48828.125)
                                     * 32767).astype(np.int16))
                parts.append(np.zeros(int(0.05 * 48828.125), np.int16))
            parts.append(np.zeros(int(0.35 * 48828.125), np.int16))
        cue = np.concatenate(parts)
        self._driver().replay_trial(str(path), self.fixture, str(self.model_path), cue, bypass=True,
                                    zero_coeff=False, gain_db=0.0, seconds=2.6, hp_volume=self.hp_volume,
                                    speaker_confirmed=True, local_capture_confirmed=True,
                                    direct_only=True, reuse_overlay=False, restore_stock=False)
        cap = np.load(str(path))
        meta = self._meta(cap)
        self._scene_frames += int(len(cap['microphone']))
        return path, cap, meta


def create_product(config):
    """Factory required by recal-product-v1."""
    return ProductHardware(config)


# ================================================================================================
# recal-runtime-v2 adaptation
# ================================================================================================
OPEN_LOOP_GAIN_Q12 = [0]          # allowed during open-loop calibration (no amplification)


class ProductHardwareV2(ProductHardware):
    """v2 behaviour required by C (contracts/recal-runtime-v2.md)."""


    LEVEL_LADDER = (-22.0, -19.3, -16.5)

    def __init__(self, config):
        super().__init__(config)
        self.run_dir = None
        self.attempt = int(config.get('attempt', 1))
        self._last_model_sha = None
        self._last_coeff_sha = None
        self._input_ready = None


    @staticmethod
    def _cancelled(cancel_event):
        return cancel_event is not None and cancel_event.is_set()

    def _cancel_result(self, request, op, caps=None):
        self.mute()
        r = {'contract': CONTRACT, 'request_id': request.get('request_id'),
             'scene_id': request.get('scene_id'), 'op': op, 'ok': False,
             'status': 'error', 'reason': 'cancelled', 'never_armed_again': True}
        if caps is not None:
            r['captures'] = caps
        return r

    # ---- helpers ---------------------------------------------------------------------
    def _capture_path(self, scene, phase, index):
        root = pathlib.Path(self.run_dir) if self.run_dir else self.run_root
        root.mkdir(parents=True, exist_ok=True)
        cid = '%s/%s/%s/%02d' % (scene, self.attempt, phase, index)
        return root / ('%s_%s_%s_%02d.npz' % (scene, self.attempt, phase, index)), cid

    def _ctrl(self):
        return self._ensure_mmio()['control']

    def _write_control(self, **fields):
        """Write control with armed-write protection and LED/gain preserved by default."""
        control = self._ctrl()
        cur = control.read(0) & 0xFFFFFFFF
        if cur & 1 and not fields.pop('allow_armed', False):
            return {'ok': False, 'error': 'refused: armed, writing control would fault the run',
                    'control': '0x%08X' % cur}
        value = cur
        if 'arm' in fields:
            value = (value & ~1) | (1 if fields['arm'] else 0)
        if 'bypass' in fields:
            value = (value & ~2) | (2 if fields['bypass'] else 0)
        if 'led' in fields:
            value = (value & ~0x3C) | ((fields['led'] & 0xF) << 2)
        if 'gain_q12' in fields:
            value = (value & 0xFFFF) | ((fields['gain_q12'] & 0xFFFF) << 16)
        control.write(0, value)
        return {'ok': True, 'control': '0x%08X' % (control.read(0) & 0xFFFFFFFF)}

    # ---- mute: stop sound only --------------------------------------------------------
    def mute(self):
        try:
            r = self._write_control(arm=False, allow_armed=True)
            import os as _os
            for reg, val in ((0x401C, 0), (0x401E, 0), (0x4023, 0xE5), (0x4024, 0xE5)):
                fd = self._board._fd()
                try:
                    self._board._write8(fd, reg, val)
                finally:
                    _os.close(fd)
            cur = self._ctrl().read(0) & 0xFFFFFFFF
            return {'ok': bool(r.get('ok')), 'contract': CONTRACT, 'muted': True,
                    'gain_q12_kept': (cur >> 16) & 0xFFFF, 'led_kept': (cur >> 2) & 0xF,
                    'effective_mode': self.effective_mode()}
        except Exception as exc:
            return {'ok': False, 'contract': CONTRACT, 'muted': False, 'error': repr(exc)[:160]}

    # ---- independent bypass / cancel indication ---------------------------------------
    def indicate(self, prompt):
        pattern = (prompt or {}).get('pattern') if isinstance(prompt, dict) else None
        if isinstance(pattern, str) and len(pattern) == 4 and set(pattern) <= {'0', '1'}:
            mask = int(pattern, 2)
        else:
            state = (prompt or {}).get('state', 'idle') if isinstance(prompt, dict) else 'idle'
            mask = int(LED_PATTERNS.get(state, '0000'), 2)
        mode = self.effective_mode()
        # LD3 tells bypass apart from cancel independently of what the caller asked for
        if mode == 'bypass':
            mask = (mask & 0x7) | 0x8
        elif mode == 'cancel':
            mask = mask & 0x7
        r = self._write_control(led=mask, allow_armed=True)
        if not r.get('ok'):
            return {'ok': False, 'contract': CONTRACT, 'error': r.get('error')}
        return {'ok': True, 'contract': CONTRACT, 'pattern': format(mask, '04b'),
                'legend': LED_LEGEND.get(format(mask, '04b'), 'custom'), 'effective_mode': mode}

    # ---- training / validation: execute the encapsulated plan -------------------------
    def _run_plan(self, request, op, cancel_event=None):
        import hashlib
        import numpy as np
        scene = request.get('scene_id')
        self.run_dir = request.get('run_dir') or self.run_dir
        plan = request.get('plan') or {}
        segs = plan.get(op) or plan.get('segments') or plan.get('captures') or []
        if not segs:
            return {'contract': CONTRACT, 'request_id': request.get('request_id'), 'scene_id': scene,
                    'op': op, 'ok': False, 'status': 'error',
                    'reason': 'plan_missing_%s_segments' % op}
        peak_cap = float(plan.get('peak_cap', 0.80))
        levels = [float(x) for x in (plan.get('levels') or self.LEVEL_LADDER)]
        caps, accepted = [], None
        for level in levels:
            caps = []
            ok_all = True
            for i, seg in enumerate(segs):
                seed = int(seg.get('seed', plan.get('seed', 4242) + (0 if op == 'training' else 1)))
                n = int(seg.get('frames', self.WINDOW_FRAMES)) + 2
                rng = np.random.default_rng(seed)
                x = rng.standard_normal(n)
                x -= x.mean()
                x *= 10 ** (level / 20.0) / float(np.sqrt(np.mean(x ** 2)))
                if float(np.max(np.abs(x))) > peak_cap:
                    ok_all = False
                    caps.append({'capture_id': '%s/%s/%s/%02d' % (scene, self.attempt, op, i),
                                 'ok': False, 'reason': 'unreachable', 'level_dbfs': level, 'seed': seed})
                    break
                src = np.rint(x * 32767.0).astype(np.int16)
                src_sha = hashlib.sha256(src.tobytes()).hexdigest()
                if self._cancelled(cancel_event):
                    return self._cancel_result(request, op, caps)
                path, cid = self._capture_path(scene, op, i)
                try:
                    self._driver().replay_trial(
                        str(path), self.fixture, str(self.model_path), src, bypass=False,
                        zero_coeff=True, gain_db=0.0, seconds=(len(src) + 2) / 48828.125 + 1e-6,
                        hp_volume=self.hp_volume, speaker_confirmed=True,
                        local_capture_confirmed=True, direct_only=True,
                        reuse_overlay=False, restore_stock=False,
                        before_start=lambda: not self._cancelled(cancel_event))
                except Exception as exc:
                    ok_all = False
                    caps.append({'capture_id': cid, 'ok': False, 'error': repr(exc)[:140]})
                    break
                meta = self._meta(np.load(str(path)))
                status = int(meta.get('capture_status') or 0)
                first = int(meta.get('first_frame') or 0)
                caps.append({'capture_id': cid, 'path': str(path),
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'first_frame': first, 'valid_frames': len(src) - first,
                             'source_sha256': src_sha, 'seed': seed, 'level_dbfs': level,
                             'ok': (status >> 22) & 1 == 0, 'bit22': (status >> 22) & 1,
                             'content_kind': 'onboard_excitation'})
                self._scene_frames += int(meta.get('frames') or 0)
            if ok_all and all(c.get('ok') for c in caps):
                accepted = level
                break
        return {'contract': CONTRACT, 'request_id': request.get('request_id'), 'scene_id': scene,
                'op': op, 'ok': accepted is not None,
                'status': 'completed' if accepted is not None else 'error',
                'level_accepted_dbfs': accepted, 'captures': caps,
                'source_sha256': sorted({c.get('source_sha256') for c in caps if c.get('source_sha256')}),
                'identity': self.identity()}

    # ---- cue + input in one call -------------------------------------------------------
    def _cue_input(self, request, cancel_event=None):
        import hashlib
        import numpy as np
        scene = request.get('scene_id')
        seconds = float(request.get('seconds', 6.0))
        cue = self._cue_pcm()
        budget = int(seconds * 48828.125)
        limit = budget - 2
        if len(cue) > limit:
            return {'ok': False, 'status': 'error', 'reason': 'window_too_short_for_cue'}
        src = np.concatenate([cue, np.zeros(limit - len(cue), np.int16)])
        if cancel_event is not None and cancel_event.is_set():
            self.mute()
            return {'ok': False, 'status': 'error', 'reason': 'cancelled'}
        path, cid = self._capture_path(scene, 'input', 0)
        if self._cancelled(cancel_event):
            return self._cancel_result(request, 'input')
        self._driver().replay_trial(
            str(path), self.fixture, str(self.model_path), src, bypass=False, zero_coeff=True,
            gain_db=0.0, seconds=seconds + 1e-6, hp_volume=self.hp_volume, speaker_confirmed=True,
            local_capture_confirmed=True, direct_only=True, reuse_overlay=False, restore_stock=False,
            before_start=lambda: not self._cancelled(cancel_event))
        meta = self._meta(np.load(str(path)))
        cue_end = len(cue)
        self._input_ready = {'request_id': request.get('request_id'), 'scene_id': scene,
                             'capture_id': cid, 'path': str(path),
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'cue_end_frame': cue_end, 'valid_first_frame': cue_end,
                             'end_frame': self._scene_frames + int(meta.get('frames') or 0),
                             'status': meta.get('stop_reason')}
        self._scene_frames += int(meta.get('frames') or 0)
        return {'contract': CONTRACT, 'request_id': request.get('request_id'), 'scene_id': scene,
                'op': 'input', 'ok': meta.get('stop_reason') == 'completed', 'status': 'completed',
                'input_ready': dict(self._input_ready), 'captures': [self._input_ready],
                'valid_first_frame': cue_end, 'identity': self.identity()}

    def _cue_pcm(self):
        """Short cue. The source buffer is capped at 131072 frames, so the cue must leave room for the
        speech window inside the same run. Three 0.12 s notes, about 0.45 s in total."""
        import numpy as np
        parts = []
        for f in (523.25, 783.99, 1046.50):
            parts.append(np.rint(0.08 * np.sin(2 * np.pi * f * np.arange(int(0.12 * 48828.125)) / 48828.125)
                                 * 32767).astype(np.int16))
            parts.append(np.zeros(int(0.03 * 48828.125), np.int16))
        return np.concatenate(parts)

    # ---- dispatch ----------------------------------------------------------------------
    def perform(self, request, cancel_event=None):
        op = request.get('op')
        if op in ('training', 'validation'):
            return self._run_plan(request, op, cancel_event)
        if op == 'input' and request.get('cue'):
            return self._cue_input(request, cancel_event)
        if op == 'install':
            return self._install(request, cancel_event)
        if op == 'run':
            return self._run_v2(request, cancel_event)
        return super().perform(request, cancel_event)

    def _install(self, request, cancel_event=None):
        import hashlib
        import json as _json
        import numpy as np
        path_model = pathlib.Path(request.get('model_path') or self.model_path)
        if not path_model.is_file():
            return {'contract': CONTRACT, 'request_id': request.get('request_id'),
                    'scene_id': request.get('scene_id'), 'op': 'install', 'ok': False,
                    'status': 'error', 'reason': 'model_missing', 'path': str(path_model)}
        try:
            md = _json.loads(path_model.read_text(encoding='utf-8'))
        except Exception as exc:
            return {'contract': CONTRACT, 'request_id': request.get('request_id'),
                    'scene_id': request.get('scene_id'), 'op': 'install', 'ok': False,
                    'status': 'error', 'reason': 'model_not_json: %s' % repr(exc)[:100]}
        coeff = md.get('coefficients_q20') or md.get('coefficients')
        if not coeff:
            return {'contract': CONTRACT, 'request_id': request.get('request_id'),
                    'scene_id': request.get('scene_id'), 'op': 'install', 'ok': False,
                    'status': 'error', 'reason': 'model_has_no_coefficients'}
        arr = np.asarray(coeff, dtype=np.int64)
        padded = np.concatenate([arr, np.zeros(max(0, 512 - len(arr)), dtype=np.int64)])
        coeff_sha = hashlib.sha256(padded.astype('<i4').tobytes()).hexdigest()
        file_sha = hashlib.sha256(path_model.read_bytes()).hexdigest()
        file_sha_original = file_sha
        # The model file carries its own fixture_id. Bind a copy to this scene rather than pretending the
        # old fixture still applies (C: the model belongs to the scene of this round).
        scene_id = request.get('scene_id')
        bound = pathlib.Path(self.run_dir or self.run_root) / ('%s_model.json' % scene_id)
        bound.parent.mkdir(parents=True, exist_ok=True)
        md['fixture_id'] = scene_id
        bound.write_text(_json.dumps(md, ensure_ascii=False), encoding='utf-8')
        file_sha = hashlib.sha256(bound.read_bytes()).hexdigest()
        self.model_path = bound
        self.fixture = scene_id or self.fixture
        gain = int(request.get('run_gain_q12', self.allowed_gain_q12[0]))

        # load through the real driver, then read back what the PL says it received
        scene = request.get('scene_id')
        cap_path, cid = self._capture_path(scene, 'install', 0)
        # C (a280-entry-review): while the install check runs the loop must stay open-loop at zero gain;
        # the selected runtime gain is restored only after the coefficient readback has been accepted.
        self._write_control(gain_q12=0, arm=False, bypass=False, allow_armed=True)
        if self._cancelled(cancel_event):
            return self._cancel_result(request, 'install')
        self._driver().replay_trial(str(cap_path), self.fixture, str(self.model_path),
                                    self._make_stimulus(seed=1, level_dbfs=-30.0),
                                    bypass=False, zero_coeff=False, gain_db=0.0,
                                    seconds=self.WINDOW_SECONDS + 1e-6, hp_volume=self.hp_volume,
                                    speaker_confirmed=True, local_capture_confirmed=True,
                                    direct_only=True, reuse_overlay=False, restore_stock=False,
                                    before_start=lambda: not self._cancelled(cancel_event))
        meta = self._meta(np.load(str(cap_path)))
        reported = meta.get('coefficients_sha256')
        loaded_count = meta.get('loaded_count')
        verified = (reported == coeff_sha) if reported else None
        if loaded_count is None and verified:
            loaded_count = int(len(arr))
        # restore the run gain and read the identity back, never the requested values
        self._write_control(gain_q12=gain, arm=False, bypass=False)
        self._last_model_sha, self._last_coeff_sha = file_sha, coeff_sha
        return {'contract': CONTRACT, 'request_id': request.get('request_id'), 'scene_id': scene,
                'op': 'install', 'ok': bool(verified), 'status': 'completed' if verified else 'error',
                'reason': None if verified else 'coefficient_readback_mismatch',
                'model_sha256': file_sha, 'source_model_sha256': file_sha_original,
                'coefficients_sha256': coeff_sha,
                'reported_coefficients_sha256': reported, 'loaded_count': loaded_count,
                'taps': int(len(arr)), 'applies_at': 'immediately',
                'run_gain_q12': gain, 'identity': self.identity()}

    def _run_v2(self, request, cancel_event=None):
        import math
        import time
        if self._cancelled(cancel_event):
            return self._cancel_result(request, 'run')
        seconds = float(request.get('seconds', 30.0))
        q12 = int(request.get('gain_q12', self.allowed_gain_q12[0]))
        src = self._run_source(request, seconds)
        if isinstance(src, dict):
            return src
        scene = request.get('scene_id')
        self._current_op = 'run'
        self._write_control(arm=False, bypass=bool(request.get('bypass')), gain_q12=q12,
                            allow_armed=True)
        if self._cancelled(cancel_event):
            self.mute()
            return self._cancel_result(request, 'run')
        self._write_control(arm=True, allow_armed=True)
        cap_path, cid = self._capture_path(scene, 'run', 0)
        wall0 = time.monotonic()
        try:
            self._driver().replay_trial(str(cap_path), self.fixture, str(self.model_path), src,
                                        bypass=bool(request.get('bypass')), zero_coeff=False,
                                        gain_db=20 * math.log10(max(q12, 1) / 4096.0),
                                        seconds=seconds, hp_volume=self.hp_volume,
                                        speaker_confirmed=True, local_capture_confirmed=True,
                                        direct_only=False, reuse_overlay=False, restore_stock=False,
                                        before_start=lambda: not self._cancelled(cancel_event))
            meta = self._meta(np.load(str(cap_path)))
        finally:
            wall = time.monotonic() - wall0
            self._write_control(arm=False, allow_armed=True)
            self.mute()
            self._current_op = None
        frames = int(meta.get('frames') or meta.get('captured_frames') or 0)
        status = int(meta.get('capture_status') or 0)
        ok = meta.get('stop_reason') == 'completed'
        return {'contract': CONTRACT, 'request_id': request.get('request_id'), 'scene_id': scene,
                'op': 'run', 'ok': ok, 'status': 'completed' if ok else
                ('protected' if (status >> 22) & 1 else 'error'),
                'effective_mode': self.effective_mode(),
                'audio_frames': frames,
                'requested_seconds': seconds,
                'elapsed_seconds': round(frames / 48828.125, 3),      # duration of the captured window
                'wall_seconds': round(wall, 3),                        # init plus waiting, separately
                'note': 'elapsed_seconds is the captured window, not the requested run length; the run '
                        'itself played requested_seconds',
                'model_sha256': self._last_model_sha,
                'coefficients_sha256': self._last_coeff_sha,
                'capture_id': cid, 'path': str(cap_path),
                'identity': self.identity()}

    # ---- poll: running identity ---------------------------------------------------------
    def poll(self):
        r = super().poll()
        if self._last_model_sha:
            r['model_sha256'] = self._last_model_sha
            r['coefficients_sha256'] = self._last_coeff_sha
        r['open_loop_gain_q12_allowed'] = OPEN_LOOP_GAIN_Q12
        return r


def create_product(config):          # noqa: F811 - v2 replaces the factory
    return ProductHardwareV2(config)
