## 2026-11-03 队长接手高频复算并修复只读脚本

- 同步B提交1e368e7，按打印精度复核A表：六行均不自洽；纠正相位/延迟、+1 dB乘法和陷波环路解释，未选择任一列作为实测真值。
- 脚本改为双SHA绑定、训练验证分开、开环与单位检查、不平移PCM、同网格复数导出；6项软件测试通过。没有操板、没有修改产品算法或RTL。
- 本地180个模型/候选JSON未命中目标；交付一次板上已有数据只读计算入口，派生JSON不含PCM。依据与入口：[独立复算](../../report/verification/highfreq-fix-2026-11-03/README.md)。

## 2026-11-03 C 交付41文件BTN2恢复包

- 新包配置逐项核验：4596/60秒，三档attempt及训练captures均4，验证2；含runtime在内的所有非prepare白名单[0,4596]，prepare保留历史档并加入4596。B原件为2026-11-02.1，A9件/驱动/位流未改。
- 仅3个指定单测通过；41文件全部SHA、manifest SHA及包内--check(identity_ok/deployment_ready=true、missing=[])通过。包内说明含BTN2免标定恢复上限3次/场景，状态与回包带两字段。
- ZIP和SHA已复制到原仓库根目录，用户Word未动；新源码在独立main副本提交。完整包名/两项SHA/冻结源/配置见[交付核验](../../report/verification/recal-product-v1/resume3-package-check.json)。未操板，A按既定验收执行；不把旧候选60秒实测冒称新包已通过。

## 2026-11-03 C 实现BTN2保护恢复（产品接口文档修订v2）

- 按用户明确语义：仅protected可短按BTN2回ready，BTN1再扩声，同scene最多3次；复核模型SHA、静音/硬件收尾和锁存，重新提交既有启动资格，不拟合/装载。状态与回包带resume_count/resumed_from，新CAL重置；其他失败保持原流程。
- 只新增正常/哈希错误/超3次三个[单测](../../report/verification/recal-product-v1/resume3-software.json)，全部通过；当前4596/60秒/4训练基线及main算法原件随包冻结，阶段白名单另核。文档修订v2、wire仍v1，不改A/驱动/RTL/算法。
- 原工作区Word未提交修改导致快进被保护性拒绝；C新建干净main副本继续，未stash/覆盖该Word，未操板。

## 2026-11-02 A 复盘提交：早上的扩声效果无法复现，路径实测强 4.7 dB

- 今日做了 6 次包改动（60 秒、判据代改、6→4 段、+1.0 dB）与约 40 次真板运行；功能目标均达成，但早上的 +3.0 dB 演示无法复现。
- 单音直接测量（与训练采集同口径）显示 405 Hz 处 |H| = 1.14~1.29（早上模型为 0.667，差约 4.7 dB）、8.4 kHz 处 1.12；跨软重启、断电重上电、重插线、换包、重标定均稳定复现。数字链路健康（bit_exact、哈希一致），模型元数据与早上一致。
- 已排除：板子过劳、线缆接触、充电头。未解释：路径变化本身、8.4 kHz 峰时有时无、产品偶发卡死（do_select，重启服务恢复）。
- 当前安全工作点 +1.0 dB（抵消 20 秒稳两次、同增益旁路啸叫）；临时包 42da66b5 已装板。
- 全过程与下一步建议：[给队长的复盘报告](../../report/verification/audio-replay/demo-protocol-2026-11-02/lead-report.md)。
## 2026-11-03 队长改写系统框图说明

- 将“实际播放字”说明改为“以实际输出音频为参考，估计音箱回传至麦克风的反馈声”；调整控制线避开文字，同步 SVG、PNG、生成器和报告 Word/PDF。
- 报告仍为 14 页，仅第 4 页图形变化。入口：[图源说明](../../materials/work/report/README.md)。

## 2026-11-03 队长修订报告关键词与创新点

- 按用户意见移除泛化的 FPGA 关键词，将创新点改为确定时序逐帧抵消、25 位宽残差及模型更新无需重构位流的软硬件分工；同步 Word/PDF。
- 重新导出 14 页 PDF，像素比对仅第 1、3 页变化，已查看两页；其余页面与已检查稿一致。未改工程代码。
- 协作入口：[报告正文与说明](../../materials/work/report/README.md)。

## 2026-11-03 队长完成官方模板报告审阅稿

- 依据 main 87ff28c 的代码与现场记录整理官方五部分技术报告，生成 Word/PDF 及六张 SVG/PNG，保留模板页眉、页码与章节格式。
- PDF 共 14 页，逐页渲染检查；三张实物照片按用户反馈留待拍摄，最新判据的整机验证与历史结果分开表述。未改工程代码、未操板。
- 交付与再生成入口：[报告说明](../../materials/work/report/README.md)。

## 2026-11-02 A 真板跑通演示链路并代实施判据变更

- 真板完整链路首次走通：冷启动不写 AUX 进待标定；CAL alid_pass（L1 2.170、峰位 126 = 实测延迟 126、300–460 Hz 带内抑制中位 +4.63 dB）；BTN1 进 running 并听到扩声；SW0 在同一运行内拨上即起振。
- 逐点二分：旁路边界 +2.1 dB（同点先稳后炸，只能报 ±0.1）、抵消边界 +5.0 稳 / +5.5 失稳，ASG 约 3.2 dB（2.9–3.4，5 秒与 20 秒两个窗口）；演示点 +3.0 dB，现场 SW0 切换后 3.49 秒被饱和保护停声。静音下 +3.0/+2.5/+2.0 dB 各跑满 60 秒（2929687 帧、零饱和），证明环路本身可稳 60 秒，60 秒失败由讲话电平推满导致。
- 按队长授权就地改包：un_seconds 8→60（重算 product-config.json 清单哈希），装到板上验证 --check 通过；包身份变为 33fad35b…，不在 C 交付链。
- 代实施 B 的判据提案（待 B 追认）：主判据改为 max|conv(h,ref)| < 0.30、L1_MAX 4.0→8.0 兜底、去掉 REJECT_SCALE 重试；算法版本升至 ecal-algorithm-2026-11-02.1。用板上真实 data 验证：原被拒的三组模型（L1 4.455/4.467/4.339，max|conv| 0.1241/0.1714/0.2301）全部 DEPLOYABLE_FIT。包 shengdi-recal-0cabfc17-0b09ef6-demo60-pred-peak-amod.zip，zip sha256 823e8787b684bf756b296007e0382eab54bd65707247e35b5f949ffe1a72bd4。
- 未验收：换电源后路径与模型匹配性；正对摆位 60 秒连续扩声的输入余量（+3.0 dB 连续讲话 8.8 秒因 input_full_scale_seen 停声）；旁路边界复现性；声压/热安全；0.9 秒按键空窗；一次 install it_exact=False 未复现。证据：[演示协议](../../report/verification/audio-replay/demo-protocol-2026-11-02/README.md)。
## 2026-11-02 C 交付最终5786/8秒演示整包

- 从已推送且干净的源码冻结ZIP，41文件及四helper身份核验、A9原件/B算法字节、包内链接均通过；check可部署、无缺项、维护自检开放。允许集准确排除6900、加入5786。
- 冻结入口在模拟I2C/MMIO/driver、真实B子进程下完成两scene：训练/验证回读0，安装/运行5786，单次8秒完成390625帧；维护安装/运行1631、3秒。导出16份非人声捕获、4模型、维护回执和算法记录，逐项SHA核对。
- c254124 §十七来源与四类未验收项在包内确认保留；未操板，不把软件流程当产品现场验收。包名/SHA/冻结源见[独立核验](../../report/verification/recal-product-v1/demo30-package-check.json)；ZIP及SHA文件仅本地根目录，不入Git，旧候选不交付。

## 2026-11-02 C 按最终确认固定5786/8秒（接口变更v11）

- 用户确认选5786/+3.0 dB，并指定A=c254124报告§十七为唯一最终参数来源；冻结器、允许集、阶段身份及运行严格单值同步，6900不在新包允许集。维护零模型仍1631/3秒，普通profile不变。
- [v11](../contracts/recal-runtime-v11.md)替代旧6900草案；包内说明原样保留四类未验收项及一次15872帧bit_exact异常，不改停声策略。区分原较长运行9.13秒拨码与产品8秒流程，起跑SW0下、运行内切换才是有效对照。
- A/B原件、helper与既有B判据未改，未操板；原件与最终授权见[冻结记录](../../report/verification/recal-product-v1/demo30-assets.json)，相关[软件检查](../../report/verification/recal-product-v1/demo30-software.json)独立记录。

## 2026-11-02 C 发现A明确撤回原演示点，暂缓ZIP交付

- 同步8b26afa后确认A已把原6900标记作废并改5786，与本轮用户人工转发要求冲突；已请求用户确认最终工作点，未自动换档，也未继续交付6900 ZIP。
- C原件、单入口、8秒时限、维护低档与46项相关软件检查可复用；旧未交付候选保留在ignored staging，根目录不留冒充最终的新ZIP。STATE仅更新C责任段；未操板、未追加A/B任务。

## 2026-11-02 C 按A新增20秒证据更正短段边界并重冻结

- 推送前同步daad1dc的时长复核，区分+4.5输入满幅与+5.5输出饱和；原5秒观察不当持续边界或确定裕量，旧ASG量级限原条件。A最新建议+4.0已记录；仍按用户本轮明示固定6900/8秒，不自动改档。
- rebase改写原冻结源后，祖先检查阻止旧来源ZIP推送；原bb71候选与SHA保存在ignored staging，核验标superseded。新冻结授权同时绑定原演示与新增时长证据，helper及A/B运行时未改。未操板。

## 2026-11-02 C 交付固定6900/8秒演示整包

- 干净源提交冻结独立ZIP，41文件/四处helper身份/包内链接核验通过；helper仍0cabfc17、A9项和B算法原字节不变，check可部署且无缺项。
- 冻结C+A、真实B子进程与模拟I2C/MMIO/driver叶子执行：实际A工厂允许6900，训练/验证回读0、安装/运行回读6900，单次请求8秒且完成帧计数390625；维护安装/运行均1631、3秒，未以零模型跑高增益。
- 两scene及导出清单逐项核验，16份非人声捕获、4模型与维护回执均保留；本次不是产品真板演示验收。包名/SHA/配置与输出见[独立核验](../../report/verification/recal-product-v1/demo45-package-check.json)，ZIP与SHA仅留根目录，不入Git。

## 2026-11-02 C 接入固定6900增益/8秒演示配置（接口变更v10）

- 按A人工转发授权固定runtime gain=6900，不放宽为允许集合任取；硬件配置允许集加入6900，阶段身份同步0/6900、准备阶段保留旧批准档，训练/验证计划不变。
- 单次START改8秒；初始化零模型的维护接口链路独立保持−8 dB/3秒并写入收据，避免维护步骤先进入高增益旁路；运行模型仍须当前CAL通过。
- [v10](../contracts/recal-runtime-v10.md)与操作单记录旁路很响/驱动饱和保护、器件长期余量未评估、0.9秒按键空窗及ASG口径。产品保护后仍需重新CAL，不照抄A直接入口的重新起跑语义。
- 相关46项[软件检查](../../report/verification/recal-product-v1/demo45-software.json)通过；A/B运行时未改、未操板。授权来源与原件见[冻结记录](../../report/verification/recal-product-v1/demo45-assets.json)。

## 2026-11-02 B 交付线迁到 main，海报改为纯文字替换

- main 从 ff1c5b3 快进到 132a5dd（落后 497 个提交）；本线只有 271361c 一个提交不在 main，按 cherry-pick 集成，不做 reset/clean。切分支前把 core-loop.html 的手动微调 stash 并另存备份，main 稳定后 pop，干净应用。
- 海报中英两版按"只改文字"重做：与 AMD 模板按几何位置逐个比对，模板 50 个形状、成品 41 个，差的 9 个全是黄色填写说明；5 张图片原位原尺寸换标注框；文字只改 `<a:t>`，段落数与模板逐段对齐（左栏四个空段原样保留，用来跳过中间的图）。
- 记一条会复现的写法：`a:latin`/`a:ea` 必须插在 `a:cs` 之前；追加到 `rPr` 末尾会被 PowerPoint 判非法并丢弃整段属性，模板继承来的白字会退回默认深色。
- 提交 0fa367b、52beaaf 已直推 main；`check_docs` 0 错误 0 警告，`poster-hush-cn.pptx` 的 blob `c5425be` 与本地备份一致。

## 2026-11-02 C 交付0cab非blocked整包

- 从干净提交冻结新包，A九项运行时和原manifest、B算法逐字节核对，四处helper钉值一致；40文件SHA与包内链接全通过，check返回identity_ok/deployment_ready=true、missing=[]，adapter-check开放。
- 冻结入口在模拟I2C/MMIO/driver叶子、真实B子进程下完成维护链路、上电AUX=0后CAL、ready中粘滞fault加BTN1、运行抵消/旁路切换、30秒实际帧计数口径结束，再次CAL新scene；不是新包真板验收。
- 单一导出回包包含2个scene、16份训练/验证原件、4份模型和维护回执，各项SHA复核，排除人声PCM。完整包名、SHA、冻结源及回包清单见[独立核验](../../report/verification/recal-product-v1/guard150-0cab-package-check.json)。ZIP和同名SHA仅放本地根目录，不入Git；A按已约定四条验收，不新增B工作。

## 2026-11-02 C 复核A新arm基线并恢复整包验收放行

- 从A=e6379ef取得0cabfc17原件，根目录/v3-io一致，九项运行时和原manifest逐字节复制；冻结器不再重放旧补丁，不改A/B源码。
- 独立执行A寄存器替身序列，新运行同一fault报告恢复；预取消不读/不改基线，五处before_start及缓存原始字标记检查通过。相关73项软件检查通过，结果见[原件复核](../../report/verification/recal-product-v1/guard150-0cab-assets.json)、[软件验证](../../report/verification/recal-product-v1/guard150-0cab-software.json)。
- v9同步原件来源和漏报修复事实；旧blocked ZIP仍阻断，只有新0cab整包恢复安装/维护检查放行，单次运行与B判据不变。约0.9秒按键空窗保留为未验收限制；未操板。

## 2026-11-02 C 冻结guard150禁止安装复核包

- 根目录生成明确标记blocked的完整review ZIP；全部40个文件及四处helper钉值独立核对，A其余运行时与B算法原字节不变，C实际产品入口正确，包内文档链接完整。
- --check返回identity_ok=true、deployment_ready=false；常驻与adapter-check均在构造硬件之前拒绝，硬件factory调用0次。安装器set -eu及首个--check的阻断顺序只做静态检查，未运行安装器。
- 空状态--export生成两项清单并逐项验SHA，明确0个scene；未冒充A现场回包。详细身份、包SHA、模型SHA及拒绝输出见[包核验](../../report/verification/recal-product-v1/guard150-package-check.json)。原始包和SHA旁文件仅留本地，不入Git。

## 2026-11-02 C 独立复现跨运行保护基线漏报，阻断候选安装

- 使用A原测试副本的真实poll函数，仅替换寄存器读取叶子，复现空闲fault→运行清零→同一fault再起却protected=false；[原始结果](../../report/verification/recal-product-v1/guard150-baseline-probe.json)保留输入序列、原件SHA与结果。
- 未把单纯放行空闲旧位当成完整修复。归一化候选增加明确blocker，关闭常驻安装与维护自检；保留此前未交付的预检产物，另组review包。v9同步写明阻断范围，不改A/B源码、不操板。
- C请求A只修新arm周期基线与原始字/缓存标记，人工转发；B无需改动。新硬件原件未到前不发可安装包，已发生的A真板成功记录保留。

## 2026-11-02 C 修正ARM计算预算与START保护记录（接口变更v9）

- 按队长通知切换并快进到 main；C 旧分支提交均在集成历史中，未覆盖任何他人工作。
- 计算预算由30秒改150秒，覆盖A实测约70秒拟合；I/O预算150、音频运行30秒，B判据不改。仅静音、无pending且硬件线程已退出的空闲粘滞位记录后接收START，活动保护和身份校验保留。
- 新增保护历史，保留命中位、阶段、request和适配器可提供的原始字；旧A缺原始字明确记null。采用A已提交补丁脚本原样重建，其结果与A报告测试副本SHA一致；没有跨线改A运行时源码。
- [v9](../contracts/recal-runtime-v9.md)明确闸门约0.9秒按键检测空窗，不把abort调用9.8ms外推为实体端到端响应。相关[70项软件检查](../../report/verification/recal-product-v1/guard150-software.json)通过；未操板、未部署。现场动作及回包见[操作单](../ref/recal-product.md)。

## 2026-11-02 队长规则变更：三线直接协作 main

