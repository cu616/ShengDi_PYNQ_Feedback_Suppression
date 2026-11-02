# 工程入门导航

适合已有数电基础、能读Python、刚接触PYNQ工程的队员。建议先理解“数据从哪里来、到哪里去”，再读寄存器和算法推导。本文按2026-10-19工作区更新；后续完成状态以 [项目进度](../log/progress.md) 最新条目为准。

第一次阅读不需要接开发板，也不需要打开Vivado或运行Notebook。先完成下面前四步，就能理解当前项目的主体。

## 第一步：知道我们做到了哪里

依次阅读：

1. [项目首页](../../README.md)：只看“当前状态”和“下一阶段”。
2. [项目进度](../log/progress.md)：先看顶部最新几条，不必从头读完历史排障。
3. [工程交接说明](../log/handoffs/2026-10-19.md)：重点看环境、版本以及文件在哪里。

当前已完成256抽头PL预测与残差集成，首次板上开环结果逐样本一致、无饱和，误差降低6.92 dB；闭环稳定增益仍未验收。旧9.69 dB为另一轮数据的软件预测结果。

读完后应能回答：我们已经验证了什么？9.69 dB为什么不能写成“扩声音量提高9.69 dB”？下一项需要开发什么？

## 第二步：先看框图，再看文件

阅读 [工作区结构与系统流程](workspace-architecture.md) 的第1～4节，顺序是目录分层、构建部署、实时直通、开环标定。

先记住这些对应关系：

| 名称 | 在本工程里做什么 |
|---|---|
| PS | Zynq上的ARM处理器，运行Linux、Jupyter和Python |
| PL | FPGA可编程逻辑，按采样帧收发和处理音频 |
| Codec | 音频转换芯片，ADC把模拟音频转成数字，DAC执行相反转换 |
| I2S | Codec与PL之间传输音频采样的串行接口 |
| I2C | Python配置Codec的控制接口，不承载本工程逐帧音频数据 |
| MMIO / AXI GPIO | Python读写PL控制、状态及样本寄存器的途径 |
| overlay | 一套加载进PL的硬件配置；本工程用匹配的bit/hwh及脚本操作 |

`audio_probe`、`audio_capture`、`audio_calibrate`等是不同用途的overlay，不能把它们理解为依次经过的音效模块。换overlay相当于换一套PL电路，旧寄存器对象不能继续盲用。

读完后应能画出两条线：实时直通的“麦克风→PL→音响”，以及标定的“已知激励→音响→箱体→麦克风→存储”。标定时麦克风不实时送回音响。

## 第三步：从最小直通模块读RTL

按下面顺序打开源码，先看中文注释和端口：

| 顺序 | 文件 | 先抓住的问题 |
|---|---|---|
| 1 | [audio_frame_path.v](../../src/rtl/audio_frame_path.v) | valid何时表示一帧？右移如何改变幅度？使能、帧预算、停帧保护怎样让输出归零？ |
| 2 | [audio_pl_probe.v](../../src/rtl/audio_pl_probe.v) | receiver、path、transmitter如何连接？哪些信号是音频，哪些是状态？ |
| 3 | [直通接口说明](../contracts/frozen/audio-bringup-v1.md)、[probe接口说明](../contracts/frozen/audio-probe-v1.md) | 控制字段怎样对应RTL？PS能读到的是快照还是连续数据？ |

这一遍可以将`iis_deser`看作“串行转左右采样”，将`iis_ser`看作“左右采样转串行”。先不钻进VHDL逐位时序。

`audio_frame_path`目前只有衰减、直通和保护。不要因为它位于音频路径中央，就认为里面已经有啸叫抑制算法。算术右移降低幅度也不等于估计并消除反馈。

读完后应能解释：Python为什么不用逐采样执行循环？帧计数增长为什么不能单独证明音响输出正确？

## 第四步：理解标定数据是怎么来的

依次阅读：

1. [开环标定操作单](../../board/audio_calibrate/README.md)：只阅读，不立即执行。
2. [标定接口v1](../contracts/feedback-calibration-v1.md)：先看数据与时间定义，再看寄存器。
3. [audio_pl_calibrate.v](../../src/rtl/audio_pl_calibrate.v)：追踪激励、tx_word、memory和读回。
4. [open_loop_capture.py](../../board/audio_calibrate/open_loop_capture.py)：追踪参数检查、配置、启动、静音、读RAM、finally恢复和保存。

建议在纸上写出一次调用的过程：

```text
现场条件确认 → 配置并启动已知激励 → 同帧记录参考与麦克风
           → 静音后读RAM → 核对参考序列 → 恢复base/PLL → 保存NPZ
```

重点区分两个计数：`scheduled`限制发声帧数，`captured`记录收到的样本数。ADC接收失败也不应让音响无限播放。另一个容易误读的地方是`capture_left/right`：标定工程里它们分别表示DAC参考和ADC左声道，不能当成一对立体声录音。

两份真实NPZ目前只在板卡上。本地`data/`有目录，不表示已经备份数据。文件位置见交接说明。

读完后应能回答：为什么不能拿两次分别录制的声音直接当同步参考？为什么读RAM耗时不等于发声时长？异常恢复为何写在finally里？

## 第五步：读路径模型，不急着推导所有矩阵

打开 [calibration.py](../../src/feedback/calibration.py)，按函数顺序阅读：

