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


## 测评软件汇总 v3（2026-10-23，B 模型比较请求）

状态：实现与验收见 [批次证据](../../report/verification/audio_closed/batch-control.md)。
生产方 C，消费方 A/B；新增派生软件字段，硬件、系数和旧 summary v2 不变。
适用于 replay experiment 与只读历史 NPZ 汇总，schema_version=3，calculation_version=c-measurement-2.1.0。

每个 trials 行直接包含 gain_q12、hp_volume、bit_sha256、coefficients_sha256、model_sha256、
model_role、logical_taps、loaded_taps。gain/hp/bit 仅取该次 metadata，不从请求 dB 或上一项填补；
coefficients_sha256 可从该次保存的 Q20 数组按 little-endian int32 独立计算，并注明来源。
原模型哈希不以系数哈希冒充。256 补零加载仍是 baseline，不得标为 candidate。

每行必须有 tail_rms_dbfs、tail_slope_db_per_s、tail_residual_over_mic_db 对象，
后者含 300-1000、1000-3000、8200-8600 三项。CSV 同时有三个平坦频带列。
无效/不足时字段保留 null、CSV 留空，tail_reasons 给出原因，不能填 0 当通过。
实际 first/completed/frames 必须一致，源结束及外部声源关闭有证据，整个所用区间位于源结束+过渡之后，
无缺帧/满幅且长度够，才计算尾段。计划有 1 s 尾段本身不构成实际窗口证据。
历史补充材料是以 NPZ SHA256 绑定的独立 evidence.json，不回写原 NPZ；必须带 provenance。

尾段 RMS 是 mic 去均值 RMS；斜率是 20 ms 不重叠块的去均值 RMS(dBFS) 对块中心时间的 OLS，
至少 8 块且总长 >=160 ms，保留拟合 R² 但不叫置信度，不以斜率单独定义起振。
三频带能量使用相同区间、去均值及 Hann 窗，RFFT 的 [lo,hi) bins，10log10(sum|E|²/sum|M|²)。
mic 全窗低于 -55 dBFS、某带低于 -80 dBFS、零残差或零分母时相关值不输出有限伪数。
比值是观测能量比，不无条件认证为 CD/ASG；噪声和源注入位置的解释由分析层另行核对。

保护、prediction 饱和、残差/增益/mix 饱和、麦克风满幅、mute_applied、波形全零分别列出；未知为 null。
静音动作不由波形全零或恢复成功推断。原始阳性事件与类别可并存。

model_pairs 是基线/候选比较；保留既有 pairs 的旁路/抵消含义。基线/候选允许模型/系数不同，
但实际 gain_q12、hp_volume、fixture_id、bit、sample rate、source、scene/session、模式、尾段区间必须一致且非空。
显式 comparison_id 内 gain 不符时两行标 invalid，保留原值与失败配对；不以请求 dB 代替相等。
缺尾段或正向对照时只用于安全/诊断记录，effect_eligible=false；不生成 MSG/ASG。
JSON/CSV 必须标明 evidence_kind；软件合成示例不能作为完成真实现场配对的证据。

### summary v3.1 兼容增补（2026-10-23，B 消费方反馈）

schema_version 仍为 3，calculation_version 仍为 c-measurement-2.1.0；
summary_revision=3.1.0 只标识以下附加遥测，不改变尾段数值判据，不生成 ASG。

- 历史 audio_replay 位流 dadbbbab…ddcb05 登记为 256 抽头。4d49dfbe…635316
  对应已退役的 audio_closed，逐行明确 retired_overlay=true、evidence_scope=pl_arithmetic_only、
  acoustic_evidence_eligible=false，并排除声学 model_pairs；原始数据与事件不删除。
  完整哈希和出处由代码登记及 bitstream_provenance 给出。
- loaded_taps 保留保存数组长度/驱动明确记录，loaded_taps_basis 说明来源；
  缺失时仅新增 derived_loaded_taps 及 derived_loaded_taps_basis，依据已批准模型的
  原数组/补零数组 little-endian int32 哈希推导。推导不冒充硬件 loaded_count 回读，
  不消除实际加载证据缺失，不单独使历史记录 effect_eligible。
- JSON/CSV 直接导出 positive_control_valid（true/false/null）。eligibility_reasons
  独立列出 tail_not_validated、safety_not_validated、positive_control_not_validated
  或 positive_control_failed；算术、配置、证据来源不合格另列，不再只给一个合并原因。
  假阴性的通路失败与没有有效尾段可同时保留；未知不改为 false。
- models/manifest.json 的 models 仅注册三个原模型；derived_artifacts 不参与模型身份注册。
  清单可附 coefficients_sha256/padded_512_sha256，C 从模型数组独立重算并校验；
  不把补零派生物重复注册为候选，不改变模型文件字节。

### 房间执行协议 v1（2026-10-24，A db29698 请求）

