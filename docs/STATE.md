# 项目现状

> **本文件是"现在是什么状态"的唯一权威。**
> 每次会话结束**原地覆盖**本文件中自己负责的那一段，不要新建副本、不要在别处复述。
> 其他文档若与本文件冲突，以本文件为准。

最后更新：2026-10-20 12:55，B 线（数据与算法）

## 一句话

在 PYNQ-Z2 上用 PL 侧 256 抽头定点 FIR 抵消声反馈，目标是提高稳定扩声音量；
**目前只有工程链路和数字核对通过的证据，没有任何正常扩声条件下的抗啸叫效果证据。**

## 当前唯一目标

在正常可听扩声、同一硬件同一增益的条件下，得到旁路/抵消的成对对照，
并测出可重复的稳定增益差（ASG）。其他一切工作都应指向这一件事。

## 三条线（各改各的段，减少合并冲突）

### A 实物与板卡

**最后动作**：2026-10-19 完成闭环零/真实模型的低增益数字核对（−36 dB）。
**当前卡点**：三个标定数据文件还没拷出板卡，B 因此拿不到真实数据。见 [R-001](REQUESTS.md)。

- 唯一操板者。
- 下一个可交付：把 `training_box_v1.npz`、`validation_box_v1.npz`、
  `candidate_box_v1_256.json` 拷到电脑任意目录（约 1 MB，不含人声）。
- 之后：建立正常扩声基线 + 一轮成对对照。

### B 数据与算法

**最后动作**：2026-10-20 交付逐频点分析与闭环参考模拟（62 项测试通过），结论全部来自合成夹具。
**当前卡点**：等 A 的三个文件（[R-001](REQUESTS.md)）；不依赖它的部分可先做。

- 已交付的东西在 [契约](contracts/path-analysis-v1.md)，代码在 `src/feedback/`。
- 拿到三个文件后，一条命令即可产出真实共振峰、CD 最差频点、128/256/512 的 ASG
  对照与现场增益点位：`python scripts/analyze_path.py --data-dir <目录>`。
- 可选并行：512 抽头的 RTL 仿真与布局布线（现在只有公式推算）。

### C 测评与工具

**最后动作**：2026-10-25从固定源码be3200e建立独立干净检出，CPython3.14 -I -S分别运行cold-start/listener-pipeline均退出0、生成PACKAGE_COMPLETE；两个ZIP在独立解压目录再用包内检查器通过。冻结Q20/bit/hwh和三点映射一致，合成+3dB误差约−0.000161dB，三类坏输入全部failed；164项软件回归通过。R-010/R-011关闭，旧真人ZIP保持。
**当前卡点**：R-009等A修复run_human_r1.sh超时/取消仍START的D4并核实旧保护事件，本轮不排现场。R-007继续既有发布文字与波形判读，无新增B任务；冷启动是离线软件复现，另一队友现场复现仍未测，旧默认与无新候选决定不变。

