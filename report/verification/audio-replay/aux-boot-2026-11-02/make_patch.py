"""Build the A-side AUX fix as a reviewable copy + unified diff. Nothing in the frozen package is touched.

Edits (three, all inside hw_api.py):
  1. get_aux_gain_db(): report an unmapped code honestly instead of folding it into None.
  2. ProductHardware.__init__(): write the documented AUX working point once, before anyone can
     read identity; a failure is recorded rather than raised.
  3. Module docstring: the header still describes the pre-I/O bitstream (2113a454, "no buttons or
     LEDs"), which is wrong for the shipped I/O build (322350656986d91f).
"""
import difflib
import pathlib
import tempfile

V3IO = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-int\board\audio_replay\v3-io')
# Generated files go to the OS temp dir on purpose: a patched copy of a frozen payload must never
# sit next to the real package where it could be picked up or shipped by accident.
HERE = pathlib.Path(tempfile.gettempdir()) / 'shengdi-auxfix'
HERE.mkdir(parents=True, exist_ok=True)
SRC = V3IO / 'hw_api.py'
OUT = HERE / 'hw_api.AUXFIX.py'

OLD_DOC = '''"""Hardware capability interface for the one-click recalibration product.

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
"""'''

NEW_DOC = '''"""Hardware capability interface for the one-click recalibration product.

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
read_switches()          SW0/SW1 as they are wired in the bitstream (see SWITCH_MAP)
read_buttons()           BTN3..BTN0 from capture_status[30:27] (I/O integration build)
set_led(mask)            LD3..LD0 from control[5:2] (I/O integration build)

Bitstream facts this module relies on (I/O integration build, bit 322350656986d91f...):
  capture_status[30:27] = BTN3..BTN0 synchronised
  capture_status[25] = SW0 raw pin, [24] = SW0 synchronised, [23] = SW1 synchronised
  either switch up forces bypass in the PL: bypass_effective = control[1] | sw0 | sw1
  control[5:2] = LD3..LD0, control[1] = software bypass, control[0] = arm
"""'''

OLD_AUX = '''    def get_aux_gain_db(self):
        fd = self._fd()
        try:
            l, r = self._read8(fd, REG_AUX_L), self._read8(fd, REG_AUX_R)
        finally:
            os.close(fd)
        def to_db(v):
            return {7: 6.0, 5: 0.0}.get(v & 0x07, None)
        return {'ok': to_db(l) is not None and to_db(l) == to_db(r),
                'aux_gain_db': to_db(l), 'raw_left': l, 'raw_right': r,
                'settable': sorted([0.0, 6.0])}'''

NEW_AUX = '''    # Low three bits of 0x400B/0x400D -> dB. 0x05 is 0 dB, 0x07 is +6 dB; every other code -
    # including the codec's power-on value 0x00 - is NOT a gain and must not be read as 0 dB.
    AUX_GAIN_CODES = {5: 0.0, 7: 6.0}

    @classmethod
    def aux_code_to_db(cls, value):
        """Map a raw 3-bit AUX code to dB, or None when the code is not one we ever wrote."""
        return cls.AUX_GAIN_CODES.get(value & 0x07)

    def get_aux_gain_db(self):
        fd = self._fd()
        try:
            l, r = self._read8(fd, REG_AUX_L), self._read8(fd, REG_AUX_R)
        finally:
            os.close(fd)
        db_l, db_r = self.aux_code_to_db(l), self.aux_code_to_db(r)
        recognised = db_l is not None and db_r is not None
        return {'ok': recognised and db_l == db_r,
                'recognized': recognised,
                'aux_gain_db': db_l if db_l == db_r else None,
                'aux_db_left': db_l, 'aux_db_right': db_r,
                'raw_left': l, 'raw_right': r,
                'unmapped_codes': [hex(v) for v, db in ((l, db_l), (r, db_r)) if db is None],
                'power_on_like': (l & 0x07) == 0 and (r & 0x07) == 0,
                'settable': sorted([0.0, 6.0])}'''

OLD_INIT = '''        self._board = Board(str(self.dir), fixture=self.fixture, hp_volume=self.hp_volume)
        self._mm = None'''

NEW_INIT = '''        self._board = Board(str(self.dir), fixture=self.fixture, hp_volume=self.hp_volume)
        # The codec powers up with 0x400B/0x400D = 0x00, which is not a gain code, so the product's
        # first identity read would otherwise see aux_db=None and refuse to start. Put the documented
        # working point in place exactly once, here, before anything can read identity. A failure is
        # recorded, not raised: identity() then reports the real readback instead of the service
        # dying inside the constructor.
        try:
            self.aux_init = self._board.set_aux_gain_db(self.aux_db)
        except Exception as exc:
            self.aux_init = {'ok': False, 'error': repr(exc)[:160]}
        self._mm = None'''

OLD_CAPS = """        return {'ok': True, 'contract': CONTRACT, 'buttons': True, 'indicator': True,
                'nonintrusive_events': True, 'abort_mutes': True, 'prepared_capture': True,"""

NEW_CAPS = """        return {'ok': True, 'contract': CONTRACT, 'buttons': True, 'indicator': True,
                'aux_init': self.aux_init,
                'nonintrusive_events': True, 'abort_mutes': True, 'prepared_capture': True,"""

EDITS = [('module docstring', OLD_DOC, NEW_DOC),
         ('get_aux_gain_db', OLD_AUX, NEW_AUX),
         ('ProductHardware.__init__', OLD_INIT, NEW_INIT),
         ('capabilities', OLD_CAPS, NEW_CAPS)]


def main():
    text = SRC.read_text(encoding='utf-8')
    original = text
    for name, old, new in EDITS:
        if text.count(old) != 1:
            raise SystemExit('anchor %r occurs %d times, expected exactly 1' % (name, text.count(old)))
        text = text.replace(old, new)
    OUT.write_text(text, encoding='utf-8', newline='\n')
    diff = difflib.unified_diff(original.splitlines(keepends=True), text.splitlines(keepends=True),
                                fromfile='board/audio_replay/v3-io/hw_api.py',
                                tofile='board/audio_replay/v3-io/hw_api.py (AUXFIX)')
    (HERE / 'aux-fix.diff').write_text(''.join(diff), encoding='utf-8', newline='\n')
    print('wrote %s (%d -> %d bytes)' % (OUT, len(original), len(text)))
    print('wrote %s' % (HERE / 'aux-fix.diff'))


if __name__ == '__main__':
    main()
