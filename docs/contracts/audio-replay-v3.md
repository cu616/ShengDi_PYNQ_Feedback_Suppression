# audio-replay v3（宽残差过增益后再钳位）

状态：实现待验证（RTL 仿真通过、综合与上板见下）
生产方：A · 消费方：A / B / C
最后变更：2026-10-27 原因：队长批准「25 位宽残差过数字增益后再做最终钳位」，修正残余溢出被误当成输出溢出。

v1 见 [audio-replay-v1](audio-replay-v1.md)，v2 见 [audio-replay-v2](audio-replay-v2.md)。
本版**不放宽任何输入保护**：预测饱和、增益后饱和、混音饱和、协议错误、超时、手动停止照旧。

## 唯一变更

| 项 | v2 | v3 |
|---|---|---|
| 增益前残差 | 先 `sat24(m−p)` 再乘增益 | **直接乘 25 位未钳残差**，钳位只在增益后做一次 |
| `capture_status` bit22 | 未使用（恒 0） | **输入满幅粘滞标志** `input_full_scale_seen` |
| 增益前残差计数（`saturation_counts[31:16]`） | 驱动收到即停声 | **只作诊断**；预测半（`[15:0]`）、增益后、混音仍停声 |

帧关系改为（其余同 v1）：

```text
p[n] = FIR_Q20(u[n-1], u[n-2], ...)          # 24 位
w[n] = m[n] - p[n]                            # 25 位，未钳，增益前
e[n] = bypass ? m[n] : sat24(w[n])            # 24 位，仅作诊断/捕获，含义与 v1 完全一致
u[n] = sat24((s[n] << 8) + sat24(round_Q12(g · w[n-2])))
```

`g ≤ 1`（`control[31:16] ≤ 32768`，Q4.12）时 `g·w` 一定落在 41 位乘积内、并可在增益后精确钳到 24 位；
钳位点由「增益前」移到「增益后」，因此 1.02× 满幅的残差不会像 v2 那样被当成本身满幅再乘增益。

## 为什么改

现场证据（[候选臂失败](../../report/verification/audio-replay/live-speech-two-arm-2026-10-27.json)、
[越界归因](../../report/verification/audio-replay/residual-overflow-result-2026-10-27.json)）：
语音瞬态上 `residual_saturations=8` 而 `prediction_saturations=0`，
宽残差 1.0230× 满幅、**增益后只有 0.4074× 满幅（余量 +7.80 dB）**。
即 v2 停的是一次没有危险输出的数值溢出。v3 后这类试次能继续跑，钳位由增益后负责。

## 输入满幅是独立检测（bit22）

零系数时 `e = m`，残差恒等于麦克风、永不越界，**残差计数天生看不见输入过载**；
历史证据里「`residual_saturations=0` 所以没有再生/没有过载」的推论因此无效。
v3 由 `rx_left == 24'sh7fffff || 24'sh800000` 直接判输入满幅，粘滞到本次 arm 清零，
报在 `capture_status` **bit22**；计数只累加不导出，导出的是粘滞位。

现场判据：**bit22 置位的试次判无效**（输入已削顶），不得用它证明抗啸叫或增益收益。
驱动把该位解成 `input_full_scale_seen` 写入证据元数据。

## 位段（完整，供 C 校对）

```text
capture_status[0]      done
capture_status[16:1]   captured（环形已写帧数，上限 16384）
capture_status[17]     arm && !config_ok
capture_status[18]     fault | fir_error
capture_status[19]     prediction_clip_seen
capture_status[20]     residual_clip_seen（增益前，v3 起仅诊断）
capture_status[21]     gain_clip_count != 0（增益后）
capture_status[22]     input_clip_seen  ← v3 新增
capture_status[31:23]  0
```

`coefficient_status` 未变。

## 兼容性

- **v3 位流 + v2/v1 驱动**：驱动会把增益前残差溢出当停声条件，遇到语音瞬态仍会早停；
  数据本身合法，但这不是 v3 想要的语义。**必须同版本配对**。
- **v3 驱动 + v2/v1 位流**：bit22 恒 0，`input_full_scale_seen` 恒 false；
  其余位段相同，不会误报，但**拿不到输入过载证据**，不得据此宣称未削顶。
- 混搭可运行但**不得作为现场证据**；[兼容清单](../../report/verification/audio-replay/residual-compat-change-list-2026-10-27.json)
  里的「位流 + 驱动 + schema 必须同版本发布」仍然有效。

## 验证状态（分层，勿混）

| 层次 | 状态 | 证据 |
|---|---|---|
| 代码生成 | 完成 | `src/rtl/feedback_fir.v`、`src/rtl/audio_pl_replay.v` |
| 仿真（FIR） | 通过 | `RESIDUAL_WIDE_PASS checked=4`；`FEEDBACK_FIR_PASS samples=2304`（含宽残差逐样本） |
| 仿真（replay） | 通过 | `RESIDUAL_REPLAY_WIDE_PASS`（iverilog + xsim 双跑，乘后钳/增益后钳/输入满幅三例） |
| 综合实现 | 见 STATE「关键数字」 | `build/work/audio_replay/timing.txt` |
| 上板 | 见 STATE | 现场两臂 |
| 现场 | 见 STATE | 稳态源 + 真人语音两臂 |

## 回退

几何与位段之外的语义回退 = 重新部署 v2 包（`/home/xilinx/jupyter_notebooks/base/audio/audio_live`，
位流 `61bb71aa…`）；v1 回退位流同在其目录内。零系数 −8 dB、手机 5 cm/8-15 的成功基线不依赖本版。
