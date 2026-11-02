# 常驻重标定产品软件协作记录

2026-11-01，C线，Codex。以下用户提示为本轮原文；后面是执行摘要，不冒充完整模型逐字回答或隐藏推理。

## 用户原始提示

收件人：C
事由：工作流调整——你负责一键重标定的产品软件与整机入口

这是队长本轮的新任务。你不再只负责事后验收、汇总和材料。
最终软件必须让普通使用者不靠 AI、不改代码、不选模型，仅按实体提示完成重标定并开始扩声。

已有测评、保护检查、身份校验和打包工具继续复用。
重点检查：
board/audio_replay/layout_experiment.py
board/audio_replay/experiment.py
board/audio_replay/recal_entry.sh
scripts/assemble_experiment.py

一、职责与并行接口
你拥有最终流程编排和统一入口；A 提供硬件适配层并唯一操板；B 提供数值判断与拟合接口。
先给出一份最小接口及输入/输出样例，随后使用模拟硬件和固定算法返回值开发，不等 A/B 全部做完。
接口约定谁改哪个文件，避免 A/C 同时重写 recal_entry.sh。
复用现有入口，不保留两套互相竞争的“正式一键入口”。

二、实现明确状态机
至少包含：
待标定→提示讲话/检查输入→提示安静→自动激励采样→拟合→独立验证→就绪→运行。
任一步均可进入取消、失败或保护停声。
需要重试时由程序按 B 的有界规则执行，不能要求用户看日志选择技术参数。

板卡上常驻运行，日常操作不依赖电脑或 AI 在线。
启动默认静音，不自动制造声学闭环。
现有单次运行时限到达后必须给出真实结束状态，不允许用拼段断音冒充无限连续。

三、人机提示
与 A 对接实际可用 LED，建议：
白色慢闪：待标定；
青色闪烁：轮到用户讲话；
蓝色闪烁：请保持安静，系统可能播放测试声；
黄色：计算/验证；
绿色：验收通过、可启动；
红色：失败或保护停声。
用闪烁方式或文字补充含义，不能只靠颜色猜测。

讲话前可播放三连音，提示音及衰减尾声必须排除在有效测量窗之外。
提示必须在准备完成后发出，不能叫用户讲话后还初始化、写代码或等待计算。
抵消/旁路用独立指示，显示实际生效模式。

四、配置和模型事务
每次运行绑定：
AUX 实际回读、Codec 音量、数字增益、采样率、模型、驱动和位流身份。
候选模型通过预定验证后才成为当前模型；安装过程失败不能留下半更新配置。
用户移动设备并重新标定后，如果标定失败，旧模型可以留作归档，但不得静默恢复到新场景继续播放。

结果至少区分：
有效通过、数据不足/无法评价、模型拒收、输入过载、硬件异常、用户取消。
不能把“无保护触发”直接当作抑制成功。
听感记录与自动数值判断分开保存。

五、软件验证与最终交付
先用模拟硬件覆盖完整成功流程，以及取消、削顶、数据不足、模型拒收、安装失败、身份混搭。
验证失败不会启用候选，计算过程不妨碍处理停止请求。
复用已有成熟检查，不重跑与本次改动无关的大量旧项目。

交给 A 一个安装包、唯一启动入口，以及按键/灯光操作说明：
明确文件在电脑还是板卡、具体路径、首次安装步骤和日常操作步骤。
日常操作说明不能再让用户打开若干脚本寻找某个代码格。

A 只需在一个完整现场窗口测试两种布局和拨码对照；你根据同一回包完成独立复核，不为格式问题要求重跑已有有效现场数据。

六、完成标准
陌生队友能按提示完成：
移动设备→按键重标定→按提示讲话/安静→看到明确结果→启动扩声→拨码切换→停止。
成功与失败都无需 AI 现场解释下一步。

交正式包、接口版本、软件验证结果、操作说明和提交号。
使用自己的分支，不覆盖 A/B 文件；通过人转发交接，不使用 REQUESTS.md 自动等待。

## 采用的设计和纠错

