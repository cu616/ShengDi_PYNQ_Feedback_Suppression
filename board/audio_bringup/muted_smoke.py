"""One-shot, muted PL check. Run only on a PYNQ-Z2 with these matching bit/hwh files.

The speaker may be powered, but this check never enables audio output.
After any attempt, the stock base overlay is reloaded. Run this in a dedicated
notebook kernel and do not operate another board notebook concurrently.
"""

from pathlib import Path
from time import sleep

from pynq import MMIO, Overlay
from pynq.overlays.base import BaseOverlay


BIT = Path(__file__).with_name("audio_bringup.bit")
HWH = BIT.with_suffix(".hwh")
assert BIT.is_file() and HWH.is_file(), "Matching bit/hwh files required"

# Hardware handoff: audio_control at 0x41200000. AXI GPIO channel 1 data=0x0,
# TRI=0x4; channel 2 input data=0x8. control=0 keeps the PL path muted.
try:
    overlay = Overlay(str(BIT), download=True)
    gpio = MMIO(0x41200000, 0x1000)
    gpio.write(0x0, 0)
    gpio.write(0x4, 0)
    assert gpio.read(0x0) == 0, "Control register did not read back as mute"
    before = gpio.read(0x8)
    sleep(0.25)
    after = gpio.read(0x8)
    assert gpio.read(0x0) == 0, "Control left mute during test"
    print({"mute": True, "frame_count_before": before,
           "frame_count_after": after, "counter_advanced": after > before})
finally:
    BaseOverlay("base.bit")
    print("STOCK_BASE_RESTORED")
