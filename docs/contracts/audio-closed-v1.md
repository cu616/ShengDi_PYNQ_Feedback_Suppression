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
