# 批次流程验证

本次实际运行Python unittest discover，共38项通过，输出见batch-software-tests.txt。新增覆盖整批8项与4对汇总、未确认不启动、准备阶段取消、尖叫反馈停止、饱和/算术错误停止、KeyboardInterrupt保留进度、配置不一致停止。模拟驱动额外检查before_start执行时Codec仍静音、PL未arm；取消仍走恢复。

首轮测试因Windows沙箱临时目录不可写报6个测试环境错误，改用仓库tmp后通过。没有据此改动设备逻辑。更新清单时同时修正package_audio_closed.py误将audio_pl_residual.v列作闭环顶层源码的记录错误，改为audio_pl_closed.v；未修改或重建bitstream。bit哈希仍为4d49dfbe53180536f0c2302a19ed6ead23e3336e959dd50567dc647473635316。

新脚本和Notebook未上板运行。没有全程窄带增长监测，无法自动识别未饱和啸叫；现场需能断电。JSON/CSV只汇总参数、末尾窗口指标、全程饱和计数及操作者听感，不产生MSG/ASG结论。后续完整阈值测量仍需连续监测与重复试验。

## 2026-10-20 R-002：实际配置字段导出

请求来自 [R-002](../../../docs/REQUESTS.md)。实现与字段口径见
[批次软件汇总 v2](../../../docs/contracts/audio-closed-v1.md#批次软件汇总-v22026-10-20r-002)。
修改仅涉及批次软件及其配套文件；既有 `metadata` 保留，实际配置增加直接读取路径和 CSV 列。

验收用例：读取实际写出的 JSON/CSV，检查两种导出与驱动遥测一致；
同档位的增益编码、音量码、bit 哈希分别制造不一致，均停止并保留两项原值；
逐项删除三个配置字段，均停止且缺值不伪造；启动前取消的项保持未知。
预期增益码由固定测试档位独立列举，测试结果不依赖真实模型或录音。

证据：

- [软件测试原始输出](batch-r002-software-tests.txt)：本机独立 Python 环境实际执行完整软件回归。
- [文档检查原始输出](batch-r002-doc-check.txt)：检查本轮交付的链接、请求状态与文档规范。
- [软件夹具 JSON](batch-r002-summary.json)、[软件夹具 CSV](batch-r002-summary.csv)：
  由实际导出函数写出的一对旁路/抵消示例，明确标注 `software_test_fixture`，不是板卡数据。

未执行上板、发声、RTL 仿真或重新构建；本次软件变更不要求它们。
部署时使用更新清单中的批次脚本哈希；bit/hwh 与原清单保持一致。
