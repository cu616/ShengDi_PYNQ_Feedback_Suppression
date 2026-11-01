# recal_algorithm 实现说明与适配清单 v1（B → C / A）

对应 C 的契约 `recal-product-v1.md`（在 C 分支 `docs/contracts/`，合并后才有链接）的"B算法函数"一节。
实现：`board/audio_replay/recal_algorithm.py`（自包含，只依赖 numpy）。
回归：`sim/feedback/test_recal_algorithm.py`（15 项）。
真实数据端到端：`report/verification/recalibration-algorithm-2026-11-01/`。

状态：**离线通过，待上板验证。** C 的 `recal_entry.sh` / `recal_product.py` 由 C 维护，本文件不碰。

## 1 入口

```python
from recal_algorithm import evaluate
reply = evaluate(request)          # 纯数值，不开设备、不写硬件
```

`evaluate` **不抛异常**：任何计算失败都转成 `decision="data_insufficient"` 并在 `reason` 里写明类型。
回复统一带 `contract / request_id / scene_id` 三个字段回显。

| phase | 判什么 | 允许的 decision |
|---|---|---|
| `input` | 讲话输入检查的采集能不能用（完整性/削顶/参考资格/宽带性/相干） | `valid_pass` / `data_insufficient` / `retry` |
| `fit` | 用 training 捕获拟合 512 抽头，判能不能装 | `valid_pass`（附 `model_path` + `model_sha256`）/ `retry` / `data_insufficient` / `model_rejected` |
| `validate` | 用独立 validation 捕获判"够不够格做抵消" | `valid_pass`（附 `qualifies_cancellation:true`）/ `model_rejected` / `data_insufficient` |

`retry` 只在 `attempt + 1 < attempts_total` 时给。`fit` 只在 `REJECT_SCALE`（尺度问题，换档可能变好）时给 `retry`；
`REJECT_SHAPE`（形状病态）与 `validate` 的任何失败都不 retry——重采一次同样的布置不会变好。

## 2 判据（全部有界，C 不猜）

### 2.1 采集资格 `input` / `fit` 的 training

拒收顺序固定，先命中的先返回：

| 顺序 | 判据 | 阈值 | 依据 |
|---|---|---|---|
| 1 | 形状/长度/有限值/dropped_frames/有效帧 | ≥ 4096 帧 | 512 抽头的 8 倍 |
| 2 | 满幅 | `|x| ≥ 0.999` 计数 > 0，或 `bit22=1` | 实测 mic 近满幅 14 帧即拒 |
| 3 | 参考资格 | `reference` 与 `source` 差 ≤ 0.01 dB 且相关 > 0.9999 | 反馈项不能还在环内 |
| 4 | 宽带性 | 谱 p95−p50 ≤ 20 dB | 多音实测 29–32 dB，白噪 8 dB |
| 5 | 相干门控率 | ≥ 30% | 部署模型训练批 73%、10-26 新布局 54% |
| 6 | 激励信噪比（兜底） | ≥ 0 dB | 只抓"激励没进来"（历史：mic 全零段 −326 dB） |

**第 5 条是主判据，第 6 条只是兜底。** 1 m 侧对布置下全局比值只有 3.9 dB 但相干 0.90、门控 73%，
是可用的数据；把 6 dB 当主判据会否掉部署模型自己的训练集（详见 `recalibration-policy-v1` 与
`report/verification/recalibration-policy-2026-11-01/`）。

### 2.2 拟合 `fit`

| 判据 | 阈值 | 处置 |
|---|---|---|
| 抽头数 | = 512 | `model_rejected` |
| 3N+3 | ≤ 2048 拍 | `model_rejected` |
| Q20 范围 | 有符号 24 位内 | `model_rejected` |
| 峰位 vs 本轮实测延迟 | 差 ≤ 4 帧 | `model_rejected`（时间原点错） |
| L1 | ≤ 4.0 | 超了：L1/max 在 25–80 内 → `retry`（尺度），否则 `model_rejected`（病态） |

`expected_peak_tap` 取本轮 `estimate_lag` 的中位，**不是上一个模型的峰位**：
50 cm 实测 127/128、100 cm 实测 183/184，差 56 帧全是声程，换摆位是正常用法。

### 2.3 独立验证 `validate` —— 只用逐段时间域残差

**这是本轮唯一改了口径的地方，原因是旧口径不稳。**

同一份数据（`bind4` 第 5/6 段做验证），好模型 = 部署模型，坏模型 = 旧夹具模型：

| 指标 | nperseg=2048 | 4096 | 8192 | 整段 | 结论 |
|---|---|---|---|---|---|
| 好模型 CD 中位 | 1.61 | 2.80 | 3.06 | 2.63 | 随口径漂 1.5 dB |
| 好模型 界差 | 4.36 | **9.24** | 3.42 | 2.76 | **随口径漂 6.5 dB，不能当判据** |
| 好模型 时域抑制 | 1.02 | 1.02 | 1.02 | 1.02 | **与口径无关** |

换成 300–460 Hz 带内时间域抑制后梯度更大：

| 模型 | 带内（300–460 Hz） | 全带（150–10000 Hz） |
|---|---|---|
| 部署模型（好） | **+4.17 dB**（逐段 3.47 / 4.94） | +2.12 |
| 旧夹具模型（坏） | **−4.40 dB** | −11.38 |
| 全零系数 | 0.00 dB | 0.00 |

**判定条件（全部满足才 `valid_pass`）：**

1. 至少 2 段验证捕获；
2. 每段带内抑制 ≥ 0（没有一段变差）；
3. 带内抑制中位 ≥ **+0.5 dB**（好 4.17、坏 −4.40，两侧余量 3.7 / 4.9 dB）；
4. 全带抑制中位 ≥ 0（没有把别的频段搞坏）。