- 先核对main=f378262；A现有hw_api明确缺按钮/LED，stop通过重采集实现。没有将其冒充产品v1能力；C声明入口归属和A/B接口后用纯软件硬件/算法固定返回开发，不连接板卡。
- C唯一recal_entry.sh保留正式名字，原experiment/layout_experiment仅标为历史证据入口。复用assemble_experiment的产品分支、load_candidate的Q20检查和哈希方法，没有更改A/B实现或新建第二套正式启动方式。
- 计算使用可终止子进程，硬件用后台线程和A并发abort约定；取消令牌/任务代次阻止迟到结果启用模型。模型先归档不可变bundle，静音安装读回后原子提交current；重新标定先使旧场景失效，绝不自动回退播放。
- 首次14项用例有7失败/1错误，主要为Windows不允许对只读文件句柄fsync及测试导入漏scripts路径；改为写句柄flush/fsync和显式测试路径。原原因与后续输出在软件回执中保留。
- 复核了开环标定0增益与运行增益不同：按封装阶段表绑定实际值，并与A允许集合交叉检查；就绪/运行恢复严格配置。没有拿运行参数伪装开环回读。
- 追加非正cue结束帧的停止用例，避免零值触发重复提示循环；拒绝负捕获帧/坏源SHA。模拟模型即使B固定返回通过也不能进入实体模式安装事务。
- 21项定向用例通过；独立解压进程模拟到ready，缺适配的实体启动退出2，导出/只读回包核验通过。安装包文档链接修正后七项可执行/配置载荷与已跑进程的版本逐字节相同，复用该进程结果，未重复旧大套。
- 真实Linux安装、灯键映射、A/B适配和两布局现场验收未执行。回包审计只宣称身份/作用域核对；真实数值重算必须使用同包非人声原件及封装B接口，不把模拟/无保护当实际收益。

接口与操作说明见[产品v1](../../docs/contracts/recal-product-v1.md)、[操作单](../../docs/ref/recal-product.md)。机器证据：[软件验证](../verification/recal-product-v1/software-tests.json)、[安装包检查](../verification/recal-product-v1/package-check.json)、[实际模拟接口样例](../verification/recal-product-v1/interface-samples.json)。

## 2026-11-01 B交接原文

```text
B → C（接口已就位，契约在 docs/contracts/recalibration-policy-v1.md）
五个函数，from feedback.recal_policy import ...：
check_capture → plan_excitation → select_probe_frequencies → check_fit → check_three_point，最后 decide() 汇总。
三条要你确认的事：

decide() 默认 require_three_point=True：只有采集合格 + 模型可部署、没有三点数据时，返回 INCONCLUSIVE/DATA_INSUFFICIENT，不会返回可安装。如果你的状态机想自己控这一步，显式传 False。
四类 cause 分开：HARDWARE_ERROR / MEASUREMENT_INAPPLICABLE / MODEL_UNQUALIFIED / DATA_INSUFFICIENT，处置不同，不要都当“失败”处理。
check_fit 的 expected_peak_tap 必须传本轮 estimate_lag 的结果，不是上一个模型的峰位——换摆位时两者差几十帧是正常的。

两个阈值我按已发生事实改过，理由写在模块顶部注释里：MIN_EXCITATION_SNR_DB 从 6.0 降到 0.0（主判据改为门控率 ≥30%，否则部署模型自己的训练集会被拒），峰位基准改为本轮实测延迟。
最小输入输出样例在契约 §3，report/verification/recalibration-policy-2026-11-01/cases.json 里有 8 例真实数据的完整返回，可以拿去对字段。
```

### C处理与范围

先fetch/pull C，固定B=edfa698；七份B源/测试/契约/历史回执原字节接入，另增C消费器，不改B阈值。确认三点强制、本轮延迟和四类cause；额外阻止decide在只给three_point时产生的部分READY进入安装。已存八例仅映射字段，原表D3明确为构造样例，不能把八例全部写成实测重算。66项定向软件测试通过，含真实库、C边界及模拟整机；首次本轮66项已通过，增加包内B依赖和独立导入检查后再次验证受影响组合通过。两次均未使用现场音频或控制板卡。

读取main=31882e0：新版位流已有BTN0/LED/SW和采集实测，hw_api代码新增灯键方法，文件顶部旧说明尚未同步；不据旧说明宣称硬件仍无I/O。create_product及整机适配清单未交，B纯判定库也不能代替实际拟合包装；软件包仍明确只供模拟检查。

检查回执见[B策略消费](../verification/recal-product-v1/b-policy-integration.json)。契约扩展单独提交，人工转发交接，不操作REQUESTS、不推main、不改A驱动/RTL。

包复核时发现新增inconclusive未加入模拟单次入口的结束集合，已在交包前修正并增加独立进程的无法评价退出用例；最终67项通过，避免模拟入口在无结论时常驻等待。旧66项记录保留在dc589fe的历史回执，未出现测试失败后改口宣称通过。


## 2026-11-01 A/B新交接与C处理

用户转发A main=c49662d：板上/home/xilinx/jupyter_notebooks/base/audio/audio_io/，仓库board/audio_replay/v3-io/；hw_api f6174972、driver 22851d32、bit 32235065、hwh bbe1eb49。create_product已实现，prepared_capture如实为False：overlay复用先Bus error，关闭restore_stock后源加载52043e80失败，实际每次重下约1秒。A请求C决定是否阻塞、是否同意cue+input单次调用，核对events命名并给额外打包字段；BTN0长按CAL、BTN1开始/停止、BTN2安静、BTN3取消，allowed_gain_q12=[1631,2303,3254,4096]；强调poll直读及armed不得写LED。