measurement_policy_version=c-room-policy-1.0.0，calculation_version=c-measurement-2.2.0、
summary_revision=3.2.0、schema_version=3。满幅判定及显式尾区间是本版分析变更，旧2.1产物保留原版本。
仅用于当前 room_v1_20261021、hp_volume=40、
48828.125 Hz、512 位流和固定 A 驱动；原始 NPZ、FIR 和寄存器不变。
使用 A 本场重标定的 256/512 两份原模型，原 B 三模型注册表不覆写。模型仍为待实验候选，
不把 A 报告中的增益差直接升级为已验收 ASG。

每项闭环前用固定 PCM、峰值 -20 dBFS 的 1 kHz 定音、direct_only（反馈增益为 0）检查通路。
初始两次合格门禁建立场次基线；后续门禁 RMS 相对该固定基线的绝对偏差 <=1.5 dB，
且信号高于登记底噪 6 dB、相关性合格、无满幅/饱和/恢复失败才允许下一项。
失败即结束本批，不在失败后重新定义基线，不自动重试闭环。
下一门禁也作为前一闭环的事后检查；若失败或未执行，前一项不能进入有效效果配对。

麦克风达到 signed24 满幅码时，独立记录 microphone_clipping 并禁止稳定/有效效果结论；
不以 PL guard 是否触发代替麦克风检查，也不单凭削顶证明反馈因果。
满幅、保护或恢复失败后结束本批，下一批须重新通过初始门禁；没有自动恢复发声。
现有 A 驱动没有全过程麦克风削顶遥测，因此该检查覆盖保存窗口，不冒充在线 ADC 保护。

闭环固定 2.1 s、数字源约 1.87 s，尾环形中同时保留一部分有源段和不少于 160 ms 的纯尾段。
以驱动确认的实际 source_end_frame_exclusive 和固定 50 ms 过渡计算唯一尾区间，
记录完整捕获区间及派生尾区间；数组裁剪仅在 C 派生分析中进行，不改原始 NPZ。
全捕获的满幅事件不能因选取尾区间而隐藏。有源段电平用于排除空测，尾段落入底噪时
明确不足，不把它当稳定或模型有效。仅记录窗口内证据，不计算 MSG/ASG。

原 schema_version=3 与统计公式保留，新增 measurement_policy_version、trial_role、
amplifier_gate、active_source_statistics、capture_window/tail_analysis_window；
基线/候选 comparison_id 与实际增益、场次、场景及尾区间绑定。外部讲话仅作功能验收，
与模型效果配对分开。返回 ZIP 含汇总、状态、模型清单及模型字节，不含捕获 PCM。

### 房间执行协议 v1.1（2026-10-24，A 08965d2 反馈）

measurement_policy_version=c-room-policy-1.1.0，calculation_version=c-measurement-2.2.1、
summary_revision=3.2.1，schema_version=3。v1 原包与原回包冻结，以下仅用于新工具或显式派生复核。

- 运行门禁与固定初始基线的偏差限放宽为 5 dB；定音、底噪+6 dB、满幅和故障要求保留。
  导出同窗 mic_over_ref_db，以及整批麦克风、reference、mic/ref 的极差与总体标准差（ddof=0）。
  这些是描述统计，不作为传递函数误差界，不据此缩放或修补任何模型。
- 效果配对另查两行各自前/后四次合格门禁的 mic/ref 极差 <=1.5 dB；不合格则
  path_comparison_control.valid=false、effect_eligible=false，但不因此停止全部运行。
  1 kHz 检查只排除已观察到的通路变化，不能认证全频段传递函数相同。
  闭环内 mic/ref 含回授相关性，不能用它代替开环 H 或给效果数值作简单归一化。
- 即使尾段信号不足，也保留实际派生尾区间的 first/end/frames；无效统计值仍为 null。
  A evidence-v2 的 stop_reason=guard 是保护阳性；completed、非早停、done且无配置故障、
  最终三个原始计数字均为零时可导出保护阴性，并附 protection_triggered_basis。
  其他缺失证据不填 false。
- 房间汇总 model_pairs 仅含两端均有真实 capture_id 的完整组；未完成组及原因为
  incomplete_model_pairs，comparison_group_count 为两者总数。失败原始行全部保留。
  人工听感为 H1；仅数值代理为 P1，另列 hearing_evidence_kind，P1 不通过外部讲话验收。
- −20log10(max|H−Ĥ|) 记为 predicted_gain_bound_db：在稳定线性路径、同一归一化/音量、
  覆盖全部实际环路频率并有可信误差约束时，严格小增益条件是实际 gain_db 小于该界。
  分频带/有限频点估计仅作设计预测，不命名为实测可稳增益，不填 msg_db/asg_db。
  +6 dB 仅记为 proposed_design_target_db，尚未替代人声与重复现场验收。
  现有 9131 Hz、DC及频带空隙不得由 300–3400/8200–8600 Hz 四段结果外推。

本次只更正 C 派生软件，未改变 A 驱动、硬件、B 算法或原始证据。新模型须收到原文件、
逐文件哈希及独立验证后再冻结发声包，不因放宽运行门禁就重复旧 RUN。
