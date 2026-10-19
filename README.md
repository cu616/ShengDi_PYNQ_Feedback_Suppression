# 声堤：实时声反馈啸叫抑制系统

ShengDi_PYNQ_Feedback_Suppression 是基于 PYNQ-Z2 的声反馈抑制项目，目标是在真实硬件上提高稳定扩声音量，并测量延迟、音质和 FPGA 资源开销。首版面向桌面扩声，助听场景留作后续探索。

## 当前状态

截至2026-10-19，256抽头Q20反馈预测与残差核已接入PYNQ-Z2音频工程。首次板上开环采集16384帧，预测和残差均与整数参考逐样本一致，无饱和，预测误差降低6.92 dB。证据为用户返回的metadata及短噪声听感，详见 [板上实测记录](report/verification/audio_residual/board-result-2026-10-19.md)。

本地已完成25项软件测试、RTL集成仿真和整板构建；[上板包](board/audio_residual/README.md)与[验证报告](report/verification/audio_residual/README.md)对应。**闭环稳定增益ASG、完整音质和端到端延迟仍未验证**；6.92 dB不是扩声音量增益。

旧记录的128/256/512抽头离线比较为4.28/9.80/10.17 dB，首版选择256；新旧记录和评分窗口不同，不能直接认定性能退化。历史过程保留在 [项目进度](docs/progress.md)。

新队员从 [10月19日交接](docs/handoff-2026-10-19.md) 和 [入门导航](docs/getting-started.md) 开始，再读 [证据索引](report/evidence-index.md)。源码、构建脚本、操作模板和结果摘要纳入本次同步；原始NPZ、板上候选模型及含实测输出的Notebook仍留在板卡，克隆仓库不能自动复现实物指标。

## 开发入口

- [工程入门导航](docs/getting-started.md)：新队员按顺序阅读的入口，每一步都有文件、关注点和理解检查。

- [工作区结构与系统框图](docs/workspace-architecture.md)：目录用途、核心文件职责、实时直通/开环标定/建模流程及接口关系。

- [核心代码阅读顺序](docs/core-code-reading-guide.md)：从实时直通、开环采集读到路径拟合与定点参考，核心源码已补中文注释。

- [团队 AI 开发规范](docs/ai-development-policy.md)：分工、接口、验证、上板与协作记录；各人的 AI 从 [AGENTS.md](AGENTS.md) 开始。
- [开发计划](docs/development-plan.md)：软硬件划分、算法路线、历史计划与验收条件。
- [麦克风接口分析](docs/hardware/microphone-requirements.md)：已知输入条件和待确认参数。
- [Git Bash 与仓库使用](docs/repository-guide.md)：定位本地目录、提交与同步。
- [参考资料](references/README.md)：板卡手册、原理图与赛事指南。

已确认设备为 PYNQ-Z2、MAX4466 和 USB 供电有源音响。官方软件使用 BaseOverlay("base.bit")，音频驱动 AudioADAU1761，I2C 编号 1。MAX4466 的实际供电、增益、声道接线需补记；当前 Vivado 为 2018.3，最小通路工程已有构建脚本。

板上 Jupyter 当前通过 http://192.168.2.99:9090 访问。完整的一键复现流程尚未形成。数据与Notebook位置、当前备份缺口见交接说明；录音传输需明确授权。

## 目录

```text
src/         RTL、Python算法源码及厂商依赖
sim/         仿真与验证脚本
build/       工程重建脚本与本地构建产物
board/       上板程序、Overlay和操作说明
data/        后续测试音频、参考结果与指标
docs/        进度、实验、硬件说明及历史方案
skill/       可复用开发与排查经验
report/      设计报告及 AI 协作记录说明
references/ 厂商与赛事参考资料
scripts/     本地仓库辅助脚本
tmp/         本地临时分析文件，不纳入 Git
```

待实现目录中的 README 仅说明预期内容，不代表功能已完成。文件路径采用英文，正文允许中文。

## 下一阶段

先用已有数据统一新旧评价窗口，解释残差差异；随后开发限时、同等增益的闭环启用/旁路对照。补齐箱体、接线与增益记录，路径变化和自适应语音另行验收。

## 资料使用与记录

按团队要求使用 GitHub 私有仓库。当前未授予全部内容统一开源许可证；厂商 PDF 等第三方材料权利归原作者。赛前公开和许可证按届时规则处理，不自动改变可见性。

每次实验记录接线、输入选择、程序版本、结果和原始证据。推测与实测分开，历史计划保留日期；重要进度同步到本 README 和 docs/progress.md。