用户转发B 0bdf7fa：真实recal_algorithm.evaluate、契约recalibration-algorithm-v1；fit预算必须>=15秒，PC fit约0.45秒/validate约0.10秒。三档低到高-22/-19.3/-16.5dBFS，每段16384帧、白噪、peak_cap .80，6训练/2验证；retry仅input激励/相干不足及fit REJECT_SCALE，shape与validate不重试。qualifies_cancellation是独立段预测抑制；每次evidence.not_asg=true/meaning明确非MSG/ASG/听感。独立验收改为300–460Hz时间域，不再按随窗漂移的CD/界差。

### C决策、证据与纠错

- 先fetch并pull C；A/B固定快照只读，B六交付文件原字节接入；C未改A/B算法或操作板卡。首次导出误用了不存在的根driver路径，改从git tree核实v3-io确切路径，不拿旧文件凑齐。
- prepared_capture=False当前阻塞。C同意A在硬件适配内合并cue+input；新增请求/scene绑定的input_ready，同域排除提示和尾声。C负责唯一入口、状态机和算法包装，A负责驱动/原子采集/实体灯键，不并改入口。
- 实际A根f617为False，包内2f253仍True，原包8/8哈希自洽。C选用户指定的根f617拼独立审阅件并保留身份分裂证据，不改A仓库或伪造原manifest。
- A纯Python适配调用配mock MMIO/捕获，证实六段训练请求只返一段默认3秒；armed indicate仍写；install把Q20 SHA混作文件SHA。另源固定16000零、路径忽略run_dir、gain/时长/模型回读等问题按代码列入一次性交接；不把静音耗时9.8ms单独当并发driver已停止的证据。
- B input会检查reference宽带与相干，C改为讲话健康独立检查，训练后才调用B input。B fit/validate实际source保留；30秒预算、attempts_total和三档实际源一次封装。预测通过另存heldout_prediction/not_asg，不偷换成三臂效果。
- B在target-lag<0时np.zeros(shift)报负维度，以相差1帧的本轮延迟复现；C不修改B数值逻辑。原validate未检查两段最小值，C按B契约在消费边界拒收单段。
- 首次82项有14错误：B测试写系统临时目录权限不足，改TEMP/TMP/tempfile.tempdir到仓库tmp，B原测试不改。C新增10项初跑两失败：mock run在启动sleep后可迟到arm、缺ready测试在其他线程读走事件后才清空；修正mock取消检查与夹具发送开关。最终95项通过，含B原15项、策略/消费者及产品相关检查；不重跑无关旧大套。
- 正式启用仍有A/B外部缺项；交deployment_ready=false的真实组合审阅件，入口检查在导入A硬件前拒绝。只推C，人工转发交接，未使用REQUESTS等待。


## 2026-11-01 A a3f516f / B 2ccf746交接

用户要求按A a3f516f接create_product到C唯一入口，A仅提供硬件对象，报告prepared_capture=false、每次重下载约1秒、有效源16382帧及首段11dB偏高；请求create_product/capabilities/prepare/training1/install/run3/abort链路与事件/安装字段确认。用户转发B冻结recal-algorithm-2026-11-01，要求identity版本/文件SHA入包及每轮、evaluate直接接请求、ATTEMPTS原样、fit>=15秒；预测资格不等整机/ASG/听感。

C先fetch取得A/B指定对象和后续main=12a5491；pull C首次TLS EOF、重试成功。指定A/B按固定对象处理，不把后续保护/预热修正静默混入。B契约原样更新单独规则提交；C未改B冻结字节、未操板。

从C main调用原A factory，只有MMIO/PYNQ、Codec和driver叶子替换，实际执行方法链并保存断言；105项相关检查通过。字段事件名与install双哈希已兼容。维护通过同一recal_entry --adapter-check，A显式给当前模型路径和完整SHA；不默认装仓库旧模型，混SHA在硬件创建之前拒绝。最终finally abort，下一捕获生效不提前提交eligible模型。

B直接evaluate已支持讲话，C正式profile撤掉自己的讲话阈值；同档有限重说、fit才升档，包/每轮/worker绑定B identity和EXIT_REASONS。canonical ATTEMPTS未改，另给每操作flat captures传输计划及4242/4243种子；原件可从白名单run_dir_root按SHA复制接入scene，原件和metadata不改。

复核A原manifest实际8项并全吻合，根与发布API均3549；没有按消息“9项”编造第9项。对已有bwindow八原件，首次假设metadata带source SHA导致KeyError，随后明确从原PCM计算来源SHA并保留metadata缺项，不让格式问题迫使重采。全部有效源窗16382；B全6训练因采集资格拒收，原训练/验证源SHA共享。去首段5段仅回顾诊断fit通过（L1约1.788、峰位/本轮延迟130），不自动删除首段或当验收。B帧数适用域裁决及A固定预热仍待明确。

