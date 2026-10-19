# 闭环最小版本

- 用户要求：按修正后的建议推进同一bitstream的抵消/旁路，优先零系数等价性和MSG，不增加诊断overlay。
- 范围：新closed顶层、工程、线级测试、限时手动脚本；不改现有FIR和开环工程，不自动现场播放。
- 接口：audio-closed-v1。沿用arm bit0，新增bypass bit1；两模式必须共同经过数字增益和相同调度，避免直接mic旁路破坏公平性。
- 验收：零系数/增益1两种输出逐字一致；非零系数核对实际播放历史索引；在线切换保持历史；限时、stall和饱和可观察；构建bit/hwh并给现场操作。
- 本轮自变量：bypass。可比较量：零模型数字输出差异=0；后续现场MSG/ASG和重复性。本地仿真不能冒充声学ASG。

完成状态：上述本地验收通过，bit/hwh与手动操作包已生成；板上A/B、MSG及电学延迟未执行。见report/verification/audio_closed/README.md。