CD 与界差仍算，但**只写进 `evidence.metrics` 的 `*_context_only` 字段，不参与判定**。
`evidence.not_asg = true` 固定存在，`meaning` 里写明这是 held-out 预测残差，不是 MSG/ASG，也不是听感结论。

**独立性的两条硬约束**：`capture_id` 与 `source_sha256` 都不能与 training 重叠，
任一重叠即 `data_insufficient`（不是失败，是测量不适用）。

## 3 预封装策略（C 的 `config['attempts']` 用这个）

三档，顺序是**低 → 标准 → 高**，每档给 `training` 与 `validation` 两个计划：

```python
ATTEMPTS = [
    {"training":   {"excitation": "white_noise", "rms_dbfs": -22.0, "frames": 16384,
                    "segments": 6, "peak_cap": 0.80},
     "validation": {"excitation": "white_noise", "rms_dbfs": -22.0, "frames": 16384,
                    "segments": 2, "peak_cap": 0.80}},
    {"training":   {..., "rms_dbfs": -19.3, ...}, "validation": {..., "rms_dbfs": -19.3, ...}},
    {"training":   {..., "rms_dbfs": -16.5, ...}, "validation": {..., "rms_dbfs": -16.5, ...}},
]
```

- **为什么从低往上**：C 的 retry 只能顺序前进。第一档低电平最不容易触满幅；不够再往上加。
  反过来（先高后低）会在第一档就撞 `bit22`，而且低档永远轮不到。
- **上限 −16.5 的理由**：白噪波形因数约 12 dB、`peak_cap=0.80` ⇒ 单 seed 可达上限约 **−17 dBFS**。
  −16.5 已是边缘；再高会削顶或（像 A 的旧脚本）被压成与上一档相同的 PCM。
- **raising excitation 只服务"让激励进得来"，不服务"让环环比开环高"**：判据里没有任何一处看 loop boost。
- 每档的 `rms_dbfs` 是**实际 RMS**，不是峰值。A 的采集端必须按 `make_excitation()` 的返回值落地，
  并用 `sha256` 证明两档不是同一个数组。

## 4 A 的适配清单（capture 落盘与元数据）

`recal_algorithm` 认两种落盘，任选其一，**同一个 scene 内必须统一**：

**A. npz（A 现有驱动的格式，推荐）**

| 键 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `reference` | float64 ±1 | 是 | 归一化到 ±1，不要给 int32 计数 |
| `microphone` | float64 ±1 | 是 | 同上 |
| `source_pcm16` | int16 或 float ±1 | 是 | int16 时按 /32768 折算 |
| `sample_rate_hz` | float | 是 | 48828.125 |
| `metadata_json` | str(JSON) | 建议 | 至少含 `first_frame`、`dropped_frames`、`bit22` |

**B. json**

```json
{"reference": [...], "microphone": [...], "source_pcm16": [...],
 "sample_rate_hz": 48828.125, "metadata": {"first_frame": 101780, "dropped_frames": 0, "bit22": 0}}
```

**其余要求**

1. `first_frame` 与 `source_pcm16` 必须同域：`source_pcm16` 是从第 0 帧开始的整条源，
   `first_frame` 是捕获窗在源时间轴上的起点。`len(reference)` 与 `len(source_pcm16) - first_frame`
   的最小值决定有效帧数——**源在窗口内必须 ≥ 16384 帧**，否则有效帧不够。
2. `source_sha256` 必须是**这一段的源**的哈希，不是文件名哈希。验证集会拿它和训练集比对独立性。
3. `content_kind`：开环激励写 `onboard_excitation`，讲话写 `human_private`。
4. **计算超时**：`compute_timeout_seconds` 对 `fit` 要给 **≥ 15 秒**。
   PC 上实测 fit 0.45 s / validate 0.10 s；PYNQ 的 ARM 慢 5–10 倍，3 秒会误杀。
5. `fit` 会把候选模型写到 `run_dir/candidate_model.json`，C 用返回的 `model_sha256` 核对，不要自己算。
6. 不改 `recal_entry.sh`、不改 `recal_product.py`、不碰 RTL。

## 5 与 `src/feedback/recal_policy.py` 的关系

板子上没有 `src/`，所以 `recal_algorithm.py` **自包含**实现了同一套阈值与判定。
两边由 `test_recal_algorithm.py::ParityWithPolicyTest` 对拍（同一输入必须同结论），
防止一份改了另一份忘改。改阈值时**两处一起改**，并同时更新本文件 §2 的表。

## 6 明确没有做的事

- 不把预测残差报成 MSG/ASG，不报听感。
- 不在 validate 里"没有保护就算通过"：触发 `bit22` 的验证捕获一律 `data_insufficient`。
- 不重采已有有效数据：`data_insufficient` 只在真的缺帧/缺身份时给，格式问题由 C 侧离线修。
- 不自动找最大增益工作点。

## 7 待上板验证

| 项 | 现状 | 需要什么 |
|---|---|---|
| 三档激励真的互异 | 合成数据验证过，板上未测 | 三档各一次，比 `sha256` |
| `peak_cap=0.80` 不触发 `bit22` | 设计值 | 每档记 `bit22` 与 mic 峰值 |
| −16.5 dBFS 是否可达 | 算出来的（波形因数 12 dB） | 板上确认 `reachable` |
| `fit` 在 PYNQ 上的耗时 | PC 0.45 s | 实测后定 `compute_timeout_seconds` |
| 验证判据的两侧余量 | 好 4.17 / 坏 −4.40，阈值 0.5 | 一次真实"好模型"与一次"错布置模型" |
| `source_sha256` 由 A 提供且正确 | 未联调 | A 的 `hw_api` 首次回包 |
