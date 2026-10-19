# Muted audio PL bring-up artifact

Vivado 2018.3 generated `audio_bringup.bit` and matching `audio_bringup.hwh` from `build/scripts/create_audio_bringup.tcl`. The `.bit` and `.hwh` are kept together by basename. With user authorization, `muted_smoke.py` was run once on the PYNQ-Z2 on 2026-10-15. It reported mute readback, a frame count increase from 2202 to 14427 over 0.25 s, and `STOCK_BASE_RESTORED`. The board Notebook is `base/audio/audio_bringup_muted_smoke_2026-10-15.ipynb`; local screenshot is `report/verification/audio_bringup/muted_smoke_board.png`.

The test loads the new overlay with control=0, checks GPIO and frame count, then restores stock `base.bit`. It does not make sound or prove audio quality. Codec configuration may affect whether the frame count advances. If `Overlay()` or subsequent calls fail, the `finally` block attempts to restore base; a power cycle and known good Notebook are the recovery path if that fails.

Do not run it concurrently with `audio_playback.ipynb` actions. A single person operates the board. The existing audio object becomes invalid after PL reload; recreate it after returning to base. No sound experiment should follow until reset, I2C codec setup, actual sample rate and I/O timing are checked.

Known limits: `audio_frame_path` only attenuates, without FIR or feedback suppression; MAX_FRAMES counts frames, not independent wall time. The build has no external audio input/output timing delays and is not a timing signoff for the Codec interface.

`codec_clock_smoke.py` is a muted PLL compatibility check. Its code was pasted into the existing board Notebook and run on 2026-10-15; it was not uploaded as a separate file. The ADAU1761 PLL locked at 50 MHz (`000000002803`) while the PL output stayed muted, and stock `base.bit` plus the original 48 kHz PLL (`0271023c2103`) were verified restored. This does not validate audio samples or playback. See `report/verification/audio_bringup/codec_clock_smoke_board.png`.
