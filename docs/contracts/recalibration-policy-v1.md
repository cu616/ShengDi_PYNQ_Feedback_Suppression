# 一键重标定的数值决策接口 v1（B → C）

状态：**待上板验证**。本契约定义 B 侧可调用的判定函数；C 的状态机按这里的顺序调用，
不自己改阈值、不自己解释 `metrics`。实现见 `src/feedback/recal_policy.py`，
回归见 `sim/feedback/test_recal_policy.py`。

## 0 边界

- 只做判定：不采集、不碰板卡、不加载模型文件、不改 RTL。输入是数组与字典，输出是字典。
- 保持既有语义：512 抽头、`lag_first=1`、Q20（`signed24_fraction20`）、参考对齐、宽残差。
- 不引入 AFC / 多速率 / 新滤波家族。
- 阈值集中在 `recal_policy.py` 顶部一节，是本契约的唯一数值来源。改阈值必须同时改回归钉值。

## 1 调用顺序

```
capture ──REJECT_*──> plan_excitation ──> (重采) ──> capture
   │OK
   ▼
fit (check_fit) ──REJECT_*──> 停，不装
   │DEPLOYABLE_FIT
   ▼
three_point (check_three_point) ──FAIL / INCONCLUSIVE──> 停，不装
   │PASS
   ▼
装模型 + 记收据
```

`decide()` 是这个顺序的现成封装；**默认 `require_three_point=True`**，
缺三点数据时返回 `INCONCLUSIVE/DATA_INSUFFICIENT`，不会返回"可安装"。

## 2 五个函数

| 函数 | 回答 | 输出 `status` |
|---|---|---|
| `check_capture(ref, mic, fs, metadata, source=None)` | 这份采样能不能用来拟合 | `OK` / `REJECT_INTEGRITY` / `REJECT_CLIP` / `REJECT_REFERENCE` / `REJECT_EXCITATION` / `REJECT_COHERENCE` |
| `plan_excitation(capture_check, attempt)` | 下一次激励怎么调，或者停 | `NO_ACTION` / `RAISE_EXCITATION` / `EXCITATION_CEILING` / `EXHAUSTED` |
| `select_probe_frequencies(H, freqs, coherence, gain_db)` | 三点测哪几个频点 | 频点列表（可能少于 3 个） |
| `check_fit(coeff_q20, fs, expected_peak_tap=...)` | 这个模型能不能装 | `DEPLOYABLE_FIT` / `REJECT_SCALE` / `REJECT_SHAPE` |
| `check_three_point(points, gain_db=...)` | 测量支不支持启用 | `PASS` / `FAIL` / `INCONCLUSIVE`（+`cause`） |

`check_three_point` 的 `cause` 四分类（彼此不替代）：

| `cause` | 含义 | 处置 |
|---|---|---|
| `HARDWARE_ERROR` | 任一臂饱和计数非零 | 查硬件，不重测算法 |
| `MEASUREMENT_INAPPLICABLE` | 三臂不同源，或所有点都没有可收回的环路提升 | 修测量条件，不算成败 |
| `MODEL_UNQUALIFIED` | 抵消臂比零臂还响，或过冲越界 | 换模型 |
| `DATA_INSUFFICIENT` | 可判频点 < 2，或缺三点数据 | 补测量，不自动装 |

## 3 最小输入 / 输出样例

### 3.1 采集判定

```python
from feedback.recal_policy import check_capture
got = check_capture(reference, microphone, 48828.125,
                    metadata={"dropped_frames": 0, "bit22": 0, "first_frame": 101780},
                    source=source_pcm16)      # source 可选；给了就核"参考是否纯源"
```

```json
{
 "schema_version": 1,
 "status": "OK",
 "metrics": {
   "frames": 16384, "valid_frames": 15407, "taps": 512,
   "ref_rms_dbfs": -19.48, "mic_rms_dbfs": -32.93, "mic_over_ref_db": -13.45,
   "ref_peak": 0.2163, "mic_peak": 0.0421,
   "fullscale": {"reference_near": 0, "microphone_near": 0, "bit22": 0},
   "coherence_median": 0.90, "coherence_gated_ratio": 0.73,
   "excitation_snr_db": 3.9, "spectral_spread_db": 8.1
 },
 "reasons": [],
 "next": {"kind": "fit", "why": "可以进入拟合"}
}
```

**C 只需要读 `status` 与 `next.kind`。**`metrics` 进收据，不参与分支。

### 3.2 激励规划

```python
from feedback.recal_policy import plan_excitation
plan = plan_excitation(capture_result, attempt=0)   # attempt = 已失败次数
```

```json
{
 "status": "RAISE_EXCITATION",
 "action": {"kind": "raise_excitation", "target_rms_dbfs": -24.0,
            "achieved_rms_dbfs": -24.0, "peak": 0.62,
            "sha256": "9f1c…", "frames": 16384},
 "reasons": ["当前 ref_rms -30.7 dBFS，抬到 -24.0 dBFS（实际达成 -24.0）"],
 "attempt": 0
}
```

- 阶梯固定 `(-30, -24, -20) dBFS`，**最多重试 `MAX_ATTEMPTS=2` 次**，之后 `EXHAUSTED`。
- 目标在该 seed 的峰值上限下达不到时返回 `EXCITATION_CEILING`，**不削顶、不降档伪装**。
- **不看"闭环比开环高 3 dB"。** 环路提升是结果，不是激励够不够的条件。

### 3.3 选点

```python
from feedback.recal_policy import select_probe_frequencies
probes = select_probe_frequencies(H, freqs, coherence, gain_db=-8.0, n_probe=3)
```

