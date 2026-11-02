# C 慢采集时限与实体提示 v8

状态：软件验证；按新包现场复核。
生产方：C；消费方：A / C；A运行时及B判据不变。
最后变更：2026-11-02；沿用[v7](recal-runtime-v7.md)的上电配置与显式CAL恢复。

## 阶段时限

io_timeout_seconds=150，覆盖每个硬件请求的完整初始化/采集/落盘墙钟；保留原1秒调度余量。A实测每段约8.6秒，六训练约51.6秒，不再被旧30秒I/O预算提前停止。compute_timeout_seconds仍30，run_seconds仍30，不增加PL音频时长、不拼段。STOP/保护优先于阶段时限，继续即时abort并等待旧调用收尾。

## 四灯图案（LD3到LD0）

| 图案 | 含义 |
|---|---|
| 0001 | 准备/计算/收尾；嵌入提示音前继续等待 |
| 0010 | 提示音与尾声已结束，请持续讲话 |
| 0100 | 等待环境安静 |
| 0101 | 正在采集训练或验证，请继续安静 |
| 0110 | 就绪/本次运行已结束 |
| 0001 / 1001运行 | 运行抵消/旁路；LD3仍由A实际模式控制 |

嵌入input不再永久停留input_capture：C先看到现有poll的实际armed模式(cancel/bypass)，再等待封装的embedded_cue_frames/sample_rate_hz及cue_indicator_guard_seconds，才进入speaking/0010。时间从实际arm回读起算，不从请求开始起算，避免把位流下载/codec初始化当讲话时间。当前A8799提示音为21969帧，附加尾声等待0.1秒；采集源字节和测量窗不变。

armed安全写灯仅对封装indicator_armed_safe=true的适配启用；当前A8799已支持。其他适配保留indicator_deferred防护，状态写明deferred原因，不盲目取消保护。没有可靠arm或提示音绑定时沿用音频提示，不提前亮讲话灯。

overlay复用与已报告PS服务卡死不属于本次修复；不以延长软件时限宣称已解决硬件初始化开销或整机稳定性。操作见[操作单](../ref/recal-product.md)。
