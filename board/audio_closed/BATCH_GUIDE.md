# C 测评与房间实验操作单

## 2026-10-26 新布局一次集中实验

本节是本轮唯一操作单；下方旧包步骤仅为历史。问题：匹配 `room_side_100cm_v1` 的新模型相对零系数是否改善运行表现，能否支持真人可辨扩声？固定布局与 EQ，唯一算法自变量是实际加载的 512 项 Q20（新模型/全零），不用旧失配模型。完成标志是取得有效同条件配对、真人与系统静音的听众差别及候选工作点持续运行结果；负面结果也是本轮答案。只报告实际档位、时长、窗口和临界/未知项，不插值 MSG，不将离线界变成现场升档授权。

### 位置、输入与唯一入口

电脑仓库 `D:\Flushbonading_Contest\ShengDi_PYNQ_Feedback_Suppression`，C 分支；准备包为 `build/packages/c-new-layout-r1.zip`。跨设备从 C 提交取得该 ZIP，无需复制这个盘符。电脑解压到一个新目录 `c-new-layout-r1`，不要覆盖旧包。

包内已含 A=`2928a4a` 的原字节驱动、v2 bit/hwh、C 批次及已有听众工具。`a-field-config-original.json` 保留 A 原记录，原文 JSON 语法问题不静默修写；程序使用独立的 `scene-input.json` 实测事实，不把原记录中插值得到的 −2.5 dB 当作放行点。

候选未到时包不含 `model.json`，也不含任何旧系数代用品。B 一次交本场模型及 `candidate-input.json`：完整提交、文件/Q20/输入清单哈希、原时序留出与诊断对齐分别的证据、lag_first=1、前向两帧仅一次、适用频带与各带 SNR 定义/门限来源、允许增益和注入范围、事前预期与否定条件。C 只绑定并核对兼容，不重跑已通过的旧算法修复。

A 一次填 `scene-input.json`：已知一米侧对与上方30cm金属板/隔音棉不动；实测讲话距离、听众位置、MAX4466旋钮标记、音响旋钮标记、固定人声片段/哈希/播放音量、录音增益和无AGC。另给 A 实际允许的增益离散档及噪声注入范围、依据；固定通路定音与提示音均为1kHz/峰值−20dBFS，确认可用才置 `control_and_cue_approved_by_A=true`，并置 `verified_by_A=true`。未知不能填成已核实；B/A 都支持的档位与注入值才写入候选输入，禁止直接使用离线稳定界。

绑定由 C 在电脑执行（均在解压目录，路径参数指向实际交付件）：

```text
python layout_experiment.py bind --model <B模型完整路径> --candidate candidate-input.json --scene scene-input.json
python layout_experiment.py check
```

`ready=true` 仅表示软件身份和兼容条件齐全。失败一次列全缺项、退出2，不触板。绑定冻结模型与场景哈希；需要修输入时重新解压后绑定，不改已运行包。C 交 A 绑定后的整个目录/ZIP，不让 A 拼代码。A 可只补事实字段再由同一条 bind 完成，无需临时编程。

板卡部署到新目录 `/home/xilinx/jupyter_notebooks/base/audio/c-new-layout-r1`，上传绑定后的**整个目录**，不要上传旧 `run_human_r1.sh`。A 在现场确认只有本会话操板并登记占用。Jupyter 打开该目录 `layout.ipynb`，从上往下**第1个代码格**，标题/首行 `# 新布局集中实验：核对绑定后执行`，代码为 `from layout_experiment import run`、`result = run()`。这是唯一现场入口，不用 `In[n]` 定位，不运行旧 sprint Notebook。默认依赖 Python3、NumPy、PYNQ；先在电脑离线检查，不在现场安装新平台。

### 集中执行顺序与动作

