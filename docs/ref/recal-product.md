# 一键重标定产品操作单

> 2026-11-02 集成取舍：仓库 `board/audio_replay/recal_entry.sh` 按队长要求保留 A 的旧流程。C 的常驻入口源码为 `board/audio_replay/recal_product_entry.sh`；打包时映射为包内 `recal_entry.sh`，以下已安装目录命令不变。不要将仓库的 A 旧脚本覆盖进 C 安装包。

C维护安装包内唯一入口recal_entry.sh；A提供硬件适配并唯一操板，B提供原版identity/evaluate。基本消息见[产品接口](../contracts/recal-product-v1.md)，数值口径见[B契约](../contracts/recalibration-algorithm-v1.md)，本次安装事务与运行时长见[整机接入v4](../contracts/recal-runtime-v4.md)，原件和停止收尾沿用[v3](../contracts/recal-runtime-v3.md)。普通用户不用电脑、不改代码、不选模型。

## 本轮闸门与 START 复核包（guard150）

电脑仓库根目录交付 shengdi-recal-7ae449af-0b09ef6-guard150-final.zip 及同名 .zip.sha256。新包采用 A 已发布测试副本原字节：下载期间的 MMIO 读闸、驱动调用期间 AUX 缓存、run 不提前 arm；hw_api.py SHA 为 7ae449af37f270503a8448892ee0dba03d790b54fb718c8b852e8de68843ee08。包内 hardware-provenance.json 绑定 A 的补丁提交与结果 SHA；不执行其验证 shell、不携带验证脚本。B 仍是 0b09ef6 原字节。

I/O 与计算预算均 150 秒，单次扩声音频仍 30 秒。A 的 ARM 拟合约 70 秒，不能再用旧 30 秒计算预算。静音且硬件任务已全部结束时，历史粘滞保护留证后继续接收 START；活动保护仍先停声。具体范围和日志字段见 [v9](../contracts/recal-runtime-v9.md)。

[阶段时限与提示v8](../contracts/recal-runtime-v8.md)区分安静0100/正在采集0101。嵌入input会在看到实际armed后等待包内21969帧提示音及0.1秒尾声，再进入讲话0010；初始化时间不计入这次等待。当前A支持armed安全写灯，已封装启用；其他适配仍保留indicator_deferred并记录原因，不盲写受保护控制寄存器。若LD3受实际旁路影响亮起，标定阶段按LD0–LD2辨认阶段。

本轮复核冷启动、CAL→ready→START→30秒结束和重复流程；不再尝试 overlay 复用。下载时按键观察可能晚约 0.9 秒，端到端未测，不宣称所有阶段实体 BTN3 ≤200 ms。正式演示与整机稳定性仍需新包实机结果。维护前停旧 service/Notebook，只允许 A 一个硬件操作者；不要另开 PYNQ 会话。新包解压到板卡 /home/xilinx/shengdi-install/recal-guard150/：

```bash
BASE=/home/xilinx/shengdi-install/recal-guard150
sudo bash "$BASE/recal_entry.sh" --check
sudo bash "$BASE/recal_entry.sh" \
  --adapter-check \
  --model "$BASE/bootstrap-model.json" \
  --model-sha256 6a5ed276b0a09e9a82f28e475c97efd84bb69642ecda9f3b055471ec312123e8 \
  --state-dir /home/xilinx/.local/state/shengdi
```

A 在既定独占窗口安装复核时使用 sudo bash /home/xilinx/shengdi-install/recal-guard150/product-install.sh；安装器及 service 行为未改。断电重启应静音待标定，不先写 AUX。长按 BTN0 ≥1秒重标定；三连音结束后持续讲话至安静灯，0010 提示讲话，0100 等待安静，0101 训练/验证采样；计算可能再需约70秒。0110 就绪后按 BTN1 扩声，SW0 切换由 LD3 显示，BTN3 停止；30秒自然结束后回就绪灯。普通失败可长按 BTN0 新 scene 重来，身份混搭/无法静音仍锁定。按键检测与 abort 调用耗时分别记，不用旧9.8ms冒充端到端响应。