```text
Capture.validate / load_capture
    → history_matrix
    → fit_path
    → predict / evaluate_path
    → quantize_coefficients / fixed_fir
    → export_model
```

先理解一个公式：

```text
预测麦克风反馈[n] = h[0]×参考[n−1] + h[1]×参考[n−2] + …
```

每个系数描述过去某一帧音响输出对当前麦克风的贡献。`fit_path`用训练数据求系数；`evaluate_path`用另一份数据检验预测是否有效。第一次可以把矩阵求解看作“找出误差较小的一组系数”，第二遍再研究去均值、特征值和岭正则项。

再看数值格式：PCM是24位补码，除以2^23转成满幅浮点；系数有20位小数，除以2^20还原。`fixed_fir`是整数计算参考，尚不是FPGA实时模块，也没有自动完成麦克风减去预测反馈的整套闭环处理。

最后阅读 [真实数据分析](../../report/verification/audio_calibrate/board-analysis-2026-10-16.md)。将每个指标对应回函数：训练结果、独立验证、错位参考对照、Q20系数量化分别证明什么？不要将系数量化检查当成完整硬件定点验证。

### 接着读已实现的抵消链路

依次看 [feedback_fir.v](../../src/rtl/feedback_fir.v)、[FIR接口](../contracts/feedback-fir-v1.md)、[audio_pl_residual.v](../../src/rtl/audio_pl_residual.v)、[残差接口](../contracts/frozen/audio-residual-v1.md)，最后看 [residual_tools.py](../../board/audio_residual/residual_tools.py) 和 [板上结果](../../report/verification/audio_residual/board-result-2026-10-19.md)。重点理解前一帧参考、跨帧计算时锁存输入、完整系数加载和逐字核对。当前残差仅存RAM，没有送回DAC。

## 第六步：理解“怎么知道代码是对的”

| 阅读入口 | 重点 |
|---|---|
| [test_calibration.py](../../sim/feedback/test_calibration.py) | 已知路径怎样构造，错误数据怎样拒绝，舍入及饱和边界怎样检查 |
| [test_capture_driver.py](../../sim/feedback/test_capture_driver.py) | 用模拟硬件验证采集和恢复流程；它不能证明真实Codec时序 |
| [tb_audio_frame_path.v](../../sim/audio/tb_audio_frame_path.v) | 从小模块理解激励、预期输出和失败条件 |
| [tb_audio_calibrate.v](../../sim/audio/tb_audio_calibrate.v) | 缩小帧数验证序列、配对及自动停止 |
| [证据索引](../../report/evidence-index.md) | 区分软件测试、RTL仿真、实现报告、用户听感和实物数据评价 |

先尝试讲清一个测试的预期结果从哪里来，再运行它。全部测试显示通过，也不能跳过真实硬件和同增益闭环对照。

## 第七步：最后读Vivado工程和底层I2S

在看懂上述流程后，再读：

1. [create_audio_calibrate.tcl](../../build/scripts/create_audio_calibrate.tcl)：找到PS7、AXI GPIO、RTL模块、时钟复位、地址分配和生成bit的步骤。
2. [audio_bringup.xdc](../../build/scripts/audio_bringup.xdc)：将端口名对应到板卡引脚和约束；当前I/O时序约束仍有缺口。
3. [厂商源码说明](../../src/vendor/pynq_v2_4/README.md)，然后看 [iis_ser.vhd](../../src/vendor/pynq_v2_4/iis_ser.vhd) 和 [iis_deser.vhd](../../src/vendor/pynq_v2_4/iis_deser.vhd)：研究LRCLK、BCLK、位序和VALID时机。

构建脚本会创建或覆盖生成工程，第一次阅读不要直接运行。已有验证使用Vivado2018.3；升级工具链不属于入门必做项。

**接手 A 线之前**：先读 [a-line-handover.md](a-line-handover.md)（现状、阻塞、路径、下一步）
和 [ai-collaboration-habits.md](ai-collaboration-habits.md)（与 A 协作的硬性习惯）。

**只想上板操作**（按哪个键、拨哪个开关、换距离怎么做、卡住怎么复位）：直接看
[board-quickstart.md](board-quickstart.md)，不用读上面这些。

## 按分工选择第二遍的重点

| 角色 | 第二遍优先阅读 | 开工前应能交付的说明 |
|---|---|---|
| FPGA主开发 | 第三、四、六、七步及接口文档 | 数据格式、时序、复位、系数更新和保护行为 |
| 算法与数据 | 第四、五、六步 | 训练/验证划分、系数顺序、量化和误差判据 |
| 硬件与实验 | 第一、二、四步及协作经验 | 接线、增益、箱体条件、操作步骤及完整结果记录 |

正式改代码前，全员阅读 [AI开发规范](../rules/ai-development-policy.md) 和 [音频协作经验](../../skill/audio-collaboration-lessons.md)。各自使用独立目录和任务分支，同一时段只有一名操作者控制板卡。

第一次可以跳过`docs/archive/`旧方案、`build/work/`生成IP、`.Xil/`缓存、`tmp/`临时副本，以及diag/tone等历史诊断分支的内部细节；遇到相应问题再查。不要跳过失败证据的边界说明，也不要删除这些文件。

完成入门的判断标准：能用自己的话解释当前两条音频路径、指出每个关键文件的职责、说明9.69 dB的含义，并明确开环残差验证与闭环ASG验收的区别。此时再领取一个边界清楚的小任务，比一开始通读全部仓库更有效。
