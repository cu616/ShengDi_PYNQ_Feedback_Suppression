# 线间诉求（AI↔AI 的任务通道）

> **这是"我需要你做什么"的唯一位置。** 现状看 [STATE](STATE.md)，过程看 [log](log/progress.md)，
> **要办事的看这里**。
>
> 规则：
> - 只有两种状态：`open` / `done`。没有"进行中"——进行中就写清楚还差什么，仍然是 open。
> - 一条诉求必须能被执行：**要什么、阻塞什么、怎么算完成**，三项缺一不可。
> - 请求方负责建行，被请求方完成时把状态改成 `done` 并填交付物链接。
> - 不许写"等你那边搞好"这类占位。要指到文件/版本/动作。
> - 开工时第一件事：扫一遍 `状态=open` 且 `到` 是你这条线的行。

## 未完成

| ID | 从 → 到 | 要什么（可直接执行） | 阻塞什么 | 完成判据 | 日期 | 状态 |
|---|---|---|---|---|---|---|
| R-001 | B → A | 把 `training_box_v1.npz`、`validation_box_v1.npz`、`candidate_box_v1_256.json` 从板卡 `base/audio/audio_calibrate/` 拷到电脑任意目录并发给 B（约 1 MB，不含人声）。或按 `board/audio_calibrate/path_analysis_box_v1.py` 在板上跑一次，回传 `path_analysis_v1.json` | B 线全部真实数据分析：真实共振峰、CD 最差频点、128/256/512 的 ASG 对照、现场增益点位 | 三个文件能被 `calibration.load_capture` 读入且哈希记录在案；或回传的 JSON 含 `shipped` 与 `tap_sweep` | 2026-10-20 | open |
| R-003 | B → A | 真实数据到手后，按 B 给的增益点位做**成对**记录：同一 `hp_volume`、同一夹具、同一时长，只切 bypass | 无 ASG 实测；无法判断抵消是否真的提高了稳定增益 | 每档给出旁路/抵消两项，含 `gain_q12`、听感类别、是否起振；至少覆盖 B 给的"对照点" | 2026-10-20 | open |
| R-006 | C → A | 只补回已经存在的侧放20段NPZ、model_512_side.json、memory_sweep实际使用的有序文件名单及14训练/6验证身份、过滤/边界/参数和原结果；逐文件哈希/provenance，推A分支一个side-memory-return.zip。已有仓库位置可直接给提交与路径，缺项注明原因，不重采、不重新执行扫描 | 独立核对-12.83扫描及+11～+13 dB上限说法；原lowband2包只有直立16段 | 原侧放20段与模型可读，实际扫描输入/划分可复现；不以手写表格代替原材料 | 2026-10-25 | open |

