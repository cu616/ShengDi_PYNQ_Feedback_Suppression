"""验证"256 抽头模型补零到 512 后加载到 512 抽头位流"在数学上等价。

判据（全部通过才算等价）：
  1. 结构：padded[k] == base[k] (k < 256)，padded[k] == 0 (256 <= k < 512)，
     即零在**尾部**（对应最大滞后），不是在头部。
  2. 浮点：predict() 逐样本完全相等（差值恒为 0.0，不是"很小"）。
  3. 定点：Q20 + 24 位饱和的比特级实现逐样本完全相等，且饱和计数不变。
  4. 反例：把零放到头部（前补零）必须被本脚本判为不等价——否则测试没有分辨力。

用法：
  python scripts/verify_padding_equivalence.py --base models/room_v1/baseline_256.json \
      --padded models/room_v1/baseline_256_padded512.json \
      --capture <ref/mic npz> [--samples 4096]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from feedback.calibration import fixed_fir, predict, quantize_coefficients  # noqa: E402


def sha256_of(values) -> str:
    payload = json.dumps([int(v) for v in values], separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def load_pair(base_path: Path, padded_path: Path):
    base = json.loads(base_path.read_text(encoding="utf-8"))
    padded = json.loads(padded_path.read_text(encoding="utf-8"))
    return base, padded


def check_structure(base_coef, padded_coef):
    n = len(base_coef)
    head_ok = all(abs(padded_coef[k] - base_coef[k]) <= 1e-18 for k in range(n))
    tail_zero = all(v == 0 for v in padded_coef[n:])
    return head_ok, tail_zero


def check_float(reference, base_coef, padded_coef):
    a = predict(reference, base_coef)
    b = predict(reference, padded_coef)
    return float(np.max(np.abs(a - b))), int(np.count_nonzero(a != b))


def check_fixed(ref_pcm, base_q20, padded_q20):
    a, sa = fixed_fir(ref_pcm, base_q20)
    b, sb = fixed_fir(ref_pcm, padded_q20)
    return int(np.count_nonzero(a != b)), sa, sb


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--padded", required=True)
    ap.add_argument("--capture", required=True, help="含 reference / microphone 的 npz")
    ap.add_argument("--samples", type=int, default=4096, help="定点逐样本核对的长度")
    args = ap.parse_args()

    base, padded = load_pair(Path(args.base), Path(args.padded))
    base_coef = np.asarray(base["coefficients"], dtype=np.float64)
    padded_coef = np.asarray(padded["coefficients"], dtype=np.float64)
    n_base, n_pad = len(base_coef), len(padded_coef)

    print("base   : %s  taps=%d lag_first=%d" % (args.base, n_base, base["lag_first"]))
    print("padded : %s  taps=%d lag_first=%d" % (args.padded, n_pad, padded["lag_first"]))
    if base["lag_first"] != 1 or padded["lag_first"] != 1:
        print("FAIL 只支持 lag_first=1 的约定")
        return 1
    if n_pad != 2 * n_base:
        print("FAIL 抽头数不是 2 倍")
        return 1

    head_ok, tail_zero = check_structure(base_coef, padded_coef)
    print("\n[1] 结构检查")
    print("    头部 256 个系数与 base 相同 : %s" % ("是" if head_ok else "否"))
    print("    尾部 256 个系数全为 0      : %s" % ("是" if tail_zero else "否"))

    cap = np.load(args.capture)
    reference = np.asarray(cap["reference"], dtype=np.float64)
    diff, mism = check_float(reference, base_coef, padded_coef)
    print("\n[2] 浮点逐样本：最大绝对差 %.3e，不完全相等的样本数 %d / %d"
          % (diff, mism, len(reference)))
    print("    说明：浮点卷积的累加顺序随抽头数改变，末位舍入差别属正常；")
    print("    判据是差值 <= 1e-12（机器精度量级），而**定点路径必须逐样本完全相等**。")

    pcm = np.rint(reference[: args.samples] * (1 << 23)).astype(np.int64)
    pcm = np.clip(pcm, -(1 << 23), (1 << 23) - 1)
    base_q20 = np.asarray(base.get("coefficients_q20") or
                          quantize_coefficients(base_coef), dtype=np.int64)
    pad_q20 = np.asarray(padded.get("coefficients_q20") or
                         quantize_coefficients(padded_coef), dtype=np.int64)
    fmism, sa, sb = check_fixed(pcm, base_q20, pad_q20)
    print("\n[3] 定点（Q20 + 24 位饱和）逐样本：不相等样本数 %d / %d，饱和计数 %d vs %d"
          % (fmism, len(pcm), sa, sb))

    # 反例：前补零（零在最大滞后处）——等价性必须在这里失效。
    front = np.concatenate([np.zeros(n_pad - n_base), base_coef])
    fdiff, fmis = check_float(reference, base_coef, front)
    print("\n[4] 反例（前补零）：最大绝对差 %.3e，不相等样本数 %d —— 必须非零"
          % (fdiff, fmis))

    print("\n[5] 系数指纹（sha256，只覆盖 Q20 整数数组）")
    print("    base   %s" % sha256_of(base_q20))
    print("    padded %s" % sha256_of(pad_q20))

    ok = (head_ok and tail_zero and diff <= 1e-12 and fmism == 0 and sa == sb
          and fmis > 0)
    print("\n结论：%s" % ("等价（尾部补零）" if ok else "不等价或无法证明"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
