# 项目进度（时间线，只追加）

> **本文件是只追加的日志，不是现状。** 每条记录是"当时"的状态，越往下越旧，
> 其中"未上传/未验证"等字样只描述当日。**当前状态一律看 [STATE.md](../STATE.md)。**
> 规则：新条目加在最上方；不修改、不删除历史条目；每条结论都应能链到 `report/` 里的证据。

## 2026-10-26 C 收尾接收B候选与A零系数可用点

核头发现B=8a02757与A=1d7872c。B候选文件/Q20/registry身份及512项Q20、lag_first与A纯参数兼容通过，按原字节随准备包交付、未激活，采用B真实fixture_id=room_v1_20261026。A报告5cm近讲、−8dB零系数两次清晰可听放大，保留为使用事实，不当作新FIR收益或静音听众配对。
B只交相干0.8、未给数值注入范围/纯信号SNR条件，README残留错误Q20哈希与旧模型预测口径集中列明，不据此升档或改算法。A已知位置/档位预填，剩余条件一次转交。新增真实候选兼容用例后11项通过，原22项不重跑。见[集成证据](../../report/verification/audio_closed/batch-control.md#2026-10-26-新布局集中包集成)。

## 2026-10-26 C 修正Notebook正常保存的冻结校验

归档发现整份Notebook字节哈希会把正常输出/执行计数保存当作改动，改为冻结代码格哈希，其余载荷仍逐文件冻结。补原输出可变/代码修改拒绝用例，新入口10项软件测试通过；相关22项结果不因无关改动重跑。见[实际输出](../../report/verification/audio_closed/sprint-rc0-20261025/layout-tests-r1.txt)。没有改变场景、候选、判据或有声授权。

## 2026-10-26 C 集成新布局一次集中实验准备包

按ddafcb7/ca9b484指定版本读取新规则与审阅，在C复用A=2928a4a原驱动/v2和已有听众工具，加入候选/场景绑定、同场背景与正向、零/新反向重复配对、分段参考/频带SNR、真人/静音听众区别及候选工作点持续分支。缺身份触板前拒绝，保护先停声、失败不升档；非人声原件随唯一回包，C一次重算后交B。
新入口9项和相关22项软件检查通过，完整操作单与包生成器交付；未操板、未使用旧模型替代新候选。B未交部署候选，A新事实JSON有语法问题且现场未知项待一次补齐，因此准备包保持禁止发声。
见[集成范围/证据](../../report/verification/audio_closed/batch-control.md#2026-10-26-新布局集中包集成)、[操作单](../../board/audio_closed/BATCH_GUIDE.md#2026-10-26-新布局一次集中实验)。普通缺项分别交A/B，不送队长重新规划。


## 2026-10-26 C 复核新场扫描并给出增益/连续采集决定

从A=b104f20取得后续真人−6保护与旧系数/零系数对照报告，未采纳早先f45449d的−6默认建议，不发手改旧包。
六原件manifest/实际ref/Q20/v2身份独立通过；直接内积给184/185帧，18个按段频谱窗给428/1052个原样/诊断对齐合格bin。
325Hz稳定/增长/分块/缺口用原C判据实跑，未改阈值或保护。见[机器复核](../../report/verification/audio_closed/sprint-rc0-20261025/a26-gain-and-capture-review.json)。
给A单arm八块ref/mic的吞吐/银行/帧序号/缺口/停止验收请求，给B合并已有新场Q20交付和原时序留出要求；二者并行，R-007保持done。
配齐实际冻结夹具后，A routing通过、start_control旧绝对路径仍失败；记录字段更正已接受，不重复原保护注入。
见[完整任务/字段](../../report/verification/audio_closed/batch-control.md#2026-10-26-增益决定与连续采集请求)，C未操板或改A/B驱动/算法。

## 2026-10-25 C 独立验收B7c6d3ed并关闭R-007

B原134项回归通过，原件正例带summary/C-review退出0，原响应窗与两组配对数值不变；
C原入口控制器正例通过、八坏例均非0且ok=false/带诊断，整体退出0，R-007按既定验收范围关闭。
N1指定文本/标签修订接受，预算数字仍未独立复算、不作现场放行；B无新增任务，默认系数/候选决定不变。
见[最终验收](../../report/verification/audio_closed/sprint-rc0-20261025/b-7c6d3ed-review.json)、[实际CLI回执](../../report/verification/audio_closed/sprint-rc0-20261025/b-7c6d3ed-cli-controls.json)。
A=3ef1532新增测量撤回而未改R-009软件四文件；接受新模型禁用和撤回目标，单bin稳定增益字段及整带归因仍应修为未知。
该记录修正并入原软件交付，不新派上板或采集。见[A接收](../../report/verification/audio_closed/sprint-rc0-20261025/a-3ef1532-receipt.json)。

## 2026-10-25 C 验收B入口修复、A启动修复并补齐外录清单

B=12e5ce2的原130项回归、五原件正例及旧五坏例通过，数字不变；三个身份/模型绑定控制仍退出0且ok=true，
集中交B唯一入口修复，R-007未关闭。[原始回执](../../report/verification/audio_closed/sprint-rc0-20261025/b-12e5ce2-cli-controls.json)。
A=d8ffaf0的精确ask语义通过，撤销启动坏输入未修的旧判断；原deliver_check引用旧电脑路径退出1，交付仍未复现。
接受其布局预填和尾窗口径更正，余下nested scene字段及逐run出处要求交A同一轮修。[复核](../../report/verification/audio_closed/sprint-rc0-20261025/a-d8ffaf0-review.json)。
C补[四份外录WAV及现场依赖清单](../../board/audio_closed/BATCH_GUIDE.md#下一次真人发包必须随消息列全的外部输入)，
五项受控门禁证明首项相对底噪、后续漂移另判；同宽带RMS/不同峰值反例否定仅凭+3dB解释全部现象。
本线164项回归通过；未改A/B生产实现、门禁门槛或已冻结包，未操板、录音或发布新有声包。

## 2026-10-25 C 发布核头发现A新增近讲回包

C验收提交f4cba1b推送成功后，再核远端发现A新增50f30dd；立即取得原ZIP，7成员与冻结包身份通过。
原结果仍2项即NO_AMPLIFICATION failed、听众未测、无保护且恢复通过；标题5cm而scene写15cm，事实待补正。
启动D4脚本原字节未改，麦克风满幅统计只限保存尾窗；未读人声PCM、不请求重跑。
该缺项并入既有R-009，B五个入口反例要求不变。见[接收证据](../../report/verification/audio_closed/sprint-rc0-20261025/a-50f30dd-human-receipt.json)。

## 2026-10-25 C 独立验收B=05657e5及入口反例

从固定Git对象核验126件原源码/材料，补齐导出夹具后B原124项回归通过，16段预测CLI与保存JSON完全一致。
五原件波形CLI正例通过；四replay算术、60秒预测/残差及两组差分与C复算一致，B未测的60秒output保持未测。
指定N1残句、归因降级及OFF稳定断言修订接受。但五种坏输入均退出0且写报告，已交回B原入口修整体失败判定。
见[独立验收](../../report/verification/audio_closed/sprint-rc0-20261025/b-05657e5-review.json)、[真实CLI回执](../../report/verification/audio_closed/sprint-rc0-20261025/b-05657e5-cli-controls.json)；C检查器真实退出2，R-007未闭合。
A远端仍47367f9，原D4/现场事实诉求保持，无新派单、无板卡操作，两个已发布离线ZIP原样保留。

## 2026-10-25 C 结束前接收A真人负面结果与B新修订

发布两项离线交付后核头，取得A=47367f9与B=05657e5。A新回包成员/身份通过，实际2项即真人NO_AMPLIFICATION停止，按原JSON记failed、听众未测，未接受“五项跑通”提交标题。
新A提交未修改D4包装脚本；B新修订与波形报告转C待独立验收，本轮不重复派B。
见[A接收证据](../../report/verification/audio_closed/sprint-rc0-20261025/a-47367f9-human-receipt.json)。两个离线完整包原字节、哈希与验收结果均保持。

## 2026-10-25 C 从干净检出交付两个离线完整包

固定源码be3200e建立独立worktree，CPython3.14 -I -S两条正式命令各退出0；两个产物独立解压后再用自带检查器通过。
冷启动389560字节、听众管线49280字节，[真实退出码/哈希回执](../../report/verification/audio_closed/sprint-rc0-20261025/delivery-r1-check.json)与[原工具输出](../../report/verification/audio_closed/sprint-rc0-20261025/delivery-r1-console.json)留存。
R-010/R-011关闭；164软件回归通过，原Q20五项自检及assets别名通过，未操板或重发真人包。
见[冷启动报告](../ref/cold-start-reproduction.md)、[听众机器报告](../../report/verification/audio_closed/sprint-rc0-20261025/listener-pipeline.json)；A入口D4仍待修复，B没有新增派单。

## 2026-10-25 C 实现两项离线机器交付入口

按A=9be9fa0的新要求实现tools/deliver_check.py的cold-start/listener-pipeline和固定清单，准备从清洁源码生成两个独立产物。
听众生产函数移到标准库入口，冻结原函数对照和+3dB/三类坏输入通过，补preflight.assets兼容别名；没有重发真人实验包。
精确执行A新ask，None/CANCEL仍返回START，D4控制失败；人声现场继续等待。
见[冷启动操作单](../ref/cold-start-reproduction.md)、[A入口复核](../../report/verification/audio_closed/sprint-rc0-20261025/a-9be9fa0-human-routing-review.json)；R-010/R-011以真实干净检出的完成行闭合。

## 2026-10-25 C 复核B发布修订、A新增保护及五原件

Git两次连接失败后，官方API取得B=3657242的92件相关原件和A=9edd83b新增三次真人回包，逐blob核对。
B原CLI退出0、保存机器结果一致，数学函数/phase/Q20入口与旧原件未变；机器修订身份和两次实际值接受，N1残句与Part二过强归因退修。
A三个原返回包的成员和冻结r4身份通过；第二次−14dB约3.568秒保护、第三次源内定音占比不足，旧包装脚本讲话仍早于解静音。
将R-009改为先暂停有声重试、核实既有故障事实；随后发现A=63f6a69已补五原NPZ，原哈希及C独立功率/整数算术复算通过，关闭R-008。
三个坏输入控制拒绝，C审计入口修改后157项软件回归通过，未重跑FIR/60秒；B可直接取原件补波形侧判读。
见[B审核](../../report/verification/audio_closed/sprint-rc0-20261025/b-3657242-review.json)、[A真人尝试审核](../../report/verification/audio_closed/sprint-rc0-20261025/a-9edd83b-review.json)、[原件复算](../../report/verification/audio_closed/sprint-rc0-20261025/a-63f6a69-waveform-review.json)和[请求清单](../REQUESTS.md)。

## 2026-10-25 C 统一A与B的后续派单

重新fetch并同步C，核对A=d013930、B=71d6a34未新增提交；两个已发布ZIP字节数和SHA256保持一致。
将A的真人五项会话登记为R-009，与R-008既有五原件补交并列；B继续R-007三项发布口径和现有汇总的限定判读。
按用户要求记录每轮分别检查A/B派单的收尾习惯；[请求清单](../REQUESTS.md)是执行入口，[原始要求](../../report/ai-records/closed-batch-control.md#2026-10-25-统一检查ab派单)留存。
没有重建包、修改A/B代码或重复现场项目。

## 2026-10-25 C 封存r4原字节汇总交B限定判读

源码c0af379打出[给B完整包](../../build/packages/c-r4-to-b-r1.zip)，376395字节，SHA256=474975275f63173e490c23ea3d97ad77c0a78a5d0977ba8da807bb7bdfc20367。
14载荷及原A回包/汇总字节一致，包含两组fir_switch_pairs、相关状态和C数值/有效性审核；[归档核验](../../report/verification/audio_closed/sprint-rc0-20261025/b-handoff-r1-check.json)。
B先做限定判读，5个原NPZ继续由C等待后独立复算；真人包和模型/资产均保持。

## 2026-10-25 C 独立通过B修订1数值并整理r4原始汇总交B

普通Git连接失败后，以原账号官方API读取B=71d6a34，91件相关原件逐blob核对；原入口和24控制测试通过。
434保存数字吻合，独立按段谱累计/FFT/Q20核对带内最大差约9e−15，零模型/完美模型控制通过。
数值修复关闭，N1–N3发布措辞/机器标签仍待改；将已有r4原字节汇总和状态交B先判读，不等5原NPZ。
证据见[B修订验收](../../report/verification/audio_closed/sprint-rc0-20261025/b-71d6a34-review.json)及[交接范围](../../report/verification/audio_closed/batch-control.md#2026-10-25-b71d6a34数值验收与原始汇总交接)。

## 2026-10-25 C 发布更新r4证据的真人五项完整包

清洁源码59f2b2a构建[真人完整ZIP](../../build/packages/c-sprint-rc01-human-r1.zip)，365967字节，SHA256=0d0a006b12df0c5b45f7049db44aa52e07769cb1b7f17b2f827bcb30f5e69c0e。
48载荷/A七件/C八件原件身份、实际归档5项自检原样复现、PROXY触板前拒绝及8类坏输入拒绝通过。
附d013930原回包独立审核和B新预测反例，157项C回归通过；[归档证据](../../report/verification/audio_closed/sprint-rc0-20261025/sprint-package-check-human-r1.json)。
真人/固定听众现场未测；r4原始波形仍待5个既有非人声NPZ，不要求重跑。

## 2026-10-25 C 取得d013930原回包并完成元数据独立审核

结束前再次fetch取得A新增d013930，原r4返回ZIP入库；成员、冻结包身份、15项配置/回执、两组差分和2951点时间线通过。
总响应两次−0.171/−0.244dB，60秒2929687帧/计数0/清理成功；波形复算仍待5个既有非人声NPZ，不重跑。
精确执行A新ask函数，5秒讲话提示在START返回前，Codec仍静音；真人专用包直接用Notebook在START后讲话。
见[独立审核](../../report/verification/audio_closed/sprint-rc0-20261025/a-d013930-review.json)。

## 2026-10-25 C 收到r4完成报告并准备真人专用包

A报告r4跑完15项、FIR/60秒工程通过，真人/听众未测；fetch后A=85f4967尚无r4原包，C按转述登记，R-008一次请求已有原件。
真人5项流程保留同工作点和全部门槛，触板前拒绝PROXY，负面人耳结果记failed并停批，不重复FIR或60秒。
证据见[接收登记](../../report/verification/audio_closed/sprint-rc0-20261025/a-r4-receipt.json)及[操作单](../../board/audio_closed/BATCH_GUIDE.md#2026-10-25-集中实验-rc0)。
按用户要求再次核遍全部四分支，仍无r4原件；取得B=dbf2858新预测，精确原函数零系数反例应0却报+0.906dB。
只退新预测五项必修，旧默认/候选与判据接受不变，见[独立反例](../../report/verification/audio_closed/sprint-rc0-20261025/b-dbf2858-review.json)。

## 2026-10-25 C 冻结并独立核验r4完整归档

清洁源码0c6102b构建[r4完整包](../../build/packages/c-sprint-rc01-r4.zip)，357884字节，SHA256=4686557c73fae096cc136f52fc56931448b74d35df141111d72c6bd19f4f6ab1。
154项C测试、44载荷/A七件/C八件原件身份、实际归档15项自检原样复现及5类预检/3类资产拒绝通过。
最小有效窗14408，源预算余量976帧；同包接入当前模型/−14dB单次60秒工程流程，硬件及声学仍待测。
证据见[归档检查](../../report/verification/audio_closed/sprint-rc0-20261025/sprint-package-check-rc01-r4.json)，旧包及失败保留。

## 2026-10-25 C 修复r3装载前拒绝并接入完整v2流程

核对A=85f4967原返回包，实际第7项首个FIR装载失败；C承认软件夹具漏检真实驱动预算约束。
r4分开源2.50秒/运行2.52秒，保留14408帧同帧窗，原门槛不变；增加冻结A纯参数前缀及旧等长拒绝控制。
942fd5b独立7控制全通过，绑定匹配v2原件，加入当前strong/−14dB单次60秒工程编排。
预检软件流程通过，现场仍待测；证据及纠正见[r3/r4核对](../../report/verification/audio_closed/batch-control.md#2026-10-25-r3装载失败与r4完整v2接入)。

## 2026-10-25 C 冻结并核验RC0.1-r3完整归档

从清洁源码45f60d0构建[r3完整包](../../build/packages/c-sprint-rc01-r3.zip)，38载荷、A六件/C七件原件匹配。
实际归档Notebook取消无板卡导入；包内13项自检完整复现preflight，四项FIR源内窗均15384帧、声学unknown保留。
5类preflight与3类资产拒绝通过；固定−14dB、原门槛和v1资产，未自动称FIR改善或稳定。
证据见[归档验收](../../report/verification/audio_closed/sprint-rc0-20261025/sprint-package-check-rc01-r3.json)。
旧包保留，v2只退已复现的两项驱动接点；C未操板或修改A/B实现。

## 2026-10-25 C 定位r2低信号并实现r3受迫响应配对

核对A=1219851回包，FIR源后窗完整，实际失败为tail_below_signal_floor；未因PROXY降低阈值或延长等待。
r3固定−14dB，改用同一宽带源播放期间的15384帧响应配对；保留原信号底限、门禁、保护和unknown声学分类，152项C回归通过。
核验补交v2资产及后续1cddd52原3组工程数据；独立模拟驱动7控制通过5项，只退确认前静音/取消清理两项。
证据与决定见[本轮复核](../../report/verification/audio_closed/batch-control.md#2026-10-25-r2低信号停批与r3受迫响应)。
未操板、未改A/B实现；从清洁源码重建完整r3，旧包保留。

## 2026-10-25 C 冻结RC0.1-r2并执行实际归档自检

从清洁源码e844119构建[r2完整包](../../build/packages/c-sprint-rc01-r2.zip)，固定−14dB/Q12=817。
实际归档34载荷哈希、A六件/C七件源码原件一致；13项自检逐字段复现preflight，三点映射通过，
5类preflight及3类资产不匹配均拒绝，实际Notebook取消不导入硬件。证据见[最终归档验收](../../report/verification/audio_closed/sprint-rc0-20261025/sprint-package-check-rc01-r2.json)。
门禁与时长不变，旧包保留；v2缺项未混入，未操板或声称低工作点等于抑制成功。

## 2026-10-25 C 核验A回包并固定r2工作点

fetch A=cf949f2但不合并，独立核对回包6哈希及原r1身份。门禁源内94.7%实际通过；
0dB第二项9835帧保护中止，未作为啸叫阈值。A声明的v2 bit/hwh未在固定提交找到，主资产仍v1，
已有60秒汇总按工程范围登记为A报告、未独立复现。证据见[A核验](../../report/verification/audio_closed/batch-control.md#2026-10-25-a-cf949f2回包与r2决定)。
r2固定−14dB/Q12=817，新增PROXY来源及A资产绑定，三点映射和13项空跑通过，150项C测试通过。
门禁/时长/模型与A原资产未变；未操板。源码冻结后重建完整r2，v2缺项和原驱动接点集中交A。

## 2026-10-25 C 冻结并验证RC0.1-r1完整归档

从清洁源码75f95a1构建[c-sprint-rc01-r1.zip](../../build/packages/c-sprint-rc01-r1.zip)，
32载荷哈希、A六件原资产和C七件源码逐字节通过。归档Notebook取消未导入板卡；
包内自检复现全部preflight内容，13项/最短14920帧/6门禁/2FIR配对通过，五类失败preflight均拒绝。
证据见[归档验收](../../report/verification/audio_closed/sprint-rc0-20261025/sprint-package-check-rc01-r1.json)。
原RC0.1未覆盖，原定音失败、60秒未测及无新候选保持；未改门禁/实验时长或部署v2。

## 2026-10-25 C 关闭B最后两项并补齐包内发送方自检

B=6128282原109项测试通过，16输入哈希和220数值一致；七类坏输入原CLI返回2且不写数值报告，
4100帧混合片段丢4片/配对4帧/差0，最后两项关闭。证据见[本轮验收](../../report/verification/audio_closed/batch-control.md#2026-10-25-独立验收-b6128282)。
C增加随包软件夹具和自动preflight，使用真实部署Q20及实际13项编排验证算术/窗口；148项C回归通过。
通过HTTPS同步C分支成功；未改驱动/算法/位流、门禁或实验时长，未操板。源码冻结后从清洁提交重建完整r1包。

## 2026-10-25 C 验收B=6a09d36并收敛至两处实现遗漏

固定Git快照上完成B原103项软件测试及原入口复算，16输入、220数值吻合；
正常帧配对、正实轴端点、错误哈希与段身份拒绝验证通过。原CLI仍在清单缺失/损坏/漏项时返回0并写报告，
混合512/513帧片段时抛NoneType解包异常，集中退B两处，不重开候选。
证据见[本轮独立验收](../../report/verification/audio_closed/batch-control.md#2026-10-25-独立验收-b6a09d36)。
本轮未改生产代码、驱动或冻结ZIP；读取A新增v2契约与preflight要求，更新C依赖状态，未操板或部署。

## 2026-10-25 C 独立验收B=9937113并退回四组定向修正

通过官方API取得并重建固定Git对象，核对原提交/tree/blob身份，不切换或合并B。
B原11项回归与Q20哈希拒绝通过，16输入、148数值复算吻合；默认模型与无新候选决定关闭。
独立控制发现5a重复尾段加权、孤立正实轴bin漏检、缺段训练身份错移及清单不符仍继续，
集中要求修原脚本和结论表述。C复核工具147项回归通过，RC0.1完整包保持原哈希，A不用等候此轮离线修正。
证据：[B修订独立验收](../../report/verification/audio_closed/batch-control.md#2026-10-25-独立验收-b9937113)。

## 2026-10-25 C 冻结RC0.1完整包并核验实际归档入口

从清洁源码af045bf重建[c-sprint-rc01.zip](../../build/packages/c-sprint-rc01.zip)，独立解压核验26载荷，
A原驱动/bit/hwh六件、C六件源码和B默认模型逐字节一致。执行归档Notebook取消，无板卡导入；
执行归档编排13调用软件流程和两组FIR配对，原时长及全部门禁保持。
验证与完整哈希见[最终整包证据](../../report/verification/audio_closed/sprint-rc0-20261025/sprint-package-check-rc01.json)。
原实测定音失败保持未通过，60秒和独立板上复现保持未测。

## 2026-10-25 C 按授权完成RC0.1最小包内修正

用户确认允许区分定音与FIR源后窗、修正汇总，且不改驱动、不放宽门禁。
据此修正C编排、静默提示与具体停止原因，原时长和源保持。146项软件回归通过，
新增覆盖定音时窗、低定音占比停批及分析裁剪不覆写原捕获；完整13调用流程仍通过。
更新唯一操作单及完整包构建入口，证据见[RC0.1交付说明](../../report/verification/audio_closed/batch-control.md#2026-10-25-rc01-授权后修正与完整包)。

## 2026-10-25 C 复核A回包并否定仅延长定音运行的修复

读取A=8c7c49c原ZIP并核验成员哈希，确认实际门禁存在有效源内窗，失败为定音占比不足；
空窗属于另一路源后分析。调用未改门禁函数的纯定音/污染控制，证实1.6秒运行配1秒定音必失去源内窗。
FIR实际源为1.87秒，2.5秒运行已保留完整尾窗。准备最小C补丁及13调用软件演练，未改产品、驱动或阈值；
鉴于本轮明确只改时长，先交[原始复核与补丁](../../report/verification/audio_closed/batch-control.md#2026-10-25-a8c7c49c-回包与-rc01-时窗复核)，请求确认包内修正范围。

## 2026-10-25 C 完成GitHub重新同步与原提交核验

按用户要求重新推送；本机github.com的HTTPS连接超时，SSH主机校验通过但本地身份无法完成签名。
改用可达的GitHub官方Git Data API与既有Git凭据，逐个校验所有blob/tree/commit哈希，
以force=false快进C分支至62e1124并回读确认。原1601350、7db5408、62e1124提交号完整保留，
未改系统DNS/代理/SSH信任或远端配置。同步包含[RC0 r1完整包](../../build/packages/c-sprint-rc0-r1.zip)。
本次只更新交付状态，不新增板卡操作或性能结论。

## 2026-10-25 C 记录RC0 r1交付推送受阻

本地完整包和交付提交7db5408完成，独立解压24成员、A/C/B原件、默认选择及Notebook取消均通过。
向C分支推送遇连接重置，后续两次重试均为本机连接GitHub443失败；没有强推或修改远端配置。
新提交尚未推送，用户可直接取得本地完整ZIP；包与证据见[B交接复核](../../report/verification/audio_closed/batch-control.md#2026-10-25-接收-bd033d00-与默认系数决定)。

## 2026-10-25 C 确认同场标定默认模型并审阅B修复

接收B=d033d00，确认calibrated_20261024与原RC0 strong逐字节一致；更新默认选择/注册和RC0 r1完整包，
缺登记不回退旧candidate。原两项相位反例修复通过，部署Q20数值重算吻合；发现末端正实轴bin仍漏检，
Q20主入口和分段拟合代码待B补。标定失败采用静音停批，未自动同增益旁路。143项回归通过，无板卡动作。
证据与测量裁决：[B交接复核](../../report/verification/audio_closed/batch-control.md#2026-10-25-接收-bd033d00-与默认系数决定)。

## 2026-10-25 C 交付冲刺 RC0 基线集中包

读取队长固定A=bb56ef1而未合并A，重新核验原包并复现B相位负实轴和低相干缺口反例；
Q20频响与独立滞后多项式一致，留出/窗长和跨段反例保留。修复中断/恢复失败的测量分类，
编排真实人声、听众开关、两组FIR和所有停止/封包分支，冻结strong基线与A原驱动字节。
软件回归、原驱动模拟和唯一Notebook入口验收证据见[复核索引](../../report/verification/audio_closed/batch-control.md#2026-10-25-冲刺-rc0-与固定提交独立复核)。
将真正60秒及全程事件/PCM的最小调用、字段和验收交A，不拼段、不改底层、不新增板上性能声明。

## 2026-10-25 C 完成 lowband2 原数据复核

取得A=1003728原包，核验27个NPZ及强模型，四项闭环保存波形逐样本算术通过。
六定音按实际门禁窗复算与4.71 dB整窗口径不同，原1.5 dB运行门禁会全通过；
明确+7.01来自全16段、同口径留出6段为+4.56，不能注册全频段物理上限。
给B相位函数负实轴误判的最小反例，读已有低收益仿真后建议暂停新RTL，不重复执行。
R-004关闭，R-005要求修相位，R-006仅请求另一套侧放已有数据；近讲作为待队长决定的新夹具提案。
135项软件回归通过，无板卡动作、无新采集，证据见[原包复核](../../report/verification/audio_closed/batch-control.md#2026-10-25-lowband2-原包复核)。

## 2026-10-24 C 复核 A 08965d2 并修正房间汇总

静默读取两份已回ZIP，定位并修正C保护读取、尾段几何与不完整配对的兼容问题；
B原消费程序两份修正结果均0阻断。第二份6组完整且配置匹配，但候选尾段不足，有效配对0。
运行门禁改5 dB，配对另验通路漂移；保留原始停止与代理听感事实，不重跑旧批次。
接口变更：[房间协议v1.1](../contracts/audio-closed-v1.md#房间执行协议-v112026-10-24a-08965d2-反馈)。
分频带界只作预测，提出+6 dB设计目标；向A请求已有强标定材料，向B请求全频段独立复核。
证据：[回包与软件复核](../../report/verification/audio_closed/batch-control.md#2026-10-24-ready-回包复核与门禁-v11)。

## 2026-10-24 C 完成房间门禁 ready v1

取得 A db29698 的原始统计回包与参考臂说明，独立统计521行、无有效尾段和正向对照；
发现交接文字的部分原因计数为旧口径，使用ZIP真实3.1结果，不要求A再跑。
按A提出的满幅/固定门禁/满幅后复验要求实现限时房间包，采用本场重标定两模型，
保留A原驱动与位流字节。124项回归、驱动8/8、实际Notebook取消流程及完整软件编排通过，
B原消费程序对新版2.2汇总0阻断。发布可执行room ready包与源码，未操板或新增ASG。
接口变更：[房间执行协议v1](../contracts/audio-closed-v1.md#房间执行协议-v12026-10-24a-db29698-请求)，
calculation版本2.2、summary_revision3.2，旧统计产物不覆盖。
[回包审计和验收](../../report/verification/audio_closed/batch-control.md#2026-10-24-房间门禁-ready-v1)。
群聊使用已安装在线Tailscale和新用户环境执行一次check，脚本缺失即停止；没有重试或修改群聊代码。

## 2026-10-23 C 落实 B 消费反馈与历史证据区分

接收 B 59ab1ee 的新清单，注册三个原模型，两个补零产物分开存放；模型整数与原文件哈希不变。
登记旧 256 replay 位流、显式排除退役 audio_closed 的声学配对；增加抽头推导来源、
positive_control_valid 与分开的尾段/保护/通路原因。接口兼容增补 summary_revision=3.1.0，
schema_version=3 和数值判据不变，[字段说明](../contracts/audio-closed-v1.md#summary-v31-兼容增补2026-10-23b-消费方反馈)。
115 项软件回归通过；B 原消费工具检查软件/历史新汇总均可直接消费、0 阻断。
重建静默复算包，保持旧结果不改，未新增采集或实测 ASG。
[复核及包验证](../../report/verification/audio_closed/batch-control.md#2026-10-23-b-消费反馈summary-v31)。

## 2026-10-23 C 落实 B 的模型与尾段汇总请求

从 B ffa035a 接收三份模型，完成哈希和纯软件加载核对。新增 summary v3 直接配置字段、
三个尾段子带、独立事件、同增益模型配对及只读旧 NPZ 批量入口；111 项回归通过。
接口变更：仅新增测评派生软件 v3，不改旧汇总或寄存器语义，
[字段定义](../contracts/audio-closed-v1.md#测评软件汇总-v32026-10-23b-模型比较请求)；本条明确通知 A/B 消费方。
软件用例与 50 条旧汇总按来源分别交付，未声称完成真实板上同增益配对。
[验收和边界](../../report/verification/audio_closed/batch-control.md#2026-10-23-b-请求模型选择平坦字段和尾段汇总-v3)。


## 2026-10-23 C 补齐仓库分支交付

首轮只给本地 ZIP，用户指出不符合开发规程。随后先 pull --rebase 同步 C，
将本轮工具及包集成到 C，保留既有 C 测评、R-002 字段和历史记录。
[C 分支 102 项回归](../../report/verification/audio_closed/c-branch-integration-tests.txt) 全部通过；
[发布前文档检查](../../report/verification/audio_closed/c-branch-docs-check.txt) 为 0 错误、0 警告。
交付包含 [完整源码 ZIP](../../build/packages/c-integration-source.zip)、
[固定离线包](../../build/packages/c-experiment-v2-offline.zip) 及 [操作单](../../board/audio_closed/BATCH_GUIDE.md)。
接口文档仅逐字引入 A 已发布的 audio-replay v1/sweep v1，未更改生产语义；规则文件单独提交。
离线包继续保留缺件门禁，不因仓库发布将其改为可发声 ready 包。


## 2026-10-23 C 修正尾段判据并交付离线固定实验包

以 main 03f3063 为基线，集成 A 59aa10e 的只读板端资产；复核 50 条历史汇总，
定位 21 条源仍在播放的捕获及早停当尾段问题。用模拟原始寄存器复现保护计数错位，
提供 A 驱动消费方八项验收，未跨线改驱动。实现五类结论与独立事件、只读 NPZ 复算、
统一批次入口、固定包门禁、异常汇总与恢复。82 项软件回归通过。
[证据与边界](../../report/verification/audio_closed/batch-control.md#2026-10-23-c-测量复核-v2)。
初次包明确 offline_only，缺 A 修复驱动及已有兼容模型；未上板、未改算法或寄存器语义。



## 2026-10-20 C 线完成离线增长判据与文件回放

实现独立于板卡驱动的窄带增长检测，提供首次报警位置、满幅保护线索、缺帧与历史不足分类；
文件回放保留 NPZ 原始帧范围，不把尾缓存当作全程；输出逐窗 CSV 以追溯判据。
受控信号和 B 的闭环模拟输出用于回放验证，证据及预期来源见
[离线验收](../../report/verification/audio_closed/batch-control.md#2026-10-20-离线增长判据与回放)。
接口新增：C 离线测评 v1，字段、候选参数和适用边界见
[契约](../contracts/audio-closed-v1.md#离线测评-v12026-10-20c)。
本次未改变既有 summary、FIR、实时调度或板卡驱动，未播放、上板或测量实际 MSG/ASG。

## 2026-10-20 C 线完成 R-002 本地验收：实际配置汇总

JSON 每项与 CSV 增加驱动返回的实际增益编码、Codec 音量码和 bit 文件哈希；
保留原 metadata，缺失或取消不伪造配置，配对不一致保留原值并停止。R-002 标为 done。
接口变更：仅软件汇总 schema_version 升至 2，兼容字段与语义见
[软件汇总契约](../contracts/audio-closed-v1.md#批次软件汇总-v22026-10-20r-002)，供 A/B 消费方读取。
更新批次脚本部署哈希；完整软件回归输出和已标注的软件夹具见
[R-002 验收](../../report/verification/audio_closed/batch-control.md#2026-10-20-r-002实际配置字段导出)。
本次未控制板卡、发声、修改 RTL 或重建 bitstream。

## 2026-10-20 补上第三个通道：线间诉求

用户指出一个真实缺口：推到仓库后，别人的 AI 看哪里知道"我们在等他们做什么"？
上一版只做了现状（STATE）和时间线（log），**诉求没有家**——它散在交接文档和聊天里，
既没有责任人也没有完成判据，所以 R-001 那种"拷三个文件"的事会一直悬着。

新增 [docs/REQUESTS.md](../REQUESTS.md)：只有 open/done 两态，每条必须写清
「要什么 / 阻塞什么 / 完成判据」，请求方建行、被请求方关行。
接入开工与收工：开工第 2 步先扫"到=我"的 open 行，收工第 5 步关掉自己交付的条目。

同时把"拉取后 30 秒对齐"写成流程（WORKFLOW §2）：git log 5 行 → STATE 三条线的
「最后动作/当前卡点」两行 → REQUESTS 里点我的 open 行 → log 顶部 1-3 条。
为此要求每次改 STATE 先更新这两行；`scripts/check_docs.py` 现在会检查这三段有没有
"最后动作"行，并打印 open 诉求数量（当前 3 条 open）。

## 2026-10-20 文档体系重整：按变化速度分层

全仓重整一次。**病因不是"文件多"（41 个文件、3963 行），而是同一事实没有唯一位置**：
`6.92` 出现在 19 个文件里，`ASG` 出现在 38 个，"当前状态/下一步"这类断言散在 30 个文件，
"现状"本身有 4 个家（根 README、progress 顶部、IMPORTANT-ai-progress、handoff），且已经互相矛盾。

处置：现状收到 [STATE.md](../STATE.md)（覆盖式）；时间线改为
[log/](../log/)（只追加，`progress`/`experiments`/`handoffs`）；现行契约进
[contracts/](../contracts/)，7 份废弃的诊断接口进 `contracts/frozen/` 并加冻结横幅；
5 份失效任务与 procurement 进 `archive/`；新增 [INDEX](../INDEX.md)（唯一入口）、
[WORKFLOW](../WORKFLOW.md)（3×(人+AI) 协作协议）。文件名由"日期式"改为"主题式"。

工具与验证：全仓相对链接重算，`scripts/check_docs.py` 报告 **0 错误 0 警告**
（断链 / 孤儿 / 重复"现状"标题 / 契约状态头）；62 项软件测试仍全过；
迁移映射见 [archive/MIGRATION-2026-10-20.md](../archive/MIGRATION-2026-10-20.md)。
本次未改任何 RTL、算法或板卡相关代码。

复盘：重整过程中我自己也制造了一次不一致——测试数从 60 变 62 后，5 处文案没有同步，
已统一。这正是本体系要防的病，说明"数字只写在一处"的规则必须先落到自己身上。

## 2026-10-20 B线开工：模型诊断、闭环参考模拟与现场增益范围

新增逐频点分析口径 `CD(f)=20log10(|H|/|H-Ĥ|)` 与稳定增益估算 `MSG=1/max|H-Ĥ|`，
补上闭环参考模拟（逐帧复刻 `played[n+2]=gain(residual[n])`、Q4.12 增益、24 位饱和）。
两套独立实现互相核对：合成路径上旁路/抵消256/抵消512 的模拟起振增益为
2.11/6.48/15.23 dB，全部落在预测区间内并贴近相位口径，见
[本轮报告](../../report/verification/algorithm-2026-10-20/README.md)。

关键判断：**宽带 RMS 与 ASG 会给出相反的排期结论**。合成里抽头 256→512，
宽带只涨 2.6 dB 而 ASG 涨 8.9 dB；把已知真值截断到同样抽头数，所得最差频点深度
与拟合模型相差不到 0.15 dB，说明限制来自覆盖长度而非估计器。单 MAC 每抽头 3 拍、
帧预算 2048 拍，架构上限约 680 抽头（256 抽头 = 1.79 m，512 = 3.60 m）。
按 |H| 加权的候选仅 +0.18 dB ASG、代价 −1.07 dB CD 中位，本轮否定。
62 项软件测试通过（38 项既有 + 24 项新增）；公开接口见
[路径分析v1](../contracts/path-analysis-v1.md)。

**本次全部结论来自合成夹具与已有报告数值，真实数据尚未运行。** 板上静默脚本
`board/audio_calibrate/path_analysis_box_v1.py` 已备好；更推荐把
`training_box_v1.npz`、`validation_box_v1.npz`、`candidate_box_v1_256.json`
三个文件（约 1 MB，不含人声）拷出板卡，用
`python scripts/analyze_path.py --data-dir <目录>` 在本地分析——**B 线不需要板卡在线**。
给 A 的背景与配合事项见 [B→A 交接](handoffs/2026-10-20-b-to-a.md)。
真实 MSG/ASG、端到端延迟、音质仍全部未验证。

## 近期成果归档与GitHub同步

按用户要求归档闭环RTL/构建与上板包、批次工具、38项软件测试证据、用户返回的四项基础复测、推进纠偏提醒及A/B/C并行分工和提示词。交接文档已改为最新状态，去除过时的“下一步才实现闭环”安排。当前核心缺口仍是实际抗啸叫效果，不增加任何新实测结论。

本次同步排除NA/、data/post40/post41临时文件、构建缓存及原始录音。提交和推送结果以Git记录为准；上传代码不表示新版批次已上板。

## 三人并行职责与提示词已确定

用户确认A负责实物验证及板卡，B负责已有数据分析与核心算法改进，C负责测评代码和工具。新增 [详细分工](../lines/README.md) 及三份可复制AI提示词，规定独立开工任务、交付、文件边界、单板调度和数据/接口交接；同步纠正开发规范中的旧A/C分工。本次只完成文档，没有启动新AI任务、开发算法或执行板上实验。

## 2026-10-19 推进纠偏：基础验收结束，转向实际效果

用户明确批评现场试验过碎、反复低增益核对耗时，却未交付抗啸叫效果。批评已写入 [接手AI重要提醒](../rules/progress-mandate.md)，并接入AGENTS及开发规范。

当前已有闭环代码、上板数字核对和恢复证据；核心目标仍缺正常可听扩声条件下的旁路/抵消效果对照及稳定增益差异。约−36dB的四项基础试验已经结束，不再重复。“一次没听到尖叫”不构成模型有效的证据，旁路同样未啸叫。

原−30/−24/−18/−12dB批次保留为工具，尚未收到该批结果；不再默认让用户直接执行。下一项先用板上已有标定数据做静默路径分析，估算有依据的增益范围与模型改善空间，再准备完整现场对照并一次汇总。此分析和正式效果对照均尚未执行。本次只同步文档，无新增硬件结果。

## 用户返回四项基础闭环复测，均未听到尖叫

附件四项均约−36dB、0.5秒，回读核对全部通过、三类饱和及满幅样本均0，脚本报告恢复静音；用户称一次都没有听到尖叫。已保存原始文字和提取metadata，见 [本轮结果](../../report/verification/audio_closed/board-basic-repeat.md)。这是基础四项的新记录，不是八项增益批次，未测MSG/ASG。基础验收不再重复，后续进入批次范围探索。

## 批次控制与汇总已准备，等待现场使用

用户先后返回zero_cancel、model_bypass、model_cancel及2秒speech_bypass：均bit_exact=true，三种mismatch和饱和为0，脚本报告恢复静音；抵消路径已有低增益板上算术证据，尚无ASG。用户反馈真实模型抵消仍无可听声音，不能用作抗啸叫效果结论。

新增closed_batch.py和batch_trial.ipynb：−30/−24/−18/−12dB，每档旁路/抵消各2秒，配置就绪仍静音，现场输入START才发声；结束输入听感再继续，无需逐项聊天。任何算术/饱和/配置错误或不良听感停止整批，每项保存JSON/CSV及原始metadata。没有全程频谱监测，输出明确不是MSG/ASG。未修改RTL/bit/hwh，未操作板卡。使用说明见 [批次操作单](../../board/audio_closed/BATCH_GUIDE.md)。

## 首次闭环零模型旁路：板上结果已返回

用户仅完成zero_bypass：约0.5秒、增益−35.99dB，回读bit_exact=true、三种mismatch及饱和均0，脚本报告恢复base和静音。zero_cancel和真实模型仍待执行，未测ASG；见 [用户结果](../../report/verification/audio_closed/board-zero-bypass.md)。操作单和Notebook补齐每格目的、动作、通过条件及继续顺序，代码与bitstream不变。文件名使用板卡旧时间，不作为实际日期证据。

## 2026-10-19 闭环最小版完成本地实现，进入现场A/B

新增独立audio_pl_closed：麦克风→预测相减/旁路→PL数字增益→DAC；两模式共用时序与增益，FIR/I²S及开环工程未改。已通过线级仿真和31项软件测试，整板bit/hwh生成：2573 LUT、4104 FF、48 BRAM、3 DSP，WNS0.666ns/WHS0.021ns。零系数+单位增益的两模式输出逐样本相同，实际播放历史、在线切换和限时保护已在仿真覆盖。ADC有效到TX装载2286拍是本地时序测量，不是模拟端到端延迟。

[手动上板包](../../board/audio_closed/README.md) 与 [证据](../../report/verification/audio_closed/README.md) 已备好；未上传、未上板、未播放。下一项现场低增益零模型及真实模型A/B，不再把旧指标窗口统一作为闭环前置。仍无MSG/ASG结论，原有I/O约束缺口保留。

## 2026-10-19 文档整理与GitHub同步

统一README、入门导航、核心代码索引及架构框图，清除当前入口中“FIR尚未实现”的过时表述；新增10月19日交接，补齐证据索引。历史日志保留当时状态。同步范围包含文档引用的源码、仿真、上板包与验证报告，排除NA、data/post40/post41等临时诊断文件、构建缓存和原始录音。提交与远端结果以Git记录为准；本轮不控制板卡、不重新采集、不重新宣称硬件验收。

## 2026-10-19 首次板上开环残差通过逐样本核对

用户反馈短噪声并提供保存文件metadata：16384帧，reference_sequence_verified及bit_exact均true，预测/残差mismatch与饱和均0；16128帧评价的开环预测误差降低6.92055 dB。bit哈希与本地包一致。证据为用户返回数据，原始PCM未传出板卡，AI本轮未控制硬件。第二次同名调用因防覆盖保护停止，不是硬件故障。详见 [首次板上结果](../../report/verification/audio_residual/board-result-2026-10-19.md)。下一步统一旧/新记录评价窗口做静默差异分析；闭环ASG仍未验证。

## 2026-10-19 修正Notebook自身哈希校验

用户已在板卡运行残差Notebook第一格，反馈AssertionError指向residual_trial.ipynb。原校验错误地包含运行/保存时会变化的Notebook自身；已将本地第一格改为明确核对bit、hwh和两个py四个固定文件，打包清单移除Notebook自身哈希。实际在本地执行校验部分返回PACKAGE_HASHES_OK，未导入硬件驱动；板卡修复后执行尚待用户反馈。本次不改RTL、bit/hwh或采集脚本，不播放、不采集。

## 2026-10-18 开环残差音频集成完成本地验证及整板构建

新增audio_residual独立overlay：256抽头实时FIR与I2S集成，四路参考/麦克风/预测/残差按输入帧保存，16384帧激励预算，ADC不回送DAC。实际通过两组种子的线级仿真、加载/故障/限时/停止检查，以及25项Python软件测试（含模拟MMIO/I2C恢复）。Vivado2018.3整板bitstream生成完成：LUT2164、FF3028、BRAM48、DSP2，WNS1.741ns、WHS0.049ns；DRC0错误、3条DSP流水警告。仍缺1输入/3输出I/O延迟约束，非完整板级签核。

本地 [上板包与手动操作单](../../board/audio_residual/README.md) 已含bit/hwh、脚本、Notebook和哈希；[验证报告](../../report/verification/audio_residual/README.md) 保留范围与失败纠正。未上传、未加载新overlay、未播放或采集；下一项需要现场手动运行约0.336秒开环核对，先验逐样本bit_exact，再评价残差。仍未验证闭环ASG。

## 2026-10-18 真实长度比较完成，首版保留256抽头

已恢复Jupyter访问，上传并执行静默compare_lengths.py。相同验证区间上128/256/512抽头分别为4.2800/9.7974/10.1671 dB，完整整数与浮点差不足0.000002 dB，预测和残差饱和均0。512仅比256增加0.3697 dB、周期接近翻倍，决定首版保留256/Q20，下一项进入开环残差音频集成。结果及评分区间与旧9.69 dB差别见 [实测数据比较](../../report/verification/feedback_fir/board-length-comparison-2026-10-18.md)。本次没有播放、采集或更换overlay，原始PCM留板；开发集复用，不是新独立验收或闭环ASG。

## 2026-10-18 定点抵消核完成本地验证，进入算法对照

新增可加载系数的feedback_fir：24位PCM/Q20、58位累加、前一帧参考、预测和残差输出及饱和标志。19项软件测试通过；256抽头2304帧RTL与整数参考逐项一致。100MHz独立核布线后WNS2.341ns、WHS0.053ns，LUT876、FF406、DSP2、BRAM0；771拍计算延迟。不含板级I/O签核、PS或音频顶层集成，尚无新的整板bit/hwh。

已实际执行128/256/512长度、完整整数误差、固定/受控NLMS路径变化的合成对照，结果见 [本轮报告](../../report/verification/feedback_fir/README.md)。这些是合成研究结果，不替代现有真实箱体9.69 dB基线。真实数据新比较因Jupyter访问超时未执行，静默脚本compare_lengths.py已准备但未上传。下一步恢复连接做真实开发集比较，再集成硬件开环残差；闭环扩声、自适应语音及ASG仍未验证。

## 2026-10-17 新队员入门导航

新增 [入门导航](../ref/getting-started.md)，按当前状态、框图、直通RTL、开环采集、算法、验证和底层工程组织阅读顺序，并给出分工侧重点。仅新增文档及入口链接，未修改代码或操作板卡。

## 2026-10-17 工作区架构说明

核对当前目录、核心RTL及构建脚本，新增 [工作区结构与系统框图](../ref/workspace-architecture.md)，包含目录树、文件职责、三张Mermaid框图及耦合点。明确各overlay互相替换，板卡数据与本地工作区分离，实时FIR仍待实现。本轮仅文档整理，未操作板卡或重新构建。

## 2026-10-17 核心源码中文注释

为标定采集/路径拟合两份Python及直通/标定三份RTL补充中文注释，新增 [代码阅读索引](../ref/code-reading-guide.md)。Python AST和RTL去注释文本检查一致，未改变功能、未重建或上板。注释改变本地文件哈希，原manifest继续保留历史构建/上传版本；前后哈希及语义检查见report/verification/core-comment-check-2026-10-17.json。

## 2026-10-17 交接文档同步

新增 [工程交接](handoffs/2026-10-17.md)、[日志证据索引](../../report/evidence-index.md) 和 [协作经验](../../skill/audio-collaboration-lessons.md)，统一README及接口中的过时状态。近期技术结论仍为下节两轮标定及开环预测9.69 dB；本轮仅整理文档，未操作板卡、未新增性能测试、未提交或推送。基线未冻结、板卡数据未备份及人员待指定等缺口已写入交接页。

以下按事件保留历史状态，同日较新条目位于上方；旧条目的“未上传/未验证”仅描述当时状态。

## 2026-10-16 两轮标定完成，真实路径离线验证9.69 dB

用户完成第二轮，反馈可听短噪声及32768帧保存、参考校验通过、base/PLL恢复并静音。AI已上传并核对现有calibration.py，在板卡本地以第一轮训练固定256抽头模型、第二轮独立验证。实测数据的开环预测误差降低9.6893 dB；四等分9.51～9.96 dB；Q20系数量化后9.6893 dB；参考错移4096帧对照为−2.8578 dB。原始PCM留在板卡，本轮不发声、不操作overlay。候选模型和分析JSON保存在板卡，Notebook已保存、内核空闲。

本阶段确认可重复路径具有建模价值，**不是反馈抑制或ASG成功**，尚无完整整数运算及实时抵消验收。完整证据和限制见 [板上分析记录](../../report/verification/audio_calibrate/board-analysis-2026-10-16.md)。下一项为可加载系数的定点FIR及开环残差验证。

## 2026-10-16 第一轮开环标定已获现场结果

用户手动运行训练轮并反馈听到短噪声，粘贴完整输出：`STOCK_PLL_READBACK 0271023c2103`、`STOCK_BASE_RESTORED_AND_CODEC_MUTED`、`LOCAL_CAPTURE_SAVED training_box_v1.npz FRAMES 32768`、`NO_DATA_UPLOADED`。麦克风RMS为−21.11853362140025 dBFS，峰值−5.670635405233404 dBFS，满幅样本0，`reference_sequence_verified=True`。证据为用户返回的运行输出与听感；本轮AI未读取原始PCM或再次控制板卡。

这支持第一轮已知激励、同步记录、序列核对和恢复流程完成；无满幅样本不排除模拟端失真，也不能单凭RMS判断路径拟合质量。下一步保持同一布置和增益，以种子1保存 `validation_box_v1.npz`，随后在板卡本地拟合和独立验证。尚未计算真实路径系数或证明反馈抑制。

## 2026-10-16 标定文件已上传，等待用户手动触发第一轮

用户回复“标定就绪”后，已将 `audio_calibrate.bit/.hwh` 与 `open_loop_capture.py` 上传到板卡 `base/audio/audio_calibrate/`。新建 `Untitled.ipynb`，第一格逐文件比对本地清单 SHA256，板上打印 `UPLOAD_HASHES_OK`；执行脚本定义后打印 `OPEN_LOOP_CAPTURE_READY; no sound until explicitly calling open_loop_capture`，内核空闲。

第二格已保存但未执行：种子0、shift=4、hp_volume=40、fixture_id=`box_v1_20261016`，目标文件为板卡本地 `training_box_v1.npz`。本轮没有加载新 overlay、播放声音或保存 PCM；用户手动触发一次后，先核对完整输出与听感，再准备独立验证轮。未获取任何真实标定数据。

## 2026-10-16 开环标定包已完成本地验证，待现场运行

在用户授权无须现场配合的工作持续推进后，新增独立 `audio_pl_calibrate`：两组不同种子的确定性宽带数字激励，单轮32768帧（标称0.671秒），同帧记录实际DAC参考与ADC左声道；ADC不回送DAC。输出帧数限制独立于ADC VALID。现有直通bit/hwh未改。

实际执行Vivado 2018.3线级仿真：缩小16帧实例的两个种子、引脚串行输出与参考一致性、ADC已知字、固定帧停止、手动停止、复位，以及无ADC VALID时输出仍停止，返回 `AUDIO_CALIBRATE_PASS`。完整32768帧工程综合实现与比特流生成完成：DRC 0，LUT1070、FF2158、RAMB36E1 48、DSP0，WNS1.333ns、WHS0.044ns。仍有1个音频输入和3个输出缺I/O延迟约束，不称板级时序签核。匹配文件、脚本及SHA256清单位于 `board/audio_calibrate/`；**未上传或上板播放**。

新增离线开环路径拟合、独立数据评价、24位/20小数位系数量化与因果FIR整数参考，接口见 [标定v1](../contracts/feedback-calibration-v1.md)。13项软件测试实际通过，包含数据条件拒绝、已知路径恢复、错误路径、定点边界、模拟板卡正常及恢复失败分支。命令行合成数据演示的独立预测误差降低44.055dB，仅是合成开环数据的软件结果，不是ASG、实物测量或反馈抑制成功。证据在 `report/verification/audio_calibrate/`。

耳机试验脚本本地上限由0.75秒改为3秒，默认仍0.5秒，低于既有PL约5秒后备停止；语法检查通过，尚未上传或运行长窗口。当前需要现场的下一步是 [开环采集操作单](../../board/audio_calibrate/README.md)：耳机摘下、音响接回固定箱体、停止外部声源，确认随手断电和短时PCM仅存板卡后，按种子0/1分别手动执行两次采集。没有真实路径数据前，不生成“箱体抵消系数”或宣布抑制效果。

## 2026-10-16 基础实时直通确认，结束有无信号排查

用户按上一轮耳机直通步骤反馈“有短促纯音”，并补充后来测试人声“也是有声音的”，但指出 0.75 秒窗口太短，人声变化难以辨认、听起来像噪音。结合静音连续采样的约 1 kHz 响应，将当前状态更新为：**自定义 ADC→PL→DAC 基础实时通路已获现场可听验证；语音清晰度、失真、延迟及持续运行稳定性尚未量化验收。**本轮为用户反馈，未提供新的完整运行输出，不补写其恢复标记或运行参数实测值。

纠正先前判断：0.75 秒适合首次限时试音，不足以作为否定语音直通的可靠听辨条件；“像沙沙声”不能据此归因为 I²S 或 Codec 故障。停止反复做有无信号排查及无证据的时序修改，保留现有通路作为基线。后续先准备约 3 秒的耳机语音验收窗口（当前脚本上限 0.75 秒，需先修改并检查；PL 已有约 5 秒帧数停止后备），同步推进开环反馈路径测量与算法参考模型。音响闭环的限时保护和增益标定另行处理，不直接沿用耳机测试条件。反馈抑制尚未实现或验证。

## 2026-10-16 用户反馈停播 / 正弦音连续采样对照

用户手动执行后粘贴统计：停播左右 RMS −29.86/−29.91 dBFS、峰值 −16.21/−16.19 dBFS、左声道主频格点 882.1 Hz；正弦音左右 RMS −22.74/−22.73 dBFS、峰值 −12.83/−12.80 dBFS、左声道主频格点 1001.4 Hz。两次均为 4096 帧，`dac_muted=True`，并打印 `PL_CONTROL_MUTED True`。RMS 分别增加 7.12/7.18 dB；这是总电平差，不是严格 SNR。若手机设置为此前要求的约 1 kHz 正弦音，此频率响应支持自定义 ADC 捕获到了外部声源；仍不能据此认定完整波形无失真或实时直通成功。停播的 882.1 Hz 只是搜索频段最大格点，不能视为啸叫证据。

本轮粘贴内容没有 `STOCK_BASE_RESTORED` / `STOCK_PLL_READBACK`，因此两次运行的恢复结果尚待核实，不将上一轮恢复成功套用于本轮。下一项在恢复标记确认后，使用同一手机纯音、箱外耳机及既有 `bounded_mic_trial` 做 0.75 秒、hp_volume=40、shift=0 的开环直通；先确认测试音能否贯穿完整链路，再回到人声。此为待执行步骤，未远程触发播放。

## 2026-10-16 静音连续 ADC 捕获上板完成

经用户同意，将匹配的 `audio_capture.bit/.hwh` 和 `muted_frame_capture.py` 上传到板卡 Jupyter 的 `base/audio/audio_capture/`，在独立 Notebook `muted_capture_2026-10-16.ipynb` 执行一次 `capture_stats('ambient')`。板上输出：4096 帧，`dac_muted=True`，左右去直流 RMS −32.53/−32.51 dBFS，峰值 −18.89/−18.82 dBFS，左声道 100–5000 Hz 最大 FFT 栅格为 393.4 Hz；结束输出 `PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`，内核返回空闲。脚本没有保存原始 PCM；音频输出全程保持静音。浏览器中已保存 Notebook。

这次没有现场核实箱外声源和环境状态，所以标签为 ambient，不能称安静底噪；单个最大 FFT 栅格也不能认定为真实 393.4 Hz 声源。连续样本及电平证明新的板上捕获和读回通路工作，但仍未证明采样位序无误、语音可辨或自定义实时直通成功。下一项应在**同一布置、输出继续静音**下，分别采固定频率已知音调和停止音调的对照，用频谱/电平差判断自定义 ADC 数据是否连贯；再决定修 I²S 接收时序还是 Codec/输出配置。接口与恢复方式见 [静音连续采样诊断 v1](../contracts/frozen/audio-capture-v1.md)。

## 2026-10-16 官方录播同条件对照通过

用户在箱内音响音频插头拔下、箱外耳机监听、手机人声保持原声源条件下，运行[官方录播对照代码](experiments/2026-10-15-stock-reference.md)。板上输出 `RECORDED_SECONDS 3 FRAMES 144000` 和 `PLAYBACK_DONE_AND_CODEC_MUTED`；用户听感为“有点底噪的清晰人声”。这证明同一套 MAX4466→LINE_IN 输入经官方 `base.bit` 录播，在这次条件下有可辨人声；录播不是实时直通，也没有保存 WAV。结合自定义 PL 耳机直通只听到沙沙声，下一项应聚焦自定义 PL 收发数据、Codec 在自定义时钟下的配置与串口时序，而非继续提高音量或先做闭环啸叫。用户反馈和软件输出分别记录，音质没有做客观测量。

为缩小故障范围，新增逐帧变化 I²S 仿真，Vivado 2018.3 返回 `I2S_DYNAMIC_PASS: 24 changing channel words checked`；这证明理想时序下收发位序及一帧延迟在测试覆盖范围内正确，不能替代板上波形。另建独立静音连续 ADC 捕获版本：`audio_pl_capture` 在片上 RAM 缓存 4096 帧，板上脚本只输出统计、不保存 PCM。缩小为 16 帧的行为仿真返回 `AUDIO_CAPTURE_PASS`；完整工程综合/实现并生成匹配 bit/hwh，DRC 0，当前不完整外部音频 I/O 约束下 WNS 3.423 ns、WHS 0.034 ns，综合映射 5 个 RAMB36E1 和 1 个 RAMB18E1。接口见 [静音连续采样诊断 v1](../contracts/frozen/audio-capture-v1.md)。上板结果见本页上一节；这些离线数据仍不能代替板级 I/O 时序签核。

## 2026-10-15 耳机对照与早期啸叫结果补记

现场用户按[手动诊断单](experiments/2026-10-15-headphone-check.md)运行官方 `stock_tone(volume=40, amplitude_dbfs=-18)`，反馈耳机听到清晰三声。`%run audio_probe/bounded_mic_trial.py` 无文字结果符合脚本仅定义函数的行为。随后运行 `bounded_mic_trial(headphones_confirmed=True, seconds=0.75, shift=0, hp_volume=40)`，用户反馈只听到“电流斯拉的声音”，没有报告可辨人声；随后补充完整打印输出：音量 40（标称 −17 dB）、右移 0，实测 0.751 秒、36693 帧、`muted_at_end=True`、`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。与音量 30 的“完全无声”相比，音量 40 有可闻异常声，但**自定义 ADC→PL→DAC 的有效语音直通仍未通过**。不要继续仅靠增加音量判断；先用同条件官方 base 短录短播确认麦克风输入是否有可辨人声，再决定查输入信噪比还是 PL 连续样本的位对齐、时序和路由。

用户本轮明确追认早期已有代码在箱内麦克风与音响形成“尖锐啸叫通路”，并进一步确认正是官方 `pAudio.select_line_in(); pAudio.set_volume(40); pAudio.bypass(seconds=10)`、音响接回箱内时发生。早先粘贴的 Notebook 文本含这段代码及“本次结束”，但缺少当时完整接线、运行期间信号和原始音频证据。因此把“官方 bypass 在该箱体和音量下产生尖锐啸叫”记为**用户现场反馈**，不抹掉该成果，也不推定它来自自定义 PL。这证明该套条件可形成声学反馈，不证明自定义 PL 直通或反馈抑制算法成功。

## 2026-10-15 固定手机声源的静音 ADC 对照

现场后续步骤先整理为[耳机直通手动诊断单](experiments/2026-10-15-headphone-check.md)，已收到听感反馈；下一项[官方录播对照](experiments/2026-10-15-stock-reference.md)已备好代码，尚未执行。

在用户确认箱盖和麦克风位置不变、箱外手机停止播放后，板上独立 Notebook 复用既有 `probe_level('quiet', seconds=2.0)`：约 2900 次非均匀寄存器快照、97685 帧，左右去直流 RMS −35.72/−35.69 dBFS。随后用户在箱外固定位置以普通音量循环播放人声，运行 `probe_level('speech', seconds=2.0)`：2888 次快照、97680 帧，左右去直流 RMS −30.74/−30.72 dBFS，分别比无声源基线高约 4.98/4.97 dB。两次输出均保持静音，结束打印 `STOCK_BASE_RESTORED` 和原 PLL `0271023c2103`；未保存录音。峰值快照与窗口时间不能用作严格实时峰值保证，两个 RMS 只支持同条件粗略电平对照，不证明语音清晰度。固定手机声源确实使 ADC 样本电平上升；下一步优先改用箱外佩戴的耳机验证 ADC→PL→DAC 直通，避免音响在箱内形成声学反馈。

用户确认已拔下音响音频插头、改用箱外耳机，并同意将 `board/audio_probe/bounded_mic_trial.py` 上传到板卡 `base/audio/audio_probe/`。脚本已做 Python 语法检查，上传后在 Notebook 先用 `%run` 仅定义函数，打印签名 `MIC_TRIAL_READY (headphones_confirmed=False, seconds=0.5, shift=0, hp_volume=30)`，没有自动播放。用户再次确认手机固定人声已开始、耳机佩戴且可随手摘下后，执行 `bounded_mic_trial(headphones_confirmed=True, seconds=0.5, shift=0, hp_volume=30)`。板上返回计划 0.5 秒、实测 0.501 秒、24476 帧、`muted_at_end=True`、`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。用户当时不在现场，因此这一轮没有有效听感。按用户要求在其重新确认就位后，以同一音量重测 0.75 秒，板上返回实测 0.751 秒、36693 帧、静音及官方 base/原 PLL 恢复；**用户明确反馈耳机完全无声**。这未证明 ADC→PL→DAC 有声直通。音量参数 30 标称约 −27 dB，手机人声的 ADC 快照 RMS 约 −31 dBFS，两者叠加说明输出可能很弱，但不是经 DAC/耳机测得的电平，不能单凭这一点排除路由或数据格式问题。脚本时间上限 0.75 秒，PL 路径另有约五秒帧数停止后备；不得在音响重新接回箱内后照此脚本开闭环。

## 2026-10-15 官方播放可听阈值与 PL 音调隔离测试

为排除实时讲话与扬声器输出重叠导致“听不出来”的可能，在官方 `base.bit` 下、关闭 Codec 输入混音，用 `board/audio_bringup/known_tone_notebook.py` 对应代码生成三段各 250 ms、约 1 kHz 的双声道测试音。第一轮波形峰值 529285（24 位满幅约 -24 dBFS）、Codec 音量参数 45（约 -12 dB），`audio.play()` 用时 1.496 秒，脚本结束后 Codec 输出静音读回通过；**用户反馈完全未听到**。用户随后确认有源音响供电、HP+MIC 输出插头正常，箱外应能听到。只读检查板上旧 `recording_0.wav`：双声道、24 位、48 kHz、240000 帧、峰值约 -69.83 dBFS；它不能作为当前箱体可听阈值的直接标定。

第二轮仅提高已知测试音电平，波形峰值 1056063（约 -18 dBFS）、Codec 音量参数 50（约 -7 dB），`audio.play()` 用时 1.494 秒，结束静音读回通过；**用户反馈听到清晰三声**。这证明当前官方 base 的已知播放音在该设置、箱体和现场听音位置可听，不能推出自定义 PL 已有声。两轮均没有录音、没有选择麦克风输入或开启闭环。数值 -25 dBFS 是波形峰值与 Codec 标称衰减之和的近似值，不是音响端电压或声压实测。板上独立 Notebook 已保存。

为隔离此前自定义直通的 ADC 电平与声学反馈影响，新增独立 `audio_tone` 诊断版本：PL 可通过控制位 5 选择内部约 1.017 kHz、三段 250 ms 的峰值约 -18 dBFS 方波，沿用默认静音、约 5 秒帧数硬停止及输出计数。Vivado 2018.3 行为仿真输出 `AUDIO_TONE_PASS`；综合、实现及 bitstream 生成完成，实现 DRC 0 违规，当前不完整外部音频 I/O 约束下 WNS 3.648 ns、WHS 0.030 ns。匹配的 bit/hwh 和脚本经用户同意上传至板卡 `base/audio/audio_tone/`。执行 `%run audio_tone/bounded_tone.py`，得到 1.502 秒内 73364 帧，其中 36621 帧非零；脚本打印 `PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。**用户反馈这一组自定义 PL 三声很响**，与之前官方 base 的另一组三声是两个独立测试。由此，已证实当前配置下自定义 PL 能驱动 Codec 和音响发出可听已知音调；没有证明 ADC→PL→DAC 的连续麦克风直通或反馈抑制。方波比同峰值正弦波 RMS 高约 3 dB，且谐波不同，不能把“很响”定量等同于声压对比。板上独立 Notebook 已保存，接口和恢复方式见 [音调诊断接口](../contracts/frozen/audio-tone-v1.md)。

## 2026-10-15 数字输出静音诊断版本（已上板）

针对两次自定义直通均未听到声音，新增独立 `audio_diag` 版本，不覆盖既有 `audio_probe`。诊断控制位 4 在内部音频帧通路运行时把物理 `sdata_o` 脚强制为 0，并提供“处理后非零帧数”和“串行器内部 1 位边沿数”两个计数器。Vivado 2018.3 行为仿真通过，包括诊断模式下计数器增长和物理输出持续静音；综合与实现完成，DRC 0 违规，当前不完整外部 I/O 约束下 WNS 3.456 ns、WHS 0.034 ns。生成匹配的 `board/audio_diag/audio_diag.bit/.hwh`，板上静音检查脚本已做 Python 语法检查。经用户明确同意，三个匹配文件上传至板卡 `base/audio/audio_diag/`，在独立 Notebook 执行 `%run audio_diag/muted_tx_diag.py`。约 1 秒内帧计数增加 48890，内部处理输出非零帧数增加 48884，串行器内部 1 位边沿数增加 1181037；控制读回静音，结束输出 `PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`，Notebook 已保存。`physical_sdata_forced_low=True` 和 `codec_output_muted=True` 是脚本根据所用 RTL 控制模式及配置写入打印的状态，**不是对物理引脚或实际声压的独立测量**。计数非零说明 PL 内部处理与串行器有活动，不能证明 DAC、音响有声或抑制啸叫。接口与恢复方式见 [诊断接口](../contracts/frozen/audio-diag-v1.md)。

## 2026-10-15 静音 ADC 采样探针（已上板读取）

新增独立 `audio_probe` 版本，在既有 I2S 接收器后锁存最近一帧的 24 位左右声道值，并通过第二个 AXI GPIO 供 PS 读取；输出控制仍默认为 0。旧 `board/audio_bringup` 的已验证 bit/hwh 未修改。接口和限制见 [探针说明](../contracts/frozen/audio-probe-v1.md)。

Vivado 2018.3 已运行 `test_audio_probe.tcl`，仿真在 ADC 数据相对 BCLK 下降沿延迟 50 ns 的条件下，左右声道带符号样本检查及静音检查通过。独立工程已综合和实现，生成匹配的 `board/audio_probe/audio_probe.bit/.hwh`；实现 DRC 0 违规，现有约束下 WNS 3.738 ns、WHS 0.041 ns。该报告没有解决前述外部音频时序模型疑点。HWH 实际分配控制 GPIO `0x41200000`、采样 GPIO `0x41210000`。

经用户明确同意，把 `.bit/.hwh` 与 `muted_adc_probe.py` 上传至板卡 `base/audio/audio_probe/`，在独立测试 Notebook 中运行 `%run audio_probe/muted_adc_probe.py`。板上返回 `muted=True`、PLL 锁定 `000000002803`；约 1 秒内帧计数增加 49645，左右各 100 次低速寄存器读取均为不同值：左最小/最大 -1195108/566817，右 -1255360/522985。结束返回 `STOCK_BASE_RESTORED` 与原 PLL `0271023c2103`，Notebook 已保存。此结果证明自定义 PL 的 ADC 数据寄存器有持续变化，不能仅凭这些统计确认声学输入频响、样本无误码或有声直通；采样寄存器是快照，不是连续录音。

随后用户现场配合安静/讲话，沿用同一自定义探针、静音输出与 Codec 配置，在板上 Notebook 定义 `probe_level` 连续读取最近样本（函数来源 `board/audio_probe/level_probe_notebook.py`，板上为粘贴的等价代码）。每段约 2 秒：安静段 2897 次读取、帧计数增加 97689，去直流 RMS 左/右 −36.35/−36.26 dBFS；讲话段 2885 次读取、帧计数增加 97668，左/右 −32.49/−32.44 dBFS，分别增加 3.86/3.82 dB。两段均返回 `STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`，Notebook 已保存。PS 读取的是非均匀抽样的寄存器快照，数值仅用于同条件粗略对照；它不是连续 PCM 录音，也不证明声学质量、无误码或反馈抑制。此前官方录音链路的 +9.64 dB 对照不能与这里直接等同比较，采样方法和讲话时段不同。

经用户反馈音响旋钮已调到最低可听档并有人能立即断电，运行 `bounded_passthrough(2.0)` 首次自定义 PL 短时直通。板上原函数使用 PL 右移 6 位、Codec 耳机音量参数 10，先静音配置并核对 PLL/串口路由，再有限时开启。板上输出：计划 2.0 秒、函数测得 2.002 秒、帧计数增加 97766、`muted_at_end=True`、`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。Notebook 已保存。**用户明确反馈现场未听到声音。**依据 ADAU1761 Rev. F 的耳机音量表，参数 10 对应约 −47 dB，PL 右移 6 位约 −36 dB，合计约 −83 dB；这足以解释无声现象，但还不是输出链路正常的实测证明。`board/audio_probe/bounded_passthrough_notebook.py` 已在本地修订为可配置音量/右移量；板上 Notebook 中也已成功定义新函数 `bounded_passthrough(seconds=2.0, shift=4, hp_volume=57)` 并保存，但**新参数尚未触发音频测试**。用户澄清音响没有外部音量旋钮。第一轮拟保持 PL 右移 6 位、Codec 耳机音量参数 30（约 −27 dB），总数字衰减约 −63 dB，比首次测试提升约 20 dB；现场须可断电，并用箱外固定循环声源避免人员持续讲话。后续增益按实测听感逐级调整。Codec 依据：[ADAU1761 Rev. F 数据手册](https://www.analog.com/media/en/technical-documentation/data-sheets/ADAU1761.pdf)。目前仅能认定软件与 PL 控制按时返回和恢复，**不能称“有声直通成功”或“啸叫已抑制”**。PL 自身有约 5 秒帧数上限作为软件卡住时的后备停止；没有独立墙钟看门狗。

现场澄清：麦克风在关盖的箱体内；此前让用户“距麦克风 20 cm 讲话”与实际布置不符。后续声源应放在箱外并固定位置，代码和检查须在提示用户开始声源前完成，避免浪费现场配合时间。

第二轮现场使用关盖箱外固定循环播放的手机人声，因有源音响无音量旋钮，执行明确参数 `bounded_passthrough(2.0, shift=6, hp_volume=30)`（PL 约 −36 dB、Codec 约 −27 dB，总约 −63 dB）。板上输出：`hp_volume=30`、`hp_db=-27`、`pl_shift=6`、计划 2.0 秒、实测 2.003 秒、帧计数增加 97786、`muted_at_end=True`、`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`；Notebook 已保存。**用户再次反馈完全没有听到声音。**这仍不能把原因归结于 PL 输出故障：按前次讲话 ADC 约 −32 dBFS 粗估，−63 dB 数字衰减后输出约 −95 dBFS，且箱外手机到箱内麦克风的电平本轮未测。不会继续盲目增加输出。结束后只读读取官方配置下的 Codec 寄存器：R0=0f，输入混音 0x400a/0x400c=00、输入增益 0x400b/0x400d=07，输出混音 0x401c/0x401e=00、耳机 0x4023/0x4024=e5，播放电源 0x4029=03、DAC 0x402a=03，串口路由 0x40f2/0x40f3=01，DSP 0x40f5/0x40f6=01，时钟 0x40f9/0x40fa=7f/03。这是恢复后的状态，不证明短时开启期间各寄存器值。PL 内部处理输出数字非零现已由后续静音诊断证实。下一步应测固定声源进入 ADC 的实际电平，另用官方播放链路标定无实体旋钮音响的可听阈值，再做可比条件下的自定义有声直通。

## 2026-10-15 Codec 时钟与音频 I/O 时序复核

在已恢复官方 base 的板卡上，只读读取到 ADAU1761 R0=`0f`、R1 PLL=`0271023c2103`、串口控制 R15/R16=`00/00`、串口输入/输出路由 R58/R59=`01/01`。板上 `AudioADAU1761.configure()` 源码与官方驱动一致，实际配置为 10 MHz MCLK 经 PLL 得 49.152 MHz，即 48 kHz 基准；而当前 PL 的 100 MHz/2048=48,828.125 Hz。两者约差 1.73%，不能直接把静音计数通过当作有声通路就绪。

在同一独立 Notebook 中执行了仅静音的临时时钟验证：先关闭 Codec 播放混音与耳机输出，加载自定义 overlay，保持 PL GPIO 控制位 0；将 Codec PLL 切到 10 MHz×5=50 MHz（对应 48,828.125 Hz），2 秒限时内读回锁定 `000000002803` 且 `mute=True`。`finally` 恢复官方 `base.bit`，再次读回原 PLL `0271023c2103`。没有录音、播放或啸叫实验。源码见 `board/audio_bringup/codec_clock_smoke.py`，其内容直接粘贴到板卡 Notebook 执行，未作为独立文件上传；截图见 `report/verification/audio_bringup/codec_clock_probe_board.png`、`codec_clock_smoke_board.png`。

依据 ADAU1761 Rev. F Table 7，使用 Vivado 2018.3 对既有已实现网表临时施加 BCLK/LRCLK 生成时钟与外部数据延迟模型；`check_timing` 不再报未约束音频输入/输出，但报告出现 ADC 输入到首级同步器 setup -54.883 ns、LRCLK 输出 hold -7.003 ns。首项涉及连续采样的同步器，不可简单按普通同步输入路径判失败；第二项的实际相位与 PCB 偏斜还须确认。将仿真 ADC 数据延迟设为数据手册最大 50 ns 后，12 字线级仿真仍输出 `I2S_PATH_PASS`。**临时约束未写入构建 XDC，也未重建 bitstream，板级时序未签核。**有声直通仍待 ADC 数据与时序问题解决后再做。详细依据和判读见 [时钟及 I/O 记录](../../report/ai-records/2026-10-15-clock-timing-review.md)。

## 2026-10-15 自定义 PL 静音上板检查

经用户明确授权，将匹配的 `audio_bringup.bit`、`audio_bringup.hwh` 和 `muted_smoke.py` 上传至板卡 Jupyter 的 `base/audio/`。在独立 Notebook 中仅执行 `%run muted_smoke.py`，没有执行旧 Notebook 的录放/旁路单元，也没有开启自定义音频输出。实际返回 `mute=True`，帧计数在 0.25 秒内从 2202 增至 14427（增加 12225），`counter_advanced=True`，随后输出 `STOCK_BASE_RESTORED`；内核回到空闲。Notebook 保存在板卡 `base/audio/audio_bringup_muted_smoke_2026-10-15.ipynb`，截图见 `report/verification/audio_bringup/muted_smoke_board.png`。

这证明自定义 bit/hwh 能加载、GPIO 静音控制可读回、PL 帧事件计数可运行，并已报告恢复官方 base。计数由 PL 自身产生的时钟驱动，**不证明 ADC 输入、DAC 输出、有声直通、真实采样率或啸叫抑制**。旧 Notebook 中的 `pAudio` 对象在重载 PL 后不可复用。下一项为修订外部 I/O 时序约束和板级时钟/Codec 初始化核对，再做低音量、限时的有声通路测试。

## 2026-10-15 最小 PL 音频通路离线构建

用户提供 Vivado 2018.3 并授权继续。以官方 PYNQ v2.4 PYNQ-Z2 base 工程（脚本声明 2018.3）与 audio_codec_ctrl 的 I2S 收发源码为参考，新增自定义 24 位双声道 PL 通路：算术右移衰减、默认静音、有限帧数停止、帧停滞静音及帧计数。它尚无 FIR 或声反馈抑制。源码、接口、Vivado Tcl、XDC、仿真和匹配的 bit/hwh 见 `src/rtl/`、`docs/interfaces/audio-bringup-v1.md`、`build/scripts/`、`sim/audio/`、`board/audio_bringup/`。

实际运行 Vivado 2018.3：核心仿真与 I2S 集成仿真通过；工程生成、综合、布局布线及比特流生成完成；实现 DRC 0 违规，内部 WNS=3.908 ns，LUT 644、FF 1163、DSP 0、BRAM 0。此为最小直通版本资源，不是算法版本资源。外部音频输入 1 个、输出 3 个端口缺完整 I/O 延迟约束，不能称板级时序签核。板卡预设引出 DDR DQS 负延迟警告，官方 v2.4 base 脚本部分数值不同；后续有声测试前需核对。`board/audio_bringup/muted_smoke.py` 已用于上方静音检查；音响测试未做，结束时脚本报告已恢复官方 base。详细证据见 [记录](../../report/ai-records/2026-10-15-pl-bringup.md)。

另核对官方旧 `user_logic.vhd` 的分频：100 MHz/2048=48828.125 Hz；此前 WAV 标头 48000 Hz 不等于已证明实际 I2S 帧率。录音 240000 帧实际调用耗时约 4.93–4.95 秒与此相符，但仍需上板测定新旧工程时钟。

## Vivado 板卡定义安装验证（2026-10-14）

确认本机 `D:/Xilinx/Vivado/2018.3` 为 Vivado 2018.3，已安装 Zynq 器件 `xc7z020clg400-1` 支持。原默认 board_files 目录没有 PYNQ-Z2；本轮新增 `pynq-z2/A.0` 的板卡 XML、PS preset、引脚映射和图片。安装后新启动的 Vivado 无需设置额外 repoPaths，即识别 `tul.com.tw:pynq-z2:part0:1.0`，内存工程设置板卡与器件成功，输出 BOARD_SETUP_PASS。

这只证明板卡定义识别和工程创建可用，未综合、实现或上板，也未证明 PYNQ 3.1.1 base 源码可用 2018.3 重建。下一步核对音频参考工程及 IP 版本。来源、校验值与恢复方式见 [安装记录](../../report/ai-records/2026-10-14-vivado-board-setup.md)。

## 配置 A 讲话对照（2026-10-14）

用户准备讲话并报告距离约 20 cm。保持关盖、音响断电及同一音频初始化，复用 capture_config_a 完成 5 秒讲话采集；无播放、bypass 或 overlay 重载。文件为板上 `base/audio/shengdi_captures/configA_speech_fe2476a2.wav`，同名 JSON 记录条件和指标，`.comparison.json` 关联背景样本 `configA_quiet_838de378.wav`。48 kHz、24 位、双声道、240000 帧；record 耗时 4.9257 秒。

通道 0/1 去直流 RMS 为 -26.5105/-26.4873 dBFS，峰值 -8.7669/-8.7430 dBFS，近满幅比例均为 0。相对上一段背景的去直流 RMS 差为 +9.6403/+9.6416 dB。这是两段录音的电平差，不是严格 SNR；未听辨、未测声学频响，不证明清晰度或反馈抑制性能。采集结束关闭输入，Notebook 已点击保存。当前可以保留输入增益推进连续通路，后续需听辨和检查背景噪声来源；原始 WAV 仍仅保留板上。

## 配置 A 关盖背景采集（2026-10-14）

用户确认约 17×17×7 cm 箱体已固定、箱盖关闭、音响断电。远程执行先发现新内核无 pAudio，断言失败且未采集；失败输出保留。随后重新加载 base.bit、创建音频对象，选择 LINE_IN 完成 5 秒录音，finally 关闭输入，没有播放或 bypass。

板上文件：`base/audio/shengdi_captures/configA_quiet_838de378.wav` 和同名 JSON。48 kHz、24 位、双声道、240000 帧，record 耗时 4.9503 秒；通道 0/1 峰值 -17.321/-17.296 dBFS，去直流 RMS -36.151/-36.129 dBFS，近满幅比例均为 0。安静标签来自实验指令，尚未听辨或频谱诊断，不能把全部能量归因于电路底噪。讲话样本待采集，增益和摆位保持不变后比较。Notebook 已点击保存；未提交或推送。

## 2026-10-14 远程录音实测

用户登录 Jupyter 后，AI 通过浏览器在原 audio_playback.ipynb 末尾追加检查与录音单元，实际完成一次 LINE_IN 5 秒采集。原 Notebook 已通过 Make a Copy 备份为 audio_playback-Copy1.ipynb。本次未播放、未运行 bypass、未重新加载 overlay。

板上驱动检查返回 AudioADAU1761、48000 Hz；WAV 回读为双声道 24 位、240000 帧（5 秒），record 调用耗时约 4.932 秒。通道 0/1 峰值为 -18.638/-18.601 dBFS，RMS 为 -35.627/-35.603 dBFS；近满幅比例均为 0，非零比例均为 1。这证明远程采集与分析链路可用，不能证明人声质量、连续实时处理或反馈抑制成功。

WAV 与 JSON 留在板卡 `/home/xilinx/jupyter_notebooks/base/audio/shengdi_captures/linein_20250504_011108_1f7571bf.*`。板卡时钟明显不正确，文件名日期不能作为实验日期。录音结束执行了 deselect_inputs；原始音频没有上传仓库。下一步固定接线与增益，分别采集安静/讲话样本，再进行现场有人看守的低音量限时直通。详见 [远程采集记录](../../report/ai-records/2026-10-14-remote-capture.md)。

## 2026-10-14 审阅与下一项任务

用户再次确认环境、麦克风和音响测试可用，可准备声反馈实验。本轮未连接板卡，也未收到新的Notebook、WAV或连续直通结果；不能追加“啸叫已复现”或“PL直通通过”。本地src/、board/、sim/、build/、data/仍只有说明文件。

下一项为[限时直通与声反馈预实验](experiments/preflight-plan.md)：先导出成功Notebook及本机驱动信息，再由现场单一操作者低音量短时测试。公开AudioADAU1761的bypass实现经PS端C轮询搬运，不是纯PL直通；实际板上版本待核对。允许先用它验证声学闭环，正式算法对照仍需同一条自定义通路。文中的测试步骤与新排期均为建议，未执行上板验证。

以下保留10月11日状态与证据。

更新：2026-10-11。来源为用户实验反馈和已有记录；本次整理没有运行硬件测试。

## 已完成与证据边界

- PYNQ-Z2 已启动并能使用 Jupyter；系统 PYNQ 3.1.1，驱动 AudioADAU1761，I2C 编号 1。
- recording_0.wav 可从 HP+MIC 输出，由耳机或有源音响播放。先前音响静音曾由音量旋钮归零导致。
- 原四段耳麦直插 HP+MIC，选择 microphone 后可录到人声，本轮再次确认。
- MAX4466 接 LINE_IN 可以录音；实际供电、增益、声道、接线照片和新录音文件尚待补齐。
- 两只新三段领夹麦：直插 LINE_IN、直插 HP+MIC、通过新四段总头/两三段分孔转接线接 HP+MIC 均反馈静音。转接时输出分孔空置；用户确认选择了 microphone。
- 原四段耳麦插入新转接线的三段麦克风孔也无法录音。

静音是用户听感描述，本轮未对原始 PCM 做数值确认。实验矩阵及分析见 [排查记录](experiments/2026-10-audio-debug.md)。触点、偏置负载和附件识别仍是猜想，不能认定板卡或麦克风损坏。

## 当前路线与待办

主线为 MAX4466 → LINE_IN，HP+MIC 的耳机输出接有源音响。备用三段麦问题不阻塞主线。基础录放成功不代表自定义 PL 直通或啸叫抑制已完成。

| 顺序 | 工作 | 完成证据 |
|---|---|---|
| 1 | 导出当前可用的板上 Notebook，记录实际接线 | board/ 有程序，docs/ 有供电、接线、输入选择 |
| 2 | 固定录放条件并保存样本 | data/ 有安静/讲话样本和采样参数、增益、距离 |
| 3 | 自定义 PL 连续直通 | 工程可重建，静音可控，计数和延迟有实测 |
| 4 | 开环标定和离线验证 | 同步输入/输出参考、独立验证数据与误差 |
| 5 | 固定系数抵消及对照 | 同一位置和条件的开启/关闭结果 |

尚无自定义 RTL/HLS、工程脚本、仿真结果、综合报告或抑制增益的完成证据。10 月 4 日倒排表保留作历史计划，不随时间经过自动标记完成。

## 网络与资料整理

目前电脑 192.168.2.1/24 直连板卡 192.168.2.99，Jupyter 端口 9090。已提出 USB 网卡连板卡、原网卡接校园网的方案，尚未确认购买或配置。板卡专用网卡不填默认网关/DNS，校园网按校方配置，并避免子网重叠。

本轮将实验归入 docs/experiments/，硬件分析归入 docs/hardware/，原始 PDF 归入 references/，早期 AI 草案归入 docs/archive/。tmp/ 留在本地且不上传。远端目标为 cu616/ShengDi_PYNQ_Feedback_Suppression，要求 private。

## 团队 AI 开发约定（2026-10-11）

新增 [AI 开发规范 v0.1](../rules/ai-development-policy.md)、根目录 AGENTS.md，以及任务、接口和协作记录模板。各人的 AI 开工前读取当前项目状态；多人通过独立目录和任务分支协作，按实际验证层次报告完成情况。关键交互保存在 report/ai-records/，完整历史对话仍待导入。本次只整理开发约定，不代表新增了算法或上板验证结果，也未配置 GitHub 分支保护。