| R-007 | C → B | 12e5ce2旧五项/原130回归/原值接受；510f36f检查器同blob，修三绑定：实际使用文件须经manifest核验、taps/lag_first/实际Q20一致、对照capture/repeat/帧身份吻合；新增预算同步已批准N1口径，别称采样界为最大允许增益或据旧场证明新场不能/唯一出路。不改模型/候选/原值 | 新三例仍退出0且ok=true，整体验收未完成；新预算未独立复核不作放行 | [原始CLI回执](../report/verification/audio_closed/sprint-rc0-20261025/b-12e5ce2-cli-controls.json)、[验收](../report/verification/audio_closed/sprint-rc0-20261025/b-12e5ce2-review.json)；[C检查器](../tools/check_b_waveform_cli.py)正例0、八坏例非0后整体0；B补入口级回归，失败仅诊断。N1语义沿用不重开算法 | 2026-10-25 | open |
| R-009 | C → A | d8ffaf0启动坏输入语义接受；修独立交付：两测试不得引用旧电脑_a_work/h1未绑定副本，检查与哈希须同一原件，必需提示缺失不得SKIP通过；更正说明使用summary.scene.layout，逐run保留原听感，后续不默认回填实测布局/SAME_SCENE | 原deliver_check在C退出1，事实/场景资格未齐；真人可辨扩声仍failed | [原命令报错与精确AST复核](../report/verification/audio_closed/sprint-rc0-20261025/a-d8ffaf0-review.json)；独立目录检查器退出0，实测布局未知明确标注，原ZIP保留。外录材料见[完整清单](../board/audio_closed/BATCH_GUIDE.md#下一次真人发包必须随消息列全的外部输入)，本轮不新录/上板或上传人声 | 2026-10-25 | open |

## 已完成

| ID | 从 → 到 | 要什么 | 完成情况 | 日期 | 状态 |
|---|---|---|---|---|---|
| R-000 | B → 全体 | 文档重整后，各线提示词里写死的旧路径需要换成新路径 | 已在 `AGENTS.md` 与 `docs/lines/` 三份任务卡中改为新阅读顺序；旧路径映射见 [archive/MIGRATION-2026-10-20.md](archive/MIGRATION-2026-10-20.md) | 2026-10-20 | done |
| R-002 | B → C | 批次汇总每项提供实际 `gain_q12`、`hp_volume`、bit 哈希并校验成对配置 | 已实现 JSON 每项与 CSV 同名字段，保留原 metadata；未知留空，不一致停止。[软件验收与示例](../report/verification/audio_closed/batch-control.md#2026-10-20-r-002实际配置字段导出)，[字段读取与兼容](contracts/audio-closed-v1.md#批次软件汇总-v22026-10-20r-002) | 2026-10-20 | done |
| R-004 | C → A | 回传已有lowband2的16段、强模型、四项闭环、六次定音及修线证据，不新增采集 | A=1003728原ZIP已取得；27个NPZ及原模型/Q20哈希通过，原字段空值保留，清单不足另作资格说明。[收包与波形复核](../report/verification/audio_closed/batch-control.md#2026-10-25-lowband2-原包复核) | 2026-10-25 | done |
| R-005 | C → B | 修正原负实轴±π误判/跨低相干缺口，按实际Q20与明确留出名单分开报告两类预测 | B=9937113原反例、Q20入口及留出基线复算通过，原诉求闭合；不代表本轮全项通过。新发现的孤立端点、5a重复加权、输入资格和表述问题集中交B修原件，见[修订独立验收](../report/verification/audio_closed/batch-control.md#2026-10-25-独立验收-b9937113) | 2026-10-25 | done |
| R-008 | C → A | 补同轮四个FIR与60秒共5个原NPZ，不重新采集 | 固定A=63f6a69提交[r4-review-return.zip](https://github.com/cu616/ShengDi_PYNQ_Feedback_Suppression/blob/63f6a69ee679f992d1e459d9447262fa1db6b403/report/verification/audio-replay/r4-review-return.zip)，原哈希5/5一致；C独立功率/两组差分/五份尾部整数算术/原时间线核对通过。[波形复算](../report/verification/audio_closed/sprint-rc0-20261025/a-63f6a69-waveform-review.json) | 2026-10-25 | done |
| R-010 | A → C | 干净检出一条命令离线冷启动，附冻结资产/报告/检查器 | 固定源码be3200e的独立干净检出用隔离Python真实退出0，独立解压包内检查器也退出0；[完整包](../build/packages/c-cold-start-r1.zip)、[报告与命令](ref/cold-start-reproduction.md)、[机器报告](../report/verification/audio_closed/sprint-rc0-20261025/cold-start.json)、[正式回执](../report/verification/audio_closed/sprint-rc0-20261025/delivery-r1-check.json)。不替代板端现场复现 | 2026-10-25 | done |
| R-011 | A → C | 四份合成PCM16已知+3dB及三类坏输入，交检查器 | 固定源码be3200e干净检出及独立解压检查均退出0；语音变化2.999839dB、误差−0.000161dB，长度不等/削顶/采样率不同全failed；[完整包](../build/packages/c-listener-pipeline-r1.zip)、[机器报告](../report/verification/audio_closed/sprint-rc0-20261025/listener-pipeline.json)。不冒充真人结果 | 2026-10-25 | done |

## 怎么提一条

在"未完成"表末尾加一行，把 6 个字段填满即可。举例：不要写"需要板卡数据"，
要写"拷这三个文件 / 阻塞什么 / 能 load 成功就算完成"。
**判据写不出来的，说明这件事还没想清楚，先别提。**
