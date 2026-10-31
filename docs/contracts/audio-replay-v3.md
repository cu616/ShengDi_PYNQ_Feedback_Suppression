# audio-replay v3（宽残差过增益后再钳位）

状态：已定冻结主线（队长 2026-10-28）；驱动 bit22 停声已改并软件验证 16 项通过；上板复验与 C 增量验收未闭合
生产方：A · 消费方：A / B / C
最后变更：2026-10-28 原因：队长决定 v3 为冻结主线，并授权把输入满幅改为停声条件；补位流/驱动配对校验。

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
u[n] = sat24((s[n] << 8) + sat24(round_shift12(g · w[n-2])))
```

**增益单位写准（C 2026-10-27 指出）**：`g` 就是 `control[31:16]`，**无符号 16 位、12 位小数**
（即 Q4.12：`g_q12/4096`，范围 `0…8.0`）；`round_shift12(x)` 指乘完右移 12 位并四舍五入。
这里**不存在"Q12 系数"**——系数是 24 位 Q20，与增益字不是同一格式，不能互相套用。

**勘误（2026-10-27，B 指出）**：本节最初写成「`g ≤ 1`（`control[31:16] ≤ 32768`，Q4.12）」，
两半自相矛盾——Q4.12 下 `32768/4096 = 8.0`，寄存器上限对应的是 **`g ≤ 8`（+18.06 dB）**，不是 1。
算术结论不变，只是适用范围写小了：`|w| ≤ 2^24`、`g ≤ 8` 时 `g·w ≤ 2^39`，
仍落在 41 位有符号乘积（上限 `2^40−1`）内，增益后照样能精确钳到 24 位。
**现场授权的工作范围**（`[−14, −6] dB`，即 `g < 1`）是另一件事，由现场门禁决定，不因这个上限放宽。

`g ≤ 8`（`control[31:16] ≤ 32768`，Q4.12）时 `g·w` 一定落在 41 位乘积内、并可在增益后精确钳到 24 位；
钳位点由「增益前」移到「增益后」，因此 1.02× 满幅的残差不会像 v2 那样被当成本身满幅再乘增益。

## 为什么改

现场证据（[候选臂失败](../../report/verification/audio-replay/live-speech-two-arm-2026-10-27.json)、
[越界归因](../../report/verification/audio-replay/residual-overflow-result-2026-10-27.json)）：
语音瞬态上 `residual_saturations=8` 而 `prediction_saturations=0`，
宽残差 1.0230× 满幅、**增益后只有 0.4074× 满幅（余量 +7.80 dB）**。
即 v2 停的是一次没有危险输出的数值溢出。v3 后这类试次能继续跑，钳位由增益后负责。

## 输入满幅是独立检测（bit22），并且**是停声条件**

零系数时 `e = m`，残差恒等于麦克风、永不越界，**残差计数天生看不见输入过载**；
历史证据里「`residual_saturations=0` 所以没有再生/没有过载」的推论因此无效。
v3 由 `rx_left == 24'sh7fffff || 24'sh800000` 直接判输入满幅，粘滞到本次 arm 清零，
报在 `capture_status` **bit22**；计数只累加不导出，导出的是粘滞位。

**把两件事分开写（队长 2026-10-28 要求）**：

| | 可见 | 自动停声 |
|---|---|---|
| 输入满幅 | `capture_status` bit22（粘滞），驱动写入 `input_full_scale_seen` | **是**：驱动轮询发现即停，`stop_reason = "input_clip"`，走既有 disarm/mute/保存/恢复路径；收尾再查一次该位，避免末次轮询漏掉 |
| 增益前残差越界 | `saturation_counts[31:16]` 与 `residual_saturations` | **否**：只计数、只上报，不停声 |

「输入过载可见」不等于「输入过载会自动停声」——v3 交付时两者都有；早期只做了前者。

现场判据：**bit22 置位或 `stop_reason="input_clip"` 的试次判无效**（输入已削顶），
不得用它证明抗啸叫或增益收益。

### 停声原因全集（驱动侧）

`completed`（跑满） / `guard`（预测饱和、增益后饱和、混音饱和） / `input_clip`（bit22） /
`fault`（`capture_status` bit17/bit18） / `incomplete`（未跑满且无 fault） / `exception`（异常路径）。
`completed` 与 `input_clip` 互斥：即使帧数跑满，收尾查到 bit22 也标 `input_clip`。

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

- **混搭在位流装载前就被拒绝**（队长 2026-10-28 第 5 项）：驱动里带
  `EXPECTED_BIT_SHA256` / `EXPECTED_HWH_SHA256`，`verify_paired_bitstream()` 在**下载 overlay 之前**
  比对同目录的 `audio_replay.bit` 与 `.hwh` 的 sha256，不一致直接 `RuntimeError`，不发声、不留证据。
  所以下面的混搭情形在 v3 驱动 + 任意旧位流下**跑不起来**，这是有意的。
- **v3 位流 + v2/v1 驱动**：驱动会把增益前残差溢出当停声条件，遇到语音瞬态仍会早停；
  数据本身合法，但这不是 v3 想要的语义。
- **v3 驱动 + v2/v1 位流**：被上面的校验拒绝。
- 位流与驱动**必须同版本发布**；[兼容清单](../../report/verification/audio-replay/residual-compat-change-list-2026-10-27.json)
  里的要求由此从"约定"变成"运行时强制"。

## 验证状态（分层，勿混）

| 层次 | 状态 | 证据 |
|---|---|---|
| 代码生成 | 完成 | `src/rtl/feedback_fir.v`、`src/rtl/audio_pl_replay.v` |
| 仿真（FIR） | 通过 | `RESIDUAL_WIDE_PASS checked=4`；`FEEDBACK_FIR_PASS samples=2304`（含宽残差逐样本） |
| 仿真（replay） | 通过 | `RESIDUAL_REPLAY_WIDE_PASS`（iverilog + xsim 双跑，乘后钳/增益后钳/输入满幅三例） |
| 软件验证（停声语义） | 通过（12 项） | `board/audio_replay/test_runtime_stop.py`：bit22→`input_clip`、增益前残差单独越界不停、预测/增益/混音仍停 |
| 综合实现 | 见 STATE「关键数字」 | `build/work/audio_replay/timing.txt`；**已施加约束满足**，四项外部 I/O 延迟约束缺口仍在 |
| 上板 | 见 STATE | 现场两臂；**bit22 停声、混搭拒绝、60 秒连续两次已在硬件上验证**（2026-10-28） |
| 现场 | 见 STATE | 稳态纯音 + 真人语音两臂 |

## 回退

几何与位段之外的语义回退 = 重新部署 v2 包（`/home/xilinx/jupyter_notebooks/base/audio/audio_live`，
位流 `61bb71aa…`）；v1 回退位流同在其目录内。零系数 −8 dB、手机 5 cm/8-15 的成功基线不依赖本版。

## 增量：v3-sw（物理算法开关）

状态：**仅构建与仿真通过，未上板**（2026-10-31）。包位置 oard/audio_replay/v3-sw/，
带自己的 manifest；**坐标只与 v3-sw 的 bit/hwh/驱动配对**，与 v3 的 48e38f78… 不可混用。

| 项 | v3 | v3-sw |
|---|---|---|
| 位流 / hwh | 48e38f78… / 9411adb5… | 30438cef… / 4de00140… |
| 新增输入 | 无 | **SW0（M20）**，两级同步后与 control[1] 或运算：高处 = 强制旁路（关抵消） |
| capture_status bit23 | 未使用（恒 0） | **开关状态**（同步后的值），0 = 未强制旁路 |
| 算法 / 定点 / 增益 / 调度 | — | **与 v3 完全相同**，不因开关改变 |
| 保护 | 不变 | 不变；**旁路不在 fault 条件里**，所以运行中可切 |
| 时序 | WNS +0.548 / WHS +0.015 | WNS **+0.954** / WHS **+0.023**（已施加约束满足，外部 I/O 延迟约束仍缺） |
| LUT | 3588 | 3589（+1，两级同步器） |

未上板意味着：**不能声称该位流在硬件上验证过**。上板前四项检查（混搭拒绝、静默自检、
输入满幅停声、连续运行）必须用 v3-sw 的驱动与载荷重跑一次。
