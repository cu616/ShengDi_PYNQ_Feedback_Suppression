# 项目现状

> 唯一状态与数字口径入口。最后整理：2026-10-30；队长已 fetch 核对 A=`2c7b955`、B=`86061a7`、C=`330e135`，硬件载荷沿用既有版本。
> 本轮安排视频、教程、报告与提交候选集成，未操板或改变程序/位流；提示词已生成，队友接收与执行仍以实际回复为准。

## 一句话

v3 工程基线可以冻结：实时抵消主路、宽残差过增益、保护与连续运行已有工程证据；扩声有定性阳性观察，固定单频的抵消有派生复算结果。正常语音下的抵消附加收益与可重复 ASG 仍未完成验收。

## 当前唯一目标

保留可恢复的 v3 基线，完成真人使用演示、HTML教程、报告与完整提交候选。具体分工、指南要求、合并冲突及内部排期见 [材料交付安排](../materials/planning/submission-plan.md)，视频按 [分镜方案](../materials/planning/video-plan.md)。使用 [版本及旧入口索引](../board/audio_replay/README.md)，不再从历史 Notebook、临时脚本或旧日志自动生成新试验。
10 月 28 日排期保留在 [原冻结计划](ref/development-plan.md) 供追溯；截止已过不等于未测项目自动通过，也不要求补跑过期计划。

## 三条线

### A 板卡底层、硬件集成与现场

**最后动作**（2026-10-30）：接收队长拍摄任务，转入真人演示与硬件可集成版本；主驱动 `79c4d9f7…`、RTL、位流 `48e38f78…` 未变。
已交 [integration.json](../materials/work/a/integration.json)（32 项硬件白名单）、
[hardware.md](../materials/work/a/hardware.md)（PS/PL 分工、保护归属、构建复现）、
[shooting-plan.md](../materials/work/a/shooting-plan.md)（一次现场窗口操作单）、
[takes.md](../materials/work/a/takes.md)、入口 `demo_take_v3.sh`。

**当前卡点**：板卡此刻不可达，`demo_take_v3.sh` **未在板上执行**（仅静态检查），现场开头先冒烟；
素材与首剪待 10-31；可听收益未定；C 的原件级复算未做；B 段（g=−3）需授权。

- 发布载荷以 [v3/manifest.json](../board/audio_replay/v3/manifest.json) 的整组哈希为准，维护源码与历史顶层包不要整目录混传。板卡部署位置及回退位置见“板卡占用”。
- 最新驱动已记录混搭拒绝、静默自检、输入满幅停声恢复与连续运行四项硬件检查，见 [工程证据](../report/verification/audio-replay/wide-residual-v3/evidence.json) 的 `driver_79c4d9f7_full_verification`。无改动不重跑。
- 新 [三臂派生回包](../report/verification/audio-replay/wide-residual-v3/C-tone-1746930178556850644.json) 保留原件及副车哈希，配对和捕获数值检查通过。完整捕获窗与共同含源窗分别计算，原始 PCM 留板。
- 分析脚本字节差异已核对：Git C 脚本加 UTF-8 BOM 并转 CRLF 后，恰好得到回包中的 producer SHA256；不据此安排重采。
- 停声条件包括输入满幅、预测/增益后/混音饱和及故障；增益前残差越过旧窄位宽上限只记录。保护停声不标成“检测到啸叫”。
- `played_level_report.sh` 保留为问题复现样本，排除在正式测量入口外。现有三臂记录可以取共同含源窗，不要求把有声运行缩短到环形缓存时长或改捕获架构。

### B 数据与算法

**最后动作**：已 fetch 核对 B=`86061a7`；队长准备 [B 教程、算法报告与模型交付任务](../materials/prompts/b.txt)，没有重训或缩放模型。
**当前卡点**：新任务尚未确认接收；教程与模型清单可独立推进，最终实测数字需引用 C 确认口径。正常语音的抵消附加收益与最终 ASG 仍缺证据。

