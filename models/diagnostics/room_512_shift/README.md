# 诊断变体：512 模型整体平移 ±1 拍

**不是候选模型，不要写进 `models/manifest.json`，不要用于部署。**

用途只有一个：判定 A 侧会话的 `ref→mic` 延迟与 B 侧标定批（125 拍）是否差整拍。
2026-10-23 A 报告 `cancel` 在 −6 dB 啸叫（主频 8285 Hz），而同一模型在标定批上的阈值是
+6.6 dB；亚采样灵敏度表显示**0.5 拍错位就能把阈值压到 −5.8 dB**（见
[peak-margin-2026-10-23](../../../report/verification/peak-margin-2026-10-23/README.md) §4.2）。

## 文件

| 文件 | 含义 | Q20 指纹（sha256 前 16 位） | 本批 H 上的阈值 |
|---|---|---|---|
| `model_512_shift-1.json` | 系数整体前移 1 拍：`h'[k]=h[k+1]`。用于"现场延迟是 **124**" | `b879b0811df5adef` | −11.28 dB @8388 Hz |
| `model_512_shift+1.json` | 系数整体后移 1 拍：`h'[k]=h[k-1]`。用于"现场延迟是 **126**" | `c899be253af70cbb` | −9.98 dB @8339 Hz |
| （原始）`manifest/model_512.json` | 未平移 | `bc559238ee078321` | +6.64 / +7.32 dB |

生成：`python scripts/diagnose_peak_margin.py --data-dir <6 段> --model <model_512> --emit-dir models/diagnostics/room_512_shift`
（`coefficients_q20` 按平移后的浮点系数重算，未沿用原数组；`validation` 字段已删除。）

## 判读

两个变体在**标定批**上都是坏的（−10…−11 dB），这是预期的：标定批延迟是 125，平移后当然不匹配。
只有在 A 侧现场延迟确实不是 125 时，对应方向的那个才会变好。

- 先量延迟：对旁路捕获做 `ref→mic` 互相关取峰，或直接用 `scripts/check_causal_alignment.py`
  的口径。**这个数一旦给出，就不必再靠变体试。**
- 延迟 = 124 → 用 `shift-1`；= 126 → 用 `shift+1`；= 125 → 两个都不用，问题不在整拍错位。
- 两个都测也无害（各 6 s），但别用"哪个听着好"当结论，要用阈值（衰减率外推的 `r=0` 横截距）。
