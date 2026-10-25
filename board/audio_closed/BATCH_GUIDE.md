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

维护者C；本节原样进入OPERATIONS.md。当前包 **RC0.1-human-r1 / c-sprint-rc01-1.0.5**，只做真人和固定听众比较。
A=d013930已补交r4原回包，C配置/配对差分/寄存器时间线审核通过；5个非人声原NPZ尚待独立波形复算。
本包不复制历史通过标记，不重复FIR对照或60秒工程项，最新结论以STATE为准。
目的：确认当前工作点是否有真人可辨扩声，以及固定听众位置系统开/关的实际变化；负面结果同样有效，不能靠降增益过关。

### 唯一入口与身份

- C电脑完整ZIP：`D:\Flushbonading_Contest\ShengDi_PYNQ_Feedback_Suppression\build\packages\c-sprint-rc01-human-r1.zip`。
- 板卡全量解压到：`/home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc01-human-r1/`，使用新目录，保留r4原件。
- Notebook绝对路径：`/home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc01-human-r1/sprint.ipynb`。
  重启内核，只运行从上往下**第1个代码格**（全包唯一），首行：
  `# C sprint RC0.1-human-r1: live speech and listener only, -14 dB, v2`。
  不用In[n]定位，不拷代码、不现场换单件。
  A在d013930新增的run_rc4_human.sh把5秒讲话倒计时放在START回调返回前，期间Codec仍静音；
  本次直接使用上述Notebook交互，按START开始后讲话，避免预先讲完。其旧15项包装入口不用于这5项会话。
- 绑定A=`85f4967f242eed61eaa6b74041be931c2f5bc7a0`，五件Python来自根目录，bit/hwh来自其v2目录，逐字节核验。
  bit SHA256=`61bb71aabb824c57191edcea93d1333143cd959c16d43028585913c54a8f61fa`；
  hwh SHA256=`92b499a39d04de891632a89512bfff49f7482a332344128556b1506529d1b75b`；MAX_RUN_FRAMES=3000000。
  A的942fd5b修复在包内，C未改A驱动或RTL。本包虽然带完整v2资产，**不调用连续运行**。
- 默认calibrated_20261024（原strong），512 taps、lag_first=1、Q20；
  文件SHA256=`c8be7f78e7ccb73c8b023aa9e74ddaa0914bc4dabf1e2de91ce46114a0679f9a`；
  Q20 SHA256=`c9d3b1e658fd2ed8b731904eaa1f2bec62677b732f5bebe1acf34f1d96fa2160`。
  固定48828.125Hz、Codec40、−14dB/Q12=817、EQ identity。路径门禁和系统关是gain=0开路，其他项FIR开启。
  candidate_512不作默认或后备；场景变化交B重标定，不在新场景套用旧系数。
- A先读preflight.all_ok并核对版本；缺失/false/版本不符回PREFLIGHT_FAIL，资产不符回ASSET_MISMATCH。
  均不上板、不改包。机器可读预检自动生成；唯一代码格在导入PYNQ前再次核对载荷、模型、资产及预检哈希。

### 发送方自检

`SELFTEST ok | trials=5 | window_frames min=14920 | gate=passed | 预计板端 0.434分钟（另加配置和人工等待）`

可选在解压目录执行`python3 sprint_selftest.py`，静默使用真实Q20及A原件纯参数前缀，不导入PYNQ、不覆盖preflight。
软件夹具的HUMAN/CLEAR确认是合成分支控制，preflight明确标synthetic_human_confirmation，不能算真人或硬件验收。
模型taps/lag_first/Q20和−12/−6/0三点ref/mic映射都在preflight中；旧等源/预算及1帧余量拒绝控制保留。
本包门禁运行1.02秒、定音1秒，源内14920帧；人声/听众每项8秒、1帧静音数字源，保存末尾16384帧。
全程波形未覆盖的区间仍未知，不能把8秒人耳报告和0.336秒PCM混成全程波形证据。

### 一次真人现场会话

1. **先备齐人和测量条件**：A为唯一操板者，安排实际讲话者和听众；确认音响可立即断电，不戴耳机。
   麦克风、音响、前放及位置与strong标定一致。准备同一个固定录制人声源，固定外部播放设备、位置和音量；
   听众/测量设备位置及测量增益固定，关闭AGC。用于定量比较的录音设备必须能确认固定增益且无AGC。
   如果不具备录音条件，可完成真人报告，但听众定量结果仍未测；不能将手机自动增益录音冒充固定增益。
2. **启动唯一代码格**：出现PACKAGE_OK、DEFAULT_MODEL和HUMAN_SESSION_ONLY_5_TRIALS后，输入READY、SAME_SCENE。
   一次写清声源到麦距离、设备/听众位置、固定文件及音量、测量增益和AGC状态。
   确有真人讲话和人耳评价才输入HUMAN_LIVE_AND_LISTENING；PROXY或未核实会在发声前结束本轮，避免无效再跑。