只读取得A后续真人30秒completed/“有放大、清晰、无啸叫”回执，归为A现场和主观记录；回执自身注明C正式入口尚未调用、尾窗仅16384帧。没有将其写作C上板/ASG。当前prepared_capture=false依然阻塞默认产品流程；先prepare后input仍重新下载，未将“明确等待”当作原子窗已实现。


## 2026-11-01 收口指令与A22/B.1

用户转发A=22c88bb：ProductHardwareV2、op=input/cue合并调用、plan训练验证、原件/实际身份、实际install与即时模式指示、19秒旧调用晚返回；给原始product-adapter/physical-controls和ca764…源码，要求重组后一次完整现场。B=0b09ef6/版本11-01.1/SHA489064…修正正负移位、0/1验证段、可达上限，要求同一数据复核。用户特别要求：“我们需要尽快收束任务，完成以上留言任务后只有在真的还需要A或B端做出改动再发留言，不要习惯性不管三七二十一给他俩发留言”。

先fetch成功；pull两次TLS EOF，改用本轮已fetch的origin/C本地对象pull/rebase，Already up to date。固定用户指定源码，不操板、不改A/B。B契约原样更新单独规则提交。

A原版纯Python方法配替换驱动/MMIO复现training与cue_input的私有__meta名字错误。为定位后续，仅隔离审计临时提供父类私有元数据别名，install随即numpy.load(JSON)失败；再临时提供JSON解析桥接才观察到gain=0/loaded_count=None。所有诊断桥接都未写入候选。预置取消Event的原版training仍调用driver一次，保留源码与实际异常轨迹；这是需要A修改的取消传播缺口，而非要求19秒调用被强杀。

C吸收晚返回：stopping及时静音、旧调用结束前互斥新任务、显式CAL可排队/STOP撤销；重复结果用原代次拒绝。A计划每次levels只封当前档，独立请求目录防覆盖；缺窗口字段从原NPZ元数据和真实源SHA接入，不改PCM。嵌入cue选2.5秒在既有源RAM范围内，听到提示音后讲话；受控现场开关逐包允许，本已知错误版本不开维护/现场。

首次受影响70项只有旧测试“立即ended”断言失败，实际已及时mute并进入新增stopping；保留失败回执，改为先查及时mute再等待收尾。新增显式安全指示兼容后72项通过，B源码精确吻合489064…；无需重复无关旧大套。同一8原件按B.1重新计算，全6采集资格/原验证同源仍拒收，去首段5段仅诊断fit通过；没有把软件补丁修好当原数据已合格。

此次只向A提供私有方法、install解析/增益/数量、取消传播4项必要修正，不给B追加任务。重组包保留A原描述和源码，门槛关闭；所有原片/原PCM/ZIP仍不自动进Git。

补充一次必要核对：A22继承run方法的AST与12a5491实物回执版本一致，elapsed从初始化前计墙钟，已记录请求30秒/返回35.755秒的A原回执；需要真实音频帧时长分列，列入第4项必要修正。C同时允许run静音初始化期gain=0，但armed后立即恢复严格运行gain校验，避免把初始化过渡当配置漂移。最后受影响72项通过，不增加B任务。


## 2026-11-02 A280收尾接入与必要取消边界

用户转发A=28051a6：hw_api SHA1378b2…，真人cue及6+2/装载/静音/abort/30秒硬件层实测；明确C正式入口未上板、现场未真正拟合、不同讲话电平不能归因抵消、50cm真人cue未做。请求用该版接入完整流程，字段问题才转给A；沿用用户“只有真的需要A/B改动才留言”的要求。

fetch取得origin/A280，pull本地远端引用首次Git/MSYS权限失败，提升后Already up to date；不操作板卡、不合main。A v3-io八项清单吻合新字节，但docs/contracts/product-adapter仍钉A22及旧blockers，C保存原件并按实际payload归一，不为格式重新派活。

首次原版A工厂+C Product+真实B子进程仅替换硬件叶子，input/fit/validate均完成，随后C轮询install阶段尚未恢复的gain0导致“阶段数字增益回读不符”。C增加安装静音过渡，兼容A重序列化scene副本：校源SHA、逐项JSON、Q20和实际loaded_count，再归档/原子提交。run.elapsed是末尾16384帧环窗而非运行长度，C从原NPZ completed_frames/done/模型身份复核完整时限，不再拿环窗当提前结束。实际离线到ready和ended，3秒请求完成146484帧=2.99999232秒；0.336秒环窗原字段保留，不声称上板。

原版A取消复现：预置Event的training/input/run不进入driver；install仍进入，因为dispatch调用_install(request)而未传第二参数。模拟driver初始化期间置Event，training/input/install/run均未提供before_start，input/install/run仍completed。C的即时abort和收尾等待无法阻止初始化之后重新开声，所以只向A请求这一边界修正；不重提已修的私有方法、JSON、增益、数量或时长问题，不给B追加任务。

