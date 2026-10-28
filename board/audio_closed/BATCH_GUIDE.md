# C 测评与房间实验操作单

## 2026-10-28 Ac1既有三臂静默复算

**问题/前提**：只补 round `1746930178556850644` 的原件级数值复算，不重新发声。A=`c1a180f` 的单位修复已通过；旧A65建议补丁无需再次应用。bit/HWH/driver79/helperbba及原件保持原样，[三项结论](../../report/verification/audio_closed/batch-control.md#2026-10-28-ac1单位修复与原件静默入口)。

**唯一入口与位置**：电脑从本次C提交取 `scripts/review_itemized_20261027.py`，只复制这一个文件到板端 `/home/xilinx/jupyter_notebooks/base/audio/audio_wide`；不复制测试、A驱动或位流。A在该目录终端执行以下完整命令，无Notebook代码格、无令牌生成、无arm/播放，也不代答任何人工确认：

```sh
cd /home/xilinx/jupyter_notebooks/base/audio/audio_wide
/usr/local/share/pynq-venv/bin/python review_itemized_20261027.py --capture-dir . --round-manifest tone_round.json --expected-round-id 1746930178556850644 --out C-tone-1746930178556850644.json
```

预计数秒至数分钟；Ctrl+C只停止分析。入口只读原manifest/三臂NPZ/status，保留哈希和原执行身份，另写C派生JSON。若原manifest归档于同目录其他文件名，仅将 `--round-manifest` 指向那份既有原件；原轮ID不符、源/身份/窗口不合、缺文件或恢复失败均留拒绝记录并退出2。路径未找到就结束本项，不运行现场脚本来补造原件、不覆盖旧结果；结果已存在时换一个派生输出文件名。

**完成标志与回包**：只回板端该目录 `C-tone-1746930178556850644.json`，PCM继续留板。JSON保留原件SHA、原始确认文字和数值核对限制；退出0只表示派生记录的配对门通过，`captured_numeric_checks_clear`及效果结论另判。收到后C一次汇总原整窗FFT四差值、共同含源窗估计与运行资格，不将软件通过当效果通过。

**窗口**：按已有2.0秒源/2.2秒运行编码，末圈应有6619帧源区间；工具用真实元数据与源数组验证，分别报告整窗和共同含源窗。短窗采用已知频率的Hann加权正弦/余弦/DC拟合，保留背景与窗长影响，不保证信噪有效。无需将运行缩到0.336秒以内或修改捕获长度。2.4秒旧交替试次含源0帧，不能从其尾窗得到节目播放电平；当前 `played_level_report.sh` 的全局glob与无源尾窗回退均值不用作有效含源比较。数字电平仍不是声压、听众收益或ASG。

## 2026-10-28 A65修复后仅静默重算

A=`65b3311`的当前入口`field_ac_segments_v3.sh`已报告完成gate+三测量臂，本轮不再跑新纯音或B段。门禁/保护停止及三类分析资格修复通过，唯一当前数值代码缺陷是Hann幅度归一化；[逐条结论及扩大搜索](../../report/verification/audio_closed/batch-control.md#2026-10-28-a65三条修复及原件扩大搜索)。

给A的[建议补丁](../../report/verification/audio_closed/sprint-rc0-20261025/tone-guard-normalization-65b3311.patch)基于guardac93e60c…，只改两份tone_round_guard.py的level_dbfs和单位标签。C未改A源；由A采纳、核对两个已知单音和更新manifest后，将新模块部署到`/home/xilinx/jupyter_notebooks/base/audio/audio_wide`，位流/驱动/源/原NPZ不动。然后**只对现有真实manifest离线运行**：

```sh
cd /home/xilinx/jupyter_notebooks/base/audio/audio_wide
bash tone_analyze.sh
```

此脚本仅读现有文件/运算，无Notebook格、无arm；通常数秒，Ctrl+C停止分析。tone_round.json是既有脚本约定的默认位置，不代表C已确认该真实文件可读；须核round_id=1746930178556850644及其files真实路径。若默认manifest被覆盖，取原件归档，不重新运行field_ac_segments生成“替代原轮”。保留原JSON、三臂NPZ/status、SHA和副本拒绝记录，输出另存派生记录、注明guard哈希；无需回传真人PCM或重新做四项硬件/60秒。

C现有`scripts/review_itemized_20261027.py`已支持driver79/helperbba整对，可继续在原件旁静默统计；它不是tone_round身份清单替代品，不能从全局glob推定同轮有效配对。源与尾段按全局帧和source_pcm16实际长度分开。

后续83b交替源2s/运行2.4s的末圈全为源停段，不能用played_level_report的该尾窗或全局alt文件均值宣称含源可听扩声被否定。先复用已存在的65含源片段并标清单位、校验范围；取不到原件则保留未知，不增加现场试次来补包格式。

## 2026-10-28 A41补证后的运行决定

A=`41fd0d6`/driverc2b2a86a…/helperbba22102…的四项工程硬件补报已按A现场证据接收；60秒手机6/15、5cm是变更条件，定性阳性听感保留。C未操板，不把这些记录改称真人或候选收益。[通过项及剩余清单](../../report/verification/audio_closed/batch-control.md#2026-10-28-a41硬件补证与剩余流程验收)。

**本版先不执行有声纯音三臂**。gate保护仍可继续、纯音保护NPZ仍被当成功、3类不合格分析仍出数；先由A在现有`field_human_pair_v3.sh`/`field_stationary_v3.sh`/`tone_arms_v3.sh`/`tone_analyze.sh`修复，不在现场拼代码。无新参数和四项硬件重跑要求。

既有静默入口继续可用：电脑仓库`scripts/review_itemized_20261027.py`复制到已确认的板端`/home/xilinx/jupyter_notebooks/base/audio/audio_wide`，不换A驱动/位流/原件，然后终端运行（不用Notebook）：

```sh
cd /home/xilinx/jupyter_notebooks/base/audio/audio_wide
python3 review_itemized_20261027.py --capture-dir . --pattern '*.npz' --out C-v3-derived-41fd0d6.json
```

预计数秒至数分钟，Ctrl+C停止计算，已有输出拒绝覆盖；只回该目录`C-v3-derived-41fd0d6.json`，PCM留板。目录当前哈希与旧试次身份分开，不补造缺失时间线。需要核完整v2“8次”时，仅提供既有blind2_cand文件实际板端路径/哈希或在其真实目录静默分析，目录未知就停止这项，不新采。

修复并冻结脚本后，现场只安排一轮约30秒的原三臂入口+真实tone_round.json。仍固定原322Hz、amp0.15、−8dB、Codec40及夹具，任何已有前提改变须先记录而非自动升档。A现场真实确认源暂停/就位/开始后才生成一次令牌；保护/取消/恢复失败先停声留证并停止后续臂。拒绝样例在副本上静默构造，标明原件SHA及派生变更。最终保留同轮NPZ/status/manifest/执行日志与派生拒绝记录，一次回包；此段为修复后的范围，**不授权当前未通过脚本运行**。

C模型输出核对仍从skip+2；bba从索引2核对的是记录prediction对应的物理输出，不是前缀模型归因。两类覆盖分别解释，不把更多物理核对帧写成缺前史已消失。

## 2026-10-28 A交付版复验后操作范围

A=`ac30584`的v3交付快照与manifest共8项哈希一致：bit48e38f78…、HWH9411adb5…、driverc2b2a86a…、helper5b11b656…。C已支持该完整版本和历史完整版本分别复算，禁止跨版混搭。**当前有声编排仍有未通过项**，见[五条结论和一次修复单](../../report/verification/audio_closed/batch-control.md#2026-10-28-a交付版ac30584五条复验)；不要启动旧SUPERSEDED入口或将新脚本存在令牌解释为已获测量放行。

板端目录仍为`/home/xilinx/jupyter_notebooks/base/audio/audio_wide`。只把本仓库`scripts/review_itemized_20261027.py`复制到该目录，保留A位流/驱动/模型/原NPZ，然后在终端静默执行：

```sh
cd /home/xilinx/jupyter_notebooks/base/audio/audio_wide
python3 review_itemized_20261027.py --capture-dir . --pattern '*.npz' --out C-v3-derived-ac30584.json
```

该入口不运行Notebook、不arm、不播放。通常数秒至数分钟，Ctrl+C停止离线计算，已有输出拒绝覆盖；只回传本目录`C-v3-derived-ac30584.json`，真人PCM留板。其当前目录哈希与原试次执行身份分别记录，缺项仅限制依赖结论。

匹配候选的文件SHA应01c9102a…、实际Q20应6118e85d…；零臂另记e5a00aa9…及zero_coeff。A当前manifest把零Q20写在候选model字段下，待更正，不据此把零臂认作匹配臂。A当前driver的硬件输入满幅停声/60秒尚待补报；旧driver的成功留证不覆盖新版。C不要求整场重跑；后续有声动作待A修复明确失败分支、冻结相同脚本身份后按既定范围集中执行。

## 2026-10-28 B残差工具字段解释

B=`e730b5b`的剩余边界已完成[限定验收](../../report/verification/audio_closed/batch-control.md#2026-10-28-be730剩余边界验收)，不更换当前现场入口或驱动。它的返回键是`frame_domain`（ok/unknown）及`frame_domain_note`；旧`frame_domain_ok`只保留在历史证据中，不能将缺键当false或补成通过。

两端齐全且`first_frame+实际帧数=completed_frames`才是闭合ok。缺起点时，全局起止/事件/邻域位置为null，仍可保留局部算术。起点已知但缺completed时，当前程序保留依该起点推导的位置、闭合状态unknown；这些条件位置不证明完整运行覆盖或末尾一圈。C现用离线工具直接读原NPZ，无旧键适配要补，不改原件或为字段重采。

B工具只说明给定输入的算术；它不代替v3身份、bit22输入无效、保护及声学判据。`prediction`的“缺前史”指本地模型重放`pred_rep`，板上记录`pred_rec`没有因为抓包截断而清空历史。局部分析保留不等于现场使用或候选改善通过。

## 2026-10-27 v3同步与既有数据复算

当前目标是验收A=e132991的v3交付，不重跑现场。A的已冻结目录为`/home/xilinx/jupyter_notebooks/base/audio/audio_wide`：bit48e38f78…、HWH9411adb5…、replay_trial6b397359…、replay_tools0d4e1933…。v2回退`audio_live`与r6原包保持原样，不能交换其中驱动/工具；当前C有声入口未放行，原8项8/8不等于完整v3验收。[通过项及一次性修正单](../../report/verification/audio_closed/batch-control.md#2026-10-27-v3消费端同步与a交付验收)。

电脑侧唯一新增交付仍是本仓库`scripts/review_itemized_20261027.py`。A只把该文件复制到上述audio_wide目录，不替换其位流/驱动，然后在板端终端执行以下**只读**命令，不运行Notebook代码格或现场.sh：

```sh
cd /home/xilinx/jupyter_notebooks/base/audio/audio_wide
python3 review_itemized_20261027.py --capture-dir . --pattern '*.npz' --out C-v3-derived-e132991.json
```

文件存在就停止覆盖，改用新派生文件名；Ctrl+C只停止离线计算。通常数秒至数分钟、无发声，回包是本目录`C-v3-derived-e132991.json`。它包含原件SHA、原metadata、版本/输入/算术各自结果及当前目录身份；真人PCM留板。当前目录哈希不自动证明旧试次执行身份，须同次提供冻结运行版本/日志绑定，原NPZ不改写。旧字段可用原件SHA绑定的补充证据恢复范围，不为补包格式或字段重新发声。

v3硬条件：`capture_status` bit22或`input_full_scale_seen=true`使该试次测量无效，即使末窗安静、四类DSP计数0。输入标志与原寄存器矛盾、版本缺失/混搭、实际帧域不明时停止相应效果归因。增益前残差越界在v3仅作诊断，不自动判保护或啸叫；预测、增益后、混音、协议及既有停止规则保持。发生现行运行异常先停声再留证，离线“无效”不授权继续运行或自动尝试下一臂。

复算使用`gain(宽残差)`、增益后钳位再混音钳位；截断模型重放从`skip+2`核对输出。记录`wide_residual_frames`的严格有符号范围及实际捕获计数范围、`output_checked_frames`和起点；没有有效输出帧不作算术通过。v3尾段残差比按25位宽残差标注，不把捕获用24位钳位诊断值误作实际增益输入。v2原件继续按v2解释。

数字源结束帧只描述板上PCM。真人仍讲话时，不能据静音PCM的结束帧把麦克风末窗称为“源停尾段”；实际人声起止需单独留证。

后续现场脚本修正必须区分两种检查：**背景/路径门禁在人安静、外部音源暂停时，且在说话臂之前测**；**真人输入余量检查是在零输出下按实际位置/声量讲话**。安静门禁不能替代讲话余量，讲话时的电平也不能冒充环境本底。二者只约束已测窗口，不靠延长预检保证整段；前后环境检查必须同配置、同带宽，零输出背景不能自动充当闭环同增益的纯信号SNR分母。暂停、就位、开始讲话和听感均须实际人工确认，当前脚本的“先说话”提示及失败后继续问题待A修，不让其自动代答。

该夹具现有三组白噪占比差+1.6/−4.7/−2.1dB未形成有效采用依据，停止原样重复此占比流程。这里的限制是这些电平/背景/窗口下的测量资格，不推出白噪形式永远不能测，也不因总RMS不同就直接认定外源漂移。需可比激励、同窗及频带信噪/相干证据；不足仅使依赖项未知。322Hz纯音的残差差与麦克风差分报，不能冒充ASG或听众扩声收益。两段连续讲话也不是同一波形，听众“分不清”不能写成两臂相同。历史手机和v2真人成功观察继续保留。

## 2026-10-27 分项执行回包的离线质检

本轮唯一新入口是仓库`scripts/review_itemized_20261027.py`，只读已有文件，不加载overlay、不arm、不播放、不代答。A实际未运行r6的Notebook，派生结果明确`r6_native_execution=false`，保留原NPZ/status身份与SHA，不能改名伪装成原生r6回包。当前不重跑整场，也不改保护语义。

电脑文件：`D:\Flushbonading_Contest\ShengDi_PYNQ_Feedback_Suppression\scripts\review_itemized_20261027.py`。A将这一文件复制到**原先保存本轮抓包的实际audio_live目录**，该目录应有`blind1_zero_1746867688283325310.npz`和`blind2_cand_1746867731709459239.npz`。A此前只写了相对目录`audio_live/`，绝对路径尚待原脚本/日志确认；不要用猜测路径替代。原件留原处，目录未知就停止文件依赖分析，没有任何有声步骤。

进入该实际目录后，板端终端只执行：

```sh
python3 review_itemized_20261027.py --capture-dir . --pattern '*.npz' --out C-itemized-derived-20261027.json
```

不运行`layout.ipynb`，不用更改它的代码格。该命令仅依赖已有Python/numpy，遍历此目录已有NPZ/status、输出清单与统计，不能恢复未保存的波形。处理时间按现有文件量估计数秒至数分钟，无发声时间；可Ctrl+C终止，只影响本地分析。输出已存在则拒绝覆盖；选择一个新结果文件名。最终回传**本目录的`C-itemized-derived-20261027.json`**，真人PCM不出板；其中自动记录真实绝对来源路径、哈希、实际帧区间、两种满幅边界、计数、历史排除、数字回放和同窗功率定义。旧配置/缺项逐条保留，不自动当本轮有效。

同次给出既有`speaker_check.sh/input_check.sh/repro5.sh/use60.sh/stationary_arms.sh/blind_arms.sh`、原执行/人工动作日志、原60秒status/timeline及首次拒绝与恢复记录。白噪NPZ/status按已有权限取回，或用上述板端统计；需要身份清单中实际bit/HWH/驱动文件哈希。只取现存文件，不能用新执行补造旧脚本或动作。源码审阅只证明该版本代码的停声顺序，实际完成/保存要由原status核对。

源、窗口、背景须可比较；同录音同片段对齐可用于比较，真人同句两遍不保证波形相同。脚本分别保留含DC RMS、去DC RMS、Hann同窗总/带功率和占比；分开源开启区间与源停后50ms区间。候选保护与两臂输入削顶保留为不同事实；不得用预测饱和为0排除再生，也不把396Hz模型预测写成现场首次事件定位。汇总和最小缺项见[本轮质检](../../report/verification/audio_closed/batch-control.md#2026-10-27-a分项执行质检与最小补证)。

## 2026-10-27 成功工作点集中复现

本节保留r6（c-new-layout-1.5.0）交付时的操作记录。**后续A=df0956c已更正：历史成功对象是手机录音，不是真人；A本轮也未走此入口。当前只执行上节离线质检，不依据本节原5cm真人分支重跑历史。** 已冻结ZIP不改写，实际分项结果分别评价，不追认整套流程等价。

### 版本、位置与唯一入口

电脑仓库：`D:\Flushbonading_Contest\ShengDi_PYNQ_Feedback_Suppression`；跨设备从交接给出的C提交取仓库文件`build/packages/c-success-reproduction-r6.zip`，不依赖本机盘符。全目录解压至新目录，部署到板卡：

`/home/xilinx/jupyter_notebooks/base/audio/c-success-reproduction-r6`

不覆盖旧包/结果。A登记占用，核实现场只有一个操作者；C不连板。重启Notebook内核，打开本目录`layout.ipynb`，只运行从上往下**第1个代码格**，标题/首行：`# 成功工作点集中复现：输入与路径确认后执行`。代码为`from layout_experiment import run`、`result = run()`；不是用In[n]定位，不接入自动答题包装脚本。

静态文件、bit61bb71aa…/hwh92b499a3…、合法512项装载格式及实际Q20均自动核对。基线始终`zero_coeff=True`、数字−8dB；`baseline-model.json`只是经过校验的加载运输文件，实际发送512个零（哈希e5a00aa9…），不使用其中拟合系数。候选文件/材料缺失或失配，只阻断候选分支；基线运输文件、底层版本或路径/保护失效则停止依赖的有声步骤。候选仍为rewired：file01c9102a…/Q206118e85d…，不另训、不自动换旧模型。

### 现场准备与历史条件

历史成功按A更正是手机1101.m4a、8/15、约5cm、零系数、−8dB；两次听众反馈保留，不能当真人验收。下面“同真人/同句/SAME”的设计源于交付时错误的历史对象前提，不能认证手机条件原样复现。后来的接线故障也不能倒推过去成功必有同一故障。

本次用同一真人和尽量相同的一句话；手机/电脑音源暂停，不能用手机录音冒充历史真人。不恢复松动接触，保持当前可靠接线。标记人、麦、音响、听众位置。程序先处于零输出，再请求：

`REPRO_READY|讲话人标识|固定句子|SAME`

最后一项仅在能确认与历史同人、同句近似时填SAME，否则填UNKNOWN。UNKNOWN保留当前使用观察，但不认证严格历史复现；其他输入取消留证。这个确认同时核实几何、前放/旋钮、Codec、单人值守、不戴耳机、可立即断音响电源以及本地存音频许可。

### 输入与路径：每个失败阻断什么

1. 先自动采0.30秒输出为零的安静输入，再在历史约5cm做0.30秒实际真人检查。已配置且数字输出为零时，先按提示说正式响度的最响部分，输入`MIC_READY`并保持到短采集结束；随后停止讲话。**含DC绝对峰值严格<−6dBFS**，等于/超过、缺帧、非有限值、保护、参考/保存/恢复失败均保留原件。实际要求讲话时完全恒读也拒绝；不据此猜唯一故障。
2. 只有“完整有效、已恢复且仅输入峰值/削顶拒绝”的5cm静音检查，允许本批**一次**距离变更：`DISTANCE|实际cm`，范围15–30cm，其他声量/数字增益/模拟设置不变。变更后再静音检查。记录“原条件输入拒绝”和独立变更条件，不把它叫原样复现。其他异常直接停；不自动靠降低音量/增益通过。取消则保留原条件拒绝，不闭环硬试。
3. 程序显示安静/讲话RMS、绝对峰值等统计。操作者必须实际确认说话/暂停时输入有响应，输入`INPUT_RESPONDS`；NO_RESPONSE或UNKNOWN停止依赖输入的有声步骤。数字差仅描述，不发明通用人声SNR门限。
4. 真人与手机都**实际停止**后输入`SOURCES_STOPPED`。自动做安静/1kHz各1.02秒，定音峰值仍−20dBFS，每项前仍有0.30秒零输出检查。程序核对实际播放reference、同一帧窗、源结束与算术；保留旧6dB/0.8及相对10dB投影统计作为诊断，不靠降低阈值认证路径。
5. 定音结束且已停声后，操作者回答刚才是否由**指定音响**实际发出测试音：`TONE_HEARD / NOT_HEARD / UNKNOWN`。真人输入有效、实际数字参考有效且指定输出实听确认，构成分别确认输入/输出的正向依据；单项1kHz耦合估计未知，不抹去这两项事实。输入、实际输出路由或参考仍未知时，停止依赖的有声试验。人工确认不是算法自动通过；测试音正常也不证明全带模型匹配。

这就是r4仍需现场时的最小区分动作，已融入同一流程；不原样第三次重复r4。首次旧回包有手机污染，只作诊断；第二次没有原件的部分保持摘要级。既有第二ZIP在网络恢复后原样取回，不重跑补造。

### 基线复现、听众对照和持续真人使用

6. 在通过输入/路径的当前距离做`OFF1 → ON1 → OFF2 → ON2`，各9.5秒、同一人同句、相近响度、同位置。OFF为系统数字前向增益0，保留自然原声；ON为−8dB且实际零系数。每项先真人0.30秒零输出预检，通过后暂停讲话；正式代码/静音配置完成才输入`START`，听到实际0.15秒提示音结束后再说固定句子，提示音不计听感。 持续或重复固定句子至程序结束；提前停讲话、停顿或没覆盖到保存尾窗须如实记录，不补成全段通过。
7. 每次ON分别记录“是否听到声音”和“相对本轮OFF是否更容易听清、清晰、无持续鸣叫/明显失真”，保存听众原话。只有符合后者才填`AMPLIFIED_CLEAR`；另有CLEAR_NO_IMPROVEMENT、UNCLEAR、DISTORTED、HOWL、UNKNOWN。普通阴性可完成预登记第二次以判断重复性；失真/持续鸣叫或任何保护立即结束后续有声分支。旧两次成功原话一直保留，不用新阴性覆盖。
8. 两次均获清晰可辨扩声、输入有效、无保护且未见失稳证据后，同设置执行一次**60秒真人使用**，不是重做静默工程验收。先做人声峰值检查，之后暂停；live接口已配置且仍静音时请求START，确认后开始正常真人讲话至程序结束，手机不播放。该接口没有注入提示音，不能等待虚构的LIVE_ARMED/音频提示；精确语音起点未测。结束后真实报告全段使用、清晰度、鸣叫/失真和未覆盖情况。全程计数加尾部16384帧不证明全程声学稳定。

### 候选分支与结果边界

9. 基线无依赖的工作先完成；随后自动列齐候选身份/适用条件缺项。若缺项，保留已完成基线、结束候选分支，不等待B重交已交材料。条件齐全时仅在**同一−8dB工作点**做两对9.5秒真人零/候选比较，顺序零/新、新/零；每项预检、START及同句同位置保持。每对记录IMPROVED/SIMILAR/WORSE/失真/鸣叫/UNKNOWN、声量可比性及听众原话。没有自动升档、改Codec或全局扫描。
10. 比较后再做一次相同输入/输出确认与诊断，报告路径传递变化。单项估计缺失仅限制相应量化结论；明确漂移、声源或配置不可比则候选归因不足，但保留之前的基线使用与人工观察。真人未校准，不把mic RMS差、保护点或模态占比变成精确FIR收益/MSG/ASG。定量听众因录音增益/AGC未知固定未测，不索取四WAV。

完整分支最多28次有限调用，名义采集/运行预算约144.58秒；一次距离变更多0.30秒。它含大量零输出检查，不等于全程发声。另有装载、就位、暂停与听感，预计15–25分钟；任何早停都少于此数。配置核对、参考、计数和汇总自动完成，真人动作和听感必须真实回复，不逐项回来聊天。

### 停止、留证和唯一回包

强烈鸣叫/不适/异常先切音响电源；内核中断可停当前项。入口打印的`results/reproduction-<id>/STOP`在下一短项开始前检查，60秒由A原轮询处理。始终先disarm/mute，再冻结/读现有缓存、保存与恢复；保存失败不延迟保护。恢复未确认保持物理断声交A，不继续。

唯一回包：

`/home/xilinx/jupyter_notebooks/base/audio/c-success-reproduction-r6/results/reproduction-<id>/return-results.zip`

含配置/实际装载、全部成功/拒绝/取消/保护/未知、原条件与距离变更、提示/回复、听众原话、全程计数/时间线、原始语音位置与哈希。真人及其预检、60秒语音PCM留板，不自动上传；静默/测试音原件按既有授权回传。精确起振过程或未保存语音无法复核的部分标未知。

C用包内`layout_experiment.py review --return-zip <完整ZIP路径> --output <B结果JSON完整路径>`一次质检，分别输出`baseline_result`与`candidate_result`。报告“原记录配置下复现 / 变更距离条件可用 / 未成功 / 前置拒绝”及候选“定性改善 / 未观察到改善 / 证据不足”，附有效范围，不以软件包完整代替效果。本包不自动追加参数探索；若仍失败，一次交清失败类型与证据，由B选择一个可区分因素、C确认测量；本日最多一轮有明确分支的定向试验，仍无区分证据才交队长取舍。

## 2026-10-26 新布局一次集中实验

本节为r5（c-new-layout-1.4.0）唯一操作单。**不要第三次运行旧r4正向对照。** A=52ee4e4更正了麦克风状态与讲话距离，旧5cm/−8dB不再是工作点依据。原包及原记录只留历史，不改写成修线后的结果。

### 本轮问题、前提与模型放行

问题仍是：匹配当前正常接线与新布局的512项FIR，相对实际全零Q20是否改善运行，并支持相对系统静音可辨扩声？布局收益、算法差异、人耳效果及工程持续运行分开。

A=52ee4e4原scene按Git原字节保留为a-scene-input-original.json；scene-input.json仅派生当前fixture编号及来源映射，其余事实保持：讲话25cm，音响距麦1米侧对、上方30cm金属板/隔音棉，听众距音响20cm；Codec40、48828.125Hz、前放出厂未动、音响最大。A成品实际允许离散档位是**−14、−12、−10、−8、−6dB**，不是默认补齐所有整数；−4与0dB不在允许清单。噪声注入范围−30..−6dBFS是A的允许范围，不自动成为B模型有效电平或本批注入设置。本批不额外注入白噪声。

当前匹配候选来自B=b6bcfb2，文件rewired_512_20261026.json，SHA256=01c9102af5e010e5d40fe01edb54f38b1c34f09b4690a936f17a88cb8e235c23；Q20 SHA256=6118e85df7d9765bd5ae93fc204a32301135666b188bcc0fcf61e1447f6e8927。B转发254b8e9勘误明确系数未变；包内原报告按manifest实际Git来源取字节，C的c-integration-notes.json另记转发勘误和判读限定，不将未取得的提交冒充已读取。C核对模型/Q20/浮点/registry、修线六NPZ来源、512 taps、lag_first=1、bias不装载、1539拍与前向两帧语义；不重训、不重跑B旧145项。新布局旧newlayout候选不进入本轮效果。身份缺失或不符时入口触板前退出2、0试次并保存停止回包。B已交模型，不再等待另一个候选或日常会签。

修线数据来源是A=52ee4e4的bind-capture-2026-10-26/manifest.json，SHA256=1a4196c27730e4ceec678fc2d6debc755212790b494716b45d9e887769bfcfaa；六NPZ集合SHA256=46aad2acf0557698281d67fdac5724daad9e246f1225c4114093d52abd0036da。包内保留原manifest及details，原NPZ/旧fixture字段不覆盖。新运行实际传room_v1_20261026b，**名称相同不能代替修线状态绑定**。C的wire_repair_binding同时绑定这两个来源哈希、实际B源码提交、模型文件/Q20及依据；旧8a02757提交硬拒绝。

A底层驱动/位流仍是已验收原字节：replay_trial2127663…、live_run a3df27ac…、v2 bit61bb71aa…/hwh92b499a3…。每次加载记录实际发送Q20、512加载计数/状态，并用捕获数据核参考算术；不冒称系数RAM哈希回读。本候选实际加载、同条件对照未完成之前，任何效果结论都不成立；软件检查通过也不等于效果通过。

### 电脑、板卡与唯一入口

电脑包：`D:\Flushbonading_Contest\ShengDi_PYNQ_Feedback_Suppression\build\packages\c-new-layout-r5.zip`，从本轮C提交取得；跨设备按仓库路径取包，不复制本盘符。解压到新目录c-new-layout-r5，整个目录部署至板卡`/home/xilinx/jupyter_notebooks/base/audio/c-new-layout-r5`，不覆盖旧包，不用旧run_human包装脚本。

重启Notebook内核，清空旧模块/板卡句柄。打开该目录layout.ipynb，从上往下**第1个代码格**；标题/首行`# 新布局集中实验：核对绑定后执行`，内容`from layout_experiment import run`、`result = run()`。这是唯一现场入口，不用In[n]定位。C不连接板卡；A登记占用并现场确认只有一个控制者。

包已包含修线候选资格与兼容绑定；现场配置仍由A核实，不预填FIELD_READY。A在同一入口一次输入：

`FIELD_READY|25|手机录音的具体文件名|播放音量数值或档位|手机相对麦克风的位置`

该确认同时核实麦克风线正常、上述几何/模拟设置未变、起始外源停止且安静、单人值守、无耳机、可立即断音响电源、准许本地存音频。手机用自身扬声器对麦克风播放，不直接改接LINE_IN；文件/音量/位置三者在本批固定并存入field-scene及run-binding；每次从文件0秒重放同一8秒片段，起点也固定登记。25cm只是当前默认；若需在A记载的15–30cm范围内拉远，可重新解压到新目录，在**新批次**输入实际距离，不覆盖失败结果、不沿用失败批次配对。变化或未知则CANCEL，不逐项回来聊天确认。

A本轮可如实确认上次实际登记：`FIELD_READY|20|1101.m4a|8/15|麦克风左侧20cm`；20cm在已有15–30cm范围内，不要求移回25cm或改变几何。任何值已变就输入当前事实开新批次。FIELD_READY/MIC_READY/START代表现场动作已完成，禁止脚本代替操作者猜答；正向对照前手机必须实际暂停，房间安静。第二次旧回包尚在板卡时，网络恢复只取回原文件，不重跑旧试次。

### 每项开始前的硬性麦克风峰值门禁

每个正式步骤前，程序调用已有A驱动做一次0.30秒预检：source为零、实际全零Q20、前向数字增益0，扬声器无注入/扩声输出。整段约14648帧均保留，必须first_frame=0且帧数/完成范围、参考、清理均有效。预检峰值按ADC原值的最大绝对值计算，**包含直流偏置**，不以去直流RMS代替；故松线时恒读−4.2dBFS也会被拒绝。

通过条件是峰值**严格低于−6dBFS**。等于、高于、缺数据/缺帧、非有限值、采集不完整或保存/恢复失败均停批；不进入下一正式步骤，也不把它判为啸叫。失败先保持停声，再保存已有记录；建议降低目标源电平或拉远后重新冻结源/距离、开新批次，不在同一配对中边改边继续。不自动升降档、旁路或重试。

安静/定音/扫描前的预检自动执行。真人或听众前，提示“输出为零”时，用正式响度说最响部分，或播放固定手机片段，输入MIC_READY并保持到短预检结束。通过后先停止讲话/暂停手机；正式项配置完成且仍静音时再输入START，**实际听到0.15秒提示音结束后**才开始正式讲话/播放。这样既不在配置未完成时提前正式讲话，也满足A对提示音前安静、外源停止和输入峰值的条件。

预检只证明该0.30秒代表性输入；不保证未来整段的最大峰值。正式项保存窗若达到/超过−6dBFS也使该项测量无效并停止后续声音。8秒/60秒仍只有末尾16384帧；未覆盖区间不能填成全程峰值通过。A原数值保护仍独立生效，r5没有修改底层为实时−6dBFS保护器。

### 单一现场窗口与结果分支

1. 通过本包模型门禁和一次现场事实绑定后，自动做静默背景/1kHz正向各1.02秒；二者都有上述静音输出预检。**波形、峰值−20dBFS与时长不提高；改变的是测量方法。** 对相同原始帧窗33420..48340（14920帧）作1kHz正余弦投影，噪声基准取静默窗1kHz投影、静默邻频平均、含源邻频平均三者最大值。相同窗长/归一化，邻频为±8..15个频率格（约951..974与1026..1049Hz）；定音投影/该基准的对比度须≥10dB。实际reference必须是登记定音，时间轴和输入有效，原有峰值/数值保护保持。麦克风总电平不必压过宽带噪声，也不要求1k占总能量0.8；这两项仅描述，不再作runtime门禁。10dB是通路检出条件，不是模型放行、全带SNR或增益收益阈值。噪声扣除SNR只在噪声可代表、平稳/不相关假设下另报，不能把对比度直接叫纯信号SNR。
2. 扫描表已按B交付与A允许清单绑定为−14、−12、−10、−8、−6dB。各档零/新两臂各2.52秒、静默同源、次序交替；−8dB再反向重复一对。每项前峰值预检，异常立即停，不为扫完继续。−6已被A报告有掩蔽风险，获准试验不表示听感通过；禁止进入−4/−2/0。
3. 自动正向复核1.02秒，用相同相对检测；前后比较的是1kHz麦克风/实际reference的投影幅度比。该窄带传递量漂移超1.5dB使算法配对无效，超5dB停止后续声学步骤；宽带噪声变响不直接当路径漂移，保留其他有效事实。缺测频段只限制相应估计，不作废整批。
4. 真人零/新均−8dB、各8秒，讲话默认25cm、同一说话人同一句；各自先有代表性输入峰值预检。听到声音HEARD与匹配模型相对零系数IMPROVED/SIMILAR/WORSE等分开记。明确恶化/失真/啸叫结束后续分支，不凭旧5cm听感填成功。
5. 听众定性比较用已固定的手机录音、同音量同位置，先系统静音8秒、再新模型8秒；各自先做该目标片段的峰值预检。静音使用数字前向增益0，提示音结束后源为零，保留自然原声。听众回答DISTINGUISHABLE/NO_AMPLIFICATION/DISTORTED/UNKNOWN，再一次写清晰度、底噪、音色、失真。只听见原声/提示音不能填可辨扩声。
6. **听众定量项从启动起固定not_tested**：A没有固定可读录音增益的设备，AGC未知/不可控。程序不再索取四WAV，不把unknown写成AGC关闭，不拿定性判断替代定量。此轮不要求A新增录音设备；以后若单独要求定量再另定规格与授权。
7. 只有听众支持相对静音可辨扩声时才做同模型/−8dB的60秒单arm工程运行，之前仍有一次静音输出峰值预检。保持安静、外源关闭；数值保护、输入保存尾窗的峰值与清理分别报告。寄存器时间线加尾部PCM不证明全程声学稳定或长期语音效果。

以完整五档表计，最多19项正式短试次+19项输入预检；可选持续项再加1次预检和1次60秒运行，共40次有限调用。名义采集/运行约131.30秒，另有装载/恢复和真人/手机就位，预计15–25分钟。除必要的真人/手机动作和听感外，身份、峰值、正向、参考和计数检查自动汇总，不逐项回来等聊天。

### 停止、边界和一次回包

强烈啸叫/不适/异常先切音响电源；当前内核中断可停止各项。运行目录`results/layout-<id>/STOP`可停止下一短项（配置后开始前检查，不是短项实时停止）；60秒项由A原轮询检查。A始终先disarm/Codec静音，再冻结/读现有环形/计数和保存，不等磁盘/网络才保护。清理未确认时保持物理断声交A，禁止继续发声。

B的离线+5.08/+8.48dB只表示不同FFT网格的门控界差异，不能保底现场收益；Q20系数范围不是PCM满幅，噪声RMS估计不保证峰值不饱和。同档零臂停止、候选完成仅能报告执行差异，不直接换算一档dB下界。两臂到−6仍完成、候选边界被截断，或任一臂观察不充分时，报告边界/收益未分辨；不机械按最高完成档差支持或否定。保护后本包结束后续声音，另一臂或真人/听众尚未执行就标未测，不为填齐数据绕停止分支。相对正向对照仍不可检出、reference或时基无效时，同样保留已完成配置/数值记录并停止声学效果分支；不自动提高声量、降低阈值或将正向改成可跳过项。

分别报告执行完成、测量有效、算法差异、听众定性效果、持续工程运行；定量听众明确未测。保护不直接判啸叫，输入峰值门禁也不判啸叫。largest_completed_gain_db只表示该条件下完成的实际档位，未观察到完整边界就保留截断/未知；不能从宽带平均耦合−10..−12推全频环路裕量，也不从保护或旧14dB预期制造精确MSG/ASG。

唯一回包是入口打印的`/home/xilinx/jupyter_notebooks/base/audio/c-new-layout-r5/results/layout-<id>/return-results.zip`。成功、取消、模型未匹配、峰值拒绝、保护、保存失败都回同一包；不手筛失败项。含非人声原件、模型/配置及全部metadata/status；真人/听众以及其输入预检PCM不上传，只回获准统计，音频留本地。

C一次执行`python layout_experiment.py review --return-zip <回包完整路径> --output <b-analysis.json完整路径>`，重核原件、峰值、正向、配对和持续结果，再交B有效数据与不确定项。A只负责现场事实与加载；底层缺口给A、匹配模型/适用条件给B。没有新平台、旧算法重验或日常三方会签。

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
