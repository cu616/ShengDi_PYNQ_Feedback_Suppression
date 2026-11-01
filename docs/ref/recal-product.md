# 一键重标定产品操作单

维护C；基础消息见[recal-product-v1](../contracts/recal-product-v1.md)，当前A/B对接见[整机扩展v2](../contracts/recal-runtime-v2.md)。正式唯一入口是板卡安装目录的`recal_entry.sh`。原批次脚本只用于历史证据复算，不再作为日常入口。

## 本轮硬件前提

真实安装须A/B提供本接口的适配包和受审策略，缺能力或有未完成项时禁止开启音频。硬件/软件接收现状只读STATE；模拟结果仅为软件验证。C可用--product-review封装真实A/B供审阅，deployment_ready仍为false，不能把审阅ZIP按下文当作已可运行的现场包。

## 实体图例（由A贴在设备旁）

按键CAL=移动设备后重标定，START=就绪后启动，STOP=随时停止。安静阶段等待提示自动进行，也可按确认键；MODE使用实体拨码，独立显示实际抵消/旁路。A按实物确认键名/编号；不能把电脑键盘当实体完成。

v3-io映射：BTN0长按至少1秒为CAL，短按忽略；BTN1按当前运行状态开始/停止；BTN2确认安静；BTN3取消并静音。四位LED：0000待标定，0001准备/计算，0010讲话（三连音及尾声结束后），0100保持安静，1000就绪/运行，1111未通过/无法评价/保护。1111时保持静音，按CAL重新检查；重复出现或显示设备不能启动时联系维护，不提高音量。运行单次结束由实际音频停止和状态回执区分；实际模式的独立实体指示仍须由A落实，不能用软件日志代替。

待标定：白慢闪/1闪，按CAL；讲话：青闪/2闪，三连音结束后自然讲话；安静：蓝闪/3闪，保持安静，可能播放测试声；计算/验证：黄/4闪，STOP始终可用；就绪：绿常亮，按START；失败/保护：红加错误闪数/文字，停止声音，按CAL重做；运行结束：绿慢闪，明确“本次扩声已结束”，再按START才新运行。颜色不可用时必须贴闪数图例；模式另用灯或文字，不从开关请求猜实际生效。

## 安装与日常操作

电脑源码位于C仓库；由维护者在仓库根打包（不是普通用户日常操作）：

```text
python scripts/assemble_experiment.py --product --output materials/staging/tmp/recal-product-v1 --product-hardware <A适配目录> --product-algorithm <B适配目录>
```

两个适配目录各含`product-adapter.json`：contract=recal-product-v1、kind=hardware或algorithm、field_approved=true、hashes为逐文件实际SHA。A额外提供expected_identity全部字段及`physical-controls.json`实体图例；B提供`product-policy.json`（attempts最多3项、quiet_seconds、run_seconds≤60、compute_timeout_seconds/io_timeout_seconds）。模块名固定hw_api.py与recal_algorithm.py，普通用户不选择模型或模块。路径与哈希检查失败不产出正式包。

A清单还提供allowed_gain_q12；B策略的phase_gain_q12明确开环采集/验证和运行各阶段允许值。开环0增益与就绪运行增益不能混写，所有阶段值必须在A允许集合内；运行时不接受阶段列表放宽后的漂移。

B判定库按[数值消费接口](../contracts/recal-policy-consumer-v1.md)调用；C已提供Consumer，包装器把其返回字段与原有evaluate任务身份/模型字段合并。使用B默认三点必需语义，缺项不能安装；本轮estimate_lag须绑定训练捕获。库与阈值由B维护，C消费器只处理状态、来源及有界重试。封装目录仍须含真正的捕获解析/拟合包装器与受审策略，不能把纯判定库当成完整算法适配。