1. 保持已绑定位置/模拟档位，现场值守、无耳机、准备断音响电源、同意音频只存本地。运行唯一格后只输入一次 `READY` 授权非人声批次；背景/正向对照/配对检查自动运行、自动汇总，不逐项询问通过与否。配置在静音中完成。准备包无绑定时返回停止结果，禁止有声试验。
2. 自动执行同场静默背景1.02秒、1kHz正向对照1.02秒；静默与正向均数字前向增益0、全零系数、同一Codec。用本场背景替代旧 −37.8dBFS；沿用已验收的通路检查：高于背景6dB、定音占比0.8、削顶检查。它只确认1kHz输出/输入通路，不认证全带模型匹配。
3. 自动执行两次配对，顺序零/新、新/零；每模式先背景2.52秒，再同一确定性噪声注入2.50秒、总运行2.52秒，共8项。增益与注入仅来自 B/A 绑定值；无自动升档。之后同场正向对照1.02秒。总11项约23.22秒名义运行，另有每项装载/恢复时间。前后通路漂移超1.5dB使算法配对无效（旧同条件比较要求）；超5dB停止后续声学分支。保留原始事实，不把单频检查当全带资格。
4. 真人项8秒：出现已配置且静音的提示后就位、输入 `START`，**实际听到包内0.15秒短提示音结束后**才讲话；提示音未听到就取消/断声。提示音不计入讲话扩声。该项只回答 `HEARD / NOT_HEARD / UNKNOWN`，不把听见原声记成扩声成功。
5. 听众比较：固定人声源、听众、录音设备就位后输入一次 `LISTENER`；否则本项未测。依次系统静音8秒/匹配模型8秒，各项 `START` 后实际听到短提示音结束再播**同一片段、同一音量**。静音由数字前向增益0实现；短提示音结束后注入为0，声学扩声输出为0，仍保留原声。听众回答一次 `DISTINGUISHABLE / NO_AMPLIFICATION / DISTORTED / UNKNOWN`，并一次填写清晰度、底噪、音色、失真。仅 `DISTINGUISHABLE` 支持相对静音可辨扩声；负面听感保持失败，仪表值不能覆盖人耳结论。
6. 复用已有听众测量工具：一个固定录音源、固定录音增益、关闭AGC，不上传人声。原始连续外录在本地裁出提示音之后同片段的等长单声道PCM16 `off-speech.wav`/`on-speech.wav`，各不少于1秒；各自同配置静默背景 `off-noise.wav`/`on-noise.wav`，各不少于1秒。四份同采样率，按原样保存到运行时打印的 `results/layout-<id>/listener/`。齐全时输入 `FIXED_SOURCE_FIXED_GAIN_NO_AGC`，缺失回车记未测。既有工具的6dB条件是含语音总功率/背景比，**不是扣背景纯信号SNR**；语音增量先扣背景，不是校准SPL，也不设通用效果通过线。
7. 仅听众报告可辨扩声时，在**同一候选/工作点**继续60秒单arm静默外源运行；配置完成、仍静音时 `START`。本项有意义的是新工作点持续工程运行，不重验旧驱动；全程寄存器时间线加最后16384帧PCM，声学缺测区仍未知。负面/未测听众时跳过，保持持续项未测，不以安静低档补通过。

整批最多15项，名义运行约107.22秒，现场预计10–20分钟（含每项装载、人员就位与四WAV整理，实际用时随板卡变化）。无需逐项粘贴输出或回到聊天等指令。

### 测量定义、停止与回包

每一arm是独立时间轴。保存实际 `first_frame/completed_frames/frames`、源结束帧、原四路、实际参考字与source/Q20哈希，先剔除环形首512帧未知历史及源末10ms淡出；同条件配对使用完全相同的全局试次帧窗。绝不把独立段连接成连续历史，不移动每段波形以提高相关。实际装载身份由 A 发送的系数/加载计数状态及捕获算术核对支持；没有系数RAM逐字哈希回读，不冒称具备它。

频带纯信号SNR=`10log10((P含源−P背景)/P背景)`，同模式、同增益、同频带、同窗；依赖背景平稳且不相关的假设。报告参考/mic电平、背景/含源/扣背景功率、门限来源及各带有效性。负功率或低SNR只屏蔽对应频带；不清空整批，也不现场提高注入。频带响应差是强迫响应窗口的描述，不是反馈稳定裕量、精确MSG或ASG。布局固定，布局收益未测；FIR收益另报。

任意强烈啸叫/不适/异常，先切音响电源。当前内核中断可停止各项，或在运行目录 `results/layout-<id>/STOP` 建空文件；短项在下次配置后开始前检查STOP，**不是短项运行中的实时停止**。60秒项由A既有轮询实时检查同一STOP。保护、削顶、异常中断、配置/参考/窗口不匹配、恢复未确认均停止依赖有声分支；不自动旁路、不升档、不第三次重试同一失败。SNR局部无效除外。

A驱动保持“disarm/Codec静音 → 读现有环形与计数 → 尽力保存”，不等磁盘/网络才保护；C只在驱动返回后汇总。保护前环形覆盖以已有缓存为限，丢失区间、落盘/清理失败保留未知；保护本身不判声学啸叫。清理失败由A查底层，先保持物理断声，不再次发声。

