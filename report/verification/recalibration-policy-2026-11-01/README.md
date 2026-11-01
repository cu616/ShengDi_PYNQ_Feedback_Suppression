# 一键重标定的数值决策层（2026-11-01）

把"看曲线后拍板"换成有界规则。本目录是它的离线复核：用**已经发生过的真实情况**逐例给出机器判定与理由。
契约见 [`docs/contracts/recalibration-policy-v1.md`](../../../docs/contracts/recalibration-policy-v1.md)。

- 实现：`src/feedback/recal_policy.py`（判定）、`src/feedback/excitation.py`（激励生成）
- 复核：`python scripts/recal_offline_cases.py` → 本目录 [cases.json](cases.json)
- 回归：`python -m unittest sim.feedback.test_recal_policy`（31 项）

**状态：离线通过，待上板验证。** 与本仓库既有的算法验证（CD、ASG、三点）分开记，不互相引用为证据。

## 0 三句话

1. 四类判定（采集 / 激励 / 拟合 / 验证）+ 一条选点规则，全部有界：重试最多 2 次、激励阶梯 3 档、
   验证至少 2 个预选点，任何一步给不出可用结论就停，**不自动安装**。
2. 复核 8 例真实历史情况，7 例与预期一致；例外是"10-28 的 322 Hz 单点 PASS"——
   新规则要求 ≥2 点，它现在判 `INCONCLUSIVE/DATA_INSUFFICIENT`。**历史上的单点"通过"比新标准松**。
3. 复核过程中改了两处判据，都不是为了让结果通过，是因为**标准与已发生的事实矛盾**：
   一个阈值会把部署模型自己的训练集判成不可用，一个基准会把正常的换摆位判成换错布置。下面 §2 给证据。

## 1 覆盖了什么

| 队长指定的情况 | 复核样本 | 机器判定 |
|---|---|---|
| 旧模型失配 | `candidate_512.json`（0.5 m，峰位 125）装到 1 m 数据 | `REJECT_SHAPE`：峰位差 −59 帧 |
| 低信噪比 | room256 `seg_3`（麦克风里无相干成分） | `REJECT_EXCITATION`：snr −326.7 dB |
| 输入削顶 | `mic_check_after_repair.npz`（mic 近满幅 14 帧） | `REJECT_CLIP` |
| 322 Hz 正收益 | 10-28 三点（boost 3.75 / acoustic 4.76） | `INCONCLUSIVE`：只有 1 点 |
| 322 Hz 残留正反馈 | 10-31 重拟合候选（acoustic −0.22 / over −2.19） | `FAIL` / `MODEL_UNQUALIFIED` |
| 322 Hz 无环路提升 | 构造 boost 0.2（仅覆盖分支，非实测） | `INCONCLUSIVE` / `MEASUREMENT_INAPPLICABLE` |
| 50 cm 局部改善 | `side16` 四段 + `model_512_side.json` | `INCONCLUSIVE` / `DATA_INSUFFICIENT`（缺三点） |

`50 cm` 那例的采集与模型都合格（四段全 `OK`，snr 中位 9.3；模型 `DEPLOYABLE_FIT`，
峰位 128 与实测 128 对齐），**但没有三点数据，因此不自动安装**——这正是"采集合格 + 模型可部署
≠ 抵消有效"的可执行版本。

## 2 复核过程中修正的两处判据

### 2.1 `MIN_EXCITATION_SNR_DB` 6.0 → 0.0，主判据改为相干门控率

原阈值把**部署模型自己的训练集**判成不可用：

| 批 | snr 中位 | 相干中位 | 门控（coh≥0.8 占比） | 旧阈值下 |
|---|---|---|---|---|
| `bind4`（`rewired_512_20261026` 的来源） | **3.9 dB** | 0.90 | **73%** | `REJECT_EXCITATION` ✗ |
| `calib6`（10-26 新布局） | 3.9 dB | 0.83 | 54% | `REJECT_EXCITATION` ✗ |
| `side16`（50 cm） | 9.4 dB | 0.91 | 76% | `OK` |
| `lowband2` | 15.7 dB | 0.98 | 95% | `OK` |

`bind4` 与 `side16` 的相干水平几乎一样，却因为全局比值低 5.5 dB 被拒。原因是这个量是
`10log10(Σcoh·Syy / Σ(1−coh)·Syy)`：在 1 m 侧对布置下，麦克风拾到大量不相干的环境/反射能量，
它压低全局比值，但没有毁掉"哪些 bin 可用"。

