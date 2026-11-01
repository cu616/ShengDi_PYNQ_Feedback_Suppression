# 一键重标定产品操作单

维护C；基础消息见[recal-product-v1](../contracts/recal-product-v1.md)，当前A/B对接见[冻结接入v3](../contracts/recal-runtime-v3.md)。正式唯一入口是板卡安装目录的`recal_entry.sh`。原批次脚本只用于历史证据复算，不再作为日常入口。

## 本轮硬件前提

真实安装须A/B提供本接口的适配包和受审策略，缺能力或有未完成项时禁止开启音频。硬件/软件接收现状只读STATE；模拟结果仅为软件验证。C可用--product-review封装真实A/B供审阅，deployment_ready仍为false，不能把审阅ZIP按下文当作已可运行的现场包。

## 实体图例（由A贴在设备旁）

按键CAL=移动设备后重标定，START=就绪后启动，STOP=随时停止。安静阶段等待提示自动进行，也可按确认键；MODE使用实体拨码，独立显示实际抵消/旁路。A按实物确认键名/编号；不能把电脑键盘当实体完成。

v3-io映射：BTN0长按至少1秒为CAL，短按忽略；BTN1按当前运行状态开始/停止；BTN2确认安静；BTN3取消并静音。四位LED：0000待标定，0001准备/计算，0010讲话（三连音及尾声结束后），0100保持安静，1000就绪/运行，1111未通过/无法评价/保护。1111时保持静音，按CAL重新检查；重复出现或显示设备不能启动时联系维护，不提高音量。运行单次结束由实际音频停止和状态回执区分；实际模式的独立实体指示仍须由A落实，不能用软件日志代替。

本包按四位LED图例操作，不依赖RGB颜色。准备完成和提示尾声结束后才轮到用户讲话；0001期间继续等待。1111时停止讲话并保持静音，按CAL重新检查，重复无变化则联系维护。模式指示须来自实际生效状态。

## 安装与日常操作

电脑源码位于C仓库；由维护者在仓库根打包（不是普通用户日常操作）：

```text
python scripts/assemble_experiment.py --product --output materials/staging/tmp/recal-product-v1 --product-hardware <A适配目录> --product-algorithm <B适配目录>
```

两个适配目录各含`product-adapter.json`：contract=recal-product-v1、kind=hardware或algorithm、field_approved=true、hashes为逐文件实际SHA。A额外提供expected_identity全部字段及`physical-controls.json`实体图例；B提供`product-policy.json`（attempts最多3项、quiet_seconds、run_seconds≤60、compute_timeout_seconds/io_timeout_seconds）。模块名固定hw_api.py与recal_algorithm.py，普通用户不选择模型或模块。路径与哈希检查失败不产出正式包。

A清单还提供allowed_gain_q12；B策略的phase_gain_q12明确开环采集/验证和运行各阶段允许值。开环0增益与就绪运行增益不能混写，所有阶段值必须在A允许集合内；运行时不接受阶段列表放宽后的漂移。

B冻结产品直接调用recal_algorithm.identity/evaluate，runtime_profile=b-frozen-v1；config.attempts深拷贝B ATTEMPTS，fit时限30秒。讲话input由B判，训练后直接fit、独立验证后validate；C不另立讲话阈值。包和每轮回执绑定version/file_sha256完整identity。旧三点Consumer及v2包装为历史/模拟用途。

三档和6/2段B策略不改；另用capture_plans转换A接受的flat captures/level_dbfs/seed字段，训练4242、验证4243，数值请求保留原plan。A原件落在run_dir_root时，C仅从白名单根按SHA复制接入本scene，保留原件路径、PCM和metadata；不因格式重采。

候选通过仅表示独立段300–460Hz预测抑制合格，heldout_prediction/not_asg/meaning原样保留。讲话重说有界且保持同档；fit retry才前进一档；validate不重试。安装applies_at=next_capture先记待生效，尚无实际装载回读时不提交eligible current。

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

## 本轮收口（A 22c88bb / B 0b09ef6）

C直接接B recal-algorithm-2026-11-01.1，文件SHA为489064051a63973c39c0f113aad28e26c2fad77fc4a5f578c44f83b0b9a1d417；正负移位与0/1段验证修正已跑过，B不再新增修改请求。fit预算仍30秒，ATTEMPTS原样，数值输出继续只表示独立段预测抑制。

C已兼容A的描述文件、开环增益集合、单次input/cue路径与返回marker：话音窗从原NPZ取真实源坐标，不改PCM；每次硬件调用隔离目录，各档levels只封当前档。C等待旧硬件调用收尾后才重用，STOP即时静音，queued CAL可被STOP撤销。19秒返回本身不要求A强杀线程。

A原版22c88bb仍有确定执行错误，已保存纯Python方法调用/替换底层I/O的复现；诊断中为继续定位而加的私有名别名、JSON桥接只存在于隔离检查，不进入候选。

1. V2的self.__meta解析成_ProductHardwareV2__meta，父类实际只有_ProductHardware__meta；training和cue+input均AttributeError。
2. install用numpy.load读取JSON模型，解析会失败。仅作诊断修通解析后，direct_only加载结束的gain_q12为0，未恢复请求1631，loaded_count为None。应正确解析JSON，并按实际装载核验填系数身份/数量、恢复运行增益后再读identity。
3. cancel_event预先置位时，V2 training仍调用driver。需要透传到plan/input/install/run及每次驱动的before_start检查，禁止取消后重新arm；C的收尾等待不能替代这一条。

本轮只给A以上必要修正，不再附泛化清单，不向B重复派活。修复后重组同一入口，才安排两布局/拨码/取消的一次完整现场窗口。

### 包与入口

本地materials/final/shengdi-closeout-22c88bb-0b09ef6-review.zip仅审阅，A/B源字节不改，原A描述文件另存于upstream-product-adapter.json。默认启动、--adapter-check和--field-trial在本版本全部拒绝，避免带确定执行错误进入现场。ZIP不进Git。

A修正后的版本经相同离线方法检查后，可按包清单开放同一recal_entry.sh的维护/受控现场参数；--field-trial仅A使用，需显式当前模型路径及完整SHA，回执标field_trial=true；它不把prepared_capture=false改为已验证。默认正式流程继续要求能力和模型事务通过，真实板卡仍由A唯一操作。

### 同一数据复核

A既有八段原件保持不变，用B新.1版本重算：全6训练仍因首段采集资格拒收，验证仍因训练/验证同源拒收；去首段5段仅回顾诊断fit通过（L1约1.788、峰位/本轮延迟130）。有效帧16382按原值交给B代码，无补零/自动删段/格式重采。旧数据限制不再转成泛化A/B修改任务；后续统一现场回包按当前封装的独立种子处理。
