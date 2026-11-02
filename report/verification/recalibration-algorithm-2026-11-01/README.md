# recal_algorithm 离线复核（2026-11-01）

C 的契约 `recal-product-v1` 里"B算法函数"一节的真实实现与复核。
实现：`board/audio_replay/recal_algorithm.py`；契约说明与适配清单：
[`docs/contracts/recalibration-algorithm-v1.md`](../../../docs/contracts/recalibration-algorithm-v1.md)。

- 复核脚本：`python scripts/recal_algorithm_offline.py` → 本目录 [cases.json](cases.json)
- 回归：`python -m unittest sim.feedback.test_recal_algorithm`（15 项）

**状态：离线通过，待上板验证。** 与本仓库既有的算法验证（CD、ASG、三点）分开记。

## 0 三句话

1. `fit` 在部署模型的来源数据上（4 训练 / 2 验证）给出 `valid_pass`，模型 L1 2.303、峰位 184
   与本轮实测延迟一致；`validate` 用独立验证段判 `valid_pass`，300–460 Hz 带内抑制中位 **+4.17 dB**。
2. 同一个 `validate` 换模型：部署模型 +4.21 dB（过）、旧夹具模型 −4.40 dB（拒）、全零系数 0.00 dB（拒）。
   **判据在真实数据上分得开，不是只在合成数据上成立。**
3. 复核中把独立验证的判据从"Welch/CD"换成"逐段时间域带内抑制"——**因为前者随谱口径漂 1.5–6.5 dB，
   后者四种口径完全一致（1.02 dB）**。这不是为了放宽，是因为原口径没有可复现的数值。

## 1 六例结果

| 例 | decision | 依据 |
|---|---|---|
| `fit` 4 训练 / 2 验证 | `valid_pass` | L1 2.303、峰位 184 = 实测延迟 184 |
| `validate` 本轮拟合的模型 | `valid_pass` | 带内中位 +4.17 dB（逐段 3.47 / 4.94） |
| `validate` 部署模型 | `valid_pass` | 带内中位 +4.21 dB（逐段 3.49 / 4.94） |
| `validate` 旧夹具模型 | `model_rejected` | 带内中位 −4.40 dB，至少一段 −4.45 |
| `validate` 全零系数 | `model_rejected` | 带内 0.00 dB < 0.5 |
| `validate` 借用训练集的 capture | `data_insufficient` | capture_id 与训练集重叠，不是独立验证 |

`fit` 在 PC 上 0.45 s、`validate` 0.10 s。PYNQ 的 ARM 慢 5–10 倍，所以契约里要求
`compute_timeout_seconds` 对 `fit` ≥ 15 s；C 当前配置的 3 s 会误杀。

## 2 为什么换掉 CD / 界差当判据

同一份数据（`bind4` 第 5/6 段），好模型 = 部署模型：

| 指标 | nperseg=2048 | 4096 | 8192 | 整段 | 漂移 |
|---|---|---|---|---|---|
| CD 中位 | 1.61 | 2.80 | 3.06 | 2.63 | 1.45 dB |
| 界差 | 4.36 | **9.24** | 3.42 | 2.76 | **6.48 dB** |
| 时域抑制（全带） | 1.02 | 1.02 | 1.02 | 1.02 | **0** |

界差在 4096 点处给 9.24 dB、整段给 2.76 dB——同一个模型、同一份数据，差 6.5 dB。
拿它当"≥1.0 dB 才通过"的判据，结论取决于选哪个窗长，不可复现。
时域残差与谱口径无关，因为它逐样本对照，不经过 Welch。

带内（300–460 Hz）抑制的梯度比全带更大，因为 150 Hz 以下和 10 kHz 以上是噪声底，
会把全带抑制的差值稀释掉：

| 模型 | 300–460 Hz | 150–10000 Hz |
|---|---|---|
| 部署模型 | +4.21 dB | +2.12 |
| 旧夹具 | −4.40 dB | −11.38 |
| 全零 | 0.00 dB | 0.00 |

阈值取 **+0.5 dB**：距好模型 3.7 dB、距坏模型 4.9 dB，两侧余量都够。

## 3 复核中修掉的两个坑

**① `validate` 没截到"源有效帧"。** 捕获尾部还有约 977 帧源已停、只剩底噪；
把它们算进 H 会把残差拖向噪声底。实测：不截断 CD 2.93 dB、截断 11.81 dB——差 8.9 dB。
现在 `fit` 与 `validate` 都走同一个 `_common_valid_length()`。

**② `expected_peak_tap` 必须是本轮实测延迟。** 用上一套布置的模型峰位当基准，
50 cm（实测 127/128）会被判成"换错布置"——而换摆位正是这套流程的用途。

## 4 明确不知道的

- **没有在 PYNQ 上跑过一次。** 所有耗时都是 PC 上的。
- **三档激励（−22 / −19.3 / −16.5 dBFS）在板上是否都可达未验证。** −16.5 是算出来的边缘
  （seed 4242 / 16384 帧实算波形因数 12.132 dB、`peak_cap=0.80` ⇒ 上限 −14.070 dBFS；
  −16.5 档峰值 0.605，距上限还有 2.43 dB。此前写的"约 −17 dBFS"是算错的，已更正）。
- **`source_sha256` 由 A 的 `hw_api` 提供，尚未联调。** 独立性判据依赖它正确；
  若 A 给的是文件名哈希而不是源内容哈希，独立性检查会失效。
- **判据只覆盖 300–460 Hz。** 低于 300 Hz 与高于 10 kHz 未纳入，理由是历史数据在这两段的
  相干不足，测不出可靠残差。
- **`qualifies_cancellation` 的含义限于"这个模型在自己的独立验证段上预测有抑制"**，
  不是 MSG/ASG，也不是听感。`evidence.not_asg = true` 每次都在。

## 5 待上板验证

| 项 | 需要什么 |
|---|---|
| `fit` 在 ARM 上的耗时 | 实测后定 `compute_timeout_seconds` |
| 三档激励互异且可达 | 三档各一次，比 `sha256` 与 `bit22` |
| 真实"好模型 / 错布置模型"各一次 validate | 确认两侧余量与离线一致 |
| A 的 `source_sha256` 口径 | 首次回包后核对 |

## 6 复现

```bash
python -m unittest sim.feedback.test_recal_algorithm
python scripts/recal_algorithm_offline.py \
    --inbox D:/Always/QianSai/_inbox \
    --out-dir report/verification/recalibration-algorithm-2026-11-01
```

`cases.json` 里每例都带 `decision`、`reason`、`metrics`；阈值与划分写在文件头，
可以只凭该文件判断结论是否仍然成立。
