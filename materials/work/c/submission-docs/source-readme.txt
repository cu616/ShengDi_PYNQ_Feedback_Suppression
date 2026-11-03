# 设计源码

| 目录 | 内容 |
|---|---|
| rtl/ | 自定义音频通路、FIR预测与残差处理、播放调度及采集逻辑 |
| vendor/pynq_v2_4/ | PYNQ v2.4 I2S收发参考源码、原始来源及BSD许可证 |
| feedback/ | 路径拟合、定点参考及离线分析实现 |

冻结位流的主要依赖为 `rtl/audio_pl_replay.v`、`rtl/feedback_fir.v` 及两个厂商I2S模块。
构建入口为 `../build/scripts/create_audio_replay_io.tcl`，约束为 `../build/scripts/audio_replay_io.xdc`。
来源哈希及对应实现报告索引见 [构建核验](../build/frozen-bit-source-audit.json)。

正式板端软件和配置位于 [board/audio_replay](../board/audio_replay/)，以冻结安装ZIP的41文件为准。
软件参考与合成测试通过只说明其验证范围，不替代板上或声学结果。
