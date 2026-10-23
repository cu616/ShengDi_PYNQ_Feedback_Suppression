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

## 2026-10-20 离线增长判据与回放

任务：完成 C 线可独立开发的离线判据、文件回放和可控测试，回答“哪些信号在何时触发报警、
哪些区间尚不足以判断”。实现为 `measurement.py` 与 `scripts/replay-audio.py`；
[输入输出与默认参数](../../../docs/contracts/audio-closed-v1.md#离线测评-v12026-10-20c)。

受控标签依据输入构造：恒幅纯音不增长，短促音只持续 80 ms；渐强音按指定 dB/s 指数增加，
增长起点在 0.25 s；缺帧位置由显式帧号确定。语音用例是多谐波、变基频与音节包络的替代信号，
不是真实人声。另把 B 的闭环模拟器 `keep_signal=True` 返回的实际播放序列接入回放：
纯延迟路径增益 0.5、数字增益 3 的旁路环路理论上不稳定，完美模型抵消后反馈项为零；
预期依据该解析关系，不读取模拟器自己的 `diverged` 标志作为测试答案。

证据（均为软件/合成输入，不含录音）：

- [完整软件回归输出](measurement-tests.txt)：记录解释器、NumPy、测试源哈希及实际结果。
- [13 个受控场景的结果](measurement-cases.json)、[命令输出](measurement-demo.txt)：
  保存每项预期、实际结果、覆盖范围、首次报警和相对已知起点的时间。
- [逐窗轨迹](measurement-trace.csv)：定位频点、窄带占比、趋势、确认时刻；不含原始 PCM。
- [文档检查输出](measurement-doc-check.txt)。

首轮检查输出文件尚未落盘，产生一条自引用证据断链；[初次输出](measurement-doc-check-initial.txt)
保留，文件生成后重新检查。最终验收以前面的文档检查输出为准。

本轮实际结果：完整软件回归 82 项通过，受控回放 13/13 项符合预设。

| 输入组 | 受控结果 |
|---|---|
| 恒幅音、噪声、语音替代、短音、快速起音后恒幅 | 未报持续增长 |
| 三种持续渐强音 | 均报疑似增长；相对已知增长起点的延迟为 0.406–0.502 s |
| 数字满幅 | 独立报告满幅，不冒称声学啸叫 |
| 中段缺帧、仅尾缓存 | 报数据不足，不判整段稳定 |
| 模拟器完美抵消 / 超阈值旁路 | 分别为未检出增长 / 满幅保护线索 |

以上时间来自信号帧号，不是硬件停止时间；这些样例不构成真实人声误报率或现场准确率。

专项测试还覆盖真实工程采样率、任意分包下结果一致、缺口清历史、短尾缓存、
满幅独立分类、输入乱序/越界拒绝、NPZ 单位与帧范围恢复，以及 CLI 只读和拒绝覆盖。
没有修改 B 的算法、原驱动或 bit/hwh，没有执行板卡、播放、现场停止或音质验收。
后续必须将观测能力接入整次实验，再用真实人声与实物反馈验证参数。


## 2026-10-23 C 测量复核 v2

基线：从 GitHub HTTPS 提取 main `03f3063a5dd7fbf658a8fe3be9bdf4da515f64f4`，
在独立目录集成 A `59aa10e537c43ba2ba259e474c487eebaa88740d` 的板端资产与公开历史汇总；
B 只读核对到 `2a3c34e95d54af6c54043901c9a547c604bf5a17`。
旧 C 分支及未合入 main 的增长检测 `4e266e3` 原样保留，复用其计算实现作为 growth_monitor.py。
C 不修改底层驱动、RTL 或抵消算法。身份边界以本轮用户要求和 A 提供的新 C 身份为准。

### 已执行的离线验证

[82 项软件回归](measurement-v2-tests.txt) 通过；其中新测评 15 项、批次集成 5 项。
受控信号的独立依据：恒幅正弦斜率 0、指数衰减 −40 dB/s、指数增长 +60 dB/s；
增长实测回归与解析值误差不超过 0.2 dB/s。固定种子宽带调幅噪声是语音替代信号，不是自然人声。
另覆盖削顶但无增长、底噪、短窗、源结束前早停、过渡边界、预测饱和旁路、保护与增长共存、
缺帧、错误范围、配置/版本/对齐错误、坏 NPZ、只读复算、通信中断、KeyboardInterrupt、
保存失败、未知版本不调用驱动、全 18 项编排及一个返回 ZIP。
真实音质、自然语音误报/漏报、在线声学停止、现场批次均未执行。
初次测试有一项临时目录的 Windows 沙箱权限错误，改为工作目录 tmp 后通过；没有放宽测量判据。

### 保护计数复核与 A 的最小修复规格

证据：[A 原驱动八项消费方验收](a-driver-baseline-acceptance.json)。这是故意对旧版运行的新规格，
结果为 1 项通过、7 项未满足，不计入上述 82 项回归通过数。
A 的 `board/audio_replay/replay_trial.py` 保护分支原记录：
`min(65535, clip_counts[0])`、`clip_counts[1]`、`clip_counts[2]`。
RTL `saturation_counts={residual_clips,prediction_clips}`；三原始寄存器实际是打包字、gain32、mix32。
模拟输入 `[0x00030002,5,7]` 应为 `[2,3,5,7]`，原保护结果为 `[65535,5,7,null]`。
正常分支的四个计数解包正确，不能把问题扩大为所有记录都错。

最小修复（由 A 修改，不由 C 跨线改动）：

```python
packed, gain, mix = clip_counts
prediction_saturations = packed & 0xffff
residual_saturations = (packed >> 16) & 0xffff
gain_saturations = gain
mix_saturations = mix
```

统一正常/保护/终点/故障分支的快照与保存；不要只轮询中间计数，最后 done/fault 后也读取原始值。
计数 65535 对 prediction/residual 是计数器上限，表示至少该数，不能恢复被 min 截掉的打包高位。
`clip_counts_raw` 原三字必须另存。原版 manifest 对 replay_trial.py 的哈希也已滞后；C 的冻结清单采用实际文件哈希。
不改变目前保护策略；旁路 prediction-only 保护仍记录为数值事件，不能推出声学阈值。

A 返回证据协议建议名 `a-replay-evidence-v2`，签名沿用 replay_trial：
- 所有 post-start 退出先静音/冻结并尽力保存四路、coefficients_q20、source_pcm16、实际 first_frame/completed_frames/frames。
- metadata 增加 driver_evidence_version、clip_counts_raw、source_end_frame_exclusive、source_schedule_verified、
  early_stop、guard_tripped 或 protection_triggered、错误原因、原有 bit/hwh/model/source/coefficients 哈希与实际配置。
- source_end_frame_exclusive 使用回读长度和该 ABI 的 `scheduled < source_length_latched` 帧关系；
  数字源最后一个索引为 N−1，结束边界为 N。它不是声学传播结束，C 另留 50 ms 过渡区。
- 恢复完成后写 `<capture>.status.json`，含 recovery_ok、cleanup_errors、save_error；
  捕获写盘失败仍尽力写状态，不能成功落盘但返回假恢复成功；取消前不许 arm。
- 不要求在驱动中判定啸叫，也不要求改变 FIR、增益、削顶或历史语义。

消费方验收入口：`scripts/check_a_driver.py --driver-dir <A返回目录> --output <新验收.json>`。
以八项全部 accepted 为集成门禁，C 会重跑，不能只改 manifest 字段。
A 负责更新自己拥有的生产契约；本报告是 C 的消费方验收规格，没有改写现行寄存器契约。

### 尾段判断与历史复算

派生结果：[50 条历史试次复核](measurement-review-v2-final.json)，保留每个输入 SHA256 和原 metadata，
输入是 A 分支公开的 12 份 JSON，未取得原始 NPZ，未伪称逐样本重算。
结果：44 条证据不足、6 条执行保护；没有任何一条能仅凭汇总认证增长或稳定。
其中 21 条有区间 `[83713,100097)`、源长度 97656 帧：窗口前 13943 帧仍在播放源，
后 2441 帧约 50 ms，连本版 2442 帧过渡区都不足，不能称为纯尾段。
其余项目不能补填源结束、原始波形或全程谱覆盖。缺数据的保护项保留保护标志、实际时间未知。
原 error 中旧格式的 `prediction,residual,gain+mix` 元组不当作现行三寄存器原字强行解包。

A 的历史 [512 报告](../audio-replay/2026-10-22-512-taps.md) §15 另有决定性时间矛盾：
其自述源 1 秒，而保护 327–961 帧即停止，对应约 6.70–19.68 ms，远早于源结束。
在该描述下，保护捕获不能作为纯尾段，原“尾段 +7326/+7127/+856 dB/s”不再具有尾段斜率资格。
原始 NPZ 不在仓库，C 不能重拟合这些数字，也不能据此断言声学增长一定没有发生。
依赖这些斜率的 −2/−6 dB 阈值、512 多约 4 dB 的尾段比较标为待原始证据复核；
依赖保护边界的 §11/14 “+4.5 dB”也不能升级为失稳 ASG。
这些处理不改写 A 原报告，也不认证/否定其他时域抵消量、CD 或其他场次 ASG。

### 测评口径

计算版本 `c-measurement-2.0.0`，实现 [evaluation.py](../../../board/audio_replay/evaluation.py)。
五类：invalid、unknown、protection、no_instability_observed_in_window、observed_instability。
类别是展示摘要；event_flags 独立保留保护、早停、满幅、四类计数和增长，保护与增长可以并存。
配置/版本/对齐/完整性有误为 invalid；缺记录或窗短/底噪/声源结束未知为 unknown。
保护不是啸叫。observed_instability 只描述合格尾段的窄带增长证据，不能独自证明因果。
不写无依据 confidence，MSG/ASG 留 null，不把未测写 0。

固定候选参数：窗 16 ms、步 8 ms、增长历史 80 ms、确认 16 ms；
窄带功率占比至少 0.55、增长至少 3 dB、斜率至少 12 dB/s、拟合 R² 至少 0.9、
20–20000 Hz 内（受 Nyquist 限制）、频点漂移最多 2 bins、音调下限 −55 dBFS。
R² 是拟合统计，不是置信度或检测准确率。噪声底门限也是事前固定候选，真实场景性能未校准。
每个增长证据的全部样本必须无满幅污染；削顶但无合格增长只保留电平事件。
无增长还需足够连续历史、信号高于底线、正向对照有效，才给“有效窗口未观察到”。
16k 尾窗口的原始覆盖与全程计数覆盖分别记录；没有全程频谱观测，不认定全程稳定。

### 固定实验包集成与交接

[操作单](../../../board/audio_closed/BATCH_GUIDE.md) 是完整流程与恢复说明。
新 [统一入口](../../../board/audio_replay/experiment.py) 和 [冻结工具](../../../scripts/assemble_experiment.py)
不触碰设备，实际播放只调用 A 的驱动；代码在模拟 18 项编排中验收。
当前交付是可离线执行、已冻结的集成候选，status=offline_only：
Git 没有现有可加载系数文件，A 原驱动尚未满足证据协议；不能把资产清单冒充可发声 ready 包。
收到修复驱动、已有兼容模型和现场配置后，C 一条集成命令自动验收并生成新 ready ZIP，
无需 A 拼代码、不要求 B 新建模型。初次包的模型缺失不以假系数替代。

待 A 的新协议属于生产方接口工作；待 A/B 的模型字节属于已存在材料回传，不是算法研究前置。
不操作板卡、没有上板实测、没有新实测 MSG/ASG；原数据不修改，复算结果独立保存。


### C 分支发布验证

首轮 main 工作树验证为上述 82 项。随后按用户指出的开发规程同步并集成到 C 分支，
保留 C 既有 R-002、离线回放等用例，[C 集成回归](c-branch-integration-tests.txt) 为 102 项全部通过。
代码、消费方验收程序、历史派生结果与完整压缩包均通过 C 分支交付，不再只给本地路径。
源码包是 C 集成后的文件快照，内附逐文件 SHA256；离线实验包仍为已冻结的 c-experiment-2.0.0。
仓库路径：build/packages/c-integration-source.zip、build/packages/c-experiment-v2-offline.zip。