3. **第1项路径门禁**：停止手机和全部外部声源/讲话，配置完成且仍静音后输入START，只播放包内定音。
   既有定音/噪底/漂移门槛保留，失败立即静音停批，不改时长或阈值。
4. **第2项真人8秒**：按提示在START时才讲话，不移动夹具。人耳如实选择CLEAR/DISTORTED/NO_AMPLIFICATION/HOWL/UNKNOWN。
   **只有可辨扩声且清晰才选CLEAR；仅听见原声选NO_AMPLIFICATION。** 不能以低音量不啸叫代替扩声效果。
   三类负面报告记failed并停批；UNKNOWN记未测，不虚填通过。保护、削顶或恢复未知也立即停批。
5. **第3项系统关8秒**：外部设备播放固定录制人声，系统为gain=0开路。固定听众位置记录声音。
   测量录音可用前6秒播放人声、后2秒停源背景；分别导出off-speech.wav和off-noise.wav。
   准备好在同一8秒状态内完成这两段，不把驱动结束后已静音的背景当作运行中的噪声。
6. **第4项门禁与第5项系统开8秒**：先停止外部声源，完成同一门禁；再按START播放完全相同的人声和音量。
   −14dB、FIR开启；位置、模拟配置、测量增益不变。按相同6+2秒方式录出on-speech.wav和on-noise.wav，并如实填人耳报告。
   路径门禁运行漂移5dB及所有保护门槛保持；不因真人或录音困难放宽。异常不继续第二种配置。
7. **录音与听众报告一次填齐**：程序提前打印本轮绝对目录
   `/home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc01-human-r1/results/sprint-<id>/listener/`。
   在确认提示前把四份固定名称WAV拷入：均单声道未压缩PCM16、同采样率、各至少1秒，人声两份同长度且无削顶。
   四份确实同源/同位置/同增益/无AGC才填FIXED_SOURCE_FIXED_GAIN_NO_AGC，否则回车记未测。
   程序做背景功率扣除并要求人声高于背景6dB；结果可为负值，不预设改善，未校准不输出绝对SPL。
   最后一次填写听众位置开/关的可辨扩声、清晰度、底噪、音色和失真；不确定写未知。
   listener passed表示定量测量资格通过，不自动表示扩声收益为正。人耳报告另列human_listener_report。
8. **停止、恢复、回包**：非START取消；保护/削顶/听感异常/门禁失败/通信落盘错误/恢复未知均停止。
   持续尖叫、严重失真或异常发热立即断音响电源并中断。A原驱动执行静音/清理，未知或失败时保持断电并交A处置。
   不自动重试、升档、换旧场系数或在原增益旁路。缺少清理回执记未核实，有明确失败才记failed，均不继续。
   最终RETURN_PACKAGE给唯一结果包：
   `/home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc01-human-r1/results/sprint-<id>/return-results.zip`。
   A只返此ZIP；包含状态、汇总、原音频哈希和板端绝对路径，NPZ/WAV留板，不自动上传人声。
   若内核被强杀，保留现场，在上述解压目录Terminal运行以下完整命令只封存既有记录，不重播：
   `python3 -c "from pathlib import Path; import json; from sprint_experiment import collect; [collect(p.parent,json.loads(p.read_text())) for p in Path('results').glob('sprint-*/summary.json')]"`。

顺利完成仅5项：2门禁、1真人、2听众，纯采集26.04秒；加配置、START、人耳报告及拷录音时间。
fir_comparison/continuous_60s本会话均记not_tested及not scheduled，不借用旧r4填本次通过；历史证据由C另行关联。
EQ identity，均衡贡献未测；不产生MSG/ASG，不以保护、削顶或尖峰直接判啸叫。
另一队友按冻结操作单的独立复现仍是单独验收，不能把A再次执行或C软件自测算作完成。

### r4原件交付要求

不重跑r4。原返回ZIP已从d013930取得，SHA256=9fd5c28704df0b35750cdf85fbd66cfee894db0467bb3ef22af0c9c3cb0a3422。
只需一次附同一轮现有07-fir-off.npz、09-fir-on.npz、11-fir-on.npz、13-fir-off.npz、15-continuous-60s.npz，
用于C独立复算FIR与当前配置60秒尾部算术。无需人声/听众PCM，无需补采；保持原文件字节，按原返回清单核哈希。
将这5个NPZ合成一个r4-review-return.zip提交，明确仓库位置；它与真人会话返回包分别留证，原返回ZIP无需再交。
FIR是4项/2组配对，r4前14项为有界试次；不写“14项FIR配对”。
60秒工程观测仅寄存器时间线+尾PCM约0.559%，不认证全程音质、话筒无削顶或全程无啸叫。
v2实际时序WNS/WHS=0.801/0.015ns，1输入/3输出缺外部延迟约束，不称完整I/O签核。
