# 闭环最小版本地验证：2026-10-19

已生成独立audio_closed bit/hwh；未上传板卡、未播放、未测MSG/ASG。已有feedback_fir、I²S和audio_residual未修改。

## 实际执行

- Vivado2018.3执行`build/scripts/test_audio_closed.tcl`：线级I²S输入/输出仿真通过。零系数/单位增益A/B逐字相同；独立输出解码核对非零FIR参考历史及在线bypass切换；覆盖环形RAM、增益饱和、ADC停滞、预算结束、人工撤销、未加载启动及运行中改系数故障。
- 仿真输入为交替确定性PCM，非零模型h[0]=0.5、h[2]=0.25；预测由测试台解码出的实际输出序列独立计算。不是声学模型性能测试。日志见 [rtl-simulation.txt](rtl-simulation.txt)。
- Python unittest discover：31项通过，包含新增3项闭环数值用例及3项模拟MMIO/I²C驱动用例。检查截断历史窗口、两个模式、半值舍入/饱和、错误输出检测、无自动播放、故障/恢复失败处理。见 [software-tests.txt](software-tests.txt)。
- `create_audio_closed.tcl -tclargs build`完成综合、布局布线及bitstream。LUT2573、FF4104、BRAM48、DSP3。WNS0.666ns、WHS0.021ns，已定义内部时序约束满足。
- DRC0错误、4条DSP流水警告；仍有1输入/3输出未定义I/O延迟，**不是完整板级时序签核**。原始报告见timing/utilization/drc.txt。

## 延迟纠正

实际仿真观察ADC样本有效至顶层观察FIR输出772拍，至TX字装载2286拍（100MHz下分别7.72和22.86µs）。输出帧索引相差2，但起点在输入帧后部，不能再把2帧+MAC相加为49.6µs。以上不是电学端到端延迟；Codec滤波、串行发送和模拟节点仍需现场测量。

## 本轮自变量与下一验收

两模式共享Q4.12数字增益、限幅和调度，只改bypass。板上先从低增益做零模型/真实模型成对限时试验，核对四路整数关系、结束静音与饱和。通过后再做可重复的MSG阈值对照；6.92dB旧开环误差降低不作为ASG预期。

末尾16384帧缓存不覆盖10秒全过程，本版不具备全程窄带增长判据，不能把末尾未饱和当成稳定。饱和器是硬削顶保护，不是听感优化或抗啸叫算法。打包哈希见board/audio_closed/manifest.json；Notebook不参与自身哈希校验。
