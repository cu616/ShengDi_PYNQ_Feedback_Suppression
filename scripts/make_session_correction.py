"""按现场复测的频带偏差修正 512 模型（C(f) = Δ幅度 · e^{jΔ相位}）。

背景：2026-10-24 A 用白噪声数字注入复测现场 H，相对标定批的偏差为
  300-1000   -0.51 dB  +2.1°
  1000-3000  +0.07 dB  -7.6°
  3000-6000  -0.60 dB +11.8°
  8200-8600  -4.97 dB +38.9°
  8380 Hz    -5.98 dB +39.5°
用它把部署模型整体乘上 C(f)，再用 512 抽头最小二乘逼近。

**这只对"同一夹具、同一音量、同一注入电平"的这一次会话有效。** 换夹具/换音量即失效。
输出里同时给：
  - 实现误差 |Ĥ_new − Ĥ·C|（这是能测量的，不是预测）；
  - 带内修正剩余误差的不确定预算下的阈值区间（这才是预测）。

用法：
  python scripts/make_session_correction.py --model models/room_v1/candidate_512.json \
      --out models/room_v1/session_20261024/candidate_512_session_20261024.json
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from feedback.calibration import quantize_coefficients  # noqa: E402

NFFT = 4096
FS = 48828.125
# (频率 Hz, 幅度偏差 dB, 相位偏差 度)；两端用 0 收口，避免把偏差外推到没有测量的频段
ANCHORS = [
    (300.0, 0.0, 0.0),
    (650.0, -0.51, 2.1),
    (2000.0, 0.07, -7.6),
    (4500.0, -0.60, 11.8),
    (8200.0, -4.97, 38.9),
    (8380.0, -5.98, 39.5),
    (8600.0, -4.97, 38.9),
    (12000.0, 0.0, 0.0),
]


def estimate_H(calib_dir):
    """标定批的 H（与 NFFT 同网格），用来构造"现场真值 = H × C"。"""
    paths = sorted(glob.glob(str(Path(calib_dir) / "seg_*.npz")))
    if not paths:
        raise SystemExit("no seg_*.npz in %s" % calib_dir)
    win = np.hanning(NFFT)
    S_uu = S_mm = S_um = None
    for p in paths:
        cap = np.load(p)
        ref = np.asarray(cap["reference"], float)
        mic = np.asarray(cap["microphone"], float)
        for start in range(0, len(ref) - NFFT + 1, NFFT // 2):
            U = np.fft.rfft(ref[start:start + NFFT] * win)
            M = np.fft.rfft(mic[start:start + NFFT] * win)
            a = (np.conj(U) * U).real
            b = (np.conj(M) * M).real
            c = np.conj(U) * M
            S_uu = a if S_uu is None else S_uu + a
            S_mm = b if S_mm is None else S_mm + b
            S_um = c if S_um is None else S_um + c
    H = S_um / S_uu
    coh = np.abs(S_um) ** 2 / (S_uu * S_mm)
    return H, coh


def response(coefficients, nfft=NFFT):
    h = np.asarray(coefficients, dtype=float)
    pad = np.zeros(nfft)
    pad[:len(h)] = h
    w = 2 * np.pi * np.arange(nfft // 2 + 1) / nfft
    return np.fft.rfft(pad) * np.exp(-1j * w)  # lag_first=1


def correction(freqs, anchors=ANCHORS):
    f = np.array([a[0] for a in anchors])
    db = np.array([a[1] for a in anchors])
    ph = np.radians(np.array([a[2] for a in anchors]))
    mag = 10 ** (np.interp(freqs, f, db, left=0.0, right=0.0) / 20)
    phase = np.interp(freqs, f, ph, left=0.0, right=0.0)
    return mag * np.exp(1j * phase)


def design(target, freqs, taps=512, weighted=True):
    """在给定网格上做最小二乘，得到因果**实** FIR（h[k] 作用在滞后 1+k）。

    未知量必须是实数：把复数方程的实部与虚部堆成两倍行数的实数系统再解，
    否则解出来是复系数，无法下发。
    """
    sel = (freqs >= 250) & (freqs <= 13000)
    w = np.ones(len(freqs))
    if weighted:
        w = np.where(sel, 1.0, 0.15)
    k = np.arange(taps)
    A = np.exp(-1j * 2 * np.pi * np.outer(freqs, k + 1) / FS) * w[:, None]
    M = np.vstack([A.real, A.imag])
    b = np.concatenate([(target * w).real, (target * w).imag])
    G = M.T @ M
    r = M.T @ b
    G += np.eye(taps) * np.trace(G) * 1e-10
    return np.linalg.solve(G, r)


def band_value(freqs, values, lo, hi):
    sel = (freqs >= lo) & (freqs < hi)
    return values[sel]


def tail_threshold(freqs, err, freqs_gate):
    """扣除低频（<300 Hz，模型已知短板）后的最大残留与阈值。"""
    sel = freqs_gate
    emax = float(np.max(err[sel]))
    return -20 * np.log10(emax), emax


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--taps", type=int, default=512)
    ap.add_argument("--calib-dir", default="D:/Always/QianSai/_inbox/2026-10-23_room6/manifest",
                    help="标定批 6 段所在目录，用来构造现场真值 H×C")
    args = ap.parse_args()

    model = json.loads(Path(args.model).read_text(encoding="utf-8"))
    h = np.asarray(model["coefficients"], dtype=float)
    freqs = np.arange(NFFT // 2 + 1) * FS / NFFT
    H_hat = response(h, NFFT)

    C = correction(freqs)
    target = H_hat * C
    h_new = design(target, freqs, args.taps)
    H_new = response(h_new, NFFT)

    impl = np.abs(H_new - target)
    at = {}
    for f0, ddb, dph in ANCHORS:
        k = int(np.argmin(np.abs(freqs - f0)))
        at["%g" % f0] = round(float(20 * np.log10(impl[k])), 2)
    inband = (freqs >= 300) & (freqs <= 10000)
    print("实现误差 |Ĥ_new − Ĥ·C|：带内最大 %.2f dB @ %.0f Hz"
          % (20 * np.log10(impl[inband].max()), freqs[inband][np.argmax(impl[inband])]))
    print("  锚点处：%s" % at)

    # 现场真值 = 标定 H × C。不能拿 H_hat 当代用真值，否则会把标定残差整体抹掉。
    H_calib, coh = estimate_H(args.calib_dir)
    H_true = H_calib * C
    gate = (freqs >= 300) & (freqs <= 10500) & (coh >= 0.8)
    Err_old = np.abs(H_true - H_hat)
    Err_new = np.abs(H_true - H_new)
    print("\n同一代用真值下的残留（自洽检查，不是预测）")
    print("  部署模型 max|E| = %+.2f dB -> 阈值 %+.2f dB"
          % (20 * np.log10(Err_old[gate].max()),
             -20 * np.log10(Err_old[gate].max())))
    print("  修正模型 max|E| = %+.2f dB @ %.0f Hz -> 阈值 %+.2f dB"
          % (20 * np.log10(Err_new[gate].max()),
             freqs[gate][np.argmax(Err_new[gate])],
             -20 * np.log10(Err_new[gate].max())))
    print("  部署模型 max|E| 位置 %.0f Hz"
          % freqs[gate][np.argmax(Err_old[gate])])

    print("\n不确定预算：8.2–8.6 kHz 带内修正仍有 δ 误差时的阈值")
    print("  δ幅度/δ相位     max|E| dB    阈值 dB")
    budget = []
    for ddb, dph in ((0.0, 0.0), (0.5, 5.0), (1.0, 10.0), (2.0, 20.0), (3.0, 30.0)):
        Cs = C * (10 ** (ddb / 20) * np.exp(1j * np.radians(dph)))
        band = (freqs >= 7800) & (freqs <= 9000)
        Cs_band = np.where(band, Cs, C)
        Hs = H_calib * Cs_band      # 真值随修正误差一起变，不是拿模型当真值
        E = np.abs(Hs - H_new)
        thr = -20 * np.log10(E[gate].max())
        budget.append({"amp_db": ddb, "phase_deg": dph,
                       "threshold_db": round(float(thr), 2)})
        print("  %+4.1f dB / %+5.1f°  %+10.2f  %+8.2f"
              % (ddb, dph, 20 * np.log10(E[gate].max()), thr))

    q20 = quantize_coefficients(h_new)
    out = dict(model)
    out["coefficients"] = h_new.tolist()
    out["coefficients_q20"] = q20.tolist()
    out["taps"] = args.taps
    out["derived_from"] = Path(args.model).name
    out["derived_from_sha256"] = hashlib.sha256(Path(args.model).read_bytes()).hexdigest()
    out["session_correction"] = {
        "anchors": [{"freq_hz": a[0], "amp_db": a[1], "phase_deg": a[2]} for a in ANCHORS],
        "source": "A 2026-10-24 现场白噪声数字注入复测，相对标定批",
        "applies_to": "同一夹具、同一 hp_volume、同一注入电平的本次会话",
        "invalidated_by": "换夹具/换音量/移动话筒或音响/改变注入电平",
        "implementation_error_db": at,
        "predicted_threshold_db": budget,
        "warning": "阈值随 8.2–8.6 kHz 带内修正精度变化；不要把预算上限当实测",
    }
    out["status"] = "session_corrected_candidate_not_board_validated"
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(Path(args.out).read_bytes()).hexdigest()
    print("\n写出 %s\n  file sha256 %s\n  q20 sha256  %s\n  q20 maxabs %d"
          % (args.out, digest,
             hashlib.sha256(np.asarray(q20, dtype=np.int64).astype("<i4").tobytes()).hexdigest(),
             int(np.max(np.abs(q20)))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