runtime_profile=b-heldout-v1使用B的真实evaluate，经C recal_runtime包装。讲话仅查完整性/满幅，不向人声要求激励相干；训练后才做B input资格检查。fit时限30秒，三档-22/-19.3/-16.5，六训练两验证。候选通过表示独立段300–460Hz预测抑制合格；状态和回执明确heldout_prediction/not_asg，不表示三点闭环实测、MSG/ASG或听感。旧三点Consumer不改口径。

不带两个适配目录时生成明确的software_simulation_only包，两端均使用模拟实现，不拼接部分真实硬件和模拟算法；日常入口和安装器会拒绝以真实模式启动。真实适配齐备后deployment_ready表示文件已绑定，仍须现场验收，不等于已经证明声学效果。

电脑产物为`materials/staging/tmp/recal-product-v1.zip`，本轮含B判定消费器的副本为`materials/final/shengdi-recal-product-v1-policy.zip`；早期`shengdi-recal-product-v1.zip`保留原SHA的历史软件包。ZIP均不自动进Git。A在电脑核本次ZIP的SHA后，拷到**板卡**`/home/xilinx/shengdi-install/`，解压到`/home/xilinx/shengdi-install/recal-product-v1/`。首次安装前由A停止旧演示服务/Notebook；不让两套程序同时控制板卡。

**首次安装只由A在板卡执行一次：**

```text
sudo bash /home/xilinx/shengdi-install/recal-product-v1/product-install.sh
```

安装器先检查载荷与真实适配前提，按白名单复制到`/opt/shengdi/releases/<清单SHA前16位>/`，原子更新`/opt/shengdi/current`，安装并启用`shengdi-product.service`。固定使用现有`/usr/local/share/pynq-venv/bin/python`和本机XRT环境，用户xilinx；系统启动后常驻，默认静音待标定。维护状态在`/home/xilinx/.local/state/shengdi/status.json`，模型归档与每次结果也在该目录。此Linux安装/自启动本轮未在板上执行，不冒报成功。

**普通用户每日只做实体动作：**

1. 移动设备后按CAL。旧模型立即失效并归档，不会在新布局失败后偷偷继续扩声。
2. 等准备完成的2闪/讲话提示；启用提示音时，三连音与尾声结束后再自然讲话。不需要准备电脑或等AI改代码。
3. 看见3闪后保持安静，自动采样；4闪表示计算/验证。需要重试时程序按封装策略自动有限重试，不向用户询问增益、滤波器或模型名。
4. 绿常亮后按START；独立模式指示显示实际抵消/旁路，拨码切换只看实际指示，不猜开关方向。随时按STOP。
5. 达到单次时限后明确结束并静音，绿慢闪；只有再次按START才新开一次。不拼段假装无限连续。

| 结果 | 提示及普通用户下一步 |
|---|---|
| valid_pass | 绿常亮，按START |
| data_insufficient | 黄2闪，数据不足、无法评价；保持安静后按CAL |
| measurement_inapplicable | 黄7闪，本次条件无法评价，已静音；按CAL重标定，仍相同联系维护 |
| model_rejected | 红3闪，模型未通过；保持静音，按CAL重试 |
| input_overload | 红4闪，先停止讲话，按CAL重新检查，不提高音量 |
| hardware_error | 红5闪；允许时按CAL重试，仍失败联系维护；无法确认停声时锁定启动 |
| protected | 红6闪，保持静音后按CAL重新检查 |
| user_cancelled | 校准中取消为待标定提示；运行中停止为绿慢闪，本次已结束 |

色彩由A映射实际硬件；设备旁必须贴闪数与CAL/START/STOP图例。没有实体灯/按钮能力就不能宣称陌生队友已能按此完成验收。

## 一次现场窗口与唯一回包

A在同一窗口依次做布局1、布局2：移动→CAL→讲话→安静→绿灯→START→拨码抵消/旁路→STOP。再保留一次取消或已有保护记录；不专门制造危险输入。每次scene_id独立，成功/失败都留档。听众原话由A记录为qualitative，不拿它替代数值判据。现场完成以本包冻结的真实适配和A验收回执为准。

