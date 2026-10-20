# Closed v1：同一配置的抵消/旁路

状态：已实现并通过整板构建；未上板做效果验收。
生产方：C  ·  消费方：A / B  ·  最后变更：2026-10-19（集成闭环最小版）

独立audio_pl_closed，保留feedback_fir、I2S和audio_residual原样。100MHz/2048=48828.125Hz，Codec在运行时设50MHz PLL。接口已通过本地线级仿真及整板构建，尚未上板验证。

- control bit0保持arm（0立即静音）；bit1为bypass；bits31:16为无符号Q4.12增益，允许0..32768（0..8倍），启动时锁存。只有bit1可在运行中切换，在下一次ADC样本接收时锁存；两模式共用FIR计算时隙、增益、限幅和输出调度。
- frame_limit：1..488281帧（不超过10秒），启动锁存；软件首次试验默认0.5秒、负增益。不自动扫MSG。
- FIR参考为当前串行帧实际tx_word。FIR返回的residual（旁路时为mic）经Q4.12乘法、半值远离零舍入和24位饱和进入u_hold；仅divider=2047时将已完成u_hold送入tx_word。允许开始两帧为零填充，之后缺新结果立即故障静音。
- 右声道完成才有VALID。FIR返回被顶层观察为772拍（7.72µs）；ADC有效到TX字装载为2286拍（22.86µs）。帧关系为played[n+2]=gain(residual[n])，不能把2帧加MAC当端到端测量。这些仿真量不包含模拟ADC/DAC及声学延迟。
- 系数toggle协议、两页RAM读回及capture_status bits0..20沿用residual。bit21新增增益饱和粘滞。audio_runtime GPIO ch1=frame_limit，ch2=completed_count。最后16384组四路数据为环形窗口；读起点为max(0,completed_count-16384)%16384。
- audio_clips双输入GPIO：ch1低16位预测饱和次数、高16位残差饱和次数（65535封顶），ch2增益饱和次数。任何饱和/故障/提前终止都不得算作稳定增益成功。
- 默认静音；系数每次试验完整重载清历史；预算独立于接收器；无新结果、busy、运行中改系数/增益/预算均故障静音。结束可读RAM；arm=0不擦除记录。

每轮记录自变量bypass，保持bit哈希、系数、hp_volume、数字增益、时长、夹具和外部声源一致。零系数/增益1首先在线级仿真验收严格相等；现场零系数试验从低音量开始，不直接将“增益1”视为安全声学闭环。

## 批次软件汇总 v2（2026-10-20，R-002）

这是 `closed_batch.py` 的软件导出版本，硬件寄存器与 Closed v1 不变。
`summary.json.schema_version` 从 1 升至 2；保留既有 `trials[].metadata`、
`pairs` 及其字段含义，在每项 `trials[]` 增加以下直接读取字段，并导出为 CSV 同名列：

| 字段 | 来源与口径 |
|---|---|
| `gain_q12` | 原样取自该项驱动返回的 `metadata.gain_q12`；是写入 PL 的整数增益编码，4096 表示 1 倍，不是模拟增益实测或独立寄存器回读 |
| `hp_volume` | 原样取自该项 `metadata.hp_volume`；是 Codec 音量设置码，不是 dB |
| `bit_sha256` | 原样取自该项 `metadata.bit_sha256`；是使用的 bit 文件 SHA256，不是 FPGA 配置内容回读 |

消费者可用 `trials[i].gain_q12`、`trials[i].hp_volume`、`trials[i].bit_sha256`
直接取值；原 `trials[i].metadata` 路径继续保留。支持 v1/v2 的消费者处理旧文件时可回退到
`metadata`；原来严格要求 `schema_version == 1` 的消费者需要显式接受版本 2。

取消、驱动中断或遥测字段缺失时，对应直接字段为 JSON `null`，CSV 留空；
不从请求的 dB、批次音量或上一项推算、填补。两项字段均缺失也不判为配置一致。
同一档位的旁路/抵消必须具有完全相同的实际配置（包括 `gain_q12`、`hp_volume`、
`bit_sha256`）；不一致则保留各自原值、标记 `configuration_matches=false` 并停止整批。
`asg_db` 仍为 `null`，软件汇总版本不改变实验效果的验收口径。

## 离线测评 v1（2026-10-20，C）

