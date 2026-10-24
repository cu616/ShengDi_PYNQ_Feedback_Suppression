# 批次流程验证

## 2026-10-24 ready 回包复核与门禁 v1.1

任务来自用户转发A=08965d2；C读取该提交的两份原ZIP、重复性、低频及现场说明。
原ZIP和JSON原字节保存在 [复核输入](room-review-20261024/inputs/)，逐文件哈希见
[audit.json](room-review-20261024/audit.json)，来源提交、驱动及B消费脚本哈希见
[review-source.json](room-review-20261024/review-source.json)。C未操板、未新增采集，原NPZ仍在A板上；
这是保存汇总与metadata的派生复核，**没有独立重算原波形**。

两份回包分别9项/3项闭环、28项/13项闭环；第二份7个比较身份中6组完整、1组在0 dB候选保护后未完成。
修正后分别1组/6组配置匹配，但有效效果配对仍均为0：候选尾段低于信号门槛。
第二份两条-3 dB基线尾段有统计值，仅可保留各自窗口内观测；不能以单边有尾段认证候选改善。
第二份末项预测计数4、mic满幅1码并早停；不把削顶单独命名为反馈因果。
A现场说明明确闭环听感码由数值代理填写，派生汇总附该说明文件SHA256，不能作人耳验收。
分别见 [run-1](room-review-20261024/run-1/summary.json)、[run-2](room-review-20261024/run-2/summary.json)。

本轮纠正三处C工具问题：

- 无效尾段仍有实际几何区间，旧工具仅随有效统计导出区间，造成假配置不符；保留区间但不补统计。
- A evidence-v2用stop_reason和终点status/raw计数保存保护结果，旧读取只找guard_tripped，误报安全未知。
  现在按明确ABI读取并保存依据，旧无版本/异常/不全证据仍为null。
- B消费程序要求model_pairs两端capture_id存在，未完成组应另存incomplete_model_pairs；没有丢掉失败行。

