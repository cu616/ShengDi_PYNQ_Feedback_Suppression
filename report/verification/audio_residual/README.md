# 开环残差集成验证（2026-10-18）

2026-10-19更新：用户已完成首次板上开环验证，逐样本一致、无饱和、预测误差降低6.92 dB。详见 [实测记录](board-result-2026-10-19.md)。下文构建/首次操作说明保留对应阶段边界。

本轮新增独立audio_residual工程，保留原audio_calibrate。256抽头、24位PCM/Q20；四路参考/麦克风/预测/残差同地址保存。16384帧固定激励，ADC不回送DAC。接收时锁存输入，等待FIR完成再写RAM，避免跨帧错配。

## 已执行验证

- Vivado2018.3行为仿真，实际256抽头、缩小16帧缓存实例，两组种子。引脚独立解码核对DAC参考；已知ADC字、h[0]=1/2和h[2]=1/4手算核对四路RAM，覆盖启动历史与重载清历史。
- 缺系数启动、旧系数重复启动、运行中改系数、FIR忙时连续输入、ADC无VALID、停止、复位均检查。PASS标记见rtl-simulation.txt。缓存全深度16384帧未另做长仿真。
- Python软件套件25项实际通过（`python -m unittest discover -s sim/feedback -p "test_*.py" -v`，0.932秒）。新增3项数值/模型检查及3项模拟硬件驱动检查；模拟硬件不是上板证据。
- 两个板卡Python脚本AST检查通过；未连接板卡或执行现场发声。

## 过程纠错

首次Tcl源文件列表仍指向旧audio_pl_calibrate， elaboration报告找不到新模块；修正后继续。首次集成仿真第二轮读取了上一轮保留的done状态，测试平台在arm写入后等待4拍再判断，新一轮通过；未放宽数值比较。Python临时目录受系统沙箱限制，改用仓库tmp隔离目录后25项通过。另补充busy故障用例后重新完成RTL仿真。

## 限制和后续

尚未上板核对真实四路数据，不宣称实时抵消或ASG成功。当前模型仍来自旧箱体，旧种子复用只用于硬件实现核对。最终效果需新的独立数据和同等增益闭环启用/旁路对照。操作见board/audio_residual/README.md。

## 整板构建完成

Vivado2018.3综合、布局布线及bitstream生成实际完成，返回AUDIO_BITSTREAM_CREATED。LUT2164、寄存器3028、BRAM48、DSP2；100MHz约束下WNS1.741ns、WHS0.049ns。DRC为0错误、3条DSP流水警告（DPOP-1/2）。音频外部接口仍有1个输入及3个输出缺延迟约束，不称完整板级时序签核；板卡预设DDR偏斜及IBUF_LOW_PWR等过程警告保留在构建日志。

匹配bit/hwh、两份Python、手动Notebook及manifest已打包到board/audio_residual；仅在本地，未上传或加载。原始构建记录为build/work/audio_residual及tmp/audio_residual_build.log；归档timing.txt、utilization.txt、drc.txt及rtl-simulation.txt在本目录。可用scripts/package_audio_residual.py从完成的构建重新打包。
