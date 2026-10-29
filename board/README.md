# 上板程序与保留版本

先读 [项目现状](../docs/STATE.md)，再按用途选目录。各 overlay 会替换 PL 配置，目录之间不是依次串联的处理模块。

| 分类 | 路径 | 用途与边界 |
|---|---|---|
| 发布载荷 | [audio_replay/v3/](audio_replay/v3/) | 按自身 manifest 整组核验；入口和恢复方法见 [版本说明](audio_replay/README.md) |
| 维护源码与现场脚本 | [audio_replay/](audio_replay/) | 混有当前源码、早期位流和历史入口，**不是可整目录上传的发布包** |
| 回退材料 | [audio_replay/v2/](audio_replay/v2/)、[rollback-v1/](audio_replay/rollback-v1/) | 各自版本保留；v2 子目录只有位流与报告，不是假定齐全的驱动包 |
| 早期闭环与测评工具 | [audio_closed/](audio_closed/) | closed 诊断载荷与 C 测评代码须按文件用途区分，不能整目录判为废弃 |
| 开环标定 / 开环残差 | [audio_calibrate/](audio_calibrate/)、[audio_residual/](audio_residual/) | 保留用于历史数据复算或明确需要的标定；不因接手就重跑 |
| 基础诊断 | [audio_bringup/](audio_bringup/)、[audio_probe/](audio_probe/)、[audio_capture/](audio_capture/)、[audio_diag/](audio_diag/)、[audio_tone/](audio_tone/) | 保留供特定故障定位；不作为 v3 的启动步骤或替代驱动 |

旧驱动、bit/hwh、Notebook、模型和原始证据均原位保留。重新使用时核对同版本依赖与适用夹具，不能只拷同名 Python 文件覆盖新包。板卡文件由 A 统一操作，本轮整理不代表已部署。
