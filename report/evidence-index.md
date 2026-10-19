# 日志与证据索引

当前交接入口：[2026-10-19交接说明](../docs/handoff-2026-10-19.md)。本页只索引材料，不替代原始输出。

| 要核对的内容 | 入口 | 证据类型 |
|---|---|---|
| 闭环最小版本地实现 | [闭环验证](verification/audio_closed/README.md) | 线级仿真、31项软件测试、整板构建；未上板 |
| 用户四项闭环复测 | [结果和来源](verification/audio_closed/board-basic-repeat.md) | 用户返回metadata与未听到尖叫的反馈；无ASG结论 |
| 批次控制 | [批次验证](verification/audio_closed/batch-control.md) | 38项本地软件测试；新流程尚未上板 |
| 推进要求与并行职责 | [重要提醒](../docs/IMPORTANT-ai-progress.md)、[三人分工](../docs/parallel-work/README.md) | 用户明确要求及可复制AI提示词 |
| 当前结论与历史变化 | [progress](../docs/progress.md) | 按阶段记录，较新条目优先 |
| 首次板上FIR残差 | [10月19日结果](verification/audio_residual/board-result-2026-10-19.md) | 用户返回metadata，逐样本一致、6.92 dB开环；非ASG |
| 开环残差整板集成 | [集成验证](verification/audio_residual/README.md) | 仿真、25项软件测试摘要及整板报告 |
| FIR核及算法比较 | [FIR报告](verification/feedback_fir/README.md)、[真实长度比较](verification/feedback_fir/board-length-comparison-2026-10-18.md) | 合成研究与真实数据开发比较分别记录 |
| 官方录播及早期排障 | [录播对照](../docs/experiments/stock-input-reference-2026-10-15.md)、[音频排查](../docs/experiments/audio-debug-log.md) | 操作记录和用户反馈，按各文件说明区分 |
| 连续ADC和纯音 | [对照操作](../docs/experiments/contiguous-adc-tone-check-2026-10-16.md)及progress | 操作单和返回输出不能互相替代 |
| 标定软件测试 | [software-tests.txt](verification/audio_calibrate/software-tests.txt) | 既有实际执行输出，13项 |
| 标定RTL仿真 | [rtl-simulation.txt](verification/audio_calibrate/rtl-simulation.txt) | 缩小16帧用例，不是板上音频结果 |
| 实现与资源 | [timing.txt](verification/audio_calibrate/timing.txt)、[utilization.txt](verification/audio_calibrate/utilization.txt)、[drc.txt](verification/audio_calibrate/drc.txt) | Vivado2018.3报告；外部I/O约束仍不完整 |
| 合成数据结果 | [synthetic-result.json](verification/audio_calibrate/synthetic-result.json) | 合成路径验证，不是实物性能 |
| 两轮真实数据评价 | [board-analysis](verification/audio_calibrate/board-analysis-2026-10-16.md) | 用户采集输出及AI直接观察分析结果的摘要 |
| 实现决定、纠错与授权 | [标定AI记录](ai-records/2026-10-16-open-loop-calibration.md) | 协作摘要，完整对话未导入 |
| 本次交接整理 | [交接AI记录](ai-records/2026-10-17-handoff-sync.md) | 文档修改与核对范围 |

板上原始NPZ、Notebook与候选JSON的准确位置见交接说明。仓库当前没有这些文件的完整备份，不能声称“克隆即可复现实物结果”。bit/hwh与关键源码校验值见 [manifest](../board/audio_calibrate/manifest.json)；近期文件来自未提交工作区，HEAD只用于定位起点。

新增日志使用日期和英文任务名，复制 [AI记录模板](../docs/templates/ai-session-record.md)。每次至少记录操作者、文件版本/校验值、fixture_id、输入及输出路径、参数、完整错误/恢复输出、实际验证层级与未验证项。听感标为用户反馈，模型推断单独写明。

正式工具输出用.txt或明确纳入版本管理的文件；当前忽略规则可能排除.log，交接前检查git status和git check-ignore。凭据不入库，录音不因“私有仓库”而自动获得上传许可。修正结论时保留原失败证据，在新条目写明修正理由。