实现 [房间协议v1.1](../../../docs/contracts/audio-closed-v1.md#房间执行协议-v112026-10-24a-08965d2-反馈)：
运行门禁5 dB，效果配对另验前后四次1 kHz mic/ref极差1.5 dB；记录实测极差、总体标准差及来源。
两份RUN的mic极差为1.810/1.989 dB，reference极差均为0，因此归一化并不能消除这次漂移。
独立六定音列表重算极差4.710、总体标准差1.590 dB。该列表缺每次reference与原NPZ，不能独立验证其比值。
若机械沿用旧scene底噪-37.8 dBFS，六次中三次也低于底噪+6 dB；放宽漂移限并不自动解决信噪不足。
请求A按已有证据登记修线后的场景/底噪，未知留空；没有为通过而降低通路信号门槛。

A的分频带−max|H−Ĥ|原数字仅记predicted_gain_bound_db，+6 dB为提议设计目标。
小增益充分条件要求可信稳定线性路径的全部环路频率满足严格环路增益<1；
参见 [MIT小增益定理](https://ocw.mit.edu/courses/6-241j-dynamic-systems-and-control-spring-2011/056c92694b953cb4645e4a4c20a363a8_MIT6_241JS11_lec17.pdf)。
四个频带未覆盖DC、3.4–8.2 kHz、8.6 kHz以上等；现场记录中还有9131 Hz峰位。
因此全频段界、MSG/ASG仍为空；+3 dB出现失败并不验证+5.42 dB充分界，需查模型/频率覆盖/路径变化/非线性。
“需要+20 dB、缺口15 dB”也缺正常扩声需求与原测量支撑，C未将其注册为验收事实。
C不修改B模型或算法，接下来唯一数据动作见 [R-004/R-005](../../../docs/REQUESTS.md)。

验证记录：131项[软件回归](room-revision-tests-20261024.txt)通过，新增真实ABI、几何、5 dB运行/1.5 dB比较分离、
不完整配对和代理听感用例。B原59ab1ee消费程序对两份派生结果均0阻断、实测有效配对0，
见 [B消费1](room-review-20261024/run-1/b-consumer.json)、[B消费2](room-review-20261024/run-2/b-consumer.json)。
初次B消费发现空capture_id阻断后修正导出，未通过改B消费者或删除失败记录规避。
新源码用旧A资产完成冻结哈希、驱动8/8、唯一Notebook格和取消不导入pynq的集成检查，
仅作软件验收，见 [整包检查](room-revision-package-check-20261024.json)。
[文档检查](room-revision-docs-20261024.txt)为0错误、0警告。

交付 `build/packages/c-room-review-v2.zip` 为上述离线结果与原输入，不是发声包。
原ready v1冻结不改，不要求重跑。新策略源码在C分支与完整源码ZIP中；强模型及独立验证材料到齐后再冻结下一发声包。

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


## 2026-10-23 B 请求：模型选择、平坦字段和尾段汇总 v3

本轮输入为用户转发的 B 执行请求，不改变 A/B 所有权。已从 B ffa035a 原样接收 models/，
三份原始 JSON 与 manifest 哈希一致、现有 load_candidate 读取通过。房间选择 candidate_512，
箱体选择 baseline_256；房间基线仍保留作同增益比较。加载容量不足拒绝；未知 fixture 不静默回退。
256 补零记录按实际系数识别为 baseline，不能冒充 candidate；C 不改模型或 A 的加载驱动。

软件结果 schema_version=3、calculation_version=c-measurement-2.1.0，
[接口字段和门禁](../../../docs/contracts/audio-closed-v1.md#测评软件汇总-v32026-10-23b-模型比较请求)。
[111 项软件回归](b-request-tests-v3.txt) 通过。新增 9 项专用验收覆盖解析 −6.0206 dB 三带能量比、
0/30 dB/s 斜率、源未结束/未知/外部源活动/短窗/满幅/底噪、模型哈希/fixture/lag/fs/容量拒绝、
同增益配对、增益不符两行 invalid、scene 变化与重复歧义、补零身份、未知事件空值、
输入不改、补充材料 SHA256 绑定及禁止覆盖真实增益。

每个 JSON 行和 CSV 同时直接有 gain_q12、hp_volume、bit_sha256、coefficients_sha256，
系数哈希独立按 NPZ 保存数组的 little-endian int32 计算；有声明哈希时必须相符。
model_sha256 保留原实际文件值，model_registry_sha256 单独指向 B 原交付；
即使 JSON 包装不同，只在实际保存系数与某个基线/候选唯一一致时识别模型，绝不冒充原文件哈希。

尾段 RMS、20ms 块斜率与三个指定频带只在完整、已确认源关闭并经过过渡区的区间计算。
外部源关闭也需记录。空白字段给出 tail_reasons；没有把请求的 1s 尾段视为实际捕获。
比值是观测带内能量比，不自动等同 CD；B 正在核对的源注入假设不影响原始统计保存。
每行保护/各级饱和/mic满幅/mute动作/观察期静音/波形全零各自独立，未知不是 false。
观察结束后的正常静音与观察期间的静音分开，不能把恢复成功推断为没有保护。

基线/候选的 model_pairs 与旧旁路/抵消 pairs 分开。配对不能要求系数哈希相等（两模型本就不同），
但实际增益、音量、bit、源、fixture、scene/session、模式和尾段范围都要一致且非空。
comparison_id 内配置冲突保留两行并标 invalid；无明确身份/重复歧义不自行挑一对。
缺尾段或正向对照、数值事件未排除时 effect_eligible=false，只保留安全/诊断证据。

### 交付的 summary 与完成边界

- [软件用例 JSON](b-request-software-summary-v3.json) / [CSV](b-request-software-summary-v3.csv)：
  一对 actual gain_q12=0 完全相等的基线/候选，所有要求列均存在、三个尾段能量比可读；
  evidence_kind=software_fixture，effect_eligible_pairs=0。此例仅验格式与流程，不验抗啸叫性能。
- [旧 50 条平坦汇总 JSON](b-request-historical-summary-v3.json) / [CSV](b-request-historical-summary-v3.csv)：
  保留实际已知值，其余为空。因本地没有这批原始 NPZ，不能替 B 补出新的尾段统计或真实候选配对。
- 独立静默包 build/packages/c-tail-review-v3.zip；唯一 Notebook 入口和电脑/板卡路径见
  [操作单](../../../board/audio_closed/BATCH_GUIDE.md#本轮优先已有房间-npz-的静默复算summary-v3)。
  只扫描 A 选择的项目数据目录，输出一个 return-results.zip，不发声、不加载 overlay、不写设备。

B 的真实完成标志仍待 A 在板上执行该只读复算并返回统计：至少一对来自 board_recording 的
同增益基线/候选，有有效尾段、配对身份和正向对照；C 不用软件示例冒充这个标志。
原始文件不修改、原始 PCM 不装入回传包。若旧记录不满足门禁，返回空值及原因，
先由 C 定位最小观测缺口，不由用户手工凑数据，也不默认安排新采集。

现有现场包的模型缺件已经解决；仍待 A 修复驱动并给出 256逻辑/512物理加载证据与现场配置。
更新集成器仅放宽到经 A 验证的等价基线加载，不自动补写模型文件；ready 门禁继续保留。


[独立包执行检查](b-request-package-check-v3.json)：实际执行交付 Notebook 的唯一代码格，
软件数据配置配对 1 对、实测可用配对 0 对；未导入 PYNQ，返回 ZIP 无 NPZ，字段齐全。

## 2026-10-23 B 消费反馈：summary v3.1

按用户转发的 B 59ab1ee 消费复核落实兼容增补，不改 A 驱动或 B 算法，
不改变 schema_version=3 / calculation_version=c-measurement-2.1.0 的数值口径。
summary_revision=3.1.0 公开本次遥测变化。

历史位流的出处为 [A 现场报告](../audio-replay/2026-10-21-asg-field.md) §4.1 与完整哈希记录：
dadbbbab…ddcb05 登记 256 taps；4d49dfbe…635316 明确为退役 audio_closed，
逐行 evidence_scope=pl_arithmetic_only、retired_overlay=true、acoustic_evidence_eligible=false，
不进入声学 model_pairs。BIT_CAPACITIES 不把退役位流列为可部署回放版本。

loaded_taps 不用推测填补。derived_loaded_taps 按原模型/补零数组 little-endian int32 哈希派生，
并保留 metadata 或 saved array 的来源；它表示匹配的数组长度，不是硬件 loaded_count 回读。
对历史 44 条得到 256，另 6 条仍未知；原 loaded_taps 全部保留空值。
有实际保存数组或驱动明确记录时，loaded_taps_basis 单列其来源。

positive_control_valid 逐行导出 true/false/null。eligibility_reasons 独立区分 tail_not_validated、
safety_not_validated、positive_control_not_validated/positive_control_failed、算术/配置/来源问题，
即使配置无效也保留这些同时存在的缺口。波形全零、正常结束或恢复成功不代替通路正向对照。

### 模型清单与哈希核对

B 59ab1ee 的 models 仅有三个可部署原模型，derived_artifacts 为两份补零文件，注册数量仍为 3。
C 独立重算每项 coefficients_sha256/padded_512_sha256，与 B 新列一致；两份派生物也核对文件哈希。
B 报告的 manifest SHA256 为 71d13ca927b23213b491ecc0af3a405210c99550dedb11f2878ddd6905573fcc，
对应 Windows CRLF；其 Git LF blob 为 5aac3957ab20a184a0c8ea0526f6cb603dea5244d2b8d9e747dec9c65af07c6d。
两者仅行尾不同。C 冻结前者，并使用已有 models/** -text 保留字节；补零文件也冻结清单声明的 CRLF 版本。
三个原模型文件不变。没有把旧 ce9aa371… 清单冒充新清单。

### 验收与派生结果

- [115 项回归](b-followup-tests-v3.txt)：新增用例覆盖旧位流登记、哈希派生不覆写原始记录、
  退役 overlay 即使带正向对照也不能入声学配对、正向对照失败/未知与其他原因独立、
  derived_artifacts 不注册及清单系数哈希错误拒绝。
- [历史派生审计](b-followup-audit-v3.json)：50 条仍 invalid、22 条标明仅 PL 算术、
  44 条推导数组长度 256；实际 loaded_taps、尾段和保护信息没有凭空补出，实测配对仍为 0。
- [历史新 JSON](b-followup-historical-summary-v3.json) / [CSV](b-followup-historical-summary-v3.csv)
  从既有不可变复核记录再次展开，输入摘要哈希保留，不是原始波形复算；旧交付文件未覆盖。
- [软件新 JSON](b-followup-software-summary-v3.json) / [CSV](b-followup-software-summary-v3.csv)
  仍显式 software_fixture、gain=0，仅验 schema 和流程，不当成板卡效果。
- 原样执行 B 59ab1ee 的 consume_summary_v3.py；[软件消费结果](b-followup-consumer-software-v3.json)
  和 [历史消费结果](b-followup-consumer-history-v3.json) 均 consumable_as_is=true、blocking_issues=[]。

静默包重建为 c-tail-review-3.1.0，操作仍是一个 Notebook 代码格、返回一个结果 ZIP；
独立执行与哈希验证见 [包检查](b-followup-package-check-v3.json)。已经运行 b2ad47d 旧包的 A
直接返回原包，C 兼容处理，不要求仅为遥测变化重复现场操作。
本轮没有板卡动作、新采集、真实配对或实测 ASG；参考臂冲突交现场事实复核，不能先认定模型无效。

## 2026-10-24 房间门禁 ready v1

输入为 A db296988a444cf2f72852dec66f777edb7c103f6。
[原统计回包](../audio-replay/a-tail-review-return-3e2e923.zip) 的 SHA256
ebd3e49c89c1fea9878a566c3a3e04647411bc4ab681096274ebdb127dbb5b1d，原字节保留。
[独立统计](room-return-audit-20261024.json) 确认 summary_revision=3.1.0、521行：
214 invalid、297 unknown、10 protection；有效尾段/正向对照/配对均为0，麦克风满幅30行、退役位流38行。
交接文字中的部分旧原因计数不用于本轮统计；不存在需要A再次重跑的版本问题。
原PCM未随回包提供，以上是统计及字段复核，不能冒充新波形复算。

[参考臂原说明](../audio-replay/a-reference-arm-check.json) 已接收：旧cancel_zero 0 dB“稳”撤回，
音响状态与会话传递不同；满幅后限幅状态污染后续测量是新增协议的现场依据。
A报告中的增益差不在C处升级为已验收MSG/ASG。

### 现行包与模型来源

发布 `build/packages/c-room-ready-v1.zip`，唯一Notebook为 experiment.ipynb，
measurement_policy_version=c-room-policy-1.0.0、calculation_version=c-measurement-2.2.0、
summary_revision=3.2.0、schema_version=3。A replay_trial.py 原样2127663…，配对bit/hwh原样。
实际当前模型均取自 A report/verification/audio-replay/recal-2026-10-23/：
256 SHA256=5537483e4cc1abd6e8566a8f8bbd6ad8bf436bae14c37a920f1a6458e56db36a；
512 SHA256=98d0956813720f4a791db0fa510e2216897f3aba2dac35083668e47678430d17。
本场模型在ready包自有models注册表中登记，仍为待实验候选；全局B历史三模型及其原状态不覆盖。
包内a-scene.json保留A原场景字节，scene.json明确标出C根据A最新重标定记录生成的模型选择。
首次基线试次由A驱动补零装满512并检查fresh；不把generic补零证据冒充本模型的新板上验收。

### 三项现场教训的具体落实

1. 全保存窗口扫描麦克风满幅，不依赖PL guard。任一满幅禁止稳定/效果结论，
   保留mic事件并结束后续调用。削顶不单独认证反馈因果。
2. 每项闭环前固定1 kHz、峰值-20 dBFS定音直放，反馈增益0；初始两次通过后固定场次基线。
   相对基线漂移超过1.5 dB、信号落底噪、定音不成立或状态恢复失败，跳过目标并结束。
   下一门禁同时复核前一闭环，失败/缺失时前项也排除效果配对，不只影响下一项。
3. 满幅/保护后不自动重试；新批次必须在物理恢复后重新通过初始门禁。
   现有A驱动没有全过程ADC满幅遥测，C只检查保存窗口，不宣称新增在线麦克风保护。

数字模型比较每项2.1 s、源约1.87 s；源码冻结实际源数组及SHA256，
根据实际source_end+2442帧选择唯一尾区间，约0.18 s；同时保留完整捕获范围及有源段电平。
派生裁剪不改原NPZ，满幅检查使用全捕获，不因裁剪隐藏有源段满幅。
尾段低于登记噪声底+6 dB时只标不足，不叫“稳”；有源段没信号则测量无效。
固定-9/-6/-3/0 dB、每档两对256/512、顺序平衡；任何事件停止后续，未执行数保存。
外部讲话有RUN末尾和独立SPEECH入口，候选抵消/旁路同增益，仅作功能听感验收。
返回包含统计、恢复侧文件及准确模型JSON，不含捕获PCM。完整操作见
[现行操作单](../../../board/audio_closed/BATCH_GUIDE.md#现行房间门禁实验-ready-v1)。

### 验收层次与限制

- [124项软件回归](room-tests-20261024.txt)：门禁失败不启动目标、1.49/1.51 dB边界、
  满幅且guard=false、裁剪不能隐藏满幅、底噪尾段不足、事后门禁失败追溯排除、
  单次外部讲话入口、取消/故障保存，以及既有算术与汇总回归。
- [整包检查](room-package-check-20261024.json)：A原驱动8/8、所有冻结哈希、唯一Notebook代码格，
  实际执行取消路径而未导入PYNQ；完整38调用软件编排通过。
  编排软件夹具用零系数，明确software_fixture，真人声完成标志为false；ready中实际部署的是上述A非零模型。
- [B原消费工具检查](room-consumer-software-20261024.json)：新版汇总直接消费、0阻断；
  模型身份、配对和统计仅验证软件流程，真实有效配对0。

ready表示软件集成验收完成；本轮C没有板卡动作或新采集，没有实测ASG。
首次现场RUN/SPEECH及当前模型效果仍交A执行，不以软件回归代替。

### 群聊配置的一次检查

Tailscale 1.104.2 本机在线，按用户要求保存三项用户环境，并在新Python进程读取这些值。
执行一次 tools/ai-group/group.py check；因提供的C/A/main提交均无此文件而失败，
[完整输出](room-group-check-20261024.txt)。已停止该项，未重试check、未创建或修改群聊协议代码。
没有在仓库或代码包保存GROUP_TOKEN。
