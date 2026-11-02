# C 计算时限与 START 保护留证 v9

状态：软件验证；新整包待 A 实机复核。
生产方：C；消费方：A / C；B 的数值判据和 A 的寄存器语义不变。
最后变更：2026-11-02；继承 [v8](recal-runtime-v8.md) 的提示与有界流程。

## 计算预算

compute_timeout_seconds 与 io_timeout_seconds 均为 150。A 的 ARM 拟合约 70 秒，旧计算预算 30 秒不足；运行音频仍限 30 秒，不延长 PL 上限。计算在子进程，STOP 继续取消计算和静音，不等待预算耗尽。

## 空闲粘滞位与活动保护

A poll 在解码后刷新空闲保护基线。只有 uncalibrated / ready / ended、没有 pending 请求、硬件线程已退出且实际模式 muted 同时满足，C 才将这次保护报告作为空闲粘滞记录，继续处理实体 START。状态机不清 PL 位、不改 A 基线、不豁免身份检查；下一次采集仍由原驱动下载和装载。

有硬件任务、尚未收取的回包或实际未静音时，保护仍优先于 START 并立即请求 abort。input_clip_seen 归入输入过载；其他命中按保护停声处理，保护不代表声学效果。

protection_history 保存触发时的 scene、request、阶段、模式、命中位、饱和诊断及适配器提供的 capture_status/control_word。旧 A 适配器未提供原始字时保存 null 和 raw_status_available=false，不能把命中位反推值称为原始回读。回包 result.json 保留这些记录。

## 本包采用 A 已发布的修复原件

C 只将 A 在 [真板证据](../../report/verification/audio-replay/guard-2026-11-02/README.md) 中提交的六处替换用于组包，结果严格等于 A 报告的测试副本 SHA；不改仓库 A 源码，不执行 A 的 shell、安装或板卡命令。包内 hardware-provenance.json 给出原始提交、补丁路径与 SHA、结果 SHA。

三项为下载时 MMIO 读闸、驱动调用期间 AUX 缓存、移除 run 预 arm。调用结束后仍需新鲜的 AUX 回读；缓存不能成为免检理由。overlay 复用不启用。

闸门期间按键观察可能延迟约 0.9 秒，端到端未实测；不能沿用“所有时刻 BTN3 ≤200 ms”的验收结论。A 的 abort 调用耗时与实体按键检测延迟分开记录。此包可供 A 独占复核，deployment_ready 表示包与接口检查放行，不表示正式演示、停止延迟或整机稳定性已验收。

操作与单一导出路径见 [操作单](../ref/recal-product.md)。