补充C可独立完成的收尾：启动零系数bootstrap文件清单固定、绝对路径、拒绝eligible；初始prepare允许A批准的历史静音增益，运行仍严格当前增益。A可能把第二scene输入落进上次调用目录，C限定自身state根按本次marker/SHA接入，保存原路径不改PCM。四灯ready/ended改0110、运行LD0且LD3留给实际模式；input初始化保持等待灯，三连音结束才轮到讲话，不提前亮“讲话”。

首轮新增bootstrap测试误用带simulation=true的模拟模型，因此先被“模拟模型不得安装到实体产品”拒绝；修正测试夹具移除simulation后检查bootstrap专用拒绝，未放宽生产校验。原75项失败输出留作本轮prior_run，旧72项历史回执恢复原字节。


最终75项通过，137文档零错误/警告。一次额外完整入口检查与测试并行时，审计脚本自身20秒总截止落在validating（没有生产阶段超时）；按唯一入口实际OPENBLAS_NUM_THREADS=1串行运行，并给审计总过程90秒后，首scene ready→run→ended、第二scene重新拟合到ready，8.4秒结束。无B代码/阈值变更；审计脚本截止纠正与原失败说明保留。


冻结时首次独立解压发现OPERATIONS两处链接越出白名单（B契约和历史报告）；保留失败ZIP另名，修正为包内ALGORITHM及源码仓库报告说明。没有改运行/数值逻辑，未重复无关测试；新实际包独立解压重新查全链接、全部SHA、真实B worker、A helper接受零模型、默认/维护/现场均exit2，通过。源码5230e0c，33载荷，ZIP不入Git；实际SHA见a280-package-check.json。


## 2026-11-02 A593重新冻结与维护开放

用户转发A=5939ee5：新hw_api 9cb48a0…、driver 0dc80c2…，要求“打开adapter_check_allowed: true”、新ZIP“放仓库根目录即可”。A已核旧ZIP ce5f2…完整部署，--check显示旧missing，--adapter-check因旧adapter_check_allowed=false拒绝；A明确不私换文件造成manifest身份不符。预期新包check部署就绪，再由A运行无听众适配检查，已有有效数据不重采。

fetch取得A593，C本地pull/rebase已对齐。原版代码已透传training/validation/input/install/run回调，driver在解除codec静音前和最终arm前均检查。原manifest实际8载荷、加清单自身9文件逐字保留；原适配描述仍旧，C只归一实际driver/helper身份，不因格式请A补单。

12个原版方法+模拟驱动初始化检查：五条路径各两项均阻止开声；父类prepare预取消仍调用driver，初始化取消仍无回调，真实存在既有取消要求的遗漏。按用户授权开启维护，但不将正式deployment_ready伪写true；只保留prepare具体missing，移除已关闭的install/运行缺口和泛化未批准提示，field-trial关闭。

C现有adapter_check短链路成功；维护模型若fixture改变，C main应从已核SHA模型取fixture_id再创建对象，新增一行并在既有原版A工厂测试中用不同fixture验证，7项通过。另真实B子进程、原版A工厂、模拟硬件叶子完整走两scene，首个ready/run/ended，第二个重新拟合ready。未改A/B源、未操作板卡、不重复无关75项。


新包在仓库根目录，35载荷加product-manifest共36文件，source=e6adcf2、SHA见a593-package-check.json，附同名.zip.sha256且两者被定向ignore。独立解压全部载荷、原A8项清单、B原字节、文档链接核验通过。直接加载冻结包C main，配原版A factory和模拟底层叶子，显式不同fixture的当前模型，--adapter-check exit0、compatibility_issues为空、没有eligible pointer；--check identity_ok=true/deployment_ready=false且只列prepare缺口。默认/受控现场仍在硬件导入前拒绝，实际板卡未由C操作。C未把A预期的deployment_ready=true伪写成实测通过。


## 2026-11-02 最终冻结指令

用户转发A最终冻结：功能最后变更b6107bc，最新7bd365b只多验证脚本；要求“一次冻结到底，不再有往返”，运行时八文件加manifest九项，其余验证脚本不打包。hw_api固定784acc6…、driver0dc80…，给出预取消prepare与真实板sudo+C官方--adapter-check+bootstrap成功实证。要求最终包放根目录、明确现场模型文件/SHA、准确--export路径与清单，deployment_ready=true/missing=[]/adapter_check_allowed=true。

fetch/pull取得冻结对象，九项逐字节匹配用户清单且与b610相同。原版A方法用模拟MMIO/Codec/驱动叶子做12项预取消/初始化取消，全部阻止开声，prepare遗漏关闭；C维护链路通过。未改A/B或操板，不向A/B再派取件/代码任务。

