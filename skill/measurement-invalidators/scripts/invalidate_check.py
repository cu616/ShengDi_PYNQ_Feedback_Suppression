#!/usr/bin/env python3
"""Measurement-validity checks for stored captures (numpy only).

Implements the four checks described in ../SKILL.md:

  1. counter blind spot  - does the reported counter contradict the rail census?
  2. rail census         - how many samples sit at full scale, and for how long
  3. stationarity        - is the metric stable within a capture, and across captures
  4. responsiveness      - optional: does the reading scale with a changed excitation

Usage:
    python invalidate_check.py --npz one.npz [more.npz ...]
    python invalidate_check.py --npz a.npz b.npz --metric band-share --band 300 360

Exit code 0 = all checks passed (the capture is usable for comparison),
1 = at least one check flagged the measurement, 2 = input problem.
"""
import argparse
import json
import sys

import numpy as np

FULL_SCALE_PCM = 8388607          # signed 24-bit positive rail
DEFAULT_RATE = 48828.125
BLOCK = 2048


def load(path):
    try:
        d = np.load(path)
    except Exception as exc:
        print("FAILED: cannot open %s (%s)" % (path, exc))
        raise SystemExit(2)
    cap = {'file': str(path), 'keys': list(d.files)}
    for key in ('microphone', 'reference'):
        if key in d.files:
            cap[key] = np.asarray(d[key], dtype=np.float64)
    for key in ('prediction_pcm', 'residual_pcm'):
        if key in d.files:
            cap[key] = np.asarray(d[key], dtype=np.int64)
    cap['rate'] = float(d['sample_rate_hz']) if 'sample_rate_hz' in d.files else DEFAULT_RATE
    cap['meta'] = {}
    if 'metadata_json' in d.files:
        try:
            cap['meta'] = json.loads(str(d['metadata_json']))
        except Exception:
            cap['meta'] = {}
    if 'microphone' not in cap:
        print("FAILED: %s has no microphone stream" % path)
        raise SystemExit(2)
    return cap


def rail_census(signal, rail):
    flags = np.abs(signal) >= rail * 0.999999
    runs, current = [], 0
    for flag in flags:
        if flag:
            current += 1
        else:
            if current:
                runs.append(current)
            current = 0
    if current:
        runs.append(current)
    return int(flags.sum()), (sorted(runs, reverse=True)[:3] if runs else [])


def block_metric(cap, band=None):
    mic = cap['microphone']
    n = len(mic) // BLOCK
    if n == 0:
        return []
    values = []
    for b in range(n):
        seg = mic[b * BLOCK:(b + 1) * BLOCK]
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        freqs = np.fft.rfftfreq(len(seg), 1.0 / cap['rate'])
        mask = (freqs >= 50) & (freqs <= 20000)
        if band is None:
            values.append(20 * np.log10(max(float(np.sqrt(np.mean(seg ** 2))), 1e-12)))
        else:
            bm = (freqs >= band[0]) & (freqs < band[1])
            total = float(np.sum(spec[mask] ** 2))
            values.append(float(np.sum(spec[bm] ** 2) / max(total, 1e-30)))
    return values