- 候选身份见“关键数字”；模型、夹具、Codec 档位和实际系数哈希必须一起核对。
- 单频相位/响度估算保留在 [B 当时的分析](https://github.com/cu616/ShengDi_PYNQ_Feedback_Suppression/blob/86061a7/report/verification/v3-working-point-2026-10-28/README.md)。不能由幅度峰值超过小增益界单独推出“必啸叫”，也不能由单频曲线推出所有语音场景提增益均无收益。
- 本轮不新增 AFC、多速率、抽头扩展或模型候选；后续改进另立版本，不覆盖冻结基线。

### C 测评与工具

**最后动作**：C=`330e135` 的定向验收和分析入口已有，A 已回传派生 JSON；队长准备 [C 候选集成、报告与 Skill 任务](../materials/prompts/c.txt)，已完成分支合并预演。
**当前卡点**：派生回包最终复核与新任务接收均未确认；main/A/B/C 存在已列出的合并冲突，不能宣布 Git 集成完成。C 可先整理无冲突候选文件与报告，不重复已过硬件检查。

- [C 已交付的验收及操作说明](https://github.com/cu616/ShengDi_PYNQ_Feedback_Suppression/blob/330e135/report/verification/audio_closed/sprint-rc0-20261025/v3-c1a180f-review-20261028.json) 与 [A 回包](../report/verification/audio-replay/wide-residual-v3/C-tone-1746930178556850644.json) 是本次交接材料。
- 测量必须指定真实 round_id/manifest，分别报告完整捕获窗与共同含源窗；不使用全目录 glob 的混合均值。
- 旧“输出太小、可听收益为负”的结论已撤回：该次交替段保存的是源停止后的尾窗。听众阳性与阴性原话均保留为定性证据，不自动互相覆盖，也不代替量化差值。

## 已验证 / 未验证

**已有证据**

- v3 算术仿真、带既有约束的综合实现、板上逐样本核对、保护和恢复；源码、载荷、构建与现场证据见 [v3 证据](../report/verification/audio-replay/wide-residual-v3/evidence.json)。
- 零系数扩声配置的连续运行及多次“能听出放大”观察；此前 [真人短时阳性](../report/verification/audio-replay/live-human-first-confirmed-2026-10-27.json) 和 [手机复现](../report/verification/audio-replay/reproduction-result-2026-10-27.json) 分开保留。
- 固定单频三臂已有实际捕获的派生分析，支持该条件下的抵消差异；不扩大为语音收益或最大稳定增益。

**尚未完成的发布指标与限制**

- 正常语音下抵消开启相对关闭的可辨、可量化附加收益，以及重复 MSG/ASG。
- 听众位置定量声压、完整音质评价、端到端电学延迟。
- 四项外部 I/O 延迟约束仍缺失；实现报告只能写“已施加约束满足”，不能写完整时序签核。
- 环形 PCM 只覆盖保存窗口，全程状态记录不等于全程声音记录。候选语音的短时完成不自动成为候选持续使用验收。

## 关键数字

| 项目 | 数值与口径 | 来源 / 使用边界 |
|---|---|---|
| 发布版本 | A=`f8f3df5` 的 v3 载荷；bit `48e38f78…`、hwh `9411adb5…`、driver `79c4d9f7…`、helper `bba22102…` | 整组精确哈希见 [manifest](../board/audio_replay/v3/manifest.json)；本次只改说明 |
| 采样与模型 | 48828.125 Hz；512 抽头，Q20、lag_first=1；前向两帧调度 | 参考历史和前向调度分开，不重复计延迟 |
| 当前候选 | `rewired_512_20261026.json`；文件 `01c9102a…`，候选 Q20 `6118e85d…`，零系数 `e5a00aa9…` | fixture=`room_v1_20261026b`；零系数哈希不能填到候选字段 |
| 最近演示配置 | 手机 6/15、距麦 5 cm、PL −8 dB、Codec 40；麦—音响 100 cm 侧对、金属板与棉 | 与历史手机 8/15、真人 12/20 cm 分开；不自动扩大允许范围 |
| 既有现场允许档位 | −14/−12/−10/−8/−6 dB；预检含 DC 绝对输入峰值严格低于 −6 dBFS | 保持原范围，运行期输入满幅仍停；不把 −3 dB 计划列为待执行冻结步骤 |
| 最新驱动连续运行 | 2929687/2929687 帧，约 60 秒；bit22=0、四类计数0、bit_exact | 零系数配置；A 记录听众“能听出放大”，不是候选 ASG |
| v3 资源与时序 | WNS +0.548 ns、WHS +0.015 ns、TNS/THS 0；BRAM 80%、DSP 3、LUT 3588、FF 5018 | 已施加约束满足；外部 I/O 缺口单列 |
| 纯音复算窗口 | round=`1746930178556850644`；共同源激活帧 `[91037,97656)`，共6619帧 | 从既有末尾16384帧中选取；不含停源尾段 |
| 322 Hz 共同含源窗 | 残差差 8.4609 dB；旁路相对开环麦端抬升 3.7016 dB；抵消相对旁路麦端降低 4.9502 dB；相对开环再低 1.2486 dB | [派生 JSON](../report/verification/audio-replay/wide-residual-v3/C-tone-1746930178556850644.json)；投影仍受噪声与有限窗影响，不是 ASG |
| 整窗旧数字 | 8.43 / 4.24 / 5.45 / 1.21 dB | 完整16384帧包含停源尾段，与共同含源窗是不同统计口径；不混报 |
| 派生文件身份 | JSON `f380c917…`；producer `81297e8a…` | producer 对应 C Git 脚本 `3e7b5b36…` 的 UTF-8 BOM＋CRLF 字节版本 |
| 宽残差修复依据 | 旧事件宽残差1.0230×满幅，乘增益后0.4074×满幅，输出未越界 | [旧事件分析](../report/verification/audio-replay/residual-overflow-result-2026-10-27.json)；增长窗口不足时不排除声学再生 |

## 板卡占用

- 最近 A 记录：空闲，部署在 `/home/xilinx/jupyter_notebooks/base/audio/audio_wide`。本轮仅整理电脑文件，未连接板卡；实时在线/占用状态由 A 与现场再次核实。
- v2 回退位置：`/home/xilinx/jupyter_notebooks/base/audio/audio_live`。本轮未覆盖、删除或部署任何板卡文件。
- 操作前核对场景、整套版本与现场值守；A 为唯一操板者。电脑工作区的“空闲”文字不是实时锁。

## 下一步

1. 用户转发 [A](../materials/prompts/a.txt)、[B](../materials/prompts/b.txt)、[C](../materials/prompts/c.txt) 三份任务。材料汇入 [materials](../materials/README.md)，授权书与 GitHub 公开事项由用户处理。
2. A 固定硬件与拍摄配置；B 做教程/模型清单；C 复核已有回包、整合提交候选与报告，按 [内部排期](../materials/planning/submission-plan.md) 并行推进。
3. 具体冲突由责任线提出处理建议后交队长；本轮未合并 main、未删历史文件。需要新增算法或实质修改时另立版本，不能混入冻结包。

整理前的状态、矛盾句和早期操作单保存在 [历史原文](archive/pre-freeze-guide-2026-10-29.md)，历史证据与日志原件未删除。撤回的“负增益必无扩声”“预测无饱和即可排除再生”“0 dB 必啸叫”“运行必须≤0.336秒”等说法不再作为行动依据。
