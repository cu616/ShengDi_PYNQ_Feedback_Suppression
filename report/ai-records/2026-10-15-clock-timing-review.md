# 2026-10-15 Codec 时钟与音频 I/O 时序复核

用户要求继续最小 PL 音频通路验证。本轮由 AI 单一操作者控制板卡；原 Notebook 中的录放/旁路单元没有运行。本文件是操作摘要，不是完整聊天记录。仓库原有未提交修改保留，本轮未提交或推送。

## 依据与板上只读结果

- [PYNQ 官方音频底层驱动](https://raw.githubusercontent.com/Xilinx/PYNQ/master/pynq/lib/_pynq/_audio/audio_adau1761.cpp) 的 `config_audio_pll()` 明确用 10 MHz MCLK 和 `R=4,N=572,M=625` 产生 49.152 MHz；`config_audio_codec()` 把 Codec 设为从模式，并将 ADC/串口、串口/DAC 路由打开。此为公开源码依据，不自动代表板上版本。
- 在板上 PYNQ 3.1.1，`inspect.getsource(AudioADAU1761.configure)` 显示该方法调用本地 `libaudio` 的 PLL/Codec 配置。通过 `/dev/i2c-1` 对地址 `0x3B` 只读寄存器（仅写入寄存器索引，无配置数据）：R0 `0f`，R1 `0271023c2103`，R15/R16 `00/00`，R58/R59 `01/01`。输出保存在板卡 `base/audio/audio_bringup_muted_smoke_2026-10-15.ipynb`，截图 `report/verification/audio_bringup/codec_clock_probe_board.png`。
- 当前 RTL `divider[10]` 的设计帧率为 100 MHz/2048=48,828.125 Hz；与板上 48 kHz PLL 基准相差 828.125 Hz，约 1.73%。静音帧计数是 PL 内部事件，不能证明 Codec 与 PL 采样同步。

## 静音时钟验证

依据 [ADAU1761 数据手册 Rev. F，PLL 与表 15](https://www.analog.com/media/en/technical-documentation/data-sheets/ADAU1761.pdf)：MCLK 可为 8–27 MHz，PLL 输出需为 41–54 MHz，整数 R 支持 2–8。10 MHz×5=50 MHz，50 MHz/1024=48,828.125 Hz。脚本 `board/audio_bringup/codec_clock_smoke.py` 的源码粘贴进同一个板上 Notebook 执行，没有上传为单独板卡文件。它先关闭 Codec 输出混音/耳机输出，保持 PL control=0，然后单次六字节写 R1 `000000002801`，最多 2 秒轮询锁定位，最后在 `finally` 恢复官方 base 并验证原 48 kHz PLL。

实际输出：`PLL_50MHZ_LOCKED 000000002803 mute True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。截图 `report/verification/audio_bringup/codec_clock_smoke_board.png`。这证明该 PLL 设置在这块板上可锁定且恢复成功，**没有验证 ADC/DAC 数据、实际声音、音质或反馈抑制**。

## 临时 I/O 时序模型

[ADAU1761 Rev. F 表 7](https://www.analog.com/media/en/technical-documentation/data-sheets/ADAU1761.pdf) 指出：ADC_SDATA 相对 BCLK 下降沿最迟 50 ns（全 IOVDD 范围，3.3 V 条件可用 25 ns）；DAC_SDATA 与 LRCLK 相对 BCLK 上升沿各需 5 ns 建立及保持。板上 IOVDD 与 PCB 数据/时钟路径偏斜尚未实测，故本轮采用 50 ns 的保守输入最大值，暂按零 PCB 偏斜建立模型。

`build/scripts/inspect_audio_timing.tcl` 在已实现网表上找到分频器 Q/C 和端口，确认原 `bclk` 没有时钟对象。`build/scripts/probe_audio_io_constraints.tcl` 在内存中添加生成时钟与上述 I/O 延迟，**没有修改原构建 XDC 或 bitstream**。报告 `report/verification/audio_bringup/io_probe_check_timing.txt` 不再报未约束音频 I/O；`io_probe_timing.txt` 中 PLL/内部 100 MHz 路径仍有原 WNS 3.908 ns，但外部相关两处违反：

1. `sdata_i` 到首级 `adc_sync_reg[0]/D` setup 为 -54.883 ns。首级同步器每个 100 MHz 周期采样，正常可能在 Codec 数据刚变化时采样；下一阶段需明确将其作为同步边界处理，并验证后级仅在稳定窗口使用样本，不能简单把这条路径当作同步数据传输或随意静默约束。
2. `lrclk` 相对 `bclk` 上升沿的输出 hold 为 -7.003 ns。当前 LRCLK/BCLK 都来自分频计数器；静态报告对任意 100 MHz 启动沿做最坏情况检查，尚未证明实际 LRCLK 过渡一定违反 5 ns 保持。需结合波形、PCB 偏斜、布局与正确的源同步时序约束复核。

补充线级仿真：将 `sim/audio/tb_audio_i2s.v` 的 ADC_SDATA 激励延迟由 BCLK 下降后 1 ns 改为数据手册全 IOVDD 范围上限 50 ns，Vivado 2018.3 再运行 `test_audio_i2s.tcl`，输出 `I2S_PATH_PASS`，检查 12 个左右声道字、符号衰减和串行静音；日志 `report/verification/audio_bringup/i2s_50ns_test.txt`。这证明该仿真模型下的接收采样窗口足够，不能代替真实 PCB、电压、时序约束或上板 ADC 数据检查。

所以当前不能宣称 I/O 时序签核，也不宜依据静音计数立即做有声直通。下一可验收任务应增加静音 ADC 数据观测，并进一步核对 LRCLK/BCLK 相位与 PCB 偏斜，决定约束或 RTL 的最小修正；最后低音量限时开声。

## 后续相位复核（2026-10-15）

静音 ADC 探针后来已在板上读到变化的左右采样数据，证据见 `docs/progress.md`。进一步检查原始分频 RTL：`divider` 每个 100 MHz 上升沿加一，`bclk=divider[4]`、`lrclk=divider[10]`。BCLK 上升仅发生在旧计数值低 5 位为 `01111` 的边界；LRCLK 翻转仅发生在旧计数值低 11 位为 `01111111111` 的边界，此时 BCLK **下降**。下一次 BCLK 上升相隔 16 个 100 MHz 周期，即设计值 160 ns。因此 LRCLK 实际边沿和 BCLK 上升沿不可能在同一个计数周期产生。

此前 hold 报告的最差路径把 `divider_reg[10]` 的 Q 变化与 BCLK **同一**上升沿比较（报告路径要求 0 ns），忽略了两位计数器状态间的可达性关系，不能直接解释为 Codec 看到了 7.003 ns 的实际保持时间违反。其证据是 `io_probe_timing.txt` 的 Min Delay Paths，起点 `divider_reg[10]/C`、终点 `lrclk`，要求项写明 `audio_bclk rise@160ns - clk_fpga_0 rise@160ns`。此分析仅消除该报告作为实物故障的直接证据；尚未测量板上 BCLK/LRCLK 引脚偏斜、时钟抖动或完整源同步约束，也未签核板级 I/O。