def check_capture(cap, band):
    problems = []
    mic = cap['microphone']
    rail_count, rail_runs = rail_census(mic, 1.0)
    duration_ms = 1000.0 * len(mic) / cap['rate']

    print("\n== %s" % cap['file'])
    print("   frames %d (%.1f ms)  mic_rms %.1f dBFS  rate %.1f"
          % (len(mic), duration_ms,
             20 * np.log10(max(float(np.sqrt(np.mean(mic ** 2))), 1e-12)), cap['rate']))
    print("   [check 2] rail census: %d sample(s) at full scale, longest runs %s"
          % (rail_count, rail_runs or "-"))
    if rail_count:
        fraction = rail_count / float(len(mic))
        # Consecutive-run length is a poor discriminator: a signal that rides the rail alternates
        # around it, so the longest run stays short even during a sustained overload. What
        # separates a transient from a runaway is the DENSITY of rail samples and whether whole
        # blocks sit near full scale.
        near = 0
        for b in range(len(mic) // BLOCK):
            seg = mic[b * BLOCK:(b + 1) * BLOCK]
            if 20 * np.log10(max(float(np.sqrt(np.mean(seg ** 2))), 1e-12)) > -3.0:
                near += 1
        sustained = fraction >= 0.05 or near >= 2
        print("             rail fraction %.2f%% | blocks within 3 dB of full scale: %d -> %s"
              % (100 * fraction, near,
                 "SUSTAINED overload / suspect runaway" if sustained else
                 "transient spike (do not call it regeneration)"))
        if not sustained and fraction > 0:
            problems.append(
                "only %.2f%% of samples are at full scale and no block sits near full scale; this is "
                "a transient, not a sustained runaway" % (100 * fraction))

    # check 1: does a reported counter contradict what the capture shows?
    residual = cap.get('residual_pcm')
    prediction = cap.get('prediction_pcm')
    if residual is not None and prediction is not None:
        pred_zero = bool(np.all(prediction == 0))
        res_rail, _ = rail_census(residual, FULL_SCALE_PCM)
        print("   [check 1] prediction all zero: %s | residual at rail: %d sample(s)"
              % (pred_zero, res_rail))
        if pred_zero and rail_count:
            problems.append(
                "counter blind spot: with the prediction identically zero the residual equals the "
                "microphone, so a residual-overflow counter cannot fire even though %d microphone "
                "samples are at full scale" % rail_count)
        if res_rail and not rail_count:
            problems.append("residual is at the rail while the microphone is not; check the clamp path")
    if pred_zero := (prediction is not None and bool(np.all(prediction == 0))):
        print("             note: zero prediction makes any residual-based counter structurally blind")

    # check 3: stationarity
    values = block_metric(cap, band)
    if len(values) >= 2:
        span = max(values) - min(values)
        unit = "dB" if band is None else "fraction"
        print("   [check 3] %s per %d-frame block: min %.4f max %.4f span %.4f %s"
              % ("level" if band is None else "band share", BLOCK, min(values), max(values), span, unit))
        if band is not None and span > 0.5:
            problems.append(
                "non-stationary source: the band share moves by %.2f (%.1f dB) inside one capture; "
                "a split-run comparison at this effect size is not interpretable"
                % (span, 10 * np.log10(max(max(values), 1e-12) / max(min(values), 1e-12))))
        elif band is None and span > 20.0:
            problems.append(
                "non-stationary source: the level moves by %.1f dB inside one capture" % span)
    return problems


def check_responsiveness(caps):
    """Check 4: if the excitation changed a lot but the reading did not, suspect the transducer."""
    if len(caps) < 2:
        return []
    levels = []
    for cap in caps:
        mic = cap['microphone']
        levels.append(20 * np.log10(max(float(np.sqrt(np.mean(mic ** 2))), 1e-12)))
    span = max(levels) - min(levels)
    print("\n[check 4] reading span across %d captures: %.1f dB" % (len(caps), span))
    if span < 3.0:
        return ["responsiveness: the reading barely moved across captures that should differ; "
                "verify the wiring and the transducer before interpreting it acoustically"]
    return []


def main():
    ap = argparse.ArgumentParser(description="measurement validity checks for stored captures")
    ap.add_argument("--npz", nargs="+", default=[], help="one or more capture npz files")
    ap.add_argument("--metric", default="level", choices=["level", "band-share"])
    ap.add_argument("--band", nargs=2, type=float, default=None, metavar=("LO", "HI"),
                    help="band edges in Hz for --metric band-share")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    if not args.npz:
        print("FAILED: no --npz given")
        return 2
    if args.metric == "band-share" and args.band is None:
        print("FAILED: --metric band-share needs --band LO HI")
        return 2

    caps = [load(p) for p in args.npz]
    problems, report = [], []
    for cap in caps:
        found = check_capture(cap, args.band)
        problems.extend(found)
        report.append({'file': cap['file'], 'problems': found})
    problems.extend(check_responsiveness(caps))

    print("\n" + "=" * 70)
    if problems:
        print("MEASUREMENT_FLAGGED (%d)" % len(problems))
        for p in problems:
            print("  - " + p)
    else:
        print("MEASUREMENT_OK: no structural problem found by these four checks")
    print("reminder: passing these checks does not prove the conclusion, only that the measurement "
          "is not obviously invalid.")

    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as fh:
            json.dump({'captures': report, 'problems': problems}, fh, indent=2, ensure_ascii=False)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