改成：**主判据 `coherence_gated_ratio ≥ 0.30`，SNR 退回兜底 `≥ 0 dB`**（只抓"激励完全没进来"，
历史同类是 mic 全零段，snr −326 dB）。全库 118 份的判定分布随之从
`OK 94 / REJECT_EXCITATION 15` 变为 `OK 106 / REJECT_EXCITATION 3`。

### 2.2 `check_fit` 的峰位基准改为**本轮实测延迟**

原实现拿"上一个模型的峰位"当基准，于是 50 cm 重标定（模型峰位 128、实测延迟 127/128）
被判成"换的不是同一套声学布置"——而这恰恰是换摆位的**正常结果**：

| 布置 | 实测 ref→mic 延迟 | 模型峰位 |
|---|---|---|
| 50 cm 侧放（`side16`） | 127 / 128 | 128 |
| 100 cm 侧对（`bind4`） | 183 / 184 | 184 |

差 56 帧全是声程。参数改名为 `expected_peak_tap`，语义写死为"本轮 `estimate_lag` 的整数延迟"；
`base_peak_tap` 作为旧名保留，等价。回归里钉了两条：同一份 128 峰位的模型，
配 `expected=128` 判可部署、配 `expected=184` 判拒收。

## 3 激励生成的问题（队长指出的第一条风险）

`board/audio_replay/pick_excitation_level.sh` 的写法是"先按目标 RMS 归一，再按峰值上限整体缩放"：

```python
x = x / rms(x) * 10**(level/20)
pk = max(abs(x))
if pk > 0.80: x *= 0.80 / pk        # 三档在这里全部被压到峰值 0.80
return rint(x * 32767)
```

白噪波形因数约 12 dB，所以 `-13.3 / -7.3 / -4.3 dBFS` 三档的峰值都在 0.80 以上，
缩放后**是同一份 PCM**：一个"电平扫描"扫的是同一个数组，等于报了三次尝试、只测了一个条件。

`src/feedback/excitation.py` 改成按 RMS 定档、峰值上限只判可达性：目标不可达时返回 `ok=False`
与可达上限，不削顶、不降档伪装。`check_distinct()` 比较 int16 字节流摘要，
是"相同 PCM 不能当多个档位"的机器执行点。

同时把 `plan_excitation` 的触发条件钉死为 `check_capture` 的相干/SNR 与输入余量，
**不看"闭环比开环高 3 dB"**——环路提升是结果，用它当激励够不够的条件等于用结果倒推前提。

## 4 明确不知道的

- **没有一次"采集 → 拟合 → 三点 → 安装"的完整闭环记录。** 本轮是离线复核，不是现场跑通。
- **10-28 的 322 Hz 只有单点读数**，没有第二个频点的同轮记录，所以 `PASS` 在新规则下不成立。
- **50 cm 布置没有三臂读数**，`E` 例只能到 `INCONCLUSIVE`。
- **`OVER_PRED_TOLERANCE_DB = 1.5` 未在真实复 `H` 上验证过**：它需要同一轮的开环复 `H` 与三点读数，
  历史数据里没有这种配对。
- **选点规则只在历史 `H` 上算过**，没有在"装模型之前现场选点、装完复测"的流程里跑过。
- **激励阶梯的 −20 dBFS 顶档**是否在所有 seed 上可达未验证：单 seed 上限约 −17 dBFS 是算出来的，
  没有板上确认。

## 5 待上板验证（与既有算法验证分开）

| 项 | 判据 |
|---|---|
| 三档激励真的是三个数组 | `check_distinct()` 返回 True，且三档 `sha256` 互异 |
| `peak_cap=0.80` 不触发 `bit22` | 每档记 `bit22` 与 mic 峰值 |
| 采集判定在真实新采数据上给 `OK` | `check_capture` 的 `metrics` 与 A 的原始记录一致 |
| 选点规则给得出 2–3 个点 | 一次开环采集后看返回点数与 `loop_gain_db` |
| 三点判据的四种 `cause` 都能被真实触发 | 至少 `PASS` 与 `MODEL_UNQUALIFIED` 各一次 |

## 6 复现

```bash
python -m unittest sim.feedback.test_recal_policy
python scripts/recal_offline_cases.py \
    --inbox D:/Always/QianSai/_inbox \
    --out-dir report/verification/recalibration-policy-2026-11-01
```

`cases.json` 里每个 case 都带 `inputs`（文件路径与关键值）、`status`、`metrics`、`reasons`，
以及能复现该结论的最小信息。三点的两个真实样本（10-28、10-31）在脚本顶部硬编码并注明来源，
**不是从 npz 重算**——那两轮的三臂读数是 A 的收据，原始 PCM 不在本仓库。