C最终统一模型约定：bootstrap零模型用于维护/静音初始化（固定SHA）；真正扩声必须本scene CAL重新拟合、独立验证、装载后eligible current，不能预填旧布局模型。最终--product不使用review参数，移除历史missing后正常生成就绪包；保留正常唯一入口，不开放另一个受控现场替代入口。

按A已验证sudo运行环境，C常驻service改root，避免以不同硬件权限部署。单回包补维护JSON，并仅导出相同包身份scene/计算回执；旧原件仍留板，避免旧包数据使最终回包身份误报。根目录最终ZIP及SHA定向ignore，不入Git。A脚本均未打包；C使用既有软件测试和冻结包解压核验，实际整机现场仍由A在一次窗口记录。


最终冻结独立解压校验中，--check/维护/两scene流程先通过，--export再次verify时因__pycache__/recal_algorithm.cpython-312.pyc发生身份不符。发现打包器导入B后把自动缓存也算进载荷；这是C打包缺陷，不是A缺件。C排除manifest与ZIP中的__pycache__/pyc/pyo，旧失败ZIP移入ignored staging保留，追加既有真实适配审阅包的防缓存断言。针对打包的3项回归全部通过（2.311秒），未重复无关全套；随后重新冻结相同A/B原字节并重新进行独立包验证，无A/B往返。


最终正常--product（非review）冻结source=2137949。独立解压：九项A运行时字节、B原版SHA、全部载荷、包内文档链接、无验证脚本/缓存均通过；--check exit0/identity_ok=true/deployment_ready=true/missing=[]，adapter_check_allowed=true。冻结C main配原版A factory/模拟硬件叶子 --adapter-check exit0/compatibility_issues=[]。同一冻结Product+真实B子进程两scene重标定成功，首个记录cancel/bypass及30秒实际帧结束；--export回包两scene、16原激励、4模型、10算法JSON和1维护JSON，全部SHA及身份通过，不含人声PCM。A真实板完整窗口尚未由C执行，交最终包后由A按既定步骤完成。

根目录最终ZIP与同名SHA已生成，完整摘要/固定模型SHA/回包清单见final-package-check.json和操作单。只推C；不合main、不改A/B冻结件、不再向A/B追加留言任务。已按用户要求给出模型文件名/SHA及准确--export目标路径。


## 2026-11-02 上电AUX、失败CAL与有限重说

用户转发A真板反馈：断电后service active但四灯亮，status failed/hardware_error/aux_db；AUX 0x400B/0x400D=0x00，手写0x05后服务可CAL。A提三选一（C先写AUX、C未初始化豁免、人工开机脚本），拟构造预写/unknown映射；另CAL没跟上后不能重试，建议quiet/speech从2/2.5到4。A等方案后一次改完，避免反复。

C选择只延后三个AUX配置字段，静音/代码/位流/算法与其余部署约束保持；成功prepare后完整严格回读，新scene重走门槛，configuration_ready入收据。A现有prepare会写AUX，所以无需新增构造I2C写或手工开机脚本；unknown/raw0如实保存，不伪报0dB。原版A getter/setter和prepare、C Product、真实B子进程在模拟I2C上电0x00下完整到ready，AUX写入均发生在prepare；未操板。

普通数据/模型/采集失败确认abort后允许物理长按BTN0新scene重来，清空尝试/讲话重说，不自动启声；去掉B运行时HARDWARE_ERROR无条件fatal屏蔽CAL，身份混搭与失败mute/abort仍锁定。单项新5测试通过；保留原B cause/原因，不把重试等同模型通过。

复查有限重说还定位到A input未取本次request.run_dir。按原A方法、模拟真实driver exclusive file创建规则，第二个同scene输入再次指向same-scene_1_input_00.npz并FileExistsError；隔离诊断仅在V2.perform绑定run_dir后两次路径分离并成功，未改A源码/候选。给A本轮这一行即可；没有因格式要求重采有效原件。quiet改4；speech4会需195310源帧而RAM上限131072，所以保留2.5（含cue总时长），不盲改使采集必失败、不新增B/RTL任务。


最终本轮47项相关检查全部通过，140文档零错误/警告。仅C侧更改提交；A原始文件未修改、隔离run_dir诊断未进入候选。决定A同步一行目录绑定后再按新helper SHA统一冻结，旧4be5083a原包不替换文件；没有因C现场问题泛化向B派活或要求重采已有原件。


## 2026-11-02 8799整包重建

用户转发A目录绑定完成：hw_api完整SHA8799f40b6d9f7ecbfa8f9b2491b084f046b4b9d8d7ffd013feca0c84dbca95e0，两副本相同，manifest/contract新helper与driver同步；要求重钉product-config1处/product-manifest3处，整包放根目录、给包名SHA。说明service PS卡死本轮未动，正式演示等待。C首次fetch仅996旧件，询问后用户确认已推b1826610ab5071ebb33789612adc64ed07f2692e（功能31eef5a165dd7ada3b9d0cd45ab869fff9c5911a），再次fetch取得正确原件；未用给旧文件改哈希的方式假造身份。