维护模型固定为包内 bootstrap-model.json，SHA=6a5ed276b0a09e9a82f28e475c97efd84bb69642ecda9f3b055471ec312123e8；只用于静音初始化/适配检查，不是现场通过模型。正式流程自动拟合并安装本轮模型；文件路径与 SHA 见 status.json 的 bundle，不手选旧模型。

结束后停止服务，再用同一包入口导出一次：

```bash
sudo systemctl stop shengdi-product.service
sudo bash /home/xilinx/shengdi-install/recal-guard150/recal_entry.sh \
  --state-dir /home/xilinx/.local/state/shengdi \
  --export /home/xilinx/shengdi-install/recal-product-return-guard150.zip
```

回包包含 return-manifest.json、summary.json、results/<scene>.json、算法收据、训练/验证原件、已安装模型及已有 maintenance/adapter-check.json；具体名称以 return-manifest.json 为准。protection_history 随 results 留证。人声 PCM、原片、授权书不自动导出。下方均为历史交付，旧 SHA 保留，不手换包内文件；以本节路径为准。

## 本轮上电与CAL复核包（A b1826610 / 功能31eef5a1）

仓库根目录交付shengdi-recal-8799f40b-0b09ef6-bootfix-final.zip及同名.zip.sha256。A根目录与v3-io的hw_api逐字节相同，SHA=8799f40b6d9f7ecbfa8f9b2491b084f046b4b9d8d7ffd013feca0c84dbca95e0；C从原件重建product-config和product-manifest，四处身份钉值一致、所有载荷哈希重新计算。九项A运行时原字节，不包A验证脚本；B仍0b09ef6，未改判据。

C[上电/恢复v7](../contracts/recal-runtime-v7.md)已包含：静音待CAL先验代码/位流身份，AUX在prepare完成后严格回读；configuration_ready标初始化门槛，不再手写0x05或加构造写入。普通失败确认静音后长按BTN0至少1秒新建scene重来，身份混搭/无法停声仍锁定。A在perform分派前绑定本次run_dir，有限重说不会碰同一NPZ，原件不覆盖。quiet=4秒，speech=2.5秒（含cue），4秒源超131072帧RAM未采用。

本包仅用于A看守下复核冷启动AUX和CAL重试。现有shengdi-product.service和安装器行为未改，已报告的PS卡死未定位/未修复，正式演示仍等待稳定性解决。上游原始product-adapter.json随包保留，其剩余阻塞也保留在清单upstream_blockers；check通过仅说明载荷/配置身份匹配，不表示PS稳定性验收。

### 本包准确路径

把ZIP传到板卡/home/xilinx/shengdi-install/，解压到/home/xilinx/shengdi-install/recal-8799/。维护检查前停止旧service/Notebook，只允许一个硬件操作者。下列命令使用包内固定bootstrap-model，SHA未变：

```bash
BASE=/home/xilinx/shengdi-install/recal-8799
sudo bash "$BASE/recal_entry.sh" --check
sudo bash "$BASE/recal_entry.sh" \
  --adapter-check \
  --model "$BASE/bootstrap-model.json" \
  --model-sha256 6a5ed276b0a09e9a82f28e475c97efd84bb69642ecda9f3b055471ec312123e8 \
  --state-dir /home/xilinx/.local/state/shengdi
```

check应identity_ok=true/deployment_ready=true/missing=[]，维护参数已开放。A决定安装/复核时：sudo bash /home/xilinx/shengdi-install/recal-8799/product-install.sh；本轮不把service上板结果提前报通过。冷启动静音待标定，长按CAL后prepare配置AUX，未跟上讲话时按有限策略重说，最终数据不足可再长按CAL，无需重启服务；保持数据/模型事务约束。

回包沿用相同目录清单，目标改为：

```bash
sudo bash /opt/shengdi/current/recal_entry.sh \
  --state-dir /home/xilinx/.local/state/shengdi \
  --export /home/xilinx/shengdi-install/recal-product-return-8799f40b.zip
```

下方7bd/4be包为历史交付，其旧SHA原样保留，不手换包内文件。模型与实体图例继续适用；本轮以上方recal-8799路径为准。

## 最终冻结（A 7bd365b / 功能 b6107bc / B 0b09ef6）

