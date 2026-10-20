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
