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

## C给A/B的一次性交接

A a3f516f的事件名recalibrate/start/stop/cancel/confirm_quiet/mode与C一致；短按BTN0和BTN1切换已兼容。install请求model_path/run_gain_q12，回复model_sha256/coefficients_sha256/applies_at也已接入，无须改名。API根/发布副本3549及双哈希已更新，旧f617/2f253及混填问题不再列为本轮缺项。

prepared_capture=false仍阻塞普通正式流程：prepare之后的input仍会重下位流，不能据prepare=true提前宣称讲话窗已备好。维护链路可先用同一入口独立跑。固定预热选择由A在create_product内实现并单独记录，不把看到异常后的首段删除冒充预热；B ATTEMPTS仍为6训练/2验证。B对16382帧的适用域裁决保留原件，不补零、不直接要求40分钟重构建。

### A一次性维护操作（板卡）

电脑包为materials/final/shengdi-recal-frozen-a3f516f-2ccf746.zip，ZIP不进Git。A将其解压到板卡/home/xilinx/shengdi-install/recal-frozen-a3f516f/。先结束A已有采集/演示，下面只由A执行；默认常驻安装仍会因能力缺项拒绝。

显式绑定A当前已核对模型，不默认安装仓库旧模型：

```bash
current_model=/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json
current_model_sha=$(sha256sum "$current_model" | cut -d ' ' -f 1)
bash /home/xilinx/shengdi-install/recal-frozen-a3f516f/recal_entry.sh --adapter-check --model "$current_model" --model-sha256 "$current_model_sha" --state-dir /home/xilinx/.local/state/shengdi/maintenance-a3f516f
```

此命令执行create_product→mute/capabilities→prepare→training一段（开环）→install→run三秒→finally abort。会播放训练激励并做三秒运行，无需人声；不是普通用户重标定验收，不写eligible current。回传单个/home/xilinx/.local/state/shengdi/maintenance-a3f516f/adapter-check.json即可，包含逐步请求/回复、实际模型和B算法身份、结束/静音情况及不兼容项。源模型文件保持原位。

### B现有数据裁决

C用a3f516f已有bwindow八段原件及2ccf746原算法复核：有效源窗均16382；全6训练因采集资格拒绝；原训练与原验证源SHA重复，因此不能当独立验证。固定“排首段”仅作回顾诊断时，其余5段fit通过，L1约1.788、峰位与本轮延迟130一致；没有把这个对照当验收或自动筛数据。

请B基于同一原件确认16382是否适用、首段资格与固定预热方案；先使用A已保存的4243独立验证原件（至少两段）补复核，不为字段格式重采。若确需算法变更，用新版本/新identity交接，保持本冻结文件字节不变。C继续使用30秒预算与B原策略；算法的预测资格不写成ASG或听感。

### 当前证据边界

C已从入口执行原版A工厂，但PYNQ/MMIO/Codec/driver叶子被离线替换；真实上板检查留给A。另读main=12a5491的真人主路30秒回执，收录A的completed及“有放大/清晰/无啸叫”主观报告；那不是C入口已上板。此次候选固定a3f516f，不静默混入后续A保护/预热更正。