```json
[{"frequency_hz": 322.2, "bin": 108, "loop_gain_db": 3.78,
  "magnitude_h_db": 11.78, "coherence": 0.97},
 {"frequency_hz": 405.1, "bin": 136, "loop_gain_db": 2.91, "magnitude_h_db": 10.91, "coherence": 0.94}]
```

- **只用开环 `H` 与增益，完全不看 cancel 数据**；装模型之前就定好，装完不能改。
- 规则：相干 ≥ 0.8 且落在 150–10000 Hz 的 bin，按 `g|H|` 降序，贪心取互相间隔 ≥ 1/3 倍频程。
- 返回少于 3 个是合法结果，由 `check_three_point` 判 `DATA_INSUFFICIENT`。

### 3.4 模型可部署性

```python
from feedback.recal_policy import check_fit
fit = check_fit(coefficients_q20, 48828.125,
                expected_peak_tap=184)   # 本轮 estimate_lag 的整数延迟，不是旧模型的峰位
```

```json
{
 "status": "DEPLOYABLE_FIT",
 "metrics": {"taps": 512, "L1": 2.288, "max_abs": 0.0457, "L1_over_max": 50.1,
             "peak_tap": 184, "expected_peak_tap": 184, "peak_tap_delta": 0,
             "q20_in_range": true, "q20_sha256": "6118e85d…",
             "hardware_cycles": 1539, "memory_ms": 10.49},
 "reasons": [],
 "next": {"kind": "install_and_verify"}
}
```

- `REJECT_SCALE`（L1 大但 L1/max 正常）与 `REJECT_SHAPE`（两者都异常）**处置不同**，不要合并。
- `expected_peak_tap` 必须来自**本轮**采集；用上一套布置的模型峰位当基准，会把正确的重标定判成换错布置
  （50 cm 实测 127/128 vs 100 cm 的 183/184，差 56 帧全是声程）。

### 3.5 三点验证

```python
from feedback.recal_policy import check_three_point
verdict = check_three_point(
    [{"frequency_hz": 322.2, "open_db": 45.44, "bypass_db": 49.19, "cancel_db": 44.43}, ...],
    gain_db=-8.0,
    saturation_counts={"prediction": 0, "residual": 0, "mix": 0},
    source_sha=[sha_open, sha_bypass, sha_cancel])
```

```json
{
 "status": "PASS",
 "cause": null,
 "points": [{"frequency_hz": 322.2, "boost_db": 3.75, "acoustic_db": 4.76,
             "overshoot_db": 1.01, "status": "PASS", "why": "收回 +4.76 dB，过冲 +1.01 dB"}],
 "reasons": ["2/2 个预选频点收回环路提升且未引入正反馈"]
}
```

判定顺序固定（先排除"这个测量不能用"，再谈"抵消有没有效"）：
`硬件饱和` → `三臂同源` → `该点有没有可收回的提升` → `抵消有效性` → `实测与离线预测一致性`。

三个量恒等，不可能同时任意取：`acoustic = boost + over`。

## 4 默认参数与适用条件

| 参数 | 默认 | 适用条件 / 依据 |
|---|---|---|
| 评价频带 | 150–10000 Hz | 采样率 48828.125；低于 150 Hz 未验证 |
| `COHERENCE_FLOOR` | 0.8 | 历史各批相干中位 0.83–0.98 |
| `MIN_GATED_COHERENCE` | 0.30 | 部署模型训练批门控 73%、10-26 新布局 54%，取 0.30 留余量 |
| `MIN_EXCITATION_SNR_DB` | 0.0 | 只抓"激励完全没进来"（历史：mic 全零段 −326 dB）；**不是主判据** |
| `SPARSE_LINE_DB` | 20.0 | 多音谱 p95−p50 ≈ 29–32 dB，白噪 ≈ 8 dB |
| `MIN_VALID_FRAMES` | 4096 | 512 抽头的 8 倍 |
| 激励阶梯 | −30 / −24 / −20 dBFS | 峰值上限 0.80、白噪波形因数 ≈ 12 dB ⇒ 单 seed 上限约 −17 dBFS |
| `MAX_ATTEMPTS` | 2 | 阶梯三档，最多试三次就退出 |
| `L1_MAX` | 4.0 | 部署 2.288、10-26 新布局 2.151 |
| `PEAK_TAP_TOLERANCE` | 4 帧 | 段间实测延迟离散 1.0–1.5 帧 |
| `BOOST_MIN_DB` | 0.5 | 低于它该点没有可收回的增益 |
| `OVER_MIN_DB` / `ACOUSTIC_MIN_DB` | −1.5 / 0.0 | 抵消臂不得比零臂更响；过冲下界 |
| `MIN_PASSING_PROBES` | 2 | 单点不构成结论 |

## 5 明确没有做的事

- **不自动寻找最大增益工作点。** 本轮只做"可靠重标定 + 明确工作配置"。
- **不把离线预测量、单频改善输出成 MSG/ASG。**
- **不因 `AUX` 能否调而改变判据。** 输入余量只用实际输入数据判（`fullscale` 计数），不靠距离推断。
- **改变 AUX 或激励档位后模型必须重新拟合**，不复用旧档模型。

## 6 待上板验证（与既有算法验证分开记）

| 项 | 现状 | 需要什么 |
|---|---|---|
| 全流程串起来 | 各函数离线通过，未在板上串联 | A 一次采集 + C 状态机跑通 |
| 激励阶梯的峰值上限 | 0.80 为设计值，未在板上确认 `bit22` 行为 | 三档各一次，记 `bit22` 与峰值 |
| 选点规则在真实 `H` 上是否给 2–3 点 | 只在历史 `H` 上算过 | 一次开环采集后看返回点数 |
| `OVER_PRED_TOLERANCE_DB` | 1.5 dB，未在真实复 `H` 上验证 | 三点数据 + 复 `H` |