仓库根目录交付shengdi-recal-7bd365b-0b09ef6-final.zip和同名.zip.sha256。A运行时仅含八个文件与原manifest.json共九项，全部原字节；不包test/field/no_listener/receipt/run_frozen验证脚本。B原版recal-algorithm-2026-11-01.1及ATTEMPTS不变。最终字段为identity_ok=true、deployment_ready=true、missing=[]、adapter_check_allowed=true；维护和普通用户共用recal_entry.sh。[最终冻结与回包v6](../contracts/recal-runtime-v6.md)是本包说明，v5中的A593限制仅对应历史包。

### 固定模型与现场实际模型

固定文件：bootstrap-model.json；SHA256：

```text
6a5ed276b0a09e9a82f28e475c97efd84bb69642ecda9f3b055471ec312123e8
```

这是512零系数文件，用于维护自检及静音初始化；A已用bootstrap完成真实板维护链路。它标bootstrap_only=true/eligible=false，不能成为正式标定结果。真人窗口按CAL后，由B本轮六训练、两独立验证产生模型并经实际装载核验；扩声自动使用该scene的合格模型。实际文件路径/SHA见状态目录status.json的bundle.model_path/model_sha256和models/current.json，不手选旧模型。

### A在板卡执行维护自检

电脑先核根目录ZIP的SHA，将原ZIP传到板卡/home/xilinx/shengdi-install/，解压到/home/xilinx/shengdi-install/recal-final/，保留feedback等子目录。A先停止旧演示/Notebook和旧shengdi-product.service，避免两个操作者。A验证脚本留在包外，不改包内文件。

板卡先检查包与维护链路（使用A已实测的sudo环境）：

```bash
BASE=/home/xilinx/shengdi-install/recal-final
sudo bash "$BASE/recal_entry.sh" --check
sudo bash "$BASE/recal_entry.sh" \
  --adapter-check \
  --model "$BASE/bootstrap-model.json" \
  --model-sha256 6a5ed276b0a09e9a82f28e475c97efd84bb69642ecda9f3b055471ec312123e8 \
  --state-dir /home/xilinx/.local/state/shengdi
```

check应退出0并显示deployment_ready=true/missing=[]。维护检查沿用已上板通过的短链路mute→capabilities→prepare→单段training→install→3秒run→abort；成功退出0、compatibility_issues=[]，写同一状态目录adapter-check.json，不提交eligible current。它不是完整重标定；6+2捕获、拟合和独立验收在正式CAL流程执行，A已有有效现场原件不因格式重采。

### 唯一正式启动与真人窗口

维护/额外诊断结束且旧程序已停后，A只安装一次：

```bash
sudo bash /home/xilinx/shengdi-install/recal-final/product-install.sh
```

安装器核SHA后复制到/opt/shengdi/releases/<清单SHA前16位>/，原子切换/opt/shengdi/current，启动shengdi-product.service。服务以root访问板卡硬件，使用现有PYNQ Python/XRT，与A实测sudo环境一致；默认静音，状态目录/home/xilinx/.local/state/shengdi。C未实机安装服务，A按同一窗口记录实际结果。

日常只按实体键；按下面操作卡依次完成两布局CAL→讲话/安静→自动拟合/独立验证→就绪→START→SW0对照→STOP。A冻结后遇到问题仅记录，窗口后统一处理，不为格式重跑已有有效数据。

## 设备旁操作卡

四个LED按LD3到LD0记图案，不依赖颜色。C传入下表的产品图案；A硬件示例页的ready图案不是本入口的图案。

| 提示 | 含义与动作 |
|---|---|
| 0000，全灭 | 待标定/已取消，移动设备后长按BTN0至少1秒 |
| 0001，仅LD0 | 准备/计算/收尾，继续等待；进入讲话采集后仍先等三连音 |
| 三连音结束 / 0010 | 听完三连音后持续自然讲话，LD1同步提示，直到0100亮起；测量只保留最后约0.34秒，不能提前停 |
| 0100，仅LD2 | 等待环境安静，继续等待 |
| 0101，LD0和LD2 | 训练或验证正在采集，继续保持安静 |
| 0110，LD1和LD2 | 验收通过或上次运行结束，点BTN1开始一次扩声 |
| 0001运行 / 1001运行 | LD0表示运行；LD3灭=实际抵消，亮=实际旁路 |
| 1111，四灯亮 | 未通过/无法评价/保护，已经静音；先停止讲话，长按BTN0重试，反复相同则联系维护，不提高音量 |