- [r4原包审核](../report/verification/audio_closed/sprint-rc0-20261025/a-d013930-review.json)、[结果与边界](../report/verification/audio_closed/batch-control.md#2026-10-25-ad013930原回包独立审核)、[唯一操作单](../board/audio_closed/BATCH_GUIDE.md#2026-10-25-集中实验-rc0)。r4原返回ZIP191815字节，SHA256=9fd5c28704df0b35750cdf85fbd66cfee894db0467bb3ef22af0c9c3cb0a3422，成员及包身份全部通过。
- [r4五原件独立波形复算](../report/verification/audio_closed/sprint-rc0-20261025/a-63f6a69-waveform-review.json)：A=63f6a69的r4-review-return.zip共2082636字节、SHA256=e9aedd0d865b40f880d8578d5275a592ce8322086def620b86654702cf787b48；5/5与原清单一致。四FIR源内功率和两次差分吻合，五份环形尾部预测/残差/输出算术零失配；60秒原时间线与状态一致，声学覆盖边界不变。
- [真人完整ZIP](../build/packages/c-sprint-rc01-human-r1.zip)、[归档验收](../report/verification/audio_closed/sprint-rc0-20261025/sprint-package-check-human-r1.json)：源码59f2b2a，365967字节，SHA256=0d0a006b12df0c5b45f7049db44aa52e07769cb1b7f17b2f827bcb30f5e69c0e；48载荷/A七件/C八件身份与实际归档5项自检原样复现通过，8类负例拒绝。SELFTEST min14920/gate passed/0.434分钟，现场未测。
- 绑定资产仍A=85f4967/v2 bit61bb71aa…/hwh92b499a3…；d013930是结果提交。strong、EQ identity、−14dB/Q12=817、Codec40不变。失败静音停批，不升档、不自动旁路、不装旧场系数。
- 真人包只做2门禁、真人、听众关/开5项；PROXY触板前拒绝，明确人耳负面记failed，四份固定增益/无AGC录音缺失记未测。A的run_rc4_human2.sh仍在START回调返回前倒计时讲话、自动填人工确认；原脚本控制复现通过。待本次保护问题核实后，使用C唯一Notebook在实际START后讲话，听众用同一固定录制源。
- [A新增三次回包审核](../report/verification/audio_closed/sprint-rc0-20261025/a-9edd83b-review.json)：均是旧r4 1.0.4，不是human-only 1.0.5。首次听感OTHER；第二次约3.568秒保护，原回包记录prediction/residual=0/2、保存窗麦克风满幅13样本，原因未知；第三次14920帧定音窗存在、tonal_fraction=0.746<0.8。三次清理回执通过，不据此证明声学可用或已排除故障。
- 两组总/中带响应均减小，高带均增大，低带方向不一致；只描述14408帧源内窗，不推出整体抑制或ASG。60秒PCM覆盖约0.559%，全程声学未知，真人/听众不能以PROXY填通过。
- [B最新发布复核](../report/verification/audio_closed/sprint-rc0-20261025/b-3657242-review.json)、[接受项与余项](../report/verification/audio_closed/batch-control.md#2026-10-25-b3657242发布复核与a新增真人回包)：原CLI退出0，revision=1/pre_registered=false及保存结果完全吻合；数学函数、phase/Q20入口和旧dbf原件未改，N2/N3接受。N1旧必要条件式/旧加法标签残句仍在；0.690dB定音差不能证明0.807dB低带差的原因，采样余量不能证明OFF本来就稳。
- [给B的冻结原始汇总包](../build/packages/c-r4-to-b-r1.zip)、[字节与哈希核验](../report/verification/audio_closed/sprint-rc0-20261025/b-handoff-r1-check.json)：入口summary-v3.json → fir_switch_pairs两组，含原A回包和C审核；376395字节，SHA256=474975275f63173e490c23ea3d97ad77c0a78a5d0977ba8da807bb7bdfc20367，14载荷通过，源c0af379。新增波形取固定A=63f6a69的r4-review-return.zip；C波形复算已完成，B按同一原件补独立判读。
- 用户常设要求：每轮回应前分别检查A、B是否需要派单；有新动作就给完整可转发消息，无新动作明确写无需新增。按最新提交去重，不因等待原件重复已经通过的现场项目。
- [冷启动一条命令](ref/cold-start-reproduction.md)只验证冻结资产与软件证据；[A新入口控制](../report/verification/audio_closed/sprint-rc0-20261025/a-9be9fa0-human-routing-review.json)实测wait=None/CANCEL/GO均返回START，D4未闭合。当前两项离线交付不依赖A给文件，也不替代真人扩声/听众或另一队友板端复现。
- [冷启动完整包](../build/packages/c-cold-start-r1.zip)：389560字节，SHA256=aba7466c675dd1829cbfae8a0db03621bac21a210692eac50923da0cedee790a；[机器报告](../report/verification/audio_closed/sprint-rc0-20261025/cold-start.json)资产字段非空，原冻结包用a_assets，新生成器兼容assets同值别名。
- [听众管线完整包](../build/packages/c-listener-pipeline-r1.zip)：49280字节，SHA256=e6325c23de965f695bed7ba730c60168ed55512036f242f1d0f78c6f26a2ea58；[机器报告](../report/verification/audio_closed/sprint-rc0-20261025/listener-pipeline.json)扣背景后的语音变化2.999839dB，原snr_db总录音/背景口径差2.978339dB，均距+3dB小于0.5dB；全为合成WAV，不算真人。
- [正式退出码与独立解压复核](../report/verification/audio_closed/sprint-rc0-20261025/delivery-r1-check.json)、[原工具回执](../report/verification/audio_closed/sprint-rc0-20261025/delivery-r1-console.json)。每个交付只回答一个问题，首行来自其真实检查器最后一行；非0不作交付，缺陷附D1–D4和具体命令。接收方无需提供文件，后续现场四份固定增益录音仍由A外部录制。
- C未操板或改A/B实现。10/26质检，10/27 20:00冻结，10/28另一队友复现并冻结源码/bit/hwh/模型/配置/哈希；v2外部I/O签核仍不完整。

## 已验证 / 未验证（只在这里写一次）

**已验证（有证据）**

- 最小 PL 直通、开环采集、256 抽头 Q20 FIR 板上逐样本一致，误差降 6.92 dB。
- 闭环零模型与真实模型两模式在约 −36 dB 下回读 bit_exact、无饱和、能恢复静音。
- 38 项既有软件测试 + B 线新增 24 项，共 62 项通过。

**未验证（不得当作已实现）**

- 正常扩声下的旁路/抵消对照；MSG / ASG 实测。
- 端到端电学延迟；音质；人声误切率。
- 512 抽头的 RTL 仿真与布局布线。
- 完整板级 I/O 时序签核（仍缺 1 输入 / 3 输出延迟约束）。

## 关键数字（只在这里写一次，其他文档一律链接到本节）

| 项 | 值 | 口径 |
|---|---|---|
| 开环预测误差降低（板上） | 6.92 dB | 宽带 RMS，16128 帧，**不是 ASG** |
| 开环预测误差降低（开发集） | 9.69 / 9.80 dB | 不同评价窗口，不可与 6.92 直接比 |
| 长度对照（真实数据 256/512） | 9.80 / 10.17 dB | 复用验证集，属开发比较 |
| 环路总延迟 | ≈71 采样 ≈1.45 ms | 2 帧调度 + 69 帧路径，**推算非实测** |
| 起振频点间隔 | ≈688 Hz | fs/71；只能在此整数倍附近起振 |
| 数字增益上限 | +18.06 dB（8×） | Q4.12 系数上限 32768 |
| 架构抽头上限 | ≈680 | 每抽头 3 拍，3N+3 ≤ 2048 |
| 抽头覆盖距离 | 256→1.79 m，512→3.60 m | 343 m/s，按抽头数换算 |
| ASG | **无实测值** | 只有合成预测，禁止写进报告当性能 |

## 板卡占用

- **空闲**。2026-10-20 12:22 由 B 探测 `192.168.2.99:9090` 不可达（板子在 A 处）。
- 规则：谁要操作板卡，先在这里改一行「占用中 / 线 / 时间」，用完改回空闲。
  单板排他，比任何聊天约定都可靠。

## 下一步

1. A：把三个标定文件拷出来 → B 当天可交付真实增益范围与 ASG 预测。
2. A：用 B 给的增益点位做一轮成对对照（旁路叫、抵消静才算证据）。
3. B：真数据到手后重算真实 CD(f) 与抽头对照，并给出 512 的可行性结论。
4. C：补全过程观测覆盖与啸叫判据。