新原件、根/v3字节、9项运行时、A契约新helper/driver核对；A契约仍有两条真实阻塞（PS卡死未定位、CAL新恢复待板），C原样保留契约文件及upstream_blockers，复核包scope不是正式演示批准。初始本地校验脚本误假定blockers清空，看到实际剩余两条后修正脚本：区分已去除的旧阻塞与仍真实存在的限制；不把service标为已修。C47项软件结果继续有效，C代码本轮不变，仅重建A字节与配置/文档。


最终源冻结6fd55d1；整包四处身份分别cfg.expected_identity.helper、manifest.hashes.hw_api、manifest.adapters.hardware.hashes.hw_api及其expected_identity.helper，全为8799完整值，实际文件SHA相同。独立解压verify/--check exit0、静音冷AUX0、真实B输入三次有限重说产生三条不同路径（模拟真实exclusive创建）、最终data_insufficient不锁死、新CAL重新prepare/拟合/验证到ready均通过；导入后的缓存不影响再次verify。C没改运行时代码，复用47项既有通过结果，补本次新A原件整包验证。模型bootstrap SHA不变，quiet4/speech2.5按实值封装。新service.unit与上版逐字节相同，PS卡死未修、正式演示未通过，A上游两项阻塞和原契约均保留。

新ZIP及同名SHA放仓库根目录，不入Git；本轮包SHA和完整核验见bootfix-8799-package-check.json，旧包未覆盖。仅推C，交A一次装包复核AUX延后校验/CAL重试，不自动操板、不要求重复已有有效数据。


## 2026-11-02 io150与灯光

用户真板CAL稳定失败“阶段超时，已停止”，training=0/numeric=PASS，指出A每次墙钟8.6秒、六训练约52秒>io30，要求阶段150验证，overlay复用另做；quiet/capturing同0100，speaking常不亮，建议区分。C仅改IO预算150，compute/run仍30，不扩音频时长或放宽B判据。

复核发现A8799包已indicator_armed_safe=true，常不亮的另一个确定原因是embedded路径从input_capture直接到quiet，从未进入speaking。C不在调用开始就亮讲话灯（会落在overlay/codec初始化之前）；利用已有poll实际armed模式首次回读，等待从精确8799源纯AST计算的21969帧cue及0.1秒尾声再进入speaking0010。quiet0100、capture0101，训练/验证硬件段都标capturing；未知/不安全适配保留deferred防护及原因记录。未增加A接口或硬件读寄存器路径，未改A/B。

新增定向4项先通过：虚拟52秒复现旧io30失败、新io150通过，长预算仍在200ms内调用模拟abort；初始化20秒仍不亮讲话灯，实际arm后cue未结束不亮，cue+guard后亮LD1且当前安全适配不defer。软件验证范围明确为模拟时钟/硬件，不冒报真板。后续完整受影响C检查和冻结包独立核验完成后交A本轮复核；PS服务卡死及overlay复用不声称已修。


本轮完整相关64项通过，141文档零错误/警告。源98663a4冻结io150新包，四处A helper身份仍8799、A/B文件原字节不变；新JSON io150/compute30/run30/quiet4/speech2.5/cue21969+guard0.1/safe indicator均实查。独立解压后以冻结C、原版A和真实B子进程，模拟硬件每个训练驱动调用给C时钟增加8.6秒（六次51.6），输入实际arm阶段保留足够cue时间，成功观测0010/0100/0101；完整重说/CAL再拟合/独立验证到ready通过，校验缓存/全部文件SHA/文档链接通过。service.unit与前版逐字节相同，overlay复用/PS卡死仍未修，不冒报上板稳定性。

新整包和同名SHA放仓库根目录，旧包保留，不手换文件、不自动入Git。仅推C，交A验证本轮150秒与提示；不新增A/B代码或无关旧测评要求。


## 2026-11-02 main / ARM拟合 / START 收尾

用户人工转发A=dd08250：独立8段下载无并发通过；与20ms MMIO读重叠会卡死；overlay复用在第二段source握手失败。A以下载期读闸通过8/8，并首次完整CAL拟合约70秒到ready；要求C将compute30改150，查START先读保护误停，并决定纳入三处A测试副本改动。队长同时授权直接在main提交；任务范围不扩大。

本线先验证C提交已含于main、工作区干净，再切main快进；不改旧分支、不操板。复核发现A poll在计算active之后才刷新空闲baseline，一次迟到的粘滞位可在ready被报告。C只在实际muted、无pending、硬件线程退出的三个空闲状态记录后继续按键；不在活动请求里屏蔽保护。新input_clip_seen分类到输入过载；日志对缺失raw字段保存null，不伪造原始状态字。

