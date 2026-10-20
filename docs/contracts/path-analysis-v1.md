# 路径分析与稳定增益估算 v1（2026-10-20）

生产方：B  ·  消费方：A / C  ·  最后变更：2026-10-20（新增本地 --data-dir 入口）

状态：已实现并通过本地合成验证；真实数据待 A 在板上执行一次静默脚本。负责人为 B。
对应代码：`src/feedback/path_analysis.py`、`src/feedback/closed_loop_sim.py`、
`scripts/analyze_path.py`、`board/audio_calibrate/path_analysis_box_v1.py`。

## 1. 这个接口解决什么

现有评价只有一个数：宽带 RMS 预测误差降低多少 dB（6.92 / 9.80 dB）。但啸叫只发生在
一个频点上，稳定条件也只由一个频点决定：

```
闭环:  u = G·z^-2·(H - Ĥ)·u + 源       稳定条件: |G·(H-Ĥ)| < 1  对一切 f
所以:  MSG_bypass = 1/max|H|,  MSG_cancel = 1/max|H-Ĥ|
       ASG = max|H| / max|H-Ĥ|          (单位 dB)
```

宽带平均误差再低，只要有一个频点的 `|H-Ĥ|` 没压下去，MSG 就不会提高。本接口把
"平均降低多少 dB"换成"每个频点还剩多少"，并直接给出起振增益。

## 2. 输入

| 项目 | 约定 |
|---|---|
| 训练数据 | `training_box_v1.npz`（`calibration.load_capture` 格式），只用于拟合 |
| 验证数据 | `validation_box_v1.npz`，只用于评价；`capture_id` 必须与训练不同 |
| 模型 | `candidate_box_v1_256.json`，需含 `coefficients`（浮点）或 `coefficients_q20` |
| 采样率 | 必须一致；当前 48828.125 Hz |
| 频带 | 默认 20–20000 Hz。下界不低于 20 Hz，见第 5 节 |
| 运行位置 | **不需要板卡在线**。三个文件在哪个目录就在哪里跑，见下 |

两个入口跑的是同一份 `analyze_captures`，输出逐字节一致：

```text
本地（推荐）python scripts/analyze_path.py --data-dir <目录> --output <json>
板上         %run path_analysis_box_v1.py     （在 base/audio/audio_calibrate 下）
```

三个文件合计约 1 MB，内容为 PL 自己产生的伪随机噪声经箱体后的回采，
不含人声或对话；拷贝它们是文件传输，不是板卡操作。板卡只在采集与实测时需要。

## 3. 输出字段

写文件 `path_analysis_v1.json`，关键字段：

| 字段 | 含义 | 单位 |
|---|---|---|
| `shipped.broadband_reduction_db` | 现有口径，便于与历史记录对照 | dB |
| `shipped.cd_median_db` | 逐频点抵消深度中位数，正值为压下去 | dB |
| `shipped.cd_min_db` / `cd_min_at_hz` | **最差频点**，决定 ASG 的那个频点 | dB / Hz |
| `shipped.msg_bypass_conservative_db` | 旁路起振增益，`1/max|H|`，安全下界 | dB |
| `shipped.msg_bypass_phase_gated_db` | 旁路起振增益，只在相位过零点取 max，更接近真实 | dB |
| `shipped.msg_cancel_*` | 同上，模型开启时 | dB |
| `shipped.asg_conservative_db` / `asg_phase_gated_db` | 稳定增益差 | dB |
| `tap_sweep[]` | 128/256/512 重新拟合后的同口径结果，含 `core_cycles`、`fits_frame_budget` | — |
| `emphasis` | 按 `|H|` 加权拟合的候选及其系数 | — |
| `dc` | 直流偏置与 20 Hz 以下环路增益 | dBFS / dB |
| `howl_bypass[]` / `howl_cancel[]` | 相位过零点排序，含 `frequency_hz`、`gain_to_howl_db` | Hz / dB |
| `resonances[]` | `|H|` 局部极大，最先起振的地方 | Hz |
| `noise_ceiling` | 相干函数给出的逐频点上限，完美模型也越不过 | dB |
| `curve` | 抽稀后的 `freqs` / `cd_shipped_db` / `coherence`，供画图 | — |

两个 MSG 口径必须一起看：`conservative` 是"保证不会叫"的下限，
`phase_gated` 是"实际会在哪叫"。合成验证里真实值落在两者之间、靠近后者，
所以现场下限用 conservative，预期起振点用 phase_gated。

## 4. 增益口径与硬件上限

- 增益指 PL 的 Q4.12 数字增益，`4096 = 1.0 倍`，即 0 dB。
- 硬件允许 1..32768，即 **最大 8 倍 = +18.06 dB**。超过就不用算了。
- 所有 MSG 都绑定当次的 `hp_volume`：`H` 随音量线性缩放，
  改音量后 MSG 按 −ΔdB 平移。换音量必须重跑或换算，不能直接沿用。

## 5. 已知限制

- 是模型预测，不是实测 MSG/ASG。声学路径漂移、模拟失真、箱体移动都不在里面。
- 抵消深度的可测上限受分段数限制（4096 点窗、50% 重叠、32768 帧 = 15 段时约 49 dB）。
  低于这个量级的差异不可信，但远高于我们关心的 0–20 dB。
- 20 Hz 以下单独用 `dc` 报告：RTL 不减 bias，残差会带直流进环路。
- `phase_gated` 依赖相位零点附近的 `H` 估计精度，窄共振处要留意栅格分辨率（约 12 Hz）。

## 6. 变更记录

- v1（2026-10-20）：首版。新增逐频点口径、双 MSG 口径、抽头扫描、加权候选、直流诊断。
  不改变任何既有模型格式、RTL 接口或寄存器；`coefficients_q20` 与现有加载方式完全兼容。