状态：实现与软件验证记录见 [离线回放证据](../../report/verification/audio_closed/batch-control.md#2026-10-20-离线增长判据与回放)。
生产方：C；消费方：A/B 的离线分析与后续观测驱动。
这是一份新软件结果格式，不改变已有 summary v2、驱动、FIR 或硬件寄存器。

入口为 `board/audio_closed/measurement.py` 和 `scripts/replay-audio.py`。
这里的“回放”是把文件逐段送入检测器，不播放声音、不加载 overlay、不写 MMIO。
输入为单声道 signed24 整数 PCM；`push(pcm, first_frame)` 的帧号非负、严格顺序且不得重叠。
缺口会清空检测历史，不跨缺口拼接 FFT 或增长趋势。`finish(total_frames)` 声明本轮总帧范围
`[0,total_frames)`；库函数 `replay` 支持可选 `frame_indices` 显式标注缺帧。

NPZ 入口支持现有 `residual_pcm`、`prediction_pcm`、`microphone`、`reference` 和
`sample_rate_hz`；后两路的满幅浮点转换回整数，其他路要求整数。
从 metadata 读取 `first_frame` / `completed_frames`；尾窗口必须保留原始帧范围。
若声明丢帧但没有位置，拒绝分析。没有总帧信息时只能以所给文件为范围，不能推断整次实验覆盖。
覆盖率以文件声明为依据，不是对传输链路的独立测量；输入文件只读，不导出原始 PCM。

判据是在去均值、Hann 窗的 FFT 上寻找持续窄带增长，所有条件必须同时满足：

| 默认参数 | 值与口径 |
|---|---|
| 窗 / 步长 | 64 / 16 ms，四舍五入到实际采样点；结果 `analysis` 给出实际点数与频率分辨率 |
| 增长历史 / 确认 | 至少 0.5 / 0.08 s，按窗口步长向上取整；缺帧重启历史 |
| 增长 | 历史内至少增加 3 dB，线性拟合斜率至少 6 dB/s，拟合 R² 至少 0.85 |
| 窄带 | 主峰及相邻频点的能量占 AC 总能量至少 0.55；历史峰位跨度不超过 2 个频点 |
| 电平与频带 | 窄带 RMS 至少 −70 dBFS；搜索 20–20000 Hz 内可用 FFT 频点，受 Nyquist 与分辨率限制 |

这些是公开的候选参数，不是通用啸叫标准或现场已冻结阈值。
`--config` 可读取 `MonitorConfig` 字段组成的 JSON 覆盖参数，输出始终保存实际配置。

输出 JSON 为 `schema_version=1`、`detector_version=narrowband-growth-v1`，关键字段：

| 字段 | 含义 |
|---|---|
| `verdict` | `suspected_howl`：观测到持续窄带增长；`full_scale`：存在满幅码；`insufficient_data`：缺帧或连续历史不足；`no_growth_detected`：给定范围和参数下未检出增长 |
| `events` / `first_suspected_howl` | 事件类别、绝对帧号、信号时间、峰值频率与增长依据；增长证据开始位置不是精确的物理起振时刻 |
| `full_scale_samples` | 数字满幅码数量；这是保护线索，不等同于声学啸叫或模拟削顶证明 |
| `coverage` | 声明总帧、实收区间、缺失区间、覆盖比例、历史是否足够；另列 FFT 实际覆盖与未分析区间（包含不足一窗的尾部） |
| `analysis` / `config` | 实际窗长、步长、历史窗数、频点间隔和可监测频带，以及参数版本 |

有增长或满幅时，即使还存在缺帧也保留阳性事件，同时 `coverage.complete=false`。
CSV 是逐窗轨迹，包含电平、峰位、窄带占比、增长斜率和候选标志。
其中 `rms_dbfs` 是去均值后的窗口 RMS，直流分量单独记录为 `dc_fs`。
报警时间是输入信号上的时间，不是程序运行耗时、硬件停止延迟或端到端音频延迟。

限制：外部持续渐强的哨音也可能满足判据，不能证明反馈因果；变化较快的频率、弱增长、
低于门限或频带外的增长可能漏检。稳定纯音不应仅因谱峰高而报警。
`no_growth_detected` 不代表整次实验稳定，更不能生成实测 MSG/ASG。
没有真实人声与实物啸叫验收前，不报告现场误报率或准确率。
本版是离线工具，事件不触发实际静音，尚未接入板卡全过程观测或在线停止。
