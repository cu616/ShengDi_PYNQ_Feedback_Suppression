# audio_replay：发布入口与历史版本索引

动态状态、允许配置、验证范围只查 [STATE](../../docs/STATE.md)。本页回答“文件用来做什么、哪些不能混用”，不是新的发声授权。

## 从哪里取发布文件

电脑端从 [v3/manifest.json](v3/manifest.json) 取得文件清单，按其 `hashes` 核对 [v3/](v3/) 内整组载荷。
该目录保存 bit/hwh、配套驱动与检查器；模型另按 manifest 的 `model` 身份取得，**v3 目录本身不包含全部场景数据和现场入口**。

A 记录的板卡部署目录为 `/home/xilinx/jupyter_notebooks/base/audio/audio_wide/`。
不要将 `board/audio_replay/` 整目录上传：**`archive/` 里的 `audio_replay.bit/.hwh` 与 `manifest.json` 是历史版本**，
顶层维护脚本又已更新，混装会造成版本错误。

## 文件分类

| 文件 / 目录 | 标注 | 保留用途与使用限制 |
|---|---|---|
| [v3/](v3/) | 工程基线载荷 | 使用自己的 manifest；精确身份和验证状态见 STATE |
| 顶层 `replay_trial.py`、`replay_tools.py`、`tone_round_guard.py` 及相应测试 | 维护源码 | 对应发布时按 v3 哈希核验；不与顶层旧 bit/hwh 组合运行 |
| [v3-sw/](v3-sw/) | **带物理算法开关的新构建（未上板）** | v3 + SW0(M20) 强制旁路，capture_status[23] 记录开关；有自己的 manifest 与驱动，**不能与 v3 载荷/驱动混用**；上板前需重跑四项检查 |
| [v2/](v2/) | 历史回退材料 | 只有 bit/hwh 和实现报告；配套驱动需取已记录版本，不能借用 v3 驱动 |
| [rollback-v1/](rollback-v1/) | v1 回退快照 | 保留原 manifest 和文件，按快照恢复；恢复前核对其他导入依赖，不能当 v3 启动步骤 |
| [archive/](archive/) 内的 `audio_replay.bit/.hwh`、`manifest.json` | 早期构建原件（已移入归档） | 保留审计；归档里的旧 manifest 不描述后来更新的维护源码，不修改旧哈希凑通过 |
| `click_panel.py`、`click-panel.html`、`start-panel.sh`、`replay_trial.ipynb`、`replay_session.py`、`sweep_plan.py`、`sweep_session.py` | 历史交互 / 扫档入口 | 早期盒内实验使用，未经现行整包集成不得直接作为演示入口 |
| `live_pa.py`、`live_pa.ipynb`、`live_run.py`、`run_rc4_human*.sh`、`run_human_r1.sh` | 历史使用 / 验收入口 | 保留流程与故障复现价值；旧时长、路径和模型不能当成新配置 |
| [field_ac_segments_v3.sh](field_ac_segments_v3.sh) | v3 已有分段现场入口 | 读取板上 `ac_mode.txt` 的 tone/speech，使用真实现场确认令牌；实际参数和版本先核对 STATE，不自动运行 |
| [long60_v3.sh](long60_v3.sh) | 专项连续运行脚本 | 使用零系数；不把它的运行结果当成候选算法收益。已通过无变化不重复 |
| [tone_arms_v3.sh](tone_arms_v3.sh) | 已替代的纯音入口 | 留作追溯；三臂 manifest 统一由 `field_ac_segments_v3.sh` 的 tone 模式生成 |
| [field_ab_alternate_v3.sh](field_ab_alternate_v3.sh)、[played_level_report.sh](played_level_report.sh) | 有已知测量限制的历史尝试 | 源停止尾窗、全目录 glob、无有效源行回退问题未完成修复；**排除在正式收益测量入口之外** |
| `verify_*v3*.sh`、`clap_test_v3.sh`、`speaker_check_v3.sh`、`listen_probe_v3.sh`、`level_ladder_v3.sh`、`peak_scan_v3.sh`、其他 `field_*` | 专项诊断 / 当时现场脚本 | 名含 v3 不等于发布默认入口；只有受影响故障需要时才核对并采用 |
| `candidate_room_v1_512.json`、`model_lowcut_250_470_512.json`、`scene.json` 等 | 历史模型 / 配置 | 文件名不是适用性证明；按场景、文件和实际 Q20 哈希识别，不能替代 manifest 指定候选 |

## 旧驱动怎样辨认

以下是版本索引，不改变任何旧程序字节。短哈希用于识别，真正装载仍核对完整哈希。

| 驱动 SHA256 前缀 | 保留位置 / 历史来源 | 说明 |
|---|---|---|
| `79c4d9f7` | [v3/replay_trial.py](v3/replay_trial.py) | 发布驱动身份以 manifest 为准 |
| `c2b2a86a` | A 历史提交 `f404948` 的 v3 文件 | 解除静音等待修复前的版本；仅用于复现旧问题 |
| `82787262` | A 历史提交 `e05bb73` 的 v3 文件 | 有输入满幅停声与整对核验，但不是最后交付字节 |
| `6b397359` | A 历史提交 `68e19fa` 的驱动 | 早期 v3，不能拿其验收范围替代后续版本 |
| `2127663` | [rollback-v1/replay_trial.py](rollback-v1/replay_trial.py)；板上历史 `audio_live` | 旧保护语义；v1/v2 的具体 bit/hwh 必须按各次记录配对 |

板上 `audio_live` 是保留的 v2 回退目录，`audio_wide` 是 v3 目录；本轮没有连接或更改它们。
需要找旧驱动时先用 Git 的只读查看或导出到单独目录，勿覆盖当前 v3 同名文件。

## 已有数据复算与恢复

C 的精确轮次分析入口与固定提交见 [STATE 的 C 段](../../docs/STATE.md#c-测评与工具)。A 已生成的派生回包直接用于后续复核，不能把“等待 C 回执”误写成“请 A 再跑一次”。
回退也必须整组核对版本、依赖、模型与保护语义；先保留当前配置和采集文件，再由 A 安排。目录名含 rollback 不代表可以无条件覆盖正在使用的包。

原来的“三格操作”、旧上传目录及按钮页说明已完整保存在 [整理前原文](../../docs/archive/pre-freeze-guide-2026-10-29.md)。它们用于理解历史记录，不作为今天的执行单。

## 本轮材料与报告入口

- 硬件交付清单：[materials/work/a/integration.json](../../materials/work/a/integration.json)（逐项哈希与依赖）、[hardware.md](../../materials/work/a/hardware.md)（分工/保护归属/构建）
- 算法片段：[materials/work/b/algorithm.md](../../materials/work/b/algorithm.md)；离线教程：`materials/learning/index.html`
- 测评与报告：[materials/work/c/technical-report.md](../../materials/work/c/technical-report.md)、[claims.md](../../materials/work/c/claims.md)、[conflicts.md](../../materials/work/c/conflicts.md)
- 可复用技能包：[skill/audio-evidence/SKILL.md](../../skill/audio-evidence/SKILL.md)

C 分支携带的 2026-10-21「逐档增益 A/B」操作页已过期，不再作为入口；其内容仍在 git 历史与对应证据目录中，不删除。