- 用户明确取消日常 A/B/C 分支交付，统一各自独立克隆的 main 提交推送；角色文件边界、板卡单操作者与冲突协调保留。
- 同步 AGENTS、WORKFLOW、三线任务卡、开发规范和材料交付入口。旧分支保留历史，不删除；禁止强推、覆盖他人未提交文件或多人同时修改同一工作目录。
- 开工同步，显式提交本人文件，推送前 fetch/rebase 本人未推送提交；冲突停下协调。脏旧目录保留，建议新建干净 main 克隆，不靠 reset/clean 迁移。
- 文档检查 0 错误、0 警告；本条不改算法、保护或板卡部署。规则以 [WORKFLOW §9](../WORKFLOW.md#9-提交与拉取让人只按回车) 为准。

## 2026-11-02 队长集成 A/B/C 与入口冲突取舍

- 用户要求合并三线到 main；冲突确认时明确选择“保留 A 的旧入口，其他按建议”。
- 集成来源及当前任务统一见 [STATE](../STATE.md)。保留 B 视频方案，合同索引保留三方有效条目，状态按责任线重整；A 的旧 `recal_entry.sh` 原字节保留。
- C 的启动脚本原字节保存在 `recal_product_entry.sh`，打包仍映射成包内 `recal_entry.sh`；运行参数/协议不变。操作区别见 [产品说明](../ref/recal-product.md)。新增打包回归防止错装 A 旧脚本。
- 首次全量 506 项遇到 29 个错误，已定位其中历史 sprint 测试仍引用归档前位流路径；改读 archive 中原件，不制造占位位流，不改变算法或声学判据。复跑 506 项中 488 项直接通过，18 项为 Windows 解码/沙箱 os.replace 问题，保持断言、统一 UTF-8 并在正常权限下复跑 18/18 通过；入口定向 24/24，文档 0 错误/0 警告。详见 [本轮集成验证](../../report/verification/recal-product-v1/main-integration-2026-11-02.json)。
- 未部署、未操板；根目录旧 main 的未提交内容及原 A/B/C 工作区保持原样。

## 2026-11-02 新包 io150 离线核验　A　包自洽、pin 全对、A/B 字节未改；仍未上板

- 收到 `shengdi-recal-8799f40b-0b09ef6-io150-final.zip`（sha256
  `a91db61e40756887beee7bec88903e8f991868c81245e93017857d28b0f758b5`，373119 字节，38 个文件），
  同时 fetch 到 `origin/C` = `cdcaa56242a84a296b32daf8e8972436197fbfca`，与 C 报的一致。
- 字节核验：`product-manifest.json` 覆盖的 37 个文件逐个重算全对；A 的 `manifest.json` 8 项全对；
  `hw_api.py` 与 `helper_sha256` 的 6 处引用全部 = `8799f40b…`；除自引用的 `product-manifest.json`
  外无未覆盖文件。位流/hwh/驱动/`replay_tools`/B 的算法与上一包逐字节相同，A 侧只有 `hw_api.py` 变。
- 代码层确认（不是只听转述）：包内 `recal_product.py` 有 `AUX_IDENTITY`、`defer_aux`、
  `configuration_ready`，AUX 在 prepare 成功回读后才比；按键分支 `if self.fatal: return`，
  普通失败不置 fatal 所以能重按 CAL；`quiet=4 / speech=2.5 / input_mode=embedded` 已核对。
- `upstream-product-adapter.json` 与 A 的 `docs/contracts/product-adapter.json` 语义完全相同
  （逐键 `==` 为真），仅序列化字节数不同。
- 包内 `source_commit` 记的是 `98663a4d5ce3d035d0ed68273d0e3bb5139f8277`（`origin/C` 的父提交），
  不是包提交 `cdcaa56…`；按"包子集提交"理解，不是缺陷。
- **未做**：未安装、未上板（`192.168.2.99:22` 不可达）、未跑 `--check`/`--adapter-check`。
  C 明说 overlay 复用与 PS 卡死仍未修。证据：
  [package-io150-2026-11-02](../../report/verification/audio-replay/package-io150-2026-11-02/README.md)。

## 2026-11-02 按 C=81b47e3 同步 run_dir 一行　A　两副本同哈希，helper_sha256 变了，等 C 同轮重钉

- C 回复：采用方案 2（AUX 配置比较延后到 prepare 成功回读，代码/位流身份仍严格检查），
  **A 不需要构造写 AUX，也不需要人工开机脚本**，未知值继续如实记录；普通失败在确认静音后
  长按 BTN0 ≥1 s 即可新建 scene 重来（身份混搭、无法确认停声仍锁定）；`quiet_seconds` 改 4，
  `speech_seconds` 保留 2.5（源 RAM 装不下 4 秒计划），B 判据不改。
- 本轮 A 唯一代码改动：`ProductHardwareV2.perform` 分派前加
  `self.run_dir = request.get('run_dir') or self.run_dir`（`hw_api.py` L927）。旧代码只有
  `_run_plan` 赋值，`input`+`cue`（自动重说）/`install`/`run` 都沿用上一次目录，
  第二次写同一个 NPZ 时独占创建失败。
- 两副本（`board/audio_replay/hw_api.py` 与 `v3-io/hw_api.py`）逐字节相同，新哈希
  `8799f40b6d9f7ecbfa8f9b2491b084f046b4b9d8d7ffd013feca0c84dbca95e0`（原 `784acc6b…`）；
  `v3-io/manifest.json` 与 `docs/contracts/product-adapter.json` 已同步，并修掉契约里过期的
  `replay_trial_repair.py 22851d32 → 0dc80c23`、旧的 `prepared_capture` 未验证等四条 blockers。
- 软件验证：同一探测脚本跑 git rev `4467906` 的旧文件与新版——旧版 3/3 沿用旧目录，
  新版 3/3 取到请求目录；`_capture_path` 因目录不同才不撞名。未上板。
  证据 [run-dir-fix-2026-11-02](../../report/verification/audio-replay/run-dir-fix-2026-11-02/README.md)。
- 上一轮准备的"构造写 AUX"四处补丁作废（C 选了方案 2），报告保留并标注取代关系。

## 2026-11-02 上电 AUX 失败的离线复现与补丁验证　A　未操板：补丁有效但单独发不了，必须与 C 同轮重冻

- 给接手会话的交接文档已就位（`docs/ref/a-line-handover.md`、`docs/ref/ai-collaboration-habits.md`）。
- 离线复现（模型化 codec，I2C 原语换成内存寄存器表）：codec 上电 `0x400B/0x400D=0x00` 时
  `get_aux_gain_db()` 回 `aux_db=None`，C 的 `_identity()` 第一项即报 `硬件身份混搭或配置不符:aux_db`，
  与现场三次现象一致。把 `set_aux_gain_db(0.0)` 放在第一次读身份之前，**10 个身份字段全部通过**。
- 新结论（决定"只冻一次"的范围）：`identity()['helper_sha256']` 是 `hw_api.py` 自身的 sha256，
  被 C 钉在 `product-config.json` ×1 与 `product-manifest.json` ×3。补丁修好 `aux_db` 后立刻报
  `helper_sha256` 不符——所以 A 侧改包必须与 C 改这 4 处 pin、重建整包同一轮完成。
- 补丁（未合入）四处：`get_aux_gain_db` 如实报未知编码、构造时写一次 AUX、`capabilities` 暴露
  `aux_init`、模块头注改成 I/O 位流事实（原文仍写 `bit 2113a454`、"没有按键和 LED"）。证据：
  [aux-boot-2026-11-02](../../report/verification/audio-replay/aux-boot-2026-11-02/README.md)。
- 未做：未连板（`192.168.2.99:22` 从本机不可达）、未改冻结包、未碰 `src/feedback/` 与 C 的脚本。

## 2026-11-02 A 线交接（会话结束）

- 冻结并通过验收：`shengdi-recal-7bd365b-0b09ef6-final.zip`（sha256 `4be5083a…`），板上
  `deployment_ready=true`、`missing=[]`、`--adapter-check` 返回 `compatibility_issues=[]` 且
  `CLOSED_VERIFICATION bit_exact=True`（15872 帧逐位一致）；已安装到 `/opt/shengdi/current`。
- 已完成并验证：cue+input 单次调用（`cue_end=valid_first=21969`）、6+2 三档标定（首档 −22.0 通过、
  训练/验证源独立）、install 装载核验（512 taps、系数回读一致）、30 秒实时扩声（有放大/清晰/无啸叫）、
  急停 9.8 ms、115 cm 物理控件三项全过。
- 未解决：产品服务三次把 PS 卡死（其中一次仅执行 `systemctl restart`，排除并发因素）；
  上电后 codec AUX 为默认值 `0x00` 导致启动即身份校验失败（临时绕过 `fix_aux_boot.sh`）；
  CAL 失败后必须重启服务才能重试；时序 `quiet=2s / speech=2.5s` 偏紧。
- 交接文档：`docs/ref/a-line-handover.md`、`docs/ref/ai-collaboration-habits.md`。

## 2026-10-31 重标定第二次尝试（多音）　A　未到判据即被保护拦下：模型系数放大 48 倍，发现缺"预测余量"闸

- 白噪在 322 Hz 相干仅 0.374（3–8 kHz 有 0.73），故换成 bin 对齐 1/3 倍频程多音 + 322 Hz 线。
- 结果：`runtime saturation guard` 在第 115 帧停声，三臂一臂都没完成 → 候选被拒。
  系数：max|h| **2.217**、L1 **178.3**；部署模型 max|h| 0.046、L1 2.288（约 48 倍）。
- **教训**：装模型前必须有"预测余量"检查；"L1 ≤ 1"不是正确判据（部署模型 L1=2.288 却可用，
  因为播放字约 −20 dBFS）。应按实际播放峰值或与部署模型量级比较。
- 同时得到：白噪重拟合与部署模型零延迟余弦 **−0.05**、互相关差 6 拍 → 不是差一拍，是独立估计。
- 证据：`report/verification/audio-replay/recalibration-2026-10-31/excitation-and-guard.json`。
- 待 B 回答：fitter 是否按激励电平归一化（多音把能量集中后估出的 Ĥ 疑似被整体放大）。

## 2026-10-31 一键重标定首次上板　A　流程 6 阶段跑通、失败自动回退有效；本次重拟合未过判据（FAIL）

- 板上真跑一次（`audio_switch` 包、bit `2113a454`）：采集 6/6 段（−8 dBFS 激励、bit22=0、**零人工出声、无门禁**）
  → 转换成本包格式（补 `sample_rate_hz`、`coefficients_q20`）→ 拟合 rc=0（taps=512、lag_first=1）
  → 候选 `741da19c…` → 用候选跑 322 Hz 三点 → **判 FAIL** → 候选改名 `.rejected.json`，**部署中的模型未被破坏**。
- 三点（用重拟合模型）：CD **8.26 dB**、环路提升 **1.98 dB**、声学差 **−0.22 dB**、过冲 **−2.19 dB**。
  判据要求声学差 ≥ 0.48 dB，实测 −0.22 → 不过；|过冲| 2.19 > 1.5 也超。
- **两个必须分开说的结论**：① 流程（编排/判定/回退）**已验证**；② 重拟合的**质量未通过**，
  不能因此宣称"换距离一键成功"。残差被压下去但没有转化为麦克风端下降，指向预测的幅度对、**时序/相位可疑**。
- 同一轮环路提升只有 1.98 dB（C 那次 3.70 dB）——它是房间+增益的性质、与模型无关，
  说明今天的布置与那轮不同，跨轮比较必须写明。
- 证据：[recalibration-2026-10-31](../../report/verification/audio-replay/recalibration-2026-10-31/)（收据 + 包 manifest）。
- 下一步要问 B：激励时长/电平是否满足拟合器协议；本轮的整数/亚采样对齐是否与部署模型一致。

## 2026-10-31 一键重标定入口　A　六阶段编排完成（零人工出声、无门禁、失败不留半装态），待上板跑通

- 需求：换摆位后能"一条命令重建模型"，且流程顺滑——不能因为门禁让人不知道该何时出声。
- **设计前提**：重标定是**机器自测**流程，激励由板子自己播放，**全程不需要人说话**，所以门禁与
  "听口令开口"这套配合在重标定里根本不存在；削顶不再靠门禁挡，而是**自动降 6 dB 重试**（最多 3 次）。
- 新增 `board/audio_replay/recalibrate_oneclick.sh`：`[1]capture → [2]package → [3]fit → [4]install →
  [5]verify → [6]verdict`，每阶段一行日志；`[5]` 用**候选模型**跑 322 Hz 三点并按 B 的判据判定；
  `[6]` PASS 才落成 `model_recalibrated.json`，FAIL 改名 `.rejected.json` 并保留，旧模型不动。
- 配套 `prep_recalibrate.sh`（写令牌与参数）与 `docs/USAGE.md` 第 6.5 节。
- 依赖：板上需有拟合器源码（`scripts/fit_newlayout_candidate.py` + 同目录 `answer_new_layout_325`、
  `diagnose_peak_margin`、`reproduce_b_screening`、`feedback.calibration`）；未就位时脚本会直接失败而不是猜。
- **未上板**：编排已静态检查（Python 体可编译），六阶段端到端尚未真实跑过一次；下一步是一次约 5 分钟的
  板上验证（6 段激励 + 拟合 + 三点）。

## 2026-10-31 v3-sw 上板验证　A　SW0/SW1 物理开关在实机成立，四项硬件检查全过

- 位流重建后**已上板**：bit `2113a454…`、hwh `6d2a0198…`，时序 WNS +0.954 / WHS +0.023。
- **实机查出并修掉一个真缺陷**：第一版约束给 SW0 写了 `PULLUP true`，把输入顶死成 1，拨码看似失效；
  厂商 base.xdc 对拨码不设内部上下拉。去掉后，40 秒寄存器实时读捕捉到 `0→1→0→1→0→1→0` 的干净跳变
  （原始位 bit25 与同步位 bit24 同步翻转，SW1 的 bit23 保持 0）。
- **开关 A/B 记录**：SW0 上 → `capture_status=0x03008001`（bit25=1、bit24=1）；SW0 下 → `0x00008001`
  （bit25=0、bit24=0）；两次都 `completed`、bit22=0、`bit_exact`。
- **四项硬件检查（本包驱动）全过**：包身份 10/10；混搭被拒；静默自检（开关上下两态）；
  60 秒 2929687/2929687 帧、四类计数 0、`bit_exact`；拍手 → `stop_reason="input_clip"`、
  bit22=1、`recovery_ok`、`cleanup_errors=[]`。
- 另一处自查：verify 脚本原先用固定文件名，**失败的运行会留下旧 npz 被当成新证据**（曾因此误读到旧位流哈希）；
  已改为每次先删捕获与副车。
- 未变：算法、定点、增益、调度与 v3 完全一致；**可听收益仍未定**，这次验证的是控制通路，不是性能提升。

## 2026-10-31 物理算法开关　A　新增 SW0 强制旁路并重建位流（v3-sw），仿真与软件测试通过，未上板

- 需求：演示时用**物理拨码**开关控制算法。设计核查：PL 的 .bypass(control[1]) 每帧直取寄存器，
  且 fault 条件只覆盖改增益/帧数、写源、写系数——**旁路不在其中**，因此运行中切换是设计允许的。
- 引脚取自 Vivado 板级文件 oard_files/pynq-z2/A.0/part0_pins.xml：**SW0 = M20**，LVCMOS33，带 PULLUP，
  不猜引脚。
- 改动：RTL 新增 input sw_bypass、两级同步器、ypass_effective = control[1] | sw_s1、
  capture_status[23] 记录开关状态；新约束 uild/scripts/audio_replay_sw.xdc；
  新构建 uild/scripts/create_audio_replay_sw.tcl（独立目录 udio_replay_sw，**原构建与 XDC 未动**）。
  算法、定点、增益、调度与 v3 完全一致。
- 自洽检查：三项 iverilog 仿真通过（宽残差、FIR、完整 replay）；Vivado 2018.3 重建成功
  （WNS **+0.954** / WHS **+0.023**，TNS/THS 0，18131 端点，BRAM 80 %、DSP 3、LUT **3589**（+1））；
  sw_bypass 在实现后 IO 报告中确认落在 **M20**。
- 新包 oard/audio_replay/v3-sw/：bit 30438cef…、hwh 4de00140…，驱动重钉两处身份常量；
  包内 40 项软件测试通过；与 v3 载荷/驱动**互斥**（混搭会被拒）。
- **未上板**：板卡当前不可达，四项硬件检查仍是 v3 的结论；v3-sw 上板前必须用本包驱动重跑一次。
- 过程中自己造成并已修正的两处：tb 里把 lways #5 clk=~clk; 吞进注释导致仿真超时；
  同步器清零被误加到会话开始分支。

## 2026-10-31 集成收口　A　cherry-pick C 修复后全量 379/379、文档 0/0、载荷 10/10，main 可推送

- 合入 C 的 `2e7c205`（历史交付验收作用域 + 模型注册测试约束）：`test_delivery` 7/7、`test_tail_summary` 13/13，测试总数仍是 379。
- 全量 `sim/feedback`：**379 通过 / 0 失败 / 0 错误**。其中最后一项在受限沙箱里会因 `os.replace` 被拒而失败，不设限重跑通过——环境限制，不是缺陷。
- `check_docs` 0 错误 0 警告（162 个 md）；v3 载荷 10/10；A 三套 16+7+17 全过。
- C 未声称跑过全量，本轮全量由 A 侧执行；C 的修复没有改 manifest、历史 ZIP、A 的驱动/RTL 或 B 的模型（已核对）。

## 2026-10-31 主线集成　A　main+A+B+C 在独立工作树合并完成，硬件字节锁定；main 暂不推送（5 项 C 侧冻结检查过期待确认）

- 起点与版本：origin/main `479a570` → 合 A `e939bf0`（`96aa37e`）→ 合 B `683493c`（`50de049`）→ 合 C `51ebc38`（`7ae0ad8`），
  分支 `codex/integrate-abc`，独立工作树 `_a_work/wt-int`；根目录 38 处未提交改动全程未动、未 reset/clean。
- **冲突处理（17 个文件，无 ours/theirs 批量覆盖）**：
  - 硬件基线：`src/rtl/audio_pl_replay.v`、`replay_trial.py`、`replay_tools.py`、`closed_tools.py` **取 A 现行版本**；
    C 侧是 v3 之前的副本（缺 `bit22` 停声、爆音前移、身份块、宽残差口径）。合并后 v3 载荷 **10/10 哈希一致**。
  - 模型：`models/*` 四份**取我方（与 B 分支字节相同）**，C 侧为旧变体。
  - 报告：`2026-10-22-512-taps.md`、`audio-replay/README.md`、`model-package/README.md` 取我方（经比对为 C 的超集）；
    `model-package/03-metric.txt` **取 C**（同一批数字，C 补了"尾段不能当判据"的三栏与模型身份）。
  - 文档：`STATE` 按线各取自己最新段（表头/关键数字/A/C 段用 A 现行，B 段用 B 的 10-30 版，C 段用 C 的）；
    `REQUESTS.md` 维持 A 的删除决定（内容早在 `docs/archive/tasks/`），5 处断链改指归档索引；
    `.gitattributes` 两侧 `-text` 规则取并集；`board/audio_replay/README.md` 保留 A 入口并加 B/C 材料链接，不恢复 C 的旧操作页。
- **验证（真跑）**：`check_docs.py` 0 错误 0 警告（162 个 md）；v3 载荷 10/10；A 三套测试 16+7+17 全过；
  驱动/工具四个模块导入通过；全量 `sim/feedback` **379 项通过 374**。
- **未通过 5 项全部是 C 侧过期钉死，不是合并损坏**：
  - `tools/delivery-freeze.json` 的 `source_sha256`：`board/audio_replay/sprint_selftest.py` 钉 `6fcd4da6…` 实际 `70e28d05…`、
    `scripts/assemble_experiment.py` 钉 `30581d0e…` 实际 `a8b0f5c0…`——**在 C 分支上就已经对不上**，LF/CRLF/BOM 三种编码均不匹配；
  - `sim/feedback/test_tail_summary.py:94` 断言 `len(registry)==4`，B 现行 `models/manifest.json` 是 5 项（新增 `01c9102a…`）。
- 因此**未推送 main**，等 C 确认重钉或改断言；集成分支本身已可构建可运行。
- 环境侧记录：沙箱下 `tempfile.mkdtemp` 以 `mode=0700` 建的目录不可访问、子进程输出按 GBK 编码，
  用 `_a_work/run_suite.py` 把这两点局部绕过（**未改任何测试与断言**）；ACL 诊断脚本判定该目录**不是**权限问题（`NOT_THIS_CLASS`）。

## 2026-10-30 转入参赛材料制作　A　交付硬件白名单/说明、一次现场拍摄操作单、素材记录模板与单段演示入口（板卡不可达，入口仅静态检查）

- 按队长 [A 拍摄与硬件交付任务](../../materials/prompts/a.txt) 与 [video-plan](../../materials/planning/video-plan.md)、
  [submission-plan](../../materials/planning/submission-plan.md) 调转本轮重点：真人使用演示、视频素材、硬件可集成版本。
- **`materials/work/a/integration.json`**：30 项硬件白名单，逐项写源提交/哈希/用途/依赖——
  RTL（`audio_pl_replay.v`、`feedback_fir.v`）、厂商 VHDL（iis_ser/iis_deser + LICENSE）、
  构建入口与约束（`create_audio_replay.tcl`、`audio_bringup.xdc`）、仿真入口与 4 个 testbench、
  v3 整组 10 项发布载荷、9 个现场入口；另写恢复入口（配对校验 → 每次试次自动静音并恢复 stock →
  `audio_live` 回退 → 失败原件成对保留）。位流字节锁定 `48e38f78…`，根目录旧位流与其它驱动不得混装。
- **`materials/work/a/hardware.md`**：平台与工具链（保留 Vivado 2018.3 及理由）、PS/PL 实际分工、
  **保护归属表（检测在 PL、判定与停声在 PS）**、块设计 IP 清单、从零复现位流 4 步、
  时序资源（WNS +0.548 / WHS +0.015 / BRAM 80 % / DSP 3 / LUT 3 588 / FF 5 018），
  并**如实标注不是完整时序签核**（四个外部 I/O 延迟约束未写）。
- **`materials/work/a/shooting-plan.md`**：一次 50 分钟现场窗口的完整操作单——布景与设备分工
  （3 手机 + 平板 + 懒人支架 + 台灯）、a01–a06 每条的**具体命令与时长**、真人站位 20 cm（不照搬手机 5 cm）、
  开跑前门禁、失败出口（门禁失败退 5 cm 最多两次 / 保护停声保留失败原件 / 时间不够优先保 a02 与 a04）、
  停止方法（固定预算自动停声；提前中断用 Ctrl-C，收尾路径会停声并恢复；不直接断电）、
  拍摄后 10 分钟当场检查，以及与 B/C 的交接内容。
- **`materials/work/a/takes.md`**：素材记录模板（文件/配置/结果/可引用结论/问题 + 板卡侧对应文件 + 失败素材区）。
- **新增拍摄入口 `board/audio_replay/demo_take_v3.sh`**：单段"静音 → 通路开启 → 静音"（a02 20 s / a05 60 s），
  带 `CUE` 时间戳便于与录像对齐、开跑前 0.6 秒静音门禁、结束自动静音；
  `prep_demo_a02.sh` / `prep_demo_a05.sh` 只写操作者令牌。
  **静态检查通过，但板卡当前 SSH 超时不可达，未在板上执行**——现场窗口开头先冒烟跑一次。
- 未做：a01–a06 实拍、首剪、播放电平对照的有效测量（需运行 ≤0.336 秒或捕获可配）、B 段。
- 采购：本轮**未下单**，按 video-plan 先试拍再决定（优先 0 元方案）。

## 2026-10-30 队长核对指南与分支，安排参赛材料并行交付

- 阅读并渲染核对 AMD 指南自主选题条款：补入 Skill、AI纠错轨迹、构建复现、工具版本说明及决赛英文海报；用户已在办理授权书与GitHub事项。
- fetch 核对远端 A/B/C/main，运行 merge-tree 预演，记录具体冲突和各线文件归属；未合并 main、未覆盖本地未提交内容、未删除历史文件。核查与候选集成安排见 [材料计划](../../materials/planning/submission-plan.md)。
- 按用户设备与“真人演示”要求交 [2分45秒视频分镜和采购建议](../../materials/planning/video-plan.md)，生成 A/B/C 可转发提示词；A 实物/视频，B HTML教程/算法，C 候选集成/报告/Skill。内部目标11月2日，未把用户“可以”解释成官方截止确认。
- 新增 [materials 入口](../../materials/README.md)，将制作说明与最终提交、原片、私密文件分开。本轮没有操板、改算法或重做功能实验。

## 2026-10-29 队长整理保留版本与旧入口　A 分支文档整理

- 按用户要求保留旧驱动、位流、Notebook、模型与原始证据字节；[上板索引](../../board/README.md) 和 [replay 版本说明](../../board/audio_replay/README.md) 区分发布载荷、历史回退、专项诊断及有缺陷的测量入口。
- 整理前 STATE、三格操作单及早期代码导航存入 [历史原文](../archive/pre-freeze-guide-2026-10-29.md)；STATE 原地改写，移走过期动作与相反结论，保留扩声阳性观察和未完成指标。旧日志未改写。
- 更正 v3 manifest 的执行驱动身份与硬件状态说明，清理重复说明项；载荷 hashes 未变。新派生回包已在 A 入库，C 最终回执仍按实际交接确认。
- 本轮核对的证据是 [三臂派生 JSON](../../report/verification/audio-replay/wide-residual-v3/C-tone-1746930178556850644.json) 及 [既有工程记录](../../report/verification/audio-replay/wide-residual-v3/evidence.json)。分析脚本与 C Git 版本的差异可由 UTF-8 BOM＋CRLF 精确解释。
- 本次没有连接板卡、播放声音、运行功能试验或修改契约语义；验证只覆盖文档结构、JSON、版本索引和历史/发布载荷字节保留。

## 2026-10-28 全天汇总　A　v3 交付驱动四项硬件全过、322 Hz 三点按源激活窗口判据成立、单位修正、可听收益撤回为"未定"

- **交付态**：位流 `48e38f78…` / hwh `9411adb5…`（全程未变）；驱动 **`79c4d9f7…`**、
  `replay_tools` **`bba22102…`**、`tone_round_guard` **`76413d84…`**、测试 **`b32f3486…`**，manifest 10 项自校验通过。
- **四项硬件检查（`79c4d9f7` 上重跑）全过**：混搭在位流装载前被拒；静默自检（status 带全身份）；
  输入满幅停声（`0x00408000`、8 满档、38877/146484 帧、`recovery_ok`）；60 秒（2929687/2929687、bit22=0、
  四类计数 0、峰值 −11.9 dBFS、`bit_exact`）。
- **322 Hz 三点**：C 用源激活窗口（6619/16384 帧）复算 **CD 8.46 / 环路提升 3.70 / 声学差 4.95 / 过冲 1.25**，
  按 B 判据 **cancellation_holds**；我整窗算的是 8.43/4.24/5.45/1.21，**以 C 为准**。
- **修掉的真 bug**：Codec 解除静音爆音落在首批帧 → 门禁误判满幅；加 0.25 s 前移，**零阈值改动**。
- **判据层（C 三轮）**：门禁全判据、纯音首臂保护即止、分析器补源数组/错帧/副车、单位补 Hann 相干增益
  （0.25 满幅 = −12.04 dBFS）、播放电平报告加无效窗口判定；守卫测试 **17 项**，另有停声 16 项、核对 7 项。
- **可听收益：未定**。撤回"输出太小/听众收益为负"——存窗只有 6619 帧含源，尾窗不能作响度判据；
  既有听众记录（10-27 与 10-28 的「听不出」「能听出放大」等）作为记录保留，不作证据。
- **B 决定的工作点**：手机 6/15 + 5 cm + g=−8 + Codec 40，ADC 换余量改为**触发式**（彩排 bit22=1 才换）。
  **B 段（g=−3 故意起振）未做**，需授权 + 人守音响电源 + 硬 2 s。
- **冻结建议**：工程基线可冻结；完整效果流程未冻结（候选改善与真人可辨扩声未成立；C 同此结论）。
- 证据：[wide-residual-v3/evidence.json](../../report/verification/audio-replay/wide-residual-v3/evidence.json)、
  [C 的复算 JSON](../../report/verification/audio-replay/wide-residual-v3/C-tone-1746930178556850644.json)；
  逐轮细节见下方 10-28 各条。

## 2026-10-28 按 C 修单位并撤回可听收益结论　A　Hann 相干增益补齐（0.25满幅=−12.04）；播放电平量的窗口在源结束之后，结论作废

- **单位错误（C 指出，属实）**：`level_dbfs` 取了汉宁窗谱的峰值却没除窗的相干增益，
  所有绝对电平被抬高 `20log10(N/4)`（N=4096 时约 60 dB）——0.25 满幅单音报 **+48.16**，应为 **−12.04**。
  修为 `amplitude = 2|rfft(x*win)| / sum(win)`，测试加一项，**17 项全过**，实测读回 −12.04。
- **三个差值不变**（同一窗口、同一因子）：CD 8.43 / 环路提升 4.24 / 声学差 5.45 / 过冲 1.21 dB；
  绝对电平重算为 open −24.48 / bypass −20.24 / cancel −25.69 dBFS（残差 −27.01 / −20.24 / −28.67）。
- **撤回"—42～−47 dBFS 证明输出太小 / 听众收益已测否定"**（C 指出，属实）：
  驱动只存环缓冲**末尾 16384 帧 = 0.336 秒**；交替段运行 2.4 秒、源 2.0 秒 → 存下的窗口是
  **2.064～2.400 秒，整段在源结束之后**，量到的是衰减尾巴，不是节目内容 → **不能作响度结论**。
  报告脚本已加 `MEASUREMENT_INVALID` 标志，并把窗口算术写死（`capture_start = completed − len`）。
- 另更正：摘要里的 1.38 dB 是把 gate 段算进了零系数臂；**四臂均值为 1.91 dB**（与 C 的 1.905 一致），
  且该差值只能作为**同窗比较**保留，不是响度测量。
- **可听收益问题重新回到"未定"**：既不是实测否定，也不是实测肯定。仍成立的是 322 Hz 三点判据。
- 合规做法已记：要真测播放电平，**运行时长必须不超过保存窗口（0.336 秒）**，或把捕获长度做成可配；
  本轮没有新增有声试次。

## 2026-10-28 可听收益改为直接测量　A　（**同日已撤回：量到的窗口在源结束之后，见上条**）

- 不再依赖听众：抓包的 `reference` 通道就是**送进 DAC 的播放字**，直接算两臂在音响上的电平。
- 四段交替（同注入源、固定 seed、各 2 秒，零/候选/零/候选）播放 rms：
  零 **−42.84 / −46.74**、候选 **−46.36 / −47.03** dBFS → **平均差 1.38 dB**，
  而**同一条件两段自己差 3.90 dB**。
- **判读：不可分辨**。效应小于同条件抖动；绝对输出只有 **−42～−47 dBFS**（满幅的百分之一量级），本来就不够响。
- 这解释了当天全部听众记录（「没放大人声」「能听到、没明显放大」「差不多/听不出」）——**不是听力问题，
  也不是抵消失效**，是输出太轻、差值太小。
- 若要改变该结论，只有三条路：把输入加大（会顶满 ADC，v3 立即停声）、把 g 加大（零臂已在响度顶点下方
  0.12 dB，−4 dB 必自激）、换更近或更高效的扬声器（夹具内不可控）。
- 过程教训（操作者指出）：两臂间隔太长无法凭记忆比较；正确做法是在**一次 armed 运行内**切 `control` bit1，
  但该工作点下结论不会变，故不再占用现场时间。

## 2026-10-28 两臂辨听　A　候选臂麦克风低 5.6 dB，但说话人听不出差别；无啸叫、都能听清

- 流程先说清再跑（第一次没给题目、跑完才问，判为**流程无效**，不作结果）。有效这次：门禁 → 同一句话两段各 6 秒
  （零系数臂 → 候选臂，间隔约 4 秒），**开跑前**已告知要判"哪段更响 / 有无啸叫 / 能否听清"。
- 全部 `completed`、bit22=0、无饱和、无满档、`recovery_ok`。
- 数字：零 **−29.9 / 峰值 −14.8**、候选 **−35.5 / 峰值 −19.7** → **候选低 5.6 dB**。
- 听众原话：**「差不多/听不出」「无啸叫」「都能听清」**。
- **判读（含方法学限制）**：麦克风电平确实降了 5.6 dB，但**说话人自己听不出来**——因为他同时是声源，
  自己直达声（骨传导 + 直达）占主导，放声电平的变化被掩蔽。历史场次用**距音响 20 cm 的独立听众**正是为这个。
  → 这条**不能**写成"抵消不可听"，只能写"该听众位置分辨不出"；要回答可听收益必须换独立听众或录 A/B 回放。

## 2026-10-28 按 C 第二轮复验修三条　A　门禁改成全判据、纯音首臂保护即止、分析器补三类漏检；修后跑一轮真实三臂

- **C 指出的三条都成立，其中第 2 条是真 bug**：
  1 **门禁只看峰值** → 若门禁本身触发保护但抓到的峰值恰好在 (−60,−6) 内，分支会继续。
     已改为**先过与真臂相同的全判据**（completed、bit22=0、无满档、recovery_ok）再判电平；
     `field_ac_segments_v3.sh`、`field_stationary_v3.sh`、`field_human_pair_v3.sh` 三处都改。
  2 **纯音首臂保护但已落 NPZ 时仍跑后两臂** → `tone_arms_v3.sh` 的"失败即止"只判文件是否存在。
     已改为按 `stop_reason/bit22/recovery_ok` 判，并标记 **SUPERSEDED**（由 A/C 脚本的 tone 模式统一产出 manifest）。
  3 **分析器漏检**：改用**实际 `source_pcm16` 数组**做哈希比对（不只信元数据声称的哈希）；
     `frames` 必须等于数组实际长度、`first_frame+frames==completed_frames`、注入源窗口三臂一致；
    **必须存在 `status.json` 副车**且 `recovery_ok=true / cleanup_errors=[] / save_error=None / stop_reason=completed`；
    三个信号统一报 **dBFS（re 24 位满幅）**，差值名称固定为 `cd_322_db / loop_boost_db / acoustic_difference_db / overshoot_db`。
    测试扩到 **16 项**（含"换源数组""三臂共同错帧数""恢复失败副车""清理错误"）。
- **修后按 C 要求只跑一轮固定配置三臂 + 真实 manifest**（拒绝样例在副本上派生，不额外发声）：
  open 47.77 / bypass 52.01 / cancel 46.56 dBFS@322 → **CD 8.43 / 环路提升 4.24 / 声学差 5.45 / 过冲 1.21**
  → **cancellation_holds**。同一天上一轮是 7.08 / 4.12 / 4.92 / 0.80，**判据重复成立，数字漂移约 1 dB**。
- 一处自查失误：改门禁时把 `gate = run(...)` 那行一起替换掉了，首跑报 `NameError`；已补回并重跑通过。
- 未做：听众的两臂辨听对照；B 段（g=−3）故意起振（需授权 + 人守电源）。

## 2026-10-28 现场第三轮　A　修掉 Codec 解除静音的爆音（门禁误停的真因）；A 段纯音三点判据成立；C 段语音臂全程无保护

- **真因不是环境噪声**：连续三次门禁在第 5 / 650 / 114 帧就报输入满幅，安静的房间里麦克风却读到 −0.0 dBFS。
  操作者说"经常听到音响**嘟**一下"→ 是 **Codec 解除静音的爆音**：驱动在解除静音的同一下 arm，
  爆音正好落在首批帧里。**修法**：`CODEC_SETTLE_SECONDS = 0.25`，在解除静音与 arm 之间等爆音衰减。
  **没有动任何阈值、没有放松保护**——只是把 arm 点后移。修完后同一轮纯音与 60 秒都干净通过。
- **A 段（322 Hz 三点，同 g/同源/同距离）**：open 185.67 / bypass 189.79 / cancel 184.87 dB →
  **CD(322) = +7.08 dB**（模型拟合）、**环路提升 = +4.12 dB**（可听收益量级）、
  **声学差 = +4.92 dB**（= 4.12 + 过冲 **0.80**）→ 按 B 的判据 **cancellation_holds**。
  三臂全部 completed、bit22=0、无满档。与 10-27（6.37/3.75/4.76）同量级，漂移约 0.4 dB。
- **C 段（语音，每臂 3 遍 × 10 秒）**：6 遍全部 completed、bit22=0、四类计数 0、`wide_residual_frames=0`。
  但**有 2 遍是静音间隙**（zero_1 −38.0、cand_2 −39.0），有效 4 遍：零 −24.2/−23.2、候选 −24.8/−25.5
  → 候选低约 1.5 dB，**但两臂不是同一句话片段，不能当配对电平比**。
  这一轮说明：该电平下**真人语音不削顶**（6 遍 bit22 全 0），候选**全程无保护**；宽残差越界仍未出现。
- **新驱动 `79c4d9f7…` 四项硬件检查全部重跑通过**：混搭拒绝、静默自检（status 全身份）、
  输入满幅停声（拍手 → `input_clip`、`0x00408000`、8 个满档、38877/146484 帧、`recovery_ok`）、
  **60 秒**（2929687/2929687 帧、bit22=0、四类计数 0、峰值 −11.9 dBFS、bit_exact、墙钟 89.2 s）。
  听众再次给出「**能听出放大**」。
- 一条当场教训：**拍手测试后不能立刻跑监听探针**，拍手尾巴会把它判成输入满幅（这轮踩了两次）。

## 2026-10-28 交付版补齐硬件复验　A　输入满幅停声与 60 秒在 c2b2a86a 上均通过；听众首次「能听出放大」

- 操作者回到现场后补跑两项（交付驱动 `c2b2a86a…`、bit `48e38f78…`）：
  - **输入满幅停声 PASS**：距麦 2–3 cm 拍手（只监听、增益 0）→ `stop_reason="input_clip"`、
    `capture_status=0x00406350`（bit22=1）、峰值 **−0.0 dBFS**、15 个满幅样本、12712/146484 帧即停、
    `recovery_ok=true`、`cleanup_errors=[]`。
  - **60 秒连续 PASS**：先跑 3 秒监听探针（mic −32.2、峰值 −19.7、bit22=0、无满幅）合格，
    再跑 60 秒 → `completed`、2929687/2929687 帧、`capture_status=0x00008001`、bit22=0、四类计数 0、
    mic RMS −31.4、峰值 −14.3、无满幅样本、bit_exact、墙钟 89.0 s。
- **听众原话：「能听出放大」**（零系数、−8 dB、Codec 40、手机 6/15、5 cm）。
  这是扩声通路的定性肯定，**不是抗啸叫收益**（当时没有抵消）。
  与更早两次否定记录并列保存：10-27 的 20 cm「感觉都没放大人声」、10-28 早些 60 秒「能听到、没明显放大」。
- 过程中两次失败如实保留：手机 8/15 在 5 cm 会顶满 ADC（31988 帧即停）；拍手尾巴未收时探针/长跑
  也被正确判停（mic −18.2、1 个满幅样本）——**判据按预期工作，不是板卡故障**。
- 证据：[wide-residual-v3](../../report/verification/audio-replay/wide-residual-v3/evidence.json) 的
  `driver_c2b2a86a_full_verification` 与 `hardware_verification_matrix`（四项全 PASS）。

## 2026-10-28 上电后硬件复验　A　混搭被拒、输入满幅停声、60 秒两次 completed 全部通过；可听收益仍未成立

- 上传驱动 `82787262…` 到 `audio_wide` 并核对：`replay_tools 0d4e1933…`、位流 `48e38f78…`、
  hwh `9411adb5…`、`test_runtime_stop c4ac1bfd…` 全部对上。
- **混搭拒绝（C 第 5 项）**：把 v2 的 bit/hwh 放到 v3 驱动旁边，`replay_trial` 在位流装载前抛错
  「bitstream does not match this driver: expected 48e38f78…」→ 未 arm、未发声。**PASS**。
- **新驱动静默自检**：58593 帧、`completed`、bit22=0、`input_full_scale_seen=false`、四类计数 0、bit_exact。**PASS**。
- **输入满幅停声（队长关键保护 / C 第 2 项）**：距麦 2–3 cm 连续拍手（脚本只监听、增益 0），
  结果 `stop_reason="input_clip"`、`capture_status=0x004019ee`、bit22=1、满幅样本 20、
  3319/146484 帧即停、`recovery_ok=true`、`cleanup_errors=[]`。**PASS**。
- **60 秒连续运行**：第一次在 8/15 会削顶 → 按判据停（31988 帧、bit22=1、mic −21.6）；
  降到 **6/15** 后先跑 3 秒监听探针（mic −25.0、峰值 −11.6、无满幅）合格，再跑两次 60 秒：
  两次都 `completed`、2929687/2929687 帧、bit22=0、四类计数 0、bit_exact、无满幅样本。
  **听众**：第一次要求重听；第二次「**能听到、没明显放大**」→ 连续性/保护成立，**可听扩声收益不成立**。
- **重要更正**：历史基线「手机 8/15、5 cm」今天在 5 cm 会把 ADC 顶满。历史那次没有输入检测器，
  它的「四类计数全 0」**从未证明输入干净**；且其记录电平比今天低 7 dB，场景不同。
  **「8/15 原样复现」这条不能再引用**；6/15 是变更条件，已标记。
- 脚本入库：`board/audio_replay/{verify_v3_driver,clap_test_v3,listen_probe_v3,long60_v3}.sh`。

## 2026-10-28 队长决定后的驱动修复　A　bit22 变成停声条件（`input_clip`），只改驱动不改位流；软件验证 12 项通过

- 队长 2026-10-28 决定：**v3 作冻结主线**，v2 保留成功基线与回退；并授权直接修
  「运行轮询不检查 `capture_status` bit22」。
- 改了什么（`board/audio_replay/replay_trial.py`）：
  - 新增纯函数 `runtime_stop(status, clip_word, gain_word, mix_word)`：bit22 → `"input_clip"`；
    预测半字 / 增益后 / 混音 → `"guard"`；**只有增益前残差半字 → 不停**。
  - 轮询循环每圈重新读 `capture_status`，发现 bit22 走既有 disarm/mute/保存/恢复，`stop_reason="input_clip"`。
  - **收尾再查一次 bit22**（末次轮询可能漏），且优先于 `completed`。
  - `input_clip` 与 `guard` 一样在结束时抛错并写明原因。
  - 未改：RTL、位流、增益前残差只计数、预测/增益后/混音/故障/超时/手动停全部照旧。
- 软件验证：`board/audio_replay/test_runtime_stop.py` → **RUNTIME_STOP_TEST PASS (12 checks)**，
  含「残差半字单独越界必须继续跑」「bit22 与其它饱和同时出现时标 input_clip」「decode_counts 拆分不变」。
- 身份重算：`replay_trial.py` = **`82787262…`**（先 `1b07586f…`，补位流配对校验后重算；旧 `6b397359…` 作废），`replay_tools.py` = `0d4e1933…`，
  核对脚本 `test_runtime_stop.py` = `ea1a09e0…`；位流 `48e38f78…` / hwh `9411adb5…` **未变**。
  **板上仍是旧驱动 `6b397359…`**（断网），上电后必须先上传新驱动再做任何运行。
- 未做：**bit22 停声本身未上板复验**（断网）；这是恢复后第一件要验的事。
- 另补队长第 5 项：驱动在**下载 overlay 之前**校验同目录 bit/hwh 的 sha256，混搭直接 `RuntimeError`；测试扩到 **16 项**（含「v2 位流 + v3 驱动」「v2 hwh + v3 位流」被拒）。
- 报告口径按队长更正：时序写「**已施加约束满足**」，四项外部 I/O 延迟约束缺口继续披露，
  不写完整签核；「输入过载可见」与「输入过载自动停声」分开写。

## 2026-10-27 勘误　A　契约里「g ≤ 1」写错，B 指出；实际寄存器上限是 g ≤ 8

- `docs/contracts/audio-replay-v3.md` 原文写「`g ≤ 1`（`control[31:16] ≤ 32768`，Q4.12）」，
  两半自相矛盾：Q4.12 下 32768/4096 = **8.0**。已改为 **`g ≤ 8`（+18.06 dB）**，
  并保留算术结论：`|w| ≤ 2^24`、`g ≤ 8` 时 `g·w ≤ 2^39 < 2^40−1`，仍落在 41 位乘积内。
  **现场授权的工作范围 `[−14, −6] dB` 是另一件事**（由现场门禁决定），不因这个上限放宽。
- 位流不受影响（工作增益 1631）。RTL 注释 `audio_pl_replay.v:195` 里还留着 "gain is <= 1.0"
  的旧说法，**故意不改**：位流 `48e38f78…` 是由改注释前的源文件构建的，改源码会让
  「源文件↔位流」对不上；该笔误登记在 [证据](../../report/verification/audio-replay/wide-residual-v3/evidence.json) 的 corrections 里。
- 同批登记：板卡在收工后 **192.168.2.99:22 不通**，因此「当前夹具的 |H| 峰频扫描」与
  「输入峰值 vs 距离阶梯」**未执行**，不作任何数字声明。

## 2026-10-27 现场窗口（A 现场配合听众）　A　纯音三点首次出现可判读的抵消；真人语音三批，v3 的「不再误停」在硬件上被复现

- **稳态源改用 322 Hz 纯音**（|H| 峰值点、0.15 FS、−8 dB、Codec 40），三点同电平：
  open（增益 0）45.44 dB / bypass（闭环不减）**49.19** / cancel（闭环抵消）**44.43**。
  → 环路把该点抬 **+3.75 dB**；抵消把**残差**压低 **6.37 dB**、把**麦克风**压低 **4.76 dB**，
  比无环路还低 1.01 dB。三臂 bit_exact、无保护、无削顶、`wide=0`。**单频单电平，不是 ASG。**
  对照：白噪两臂三轮占比差 +1.6 / −4.7 / −2.1 dB，符号都翻 → 白噪在这夹具里不是能用的仪器，已停用。
- **真人语音三批**（注入源静音，人就是声源；−8 dB、Codec 40）：
  ① **12 cm 零系数臂**：completed、尾部峰值 −12.2 dBFS，但 **bit22=1**（中途顶到 ADC 满幅）→ 按判据不合格；
  ② **20 cm 分开两臂**：零系数 −36.6/峰值 −23.1、bit22=0 → 合格；候选 −27.8/峰值 −16.6、**bit22=1**、
     **rsat=7 且 psat=0**、**仍然 completed（292968/292968 帧）**——这正是 10-27 现场让播放中断的那个签名；
     v2 驱动会在第一个残差饱和就停，v3 **没停**。声学上该试次不合格（输入削顶），但**保护语义的改动在硬件上被证实**；
  ③ **20 cm 同一段连续语音的两臂**（可比性最好）：零系数 −21.6/峰值 −8.5、候选 **−24.0**/峰值 −10.2，
     两臂都 bit22=0、四类计数 0、bit_exact、completed → **两臂都合格**，候选低 **2.4 dB**。
- **听众（A 本人）原话**：三次都是「没有啸叫」；20 cm 分开两臂「听不出来（自述听力不佳，明确不是"差不多"）」
  「两遍都听不清」；20 cm 同语音两臂「感觉都没放大人声」。
  → **20 cm / −8 dB 这个工作点没有可听出的扩声收益**；这是工作点结论，不是两臂差异，也不区分 v2/v3。
- 门禁更正：上一次报的「静默门禁漂 11.8 dB」里，至少有一部分是**人在说话时测的门禁**。
  现场窗口的门禁必须在人安静时测，且放在说话臂之前。
- 未完成：12 cm 下候选臂的合格试次（该距离会顶满 ADC）、可听扩声收益、v3 的现场 ASG。

## 2026-10-27 补记（同日，撤回一条判断）　A　音响声路其实是通的；稳态两臂两轮都不足以下结论

- **撤回**：本页下一条写的「音响声音没有到麦克风、两臂判无效」的**原因部分是错的**。
  真因是**宽带噪声在这套夹具里耦合弱**：−20 → −6 dBFS 只把麦克风抬高 3.5 dB，
  −20 dBFS 白噪在任一 60 Hz 带内的能量低于房间底噪，所以两臂都贴在底噪上。
- 判据错在哪里：用「宽带噪声 RMS 对静默门禁」判断声路。改用**频率集中的 1 kHz 音调**并
  把数字增益强制为 0（无反馈）后，声路立刻显形：麦克风 RMS **+6.5 dB**、1 kHz 频带相对其余频带 **+30 dB**
  → **board → codec → 音响 → 空气 → 麦克风 是通的**（spk_silent / spk_tone 两试次）。
- 电平阶梯（同样强制增益 0，白噪 seed 4242）：−20/−12/−6 dBFS 峰值 → 麦克风 −38.6/−37.1/−35.1 dBFS，
  峰值 −22.7/−24.6/−21.2，全部无削顶。
- 稳态两臂第一轮（−20 dBFS）：零臂占比 0.0695、候选 0.0484，两臂都贴底噪 → 不可用。
- 稳态两臂第二轮（−8 dBFS）：门禁 −26.4/峰值 −13.8（低于 −6 上限）；
  **零臂 −27.3/峰值 −13.3、占比 0.0103；候选臂 −35.1/峰值 −21.5、占比 0.0304**；
  两臂都 bit_exact、无保护触发。候选臂总电平低 7.8 dB，占比反而高 4.7 dB 而绝对带内低约 3 dB ——
  **占比被总电平差混淆**，不作抵消结论。
- **新问题（未解）**：静默门禁在同一会话的两轮之间从 −38.2 漂到 −26.4 dBFS（11.8 dB），
  板卡侧只改了激励电平，未动接线/增益。可能是外部功放增益或限幅状态、或房间变化。
  任何现场窗口都必须「门禁 → 两臂 → 门禁」，把漂移量摆出来。
- **本轮所有试次 `wide_residual_frames=0`**：语音瞬态那种越界形态没有在硬件上重现。
  v3 就是为这个形态做的，而注入式声源与真人说话不等价（麦克风看到的瞬态与预测相关），
  所以**只有真人近距离说话能验证 v3**。
- 仍然未做：真人语音两臂、门禁稳定性、v3 现场结论。

## 2026-10-27 宽残差下半轮　A　replay 侧已仿真、已综合出时序、已上板，稳态两臂因音响未出声判无效

- ② 让 audio_pl_replay 可 elaborate：真正原因两个，都不是"缺 I2S 源"那么简单。
  一是 iverilog 不接受一个 ANSI 端口声明里写两个带初值的端口（`output reg [23:0] a=0, b=0`），
  已把两处拆成独立声明；Vivado 两种写法都接受，属纯解析可移植性改动，语义为零改动。
  二是 iis_deser/iis_ser 是厂商 VHDL，Icarus 根本编不了 —— 新增 `sim/audio/iis_sim_models.v`，
  按 VHDL 状态机逐行翻译（状态表、位计数比较值、边沿检测、更新顺序一致，非阻塞赋值复现 VHDL 语义），
  仅用于仿真；Vivado fileset 仍用 VHDL。模型可信度自证：原本对着 VHDL 写的 `tb_audio_replay.v`
  不改一行即在 iverilog 下 AUDIO_REPLAY_PASS，同一 tb 在 xsim + 真 VHDL 下也通过。
- ② 新增 `sim/audio/tb_replay_wide.v`（`RESIDUAL_REPLAY_WIDE_PASS`）三例：h0=−1.5、mic 8,000,000 时
  prediction −6,000,000 且 **psat=0**、窄残差钳到 0x7FFFFF、宽残差 14,000,000、增益 0.5 → 播放 7,000,000
  （旧钳位路径只会给 4,194,304）；同一形状增益 1.0 → 16,388,608 越界，**钳位发生在增益后**，
  gain_clip_count>0、capture_status[21]=1；零系数 + mic=0x7FFFFF → 残差计数全 0 而 bit22=1，
  证明输入满幅是独立检测。用 `build/scripts/test_audio_replay_wide.tcl` 在 xsim + 真 VHDL 下复跑通过。
- 顺带修两处测试腐化：`tb_audio_replay` 只装 256 个系数而 RTL 自 39d5ac3 起默认 512（`fresh` 永不置位），
  已改为 512；`tb_feedback_fir` 的黄金向量是 256 抽头，改为 `.TAPS(256)` 固定，并新增
  `residual_wide == mic − pred` 的逐样本核对（2304 样本）。
- ③ 综合实现（Vivado 2018.3，`create_audio_replay.tcl build`）：**WNS +0.548 ns、WHS +0.015 ns、
  TNS/THS 0、0 失败端点、18128 端点、100 MHz，"All user specified timing constraints are met"**；
  BRAM 112/140 = 80.00%、DSP 3、LUT 3588。位流 `48e38f78…`、hwh `9411adb5…`。
  与 v2 基线（+0.287/+0.034/80%）比，setup 更宽、hold 窄 19 ps 但仍为正。
- ④ 重建向量：`scripts/make_fir_vectors.py` 生成 `tmp/fir_vectors`（3 例 × 768 帧 × 256 抽头），
  `FEEDBACK_FIR_PASS samples=2304 latency=771`。
- ⑤ 上板：新包目录 `/home/xilinx/jupyter_notebooks/base/audio/audio_wide`，v2 包 audio_live 原样未动。
  静默自检 58593 帧、`capture_status=0x00008001`、bit22=0、四类计数 0、`coefficient_status=0x200A`、
  新判据下 bit_exact=true。随后稳态源两臂各 107421 帧、**无保护触发**，但麦克风电平（−38.4/−38.7 dBFS）
  与静默门禁（−38.2）持平、零系数臂频带占比 0.0695 远低于上次有效场次 0.2281 →
  **音响声音没有到麦克风，两臂判无效**，不作抵消结论。
- 证据检查器两处修正（`board/audio_replay/replay_tools.py`）：输出基准改用 mic−prediction 的宽残差
  （否则宽路径生效处必然报失配）；截断环形缓冲的输出核对起点改为 skip+2（此前把 512 帧不可知历史
  算成失配，使任何非零模型臂看起来都不 bit_exact，这个问题早于 v3）。同一份板上候选捕获用新判据
  output_mismatches 0、旧判据 512。
- 契约：[audio-replay-v3](../contracts/audio-replay-v3.md) 记录位段（bit22）、乘宽后钳位与保护语义；
  版本索引同步。证据：[wide-residual-v3](../../report/verification/audio-replay/wide-residual-v3/evidence.json)。
- 工具经验：Vivado 的 `launch_runs` 在后台任务里子进程会消失（停在 "Waiting for synth_1"），
  须前台执行；同沙箱下 `update_compile_order` 也会静默返回空、块设计引用失败，综合/仿真都要完整访问权限。
  `docs/log/progress.md` 原有 4 个 NUL 字节导致文本工具判为二进制，本次一并清除，正文未改。
- 未完成：真人语音两臂（需现场）与音响声路确认。


## 2026-10-27 宽残差轮　A　FIR 半已改并仿真验证、驱动 guard 已改，replay 侧未仿真、未综合

- 按队长批准实施「25 位宽残差过数字增益后再钳位」。
  feedback_fir.v 新增 residual_wide_pcm[24:0]（未钳位 25 位差），旧 24 位残差与 rsat 含义不变；
  audio_pl_replay.v 改乘宽残差（显式符号扩展）、新增独立输入满幅检测与计数、capture_status 第 22 位；
  replay_trial.py 的 guard 改为只按预测/增益/混音停，增益前残差只作诊断。
- 新增 sim/audio/tb_residual_wide.v，iverilog -g2012 通过：RESIDUAL_WIDE_PASS checked=4
  （无越界时宽窄一致；正越界宽残差 8389607 / 窄 8388607 / rsat=1；负向未越界 rsat=0；bypass 符号扩展）。
- 未完成且如实记录：audio_pl_replay 无法被 iverilog elaborate（缺 I2S 源）故 replay 侧未仿真；
  未综合无时序（Vivado 2018.3 在 D:\Xilinx）；tb_feedback_fir 缺向量文件未跑；未上板。
- 新增 docs/lines/a-interaction-notes.md，记录 AI 与 A 的协作习惯（通知节奏、汇报方式、
  异议处理、文档纪律、现场操作、环境工具、三条硬经验），供后续新窗口开工先读。

## 2026-10-27 B 脚本轮　A　越界归因跑通、失败捕获静默分析、兼容清单就绪

- 跑通 B 的 analyze_residual_overflow.py（B=3e69ab5）：候选臂归因可以——8 个越界样本、
  宽残差 1.0230× 满幅（超 0.20 dB）、增益后 0.4074× 满幅且余量 +7.80 dB、越界 0；
  辅路径模型整数重放 prediction 失配 0/15871；首次越界全局帧 114687，保护 0.63 ms 后停机；
  增长窗口 41.94 ms < 100 ms，增长趋势记未知。零系数臂因模型被覆盖而归因停止。
- 静默分析既有失败捕获：零系数臂末段一个块内抬升 25 dB、持续压满 3 个块（0.13 s，满幅 20.6%），
  属失控但 completed 未被抓；候选臂满幅仅 26 样本、最长连续 24 帧，属瞬态。
  按队长指示不把输入满幅当再生证据，零臂依据是那 25 dB 台阶。
- 兼容改动清单（9 项）就绪，未应用；位流+驱动+schema 须同版本发布，混搭拒绝运行。
- 基线可恢复性核实：v2 位流/hwh/驱动在位，v1_audio_replay.bit/hwh 回退位流同时保留。
- 工具注意：B 的脚本在 Windows GBK 控制台会因 U+2212 崩，须 -X utf8。

## 2026-10-27 现场轮　A　复现成功、首次真人扩声、候选稳态有效但语音瞬态触发保护

- 音响出声验证：1 kHz 窄带 +15.9 dB，排除"音响没开"这一解释。
- 原配置复现成功：手机 5 cm / 8-15 / 零系数 / −8 dB，两次均能听出放大；
  60 秒持续 2929687/2929687 帧、completed、计数全 0、无啸叫。
- 首次确认真人扩声：12 cm、−8 dB、零系数，本人"能 / 一般清楚 / 比不开系统更大 / 没有啸叫"。
  5 cm 那次因实跑比预检更响而削顶 1081 样本，判无效。
- 候选在稳态源上有效：白噪两臂，300–360 Hz 占比 0.2281 → 0.0476，压低 6.8 dB（绝对 7.9 dB），
  超过 B 的 4 dB 门槛。
- 候选在真人语音上不可用：零系数正常完成，候选 residual_saturations=8 触发 guard 中断播放；
  prediction 饱和为 0，故是数值溢出而非啸叫；真人语音波峰因数实测 21.4 dB。
- 方法结论：分次比较频带必须用稳态源（手机内容导致占比漂移约 30 dB，曾使两臂方向相反）。
- 撤回：环路 −19 dB 正增益可行、候选压低 12 dB、历史 5 cm 实为 78 cm、5 cm 可作工作点、
  10.9 dB 饱和余量、把手机播放写成真人说话。

## 2026-10-26 夜　统筹　安排次日成功复现并更正状态依据

- 按队长要求同步 A=2b51694、B=254b8e9、C=fa13877 至 [STATE](../STATE.md)：保留两次主观成功，撤回由后续松线倒推历史原因、单项未检出归咎几何及系数和判根因的解释。
- [10/27计划](../ref/development-plan.md#2026-10-27-执行顺序) 改为 A 复现、B 差异分析、C 修复测量入口并行；取消机械补满重复次数，保留现有保护与功能/代码冻结日期。
- 原始实验记录及旧计划JSON未改写；本次未修改算法、驱动、契约或操板。临时提示词由聊天交付，Git推送不代表三线已接收。

## 2026-10-26 夜　统筹　按队长要求修订成功复现与三线责任

- 在 [WORKFLOW](../WORKFLOW.md#成功结果如何继续) 增加成功配置优先复现、事实/解释分离和真人确认规则；同步 [分工](../lines/README.md) 及长期角色说明。
- 修正 [交付规则](../ref/development-plan.md#交付判据-r1r52026-10-25-新增冻结期生效)：失败须及时回传，包完整性不替代现场有效性，已有基线按依赖继续。
- 本次为队长授权的公共规则修订；未改接口、算法、保护或执行入口。授权摘录见 [协作记录](../../report/ai-records/README.md)。

## 2026-10-26 夜–27　A　r4 停在正向对照；唯一成功扩声案例的复现计划入库

- 核对并部署 C 的 c-new-layout-r4（338417 B，sha256 b9ad6dab…），绑定
  fixture room_v1_20261026b / model 01c9102a / Q20 6118e85d，与要求一致。
- 两次执行各跑 4 个试验后停在 `positive_control_failed: gate_at_noise_floor`：
  1.02 s 定音在 100 cm 侧对几何下到麦克风已弱且扩散，构不成可检测单音；实测"放定音时不比静音更响"。
  判为判据与几何不匹配，归 C；同类失败两次，按流程不再跑第三次。
- 第一次失败原因另行查明：我的自动应答替操作者回答了"先暂停手机"的 START；第二次已修正。
- 重复性测量 4 次极差 **3.1 dB** → 不支持"麦克风灵敏度漂移"解释，现场操作者的"音源更近"仍成立。
- 新增 reproduce-plan-2026-10-27.json：记录 5 cm/−8 dB 那次确认可辨扩声的完整设置、
  两种竞争解释、当前证据与明天的分步复现协议。
- 撤回："10.9 dB 饱和余量"（LOAD_OK 只是文件校验）。

## 2026-10-26（第三轮）　A　修线后现场准备完成，静默等待 C 的绑定包

- 板端身份核对：bit 61bb71aa / hwh 92b499a3 / replay_trial 2127663；旧失配模型仅存 STALE 名。
- scene-input 补齐：允许增益 [-14..-6]、注入 [-30,-6]、cue 允许条件、前放出厂未动、
  固定源=手机录音、录音增益与 AGC 如实记未知 → 听众定量项固定未测、定性单列。
- 讲话距离由 5 cm 更正为默认 25 cm（5 cm 正常接线下输入削顶）。
- 四份非法现场 JSON 修复，现 0 损坏。
- 本轮保持静默：未跑任何有声试验，未装裸系数，未换低切模型。
- 等待 C=bbc89b2 的 c-new-layout-r3 绑定执行版本；B 的匹配系数到板后做同条件对照。

## 2026-10-26（第二轮）　A　零系数可用窗口被 331 Hz 夹住；麦克风松线使一条结论撤回

- 停用旧失配系数（fixture 为旧夹具、延迟错 57 帧），板上 A/B 证实其比不装模型更差。
- 零系数线上对照：−8 dB 干净但听不出人声；−6 dB 能听到放大但被白噪声样再生盖住；
  −4 dB 更响但更浑浊（331 Hz 占比 0.68）；0 dB 起振。**无"又响又清楚"的点。**
- 麦克风线松导致三次采集判废（ADC 恒 −4.2 dBFS，与激励无关）；重插后底噪 −35.1、无削顶。
  据此撤回"5 cm/−8 dB 确认可用"作为标定点——正常接线同位置会输入削顶。
- 交付 B 要求的开环采集（6 段，源 −6 dBFS，−40 dB 开环）：宽带耦合 **−10…−12 dB**；
  "耦合 +15 dB、满音量自激"作废。
- 自设计低频抑制系数失败：sum|q| 距饱和阈值 6.2 dB，故为**环路发散**而非字宽问题（B 判断正确）。
- 判据新增：读数不随激励变化时先查接线。

## 2026-10-26　统筹　审阅 B 补充并纠正过期状态

- 读取 A=b104f20 及 fetch 后的 B=e9e267b、C=7a2acfd 记录，更新 [STATE](../STATE.md) 中模型失配、既有运行验证和各线已交付状态，保留历史证据不改写。
- [审阅](../../report/analysis/2026-10-24-situation-and-limits.md#工作流修订后对-b-意见的审阅2026-10-26) 采纳现场必要条件，限定现场/离线互证；纠正保护先落盘、SNR电平差及681为BRAM极限等说法。
- 实际执行源码/报告阅读及标量算术复算；未重拟合、未仿真/构建/操板。本次不将新候选收益写成已实现，也不把法规/赛事日期转述当官方核验。

## 2026-10-26　统筹　按队长要求修订失败分支与现场交付流程

- 将问题、前提、完成标志、失败出口及前提变更后的处理并入 [WORKFLOW](../WORKFLOW.md#2-ai-会话的标准动作)，三份角色文档补职责入口。
- 明确必要测量条件自动汇总、保护先停声再落盘、结论撤回同步更新状态；文档检查不等于技术验证。
- [冻结计划](../ref/development-plan.md) 区分功能/代码冻结与后续材料制作；队友转述的外部截止保留待核实。
- 本次为规则与文档修订，未改代码/契约或操板；未将要求标为已实现的检查器能力。用户授权摘录见 [协作记录](../../report/ai-records/README.md)。

## 2026-10-26　A　真人可用窗口实测：当前配置不存在可辨扩声的工作点

- 板卡重启后补完多频带大声测量（8 频带 × 2 次）：最好相干性 0.439，无可用频带；
  三种测量设计全部失败，根因定位为单段 0.336 s 窗口无法验证冲激响应。
- 量化相干性与电平的关系：源 +12 dB 只换 4–9 dB 信噪比，约一半干扰随信号增长 → 混响拖尾。
- 静音源增益扫描：−6 dB 稳定、−5 dB 啸叫（单模 325 Hz，占比 0.93），估算最大稳定增益 −5.5 dB。
- **纠正**：静音源边界不是可用边界。真人说话下 −12 dB 稳定、−10 dB 接近再生、−6 dB 保护停批，
  −14 dB 听众报"听不出放大"。**从听不出到接近再生仅约 4 dB。**
- 结论：当前声学耦合 + 512 抽头 FIR 下，不存在"真人可辨扩声且不啸叫"的工作点，差约 6 dB 抵消量。
- 交付检查修复（绑定哈希、缺失即 FAIL）；A 分支合入 main（479a570）。

## 2026-10-25　A　交付判据 R1–R5 与驱动路由走查

- 冻结计划新增"交付判据 R1–R5"：禁止过程性回复、检查器退出码即交付判据、
  消息首行必须是 `PACKAGE_COMPLETE <sha256>`、分叉一次列完给默认值、一包一问题。
- 新增 board/audio_replay/test_human_routing.py：把 C 的真人包 10 条提示逐个过驱动路由表，
  不发声、不碰板卡。首次运行 ROUTING_RESULT PASS，同时暴露并修掉了三处路由错误
  （讲话时机在 Codec 静音期内、"听众"误匹配布局提示、无录音时谎称 FIXED_SOURCE 齐全）。

## 2026-10-25　A　v2 位流与连续 60 秒、条件 4 注入、C 的 r1/r2 执行

- 队长批准运行上限 v2；契约 v2 + v1 保留 + 索引更新；RTL 两处参数 488281 → 3000000（仅 2 行）。
- 由 A 分支导出到 D:\a 短路径构建（worktree 路径 108 字符会让 Vivado 报 BD 41-1690）；
  bit 61bb71aa…、hwh 92b499a3…、时序全过、资源与 v1 相同；原件入库 board/audio_replay/v2/。
- 上板跑通连续 60 秒（2929687/2929687 帧、无保护）与停止测试（1.672 s 停止、stop_latency 0.001 s）；
  原始 npz 与时间线导出到 report/verification/audio-replay/v2-runs/。
- 条件 4 用模拟寄存器注入通过：饱和独立停止、保护不被 completed 覆盖、gain 32 位、
  静音失败不谎报。无板卡、无声、无失控。
- live_run 补 before_start 接点与保存失败留证；驱动从 HWH 判定位流能力（pl_contract v1/v2）。
- 执行 C 的 RC0.1-r1：0 dB 第 2 项真实人声 9835 帧（约 0.201 s）保护中止（计数 3/1）。
- 执行 C 的 RC0.1-r2：−14 dB 下 7 项跑通、无一次保护，停在 fir_observation_insufficient。
  回包入库；−14 dB 工作点可用。
- 发布检查新增"发送方自检"与资产绑定规则；C 指出的"v2 原件未入库"已补齐（83ed775）。

## 2026-10-25　A　连续运行入口、live_run 修正、RC0 执行与自检规则

- 新增 `live_run.py`（a-continuous-v1）并上板验证：9.5 s 跑满、时间线 469 点、停止 0.773 s 响应、
  异常 disarm+mute。60 s 只差 `MAX_RUN_FRAMES`（提案已提，待批）。
- 修 `live_run` 的 microphone/reference 通道标签写反；三点与 `replay_trial` 对齐（≤0.004 dB）。
- 成对对照（同增益只改 bypass）：−12 dB 无差别；−8 dB cancel 低 5.5 dB。
- 录音→关麦→回放：操作者确认"比较清楚"，麦克风与音响均正常；干净放音拐点在 −14 与 −8 dB 之间。
- 执行 C 的 c-sprint-rc0 两次，均在 path-gate 失败：捕获窗 0 帧（seconds=1.02 < 1.42 的约束），
  回包入库。据此在冻结计划新增"发送方自检"规则。

## 2026-10-25　A　发布检查新增"发送方自检"规则

- C 的 RC0 两次在同一点失败（path-gate 捕获窗 0 帧，参数可纸笔算），验证成本转移到了板卡与现场。
- 在 docs/ref/development-plan.md 的发布检查里新增：发送方软件夹具自检 + preflight.json + A 只读 all_ok
  + 缺陷分类累计三次上报；A 不新建工具。
- 细节见该计划"发送方自检"小节。

## 2026-10-25　统筹　修正跨设备交接并准备 GitHub A 分支交付

- 按队长纠正，将上一轮复核、冻结计划、长期角色说明和证据纳入 A 分支交付；本机路径不能作为其他设备唯一入口。
- 在 [冻结计划](../ref/development-plan.md#跨设备获取本轮材料) 增加仓库/分支/提交取得方式、相对路径索引和已有 ZIP 获取步骤；B/C 可保持本线分支读取 A 的材料。
- 保存复核所用相位函数片段，使反例不依赖未提交临时目录；不上传新增原始录音、凭据或临时工作树。
- 已执行 git pull --rebase --autostash origin A，远端同步无冲突；本轮无算法、接口或现场变更。最终提交和推送结果在发布消息核验。

## 2026-10-25　统筹　归档独立复核并压缩至 10 月 28 日代码冻结

- 按用户期限重排四天并行交付：A 硬件与连续使用，B 分析纠错及有限候选，C 判据与完整实验包；候选、功能和代码冻结节点见 [计划](../ref/development-plan.md)。旧排期完整保存在 archive。
- 保存此前一轮只读复核的 [六问答复](../../report/analysis/2026-10-24-situation-and-limits.md#独立复核答复2026-10-25) 和 [数值证据](../../report/verification/audio-replay/independent-review-2026-10-25.json)，保留送审原文；纠正离线估计冒充实物上限、相位穿越、相干地板及声学增益推断。
- 覆盖 STATE 的争议口径并标记各线执行未在本会话发生；保留板卡占用为上次登记、待现场核实。长期角色提示词不混入一次性任务，启动提示词在聊天交付供人工转发。
- 本次只改文档与证据索引，未改算法/驱动/契约、未上板或发声。文档检查结果在交付时报告；不把计划交付记为代码或声学效果完成。

## 2026-10-24　A　记忆扫描判死抽取方案；C 要的 lowband2-return.zip 已入库

- 8×/16× 抽取 + 384…3072 抽头：300–1000 Hz 残差稳定在 −12.8 dB（63–250 ms），超过 250 ms 变差。
  地板由相干 0.87–0.89 决定，不是抽头 → B 的抽取方案也到不了 −18 dB；天花板 +11…+13 dB。
- 真正可行：近讲麦克风（头戴/领夹），抬语音、降耦合，不需改 RTL。
- C 的 lowband2-return.zip（5.61 MB，39 项，manifest 逐文件 sha256）已放
  report/verification/audio-replay/lowband2-return.zip。
- 证据：`a-memory-sweep-2026-10-24.json`、512 报告 §24。

## 2026-10-24　A　指向测试判死物理解耦：降耦 5.7 dB 只换来 <2 dB 可用增益

- 现场约束：不能严格 1.0/1.5 m，故用同距离的麦克风侧放替代距离扫描。
- 直立 16 段 vs 侧放 20 段（均 -12 dBFS 注入、直通、hp40，B 的脚本出阈值）：
  宽带 |H| +0.38 → -5.34 dB（降 5.72）；必要阈值 +7.01 → +8.63；相位一致 +9.53 → +10.38。
- 原因：限制点从 441 Hz 移到 358 Hz，该处 CD 由 +12.32 掉到 +8.16，把降耦收益吃掉。
- 结论：物理解耦不是解法，瓶颈是低频记忆长度 → 只剩 B 的 8× 抽取 + 384 抽头。
- 证据：`a-orientation-2026-10-24.json`。

## 2026-10-24　A　分带补到 12 kHz：9131 Hz 不是限制点，435 Hz 才是

- 用 lowband2 的 16 段重算：300-1000 -5.42 dB；3400-6000 -6.77；8600-10250 -11.42；
  9131 Hz 处 -17.39 dB（相干 0.75）。
- 9131 Hz 峰在稳定试次与开环标定段（8744 Hz、Q≈293）里都出现 → 是音响/房间共振，不是环路自激。
- 相位拟合延迟按频段 135/124/126/111 样本，残差 24–108 度 → 相位不是纯延迟，模型必须 FIR。
- B 的 diagnose_peak_margin.py 在同样 16 段上：必要 +7.01 dB @441 Hz、相位一致 +9.53 dB @460 Hz。
- 证据：`a-band-12k-2026-10-24.json`；给 B 的 16 段包 `for_b_lowband.zip`（3.72 MB）。

## 2026-10-24　A　带限无效，低频标定加强得 +5.42 dB

- 带通 300–3400（6 阶）：8.2–8.6 kHz 环路项降到 −35.75 dB，但限制点在 381 Hz，
  cancel 可稳增益只从 +3.65 → +3.89 dB。带限不是出路。
- 低频标定加强（16 段、−12 dBFS、相干 0.81→0.93）重拟合：300–1000 dB 的
  max|H−Ĥ| = −5.42 dB @435 Hz → 预测可稳 +5.42 dB。
- 上板：0 dB 稳 2/2，+3 dB 稳 1/2，主频 9131 Hz / 457 Hz。预测与实测吻合。
- 距"当扩音器用"（约 +20 dB）仍差约 15 dB。
- 证据：`a-lowband-2026-10-24.json`、512 报告 §23。

## 2026-10-24　A　麦克风是线松脱（已修）+ 外部讲话扩声仍未做成

- 重插 VCC/GND/LINE_IN 后麦克风恢复：8 s 讲话 −11.9 dBFS、14 个满幅样本，MIC_DEAD 作废。
- 修复后两次扩声测量（bypass 9 s，各无保护无饱和）：
  −9 dB mic −35.0/峰值 −17.8、ref 峰值 −26.8，操作者「白噪声为主 + 轻微尖啸」；
  −15 dB mic −30.3/峰值 −11.8、ref 峰值 −26.8，操作者「只有沙沙声，比之前更小」。
- 结论：bypass 负增益不可能听起来像扩音；≥0 dB 才可听，而 0 dB 因 |H|>0 dB 必自激。
  差距 3–9 dB，与夹具 4.7 dB 重复性同量级。
- 证据：`a-speech-entry-2026-10-24.json`。

## 2026-10-24　A　人声入口被麦克风硬故障阻断

- 外部讲话→扩声两次尝试（−15 / −9 dB bypass，各 9 s）：无保护、无饱和、包络平稳，
  ref 比 mic 低对应增益，说明系统确实在放麦克风信号；但麦克风只有底噪，没有语音。
- 8 s 纯麦克风检查（贴合讲话、不播放）：mic −37.7 dBFS、包络八段不动 → `MIC_DEAD`。
- 回溯：重标定时 mic −18.1 正常，门禁漂移测试时 −29…−34 正常；故障出现在 0 dB candidate 饱和之后。
- 证据：`a-speech-entry-2026-10-24.json`。

## 2026-10-24　A　夹具电平重复性 4.7 dB，C 的门禁无法通过

- 6 次相同 1 kHz −20 dBFS 定音：麦克风 −32.85…−29.36 dBFS，极差 4.71、σ 1.59。
- C 的 c-room-ready-v1 两次 RUN 均停在同一门禁；两次 SPEECH 分别停 gate_tone_not_observed 与 gate_drift，
  人声项一次都没采到。
- 结论：本夹具绝对 ASG 不可引用；1.5 dB 门禁不可满足；跨场次差异不能排除是同一因素。
- 证据：`a-fixture-repeatability.json`、512 报告 §22。

## 2026-10-24　A　门禁版对照：B 掩模系数不如现场重拟合

- 验证 B 的 `candidate_512_session_20261024.json`：Q20 sha256 `e353c10e…` 一致，文件 sha 因序列化不同。
- 同一门禁场次对照：A 重拟合 −9 dB 稳（−37.2）、−3/0 啸叫（8.35 kHz）；
  B 掩模 −9 dB 即啸叫（405 Hz 顶满幅）、−6/−3 啸叫（8.36/8.35 kHz）。
- 发现门禁基线会漂（两次差 10 dB），改为静置 8 s + 连续 3 次 1.2 dB 内取中位数。
- 发现纯音测延迟是周期模糊（70/118/21），只认白噪声 124/125。
- 证据：`a-model-ab-2026-10-24.json`、512 报告 §21。

## 2026-10-23　A　驱动证据层按 C 规格升级 + 8.4 kHz 相位定位

- 按 C 的 a-replay-evidence-v2 规格重写 `replay_trial.py` 证据段：计数解包、唯一保存路径、
  `source_pcm16` 入库、`source_end_frame_exclusive`/`source_schedule_verified`、`.status.json` 边车。
- C 的 `check_a_driver.py` 官方验收 **8/8、accepted=true**（驱动 sha256 `2127663…`，
  由用户在宿主 PowerShell 执行；沙箱内因工作区继承 `Everyone:(DENY)(DC)` 无法删临时目录）。
- 256 模型补零加载实证：`logical_taps=256 / loaded_taps=512 / coefficient_status=0x200A /
  bit_exact 0 处不符`。证据：`a-loading-compatibility.json`。
- 抵消惩罚逐频段：300–1000 −11.16 dB、1000–3000 −10.77、3000–6000 −4.47、
  8200–8600 **+0.29（最差 +1.06）**、6000–12000 +0.07（最差 +4.65）。
  8.4 kHz 幅度准（9.17 vs 9.14 dB）但相位差约 33°，`|H−Ĥ| ≈ |H|`。
  证据：`a-cancellation-penalty.json`、512 报告 §17。

## 2026-10-23　A　实时扩声入口 + 板端版本核对（新分工）

- 新增 oard/audio_replay/live_pa.py：一次装载 overlay、一次装载模型，连续跑 N 段（每段 ≤9.5 s），
  话筒→PL→音响；ypass=1 普通扩声、ypass=0 带抵消扩声。导入不发声。
- 新增 oard/audio_replay/live_pa.ipynb：4 个代码格（1 核对哈希/2 设参数/3 发声/4 汇总），只有格 3 发声。
- 部署到板卡 /home/xilinx/jupyter_notebooks/base/audio/audio_live/（512 位流 8b2426f4…、
  模型 model_room_512.json 7fae6af…、live_pa.py 531ffe5…）。
- 连通性自检（不发人声，−18 dB 旁路 3 s）：completed_frames=146484、status x00008001、
  三路饱和计数全 0、捕获 plumb_01_b1_g516.npz 已存。
- 核对接口位段：captured 是 **16 位**，所以 capture_status[16:1]=captured；
  x00008001 = done + captured=16384（**不是削顶**），x00020000 = 配置被拒（bit17）。
- 更正：本轮早先怀疑"gain_clip 标志与计数不一致"是我数错位宽，RTL 与读数自洽，无缺陷。
- STATE 覆盖 A 段（新职责、实时扩声现状、接口位段、夹具=0.5 m 房间）。
## 2026-10-23　A　按队长要求更新三线分工与人工交接

- 明确 A 维护底层驱动、硬件集成及现场，B 维护算法与事前预测，C 维护测量/复算并整合完整实验包；按功能划定混合目录的文件边界。
- 重写三份可全文转发的 AI 提示词，加入第一轮任务、准确文件/代码格定位、批次停止分支和结果包交付；统一人工消息转发，不使用 REQUESTS 待办表。
- 同步 AGENTS、WORKFLOW、开发规范和导航，消除旧分支/权限及角色归属冲突。按用户指定交 A 分支，供队长后续合并 main。
- 验证：`python scripts/check_docs.py` 与 `git diff --check`；本次仅文档与规则修改，未执行算法测试、综合或实物实验，未改变契约语义。
- 依据：[用户授权摘录](../../report/ai-records/README.md#2026-10-23-队长要求的新分工授权摘录与采用说明)；交付：[分工及提示词入口](../lines/README.md)。

## 2026-10-22　A　512 抽头改建与箱体复测

- 修 src/rtl/audio_pl_replay.v 的三处前向引用（scheduled/u_ready/rm 声明前使用）——
  仓库里这版源码原本重建不出已发布的位流，xvlog 直接报错。
- TAPS 256→512，驱动去掉硬编码 256（
esidual_tools、
eplay_tools、
eplay_trial）。
  重建后 WNS +0.287 ns、WHS +0.034 ns、LUT 6.61 %、BRAM 80 %，位流 sha256 8b2426f4…。
  沙箱内 BD 解析失败（BD 41-1690），宿主 PowerShell 一次通过——环境限制，非设计问题。
- 回归：512 位流 + 256 模型补零 → 控制项 −18.1 dBFS、延迟 114 帧、bit-exact，与 256 基线一致。
- 箱体 512 标定改用按 RMS 定标的合成白噪声（记录噪声分段峰值归一化后实际太小，采集被底噪主导）：
  256/384/512 验证集降低 6.22/6.34/6.49 dB，max|H| 26.45 dB @417 Hz 与独立实测 26.3 dB 吻合。
- 箱体起振点：旁路 −24、抵消 −13.5 仍起振，**512 没有改善**（ASG 仍约 10.8 dB）。
  证据：[512 报告](../../report/verification/audio-replay/2026-10-22-512-taps.md)。
# 项目进度（时间线，只追加）

## 2026-11-02 C 延长慢采集阶段预算并区分实体提示

据用户真板训练6×8.6秒超io30，C改io150、保留compute/run30。接口v8分开quiet0100/capturing0101；定位旧embedded没有speaking转换，按现有实际arm回读和哈希绑定的21969帧cue+0.1秒尾声亮0010，当前A安全armed写灯启用，其他适配deferred保护保留。64项受影响C软件检查与141文档检查通过；98663a4干净源码冻结新ZIP，独立解压及全部哈希通过，原版A/冻结C/真实B子进程配模拟MMIO与虚拟6×8.6秒训练完整到ready，观测到0010/0100/0101，未因阶段时限中止。纯AST执行A的cue生成函数取帧数，无导入硬件/操板；A/B原件未改，overlay复用/PS稳定性问题仍保留。[绑定来源](../../report/verification/recal-product-v1/io150-assets.json)、[v8](../contracts/recal-runtime-v8.md)、[新包路径](../ref/recal-product.md#本轮慢采集与灯光复核包io150)。


## 2026-11-02 C 按8799原件重建冷启动/CAL复核包

首次fetch远端A仍996bd38，随后取得用户确认的新b1826610（功能31eef5a1），根/v3 helper及原manifest逐项吻合8799完整SHA；原契约已同步新helper/driver并移除失效阻塞，保留PS卡死及CAL待板复核两项。C从统一源生成配置/清单四处身份，连同81b冷启动/显式CAL恢复和quiet4重建，未手改旧ZIP、未改B阈值或service文件。6fd55d1干净源码重建根目录整包，独立解压四处钉值/全部载荷/文档/导入后再次验包均通过；原版新A+冻结C+真实B子进程配模拟冷I2C与独占文件，三次无声重说路径各异、失败后新CAL到ready通过。新包仅A看守复核，正式演示仍受PS稳定性阻塞。[原件核对](../../report/verification/recal-product-v1/bootfix-8799-assets.json)、[准确路径](../ref/recal-product.md#本轮上电与cal复核包a-b1826610--功能31eef5a1)。


## 2026-11-02 C 修上电AUX门槛与失败CAL恢复

据A真板断电默认0x00/aux_db失败，C选择prepare后核AUX，仅提前严格核代码/位流等身份，新增configuration_ready状态；普通场景失败安全abort后可长按BTN0新scene，不再因B HARDWARE_ERROR永久屏蔽CAL，身份混搭/无法停声锁定保留。quiet改4，speech因131072源RAM保留2.5。47项受影响软件检查及140文档检查通过；原版A实际getter/setter+prepare配模拟I2C和真实B完整到ready，无构造预写/人工步骤。另原版A两次input撞独占NPZ，隔离仅绑定request.run_dir后两次成功，给A这一处必要单行同步，未改A源码。[冷启动](../../report/verification/recal-product-v1/boot-cold-original-a.json)、[路径复现](../../report/verification/recal-product-v1/boot-retry-path-audit.json)、[接口v7](../contracts/recal-runtime-v7.md)、[说明](../ref/recal-product.md#上电与重试修复c源码a-5b0648c)。


## 2026-11-02 C 最终冻结A7bd功能b610并清空阻塞

按A最终指令只取八项运行时及原manifest九文件，逐SHA核验且与功能提交b610相同；不包验证脚本。12项取消边界全部通过，原版A工厂维护链路通过；2137949干净源码最终正常product冻结开放部署及维护，B判据原字节不变。42项软件/3项打包回归、139文档检查通过；34载荷/35文件最终ZIP独立解压后check与维护exit0，两个scene完整模拟、实际模式切换/30秒帧结束及单回包身份/文件SHA通过。接口v6固定bootstrap维护模型、本轮CAL自动生成正式模型和单一回包清单；按A sudo实测将C常驻服务运行身份固定root，导出仅绑定当前包scene/计算回执并包含维护JSON。C自行完成冻结核验，不再索取A/B字段或重采原件，未操板。[固定载荷与模型](../../report/verification/recal-product-v1/final-assets.json)、[全部取消检查](../../report/verification/recal-product-v1/final-runtime-check.json)、[v6](../contracts/recal-runtime-v6.md)、[一次窗口命令](../ref/recal-product.md)。


## 2026-11-02 C 按A593原字节重冻结并开放维护自检

用户要求新包adapter_check_allowed=true并放仓库根目录；A旧包部署/校验回执按现场反馈保存。核A八项载荷与原manifest，新的driver/helper身份同步，B原字节不动。12项预取消/初始化取消定向检查关闭五条路径的旧阻塞，仅父类prepare两项仍失败；维护链路通过，7项既有受影响检查通过，两个scene真实B完整模拟接入通过。e6adcf2干净源码冻结根目录35载荷/36文件新包，独立解压逐SHA与文档链接通过，冻结C main+原版A工厂的模拟维护自检exit0；adapter_check_allowed=true，正式缺口仅prepare。接口变更v5按用户授权把维护开放与正式部署门槛分开；C维护创建对象使用显式当前模型fixture。只向A提供prepare这一处必要修正，B无新增请求，未操板。[原版方法检查](../../report/verification/recal-product-v1/a593-runtime-check.json)、[软件](../../report/verification/recal-product-v1/a593-software.json)、[新载荷](../../report/verification/recal-product-v1/a593-assets.json)、[维护v5](../contracts/recal-runtime-v5.md)、[准确命令](../ref/recal-product.md#a在板卡执行维护自检)。


## 2026-11-02 C 接通A280原版工厂与B完整数值流程

接口变更v4：C接收source_model_sha256/scene绑定副本，逐项核验内容及Q20后原子提交；从原NPZ completed_frames区分完整运行与16384帧环窗；封装不可成为有效模型的静音启动零模型，四灯图例保留LD3实际模式。A原版工厂+C状态机+B子进程仅替换硬件叶子，连续两个scene均ready，首个运行ended；75项受影响软件检查及137文档检查通过。5230e0c干净源码冻结33载荷审阅ZIP，独立解压、A/B字节、零模型格式、B worker、包内链接及三种启动门槛核验通过；原链接失败包另名保留。复现预取消install仍进入driver，以及初始化中取消缺少before_start；只向A请求这一取消边界修正，B无新增任务。A现场消息与C离线结果分别归档，未操板。[入口与停止证据](../../report/verification/recal-product-v1/a280-entry-review.json)、[固定载荷](../../report/verification/recal-product-v1/a280-assets.json)、[v4](../contracts/recal-runtime-v4.md)、[操作单](../ref/recal-product.md)。


## 2026-11-01 C 收口A22/B.1重组与必要阻塞复现

按用户“仅真实需要改动才留言”收束，接B 0b09ef6原字节与A22描述；72项受影响检查通过，B正负移位/少段验证修正确认，同一原件结论保持采集资格/独立性拒收。C吸收旧调用晚返回、隔离文件与嵌入提示窗格式，未让硬件端隐式重扫档。A原版training/input私有名错误、install JSON解析及后续gain/count问题、预取消仍调用driver经隔离叶子I/O复现；run墙钟/音频口径由源码及A既有30秒回执核实；诊断补丁未入候选。ff9e5c8干净源码冻结31载荷本地审阅包，独立解压/源SHA/B worker/文档核验通过，默认/维护/现场均在导入硬件前拒绝。只给A必要4项，不追加B任务，未操板。[A复现](../../report/verification/recal-product-v1/a22-runtime-audit.json)、[72项](../../report/verification/recal-product-v1/closeout-software.json)、[包核验](../../report/verification/recal-product-v1/closeout-package-check.json)、[同一数据](../../report/verification/recal-product-v1/closeout-data-review.json)、[收口说明](../ref/recal-product.md#本轮收口a-22c88bb--b-0b09ef6)。


## 2026-11-01 C 接A a3f516f与B冻结身份并复核现有原件

接口变更：交冻结接入v3，直接调用B 2ccf746 identity/evaluate，ATTEMPTS原样及30秒预算，包/每轮/计算回包绑定版本SHA。同一入口加A维护检查与显式当前模型SHA；原版A factory经C main调用、底层叶子I/O替换验证，105项相关软件通过。固定A根/发布3549及8项manifest；接双哈希/applies_at，次捕获生效未获回读不提交current。只读复算已有八段16382帧，全训练拒收/验证同源；去首段5段仅诊断fit通过，不升格验收。1505a17干净源码冻结30载荷本地包，解压哈希/文档/B身份worker通过；维护参数可用，默认普通流程保留prepared_capture阻塞，C未操板。另归档A后续真人30秒回执的来源与听感范围，不混源码。[接口](../contracts/recal-runtime-v3.md)、[105项](../../report/verification/recal-product-v1/frozen-integration.json)、[包核验](../../report/verification/recal-product-v1/frozen-package-check.json)、[现有数据](../../report/verification/recal-product-v1/frozen-data-review.json)、[A/B操作](../ref/recal-product.md#c给ab的一次性交接)。


## 2026-11-01 C 对接A整机适配与B真实evaluate

接口变更：C交整机扩展v2，允许A实施原子cue_input，以匹配的ready事件约束讲话提示；保留prepared_capture缺项阻塞。接入B 0bdf7fa原字节，自带30秒时限和三档6/2段源计划；区分讲话健康与激励资格，保存独立预测口径，补两验证段拒收。95项软件检查通过，真实B子进程配模拟采集到ready；A原包8/8但hw_api根/包分裂、六段计划变单段、安装hash混填经离线调用确认，B负延迟对齐已复现。90a96ac干净源码冻结27项载荷审阅包，独立解压/身份核对/B worker通过，真实和混合模拟启动均退出2。不改A/B实现、不操板、不要求重跑有效原件。[接口](../contracts/recal-runtime-v2.md)、[95项](../../report/verification/recal-product-v1/runtime-integration.json)、[包核验](../../report/verification/recal-product-v1/runtime-package-check.json)、[交付审计](../../report/verification/recal-product-v1/a-b-delivery-audit.json)、[一次性交接](../ref/recal-product.md#c给ab的一次性交接)。


## 2026-11-01 C 承接B判定库与三项确认

接口变更：新增recal-policy-consumer-v1扩展，B契约按edfa698原样引入。C显式要求三点及采集/拟合齐全，绑定本轮estimate_lag与训练原件；四类cause分别停声/无法评价/拒收，原回执留存，有限激励重试只匹配预封装下一档。B的0 dB SNR与30%门控阈值未改。相关67项软件检查通过，B七文件原字节一致；8份已存B输出只做字段映射，D3为构造样例，未声称新实测或原PCM重算。175e469干净源码冻结新版本地ZIP，独立解压入口/回包/B库导入通过，实体模式仍拒绝。另只读确认A=31882e0已提供灯键实测，未再沿用旧缺I/O结论。实体适配/拟合包装与统一现场验收仍待交付，未操板。[消费接口](../contracts/recal-policy-consumer-v1.md)、[检查回执](../../report/verification/recal-product-v1/b-policy-integration.json)、[包身份](../../report/verification/recal-product-v1/policy-package-check.json)、[操作说明](../ref/recal-product.md)。

## 2026-11-01 C 交常驻重标定产品软件v1

核对main=f378262缺实体I/O及即时停止能力后，先交最小接口和A/B/C文件边界，使用模拟硬件与固定算法返回独立开发。实现唯一recal_entry、显式状态机、可终止B子进程、配置身份绑定、独立验证后原子模型安装、真实单次结束与多布局单回包；复用assembler与Q20检查，不改A/B实现。21项软件用例、Bash语法、独立解压模拟到ready及启动拒绝/回包核验通过；首次文件句柄/路径失败、阶段增益与坏提示窗纠错保留。真实适配/灯键/服务安装及两布局现场未执行，安装包不标实物就绪。[接口](../contracts/recal-product-v1.md)、[操作](../ref/recal-product.md)、[机器回执](../../report/verification/recal-product-v1/package-check.json)、[任务与纠错](../../report/ai-records/recal-product-v1.md)。

## 2026-10-30 C 修正集成树五项历史验收失败

取得5c43d62并原样复现delivery四项/tail一项失败，确认两项源钉值属于be3200e r1，不重钉为现行字节。2e7c205改测试指向SHA固定的原ZIP解压根并保持五项哈希校验，源篡改仍D2拒绝；registry不再钉总数或旧文件哈希，旧默认缺项仍拒绝、不改生产选择。C及集成副本定向20/20，v3载荷10/10，C文档126份零错误；正式集成目录文档与全379由A按原计划执行。认可C三栏metric与A现行README入口，未改硬件/模型或操板。[证据](../../materials/work/c/integration-review-5c43d62.json)、[历史作用域](../ref/cold-start-reproduction.md#在后续集成树中复核历史r1)。

## 2026-10-30 C 查明系统代理差异并成功推送

用户要求继续尝试后，读取Windows启用的本机代理127.0.0.1:7897，以命令级http.proxy和HTTPS映射推C成功，远端从330e135更新到862fd2e；原origin与持久Git配置未改。覆盖本线与交付清单的待推状态，保留前次失败记录和离线备份。未修改已验证候选或重新运行无关测试。[取件与后续同步方法](../../materials/work/c/release-checklist.md#远端交接与离线取件)。

## 2026-10-30 C 保留推送失败并导出离线提交包

HTTPS推C遇连接重置及443连接失败，原SSH限时尝试报publickey拒绝；未改origin、可见性或历史。为本轮C提交导出可验证Git bundle，最终候选与报告仍保留本机，未声称远端已同步。[取件与缺件](../../materials/work/c/release-checklist.md)。

## 2026-10-30 C 交独立候选、报告初稿与最小Skill

fetch取得facd3de并完整执行C材料任务，36项派生回包核对一致；从A/B/C固定源码导出独立目录，以A v3完整载荷运行，不合main。9页报告初稿生成并逐页渲染；引用表分清固定频率、普通扩声与零系数60秒。候选10项载荷、模型、导入、独立解压与坏helper拒绝通过；C测试对旧helper的隐式依赖在新组合暴露，改为SHA固定的sim夹具，窗口7/宽残差4通过，首次失败保留。最小Skill及check_docs通过；A/B片段、模板、媒体与真实RAR待收口，未操板或扩平台。[交付入口](../../materials/work/c/release-checklist.md)、[回执](../../materials/work/c/validation.json)、[冲突建议](../../materials/work/c/conflicts.md)、[协作纠错](../../materials/work/c/session-record.md)。

## 2026-10-28 C 验收Ac1单位修复并交既有原件静默入口

固定Ac1快照10/10与单位3/3通过，四差值仅摘要算术核对；接受源停尾窗扩声负结论撤回，保留听众原话。复用现有C脚本增加原manifest/指定round_id三臂模式，8个新增用例通过，仅重验受影响范围/路径；交A一次只读原件回派生JSON，不新增有声试次。纠正“须≤0.336秒或扩捕获”：原2.2秒记录按参数有6619含源帧，待原件静默核实。played报告全局glob与无源回退仍限定，未冒称原件复算完成。[证据及操作](../../report/verification/audio_closed/batch-control.md#2026-10-28-ac1单位修复与原件静默入口)。

> **本文件是只追加的日志，不是现状。** 每条记录是"当时"的状态，越往下越旧，
> 其中"未上传/未验证"等字样只描述当日。**当前状态一律看 [STATE.md](../STATE.md)。**
> 规则：新条目加在最上方；不修改、不删除历史条目；每条结论都应能链到 `report/` 里的证据。

## 2026-10-21 A首次实测ASG：两种激励符号相反，并证实audio_closed输出不通

用 `audio_replay`（先以 −36 dBFS 直放标定出 +23 dB 播放→麦克风耦合）在关盖箱体做逐档成对
对照，2.05 s/项、同增益只改 bypass。**噪声源**：旁路起振 ≈ −19 dB、抵消 ≈ −13.5 dB，ASG ≈ +5.5 dB，
由 −24 dB 旁路再增量反推 `|H|max ≈ +23 dB`（模型 ℓ1 为 +28.5 dB）。**人声源**（`girl_voice`
截 2 s 数字注入）：抵消 −18 dB 起振、旁路 −13.5 dB 起振，ASG ≈ −4.5 dB。两种源给出相反符号；
关掉保护单跑一次，麦克风峰值达 −3.0 dBFS，确认是声学啸叫而非数字自激。

按频点分析解释了差异：噪声源起振在 **232 Hz（抵消）/423 Hz（旁路）**，人声源抵消起振在
**274 Hz**——正好落在 `girl_voice` 基频上，所以真实人声更容易把抵消回路推起来；
B 预测的 381 Hz 共振两次都没成为起振点。

同轮证实 `audio_closed` 的 DAC 输出无效：同批配对（−60/−26/−60 dB）中 −26 dB 环路对麦克风的
贡献只有 **+0.06 dB**（应 +5 dB），而其 ADC 正常（手机近距离播放 −26.7 dBFS）；已排除 RTL 顶层、
驱动与 Codec 配置差异，指向 bitstream。按用户决定退役该 overlay，历史"闭环"结果只证明算术。
另：板卡既有 `source.wav` 实为噪声（平坦度 0.55、帧起伏 3.1 dB）。

证据：[本轮报告](../../report/verification/audio-replay/2026-10-21-asg-field.md)。
未执行：10 s 长窗口、端到端延迟。

## 2026-10-21 A修复PYNQ后台线程事件循环

现场初始化报No current event loop。读取板卡pynq/uio.py确认UIO注册依赖调用线程事件循环；将每次新建线程改为持久单音频工作线程，初始化并保留同一事件循环，启动预检实际工作线程，并记录完整异常栈。部署后重启空闲服务；未触发录音播放。[证据](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A修复SSH服务XRT设备注册

根据现场No Devices Found错误，读取板卡PYNQ源码确认设备注册依赖XILINX_XRT；加载板卡官方环境后枚举到EmbeddedDevice。加入启动脚本、启动设备检查并部署；未加载overlay或发声。[证据](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A修复按钮页录音环境与失败提示

用户报告录音后无后续按钮；读取状态确认多次录音均在导入pynq时失败，未生成录音。切换PYNQ虚拟环境并加入启动导入检查、页面错误直显；保留计划和原链接，仅重启已确认空闲的A服务。[证据](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A通过SSH部署并完成静默选档

获用户授权后直接SSH/SFTP调试，确认板卡旧包并备份更新，逐文件核对15项。真实数据静默选档通过，仅回传JSON，未发声。新增按钮页并核对HTTP待机状态。接口变更：[逐档v2](../contracts/audio-replay-sweep-v2.md)保留原保护上限，追加有间隔的末档并提供按钮交互；硬件不变。[证据](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A修复Notebook保存导致的哈希拒绝

用户返回package阶段停止摘要，无试验项、零发声。将Notebook校验从整文件改为代码格内容摘要，保留其他程序和bit/hwh字节校验，更新完整包及两文件恢复步骤。未拿到板卡Notebook，不能断言此次只改了输出；本次未上板。[修复证据](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A补齐逐档增益批次

根据用户一次性交付要求，新增已有标定数据静默选档和逐档抵消→旁路运行器，固定整批声源电平并自动保存配对/停止原因；完整包从10项更新为13项。接口变更：新增[audio-replay-sweep-v1](../contracts/audio-replay-sweep-v1.md)，旧硬件/接口保留。执行语法、打包与文档检查，未运行本版回归或上板，真实档位留待板卡数据计算。[实现记录](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A同步微信协调规范并保留交付

按用户授权处理REQUESTS删除/修改及STATE冲突，将远端main `18681fc`变基合入A。保留A程序和证据，撤掉旧诉求表；历史条目仅移除已删除文件的失效链接，事实内容保留。代码与交付ZIP未改，未操作板卡。B/C分支已取回，C代码未合入A。见[交付记录](../../report/verification/audio-replay/README.md)；协调采用用户微信转发，仓库保存全局记忆。

## 2026-10-20 A线交付预录语音程序与独立接口

用户要求手机录好后停止外放、音响播放同时实时采样。A交付独立audio_replay RTL、bit/hwh、驱动与三格Notebook完整包；70项软件检查、RTL仿真及最终构建通过。首次构建时序失败已修复并保留证据。未操作板卡，真实听感仍待一次现场执行。接口变更：新增[audio-replay-v1](../contracts/audio-replay-v1.md)，旧接口保持不变；数字源加入实际输出，B/C消费注意事项见REQUESTS的R-005/R-006。[交付与检查证据](../../report/verification/audio-replay/README.md)。

## 2026-10-20 A线澄清二次确认并修正文案

用户提供第二次摘要：模型范围已正常生成 `−35 dB` 单档，第一次 `READY` 已通过；脚本第二次提示要求 `START`，用户再次输入 `READY`，触发 `operator_cancel_before_start`。`trials=[]`、发声0秒，没有现场效果证据。已将第二次提示改为明确的“第二次确认：输入 START 才开始旁路/抵消配对”，并同步Notebook预检SHA和操作包；最新版尚未上传板卡。详见[现场记录](../../report/verification/field-validation/model-bound-zero-playback-2026-10-20.md)。

## 2026-10-20 A线现场批次因模型增益上限零播放

用户提供的 `field_651b97b20f6d/summary.json` 显示配置核验通过，候选模型 `L1=26.744`，估算小增益上限 `−28.545 dB`，扣除6 dB保护量后运行上限为 `−34.545 dB`。原计划从 `−30 dB` 开始，故 `gain_levels_db=[]`、`trials=[]`、`sound_seconds_completed=0`，脚本安全停止；无现场音频结论。A 已在本地将起点改为 `−35 dB`，该候选模型可生成一组成对档位，预计总发声4秒。新版尚未上传板卡，需下次现场前完成静音核验。具体证据和给B/C的事项见[现场记录](../../report/verification/field-validation/model-bound-zero-playback-2026-10-20.md)。


## 2026-10-30 交参赛材料：离线教程、报告片段、集成清单、视频图

按队长 `facd3de`（`materials/prompts/b.txt` + `submission-plan.md` + `video-plan.md`）做本轮材料。
**不新增算法探索、不操板、模型与系数未改。**

**1 离线教程 `materials/learning/index.html`**（+ `assets/tutorial.css`、`assets/tutorial.js`，共约 124 KB）
面向"有数电基础、没有 DSP 背景"的队友，12 节，两个入口（10 分钟概览 / 深入阅读）。
四个可操作演示：
- **反馈环路**：|H| / g / 相位 / 模型幅度误差 / 模型相位误差 / 抵消开关 六个滑杆，
  固定纵轴 −60…+6 dBFS、横轴 0…300 ms，实时算环路增益与 `played/source`。
- **FIR**：3 抽头单步累加（可暂停/复位，表格逐抽头显示乘积与累加器）+ 512 抽头的每帧预算条。
- **宽残差**：按 RTL 的位宽与舍入做**真实整数运算**，同屏对照 v2 / v3 两条路径的中间量与是否越界。
- **捕获窗口**：拖动窗口看"看起来的抑制"怎么被含源/尾段改变。

**关键自查（用 headless Chrome 复跑，可复现）**：零系数 −8 dB → 环路增益 **−3.60 dB**、`played/source` **+3.75 dB**；
候选等效模型 → **−10.02 / +0.02 dB**；0 dB → **+4.40 dB 自激**；FIR 3 抽头 → **p=+0.525、w=+0.075**；
宽残差现场预设 → v2 **0.3982×** / v3 **0.4074×** / 余量 **+7.80 dB** / v2 会停声；
窗口只取尾段 → 0.0% 有源 → 判无效。**控制台 0 错误，无任何外部 URL。**

**2 报告片段 `materials/work/b/algorithm.md`**：问题定义 → 前人工作（3 条路线，引 3 篇原始论文）→
方法（三式 + 参数依据）→ 定点与宽残差 → 标定流程 → 已验证结果（带口径）→ 未测 → 未实施 → 复现 → 参考。
明确区分"可引用 / 不可直接引用（口径不同）/ 未测"三档。

**3 集成清单 `materials/work/b/integration.json`**：模型身份（file `01c9102a…`、Q20 `6118e85d…`、
float `17ea2b34…`、512 抽头、lag_first=1、bias 不装载）、适用性与不适用、六个脚本与十二个测试的
精确路径与引入提交、黄金参考（整数重放的验证结果 0/15871）、数据生成协议、依赖、
**`not_this_line`（RTL / 板端驱动 / v3 证据归 A，不列为本线版本）**、文件名映射
（`model_512_shift+1.json` → `_plus1`，并指出生成器 `diagnose_peak_margin.py:302`）。

**4 视频图 `materials/work/b/video/*.svg`**（1920×1080，可直接叠片）：信号流、FIR 与每帧预算、宽残差先后钳位。
三张都带"原理示意 · 非实测"或"数值来自板上抓包"角标，A 不需要临时截图调画面。

**发现并修正的三处自身问题**（都记在这里，不进其他文档）：
- 演示 1 的候选预设最初用"幅度 46% + 相位 8°"，反算出的 CD 只有 5.2 dB，与 6.37 不符；
  改为由 CD=6.37 与"cancel ≈ open"两条实测反算的 **ε=71%、Δφ=−26.3°**（|H−Ĥ|=0.797、∠≈81°），
  才同时复现 6.37 dB 与 +0.02 dB。
- 宽残差演示里"预测幅度"没夹到 24 位，p 取 +满幅时宽残差算成 −1 而不是 ~2.0；已夹。
- 三处结论框用 `textContent` 写含 `<b>` 的字符串，标签会被当字面显示；改 `innerHTML`。

## 2026-10-28 中午 322 Hz 反解出相位 ±40°；提 g 换不到响度，演示不能讲"更响"

按 A 的 `41fd0d6` 回答两件事（工作点、bypass/cancel 对照设计），并先把 6.37 dB 的口径拆开。
**只从他给的三点反推，没引入新数据、没操板、模型未动。**

**1 三个量必须分开。** CD(322)=6.37 是**残差深度**（bypass 与 cancel 的 residual 之比），衡量模型拟合程度；
**可听收益的量级 = 环路提升 = bypass − open = +3.75 dB**；声学差 4.76 = 3.75 + cancel 过冲 1.01
（cancel 比 open 还低，属过抵消/估计误差，**不能计入收益**）。A 的 evidence 里那句
"removes the loop's +3.75 dB boost and slightly more"是对的，只是报数时别把 4.76 或 6.37 当收益。

**2 反解出 322 Hz 处 H 的相位 ≈ ±39.8°**（`|H|=10^(4.40/20)=1.6596`、`g=0.3981`、实测 boost 3.75
→ `|1−gH|=0.6494` → `cosφ=0.768`）。两个后果：
- `g + |H|_dB` 的 dB 相加**只对幅度界成立**，不能推响度。同相口径会给 9.4 dB，实测 3.75，差 5.7 dB 全在相位上。
  **A 说的"g 每提 1 dB、峰值处约提 3 dB"在这份数据上不成立。**
- 零臂 `played/source = 1/|1−gH|` 现在可算（幅度相位都有）。

**3 提 g 换不到响度：`played/source` 在 g=−6.7 见顶 3.87 dB，−8 dB 时已经 3.75。**
只剩 0.12 dB 空间；越过顶点后继续提 g 反而下降（|1−gH| 增长快于 g）。g > −4.4 之后零臂已自激，
那几行只是外推。**所以"音响不如音源响"不是 g 的问题，是扬声器效率/指向/到听众的距离。**
候选那 5.08 dB 增益余量换成多少输出**离线算不出**——需要 `H−Ĥ` 的**相位**，而离线只有逐点模。
若同相会发散、若反相会小于 1，区间太宽 → 记未知，只能现场同 g 对照测。

**4 工作点：默认 6/15 + 5 cm + g=−8，不换 ADC。** 这是唯一跑过两次 60 秒的配置，冻结前不动。
`ADC×k / 系数×k / g×1/k` 三步后环路与输出都不变（A 自己也这么写），**它买的是"不削顶"，对响度零贡献**，
代价是系数重登记 + 全部电平重标。**改成触发式**：彩排 `bit22=1` 才做，否则演示中途停声比"不够响"严重。
另：**"拉远就更安全"不成立**——A 的记录里 12 cm 与 20 cm 都出现过 `bit22=1`，削顶取决于讲话力度而非距离。

**5 对照设计三段**：A 安全档 −8（两臂都稳，测三点 + 语音 3 遍）；B 临界档 −3（零臂环路 +1.40 必叫、
候选余 3.68 dB），**先候选 30 s 再零臂 ≤2 s**（反过来啸叫会污染候选段）；C 语音臂同 A。
判据：声学差 ≥ 环路提升 − 1.5 dB 且过冲在 ±1.5 dB 内。四个陷阱：提 g 会抬 mic（每档重测 bit22）、
**零臂停声是 bit22 触发的不是啸叫检测**、bypass 臂 mic 高 4.76 dB 会更早顶满、不能靠降整机音量制造成功。

**证据**：[工作点与对照设计](../../report/verification/v3-working-point-2026-10-28/README.md)、
[repro.txt](../../report/verification/v3-working-point-2026-10-28/repro.txt)、
[metrics.json](../../report/verification/v3-working-point-2026-10-28/metrics.json)。
工具 `scripts/answer_v3_working_point.py`；回归 `sim/feedback/test_v3_working_point.py`（12 项，
钉住三点自洽、相位反解与往返、临界 g、`played/source` 上顶与"−8 已贴近顶"）。
全量 202 项通过；check_docs 0 错误 0 警告。

## 2026-10-28 早 按 C 的复验补齐三处边界 + 一处措辞

C 复验 `67d28b2`：点名 8 项全过、原四类反例已修，同范围边界检查 8/11，剩三处 + 一条措辞。全部改完。

1 **归一化浮点容差收到 4·eps（≈8.9e-16）**。修前容差 `1e-6`，±(1+2^-23)=1.000000119 在容差内被夹回，
  整轮分析继续跑（最后判不能归因、退出 2，没有错误放行，但**应更早拒绝**）。现在这类输入直接
  `FAILED:` 退出 2；恰好 ±1.0 仍允许，÷2^23 的取整夹回只计数上报。
  理由：归一化字段超范围说明**字段语义本身不是我以为的那个**（可能是原始码值或 ÷32768），
  不该走到数值比较阶段才暴露——否则中间那些"看起来正常"的余量与首次越界会被人引用。
2 **缺帧域字段标 unknown**。修前缺 `first_frame` 默认 0、`frame_domain_ok` 恒 true、全局帧号照报 0..1023。
  现在缺字段 → `frame_domain="unknown"`，**只把真正缺的那一项标未知**：
  有 `first_frame`、缺 `completed_frames` → 全局帧位置保留真实值（如 1000–3047），只写「闭合核对未知」；
  缺 `first_frame` → 位置标 null，写「全局帧位置未知」。
  按 C 的分寸：**局部分析保留、归因不阻断**（缺 `completed_frames` 只影响"是不是末尾那一圈"的核对，
  不影响 `mic − prediction` 这个局部算术）。
3 **帧号先查整数性**。修前 `int()` 直接截断，0.5 / 1024.5 会被当成 0 / 1024 且退出 0。新增
  `as_frame_index`：bool、非数值、非有限、非整数一律拒绝并退出 2。
4 **措辞**：「RTL 历史为空（从零开始填）」改为「**本地模型重放缺前史**」。抓包只留末尾一圈，
  板上 prediction 本身没有缺，缺的是本地重放的前 taps 帧；所以主路径不受影响，只有辅路径前 taps+1 帧不可信。
  另把主路径 note 的"prediction 不可信"写明是**本地重放的 `pred_rep`**——板上 `pred_rec` 是落盘的记录事实，
  永远可信；两者混着说会让人以为板上的 prediction 也残缺。

用例 26 → 31 项；全量 190 项通过；`check_docs` 0/0。`repro.txt` 重跑后 A/B 段数字逐字相同，
C 段身份门反例仍是「归因：停止」+ `exit=2`。模型与系数未动。

**C 验收 `e730b5b` 后补的两处**（点名 4/4、C 改动范围 5/5 通过；代码本来就对，是我的文字写错）：
① "全为 null"改成"缺哪项标哪项"——有 `first_frame` 时位置保留、只标闭合未知（新增用例钉住）；
② note 明确 `pred_rep` vs `pred_rec`。C 现用代码没有 `frame_domain_ok` 旧字段依赖，不需要适配器。

## 2026-10-27 22:00 按 C 的四处缺口修工具；对 v3 上板后两问给结论

**1 工具四处缺口（C 逐条指出，全部成立）**
- 归一化浮点被混作 unsigned24：按值域猜编码会让 **+1.0 → −2^23**，且 **2.0 被静默夹**仍允许归因。
  改成浮点/整数分开：浮点只收 `|x|≤1`，超了退出 2；恰好 ±1.0 允许但计数上报；整数字段要整数 dtype，
  混合符号又超正满幅一律拒绝。用例 3 条。
- Q20 身份：加**实际数组哈希**（int32 LE，与 manifest 同口径）与 `metadata.coefficients_sha256` 比对，
  不符即停止归因。用例 2 条。
- 帧域：要求 `first_frame + frames == completed_frames` 且 `first_frame ≥ 0`，否则退出 2
  ——C 给的 1024/0/2000 现在被拒。用例 1 条。
- 有效区余量：整窗 / 有效区分开报（mic 峰值、pred 峰值、宽残差 max、余量、增益后 out），
  越界样本分 whole/valid/history；辅路径标"依赖历史、只判有效区"，前缀失配另计。用例 2 条。
- **C 还纠正我一句，接受**：上一封写的"零系数臂 3359 贴轨属于浮点取整"是错的——3359 是真的贴轨，
  `residual_saturations=0` 只因 `pred≡0` 时残差≡麦克风。工具里夹回只计数上报，不再拿来解释贴轨。
- 用例 19 → 26 项。

**2 对 A 的工作点问题：三选一都不对**
- 15 cm 不够：12 cm 峰值 0 dBFS、门限 −6 dBFS，还差 ≥6 dB；12→15 cm 只给 1.94 dB，仍超约 4 dB。
- 降 Codec ADC 增益：整链乘 k，`H→kH`，desired 与 feedback 同比例降 → 环路裕量 +20log10(1/k)，
  输出 −20log10(1/k)，对"音响盖过原声"**零贡献**；系数按 `k·Ĥ` 缩放虽精确，但要重核身份。不划算。
- 提数字增益：唯一能改输出/输入比例的旋钮；候选在 −8 dB 的界 +0.68 → 还有约 8.7 dB 余量。
- 建议顺序：先用 `input_check`（输出静音）量 12/15/20/24 cm，取第一个 <−6 dBFS 的距离（按 12 cm=0 算落在
  24 cm 量级），再在那个距离上把 g 往 −6/−4 试；每档盯输入峰值、v3 bit22、三类饱和计数。
  **注意 `mic = H·u + s`：提 g 会把 mic 一起抬起来，不能先定距离再无限加 g。**
- **12 cm 在现有输入链下不可用**：ADC 满幅＝信息已丢，数字侧补不回来。

**3 对 322 Hz 单点：认可，但四个前提**
① 频率要用**当前夹具实测**的 |H| 峰，不能从 `room_v1_20261026b` 搬；② 主读数用 **cancel vs bypass**
（同 g 同幅度），cancel vs open 会把环路提升算进去——他给的 bypass 49.19→cancel 44.43=4.76 dB 正是这个量，
"6.37 dB 残差深度"要写清分母；③ 幅度在线性区（ADC 不满幅、三类计数 0）；④ 单点单电平不是 ASG。

**4 先要回答的前提：夹具换了但 fixture_id 没换** —— 0.5 m / HP NS1 Pro / 备用麦 若不是
`rewired_512_20261026` 拟合的那套，6.37 dB 测的是"模型在新夹具上的错配程度"，结论与"模型有用"相反。
**5 顺带**：`audio-replay-v3.md` 里"`g ≤ 1`（`control[31:16] ≤ 32768`，Q4.12）"自相矛盾——32768/4096 = 8.0。

## 2026-10-27 20:00 A 跑通静默脚本；13 dB 定位到末 41.94 ms 一块

A（`9b89181`）在板上跑 `b-analyze_residual_overflow-3e69ab5.py`，逐项对上：
有效窗口 15871 帧/325.0 ms、板上计数 0/8/0/0、`|mic|` −0.0 dBFS、`|pred|` −20.3 dBFS、
宽残差 **1.0230×满幅**（超 0.20 dB）、增益后 **0.4074×/+7.80 dB/越界 0**、残差上限 2.511×、
首次越界 16353/全局 114687、保护 31 帧（0.63 ms）后停机、辅路径**失配 0/15871**、归因=可以。
→ **§3 的"乘增益后只到 −7.8 dBFS"是板上事实，不再是我按模型推的。**

**13 dB 的定位变了**：捕获窗内每 2048 帧（41.94 ms）包络为
−38.6/−37.6/−40.2/−39.2/**−26.7/−29.7/−33.2/−12.6** dBFS。前 4 块近静音，第 5 块跳 +12.5 又落回，
末块比前一块高 **+20.6 dB**，越界就在末块。整窗 mic 贴 ±满幅 26 个样本、最长连续 24 帧（0.49 ms）；
残差只贴 8 个，因为只有 pred 为负的那 8 个样本才会让 `mic − pred` 超 +满幅。
**所以不是"整轮高 13 dB"，是"末 42 ms 高上去"。**

**倾向讲话、不是环路（未定案）**：328 Hz 处 `g|H| = 0.398×1.66 = 0.66`，每圈 −3.6 dB、一圈 3.05 ms
→ **≈ −1.18 dB/ms**；真起振应当**单调**地几十 dB/42 ms 变。实测是 **+12.5 → −3.0 → +20.6**，
中途"落"过，一个在爬的环路做不到。所以倾向讲话的起停。**定案要看末块主频与窄带占比**
（环路出 328 Hz 窄线，讲话是共振峰），一行 FFT 即可。

**工具两处改动**：① 加 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`——A 报 Windows GBK
控制台会在 U+2212 上崩（他用 `-X utf8` 绕过的）；② 新增 `--envelope --block N`，逐块打 RMS/峰值/贴轨/
主频/窄带占比。包络的"贴轨"按物理含义算（含合法的 −2^23），与越界判据分开。用例加到 19 项。

**改驱动**：A 问要不要改 `replay_trial` 加时间线或加长捕获环。B 意见**先不改**——这条只影响"那次为什么
那么响"，不影响候选判定；改捕获环会同时动驱动/格式/复算脚本。若队长要可追溯，更省的是下次有声运行前
用同一句话、同位置、输出静音先记一次电平。**由队长定。**

## 2026-10-27 晚 撤回残差越界的机理判断；工具按 C 五类边界修正

A 交来 `fc49529`（候选失败证据 / 宽残差影响清单 / r6 等价性）。**上一版两条判断撤回，一个公式更正。**

**1 撤回"396 Hz 反相放大 1.84 倍是本次机理"。** 实测 `prediction_peak=810578`＝**−20.3 dBFS**（0.0966），
麦克风 0.98–1.00，宽残差只超满幅 **0.8–2.3 %**（+0.07…+0.20 dB），乘 −8 dB 后 **−7.8 dBFS**。
若真是 1.84 倍，pred 要到 0.45 量级（−7 dBFS），与此不符。396 Hz 只是**模型敏感点**，不是现场越界频率。

**2 撤回"零臂正常、候选独自失败"。** 零臂 mic RMS **−4.8 dBFS**、峰值 0.0、残差贴轨 +2197/−1162；
`residual_saturations=0` 只因 `pred≡0` 时残差≡麦克风、永不"超过"24 位。**两臂输入都到 ADC 满幅，
这一轮两臂对照对两臂都无效**——不能用它判候选优劣，也不能说零臂"干净"。

**3 公式更正。** 输出侧容得下的残差是 **`4096/gain_q12` = 4096/1631 = 2.512 倍满幅**，
上一版写成 `2^23/1631`（量纲错）。数值 2.51 不变，**钳位仍比输出约束早 8.0 dB** 这条结论不变。

**4 首次越界定位（用 A 的摘要，全部可复核）。** 抓包 index **16353–16360**（8 个样本贴 +轨），
全局帧 `98334+16353 = 114687`，`completed_frames=114718` → 保护在 **31 帧（0.63 ms）** 后停机。
**计数 8 == 窗口内贴轨 8** ⇒ 窗口外没有更早越界（计数 sticky）——比"不能排除"更强的结论。

**5 最该追的异常：预检与实跑差 13 dB。** 同一天同夹具的 `input_check` 报 12 cm 真人峰值 **−13.11 dBFS**，
实跑却到 0 dBFS。可能是讲话距离/响度、输入链、或环路把电平抬起来，**三种都可能，现有材料分不开**。
不能拿"满幅"三个字替代原因，也不能据此说"再生"。

**6 工具按 C 的五类边界修正**（`scripts/analyze_residual_overflow.py`）：
合法负满幅（`x>2^23−1 或 x<−2^23`，−2^23 合法）、增益**半值远离零**（原来用 Python 向下取整）、
`taps+1` 历史前缀排除在首次越界/余量/计数外、**系数不同即停止归因并退出码 2**、窗口按真实采样率报 ms
（覆盖 <100 ms 记未知）、缺文件/缺字段/无帧硬失败。另把浮点字段四舍五入到 1.0 的情况夹回 24 位，
免得把"浮点取整"当越界。**主路径改成完全用抓包的 mic 与板上 prediction 重建**（不依赖模型），
模型整数重放降为交叉核对。

**7 方案排序改了。** 榜首是**加"麦克风满幅计数"**：零臂输满幅却 `residual_saturations=0`，
这次失败在旧计数体系里完全不可见；没有它，"这一轮有效"永远判不了。宽残差排第二。
宽残差能解决过早钳位、误停、削波失真；**不能解决输入满幅、是否再生、候选优劣**，
也**不能**把这一轮判成"候选通过"。契约按新版本走（audio-replay 出 v3，不动 v2）。

**证据**：[修正版分析](../../report/verification/residual-overflow-2026-10-27/README.md)、
[repro.txt](../../report/verification/residual-overflow-2026-10-27/repro.txt)（含身份门反例：套错模型 → 归因停止、退出码 2）。
回归新增 `sim/feedback/test_residual_overflow_tool.py`（16 项边界用例），全量 175 项通过。

## 2026-10-27 下午 首次残差越界：钳位比输出约束早 8 dB；PS 拓扑在 396 Hz 放大 1.84 倍

按队长（A=d17ff29）的要求，用已有记录定位候选臂那次 `residual_saturations=8` 的保护。
**不改 RTL、不改系数、不重训、不操板。**

**1 事实核对。** `prediction_saturations=0`、`residual_saturations=8`，打印的
`packed_prediction_residual=524288=0x80000=8<<16` 自洽。8 个样本 = 164 µs；396 Hz 一个周期 124 样本，
幅度超满幅 0.05 dB 时每周期约 8.5 个点超线 → 与"刚刚越线"一致（但保护 2 ms 轮询，不能排除本来会继续涨）。
驱动在停机前会存 `replay_trial_guard` 抓包，所以原件是存在的，只是还没到我手上。

**2 钳位点读码确认。** `feedback_fir.v:35-38` 把 `mic − pred` 算成 25 位后**立刻**钳到 ±2^23；
`audio_pl_replay.v:173` 才乘 `gain_q12`。−8 dB → `gain_q12=1631`，输出侧能容纳的残差是
`2^23/1631 = 2.51 倍满幅`，而残差在 1.0 处就被钳 → **早 8.0 dB**。
`prediction_saturations=0` 但残差先炸，是因为 `mic − pred` 是两个各接近满幅的量之差（25 位可到 ±2）。

**3 为什么偏偏在语音上触发。** PS 拓扑单频关系 `residual/mic = 1/(1+g·e^{-j3ω}·H_raw)`，
**分母只取决于模型与增益**。候选在 −8 dB 下最小分母 **0.544 @396.4 Hz**（该带 |Ĥ|=1.13–1.17、
相位 −177…+179°，**反相**）→ 残差放大 **1.84×**；麦克风峰值 0.544（**−5.3 dBFS**）时残差即满幅，
而现场门限是 −6 dBFS（0.501）→ **只剩 0.71 dB 余量**。−6/−10/−12/−14 dB 分别放大 2.35/1.57/1.40/1.30×。
差别**不在波峰因数**：白噪把能量摊在 300–10250 Hz，396 Hz 附近窄带幅度很低；
语音把能量压在 300–420 Hz（元音 F1），同一宽带电平下该频点幅度高得多。残差越界只看该频点的 `|mic(f)|/|1+…|`。
**越界频率 396 Hz ≠ 稳定边界 328 Hz，两者不能互为证据。**

**4 首选修复：宽残差。** 25 位残差保留到乘增益之后再钳，守卫改挂 `gain/mix` 饱和（标志照报，不是吞掉）。
覆盖可证：`输出/麦克风 ≤ g/min|1+…|` = **0.732 @−8 dB** → 麦克风满幅也不越输出；
−6 dB 档 1.176，需同时限制输入（门限内 1.176×0.501=0.589 仍安全）。零系数臂恒为 1，不受影响。
失败条件四条：首次越界乘增益后仍 ≥1 / 越界前单调爬升且主频 328 Hz / 麦克风钉在 ±1.0 / WNS 变负。
接口与契约影响（`feedback-fir-v1.md` 第 12 条、`audio-replay-v1.md` 保护语义）**交队长确认，A 实施**。

**5 负对照。** 同一模型跑在修线后六份开环抓包上（mic 峰值 −19.7…−11.5 dBFS），残差离满幅还有
+11.5…+23.1 dB，**没有越界样本** → 开环数据无法复现这次事件，因为它没有 `1/(1+g·Ĥ)` 这个闭环分母。
这也是为什么必须看 guard 抓包。

**证据**：[残差越界分析](../../report/verification/residual-overflow-2026-10-27/README.md)、
[repro.txt](../../report/verification/residual-overflow-2026-10-27/repro.txt)。
工具 `scripts/analyze_residual_overflow.py`（单文件、只依赖 numpy，板上可跑，输出只有数字不导音频）；
回归新增 `sim/feedback/test_residual_headroom.py`（5 项：最差分母 0.544@396 Hz、门限余量 <1 dB、
−8 dB 输出上界 <1、−6 dB 需输入约束、零系数恒为 1）。

## 2026-10-27 成功 vs 削顶：撤回"环路增益 −19 dB"，候选适用、判据换成 328 Hz 抬升

按 A 的 `0f17c74`（冻结计划 + 新责任边界）用已有记录做差异分析。**系数未动、未重训、未操板。**

**1 单位先独立核对**（`scripts/audit_units_and_saturation.py`）：RTL `feedback_fir.v:30/32` 是
`( |acc|+2^19 )>>20` 再 clip 到 ±2^23 计数，`verify_r4_waveforms.py` 的 `SCALE=2**23` 同约定 →
**PCM 满量程 ±1.0、系数满量程 ±8.0**。候选 ‖h‖₁=2.2875843 > 1，"任何输入都不饱和"不成立；
`max|Ĥ|=1.2309 @359.1 Hz`、`|Ĥ|≥1` 只在 292.1–421.7 Hz（88 bin）；解析阈值 1/|Ĥ|max=0.8124（−1.80 dBFS）
已用整数路径复现（+5 % 出现饱和、−1.6 dB 干净）。本批 |u|峰值 −6.0…−8.3 dBFS、pred 峰值 −22.07 dBFS、
饱和 0——该档电平下的观测，不是保证。

**2 撤回 A 的"环路增益 −19 dB、正增益可行"**：−11 dB 是**带内能量平均**（我复算 −11.01，与 A 记的
−10…−12 同口径）。稳定性看**带内幅度峰值 +4.40 dB @321.9 Hz**。峰值口径下 0/−4/−6/−8 dB 的环路增益是
+4.40/+0.40/−1.60/−3.60 dB，与 A 的有声源台阶（0 满幅／−4 浑 0.68／−6 近再生 0.37–0.70／−8 稳 0.12–0.16）
逐档对上；与 −19 dB 差 15.4 dB。**0 dB 时环路增益 +4.4 dB，必然自激**，与实测一致。

**3 首次标定"界有多保守"**：静音源台阶（`ab-stale-vs-nomodel`，零系数）实测 −4 稳／−3 临界／−2 起振
→ 自激边界 ≈ −2.5 dB；小增益界给 −4.40 dB → **界保守 1.9 dB**（充分条件的正常表现）。

**4 成功 vs 削顶的 20–24 dB 缺口：两个解释，且"量电平"分辨不开。**
两次成功 mic −27.9/−24.3、波峰因数 16.6/12.3（未削顶）、主频 253/298 Hz 两次不同；换线后同一 5 cm 读
−4.0 dBFS、峰值 0.0、波峰因数 4.0（削平）。解释一=当时输入链低 20–24 dB（连带环路也低，近讲那次几乎
是开环放大）；解释二=当时实际距离约 78 cm。**代数上两者对"25 cm 该读多少"给出同一个数**
（−17.98 dBFS；40 cm 均 −22.06），所以按计划先量 25 cm 电平**不能**分辨，只能判门槛合不合格。
倾向解释一的线索：环路模态固定在 328 Hz（五档全是 328），而两次成功的主频是 253/298 → 更像语句谱峰。
**未定案**：要成功那两次的原件（或板上静默算 50–1000 Hz 谱与语句间隙电平）。

**5 顺带一个可能被门槛挡住的算术**：按 16.6 dB 波峰因数，25 cm 的峰值约 −1.4 dBFS、40 cm 约 −5.5，
而门槛是峰值 < −6 dBFS（要求 RMS ≤ −22.6）→ 距离可能要到 45–50 cm 或降源电平。算术推断，以实测为准。

**6 候选适用、判据要换**：−14…−6 五档内两臂都不会自激（候选把"稳"点从 −8 平移到约 −2.9），
"有没有叫"分辨不了。能分辨的是**源还在放时 328 Hz 的抬升**：−8 处 +9.4→+4.0（差 5.4 dB）、
−6 处 +15.5→+5.4（差 10.1，压缩会吃小）。同轮锚点：**候选@−6 ≈ 零系数@−12**（环路 −6.68 vs −7.60）
→ 零臂请一并跑 −12/−14，就在允许范围内，不需要跨场次基线。

**证据**：[差异分析](../../report/verification/success-vs-clip-2026-10-27/README.md)、
[repro.txt](../../report/verification/success-vs-clip-2026-10-27/repro.txt)、
[units-audit.txt](../../report/verification/success-vs-clip-2026-10-27/units-audit.txt)、
[metrics.json](../../report/verification/success-vs-clip-2026-10-27/metrics.json)。
回归新增 `sim/feedback/test_unit_scale_guard.py`（9 项：PCM/系数两个满量程不许混、L1>1 不许作保证、
窄带阈值必须被整数路径复现）。

## 2026-10-26 夜 按 C 的接收更正五处口径（系数未变）

C 核对 `b6bcfb2` 的模型与文件/Q20/浮点身份一致、六份采集哈希一致，要求把预测与否定条件限定到
"A 允许的五档 + 实际覆盖 + 现场证据"。**不重交模型、不重训、不重跑旧回归。** 更正如下：

1. **撤回"满幅输入仍有 10.9 dB 余量、装板不会饱和"**。错在把**系数**的 Q20 满量程 ±8 当成 **PCM** 满量程；
   PCM 侧饱和阈值是 1.0。`‖h‖₁ = 2.2875843 > 1` → **存在合法满幅历史使 |pred| 到 2.29 倍满幅**，
   不能承诺"不会饱和"；`‖h‖₁ ≤ 1` 才是充分条件，L1 上界也不是充要条件。
   噪声型 |pred|rms = ‖h‖₂·σ_u（0.1702）→ 需 σ_u≳1.5 满幅；单音/自激型在 359.1 Hz（|Ĥ|=1.2309）
   处 A_u 超过 0.81（−1.8 dBFS）即饱和。本批实测 |pred|max −22.1…−24.3 dBFS（距满幅 22 dB），
   是该电平下的观测，不是保证。现场各级饱和保护保留；不代表已饱和，也不据此否定候选。
2. **+5.08/+8.48 dB 只表述为两个 FFT 网格（8192/4096）、同一门控规则下的离线小增益界差异**；
   不承诺现场收益区间、不设保底。界是充分条件，界不足不能推出起振；"零臂 −6 会起振"降为待检验预测。
3. **有限网格判读改为删失感知**：两臂到顶 → 报"未分辨/区间未知"，不要求 −4/−2、不据此否定；
   只有"候选失败而零臂同档完成"是否定；模态占比或一次保护不单独构成否定。
4. **摘要副本来源分开记**：C 核对的 `bind_manifest.json = 13aeb0a2…/1731` 是 Git 原件（正确）；
   我本地 `03ff23a3…/1788` 是 `git archive` 解包被转 CRLF 的另存件（`report/**/*.json` 无 `-text` 属性）。
   `manifest.json` 同理（原件 `1a4196c2…/1635` LF）。六份 NPZ 是二进制、不受影响。不改原件、不重采。
5. **适用范围**：`room_v1_20261026b` 替代旧 `newlayout`；1000–3000 Hz 有 190/336 = 57 % 过门控 bin，
   不再笼统称"中频未测"，但不等于整带覆盖；<300 Hz、>10.25 kHz、随电平、闭环、真人、听众、跨场次仍未知。
   **布局收益与 FIR 收益分开**，不复用旧批次的 +13.9 dB。

同步更新：[候选包](../../report/verification/rewired-candidate-2026-10-26/README.md) 增加 §0 勘误、
§3 饱和口径、§5 覆盖措辞、§6 判读规则；`test_newlayout_candidate.py` 的 L1 判据从"≤8 就不会饱和"
改为"L1 只作风险标记"（原写法基于错误阈值）。

## 2026-10-26 晚 修线后 512 候选交付；开环状态按数据判定

按 C 的需求单，用 A 的修线后六份 `ref/mic`（`52ee4e4`，`bind-capture-2026-10-26/`）交一个候选。

**输入资格按实际数据判，不按标签。** 6/6 npz sha256 与 `manifest.json` 一致；`bind_manifest.json` 与实际文件
不符（声明 `13aeb0a2…`/1731 字节，实际 `03ff23a3…`/1788 字节，只是人读摘要，不参与身份）。
`gain_q12=0` 表示反馈增益为 0（4096 才是 1.0），与 manifest 写的 −40 dB 不一致；硬证据是六份
`reference` 与 `source_pcm16/32768` **逐样本相同**（0.0000 dB、corr 1.000000）→ `played=source`、
反馈项没进环 → **真开环，不是弱闭环**。延迟 184/184/184/183/183/183（两档整采样相位）。

**模型** `models/room_v1/rewired_512_20261026.json`：file `01c9102a…`、Q20 `6118e85d…`、512 抽头、
`lag_first=1`、`signed24_fraction20`、bias 0 不装载、3N+3=1539；已登记 manifest，
`fixture_id=room_v1_20261026b`，并 `supersedes` 加棉前那份。

**结果（量化后）**：零系数界 −4.40 @321.9 → 候选 **+0.68 @333.8**（差 **+5.08 dB**；4096 分辨率 +8.48）。
时域 val 1.43/3.48、dev 1.40/4.93、train 3.05/5.08、CV 2.10/4.61 与 2.10/4.87；
**部署口径（不对齐、逐段原始六份）** 总体 1.01–3.65（中位 2.36）、300–460 3.49–6.00（中位 4.93）。
短板在 333–340 Hz（CD 4.3），界被它压住。修线后门控覆盖 33.6 %，**1000–3000 Hz 由"无覆盖"变 190 bin**。

**顺带回答 A 的"会不会撑爆 24 位"**：pred 饱和 ⟺ `‖h‖₁·max|u| ≥ 8`。本候选 ‖h‖₁=2.29、max|q|=47879、
`max|Ĥ(f)|`=1.2309 → 满幅输入也差 10.9 dB，不可能饱和。历史 `box_v1/baseline_256` 的 ‖h‖₁=26.7，
满幅会饱和（靠 mic 常在 −18 dBFS 才没触发），已写进回归测试注释。

**证据**：[候选包](../../report/verification/rewired-candidate-2026-10-26/README.md)、
[metrics.json](../../report/verification/rewired-candidate-2026-10-26/metrics.json)、
[repro.txt](../../report/verification/rewired-candidate-2026-10-26/repro.txt)。

**下一步（A/C）**：同轮跑零系数臂与候选臂，−14…−6 五档。注意：若两臂在 −6 都稳而 C 不授权 −4/−2，
2 dB 网格分辨不了 5–8 dB 的改善，**这一轮判不了**，应回报"需要决定档"。

## 2026-10-26 新布局 512 候选交付；撤回"穿越判据复现实测"的说法

按 A 的 `ddafcb7`（规则）与 `ca9b484`（审阅）执行：以 `e9e267b` 为起点，用 A 的六份新布局 `ref/mic`（`f45449d`）
交付**一个** 512 抽头 Q20 候选，固定 train(第1–4段)/dev(第5段)/val(第6段) 划分，val 只评一次。

**做了什么。** `scripts/fit_newlayout_candidate.py` 一条命令完成拟合→量化→评价→写模型：
模型 `models/room_v1/newlayout_512_20261026.json`（file `36c0d970…`、Q20 `e8757833…`、512 抽头、`lag_first=1`、
3N+3=1539 拍、无需补零），已登记 `models/manifest.json`；配套回归
`sim/feedback/test_newlayout_candidate.py`（文件哈希/系数哈希/清单三者一致 + Q20 范围 + 帧预算）。

**结果。** 时域（量化后）：val 4.05 dB、300–460 Hz 5.14 dB；3/3 CV 3.85/4.19 与 4.61/4.53 dB；
不对齐直接跑原始六份 2.28–4.51（中位 3.84）、300–460 3.75–5.51（中位 4.76）→ 收益不是对齐造出来的。
频域（同门控、1066/4046 bin）：旧系数界 −8.69、零系数 −3.15、候选 +5.27（CV +5.34/+4.82）。
325 Hz：`|H|=+1.24`、旧系数 CD −4.27（负，在放大）、候选 CD +10.86。

**撤回一条旧说法。** 上一版报"穿越判据 −5.66 @326.5 与实测 −5.5 @325 差 0.16 dB"。做敏感性后不成立：
同一份 H 只改统计窗口(全 16384/源有效 15407)与 nfft(8192/4096)，界基本不动（旧 −7.56…−8.69、零 −2.25…−3.16、
候选 +5.12…+6.82），**穿越会跳**（旧 −5.66→+0.02、零 −1.64→+3.06→+4.18、候选 +10.02→+21.11）。
所以 0.16 dB 是挑了有利组合的结果，改为：**穿越在本批数据上给不出可依赖的绝对阈值；定量结论只用界。**
连带修正三处表述：界≠实测最大增益、681 是每帧计算预算而非 BRAM 上限、(S+N)/N 之差≠纯信号 SNR（Δ=3/4 dB → 0.0/+1.8 dB）。

**证据。** [候选包](../../report/verification/newlayout-candidate-2026-10-26/README.md)（身份/场景/语义/兼容/划分/比较/预测/否定条件）、
[metrics.json](../../report/verification/newlayout-candidate-2026-10-26/metrics.json)、
[325 分析](../../report/verification/newlayout-325-2026-10-26/README.md)（三个数字 + §6 判据稳定性）、
[repro.txt](../../report/verification/newlayout-325-2026-10-26/repro.txt)。

**下一步（A）。** 把候选装板，与零系数**同轮**对照；判据是「候选比参考臂高多少 dB 仍稳」+ 听众是否听到可辨放大。
差 <3 dB 即否定候选；460–3000 Hz 本批无覆盖，若现场在该段出问题不能用离线结论反驳。

## 2026-10-23 按 C 的复核补正：注入位置、补零加载、尾段判定

C（1be7966）确认收到三个模型文件（SHA256 一致、`load_candidate` 可读），并提出三项核对。

**注入位置（我上一版推错了前提）。** C 指出 A 的实现是 `u=sat(source+gain·residual)`，
声源在 **DAC 输入端**，不是麦克风端。重新推导：

- 数字注入：`residual/mic = (H−Ĥ)/H`，**逐频点精确，与增益、声源大小无关** —— 它就是 −CD。
- 声学注入：`residual/mic = 1/[(1−loop)+g·H·z⁻²]`，随 g 变，完美模型与空模型都回 0 dB。

所以上一版"有源残差比不含模型信息"只对声学注入成立。用合成路径 + 单音时域仿真做可控验证，
两种情形与闭式解的差都 <0.01 dB，且数字注入换增益后比值不变。
**直接后果**：A 那条 −1.8 dB 若取自数字注入路径，就是有效读数，与离线 −20 dB 差 18 dB 属真实分歧，
优先查对齐（差一帧在 8.4 kHz 是 62°，足以把 +20 dB 打成 −1 dB）与电平依赖，而不是改模型。

**256 模型装 512 位流。** `feedback_fir.v` 只在 `load_index==TAPS-1` 置 `loaded`，
512 位流必须收到 512 项，上一版 README 说"可以装 256"在协议层是错的。已生成
`*_padded512.json`（`logical_taps=256`、`loaded_taps=512`、`derived_from_sha256`、
频响 `max|ΔH|=0.000e+00`），并明确：不能用补零产物论证 512 的收益。

**尾段判定。** 同意"计划 1 s 尾段"不等于实际保存的片段在尾段。新增
`scripts/check_tail_window.py`，六项判据（源已停 ≥40 dB、距最后有源帧 ≥512 帧、
mic 高于底噪 ≥10 dB、不削顶、长度 ≥2048、元数据一致）。用现有两份捕获试跑
（`manifest/seg_0`、`h30`）都判 FAIL——"有捕获"不等于"有尾段"。

---
## 2026-10-23 按新分工复核四项口径，交付模型包

按 `docs/lines/b-algorithm.md` §4 复核，并交付 C 可集成的 `models/` 包。

**因果延迟（四项检查全过）**：`predict` 对脉冲的响应严格延迟 1 帧、`fir_response` 与
`predict` 冲激响应的 FFT 差 4.7e-14、拟合索引与 `predict` 一致（回代 −81.6 dB）、
`history_matrix` 首行语义正确。**仓库里没有漏拍**；漏拍只在 A 审阅到的临时脚本里。
量化其代价：8.4 kHz 上 61.9°、幅度误差 103%——既能把残差算小也能算大，
所以它不能解释任何单一方向的偏差，更不能据此改 RTL 历史语义。

**用部署 Q20 系数同条件重算**（逐段独立预测、共同窗口 513 点、段边界不入统计）：
房间本场 256 −9.87 / 512 −11.16；跨场 256 −8.85 / 512 −10.88。
512 相对 256 本场 −1.28 dB、跨场 −2.03 dB，每子带不差。旧的低信噪比拟合只有
−5.70 / −7.15 —— **重标定本身是最大的一步，换抽头是第二步。**
箱体验证集 256 −9.79 / 512 −10.17（只 +0.38），故箱体不必换 512。

**三个口径复核**：
- 负 CD：相干≥0.5 的 397 个 bin 里，256 与 512 的 CD<0 个数都是 **0**；显著耦合点上最差
  分别是 +1.4（334 Hz）与 +7.4 dB（1979 Hz）。负 CD 只存在于 0.49 相干那批数据。
- "过预测→相减增能量"：只有 256 在跨场 100–300 Hz 出现 +1.2 dB，512 同处 −4.5 dB。
  它是特定频段与场次的现象，不是普遍性质；峰值比不能用来判断能量增减。
- 离线 vs 闭环：`scripts/closed_loop_metric_check.py` 证明"有源闭环 residual/mic"
  **在完美模型与空模型两端都回到 0 dB 附近**（完美模型 −0.6…−4.4，实测模型 −0.6…−4.5），
  不含模型信息，不能与离线 CD 相减。**尾段（无源）才是 −CD**：512 在尾段是 −11.6…−25.9 dB。
  A 测到的 −1.8/−3.7 dB 落在完美模型也会给出的范围内，故"残差本身只有几 dB"不成立。

**模型包**：`models/`（manifest 含 SHA256、拍数、量化范围）+ `models/README.md`
（系数语义、兼容条件、使用方法、预测与否定条件）。新增 `scripts/check_causal_alignment.py`、
`scripts/score_time_domain.py`（支持部署 Q20 与跨场次）、`scripts/closed_loop_metric_check.py`；
新增 5 项因果回归测试；仓内测试合计 75 项通过（含合并 A 分支带来的 8 项）。

## 2026-10-23 阈值缺口定位：256 与 512 的绑定频点不是同一处

A 改用尾段余振测阈值（源 1 s + 尾段 1 s），得 256 ≈ −5.5 dB、512 ≈ −1.5 dB，
并观察到「256 在 −6 失控、−4 却安静」的非单调。

**非单调在 LTI 回路里不可能**，只能是那一次回路没通。而尾段判据恰好分不清
「稳定」与「回路断了」——两者都表现为尾段贴底噪、斜率 ±2 dB/s。10-22 已确认音响会待机。

**绑定频点不同**（相位门控 + 显著耦合掩码）：256 被 405 Hz 限住，模型残差 −3.30 dB，
实测 −5.5，**只差 2.2 dB**；512 把低频补上后瓶颈转到 4.2 / 8.4 kHz，模型残差 −11.1/−11.5，
实测 −1.5，**差约 10 dB**。所以那个「11–12 dB 共因」不存在，是两个频点上的两个问题。
这也解释了 256→512 实测只涨 4 dB，而模型说该涨 7.6 dB。

**512 那 10 dB 的可能来源**：实测残差 1.19 对应约 21° 相位误差，模型 0.296 对应约 5°；
多出的 16° 无法由 24 Hz 峰值位移解释（窄共振 ±1 bin 仅约 5°），更像该峰在闭环电平下
幅度低 3–4 dB（3.23−2.04 = 1.19，数值正好）。一次高电平标定即可判别。

**阈值测法建议改成衰减率外推**：r(g) = 20log10(g|H|)/T_loop，r 对增益线性、
斜率 = 1/T_loop ≈ 690 dB/s per dB，r=0 的横截距即阈值。三个好处：不用推到啸叫、
不用在底噪上分辨、死环路会暴露成异常陡的衰减而不是伪装成「稳定」。

**激发改为对准绑定频点的窄带突发**（400 Hz 带宽，总 RMS 不变）：能量集中 17 dB，
尾段起点抬高 10 dB 以上。频带随模型变（256 → 405 Hz，512 → 4.2 / 8.4 kHz），不要写死。

证据见 report/verification/a-package-2026-10-23/README.md §10。

## 2026-10-23 A 数据包复核：8.4 kHz 不是瓶颈，低频是这批数据测不出来

复核 `manifest/`（6 段旁路直采、−24 dBFS 注入、延迟全 125）与 A 的两个模型。

**模型不是分歧点**：同一批数据重拟合，与 A 交付的模型相关 0.9996（256）/ 0.9992（512），
最大差 0.006。所以后面所有差异都不来自"谁拟合得更好"。

**口径换成时域逐段残差**（与板上 prediction 逐样本一致，不受 Welch、窗长、相干门控影响）：

| 模型 | 宽带 | 300–1k | 1–3k | 3–6k | 8.2–8.6k |
|---|---:|---:|---:|---:|---:|
| 256 | −9.91 | −2.3 | −5.4 | −11.2 | −18.4 |
| 512 | −11.24 | −4.0 | −6.6 | −13.4 | −23.4 |
| 680 | −11.64 | −4.5 | −7.0 | −14.0 | −23.5 |

**8.4 kHz 不是瓶颈**：十段（两批）全部落在 8345–8416 Hz、+9.7…+11.1 dB、半功率宽 405–811 Hz，
可复现；而模型在该带的抑制是 −18.4 / −23.4 dB。A 表里"6–12 kHz CD 最差 −4.89"的负值
来自 `|H|` 零点（那里 `|H|→0`、残差不为零，比值必然为负），与是否放大环路无关。

**300–1000 Hz 的短处是测量而不是模型**：同一模型在同一批的 300–1k 是 −4.0 dB，
换到旧批（mic −14 dBFS、相干 0.74）是 −10.1 dB。两批只差相干（0.49 vs 0.74）。
相干 0.49 意味着约 76% 的麦克风功率与参考不相关，那部分任何滤波器都减不掉。
**所以低频标定必须把注入提高 10–12 dB。**

**跨场次只损失 1.6（256）/ 3.0（512）dB**，模型是可迁移的。这条纠正了我当天早些时候
基于无门控 `max|H−Ĥ|` 得出的"跨场次塌到 0 dB"——那个量被单个边缘 bin 决定。

**抽头**：512 相对 256 每个子带都更好（8.2–8.6k 好 5.0 dB、3–6k 好 2.2、300–1k 好 1.7）；
680 只再多 2.1 dB 且 2043 拍只剩 5 拍余量。512 是本轮唯一被定量支持的改动。

**未解决**：实测阈值比模型低 11–12 dB，且对 256（+6.54 vs −5.5）与 512（+10.58 vs −0.5）
完全一致。恒定 ⇒ 共因而非模型质量。判定实验：在稳定增益下存一段 mic+pred+residual，
比 8.2–8.6 kHz 的 `|residual|/|mic|`，−23 dB 说明残差没问题、是判据测高了。

新增 `scripts/score_time_domain.py`（自动剔除静音段与延迟不一致段）与
证据 `report/verification/a-package-2026-10-23/`。

## 2026-10-23 512 上板：箱体无收益、房间有效，房间还要先重标定

A 交付 512 上板结果：WNS +0.287 ns、WHS +0.034 ns、BRAM 80%、1539 拍，
回归与 256 基线逐帧 bit-exact（512 位流 + 256 模型补零）。顺手修了 `audio_pl_replay.v`
三处前向引用——**已发布的 256 位流此前用仓库源码重建不出来，可复现性曾经是断的**。

**箱体上 512 无收益，而且模型上就能看出来**：validation 的逐子带 CD 在 256 是
+12.05（300–1000）/ +7.86（1–3 k），512 只到 +13.37 / +7.91，全带 ASG 13.72 → 14.03（+0.31 dB）。

**原因不是"箱体冲激响应短"**：两个夹具的能量 95% 点都在 235 帧左右（箱体 236、房间 235），
256 抽头对两者都只覆盖 95%。真正的差别是 `|H|` 的绝对水平——
箱体 300–1000 的 max|H| 是 **25.45 dB**，房间只有 **4.70 dB**。CD 是比值，
箱体的容错大 20 dB，同样的绝对误差在房间上就变成 CD 负。

**8.4 kHz 的发现**：房间在 8.3–8.5 kHz 有一个 +9~10 dB 的共振（6 段一致、相干 0.85–0.98），
shipped 模型在那里的余量缺口是 +2.56 dB。但用同一批高 SNR 数据重拟合的 256 抽头，
该点残差是 **−12.10 dB**。**所以高频短板是低 SNR 标定造成的，不是硬件**——
把它当音箱/摆位问题去改会走偏。

**结论从"加抽头"改成两步**：先重标定（修高频，也修掉低频的一部分），再上 512（补时长）。
refit 512 的四个子带 CD 全为正（+5.49 / +3.30 / +6.96 / +3.96），ASG +15.91。

对保护改动的意见：**不放宽门限**，改成"触发时存 mic/residual 的前 15 ms 包络"——
保护触发本身就是"已起振"的证据，需要区分的只是"真起振"与"数字瞬时过冲"。

新增 `scripts/compare_fixtures.py` 与 `report/verification/box-vs-room-2026-10-23/`。

## 2026-10-22 房间夹具：限制 ASG 的是抽头时长，不是低频估计器

A 交付房间夹具（0.5 m）9 段采集，要判"300–1000 Hz 模型不准"是估计器欠拟合还是标定 SNR 问题。

**先修数据：只有 4 段能拼，不是 6 段。** seg_0/seg_2 的 `ref→mic` 延迟是 124 帧，
其余可用段是 125 帧，差一帧。证据不止互相关：seg_0 的 `pred→mic` 相位差随频率线性增长
（−1.9° → −69.7°），斜率对应 1.05 帧，所以那两段的 `mic−pred` 抑制只有 −0.3 dB
（其余段 −8.4…−9.7 dB）。这是数据问题，不是算法问题。

**判据一：低频并不比高频难。** shipped 256 的 300–1000 残差 −1.11，6–12 k 是 +3.46，
低频反而好 4.6 dB；512 下低频再好 3.3 dB。原来"低频差 8 dB"来自低 SNR 标定（相干 0.32），
这批高 SNR 数据在 300–1000 的相干是 0.74。**所以 SNR 那一半的怀疑成立。**

**判据二：真正的缺陷是 256 抽头在 300–3000 Hz 的 CD 为负**（−0.53 / −1.96），
高频反而是正的（+3.26 / +0.20）。这就是"宽带把麦克风压低 20 dB、ASG 只有 4 dB"的形态。

**512 抽头把这两段翻正**（+5.41 / +3.76），且 300–1000 的 `max|Ĥ|` 从 −1.03 提到 +5.09，
与实测 +4.70 只差 0.39 dB。全带 ASG：shipped 256 +6.73 → refit 256 +11.32 → 512 +16.32 dB。

**纠正 A 的"512 只多 1.3 dB、不用改 RTL"**：那是宽带预测误差；ASG 口径下 512 多 5.0 dB，
300–1000 的 CD 多 6.0 dB。而加抽头只需改参数——512 用 1539 拍，预算 2048 拍，剩 509 拍，
不需要增加 MAC 单元。

取舍只给一个：**加抽头到 512**。加正则、预白化都改不了覆盖时长；重分配抽头（间隔加倍）
虽然也能覆盖 10.5 ms，但会把频率上限砍到 12 kHz，而这批数据里 6–12 k 的 |H| 是 10.27 dB，
是全带最强的，不划算。

新增 `scripts/analyze_room_taps.py`（自动剔延迟不一致与静音段，再做抽头扫描）与
证据 `report/verification/room-v1-2026-10-22/`。预测房间夹具换 512 后 ASG 4.0 → 约 13 dB，
待上板验证。

## 2026-10-22 结论反转：小信号下抵消有效，ASG 预测 +15.1 dB

A 改用开环直采（−30 dBFS 注入、不推到啸叫，两只音响在线、零削顶），并交出板上实际算出的
`prediction_pcm`。用板上 pred 直接相减：**mic 峰值降 11.41 dB、RMS 降 14.06 dB**——
不依赖窗长、相干门控与任何模型假设。

A 之前算的 `CD +2.4` 是**相干门控不足**：900 Hz 附近相干塌到 0.005–0.5，那个 22.89 dB
的残差峰落在 906 Hz、相干仅 0.532。门控从 0 提到 0.8，同一份数据的数字是：
max|H−Ĥ| 22.89 → 11.25 dB，CD 最差 −14.26 → +14.83 dB。**符号都变了。**

开环 max|H| = +26.32 dB @381 Hz，与标定数据的 +26.06 一致——**耦合没变**，
此前"弱了 8 dB"的推断（β）彻底作废。预测的抵消起振 −11.25 dB 与 A 闭环实测的
−12 dB 起振差 0.75 dB。

旁路侧"−18 dB 稳定"仍与预测 −26.3 dB 矛盾，但已由音响待机解释。因此小信号下
**ASG +15.06 dB 成立（模型推算）**；仍缺实测 ASG——旁路阈值缺失，且"抵消比旁路更早起振"
这个跨试验比较要求两次试验音响状态相同，也不成立。

新增 `scripts/analyze_live_h.py`（一条命令复算任何新采集，含窗长与门控敏感度）与
证据目录 `report/verification/live-h-2026-10-22/`。

## 2026-10-22 撤回：音响待机会让所有"没叫"变成假阴性

A 查明有源音响会进入待机：同一播放电平下，直放时麦克风 −29.8 dBFS，换一次试验变成
−64.3 dBFS，中间没有任何硬件变化。**这使所有"某档稳定/干净"的判据失去意义。**

B 于 10-21 用"旁路 −18 dB 跑满 10 s 稳定"反推出耦合比 β=0.395，这个观测是**负向**的，
正好落在待机能伪造的那一类。β 作废，其派生结论连锁作废：CD 最差 −3.64 dB、
CD≤0 覆盖 100%、512 更差、分频段退化成旁路、重标定预期 +13.5 dB、抵消起振候选 262 Hz。
A 同批做的 ×0.395 验证也未复现（抵消仍比旁路更饱和）。

**A 说"照单收下"的四条里，有三条同样以 β 为输入**：200–300 Hz 子带比值 1.42、
CD≤0 占 100%、512 更差、分频段等于全关。只有"换估计器无用"（真值截断测试）不依赖 β。

另澄清一处：**"相位结论与 β 无关"只对旁路成立**。旁路的 H_eff=βH 是纯缩放，候选频点
在 β=1 与 β=0.395 下都是 417 Hz；抵消的 H_eff=βH−Ĥ 是矢量差，β 改变合成相位
（β=1→226 Hz、β=0.5→274 Hz、β=0.395→262 Hz）。所以"262 Hz 命中 274 Hz"也属作废项。

仍可信：标定路径 +26.06 dB @381 Hz；标定条件下 ASG 13.53 / 14.68 dB（条件式，非实测）；
换估计器无用；旁路起振频点 417 Hz 的预测；以及实测的正向观测——同一增益下抵消比旁路
更饱和、起振频点 232 / 274 / 423 Hz。A 进一步查明 274 Hz 正是 `girl_voice` 基频，
这解释了两种激励为何符号相反（不是饱和保护）。

替代测量方式：**开环采集 ref+mic 两路存 npz（0.67 s，不需啸叫），直接算 H_live**。
阈值反推是单点估计、要推到啸叫、且已被待机污染，不再使用。证据报告第 0 节是逐条撤回清单。

## 2026-10-21 实测否定预测：诊断为标定↔使用耦合失配

A 交付首次真实声学对照（10 s 窗口），结论与 B 的模型预测**符号相反**：抵消 −19.5 dB
（人声）就起振，而旁路 −18 dB 跑满 10 s 零饱和。即当前系数在真实回路上**降低**稳定增益。

诊断：由实测旁路阈值反推，实测耦合只有标定的 **0.40 倍（−8.1 dB）**——
Ĥ 的幅度比真实 H 大 2.5 倍，减过头，残差比原环路还强。用这个 β 再预测抵消阈值得
−21.6 dB，与 A 的 ≤ −19.5 一致；相位允许的起振频点 262 / 417 Hz 对 A 实测的
274 / 423 Hz，偏差均在一个 FFT bin（11.9 Hz）内。延迟、相位、调度都对，只有幅度错。

三个候选方案在同条件下全部定量否定（β=0.395）：加抽头 512 使 ASG 从 −3.63 降到 −4.93
（模型越精确，失配时越危险）；分频段退化成旁路（CD≤0 覆盖 100% 频带，没有可留的好频段）；
换估计器无效（拟合已在最优附近，真值截断差 0.15 dB）。**按实测幅度重标定可恢复 +13.5 dB。**

修掉两处工具缺陷：`closed_loop_sim` 的麦克风满幅此前未计入发散判据（ADC 削顶后环路
"不再增长"会被误判成稳定，与 A 的判据口径不一致）；`diagnose_mismatch` 的相位过零
条件过宽导致候选频点几乎覆盖每个 bin。前者仍有非单调问题未修完，已记入 STATE 的未验证项。

证据 `report/verification/asg-field-2026-10-21/`；复现 `scripts/diagnose_mismatch.py`。

## 2026-10-21 真实箱体分析：381 Hz 的共振决定了全部

A 交出三个标定文件，第一次在真实数据上跑通逐频点分析。全部结论为**模型预测，非实测**。

- 路径峰值 **+26.1 dB @381 Hz**（相干 0.970），旁路起振约 −26 dB；模型在 381 Hz
  与 H1 估计只差 0.9 dB，说明 256 抽头确实把这个共振学进去了。
- 256 抽头抵消后 **ASG ≈13.5 dB**（相位口径 17.3）；512 只多 1.2 dB，
  **保留 256 的决定被真实数据支持**。
- 早先 −36 dB 的测试比阈值低 10 dB，物理上不可能起振——那批"没听到尖叫"无信息量。
- 20 Hz 以下相干仅 0.04，不给数值；10.6–10.9 kHz 模型略有害（CD −3.3 dB），不决定 ASG。

真实数据暴露并修掉两个缺陷：分析频带必须按相干门控（否则 12 kHz 以上估不出 H 的频点
会把 CD 中位数拉到 0）；加权拟合在预加重后越界，触发 Capture 的削顶拒绝。

现场点位：起点 −32 dB、对照点 −24 dB（旁路应叫、抵消应静）、终点 −12.5 dB。
证据见 report/verification/algorithm-box-v1-2026-10-21/。

## 2026-10-20 撤掉诉求通道：仓库只做记忆，协调走微信

用户重新定位了文档的职责：**只用来同步进度与背景**，不作为任务派发渠道。
诉求由 AI 写成可转发的文字，用户用微信转给队友。

撤掉了当天新建的 `docs/REQUESTS.md`。原因不是设计失败，而是它必然长成第四类文档：
需要维护状态、需要人记得关闭、会和微信里真实发生的沟通并行成两套账。
上一版上线六小时，一条 open 都没被真实使用过——真正推动事情的是微信。

同步改动：
- `AGENTS.md` 开工由四步回落到三步（去掉"扫诉求"），收工六步改为五步
  （"关诉求"换成"把需要队友配合的事写成可转发文字"）。
- `WORKFLOW.md` §2 拉取对齐由四处减到三处；§8 整节重写为"对外沟通：不进仓库"，
  保留三要素（要什么/卡住什么/怎么算完成）但载体改成微信文字。
- `scripts/brief.py` 去掉诉求段；`scripts/check_docs.py` 去掉诉求表检查，
  只保留 STATE 三条线的"最后动作/当前卡点"校验。
- `docs/INDEX.md`、`README.md` 的入口链路同步去掉诉求一环。

没做什么：不改任何技术结论、不改 STATE 的现状与关键数字。
## 2026-10-20 A 线补齐现场配置字段说明并识别夹具不匹配风险

用户贴出field_setup.json后澄清固定硬件是两个扬声器模块、一个MAX4466麦克风；此前把注释误读为双麦克风。操作包已修正为两组扬声器坐标，并区分麦克风增益与扬声器外置音量控制字段。配置仍有channel_mapping_verified空值与JSON注释等语法错误；operator_notes类型不符，音箱控制备注与确认标志矛盾。原标定资料没有完整记录扬声器布置，需先确认两只扬声器是否与标定条件相同，再决定夹具匹配标志。审查依据见[配置审查记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。

## 2026-10-20 A 线处理现场配置JSON解析失败

用户返回的summary为 `status=stopped`、`trials=[]`、`pairs=[]`、`sound_seconds_completed=0`，错误指向板卡 `field_setup.json` 第12行第33列的 `JSONDecodeError`。据此确认该次没有进入READY交互或播放项；由于板卡编辑版配置未提供，未猜测非法字符。操作包新增按行列定位、JSON语法核对和先重跑静音代码格1的恢复步骤，见[恢复记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。

## 2026-10-20 A 线澄清现场Notebook的READY输入位置

用户反馈执行代码格2后找不到 `READY` 输入框。截图里执行编号已经返回，且输出 `summary.json` 路径，说明调用已退出而非等待输入。脚本在异常退出时同样保存摘要；具体停止原因需打开板卡 `field_results/field_<id>/summary.json` 查看 `status` 和 `stop_reason`。已把这一判别写入[操作包](../experiments/field-validation/README.md)与[恢复记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。在停止原因明确前不重跑代码格2。

## 2026-10-20 A 线记录现场配置文件缺失的静音恢复步骤

用户补传运行器后报告代码格1缺少板卡 `field_setup.json`。该检查在静音核验中，尚未运行批次。操作包补充单文件上传步骤：电脑本地配置模板上传至板卡 `base → audio → audio_closed`，确认列表出现后只重跑代码格1；模板须等现场条件确认后填写，不能为通过核验臆填。操作依据见[现场操作包](../experiments/field-validation/README.md)和[预检恢复记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。没有播放音频。

## 2026-10-20 A 线修正现场运行器SHA256大小写误判

用户补传 `field_validation.py` 后，代码格1报告实值与预期哈希仅十六进制大小写不同，却因字符串区分大小写而拒绝文件。已把Notebook比较改为大小写归一，并在[操作包](../experiments/field-validation/README.md)说明：电脑本地运行器无需重传；只需覆盖上传新版 `field_trial.ipynb`，然后重跑代码格1。证据与恢复步骤见[预检恢复记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。尚未运行代码格2或播放音频。

## 2026-10-20 A 线修复现场Notebook缺少运行器时的静音预检指引

用户执行 `field_trial.ipynb` 代码格1时报告 `field_validation.py` 的 `FileNotFoundError`。回溯显示清单和闭环包哈希检查已通过，异常发生在运行器文件读取，代码格2尚未执行。已在Notebook中增加明确的缺文件/哈希不匹配提示，并在[操作包](../experiments/field-validation/README.md)写明只需把电脑本地 `board/audio_closed/field_validation.py` 上传到板卡 `base → audio → audio_closed`，确认文件出现后只重跑静音核验格。恢复记录见[静音预检记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。没有启动声源或运行批次。

## 2026-10-20 A 线审查 B 线分析交付并提出修订请求

审查 `src/feedback/path_analysis.py`、对应测试及 [B 线合成报告](../../report/verification/algorithm-2026-10-20/README.md)。`recommend_field_range` 当前以 `msg_bypass_conservative_db + 2 dB` 生成对照点，并注释称旁路应起振；报告交叉核对的旁路阈值为保守 −2.02 dB、相位口径约 +2.12 dB、整数闭环模拟约 +2.11 dB，因此代码给出的约 −0.02 dB 不能据此称为预测旁路起振点。要求 B 重新定义可行区间和保护裕量，无安全区间时明确不推荐现场点。

另发现加权候选在报告 ASG 等评分时使用浮点系数，JSON 同时附带 Q20 整数系数；要求用实际量化系数重算验证指标，避免浮点结果被当作可部署候选收益。测试文件有两份同名 `ModelArtifactTests` 定义；要求去重并保留覆盖。R-001/交接把“不含人声”作为可传输依据，与用户原始 PCM 未经同意不得传出的要求冲突；请求改为优先板上静默分析、仅回传统计 JSON，原始数据须获授权。上述事项记录于 R-004（当时的诉求编号），尚未修复或复验；没有运行板卡或播放音频。









## 2026-10-28 C 完成A65三条复验并扩大原件检索

A65快照10项及sh换行身份核对，守卫16/16、C门禁/保护5/5、三类资格+控制4/4；已知单音揭示dBFS未做Hann幅度归一化，附未应用最小补丁并内存2/2。C身份2项/消费者4项通过；按用户要求搜索20个GitZIP、158个本地ZIP及历史/工作树，找到摘要未见原件。后续83源2s/运行2.4s的保存末圈全无源，不能用其电平作含源可听负结论；四行均差还与摘要不符。只静默重算、不新增现场，成功/失败及听众原话保留。[证据](../../report/verification/audio_closed/batch-control.md#2026-10-28-a65三条修复及原件扩大搜索)。

## 2026-10-28 C 接收A41硬件闭合并拒绝当前纯音现场绕行

按A=41fd0d6接收c2四项硬件记录，60秒及定性阳性明确为手机6/15变更条件，失败记录保留。新helper7/7与512前缀修复通过，4份真v2抓包计数匹配，33点摘录局部8次成立；非完整8次原NPZ重放。C checker2项/消费者5项通过，不重跑16项。编排2/5、纯音资格6/9仍有缺口，明确当前不跑30秒、修后仅一轮真实manifest，坏样例静默派生；底层工程与完整效果流程冻结分开。[证据](../../report/verification/audio_closed/batch-control.md#2026-10-28-a41硬件补证与剩余流程验收)。

## 2026-10-28 C 按交付字节复验A五条修复

固定A=ac30584，以快照/manifest落盘字节核8/8；不沿用旧8/8或3/7。保存失败/输入停声驱动桩3/3、新算术测试7/7、消费者身份4项通过；真实前缀反例仍报0/512，编排4/8、无令牌3/3、纯音资格4/9，剩余缺陷及manifest零Q20/旧摘要一次交A。C同步新旧完整身份、拒绝混搭，未改A底层或上板，硬件两项未复跑和可听收益未成立分别保留。[五条证据](../../report/verification/audio_closed/batch-control.md#2026-10-28-a交付版ac30584五条复验)。

## 2026-10-28 C 完成Be730剩余边界限定验收

B=e730b5b点名4项、C改动范围5组均通过；只复验剩余三个数值边界与前史措辞，没有重跑已过Q20/整窗分列或189项。核对frame_domain改名无现用C旧键依赖，保留缺帧域的局部分析，说明已知起点/缺完成帧的条件位置与未知闭合。两个文案对齐不阻塞既有静默分析，不推导新现场结论。[验收证据](../../report/verification/audio_closed/batch-control.md#2026-10-28-be730剩余边界验收)。

## 2026-10-28 C 限定复核B67四处工具修正

按B=67d28b2只跑点名8项，全部通过；C同四类独立边界11项8过3未过，确认原四类反例修复，但近满幅容差、缺失帧域默认0和小数帧号截断仍须修。近满幅完整分析已停止归因/退出2，区别于解码器直接拒绝。整窗/有效区分列及Q20声明核对通过；未重采、操板或跑185项，保留原件与历史观测。[范围与证据](../../report/verification/audio_closed/batch-control.md#2026-10-28-b67四处修正版限定复核)。

## 2026-10-27 C 同步v3判据并给A一次验收清单

按A=e132991核对v3 bit/HWH/driver/helper身份，原8项8/8；v3补充7项3过4未过，定位失败sidecar丢bit22/身份及宽残差两类计数错误。脚本驱动失败桩还复现人声门禁失效和纯音失败后继续。C同步bit22硬无效、宽残差/skip+2、25位尾段语义及版本混搭拒绝；新增15、受影响旧21个用例通过，不跑175项或新现场。操作单区分安静背景与讲话余量、限制三组白噪结论，保留历史阳性及新听众原话。需A修改一次列清，无A驱动/RTL/保护改动。[验收与证据](../../report/verification/audio_closed/batch-control.md#2026-10-27-v3消费端同步与a交付验收)。

## 2026-10-27 C 限定复核B3e并读A新派生结果

取得B=3e69ab5与A=5c67f21，10项指定测试通过，已有r4真实错模型反例退出2。C同范围8探针3过5未过，定位浮点符号/静默钳位、声明Q20哈希、实际帧域与有效区余量4处剩余缺口，未跑175项。对A返回33点按显示精度独立计算，8点确定越界且帧域自洽；范围明确为摘要算术，不冒充整份原件重放。纠正3359贴轨属浮点取整的无依据解释，保留零臂主路径观察；无新采集、模型或保护变更。[通过项/反例/失败出口](../../report/verification/audio_closed/batch-control.md#2026-10-27-b3e修正版限定复核)。

## 2026-10-27 C 审A分项执行并交离线复算入口

按队长转发读取A=d17ff29/fc49529/df0956c及a735d45，搜索main/A/B完整目录及20个ZIP，未找到本轮抓包/现场脚本/时间线。分开手机成功、真人12cm短时阳性、两臂削顶与候选保护，纠正零正常/候选独败及非稳态一律无效的推断，定位白噪6.805/10.105条件值与7.9矛盾。交只读派生适配器，14项不同定向用例最终通过；B当前fee0e59的5个反例均失败，修正版未到，不冒报通过。原件/流程缺口一次列清，先补既有文件和静默统计；无新发声/保护变更/全场重跑。[派生质检与证据](../../report/verification/audio_closed/batch-control.md#2026-10-27-a分项执行质检与最小补证)、[离线操作单](../../board/audio_closed/BATCH_GUIDE.md#2026-10-27-分项执行回包的离线质检)。历史对象已更正为手机，r6原ZIP保留。

## 2026-10-27 C 补清手机污染与同轮候选判读

按B反馈细分r4首包持续手机播放与尚未知的增益/AGC漂移，不将污染简写为可剔通知音；首包无闭环配对，不作328Hz收益。明确独立源归一化缺失时的未分辨范围、历史成功原件不阻候选、跨增益工作点预测不作实测算法收益。仅更新[审计与解释](../../report/verification/audio_closed/batch-control.md#2026-10-27-补清手机污染与同轮对照边界)，r6代码/模型/ZIP未变，未重跑软件回归或操板。

## 2026-10-27 C 冻结r6基线优先完整流程

从干净d95c3a2生成c-success-reproduction-r6.zip，358489字节，35项载荷/唯一Notebook代码及已测源码字节核对完成；实际打印STOP，取消0试次仍回包保留历史反馈。9.5/60秒纯参数验证范围明确；语音PCM留板，结果分别导出基线/候选。操作单与Notebook文案均不让候选缺项阻断基线，未改A驱动或B系数。[包身份与限制](../../report/verification/audio_closed/sprint-rc0-20261025/reproduction-package-r6-check.json)、[现场操作单](../../board/audio_closed/BATCH_GUIDE.md#2026-10-27-成功工作点集中复现)。无C操板/新现场结论。

## 2026-10-27 C 按0f工作流整合成功复现与候选依赖

fetch后读取A0f17c74指定规则/计划，保持C。核对r4实际源/帧窗/背景及首四角色无START路由，未把距离或阈值定为唯一原因；第二次仍摘要。r6在已有入口先零系数−8基线，5cm仅静音资格检查、一次距离变更，真人/静音听众两次及条件60秒使用后再同增益候选；缺模型不阻基线，实际人工动作有阶段记录。11个不同软件用例最终通过，初次满幅分支失败及定向修复留证，未全套重验。[审计与完成/失败出口](../../report/verification/audio_closed/batch-control.md#2026-10-27-r6按成功复现顺序整合基线与候选)、[原帧审计](../../report/verification/audio_closed/sprint-rc0-20261025/reproduction-r6-audit.json)。无C操板或新效果。

## 2026-10-26 C 冻结r5相对正向检测最终包

从干净c2acf87冻结c-new-layout-r5.zip（342392字节），独立解压32项载荷、Notebook及已测源码身份核对完成；取消退出2、0试次、无活动绑定。定音频率/声量/时长、模型/bit、五档及原保护保持，仅改runtime测量和原件复算。第一回包有污染、零算法配对；第二回包待A网络恢复取回，不要求旧试次重跑。最终SHA与限制见[r5机器记录](../../report/verification/audio_closed/sprint-rc0-20261025/layout-package-r5-check.json)，[操作单](../../board/audio_closed/BATCH_GUIDE.md#2026-10-26-新布局一次集中实验)。无C操板或新效果结论。

## 2026-10-26 C 复算A正向失败并修复r5检测

读取A26aaedd原摘要及083f31c第一份原ZIP，身份/原件质检无差异，闭环对照0；手机污染只作诊断。原窗1k分量−38.27、相对背景/邻频约27.57dB，旧宽带+6dB/占比0.8要求过强。C选相对等窗检测，保持声量/时长/模型/五档/保护，不旁路正向；4检测+4runtime/质检用例通过，未重跑旧145项。第二次仅摘要且板卡断网，待取原件，不原样第三次试验。[决定与失败出口](../../report/verification/audio_closed/batch-control.md#2026-10-26-r5修复正向对照的宽带支配门禁)、[复算](../../report/verification/audio_closed/sprint-rc0-20261025/positive-control-r5-audit.json)。

## 2026-10-26 C 纠正A收到r3的交付错位

接收A3af转发，确认旧r3守卫拒绝合理；明确取已交r4/fa13877及完整SHA，不重建原包。答复零臂用合法模型+zero_coeff=True、0.30秒严格含DC峰值及恒读检测范围；纠正LOAD_OK不是PL加载证据、10.9dB余量已撤回。未改代码、未重验、未操板。[交接证据](../../report/verification/audio_closed/batch-control.md#2026-10-26-a3af收件错位纠正与r4执行确认)。

## 2026-10-26 C 补齐r4远端同步与B254原件核对

远端连接恢复，C的需求、源码及r4归档已推送至c0b1772；随后取到B=254b8e9，阅读原勘误§0与测试修订，模型与b6bcfb2逐字节相同。更新[r4机器记录](../../report/verification/audio_closed/sprint-rc0-20261025/layout-package-r4-check.json)中的提交/README身份和同步结果；冻结ZIP未替换，不重复无变化的软件检查，仍无现场效果结果。

## 2026-10-26 C 冻结r4修线候选最终执行包

从干净9797a12冻结c-new-layout-r4.zip，独立解压32项载荷/Notebook代码及已测源码核对通过；仅余A一次现场手机事实与本地冻结绑定。取消入口退出2、0试次、无活动模型并生成停止回包。最终包338417字节及SHA见[r4机器记录](../../report/verification/audio_closed/sprint-rc0-20261025/layout-package-r4-check.json)，[操作单](../../board/audio_closed/BATCH_GUIDE.md#2026-10-26-新布局一次集中实验)。未操板、未声称效果通过；远端连接失败，交付本地ZIP与C提交，保留待推送事实。

## 2026-10-26 C 接收B勘误并完成r4修线候选绑定

按用户转发254b8e9勘误接入b6bcfb2同字节候选；网络未取到新Git对象，包内原字节来源与转发勘误明确分开。补六段数据集身份拒绝，派生新fixture同时保留A52原件；五档、峰值门禁、手机同片段、定量未测与保护停止保留。23个相关软件用例及最后一次运行回包复验通过，未重跑旧145项或操板。[集成/失败出口](../../report/verification/audio_closed/batch-control.md#2026-10-26-r4接收b勘误并绑定修线候选)、[检查记录](../../report/verification/audio_closed/sprint-rc0-20261025/layout-package-r4-check.json)。

## 2026-10-26 C 接收修线候选并重写A/B需求

按用户最新转发B=b6bcfb2重写两线需求，撤回“仍等B修线模型”的卡点；保留r3旧模型阻断，未伪称新执行包已放行。定向核对模型/Q20及A52六NPZ、按全局帧号重建source均一致；Git摘要13aeb0a2…/1731与A清单匹配，B本地副本差异另列。纠正预测器输出满幅单位、网格界保底承诺和封顶档差机械否定，保留五档硬上限、峰值门禁与定量未测。[需求与交接](../../report/verification/audio_closed/batch-control.md#2026-10-26-修线候选到达后的a与b需求单)、[原字节/数值证据](../../report/verification/audio_closed/sprint-rc0-20261025/rewired-handoff-check.json)。本次未改执行代码或重新验旧基础，无操板/效果结论。

## 2026-10-26 C 归档r3修线后待绑定完整包

从干净源码4a3a71a生成c-new-layout-r3.zip，独立解压31项载荷与Notebook代码格核对通过；旧B8a02757即使带FIELD_READY也退出2、0试次、无活动模型。A52成品与四JSON修复已合入，严格−6峰值门禁和听众定量未测已备好，收到包不等于效果试验放行。最终身份及全部软件回执见[r3机器检查](../../report/verification/audio_closed/sprint-rc0-20261025/layout-package-r3-check.json)。C未操板，唯一待绑定外部条件是B修线匹配模型及来源。

## 2026-10-26 C 接受A52ee4e4修线更正并完成r3集成

按A原成品更新25cm与五档允许值，逐一接受field-config/live-round/mic-fault-impact/usable-point四JSON语法修复，不再退回旧缺陷。撤回5cm工作点适用性与r1/r2在当前接线条件下的使用；历史事实/原包保留。
r3每项前0.30秒零输出完整采样，以包含DC的绝对峰值严格<−6为门禁，拒绝恒定−4.2和5cm；通过后才进入正式项，仍保留A先停声后保存。听众定量固定未测、定性单列，不要求找设备。B8a02757尚未更新到修线数据，修线manifest/集合和新模型绑定缺失时触板前0试次退出。
21项主检查及2项针对检查通过，源/距离、故障停声与持续元数据均覆盖；无关22项不重跑。见[r3证据](../../report/verification/audio_closed/batch-control.md#2026-10-26-r3接受a修线更正与峰值门禁)。未操板/发声，未产生效果结论。

## 2026-10-26 C 冻结r2现场执行包

从干净源码5e73892生成c-new-layout-r2.zip，独立解压27项载荷与Notebook代码格核对通过；现场取消实际退出2、0试次、未生成活动模型，B无补材料阻塞。16项相关测试通过，未重跑无关基础项。最终字节/哈希与命令回执见[r2机器检查](../../report/verification/audio_closed/sprint-rc0-20261025/layout-package-r2-check.json)。未操板、未获得现场效果或MSG；A一次确认事实后执行，C收一次回包再质检交B。

## 2026-10-26 C 接受B正式交接并修正整批等待

B正式转发8a02757候选与加载/验证/执行条件，C撤回r1把纯SNR门限、额外注入范围和可选录音配置设为整批前提的做法，改为按依赖分支验收。完成−14..−8dB静默注入的零/新有界配对、真人两臂同句、系统静音听众及条件性60秒运行，A只需唯一入口FIELD_READY核实事实并执行，无需临时拼代码或等B再给数。
同窗正向背景/SNR、实际身份与参考、保护停止、原件回包复算均集成；保留频域估计、全程声学及边界未知。14dB旧模型比较不转作零系数门限，不采用3/8dB自动放行/否定。A新d2a6b55低切失败与B候选分开，未扩大算法或硬件范围。见[r2集成与证据](../../report/verification/audio_closed/batch-control.md#2026-10-26-r2接收b正式交接并交现场执行包)。

## 2026-10-26 C 归档含候选的集中实验完整准备包

从干净源码c6980a1生成c-new-layout-r1.zip，含A原字节底层、B原候选与身份材料、C入口和唯一操作单；26项载荷和Notebook代码格独立解压核对通过。缺注入/SNR适用条件及现场限制时实际check退出2，候选未激活、未操板。最终哈希、字节及完整缺项见[机器回执](../../report/verification/audio_closed/sprint-rc0-20261025/layout-package-r1-check.json)，A/B由本轮消息一次转发剩余材料，不误报候选缺失或效果通过。

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
见[B审核](../../report/verification/audio_closed/sprint-rc0-20261025/b-3657242-review.json)、[A真人尝试审核](../../report/verification/audio_closed/sprint-rc0-20261025/a-9edd83b-review.json)、[原件复算](../../report/verification/audio_closed/sprint-rc0-20261025/a-63f6a69-waveform-review.json)和[请求清单](../archive/README.md)。

## 2026-10-25 C 统一A与B的后续派单

重新fetch并同步C，核对A=d013930、B=71d6a34未新增提交；两个已发布ZIP字节数和SHA256保持一致。
将A的真人五项会话登记为R-009，与R-008既有五原件补交并列；B继续R-007三项发布口径和现有汇总的限定判读。
按用户要求记录每轮分别检查A/B派单的收尾习惯；[请求清单](../archive/README.md)是执行入口，[原始要求](../../report/ai-records/closed-batch-control.md#2026-10-25-统一检查ab派单)留存。
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

新增 docs/REQUESTS.md（当天晚些时候已撤掉，见上方最新条目）：只有 open/done 两态，每条必须写清
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
## 2026-10-23　A　按队长要求更新三线分工与人工交接

- 明确 A 维护底层驱动、硬件集成及现场，B 维护算法与事前预测，C 维护测量/复算并整合完整实验包；按功能划定混合目录的文件边界。
- 重写三份可全文转发的 AI 提示词，加入第一轮任务、准确文件/代码格定位、批次停止分支和结果包交付；统一人工消息转发，不使用 REQUESTS 待办表。
- 同步 AGENTS、WORKFLOW、开发规范和导航，消除旧分支/权限及角色归属冲突。按用户指定交 A 分支，供队长后续合并 main。
- 验证：`python scripts/check_docs.py` 与 `git diff --check`；本次仅文档与规则修改，未执行算法测试、综合或实物实验，未改变契约语义。
- 依据：[用户授权摘录](../../report/ai-records/README.md#2026-10-23-队长要求的新分工授权摘录与采用说明)；交付：[分工及提示词入口](../lines/README.md)。

## 2026-10-22　A　512 抽头改建与箱体复测

- 修 src/rtl/audio_pl_replay.v 的三处前向引用（scheduled/u_ready/rm 声明前使用）——
  仓库里这版源码原本重建不出已发布的位流，xvlog 直接报错。
- TAPS 256→512，驱动去掉硬编码 256（
esidual_tools、
eplay_tools、
eplay_trial）。
  重建后 WNS +0.287 ns、WHS +0.034 ns、LUT 6.61 %、BRAM 80 %，位流 sha256 8b2426f4…。
  沙箱内 BD 解析失败（BD 41-1690），宿主 PowerShell 一次通过——环境限制，非设计问题。
- 回归：512 位流 + 256 模型补零 → 控制项 −18.1 dBFS、延迟 114 帧、bit-exact，与 256 基线一致。
- 箱体 512 标定改用按 RMS 定标的合成白噪声（记录噪声分段峰值归一化后实际太小，采集被底噪主导）：
  256/384/512 验证集降低 6.22/6.34/6.49 dB，max|H| 26.45 dB @417 Hz 与独立实测 26.3 dB 吻合。
- 箱体起振点：旁路 −24、抵消 −13.5 仍起振，**512 没有改善**（ASG 仍约 10.8 dB）。
  证据：[512 报告](../../report/verification/audio-replay/2026-10-22-512-taps.md)。
# 项目进度（时间线，只追加）

> **本文件是只追加的日志，不是现状。** 每条记录是"当时"的状态，越往下越旧，
> 其中"未上传/未验证"等字样只描述当日。**当前状态一律看 [STATE.md](../STATE.md)。**
> 规则：新条目加在最上方；不修改、不删除历史条目；每条结论都应能链到 `report/` 里的证据。

## 2026-10-21 A首次实测ASG：两种激励符号相反，并证实audio_closed输出不通

用 `audio_replay`（先以 −36 dBFS 直放标定出 +23 dB 播放→麦克风耦合）在关盖箱体做逐档成对
对照，2.05 s/项、同增益只改 bypass。**噪声源**：旁路起振 ≈ −19 dB、抵消 ≈ −13.5 dB，ASG ≈ +5.5 dB，
由 −24 dB 旁路再增量反推 `|H|max ≈ +23 dB`（模型 ℓ1 为 +28.5 dB）。**人声源**（`girl_voice`
截 2 s 数字注入）：抵消 −18 dB 起振、旁路 −13.5 dB 起振，ASG ≈ −4.5 dB。两种源给出相反符号；
关掉保护单跑一次，麦克风峰值达 −3.0 dBFS，确认是声学啸叫而非数字自激。

按频点分析解释了差异：噪声源起振在 **232 Hz（抵消）/423 Hz（旁路）**，人声源抵消起振在
**274 Hz**——正好落在 `girl_voice` 基频上，所以真实人声更容易把抵消回路推起来；
B 预测的 381 Hz 共振两次都没成为起振点。

同轮证实 `audio_closed` 的 DAC 输出无效：同批配对（−60/−26/−60 dB）中 −26 dB 环路对麦克风的
贡献只有 **+0.06 dB**（应 +5 dB），而其 ADC 正常（手机近距离播放 −26.7 dBFS）；已排除 RTL 顶层、
驱动与 Codec 配置差异，指向 bitstream。按用户决定退役该 overlay，历史"闭环"结果只证明算术。
另：板卡既有 `source.wav` 实为噪声（平坦度 0.55、帧起伏 3.1 dB）。

证据：[本轮报告](../../report/verification/audio-replay/2026-10-21-asg-field.md)。
未执行：10 s 长窗口、端到端延迟。

## 2026-10-21 A修复PYNQ后台线程事件循环

现场初始化报No current event loop。读取板卡pynq/uio.py确认UIO注册依赖调用线程事件循环；将每次新建线程改为持久单音频工作线程，初始化并保留同一事件循环，启动预检实际工作线程，并记录完整异常栈。部署后重启空闲服务；未触发录音播放。[证据](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A修复SSH服务XRT设备注册

根据现场No Devices Found错误，读取板卡PYNQ源码确认设备注册依赖XILINX_XRT；加载板卡官方环境后枚举到EmbeddedDevice。加入启动脚本、启动设备检查并部署；未加载overlay或发声。[证据](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A修复按钮页录音环境与失败提示

用户报告录音后无后续按钮；读取状态确认多次录音均在导入pynq时失败，未生成录音。切换PYNQ虚拟环境并加入启动导入检查、页面错误直显；保留计划和原链接，仅重启已确认空闲的A服务。[证据](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A通过SSH部署并完成静默选档

获用户授权后直接SSH/SFTP调试，确认板卡旧包并备份更新，逐文件核对15项。真实数据静默选档通过，仅回传JSON，未发声。新增按钮页并核对HTTP待机状态。接口变更：[逐档v2](../contracts/audio-replay-sweep-v2.md)保留原保护上限，追加有间隔的末档并提供按钮交互；硬件不变。[证据](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A修复Notebook保存导致的哈希拒绝

用户返回package阶段停止摘要，无试验项、零发声。将Notebook校验从整文件改为代码格内容摘要，保留其他程序和bit/hwh字节校验，更新完整包及两文件恢复步骤。未拿到板卡Notebook，不能断言此次只改了输出；本次未上板。[修复证据](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A补齐逐档增益批次

根据用户一次性交付要求，新增已有标定数据静默选档和逐档抵消→旁路运行器，固定整批声源电平并自动保存配对/停止原因；完整包从10项更新为13项。接口变更：新增[audio-replay-sweep-v1](../contracts/audio-replay-sweep-v1.md)，旧硬件/接口保留。执行语法、打包与文档检查，未运行本版回归或上板，真实档位留待板卡数据计算。[实现记录](../../report/verification/audio-replay/README.md)。

## 2026-10-21 A同步微信协调规范并保留交付

按用户授权处理REQUESTS删除/修改及STATE冲突，将远端main `18681fc`变基合入A。保留A程序和证据，撤掉旧诉求表；历史条目仅移除已删除文件的失效链接，事实内容保留。代码与交付ZIP未改，未操作板卡。B/C分支已取回，C代码未合入A。见[交付记录](../../report/verification/audio-replay/README.md)；协调采用用户微信转发，仓库保存全局记忆。

## 2026-10-20 A线交付预录语音程序与独立接口

用户要求手机录好后停止外放、音响播放同时实时采样。A交付独立audio_replay RTL、bit/hwh、驱动与三格Notebook完整包；70项软件检查、RTL仿真及最终构建通过。首次构建时序失败已修复并保留证据。未操作板卡，真实听感仍待一次现场执行。接口变更：新增[audio-replay-v1](../contracts/audio-replay-v1.md)，旧接口保持不变；数字源加入实际输出，B/C消费注意事项见REQUESTS的R-005/R-006。[交付与检查证据](../../report/verification/audio-replay/README.md)。

## 2026-10-20 A线澄清二次确认并修正文案

用户提供第二次摘要：模型范围已正常生成 `−35 dB` 单档，第一次 `READY` 已通过；脚本第二次提示要求 `START`，用户再次输入 `READY`，触发 `operator_cancel_before_start`。`trials=[]`、发声0秒，没有现场效果证据。已将第二次提示改为明确的“第二次确认：输入 START 才开始旁路/抵消配对”，并同步Notebook预检SHA和操作包；最新版尚未上传板卡。详见[现场记录](../../report/verification/field-validation/model-bound-zero-playback-2026-10-20.md)。

## 2026-10-20 A线现场批次因模型增益上限零播放

用户提供的 `field_651b97b20f6d/summary.json` 显示配置核验通过，候选模型 `L1=26.744`，估算小增益上限 `−28.545 dB`，扣除6 dB保护量后运行上限为 `−34.545 dB`。原计划从 `−30 dB` 开始，故 `gain_levels_db=[]`、`trials=[]`、`sound_seconds_completed=0`，脚本安全停止；无现场音频结论。A 已在本地将起点改为 `−35 dB`，该候选模型可生成一组成对档位，预计总发声4秒。新版尚未上传板卡，需下次现场前完成静音核验。具体证据和给B/C的事项见[现场记录](../../report/verification/field-validation/model-bound-zero-playback-2026-10-20.md)。


## 2026-10-20 撤掉诉求通道：仓库只做记忆，协调走微信

用户重新定位了文档的职责：**只用来同步进度与背景**，不作为任务派发渠道。
诉求由 AI 写成可转发的文字，用户用微信转给队友。

撤掉了当天新建的 `docs/REQUESTS.md`。原因不是设计失败，而是它必然长成第四类文档：
需要维护状态、需要人记得关闭、会和微信里真实发生的沟通并行成两套账。
上一版上线六小时，一条 open 都没被真实使用过——真正推动事情的是微信。

同步改动：
- `AGENTS.md` 开工由四步回落到三步（去掉"扫诉求"），收工六步改为五步
  （"关诉求"换成"把需要队友配合的事写成可转发文字"）。
- `WORKFLOW.md` §2 拉取对齐由四处减到三处；§8 整节重写为"对外沟通：不进仓库"，
  保留三要素（要什么/卡住什么/怎么算完成）但载体改成微信文字。
- `scripts/brief.py` 去掉诉求段；`scripts/check_docs.py` 去掉诉求表检查，
  只保留 STATE 三条线的"最后动作/当前卡点"校验。
- `docs/INDEX.md`、`README.md` 的入口链路同步去掉诉求一环。

没做什么：不改任何技术结论、不改 STATE 的现状与关键数字。
## 2026-10-20 A 线补齐现场配置字段说明并识别夹具不匹配风险

用户贴出field_setup.json后澄清固定硬件是两个扬声器模块、一个MAX4466麦克风；此前把注释误读为双麦克风。操作包已修正为两组扬声器坐标，并区分麦克风增益与扬声器外置音量控制字段。配置仍有channel_mapping_verified空值与JSON注释等语法错误；operator_notes类型不符，音箱控制备注与确认标志矛盾。原标定资料没有完整记录扬声器布置，需先确认两只扬声器是否与标定条件相同，再决定夹具匹配标志。审查依据见[配置审查记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。

## 2026-10-20 A 线处理现场配置JSON解析失败

用户返回的summary为 `status=stopped`、`trials=[]`、`pairs=[]`、`sound_seconds_completed=0`，错误指向板卡 `field_setup.json` 第12行第33列的 `JSONDecodeError`。据此确认该次没有进入READY交互或播放项；由于板卡编辑版配置未提供，未猜测非法字符。操作包新增按行列定位、JSON语法核对和先重跑静音代码格1的恢复步骤，见[恢复记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。

## 2026-10-20 A 线澄清现场Notebook的READY输入位置

用户反馈执行代码格2后找不到 `READY` 输入框。截图里执行编号已经返回，且输出 `summary.json` 路径，说明调用已退出而非等待输入。脚本在异常退出时同样保存摘要；具体停止原因需打开板卡 `field_results/field_<id>/summary.json` 查看 `status` 和 `stop_reason`。已把这一判别写入[操作包](../experiments/field-validation/README.md)与[恢复记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。在停止原因明确前不重跑代码格2。

## 2026-10-20 A 线记录现场配置文件缺失的静音恢复步骤

用户补传运行器后报告代码格1缺少板卡 `field_setup.json`。该检查在静音核验中，尚未运行批次。操作包补充单文件上传步骤：电脑本地配置模板上传至板卡 `base → audio → audio_closed`，确认列表出现后只重跑代码格1；模板须等现场条件确认后填写，不能为通过核验臆填。操作依据见[现场操作包](../experiments/field-validation/README.md)和[预检恢复记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。没有播放音频。

## 2026-10-20 A 线修正现场运行器SHA256大小写误判

用户补传 `field_validation.py` 后，代码格1报告实值与预期哈希仅十六进制大小写不同，却因字符串区分大小写而拒绝文件。已把Notebook比较改为大小写归一，并在[操作包](../experiments/field-validation/README.md)说明：电脑本地运行器无需重传；只需覆盖上传新版 `field_trial.ipynb`，然后重跑代码格1。证据与恢复步骤见[预检恢复记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。尚未运行代码格2或播放音频。

## 2026-10-20 A 线修复现场Notebook缺少运行器时的静音预检指引

用户执行 `field_trial.ipynb` 代码格1时报告 `field_validation.py` 的 `FileNotFoundError`。回溯显示清单和闭环包哈希检查已通过，异常发生在运行器文件读取，代码格2尚未执行。已在Notebook中增加明确的缺文件/哈希不匹配提示，并在[操作包](../experiments/field-validation/README.md)写明只需把电脑本地 `board/audio_closed/field_validation.py` 上传到板卡 `base → audio → audio_closed`，确认文件出现后只重跑静音核验格。恢复记录见[静音预检记录](../../report/verification/field-validation/notebook-preflight-recovery-2026-10-20.md)。没有启动声源或运行批次。

## 2026-10-20 A 线审查 B 线分析交付并提出修订请求

审查 `src/feedback/path_analysis.py`、对应测试及 [B 线合成报告](../../report/verification/algorithm-2026-10-20/README.md)。`recommend_field_range` 当前以 `msg_bypass_conservative_db + 2 dB` 生成对照点，并注释称旁路应起振；报告交叉核对的旁路阈值为保守 −2.02 dB、相位口径约 +2.12 dB、整数闭环模拟约 +2.11 dB，因此代码给出的约 −0.02 dB 不能据此称为预测旁路起振点。要求 B 重新定义可行区间和保护裕量，无安全区间时明确不推荐现场点。

另发现加权候选在报告 ASG 等评分时使用浮点系数，JSON 同时附带 Q20 整数系数；要求用实际量化系数重算验证指标，避免浮点结果被当作可部署候选收益。测试文件有两份同名 `ModelArtifactTests` 定义；要求去重并保留覆盖。R-001/交接把“不含人声”作为可传输依据，与用户原始 PCM 未经同意不得传出的要求冲突；请求改为优先板上静默分析、仅回传统计 JSON，原始数据须获授权。上述事项记录于 R-004（当时的诉求编号），尚未修复或复验；没有运行板卡或播放音频。

## 2026-10-20 补上第三个通道：线间诉求

用户指出一个真实缺口：推到仓库后，别人的 AI 看哪里知道"我们在等他们做什么"？
上一版只做了现状（STATE）和时间线（log），**诉求没有家**——它散在交接文档和聊天里，
既没有责任人也没有完成判据，所以 R-001 那种"拷三个文件"的事会一直悬着。

新增 docs/REQUESTS.md（当天晚些时候已撤掉，见上方最新条目）：只有 open/done 两态，每条必须写清
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

## 补零等价确认与 8.4 kHz 裕度诊断（2026-10-23，B）

书面确认 256 抽头模型尾部补零到 512 与 256 抽头位流数学等价，条件是零落在最大滞后一侧：
Q20 加 24 位饱和逐样本 0/4096 不符、饱和计数同为 0；把零补到头部则 15701/16384 不符，
说明该判据有分辨力。工具 scripts/verify_padding_equivalence.py，C 的集成门禁可据此放行。

用 A 的房间 6 段标定批复核 8.4 kHz 啸叫：该频段模型没有反相（CD +21.5 到 +39.4 dB、相位差小于 5 度），
模型在本批的阈值是 +6.64 dB（必要）/ +7.32 dB（相位一致），而现场实测 -6 dB，差 13 dB。
灵敏度预算给出原因的量级：8380 Hz 处 1 拍等于 61.8 度，错位 0.5 拍阈值降到 -5.8 dB；
峰值幅度过预测 2.6 dB 即 -1.8 dB、4.5 dB 即 -7.4 dB。所以缺口是会话级传递差异，不是系数书写错误。

三臂对照的参考臂存在问题：cancel_zero（预测恒零、回路闭合）的阈值是 -11.11 dB，0 dB 时必须啸叫；
旁路臂是开环，任何增益都稳，不能当不用模型的基线。另给出两条可当测量手段的恒等式：
数字注入下 mic/ref 等于现场 H、mic/pred 等于 H/Hat，都与增益无关，
因此任取一段未压缩的闭环捕获即可同时量出现场路径与模型误差，不必另做标定。
见 report/verification/peak-margin-2026-10-23/。

## 汇总 v3 消费核对与历史缺口定位（2026-10-23，B）

核对 C 的 b2ad47d（schema_version=3、c-measurement-2.1.0）：可以直接消费。
软件夹具两行都命中本仓模型注册表，其中基线那行命中补零到 512 的系数数组、候选那行命中原数组，
256 到 512 的加载身份由数据侧证实，不依赖声明。尾段空值与门禁自洽，asg_db 为空。

历史 50 条全部 invalid：44 行缺 loaded_taps、缺 comparison 身份，且位流容量未登记；
6 行连 gain/音量/位流/系数/模型都没有。尾段 RMS、斜率、三频带与保护字段在全部 50 行都是空的，
所以历史批不可能产出可用配对。44 行都是 box_v1 的 256 抽头基线，系数哈希全部命中原数组，
说明这批从没加载过补零数组。

两个位流的归属查清：4d49dfbe 是已退役的 audio_closed（DAC 无输出）共 22 行，不能当声学证据；
dadbbbab 是 audio_replay 256 抽头共 22 行，需要先登记到 BIT_CAPACITIES 才不会永久判容量未验证。

同时修掉 B 侧清单的两处问题：补零产物的 file 带了 models/ 前缀会在相对解析时指错目录；
补零产物的系数哈希与原模型的补零哈希相同，两条记录并存会让按系数反查模型变成歧义。
现在清单分成 models（可部署 3 条）与 derived_artifacts（补零件，不参与注册），三份模型文件未改动，
新清单 SHA256 71d13ca9。工具 scripts/consume_summary_v3.py，测试 4 项。
见 report/verification/summary-v3-consumption-2026-10-23/。

## 会话修正系数与 A 的现场 H 复测（2026-10-24，B）

A 复测现场 H：8.38 kHz 相对标定批 -5.98 dB、+39.5 度，远超反证门限，会话传递假设成立。
用它把部署模型乘一个频带掩模，再用 512 实系数最小二乘逼近，得到会话专用候选
models/room_v1/session_20261024/（登记在 derived_artifacts，不进注册表，C 不会自动选）。

预测与实测对照：部署模型对现场真值的阈值算得 -7.42 dB，A 实测 -9 稳、-6 叫，落在括号内；
修正后阈值 +6.74 dB，限制点转到 381 Hz，A 门禁版实测 >=6 dB，两边独立收敛到同一量级。
带内修正残差预算：0.5 dB/5 度仍 +6.7，2 dB/20 度降到 +0.8，所以 6 dB 余量要求带内准到 1 dB/10 度。

方法上修掉一处错误：第一版拿模型自己当代用真值，把标定残差整体抹掉，自洽到 -30.9 dB 的假完美。
真值必须是标定批 H 乘掩模。另接受 A 的更正：mic/ref 等于 H 只在 reference 记录实际播放信号时成立，
若记的是增益级输出，预测为零时 mic/ref 等于 1/g；mic/pred 等于 H/Hat 不受影响。

## 低频 −15 dB 的可行性核算（2026-10-24，B）

A 要 300-1000 Hz 压到 -15 dB，我给出的是量化否定而不是一版新系数。
512 抽头在同一批上 in-sample 只到 -9.44 dB，交叉验证（3 段训练/3 段测试）只有 -5.15 dB，
680 抽头 -13.42(训练)/-5.10(测试)；同一批两半的 H 自身就差 -4.08 dB（相干 0.5 的估计噪声）。
加抽头对独立集无益，2048 反而更差，因为拟合的是噪声。

物理上的解释：381-435 Hz 那个峰 -3 dB 宽 95 Hz，Q 约 4.5，振铃时间常数 3.3 ms；
512 抽头 10.5 ms 只覆盖 3.2 个时间常数，压 20 dB 要 10 个（约 1600 抽头）。
而 681 抽头在本器件已经放不下（512 时 BRAM 80%），所以靠加抽头这条线是关的。

提出的替代是 8 倍抽取的二级：6.1 kHz 上 384 抽头等于 60 ms 记忆，MAC 只有主 FIR 的 9%，
延时线 384 字。这一步需要 A 加抽取链，不是改系数能完成的。

另外发现 A 的分带表只到 8600，而板上起振主频三次是 9131 Hz——限制点可能落在未测量的 8600-10250。
我这边的模型在那段是 -13.48 dB，但他那次会话的 H 在 8.4k 已经差 6 dB，必须重测。

见 report/verification/lowband-limit-2026-10-24/。

## lowband2 复核：瓶颈不是一个频段，答复选 b（2026-10-24，B）

用 A 的 16 段（mic 电平 σ 0.14 dB）和 model_512_strong 在留出 6 段上复核：
总体阈值 +4.56 dB @441，3898 Hz +7.33，1585 Hz +9.47——三个频段挤在 5 dB 内。
"缺口全在 300-1000"不成立，修好 441 立刻撞 3898。

加权重拟合是零和：低频 -6.10，但 1000-2000 掉到 +0.92，总体更差，不交付。
前向陷波组封顶 +9.18（435 陷完 3898 接棒）。

答复 A：选 b 物理解耦（宽带），不选 a 抽取二级（只修 300-1000，修完仍 +7.3）。
给位置扫描协议：0.5/1.0/1.5 m 各采一批开环，逐位置拟合报两个阈值，按全带最小阈值选。
435 Hz 处 0.5 m 只有 0.63 个波长，是压力场，1/r 不成立，必须实测。

口径澄清：9131 Hz 处 |H| 仅 -1.19 dB，8500-9200 只有 +4.56 dB @8762、Q≈23 的宽峰，
不是环路自激；429 Hz 峰顶在两半之间差 9.4 dB（几 Hz 频移），这是峰顶残差无法验证到 -15 dB 的根源。
见 report/verification/lowband2-2026-10-24/。

## 两级抽取仿真：+1.0 dB，不给 a 的参数（2026-10-24，B）

A 判 b 无效（降耦 5.72 dB 只换来 0.85-1.6 dB），要我给 a（8x 抽取 + 384 抽头）的 5 项参数，准备 1-2 天 RTL。
我先按真实结构仿真了一遍，结论是不值得：

延时预算先卡住：线性相位原型 65 抽头 -> 单次延时 32 样本，两级固定 64 样本 < 声学 125，剩 7 个抽取样本
可用；193 抽头原型（两级 192）直接不可行。
收益：300-1000 Hz +1.0 dB，其余频段 0；二级 256/384/512 抽头结果完全相同。

原因：一级 512 拟合后的残差与 u 在 300-1000 的相干只有 0.023（线性可解释上限 0.1 dB），
能被线性滤波器解释的部分已经拿走了，剩下是噪声/畸变/模态漂移。

抽头数也不稳健：三种划分下 512/680/1024 分别是 +4.19/+7.98/+8.99（前10后6）、
+1.79/+1.68/+1.83（前6后10）、+4.38/+4.00/+3.20（奇偶）。限制点在 441 Hz 与 8.3k 之间跳，
说明"唯一瓶颈 441"是划分的产物。680 那个 +3.8 dB 两次交叉验证都吐不出来。

也复核了 A 的 b 数据：侧放 max|H| +4.19@429、宽带 -5.34、必要 +8.63@358、相位一致 +10.38@337，
和他报的一致。机制是限制点从 441 移到 358，而 358 的 CD 只有 +8.16（441 是 +12.32），
相对误差恶化 4.2 dB，把峰值降的 1.92 dB 全吃掉。

顺带做了数据归档：A 发来的所有包移到 D:/Always/QianSai/_inbox/<日期_批次>/，
写 _inbox/MANIFEST.md 登记（含 sha256），仓库里 8 个脚本的默认路径同步改掉。
见 report/verification/twostage-2026-10-24/。

## 判据三处修正 + 两项筛选否定（2026-10-25，B）

按独立复核（bb56ef1）修三处：
1) 相位穿越重写为 positive_real_crossing：只在原始相邻且两端过门控的 bin 之间插值，
   用复数环路 Im=0 且 Re>0 判穿越，±180 折返不算。复核给的 400/410、+179/-179 反例现在返回 inf，
   并写进 sim/feedback/test_phase_crossing.py（4 项）。与复核四个数逐个吻合：4096 7.01/9.87，8192 4.75/7.95。
2) 时间域回归改分段构造，段间不共享历史。因此撤回上一轮"两级抽取 +1.0 dB"——那是拼接历史的产物。
3) 不再把 -10log10(1-C) 当绝对残差地板或 ASG，只当可解释功率占比。

基线重算（部署 Q20 + lag_first=1 + 2 拍调度）：同场留出 4096 +4.56/+10.71、8192 +2.77/+6.60；
部署 candidate_512 在新场次 −0.39/+0.09（4096）、−1.05/−0.65（8192）；反向迁移 −5.33/−3.94。
换窗长判据值差 2–4 dB，所以 <2 dB 的差异不写结论。

筛选 a 否定：ridge 1e-9…1e-3 从 +2.68 掉到 −1.22；低频加权是零和；多场次只有两个场次且 10-23 在
话筒故障期，无法验证。
筛选 b 否定：435/880/3900 三个 8 dB 陷波只换来 +3.5 dB，3.9k 缺口 488 Hz 宽，还要改前向通路和参考取点，
3 天内不值得。

交的是否定结果 + 一个决定：默认系数要不要从 candidate_512（10-23 拟合，在新场次 −1 dB）
换成 calibrated_20261024（同场拟合，+2.8…+6.6），以及"标定失败即旁路"。已把该系数作为逐字节副本
放进 models/room_v1/calibrated_20261024.json 并登记在 derived_artifacts（不进注册表，选择权在 C）。
见 report/verification/b-screening-2026-10-25/。

## 判据右端修复、Q20 生产入口与唯一复算入口（2026-10-25，B）

按 C 的审阅（f039f49）修三处：

1) positive_real_crossing 补上端点：虚部恰为 0 且 Re>0 的 bin，不论在区间左端、右端还是内部都算一次，
   按 bin 去重防重复计数。C 的最小反例（f=[400,410]、L=0.5·exp(j·[10°,0°])）现返回 410 Hz/+6.0206 dB；
   内部控制（±10°、|L|=0.5）保持 405 Hz/+6.1536 dB，没退回幅度插值口径。
   回归 11 项，含 ±180° 折返、跨缺口不插值、端点计数、Q20 身份与 lag_first 只加一次。
2) 生产入口改成部署口径：频响一律 coefficients_q20/2**20，并打印/校验 Q20 哈希
   （--expect-q20-sha256 不符即退出）；浮点只在 --dev-float 下可读且标注。lag_first 与 2 拍调度各计一次。
3) 复算收成唯一入口 scripts/reproduce_b_screening.py：输入清单与哈希、基线（两窗长分开）、
   FIR-off 基准（同一份 H、同一门控，Ĥ≡0）、ridge 与权重阶梯、EQ 幅度阶梯、分段边界控制、
   10-23 批次只作跨场压力测试。约 5 s 跑完，输出 repro.txt / repro.json。
   报告目录下的脚本副本与旧口径 run-*.txt 已删除，实现只有 scripts/ 一份。

基线（留出 seg_10..15，相干>=0.8、>=300 Hz）：8192 小增益 +2.77 dB @435、穿越 +6.60 dB @424；
4096 +4.56 @441、+10.71 @884。同门控 FIR-off 是 -7.40/-6.46（8192），即模型贡献 +10.2/+13.1 dB。
过门控 bin 只占 29.0%（4096 为 27.2%），其余记未知。

跨场：candidate_512 在留出段 -4.54/-0.62，但相对 FIR-off 仍 +2.86/+5.84 dB。
所以"跨场系数不如不装"是错的，正确说法是"不足以支撑 0 dB 工作点"；比较必须对 FIR-off，不能对 0 dB。

筛选：ridge 1e-9..1e-5 与部署模型差 0.1 dB 内、1e-3 起恶化；低频加权 x5 只 +0.7/+1.5、x20 反转为 -3.3/-1.9
（不是严格零和，但方向不稳且低于现场可验证量级）；EQ 三个 8 dB 陷波 +3.50/+3.41 dB。两项维持否定。
分段边界控制：切段评估差 0.53 dB，拼段拟合与逐段拟合差 0.00 dB，拼段评估把抑制少报 0.20 dB
——本数据上拼段不制造收益；两级抽取 +1.0 dB 的撤回保持，但不能归因于拼段。

默认模型按 C 的 RC0.1 定案关闭：calibrated_20261024 为默认，candidate_512 不作默认/后备，
manifest 状态改为 rc0_1_default_baseline_closed_by_C 并附离线参考数字，新清单 SHA256 8799f321。
10-24 会话修正那三个数（-7.42/+6.74/余量预算）用的是旧相位判据，STATE 里标为口径作废、仅存档。
见 report/verification/b-screening-2026-10-25/。

## RC0.1-r4 事前预测（2026-10-25，B）

C 的下一项任务：现场结果到达前先固定一份可核对的预测。工作在 r4 协议常量上（Q12=817／−14 dB／
Codec40／EQ identity／source −24 dBFS／pair 2.52 s／delay 2 拍），用低带 16 段和部署 Q20 复算。

核心结论：−14 dB 下 OFF 允许增益 −7.40 dB、ON +2.77 dB（留出 8192 全带），
即工作点余量 OFF −21.4 dB、ON −11.2 dB，两者都远在稳定区。而 r4 测得到的量是
mic/source = H/(1−gL) 的 ON/OFF 比，预测只有 +0.02 dB（单 bin −0.84…+0.88），
比配对门禁 1.5 dB 小一个量级 → **这一档只能否证，不能证明收益**；"跑完/未触发保护/60 s 通过"
在 OFF 臂也成立，零信息量。这条与 C 自己写的"不能单独写成抗啸叫成功"同向，但给了定量理由。

分带（留出 8192）：300–1000 90/117 bin、+10.17 dB；1000–3000 312/336、+12.20；
8200–8600 只 5/67、+19.00 但只代表 5 个边沿 bin——8368 Hz 峰顶（+6.64，相干 0.770）被门控挡掉，
所以这一带**记未知**。训练段能过 10 个 bin 且全带最差点就在 8368，说明同一峰顶在两种划分里
一个进门控一个没门，结论不稳。四个表（训练/留出 × 4096/8192）方向完全一致，无 worse_bin。

修正一处实现缺陷：预测段里写了 glob=rows[-1]，把模块 glob 变成 main 的局部名，
导致带 --cross-session-dir 时 [6] 段 UnboundLocalError（常规复算走不到那行）。改名 gtot，
补 ast 级回归（main 不得遮蔽模块名）+ 3 项预测表回归。全量 113 项通过。

统一脚本新增 band_switch_table / gated_bin_map / [7] 段 / --work-gain-q12，
输出 run/prediction.json。Part 二等 C 的 summary-v3.json（fir_switch_pairs）回包再判。
见 report/verification/rc01-r4-2026-10-25/。

## r4 预测口径修订 1：两臂闭环（2026-10-25，B）

C 的反例成立：M=0 时 OFF/ON 必须完全相同（0 dB），我原稿把 OFF 当开环 H 直接比，
在 H=0.5、Q12=817、429.153 Hz 给出 +0.906 dB。修成两臂闭环：
    T_off = H/(1−gDH)，T_on = H/[1−gD(H−M)]，带内做 |T|² 功率积分。
余量改成"允许增益 − 实际增益"（原来写成 g+允许，那其实是环路增益，标签错）。
新增两个闭式控制：M≡0 → 精确 0 dB；M≡H → Σ|H|²/Σ|H/(1−gDH)|²，实测与闭式差 <1e-15。

修订后（留出 8192）：允许增益 OFF −7.40 / ON +2.77；余量 **+6.60 / +16.78 dB**（与 C 的 +6.605/+16.778 一致）；
ON−OFF 全带 **−0.42 dB**（逐 bin −4.06…+2.46），300–1000 **−1.15**、1000–3000 −0.22、
8200–8600 +0.31（5/67 bin，不可判）。四个表方向一致：ON 略安静、低频最明显。
所以原稿"全带 +0.02 dB 基本无差"作废；正确说法是"ON 略安静但不是零，也不是抵消无效"。

C 的另外三条也改了：
- 删掉"1.5 dB 以内分辨不了"——配对漂移门禁是配置一致性门槛，不是测量分辨率；
- 保护 ≠ 啸叫；|g·L|>1 不充分证明失稳，也不能给固定增长时间（385 dB/s 只作定性说明）；
- README 原写"更差 bin 全 0"与 JSON 冲突：三个带内确实 0，但留出 8192 的全带行有 1 个，
  在 3516.7 Hz（不在三带内），4096 为 0——已在修订稿里列出，不当恶化结论。

14408 帧按 C 说明是尾部有效子窗、运行仍 2.52 s，原"单位待确认"删掉。
原稿保留在 README.md（顶部加横幅注明作废范围），修订写在 revision-1.md，标明"口径修订，非事前预测"。
回归：预测表 5 项重写（含 C 的 429.153 Hz 反例、闭环 OFF、闭式 M≡H、更差 bin、余量定义），
全量 116 项通过。输出在 run-rev1/。

## N1–N3 发布口径 + Part 二 实测判读（2026-10-25，B）

Part 二（基于 C 的 896657b 的 c-r4-to-b-r1.zip，sha 47497527…，2 组配对）：
两组资格齐全（configuration_matches / window_comparison_valid 均 true，reasons 空），
四试次帧区间完全一致 107174–121582（14408 帧尾部子窗），无保护/削顶/早停，source_response.valid。
ON−OFF：总 −0.171 / −0.244（两次都 ON 略安静）；300–1000 −0.756 / +0.051（方向不一致）；
1000–3000 −0.120 / −0.445；8200–8600 +0.379 / +0.253。
对内门禁漂移 0.086/0.115 dB；跨 repeat 的 OFF 臂自身差 0.690 dB，与低频那次 0.807 dB 摆动同量级，
所以不能把低频摆动读成"抵消有效/无效"。
与修订预测对照：总/中/高三个同向，低频一次反向。统计量不同（预测是合格 bin 白谱稳态参考，
实测是整带麦克风 RMS；14408 帧 0.295 s 受迫响应；标定 −12 dBFS vs 源 −24 dBFS），不换算。
不产生 MSG/ASG（summary 里 measured_msg_db/measured_asg_db 均 null），不写整体成功；
OFF 臂本身余量 +6.605 dB，"没叫"两边都成立。

N1：max|gL|<1 只说充分非必要、门控有缺口就不担保全频；余量=允许−实际、环路增益=实际−允许=−余量
（旧"实际+允许"是公式错误）；删掉 385 dB/s。
N2："全带"改称合格 bin 白谱稳态参考；否证降级为调查触发；repeat 散布只描述本批，不替代 1.5 dB。
N3：入口 [7] 标题改"口径修订 1"，JSON 加 revision=1/pre_registered=false/supersedes。
交付：revision-1.md、part2-field-pairs.md、run-rev1/{repro.txt,prediction.json}。116 项测试通过。

## N1 残句清零 + Part 二归因降级 + 5 原件波形复核（2026-10-25，B）

C 的 9b2424 验收：3657242 的 N2/N3、配对原值、默认模型都通过，剩三处发布修正，另要求补波形侧判读。

1) N1 残句：全部改称**采样网格小增益界 B**（1/max|·|，只在过门控 bin 上，充分条件非必要、有缺口不担保全频）；
   §1 旧表格里"其实是环路增益"改成"负号算两次的公式错误"；band_switch_table docstring、入口 [7] 标题同步；
   JSON 增 criterion_kind=sample_grid_small_gain_bound。revision-1 加术语表，把五处旧说法逐条对照。
2) Part 二归因降级：0.690 dB 是两次不同定音试次各自的读数，不证明房间/通路变过，也不能确定它造成
   低频 0.807 dB 摆动；−12 vs −24 dBFS 的电平差不能证明 H 随电平变、也不能证明低频受影响更大 → 原因记未知，
   并写明要判它需要同批重复定音或第三场同夹具标定。
3) 撤回"OFF 臂本来就稳"：+6.605 dB 是网格上的界、71% 缺口，证明不了全频稳定；可写的只有
   "r4 两次有效源内响应记录未触发保护"，且不提供 ASG 识别证据。A 的另一轮真人会话（−14 dB 触发保护）
   单独登记为 §9，两个方向都不下结论（不拿参考余量否定事件，也不据保护判啸叫/模型失效）。
4) 波形侧复核：新增 scripts/verify_r4_waveforms.py，包 5/5 哈希、4 试次 prediction/residual/output
   全 0 失配（15872/15872/16382 帧）、60 s 尾环 prediction/residual 0 失配、响应窗 107174-121582（14408 帧）、
   由原件重算的两组配对与 summary-v3 差 ≤7.1e-15 dB、与 C 的复核电平差 0.00e+00。
   60 s 的 output 记为未测（包里无 source_pcm16），不并进"通过"。

踩坑：第一版用 cap.get("bypass") 判臂别，而 bypass 只在 metadata_json 里，于是 bypass 臂按 FIR-on 算，
residual 整段 15872/15872 失配——像"原件有问题"，其实是检查器错。改为从 metadata 传入，并加回归
（test_r4_waveform.py 8 项，含"故意传错臂别必须报失配"）。全量 124 项通过，check_docs 0 错误。

## 波形检查器补整体资格判定（2026-10-25，B）

C 的 R-007 只剩这一项：verify_r4_waveforms.py 的 main 原来只按 pkg_ok 返回，其余失败只打印不拦截，
所以"算出来有失配"也能退出 0，产物看起来像合格结果。C 复现了五个反例全部退出 0（D2/D3/D4）。

现在四项同时成立才返回 0（否则 2）：
1) 文件齐全：包哈希/字节数 + 角色件数（2 个 FIR-off、2 个 FIR-on、1 个 60 s）；
2) 模型绑定：每次试次 metadata 里的 coefficients_sha256 必须等于给定模型的 Q20 哈希；
3) 算术：4 试次 prediction/residual/output、60 s 的 prediction/residual 必须 0 失配；
4) 显式对照：给了 --summary-v3/--c-review 就必须存在、可解析、差值 <=1e-3 dB。
不合格时打印"判定：不合格（N 项）"+代码，waveform.json 写 ok=false 与 failures，判定行也写进 waveform.txt。

回归 test_r4_waveform.py 扩到 14 项，新增 CliVerdictTest 6 项（整包正例必须 0；改一帧 prediction、
删 60 s 并漏列、模型 Q20 首项 +1、汇总差分 +1 dB、显式不存在的汇总，五种坏输入必须非 0）。
自建合成包（11000 帧 × 5 件）跑 subprocess，不依赖真实 200MB 原件。全量 130 项通过，check_docs 0 错误。

## 回 A："512 能不能在最差频段给 15 dB"——不能（2026-10-25，B）

A 新布局（100 cm 侧对）净耦合 +3.0 dB，要 +6 dB 数字增益（环路 +9 dB），问 512 抽头能否给 ≥15 dB。

用 lowband2 16 段（训练 0-9 / 留出 10-15，Welch 8192，相干 ≥0.8，延迟 2 拍）算：
绑定 bin 435.1 Hz（相干 0.945），|H|=+6.62 dB、|H−Ĥ|=−2.77 dB → **CD=9.40 dB、g_max=+2.77 dB**。
+6 dB 需要该点 CD 12.62（差 3.23）；按 A 的峰值（宽带 +3.0，峰/宽带比 6.2 → 约 +9 dB）则需 15 dB，
差 5.6。所以**"15 dB"不成立**，且不是抽头能补的：256/512/680 → CD 4.50/9.31/10.18、
g_max −2.90/+2.68/+6.11，680 既装不下（512 时 BRAM 80%，上限 681）又把限制点跳到 3898 Hz。

关键结构发现（这次最有用的）：逐频查表里**只有 435 Hz 一列是负的**（g=+6 时差 −3.23），
第二紧是 3898 Hz（+0.41）。所以短板是一个模态峰，不是整条曲线。
推论：435 若被压 3.3 dB，限制点立刻换到 3898，天花板 +6.41 dB——对 +6 dB 只有 0.4 dB 余量。

自洽性：A 说 0 dB 就饱和 → 0 + |H|peak > CD → |H|peak > 9.4 dB，与他宽带 +3.0 一致，
也说明该点 CD 现在就不够，+6 dB 只会更不够。这个结论**不依赖他的曲线**。

工具 scripts/answer_gain_budget.py（只读，不改模型），输出 report/verification/gain-budget-2026-10-25/。
边界：数据是旧布局 0.5 m 正向；A 的侧放实测已证明降耦 5.72 dB 只换来 0.85-1.6 dB（限制点移到 358、
那里 CD 只有 8.16），所以"降耦"不能按 1:1 兑现，必须按新数据重算。要他的 2.4 s 捕获 + 曲线 + 延迟
才能把结论收紧到新布局。

## 波形入口三处身份门 + 增益预算 N1 口径（2026-10-25，B）

C 又复现三个"退出 0 且 ok=true"的反例，都是身份没绑住，已修：

1) 09-fir-on.npz 仍在磁盘、仍被读，只从 manifest 删掉 → 之前只遍历清单条目，这文件从未核验却照样算。
   现在每个被读取的文件都过 verify_used_file（必须在清单内 + sha256 + 字节数），否则 unverified_file。
2) 模型 lag_first 1→2、Q20 不变 → 之前只比 Q20 哈希，算术还写死 lag_first=1。
   现在 lag_first 必须等于部署约定 1（model_convention），taps 与 loaded_taps 必须等于 Q20 项数
   （model_identity），算术改为用模型声明的 lag_first。
3) summary 首组 off_capture_id 换成别 id、数值与 valid 标记不动 → 之前只比数值。
   现在按 capture 身份绑定：id 必须对上实际捕获，独立核对臂别（off=bypass/on=非 bypass）、
   gain_q12、两臂响应窗逐帧相同、四试次各用一次；数值由这两个实际捕获重算；
   configuration_matches/window_comparison_valid 只作一致性检查，不当身份依据。

回归 test_r4_waveform.py 18 项（新增 4 例：文件未登记、lag_first 漂移、capture id 替换、off/on 对臂）。
用 C 的 948f836 检查器本机复跑 8b01999：passed | positive=passed | bad_rejected=8/8，exit 0，
脚本 sha a24e2cd6…b57。全量 134 项通过，check_docs 0 错误。真实正例数字与 12e5ce2 完全一致。

另外按 C 的要求把增益预算的口径收紧：
- 一律叫"采样网格小增益界"（充分条件上界），不再写"最大允许增益"；
- 明确旧场（0.5 m 正向）数据**不能证明**新布局"不能"，也给不出"唯一出路"，
  只能说"若限制点仍在 300–6000 Hz 且 CD 同量级，则差 3…8 dB"；
- 删掉"唯一出路""唯一可能翻盘"这类断言；标注未经 C 独立复算、不参与现场放行。
数值一个没变（9.40 / +2.77 / 12.62 / 5.6）。
