"""检验一张复频响表是否自洽：|H|、|Ĥ|、相位差、|H−Ĥ| 四列必须满足余弦定理。

现场报告里"相位差"与"复残差"两列经常来自不同口径（一个取自峰值读数的角度，
一个取自相减后的模），肉眼看不出，但用余弦定理一验就露。

判读：
  偏差 |余弦值 − 报告值| <= 0.05       → 该行自洽，可用
  偏差明显但方向一致                  → 某一列整体偏移（多为相位列取了 ∠H 而非 ∠H−∠Ĥ）
  偏差方向不一致                      → 几列来自不同数据/不同频点，整张表不可用

用法：
  python scripts/verify_complex_response_table.py
  python scripts/verify_complex_response_table.py --json out.json   # 指定自定义表
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

# lead-report §12.4 的原表：(f, |H|, |Ĥ|, 报告|H−Ĥ|, 报告相位差°)
DEFAULT_ROWS = [
    (400,  1.331, 0.994, 0.459,   16.9),
    (4000, 0.515, 0.628, 0.262, -109.2),
    (8000, 0.505, 0.476, 0.372,  174.5),
    (8350, 1.276, 1.079, 0.815, -152.0),
    (8500, 1.295, 1.135, 1.141,   32.3),
    (9000, 0.320, 0.269, 0.245, -136.0),
]

GAIN_3DB = 5786 / 4096          # +3 dB 数字增益
TOL = 0.05


def check(rows, gain=GAIN_3DB):
    out = []
    for f, a, b, rep, dphi in rows:
        cosd = np.cos(np.deg2rad(dphi))
        calc = float(np.sqrt(max(a * a + b * b - 2 * a * b * cosd, 0.0)))
        # 反方向：由残差反解相位差，看报告相位是否落在同一支
        c = (a * a + b * b - rep * rep) / max(2 * a * b, 1e-12)
        back = float(np.degrees(np.arccos(np.clip(c, -1, 1))))
        out.append({
            "hz": f, "H_abs": a, "Hh_abs": b,
            "reported_resid": rep, "cosine_resid": calc,
            "delta": calc - rep,
            "consistent": abs(calc - rep) <= TOL,
            "reported_phase_deg": dphi, "implied_phase_deg": back,
            "loop_from_reported": rep * gain, "loop_from_cosine": calc * gain,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="自定义表：[[f,|H|,|Ĥ|,残差,相位°], ...]")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = DEFAULT_ROWS
    if args.json:
        rows = [tuple(r) for r in json.loads(Path(args.json).read_text(encoding="utf-8"))]

    res = check(rows)
    print("+3 dB 线性增益 = %.5f（q12 5786 / 4096）" % GAIN_3DB)
    print()
    print("%7s %7s %7s %11s %11s %8s %9s %10s" % (
        "f/Hz", "|H|", "|Ĥ|", "报告残差", "余弦推出", "偏差", "报告Δφ", "反解Δφ"))
    print("-" * 82)
    for r in res:
        flag = "" if r["consistent"] else "  <-- 不自洽"
        print("%7.0f %7.3f %7.3f %11.3f %11.3f %+8.3f %8.1f° %9.1f°%s" % (
            r["hz"], r["H_abs"], r["Hh_abs"], r["reported_resid"],
            r["cosine_resid"], r["delta"], r["reported_phase_deg"],
            r["implied_phase_deg"], flag))

    n_bad = sum(1 for r in res if not r["consistent"])
    deltas = [r["delta"] for r in res if not r["consistent"]]
    print()
    print("自洽 %d / %d 行" % (len(res) - n_bad, len(res)))
    if n_bad:
        same_sign = all(d > 0 for d in deltas) or all(d < 0 for d in deltas)
        print("不自洽行偏差方向%s" % ("一致（疑似某列整体偏移）" if same_sign else
                                "不一致（几列来自不同数据/频点，整表不可用）"))
        print("提示：若报告相位列实际是 ∠H 而非 ∠H−∠Ĥ，用'反解Δφ'替代后再核一次。")

    print()
    print("同一残差下的 +3 dB 环路增益：")
    for r in res:
        print("  %5.0f Hz  报告值 %.3f → %.2f %-4s | 余弦值 %.3f → %.2f %-4s" % (
            r["hz"], r["reported_resid"], r["loop_from_reported"],
            "越界" if r["loop_from_reported"] > 1 else "可",
            r["cosine_resid"], r["loop_from_cosine"],
            "越界" if r["loop_from_cosine"] > 1 else "可"))

    if args.out:
        Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\nJSON 已写: %s" % args.out)


if __name__ == "__main__":
    main()