结束后由A在板卡只导出一个回包，不让普通用户操作日志：

```text
bash /opt/shengdi/current/recal_entry.sh --state-dir /home/xilinx/.local/state/shengdi --export /home/xilinx/shengdi-install/recal-product-return.zip
```

回包含多布局状态/实际模式轨迹、B原结构化请求回复、模型、原非人声激励捕获及映射清单。人声PCM与计算日志留板，未知来源捕获不自动回传。C用同一安装包代码执行`python recal_product.py --base <同版本安装包解压目录> --review-return <回包.zip>`核对身份/作用域，再按封装B接口对所含原件数值复核；未做数值重算时不会标成独立数值通过。字段格式问题离线修适配，保留原件哈希，不要求重跑已有有效现场数据。

## 软件验证

开发者运行`python -m unittest discover -s sim/feedback -p test_recal_product.py -v`。覆盖成功状态流、所有I/O与计算阶段取消、过载、数据不足、拒收、安装/原子指针失败、混搭、能力缺失、提示音窗、独立留出、无效果证据、有限重试、实际模式、单次结束、多布局回包、真实子进程停止和篡改拒绝。所有信号/判据为模拟或固定返回值，不代表上板效果。

## C给A/B的一次性交接

A：同意你实施cue+input单次调用方案，改动限硬件适配及驱动调用；按整机扩展v2给匹配请求/scene的input_ready事件，同域排除三连音和尾声。当前prepared_capture=false不能正式启用；不能仅修改capability。events名称兼容，C已过滤短按BTN0并按自身状态解释BTN1；LED已翻译为四位，armed时C延后写，A仍须做寄存器侧竞态防护。

A需一并补齐：按request.plan.training/validation执行6/2段及真实白噪源（当前默认单段、固定16000个零）；路径使用request.run_dir；允许开环实际gain_q12=0且mute不清除运行配置；install真正完成系数安装并分别返回文件SHA和实际Q20 SHA（不能仅解析JSON）；running poll实际模型/Q20回读、音频帧时长与初始化墙钟分开；并发取消后旧driver不得重新arm。独立实际模式灯/指示及hp_volume实际读回来源也需补充。B模型fixture_id绑定scene，A运行不得继续钉旧fixture；初次零系数采集若依赖启动模型文件，应显式列入白名单，不依赖板上未声明的旧模型。根目录f617与v3-io包内2f253分歧应在A刷新manifest时统一；C审阅包明确选f617，不覆盖A仓库文件。

打包字段：product-adapter.json中的contract/kind/source_commit/hashes、expected_identity十项、allowed_gain_q12、allowed_calibration_gain_q12、capabilities实测回执、blockers及physical-controls.json。每段capture_id含scene/attempt/phase/index；原NPZ/source SHA和本地源坐标保留；C按同一原件离线适配，格式问题不要求重跑有效数据。

B：三档和30秒fit预算已接入，原evaluate及阈值未改；retry仅input/fit且前进下一档，validate不重试。请修复fit/validate中target-lag为负时np.zeros(shift)报错（C已用相差1帧的当前延迟复现）。MIN_VALIDATION_CAPTURES=2在原validate未被实际检查，C消费层已按你的契约补缺段拒收，建议B也补生产检查。独立预测口径完整保留，不写成ASG/听感。seed4242/16384帧实算可达上限为-14.070dBFS，-16.5实际峰值约0.605；C保留你的三档，并对所有封装seed逐个验证可达，不使用约-17的估算作为执行参数。

本轮电脑审阅件为materials/final/shengdi-recal-runtime-v2-review.zip，源和哈希读对应机器回执；只能解压审阅/离线软件验证，真实启动和安装检查必须失败。修正完成后C用同一打包器重组正式现场包，入口仍为recal_entry.sh。