compute及缺省预算改150。虚拟70秒拟合在旧30失败、新150可完成；计算中取消立即发abort且旧结果不能装模型。新增六项并复用此前相关检查，共70项通过，未重跑无关测评全套。docs检查203篇零错误/警告。

A三处修法采用其仓库full_cal_guard3.sh中已发布六处字符串替换，不执行shell。以A冻结8799原件生成的helper严格等于其报告7ae449af37f270503a8448892ee0dba03d790b54fb718c8b852e8de68843ee08；C只写打包器和候选暂存，不改A/B源文件。MMIO闸约0.9秒按键空窗、AUX缓存未独立隔离上板验证以及新整包START待验证，均保留为实机边界。B原版0b09ef6与位流/驱动不变，不把无保护当作抑制收益。

首次候选组包被打包器正确拒绝：C归一化硬件元数据漏带capabilities，报input capture is not prepared。补齐与原A已验证接口一致的七项能力，并修正包内v9链接映射；预检整包生成通过，--check返回identity_ok/deployment_ready=true、missing=[]。失败暂存保留，未作为交付ZIP。


独立探测又发现原A保护基线会跨运行掩盖同一fault：真实冻结poll+模拟状态输入，空闲bit18=1后baseline=262144；_current_op=run，状态0后再bit18=1，protected仍false。这不是新的真板观察，不据此否认A已完成的CAL与直接扩声；它是候选保护逻辑的确定漏报。C不能修改A底层，也不让已知漏报的包继续标deployment_ready。归一化A元数据追加blocker、adapter_check_allowed=false，改交禁止安装的review包，普通入口、安装器和维护链路都必须拒绝。原预检包保存在staging，未交付。已给用户一条可原样转A的消息，请A在新装载且取消检查通过后的before_start建立本轮基线，并返回原始状态字/缓存标记；这次转发是实际新增阻塞，不给B追加工作。

最终review包40文件独立解压核验全部SHA、四钉值、入口和链接通过。--check退出2，identity_ok=true但deployment_ready=false；常驻与维护均在硬件对象构造前拒绝（factory调用0次）。installer仅静态确认set -eu及--check先于mkdir，未执行。空状态导出只验清单/隐私结构、0个scene，不冒报A现场回包。完整JSON见guard150-package-check.json；ZIP=shengdi-recal-7ae449af-0b09ef6-guard150-blocked-final.zip，SHA=6854654f71d39058f35c0b6dd8cce8823aca62aa55e8c04695fed0da0f632f72，冻结源=4f8c27c8aacba140596c6273b9a7ab7900307ef2。


## 2026-11-02 A 0cabfc17原件重冻结

用户转发A main=e6379ef331762b3162542d6325a644f5b34934da，功能提交0d349af6b6984c299cc04da1d57f90921a836b7f：五处before_start通过_arm_baseline先检查取消再回读基线；poll带capture_status/control_word/mmio_held/protect_baseline。完整helper SHA=0cabfc17cca1fb0e2629e1b382c119b48f00e1fe9b2a437a0302ed04e06ed3c5。A要求重钉四处并交非blocked整包；若仍封锁须明确原因。A接包后按既定四条真板验收，约0.9秒按键空窗保持未验收，不扩展本轮。

C先查工作区干净并fetch/快进main，逐字核验A原件，未改A/B。冻结器改为复制该提交九项运行时与原manifest，不再应用旧测试脚本。独立载入A探测程序，只将其原硬编码本机路径绑定到C暂存原件，执行的MMIO仍为两个寄存器替身，未访问板卡。对照无rebaseline漏报、加回调报告新fault、取消拒绝与基线不动均与A返回一致；另测缓存/实读字标记，AST核对五回调。73项相关软件检查全部通过。C日志额外保存protect_baseline，原始字不反推。旧blocked包原SHA保留，新包放行范围为A现场四条验收，不能提前写成整机通过。

新包=shengdi-recal-0cabfc17-0b09ef6-guard150-final.zip，SHA=45cbd0469437b6e22e5bf6c5d6a032120d7024b822050408ee8086648f1b58a9，字节=379217，冻结源=ffe8d10a3f762e4c033c0bb462bfd7185b1e3ac5。独立核对40文件及四钉值、A9原件与B字节、包内链接、check和维护调用通过。原版A/C+真实B子进程、模拟I2C/MMIO/driver叶子完成cold AUX0→prepare写5→6训练2验证拟合安装ready；ready人为设置旧fault并模拟BTN1释放，START正常进入running，arm基线归0，保护记录保留原字及baseline；切旁路后30秒元数据帧计数结束，再CAL另一scene到ready。导出2scene、16非人声捕获、4模型、维护回执和算法收据，各项SHA核对，无人声PCM。所有运行与30秒均为软件叶子模拟证据，不冒报真板。installer未执行；A真实四条验收与0.9秒观察空窗仍按原边界。
