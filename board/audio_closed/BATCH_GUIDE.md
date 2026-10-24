# C 测评与房间实验操作单

## 2026-10-25 原包复核后的安排

A=1003728的lowband2-return已接收，无需重发原包或重跑原试次。
本轮c-lowband-audit-v1.zip仅为C离线数字复核，见[完整证据](../../report/verification/audio_closed/batch-control.md#2026-10-25-lowband2-原包复核)。
没有新发声包、没有+10 dB验收指令；不据旧相位阈值升增益。
只需A补现有侧放20段/模型/实际14+6名单（R-006），B修相位检测后复算（R-005）。
近讲作为新夹具提案交队长判断，尚未下发物理变更或重采；现有模型不能改标签沿用到新夹具。

## 2026-10-24 回包后的执行安排

已接收 A=08965d2。下方 ready v1 已执行并回包，本轮不再运行它，也不再重采原增益批次。
C 的派生复核与 B 消费结果见 [回包复核证据](../../report/verification/audio_closed/batch-control.md#2026-10-24-ready-回包复核与门禁-v11)。
本轮交付 `build/packages/c-room-review-v2.zip` 为离线结果，不能用于发声。

新源码采用运行漂移限5 dB，并记录 mic/ref、极差和总体标准差；匹配效果仍另查四次前后门禁
mic/ref极差1.5 dB，不通过时保留记录但排除效果配对。不降低信号高于底噪6 dB的通路要求。
听感输入改为 H1人工回听或P1数值代理，P1不能通过讲话验收。完整组与未完成组分别导出，
没有删除任何失败行。字段定义见 [房间协议v1.1](../../docs/contracts/audio-closed-v1.md#房间执行协议-v112026-10-24a-08965d2-反馈)。

A 下一步只打包现有 `/home/xilinx/lowband2` 数据、强模型和原关联日志，无需新增采集；
按 [R-004](../../docs/REQUESTS.md) 的字段写 manifest，以原相对路径和SHA256绑定，推A分支后交回。
其中需有已存在的零源闭环四项、六次定音及修线后场景/底噪的证据；缺失保持null并记原因。
B/C复核后才冻结采用强模型的下一发声包。+6 dB先作设计目标，现有分频带预测不代替全频段或人声验收。

## 现行：房间门禁实验 ready v1

使用 `build/packages/c-room-ready-v1.zip`（c-room-experiment-1.0.0）。A=db29698，
驱动 SHA256=2127663…，bit=8b2426f4…、hwh=3873b16b…，与现行 audio_live 同源。
当前夹具 room_v1_20261021：0.5 m、MAX4466/LINE_IN、惠普 NS1 Pro/HP+MIC、音响1只、Codec40。
模型为 A 本场重标定的256基线（5537483e…）与512候选（98d09568…）；原B模型仅作历史分析。
256由A原驱动补零装满512，记录逻辑/实际抽头和哈希，不称为新训练512。
`a-scene.json` 保留A原文，`scene.json` 为C结合A最新重标定证据生成的集成记录。

1. A 将整个 ZIP 上传板卡并解压到全新目录
   `/home/xilinx/jupyter_notebooks/base/audio/c-room-ready-v1`，整套文件一起部署。
   关闭其他占用音频的 Notebook，在 STATE 记录板卡占用；手机和外部播放器静音。
   人员全程值守，手能立即切断音响电源。不要戴耳机。
2. 打开包内 `experiment.ipynb`，重启内核，仅执行从上到下唯一代码格。
   首行 `# C current-room gated experiment entry`。程序先检查所有冻结文件及模型哈希。
3. 输入 `RUN` 执行固定模型比较；输入 `SPEECH` 只做人声功能验收；其他输入结束并保存结果。
   此确认同时授权后续每次1.02秒的固定定音门禁直放。闭环每项仍先装载并静音，
   提示 `START` 才开始；外部讲话也只在其START后讲话。
4. 初始两次合格门禁建立固定场次基线，每个后续闭环/讲话前重测同一1 kHz、峰值-20 dBFS定音。
   麦克风须高于登记底噪6 dB、确有定音、无满幅；与固定基线偏差超过1.5 dB则跳过目标并结束本批。
   不在失败后重新定义基线。正常结束后输入听感：1清楚/可接受，0无声，2失真，3尖叫，4未静，q停止。
   下一门禁同时复核前一闭环；事后门禁失败或缺失时，前一项也标为测量无效。
5. 最后只返回 `RETURN_ONE_FILE` 指向的 `results/room-<id>/return-results.zip`。
   包含 summary JSON/CSV、逐项恢复状态及本场模型字节；原始NPZ留在板卡，不装入返回包。
   失败项、未执行数和停止原因也保存；不手工筛选成功项。

RUN：-9/-6/-3/0 dB，每档两对256/512，先候选再基线、第二对反序。
每项2.1秒，固定约1.87秒白噪声（RMS -24 dBFS）；尾环形同时覆盖有源段和源结束+50 ms后的尾段。
尾段用实际源结束帧计算并单独标区间；落入底噪只记不足，不算稳定。当前场次模型是否改善是本批的决策目标。
全部通过后做人声：候选抵消/旁路同为-9 dB，各3秒；只作可听扩声功能验收。
完整RUN最多38次限时调用、主动发声约60秒；SPEECH模式最多6次、约10.08秒。
装载/读回/恢复和人工确认会增加墙钟时间，任何保护、满幅、故障、恢复失败或门禁失败立即结束后续项目。

麦克风满幅与PL guard分别记录。现有硬件只保存末尾16384帧，麦克风满幅检测覆盖该窗口，
没有全过程ADC在线保护；不要把guard未触发当作整次无削顶。发生满幅后本批结束，
音响恢复后仅能通过新批次的初始门禁重新开始，没有自动重试或自动续播。
结果不生成实测MSG/ASG，软件 ready 表示集成验收通过，首次现场执行仍由A完成。

已有521条房间记录的静默回包已收到，不需要为了本包再运行旧记录复算。

维护者 C。适用 `c-experiment-2.x`；先看 `experiment-manifest.json` 的 status。
`offline_only` 只用于静默复核，不能用于发声。该门禁由代码强制执行，不能改字段绕过。

C 分支交付位置：`build/packages/c-integration-source.zip`（完整源码）和
`build/packages/c-experiment-v2-offline.zip`（已冻结的离线实验候选包）。
A/B 可直接从 GitHub C 分支取得，无需用户另传本地 ZIP。
仓库 C 集成版本的回归输出见 `report/verification/audio_closed/c-branch-integration-tests.txt`。

## 本轮优先：已有房间 NPZ 的静默复算（summary v3）

包版本为 c-tail-review-3.1.0，summary_revision=3.1.0；schema_version=3 与数值判据不变。
新增正向对照 true/false/null、独立的尾段/保护/通路原因、历史位流登记及抽头推导来源。
退役 audio_closed 记录仅保留 PL 算术证据，不进入声学配对；推导抽头数不冒充硬件回读。
若已经用 b2ad47d 的 3.0 包执行过，直接返回原结果，C 负责兼容复核，无需仅为这些字段再跑一遍。

目的：先复用旧记录，按 B 的要求导出实际配置和同增益基线/候选；不发声、不加载位流、不写 Codec/MMIO，不需要新增采集。
材料来自 GitHub C 分支：`build/packages/c-tail-review-v3.zip`；三个原模型来自 B ffa035a，
模型清单及补零派生物同步 B 59ab1ee。包内只注册三个原模型，不把派生物重复当候选。

1. A 取得 C 指定提交的 ZIP，在板卡解压到新的完整目录：
   `/home/xilinx/jupyter_notebooks/base/audio/c-tail-review-v3`。
   上传整个 ZIP 后，可在 Jupyter Terminal 使用一次完整解压命令：
   `python3 -m zipfile -e /home/xilinx/jupyter_notebooks/c-tail-review-v3.zip /home/xilinx/jupyter_notebooks/base/audio/c-tail-review-v3`。
   包内应有 tail-review.ipynb、summarize_tail_batch.py、evaluation.py、tail_metrics.py、model_comparison.py、
   growth_monitor.py、closed_tools.py、replay_tools.py、residual_tools.py、models/、review-manifest.json、OPERATIONS.md。
2. A 的 AI 先核对已有房间闭环 NPZ 的实际存放目录。只用本项目获准的记录，不扫描无关私人目录。
   A 的 AI 如能从原始日志、ABI 和正向对照记录确认旧数据缺失的源结束/外部源关闭/配对身份，
   可一次生成独立 evidence.json；以每个 NPZ 相对路径和 SHA256 绑定，含 provenance 证据来源。
   不让用户逐条猜字段。不能确认就不补，不以“总时长=源长+1秒”代替实际捕获证据。
   不允许补充材料覆盖 gain_q12、hp_volume、bit/系数/模型哈希或任何原始非空矛盾字段。
3. 打开 tail-review.ipynb，重启内核，只执行从上到下第 1 个代码格。
   标题“C 已有记录静默复算”，首行 `# C existing NPZ review: silent, read only`。
   Shift+Enter 后应看到 SILENT_PACKAGE_OK；之后只输入现有 NPZ 根目录完整路径，
   再输入 A 核实的 evidence.json 路径（没有则直接回车）。不用编辑代码，不需要 READY/START，不需讲话或播放。
4. 程序一次扫描并处理全部 NPZ，保留失败项，预期输出 SILENT_REVIEW_COMPLETE 和 RETURN_ONE_FILE。
   最终只返回：
   `/home/xilinx/jupyter_notebooks/base/audio/c-tail-review-v3/results/review-<id>/return-results.zip`。
   包含 summary.json 与 summary.csv；原始 NPZ 留在原目录，不修改、不装入返回 ZIP。
5. 任一版本/模型哈希不符时停止，不绕过校验。旧数据窗不合格时正常输出空统计和原因，
   这是安全记录而非效果通过。如果有效配对为 0，仍返回同一个 ZIP，C 再确定最小缺口；不自行开始新采集。

所有行直接有 gain_q12、hp_volume、bit_sha256、coefficients_sha256 及尾段三组值；
三组值为 tail_rms_dbfs、tail_slope_db_per_s、tail_residual_over_mic_db（含三个指定子带）。
CSV 另有 tail_residual_over_mic_db_300_1000、_1000_3000、_8200_8600。
保护、预测/残差/增益/mix 饱和、mic 满幅、静音动作和波形全零各自列出；未知保持空值。
positive_control_valid 单列导出，失败、未知与尾段不足分别列原因；不能把通路无效判断为模型无效。
comparison_id/session_id 等身份必须有依据；不能只因为请求 dB 一样就拼一对。
同一 comparison_id 中实际 gain_q12 不相等，两行保留原值、标 invalid，不参与比较。
256 补零的保存系数仍识别为 baseline，不能成为 candidate；不截断任何模型。

补充材料格式（由 A 的 AI 依据已有证据生成，不让用户手填）：
顶层 captures，以相对 NPZ 路径为键；每项含 input_sha256、provenance、metadata。
metadata 只可补 source_end_frame_exclusive、source_schedule_verified、transition_frames、
external_source_off_verified、external_source_active、positive_control_valid、scene_sha256、session_id、
comparison_id、repeat_id、mute_applied、mute_during_observation 和相关来源说明。
“计划含1秒尾段”以及早停前的源播放数据，都不能授权填 source_schedule_verified=true。
尾段数值只是该段的描述统计；源注入位置、噪声与非线性未排除时不能称为 CD，更不计算 ASG。

软件示例在 `report/verification/audio_closed/b-request-software-summary-v3.json`，
明确 evidence_kind=software_fixture、gain_q12=0；只验字段、算法和配对，不算现场完成或候选改善。

## 1. 电脑文件和版本

电脑工作根：`D:\Flushbonading_Contest\shengdi-c-main-20261023`。
初次交付包：`D:\Flushbonading_Contest\c-delivery-20261023\c-experiment-v2-offline-final.zip`。
源码与离线复算的完整目录在上述工作根；旧 C 分支目录保留。
以 `experiment-manifest.json` 逐文件 SHA256 为准，Notebook 仅校验代码格内容，保存输出不会误报。

main 固定为 03f3063，A 板端资产来自 59aa10e；C 没有修改 A 的 Codec/MMIO、驱动或 RTL。
模型不在 Git，且 A 原驱动存在已复现的证据保存缺陷；初次包标为 offline_only。
A 修复的 driver 与现有兼容模型收到后，C 运行集成工具生成一个新的 ready 包；不用等待新模型研究。
集成动作由 C 完成，不由现场用户拼文件：
`D:/Anaconda/python.exe scripts/assemble_experiment.py --assets <A返回的资产目录> --output D:/Flushbonading_Contest/c-delivery-20261023/c-experiment-v2-ready`。
资产目录须含 replay_trial.py、replay_tools.py、closed_tools.py、residual_tools.py、audio_replay.bit/hwh、model.json、scene.json。
scene.json 须有 fixture_id=box_v1_20261016、hp_volume=40、operator_verified=true、calibration_match_original=true、approved_model_sha256 及实际接线/箱盖/位置/音量说明。
assemble 会重跑 A 驱动的八项模拟验收、验证模型与 512 位流兼容、锁定所有哈希；任一失败不生成可用 manifest。

## 2. 一次部署完整目录

目的：避免新旧 Python 模块混用。ready 包才执行本步。
A 将整个 ready ZIP 上传到板卡 Jupyter 根 `/home/xilinx/jupyter_notebooks`，解压到全新目录：
`/home/xilinx/jupyter_notebooks/base/audio/c-experiment-v2-ready`。
不用覆盖旧 audio_replay 或 audio_closed；旧结果与旧 Notebook 原样保留。
包内根目录必须同时有 experiment.ipynb、experiment.py、evaluation.py、growth_monitor.py、replay_trial.py、
replay_tools.py、closed_tools.py、residual_tools.py、audio_replay.bit、audio_replay.hwh、model.json、scene.json、
a-acceptance.json、experiment-manifest.json、OPERATIONS.md。
可在 Jupyter Terminal 执行唯一的部署命令（ZIP 位于 Jupyter 根时）：
`python3 -m zipfile -e /home/xilinx/jupyter_notebooks/c-experiment-v2-ready.zip /home/xilinx/jupyter_notebooks/base/audio/c-experiment-v2-ready`。
预期：目录完整，无需手抄任何 Python 代码。电脑原始包为恢复副本。

## 3. 现场准备

目的：固定公平对照条件、排除音响待机。接线、关盖、两只音响、麦克风与音量必须与 scene.json 一致。
只允许 A 操板。关闭其他加载 overlay 的 Notebook 会话；在 STATE 记录占用。
手机停止外放；数字试次中人员安静，不戴耳机，手能立即切断音响电源。
原始采样只保存在板卡；返回包默认不含 PCM。
正向对照使用同一数字突发、g=0；麦克风 RMS 要在 −45 到 −3 dBFS、相关系数至少 0.1；
一对前后电平差最多 6 dB、延迟差最多 1 帧。该宽限仅用于发现断路/待机/配置变化，不代表校准精度。

## 4. 只执行一个 Notebook 代码格

打开 ready 目录的 `experiment.ipynb`，重启内核。
从上到下只有 **第 1 个代码格**，标题是上方的“C 固定批次”，代码首行为 `# C fixed experiment entry`。
选中该格按 Shift+Enter；不要按 In [数字] 找位置。
目的：自动核验、集中执行、自动汇总。预期：固定计划说明及 READY 提示。
若看到 PACKAGE_INCOMPLETE、版本/模型/现场不匹配，停止；下载已生成的结果包，不录音、不讲话、不加载新 overlay。

READY 表示 A 确认现场和本地保存。每一项由驱动先装载并保持静音，显示配置完成后才提示 START。
START 后立即发声/采样。其他输入取消当前项并结束整批。
每项结束后听感输入：1 可接受且已静音；0 无声；2 失真；3 增长尖叫；4 未静；q 停止。
除 1 外都结束整批，后续项目标为未执行。输入框只在静音期间出现，不是发声中的停止按钮。

## 5. 预定项目、时长和决策

只变 bypass，模型、数字源、实际 Q12 增益、音量、夹具、帧预算固定。
数字源为固定种子、1 秒宽带突发，峰值上限 −42 dBFS，首尾淡变；不能将它视为普通人声。
档位 −26 / −24 dB，每档 2 对。第一对先抵消再旁路，第二对先旁路再抵消。
每对顺序：直放对照 1.02 秒 → 两项闭环各 1.4 秒 → 直放对照 1.02 秒。
四对最多 16 项、19.36 秒。若全部有合格窗口，才做外部讲话抵消/旁路各 2 秒（−26 dB），共最多 18 项、23.36 秒。
配置、装载、读缓存与静音输入会增加墙钟时间；23.36 秒只是程序主动发声/采样总时限，并非现场总耗时。
外部讲话项目只有 START 后才以普通音量讲话，至程序提示结束；手机继续静音。
讲话记录用于“麦克风扩声可用”功能验收，不使用数字源结束时刻判断它的纯尾段。

问题与分支：
- 正向对照失败/漂移：停止，A 查待机、接线和位置；该对不能用于负面效果结论。
- 算术、版本、实值或配对不符：停止，C 查数据与集成，A 查底层。
- 保护、削顶/饱和、已观察到增长、执行/恢复失败或异常听感：停止后续播放，不自动重试。
- 窗口证据不足：保存该对、停止升档，C 复算后给出下一次有区分度的观测方案。
- 合格窗口未观察到增长：按已冻结顺序继续；只解释该窗口，不称全程稳定。
- 讲话无声/不清楚：功能验收失败，不能将数字源对照冒充正常扩声通过。
阈值未被夹住，不算 MSG/ASG。当前计划只判断固定工作点，四对也不构成精确阈值试验。

## 6. 异常、保存和恢复

发声中异常或持续强叫：A 立即切断音响电源；不要等待 Python 输入。
每项声音上限由 A 位流帧预算执行；增长判据在落盘后运行，没有新增在线声学停止器。
底层先 PL/Codec 静音并冻结，再保存四路 PCM、源、原始计数与实际帧数，最后恢复 stock base/PLL 并再次静音。
C 收集驱动的 capture.status.json；recovery_ok 不为 true 时禁止后续试验。
C 在每个状态变化保存 summary.json；finally 保存 JSON/CSV 和 return-results.zip。
若磁盘满，屏幕显示 RESULT_SAVE_FAILED 与完整结果目录，立即停机并保留目录；不得删除失败后重跑掩盖它。
恢复：保留旧目录/旧包与失败文件，切断音响后让 A 恢复 stock base 并确认静音；修复后新建 run_id。
不从中断项自动续播；只收集已落盘的数据不产生声音。

## 7. 一次返回

正常、取消或失败均只需返回屏幕 `RETURN_ONE_FILE` 后的完整路径：
`/home/xilinx/jupyter_notebooks/base/audio/c-experiment-v2-ready/results/run-<id>/return-results.zip`。
包内含全部已执行/失败项的 metadata、事件、判据版本、配置、覆盖、原始 NPZ 哈希与路径、恢复结果和 CSV。
原始 NPZ 留在同一板卡目录。没有逐格贴输出的步骤。
若内核被强制杀死导致 finally 未运行：不要重播；重开内核后在同目录 Terminal 执行
`python3 -c "from pathlib import Path; import json,experiment; [experiment.collect(p.parent,json.loads(p.read_text())) for p in Path('results').glob('run-*/summary.json')]"`。
它仅整理已有汇总，不操作板卡。驱动已落盘但尚未进入汇总的 NPZ 会在 raw_files 中列出，供 C 后续静默分析。
返回结果后由 C 核对/复算再交 B，不要求 A 临时判断斜率或计算指标。

## 2026-10-25 集中实验 RC0

维护者 C；本节就是包内 OPERATIONS.md。仅适用 `c-sprint-rc0-1.0.0`，不要执行上方历史包。
决策：先用已有 strong 基线回答真实拾音/听众效果是否成立、同配置 FIR 开关是否有观察窗证据。
自变量分别为系统开关和 FIR bypass，均衡固定 identity；不测新增益阶梯，不自动越过保护。
截止按队长固定提交 bb56ef1 的计划：10/26 集中实验与质检、10/27 20:00 功能冻结、10/28 独立复现和封包。

### 唯一入口与固定身份

- C 电脑完整 ZIP：`D:\Flushbonading_Contest\ShengDi_PYNQ_Feedback_Suppression\build\packages\c-sprint-rc0.zip`。
- 板卡解压目录：`/home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc0/`。用新目录，保留现役基线供恢复。
- Notebook 完整路径：`/home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc0/sprint.ipynb`。
  重启内核；从上往下**第 1 个代码格**，标题/首行 `# C sprint RC0: fixed baseline, single entry`，
  下一行为 `from sprint_experiment import run_sprint`。全包只有一个代码格，不以 In[n] 定位。
- 使用 A=bb56ef13300dbfecb6bbd525528a0dcf47ebd7e6 的原驱动/bit/hwh，
  strong 模型 c8be7f78e7ccb73c8b023aa9e74ddaa0914bc4dabf1e2de91ce46114a0679f9a；
  Q20 c9d3b1e658fd2ed8b731904eaa1f2bec62677b732f5bebe1acf34f1d96fa2160。
  完整文件与源码身份以 `sprint-manifest.json` 为准。版本/文件/系数不符则停止。
- 参数已冻结：48828.125 Hz、512 taps、lag_first=1、Codec40、Q12=4096（0 dB）、EQ identity。
  0 dB 仅来自同场历史短运行，不是保证安全或正常扩声的认证；不执行 +3 dB 重试。
  模型/现场几何不符就停止交 B，不自行把同一模型挪到新场景。

### 编号现场操作单

1. **准备与静默核验**：A 核实单人占板，把 ZIP 全量解压到上述新目录；运行唯一代码格。
   预期 `PACKAGE_OK; 60s_CONTINUOUS_NOT_AVAILABLE`。此时尚未导入板卡驱动、尚未发声。
   缺文件/哈希错误直接生成停止结果。Python 依赖仅标准库、NumPy、板端既有 PYNQ；不现场安装新库。
2. **一次冻结场景**：固定麦克风、音响、前放和 Codec，与 strong 标定一致；音箱可立即断电，不戴耳机。
   在提示内输入 READY、SAME_SCENE，并一次写清声源到麦距离、设备位置、听众/测量位置、固定源及音量、
   测量增益/AGC 状态。外部声源先停播。不能核实就取消，不能用沉默代表同意。
3. **先真实人声**：路径门禁后，程序完成配置并静音才提示 START。现场此时靠近现有麦克风讲话；
   不移动麦克风或音响。8 秒限时结束后填 CLEAR / DISTORTED / NO_AMPLIFICATION / HOWL / UNKNOWN。
   CLEAR 只表示 A 的现场人声/听感记录；不自动证明全程无失稳。没有真实拾音不填 CLEAR。
4. **固定听众开/关比较**：同一段固定录制人声由同一外部设备、同音量在固定源位置播放，经 MAX4466 拾音。
   关/开各 8 秒，听众与录音设备位置和测量增益不变，AGC 关闭。系统关使用前向开路且数字源全零。
   可选测量 WAV 固定保存到本轮打印的 `.../results/sprint-<id>/listener/` 下，文件名依次为
   `off-speech.wav`、`off-noise.wav`、`on-speech.wav`、`on-noise.wav`；单声道未压缩 PCM16、
   同采样率、人声两份同长度、各至少 1 秒，无削顶；噪声段在对应系统状态/测量增益下采集。
   可在每个 8 秒状态内录前 6 秒固定人声、后 2 秒停源背景，再分别导出；不要把两种系统状态混在同一测量文件。
   手工录制设备需提前就绪，在提示输入前拷入这四个固定文件即可，不需拼代码。
   不具备固定测量条件直接回车，标未测；音色/噪声/失真由听感字段分别保留，不用总 RMS 冒充语音改善。
   程序扣除背景功率并要求人声相对背景至少 6 dB，条件不足不算语音增益。未校准不输出绝对 SPL。
5. **FIR 对照**：关闭外部源，保持位置和模拟配置；固定数字 burst，FIR 开/关两组配对，顺序 OFF/ON、ON/OFF。
   每项 2.5 秒，前置同一门禁。配对实际 Q12/bit/模型/Q20/源/EQ/场景一致，只有 bypass 改变。
   沿用运行漂移 5 dB、配对 mic/ref 漂移 1.5 dB，不放宽它们来跑完整批。
   有效结果限保存的源后窗口；全程无饱和不推出全程无失稳。未测到有效边界不生成 MSG/ASG。
6. **连续运行与 EQ**：原驱动最多 10 秒，live_pa 也有窗口停顿。RC0 自动把连续 60 秒列为未测，
   不调用 live_pa 拼段、不修改限时。EQ identity，贡献未测；有 B 候选后由 C 核对配置并重发完整包，
   FIR 对照须在同一 EQ 下，EQ 收益另作开/关对照。
7. **停止与恢复**：输入非 START 取消；听到持续尖叫、严重失真或异常发热立即切断音响电源并中断代码。
   程序在保护、削顶、执行/落盘/恢复失败、无效配置或 FIR 观测不足时结束本轮，保留所有已执行项。
   原 A 驱动负责静音、恢复 stock base/PLL，状态文件确认 recovery_ok。恢复未知/失败时保持音箱断电，
   不发下一项；由 A 按已核实基线处理，不把恢复 stock overlay 当重新标定或效果通过。
   STOP/通信中断/落盘失败的软件分支通过不等于紧急静音实物已验收。
8. **一次回包**：最终屏幕 `RETURN_PACKAGE` 给出唯一结果 ZIP：
   `/home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc0/results/sprint-<id>/return-results.zip`。
   包含所有已执行/失败记录、原始 NPZ 哈希、本地路径、汇总 CSV、覆盖和恢复结果；人声 NPZ/WAV 留板，
   B 可直接读 `summary-v3.json` / `summary-v3.csv`（原 schema3）；FIR 开关配对在 `fir_switch_pairs`，
   不冒充不同模型的 baseline/candidate 配对。包中 `models/manifest.json` 绑定当前 strong 基线。
   不自动上传。A 只返回此 ZIP。若内核被强杀或断电，用同一代码格的恢复说明：在该目录 Terminal 执行
   `python3 -c "from pathlib import Path; import json; from sprint_experiment import collect; [collect(p.parent,json.loads(p.read_text())) for p in Path('results').glob('sprint-*/summary.json')]"`。
   此命令只读既有汇总并封包，不连接硬件；未进汇总的文件需保留并交 C 静默质检，不重播。

完整基线顺利执行共 13 项：6 次门禁、3 次真实/听众项、4 次 FIR；发声/观察约 40.12 秒，
外加配置、人工 START、听感填写和可选测量文件转存时间。听众噪声录音可延长现场时间。
任何停止都会缩短批次，不要求为了凑齐项目继续。每项在静音配置完成后才要求讲话/启动外部源。

### A minimal observation and continuous-run request

以下是交 A 的**待实现能力与验收要求**，不是已批准/已部署寄存器契约；C 不修改底层。
基线文件为 A=bb56ef1 的 `board/audio_replay/replay_trial.py`、`live_pa.py`、`closed_tools.py` 和对应 RTL。
最小建议：由 A 提供 `run_continuous(output_dir, fixture_id, model_path, bypass, gain_q12, hp_volume,
seconds=60, before_start=..., stop_request=...)` 或说明实际等价入口；配置与静音完成后再调用 before_start。

| 必需证据 | 字段/行为要求 | 可控验收 |
|---|---|---|
| 连续主路 | run_id、帧域/epoch、实际首末帧、开始/停止单调时刻、overlay 加载/重装次数、静音/断音区间、停止原因 | 单次实际覆盖至少 60 秒；期间无重新 arm/加载/Codec 静音拼段；正常停止与现场中断都可静音 |
| 全程事件 | event_sequence、event_kind、frame 或轮询上下界、原始状态/clip words、保护类型、计数覆盖首末帧、饱和计数标志 | 在首/中/末注入保护/计数变化，全部留证；轮询只能定位区间时不填假精确首发帧 |
| 缺失与覆盖 | 每块 first_frame/end_frame_exclusive、sequence、dropped_frames/blocks、unknown intervals、计数与 PCM 分别覆盖 | 缺块/回卷/重复/乱序/通信中断被识别，不把缺失填零；中间缺失仍保留有效局部证据 |
| 失稳观测 | 优先保存完整单声道 microphone signed24-in-int32（60秒约12MB），末尾四路继续供算术核对；或提供经C验收的连续FFT特征及参数/覆盖 | 不阻塞音频；丢日志计数；稳定纯音、尖峰、削顶不自动叫啸；增长发生在中段仍可离线检出 |
| 配置绑定 | source/code/bit/hwh/model/loaded_Q20/EQ 哈希、实际 g/Codec/bypass/源调度、场景/会话、采样率 | 同配置配对，故意改一个字段必须拒绝；FIR/EQ贡献可分别归因 |
| 失败留证 | 中断/保护先静音冻结，尽力保存；NPZ失败也有独立状态 sidecar，recovery_ok/cleanup_errors/save_error | 正常、取消、保护、执行异常、通讯异常、落盘失败、恢复失败全部可回包；恢复失败不继续 |

若全 PCM 暂不可用，A 可先交连续主路与全程事件；C 将波形未覆盖区间保持 unknown。
延长 watchdog 或改 ABI 由 A 提最小兼容变更表与回退，按现行流程审批，不由 C 绕过。

### C 收包与冻结

10/26 C 对 ZIP/身份/实际配置/覆盖/保护/恢复和配对进行质检，一次给出有效性与 RC1 必修项。
10/27 20:00 固定功能、入口与评价口径。10/28 由另一位队友（具备现场操板资格时由 A 安排）
冷启动按本操作单复现，保存执行人/时间/环境/原包哈希/结果 ZIP；不把 C 自测算独立复现。
发布包冻结源码提交、源码归档、bit/hwh、模型、Q20、配置/EQ/源、依赖版本、构建和实测证据及逐文件哈希。
通过、未通过、未测分别列出；人声、60秒与停止恢复仍有必修项时，整体不得写“验收通过”。
