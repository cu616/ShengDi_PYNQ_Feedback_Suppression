# C 计算时限与 START 保护留证 v9

状态：A 0cabfc17 原件重冻结；软件复核通过，可供 A 独占实机验收。
生产方：C；消费方：A / C；B 的数值判据和 A 的寄存器语义不变。
最后变更：2026-11-02；继承 [v8](recal-runtime-v8.md) 的提示与有界流程。

## 计算预算

compute_timeout_seconds 与 io_timeout_seconds 均为 150。A 的 ARM 拟合约 70 秒，旧计算预算 30 秒不足；运行音频仍限 30 秒，不延长 PL 上限。计算在子进程，STOP 继续取消计算和静音，不等待预算耗尽。

## 空闲粘滞位与活动保护

A poll 在解码后刷新空闲保护基线。只有 uncalibrated / ready / ended、没有 pending 请求、硬件线程已退出且实际模式 muted 同时满足，C 才将这次保护报告作为空闲粘滞记录，继续处理实体 START。状态机不清 PL 位、不改 A 基线、不豁免身份检查；下一次采集仍由原驱动下载和装载。

有硬件任务、尚未收取的回包或实际未静音时，保护仍优先于 START 并立即请求 abort。input_clip_seen 归入输入过载；其他命中按保护停声处理，保护不代表声学效果。

protection_history 保存触发时的 scene、request、阶段、模式、命中位、饱和诊断及适配器提供的 capture_status/control_word/protect_baseline。mmio_held 写入状态字缓存标记；旧适配器缺字段时仍保存 null，不反推伪造。回包 result.json 保留这些记录。

## 本包采用 A 已发布的修复原件

C 直接复制 A 提交 e6379ef331762b3162542d6325a644f5b34934da 中 v3-io 的九项运行时原件；hw_api.py SHA=0cabfc17cca1fb0e2629e1b382c119b48f00e1fe9b2a437a0302ed04e06ed3c5，根目录与 v3-io 副本一致。manifest.json 原字节保留，全部哈希核对；不再套用旧测试脚本补丁。包内 hardware-provenance.json 给出来源和适用范围。原 [真板证据](../../report/verification/audio-replay/guard-2026-11-02/README.md) 的验证层次保留。

三项为下载时 MMIO 读闸、驱动调用期间 AUX 缓存、移除 run 预 arm。调用结束后仍需新鲜的 AUX 回读；缓存不能成为免检理由。overlay 复用不启用。

闸门期间按键观察可能延迟约 0.9 秒，端到端未实测；不能沿用“所有时刻 BTN3 ≤200 ms”的验收结论。A 的 abort 调用耗时与实体按键检测延迟分开记录。后续获放行包的 deployment_ready 也只表示包与接口检查放行，不表示正式演示、停止延迟或整机稳定性已验收；本候选的阻断见下。

## 基线漏报的修复与旧包边界

旧 7ae449af poll 的 [基线漏报](../../report/verification/recal-product-v1/guard150-baseline-probe.json) 保留为失败证据，旧 blocked ZIP 不放行。A 已在五处驱动 before_start 接入 _arm_baseline：取消则返回 False 且不读/不改基线；通过后在实际 arm 前回读本轮基线。poll 新增原始字、基线与缓存标记。

C 用精确 0cabfc17 原件复跑 A 的寄存器替身序列、取消及缓存标记检查后，才在新包恢复 deployment_ready=true、adapter_check_allowed=true、missing=[]。这一放行用于 A 已约定的冷启动/CAL/START/重复流程实机验收，不宣称新包已上板。

操作与单一导出路径见 [操作单](../ref/recal-product.md)。