按钮：BTN0长按重标定，短按忽略；BTN1就绪时开始、运行时停止；BTN2确认安静；BTN3随时取消并静音。SW0拨上为旁路，拨下为抵消，以运行时LD3实际指示为准；SW1保留。运行上限按本包30秒，到点进入0110并静音，只有再点BTN1才开始下一次。

陌生队友依次执行：移动设备→长按BTN0→等三连音结束后持续讲话→0100时安静→0110时点BTN1→拨SW0查看模式→点BTN3停止。失败按四灯提示处理，无需AI解释日志。移动后旧模型立即失效；新标定失败不会偷偷恢复旧场景扩声。

## 模型事务与结果

启动及移动后current立即失效；本轮拟合/独立验证、512系数回读和运行增益一致后才原子启用。安装失败不留半更新配置，不恢复新布局的旧模型。实际AUX/Codec/采样率/增益/模型/Q20/驱动/位流身份逐轮保存。

机器结果分别保留valid_pass、data_insufficient、measurement_inapplicable、model_rejected、input_overload、hardware_error、user_cancelled和protected，听感另记qualitative。valid_pass只表示独立段300–460Hz预测抑制合格，不表示ASG或听感；无保护不等于抑制成功。

## 一次现场窗口与一个回包

A在一个完整窗口依次做115cm和50cm两布局。每次移动后重新CAL，按提示讲话/安静；本轮真正拟合和独立验证成功才START、SW0对照、STOP，保留一次取消。失败也是有效结果，不为凑通过手动改变技术参数。听感由A独立记原话，不能拿不同讲话电平差当抵消收益。

结束后在板卡导出一个回包，准确路径如下：

```bash
sudo bash /opt/shengdi/current/recal_entry.sh \
  --state-dir /home/xilinx/.local/state/shengdi \
  --export /home/xilinx/shengdi-install/recal-product-return-7bd365b.zip
```

目标已存在时不覆盖；原件保留。文件清单：

| 回包路径 | 内容 |
|---|---|
| return-manifest.json | 每个文件的SHA清单 |
| summary.json | 本包身份、多scene状态/实际模式/数值/听感及原件映射 |
| results/<scene>.json | 成功/失败/取消回执 |
| algorithm/*-request.json、*-reply.json | 本包scene的B请求/回复，排除人声input请求 |
| captures/.../*.npz | 非人声激励原件，保留字节与SHA |
| models/<scene>/<sha>/...json | 拟合原模型、实际安装副本 |
| maintenance/adapter-check.json | 同一状态目录维护回执（存在时） |

只导出当前包绑定的scene及计算回执；旧包原件留板。人声PCM、运行人声捕获和未知来源音频不自动回传。C按相同包身份及B接口离线复核，不因字段格式让A重采有效原件。

## 复核与维护

C原版工厂接入检查用真实A方法和真实B子进程，只替换MMIO/Codec/驱动叶子，完整走到ready再运行并ended。运行核对原NPZ的completed_frames；elapsed_seconds的0.336秒只是环窗，wall_seconds另存，不作完整播放时长。A绑定scene的模型副本逐项比对原内容、源SHA和Q20后才提交。

所有调用先静音，计算在子进程，STOP不等待计算。旧驱动返回慢时显示收尾；等其返回才能开始下一硬件任务，排队CAL可被STOP撤销。软件验证与模拟通过不替代真实完整入口验收。

开发复用sim/feedback下test_recal_algorithm、test_recal_frozen、test_recal_runtime、test_recal_product和test_recal_closeout，及既有check_docs。不扩建测评平台，不重复无关旧全套。

## 本轮收口（A 22c88bb / B 0b09ef6）

历史审阅包shengdi-closeout-22c88bb-0b09ef6-review.zip及原回执保留；本次接入以本文最终冻结版本及STATE为准。旧原件的回顾诊断不变，不重新派给B。[历史收口证据](../../report/verification/recal-product-v1/closeout-package-check.json)。