唯一回包为入口打印的 `/home/xilinx/jupyter_notebooks/base/audio/c-new-layout-r1/results/layout-<id>/return-results.zip`。成功/取消/保护/无效均回这一包；含非人声原NPZ、全体metadata/status、配置与汇总，排除真人NPZ和四WAV。不要手筛失败项；若落盘失败仍返回能取得的日志/目录并标明。最终听众音频只留板端或本地授权位置。

C拿到一次回包后执行 `python layout_experiment.py review --return-zip <回包完整路径> --output <b-analysis.json完整路径>`，统一核对回包哈希、重算配对及有效频带，再把原非人声数据、有效结果和不确定项一次交B。执行完成、测量有效、算法差异、听众效果、持续运行五项分报；`ready`/通路通过不等于效果通过。底层缺口给A、算法条件给B；仅完整有效实验失败、关键结论复核后冲突或范围/架构/截止改变才给队长一个问题。

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

### 下一次真人发包必须随消息列全的外部输入

此节补齐交付说明，不改变已冻结ZIP、不授权当前新布局执行旧模型；先完成R-009软件与场景核实，再发下一份完整现场包。
C须在发包消息正文逐项列出下表，不能只让A读代码或等到录音环节才发现依赖。

| A需准备的输入 | 谁生成、用途 | 要求与缺失分支 |
|---|---|---|
| 实际现场记录 | A核实讲话者/麦克风/音响/听众位置、朝向、模拟配置、固定源及音量、测量增益/AGC | 不用默认布局代填；未知写未记录，不能自动确认SAME_SCENE |
| 同一份固定录制人声源 | A用外部播放设备播放，两次使用同一文件、设备、位置和音量 | 真人自由讲话只用于真人项，不能代替两次固定源的听众定量比较 |
| off-speech.wav | A用外部固定增益录音设备在系统关、固定人声播放时录制 | 建议6秒；与on-speech精确同帧数，至少1秒 |
| off-noise.wav | A在同一次系统关状态、外部声源已停止时录背景 | 建议2秒，至少1秒；不能拿驱动结束、系统已静音后的录音代替 |
| on-speech.wav | A在系统开且FIR开启、播放同一人声文件时外录 | 与off-speech同帧数；录音位置/增益不得改变 |
| on-noise.wav | A在同一次系统开状态、停止外部声源时外录背景 | 建议2秒，至少1秒；保持开状态及录音配置 |

四份WAV均为**单声道、未压缩PCM16、同采样率、无满幅削顶**；关闭AGC、自动降噪及逐档归一化，
保留原测量增益。四份不是C包或板端NPZ自动生成，A需提供外部录音设备；没有条件则listener定量记not_tested，
不能填FIXED_SOURCE_FIXED_GAIN_NO_AGC。未校准不报绝对SPL；定量资格通过不等于扩声有正收益。

当前冻结包在C本地为`D:\Flushbonading_Contest\ShengDi_PYNQ_Feedback_Suppression\build\packages\c-sprint-rc01-human-r1.zip`；
板端解压根为`/home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc01-human-r1/`。
四份WAV只需在流程允许进入听众比较后产生，放入程序打印的本次**完整绝对目录**
`/home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc01-human-r1/results/sprint-<id>/listener/`，
操作者不需遍历历史结果找目录。真实人声文件留板；只回程序打印的return-results.zip，其中保留哈希和绝对路径。
若真人项失败停批，不为补齐这四份WAV继续运行；本轮不要求新录音或上传人声。

### 门禁的两种职责与换布局分支

当前首项不是与旧标定电平精确匹配：使用**传入底噪+6dB**、定音占比≥0.8、源内有效窗、上限和满幅检查；
首项没有previous_gate基线。随后≤5dB运行漂移和≤1.5dB成对漂移是配置一致性门禁，不能删成单一“有响应”。
[五个受控案例及耦合反例](../../report/verification/audio_closed/sprint-rc0-20261025/gate-coupling-review.json)验证以上区别。

冻结sprint调用仍硬编码旧场底噪−37.8dBFS。下一包须绑定当前同场、同模拟配置、源关闭的实际底噪原件与统计窗；
没有该证据就标未核实，不把驱动中的定音残差当实测静默底噪，不自动重置漂移基线去通过。
布局变化先使SAME_SCENE及旧模型适用资格失效，不能因1kHz读数相近或相对底噪有响应就授权跨场装旧系数。
先核实场景/标定资格再发新包；本轮未改变门槛、运行代码或保护，也不以自适应门禁掩盖NO_AMPLIFICATION。

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
