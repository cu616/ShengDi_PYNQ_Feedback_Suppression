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

**最后动作**：2026-10-26取得A=b104f20/B=e9e267b，独立核验新场六原件、实际播放参考/Q20、184/185帧延迟及逐段频谱；以原C判据验证325Hz稳定/增长/缺口控制。后续真人−6保护推翻早先“−6可安全真人测试”建议，不发旧包手改增益版。已提出A连续原始采集字段/验收、B同场Q20完整交接，两者并行，R-007仍done。
**当前卡点**：新场实录Q20=93f7ab6e…与C冻包c9d3b1e6…不同，尚无可部署的新场Q20/场景及真人工作点资格；−5.5只是两档中点，不作为精确MSG或0.16dB预测验证。v2只有事后16384帧尾环，没有单arm连续分块协议。A已修部分路由/记录字段，但完整夹具实跑仍因test_start_control旧绝对路径退出1。保持负面听感与未测项，不自动旁路、升档或改保护。

- [r4原包审核](../report/verification/audio_closed/sprint-rc0-20261025/a-d013930-review.json)、[结果与边界](../report/verification/audio_closed/batch-control.md#2026-10-25-ad013930原回包独立审核)、[唯一操作单](../board/audio_closed/BATCH_GUIDE.md#2026-10-25-集中实验-rc0)。r4原返回ZIP191815字节，SHA256=9fd5c28704df0b35750cdf85fbd66cfee894db0467bb3ef22af0c9c3cb0a3422，成员及包身份全部通过。
- [r4五原件独立波形复算](../report/verification/audio_closed/sprint-rc0-20261025/a-63f6a69-waveform-review.json)：A=63f6a69的r4-review-return.zip共2082636字节、SHA256=e9aedd0d865b40f880d8578d5275a592ce8322086def620b86654702cf787b48；5/5与原清单一致。四FIR源内功率和两次差分吻合，五份环形尾部预测/残差/输出算术零失配；60秒原时间线与状态一致，声学覆盖边界不变。
- [真人完整ZIP](../build/packages/c-sprint-rc01-human-r1.zip)、[归档验收](../report/verification/audio_closed/sprint-rc0-20261025/sprint-package-check-human-r1.json)：源码59f2b2a，365967字节，SHA256=0d0a006b12df0c5b45f7049db44aa52e07769cb1b7f17b2f827bcb30f5e69c0e；48载荷/A七件/C八件身份与实际归档5项自检原样复现通过，8类负例拒绝。SELFTEST min14920/gate passed/0.434分钟，现场未测。
- 绑定资产仍A=85f4967/v2 bit61bb71aa…/hwh92b499a3…；d013930是结果提交。strong、EQ identity、−14dB/Q12=817、Codec40不变。失败静音停批，不升档、不自动旁路、不装旧场系数。
- 真人包只做2门禁、真人、听众关/开5项；PROXY触板前拒绝，明确人耳负面记failed，四份固定增益/无AGC录音缺失记未测。A的run_rc4_human2.sh仍在START回调返回前倒计时讲话、自动填人工确认；原脚本控制复现通过。待本次保护问题核实后，使用C唯一Notebook在实际START后讲话，听众用同一固定录制源。
- [A新增三次回包审核](../report/verification/audio_closed/sprint-rc0-20261025/a-9edd83b-review.json)：均是旧r4 1.0.4，不是human-only 1.0.5。首次听感OTHER；第二次约3.568秒保护，原回包记录prediction/residual=0/2、保存窗麦克风满幅13样本，原因未知；第三次14920帧定音窗存在、tonal_fraction=0.746<0.8。三次清理回执通过，不据此证明声学可用或已排除故障。
- 两组总/中带响应均减小，高带均增大，低带方向不一致；只描述14408帧源内窗，不推出整体抑制或ASG。60秒PCM覆盖约0.559%，全程声学未知，真人/听众不能以PROXY填通过。
- [B=7c6d3ed最终验收](../report/verification/audio_closed/sprint-rc0-20261025/b-7c6d3ed-review.json)：与8b01999同Git blob，原134项回归通过；真实正例及对照均通过、原数不变。采样界及旧场限定等请求修订接受，新增预算数字仍未独立复算、不参与现场放行。60秒output在B侧仍未测，不混用C证据；默认与候选不变。
- [B入口完整回执](../report/verification/audio_closed/sprint-rc0-20261025/b-7c6d3ed-cli-controls.json)：C[专用检查器](../tools/check_b_waveform_cli.py)正例通过、八坏例均退出2且ok=false/附诊断，整体退出0，末行positive=passed/bad_rejected=8/8。R-007按既定r4范围关闭，不重开旧判据/候选；B的新场同场Q20交接另列R-012，沿用其唯一生产脚本。
- [给B的冻结原始汇总包](../build/packages/c-r4-to-b-r1.zip)、[字节与哈希核验](../report/verification/audio_closed/sprint-rc0-20261025/b-handoff-r1-check.json)：入口summary-v3.json → fir_switch_pairs两组，含原A回包和C审核；376395字节，SHA256=474975275f63173e490c23ea3d97ad77c0a78a5d0977ba8da807bb7bdfc20367，14载荷通过，源c0af379。新增波形取固定A=63f6a69的r4-review-return.zip；C波形复算已完成，B按同一原件补独立判读。
- 用户常设要求：每轮回应前分别检查A、B是否需要派单；有新动作就给完整可转发消息，无新动作明确写无需新增。按最新提交去重，不因等待原件重复已经通过的现场项目。
- [A更新交付复核](../report/verification/audio_closed/sprint-rc0-20261025/a26-delivery-binding-review.json)：配齐且核对冻结原包夹具后，routing实际退出0，start_control仍读旧绝对路径并退出1，整体DELIVERY_INCOMPLETE。接受summary.scene.layout说明及旧max_stable_gain_db改null的修订，R-009只保留未闭合软件/来源绑定；不重复保护注入或已通过START语义。
- [下次发包外部输入清单](../board/audio_closed/BATCH_GUIDE.md#下一次真人发包必须随消息列全的外部输入)列全A需外部产生的四WAV、固定源与实测布局；没有WAV则listener未测，失败停批不为录齐而继续。C交付消息漏列责任已补，旧冻结包字节不改。
- [门禁与耦合独立复核](../report/verification/audio_closed/sprint-rc0-20261025/gate-coupling-review.json)：首项已有传入底噪+6dB及定音0.8，后续漂移另判；冻结旧底噪−37.8不能当新场测量。下一包需当前同场静默证据绑定，未知不自动适配或重置。A报宽带+3dB未交原校准捕获，C只核算差值，不接受解释全部现象；同RMS而不同峰值、同1kHz而不同宽带的受控反例通过。
- [10/26增益与采集独立复核](../report/verification/audio_closed/sprint-rc0-20261025/a26-gain-and-capture-review.json)：六原件哈希/实际ref与source及v2 bit通过；直接内积延迟184/185。未对齐与诊断对齐后合格bin为428/1052（总4046），460–3000Hz仍未知；对齐诊断不是部署保证。已有六片可继续按段训练/验证，不能称物理不可拟合或把0.336秒认作唯一根因。
- [连续采集具体请求](../report/verification/audio_closed/batch-control.md#2026-10-26-增益决定与连续采集请求)：A负责新契约/底层，目标单装载单arm八块ref/mic；C已有显式帧号/缺口重置的接收判据。v2不具备运行中原子快照/银行确认；多次arm只能独立段。R-013先做静音吞吐/原子性可行性，不承诺2.684秒连续已实现。
- 325Hz作为局部诊断与全带并列，不把0.93能量集中度独自判啸叫或接近起振。原C增长判据已验证稳定325Hz不报增长、增长325Hz报疑似证据、跨缺口不累计；未改现有门禁/保护阈值。A报告保护计数−3为prediction/residual=0/9，真人−6为0/2；仅解码已有回执，不据保护求精确阈值。
- 收尾已通过官方API读A=ca9b484的统筹审阅，仅文档/状态变化，没有新增模型或接口；其现场/离线分级、SNR/对齐/串行预算及先停声后保存原则与本轮合并执行。B的科学口径修订归同一R-012，不再开平行任务；现有有效观测保留，旧系数不再多档证伪。
- [冷启动完整包](../build/packages/c-cold-start-r1.zip)：389560字节，SHA256=aba7466c675dd1829cbfae8a0db03621bac21a210692eac50923da0cedee790a；[机器报告](../report/verification/audio_closed/sprint-rc0-20261025/cold-start.json)资产字段非空，原冻结包用a_assets，新生成器兼容assets同值别名。
- [听众管线完整包](../build/packages/c-listener-pipeline-r1.zip)：49280字节，SHA256=e6325c23de965f695bed7ba730c60168ed55512036f242f1d0f78c6f26a2ea58；[机器报告](../report/verification/audio_closed/sprint-rc0-20261025/listener-pipeline.json)扣背景后的语音变化2.999839dB，原snr_db总录音/背景口径差2.978339dB，均距+3dB小于0.5dB；全为合成WAV，不算真人。
- [正式退出码与独立解压复核](../report/verification/audio_closed/sprint-rc0-20261025/delivery-r1-check.json)、[原工具回执](../report/verification/audio_closed/sprint-rc0-20261025/delivery-r1-console.json)。每个交付只回答一个问题，首行来自其真实检查器最后一行；非0不作交付，缺陷附D1–D4和具体命令。接收方无需提供文件，后续现场四份固定增益录音仍由A外部录制。
- [最新真人回包接收](../report/verification/audio_closed/sprint-rc0-20261025/a-50f30dd-human-receipt.json)：A=50f30dd的7成员/冻结human-r1身份通过、门禁通过、无保护、清理通过；仍2项停在NO_AMPLIFICATION，明确failed。标题称5cm但scene写15cm，实际距离/声源未核实；麦克风未满幅只限保存尾窗的metadata统计，不推全8秒。没读人声PCM，听众未测；R-009启动脚本字节未改，事实补正与原D4合并处理，不新派有声试验。
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
