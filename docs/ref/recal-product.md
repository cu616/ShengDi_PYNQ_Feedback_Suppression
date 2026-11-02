# 一键重标定产品操作单

C维护唯一入口recal_entry.sh；A提供硬件适配并唯一操板，B提供原版identity/evaluate。基本消息见[产品接口](../contracts/recal-product-v1.md)，数值口径见[B契约](../contracts/recalibration-algorithm-v1.md)，本次安装事务与运行时长见[整机接入v4](../contracts/recal-runtime-v4.md)，原件和停止收尾沿用[v3](../contracts/recal-runtime-v3.md)。普通用户不用电脑、不改代码、不选模型。

## 本轮接入（A 5939ee5 / B 0b09ef6）

仓库根目录交付shengdi-recal-5939ee5-0b09ef6-maintenance.zip及同名.zip.sha256；ZIP不进Git。A所有载荷取5939ee5的v3-io原字节，原清单与原适配描述一并保留；B仍为recal-algorithm-2026-11-01.1，ATTEMPTS不变，fit预算30秒。当前权限见[维护开放v5](../contracts/recal-runtime-v5.md)。

adapter_check_allowed=true，维护者可以使用本包入口验证create_product。五条路径training/validation/input/install/run取消修正已通过离线调用。deployment_ready仍为false，missing只剩prepare父类路径未传cancel_event/before_start；预取消prepare仍调用driver，初始化取消后仍会继续。默认常驻、服务安装及field-trial继续关闭，避免把维护开放误写成正式产品已通过。C未操作板卡，B不需修改。

### A在板卡执行维护自检

电脑先核根目录ZIP的SHA，将原ZIP传到板卡/home/xilinx/shengdi-install/，解压到/home/xilinx/shengdi-install/recal-5939ee5/，保留feedback等子目录。停止旧演示/Notebook，同一时刻只让本入口控制硬件。

板卡核完整包：

```text
bash /home/xilinx/shengdi-install/recal-5939ee5/recal_entry.sh --check
```

此版本预期identity_ok=true、deployment_ready=false且只列prepare取消缺口，退出码2。它与允许维护检查独立，不要为让check变绿修改manifest。

然后A显式使用板上当前已核对模型（仅维护使用，不提交日常current）：

```bash
MODEL=/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json
bash /home/xilinx/shengdi-install/recal-5939ee5/recal_entry.sh \
  --adapter-check \
  --model "$MODEL" \
  --model-sha256 "$(sha256sum "$MODEL" | cut -d ' ' -f1)" \
  --state-dir /home/xilinx/.local/state/shengdi-a593-maintenance
```

该命令直接使用既有维护短链路：mute→capabilities→prepare→单段training→install→3秒run→abort，结束写adapter-check.json；成功退出0。C不把它称为完整6+2拟合或真人产品验收。A已有有效6+2和真人原件继续保留，不因格式重采。普通用户仍按下方实体动作操作；其正式启动须等prepare缺口修复后重新冻结。

## 设备旁操作卡

四个LED按LD3到LD0记图案，不依赖颜色。C传入下表的产品图案；A硬件示例页的ready图案不是本入口的图案。

| 提示 | 含义与动作 |
|---|---|
| 0000，全灭 | 待标定/已取消，移动设备后长按BTN0至少1秒 |
| 0001，仅LD0 | 准备/计算/收尾，继续等待；进入讲话采集后仍先等三连音 |
| 三连音结束 | 持续自然讲话，直到0100亮起；测量只保留最后约0.34秒，不能提前停 |
| 0100，仅LD2 | 保持安静，系统可能播放测试声 |
| 0110，LD1和LD2 | 验收通过或上次运行结束，点BTN1开始一次扩声 |
| 0001运行 / 1001运行 | LD0表示运行；LD3灭=实际抵消，亮=实际旁路 |
| 1111，四灯亮 | 未通过/无法评价/保护，已经静音；先停止讲话，长按BTN0重试，反复相同则联系维护，不提高音量 |

按钮：BTN0长按重标定，短按忽略；BTN1就绪时开始、运行时停止；BTN2确认安静；BTN3随时取消并静音。SW0拨上为旁路，拨下为抵消，以运行时LD3实际指示为准；SW1保留。运行上限按本包30秒，到点进入0110并静音，只有再点BTN1才开始下一次。

陌生队友依次执行：移动设备→长按BTN0→等三连音结束后持续讲话→0100时安静→0110时点BTN1→拨SW0查看模式→点BTN3停止。失败按四灯提示处理，无需AI解释日志。移动后旧模型立即失效；新标定失败不会偷偷恢复旧场景扩声。

## 首次安装（A维护，取消修复版核对后使用）

电脑：仓库和ZIP在电脑，不在板卡。A先核对C交付的ZIP SHA，传到板卡/home/xilinx/shengdi-install/，解压到/home/xilinx/shengdi-install/recal-product-v1/。停止旧Notebook/演示程序；只有本入口控制音频。

板卡首次安装一次：

```text
sudo bash /home/xilinx/shengdi-install/recal-product-v1/product-install.sh
```

安装器检查包身份，复制到/opt/shengdi/releases/<清单SHA前16位>/，原子更新/opt/shengdi/current，启用shengdi-product.service。使用板上现有/usr/local/share/pynq-venv/bin/python和XRT环境，常驻用户xilinx；启动默认静音。日常不再打开脚本或Notebook。Linux服务首次安装由A验证，C离线检查不冒报上板。

启动只用封装的bootstrap-model.json零系数完成开环准备；该文件标bootstrap_only/eligible=false，不能成为合格模型。真正运行模型必须来自本轮拟合、独立验证和512系数装载核验。模型文件SHA、Q20 SHA、实际AUX/Codec/采样率/增益/驱动/位流身份逐轮保存。安装失败不留半更新的current指针。

维护者的现场状态文件在/home/xilinx/.local/state/shengdi/status.json；普通使用者不需要读它。机器结果分别保留valid_pass、data_insufficient、measurement_inapplicable、model_rejected、input_overload、hardware_error、user_cancelled和protected，听感另记qualitative。valid_pass仅表示独立段300–460Hz预测抑制合格，不表示整机ASG或听感；无保护也不等于抑制成功。

## 一次现场窗口与一个回包

取消修复版经过同一离线核对后，由A在一个完整窗口依次做115cm和50cm两布局：每次移动后重新CAL，按提示讲话/安静，实际拟合及独立验证，成功才START、SW0对照、STOP；保留一次取消。失败也是有效结果，不为了凑通过额外改变档位或要求用户看日志选参数。已有有效原件不因格式重采。

结束后A在板卡导出一个回包：

```text
bash /opt/shengdi/current/recal_entry.sh --state-dir /home/xilinx/.local/state/shengdi --export /home/xilinx/shengdi-install/recal-product-return.zip
```

回包含多布局状态、实际模式、B请求/回复、拟合原模型与实际安装副本、非人声激励原件和映射。人声PCM、运行人声捕获、未知来源音频留板，不自动回传。C按同一冻结包核身份并使用同一B重算；不把接口层A现场或不同讲话电平差当作抵消收益。

## 复核与维护

C原版工厂接入检查用真实A方法和真实B子进程，只替换MMIO/Codec/驱动叶子，完整走到ready再运行并ended。运行核对原NPZ的completed_frames；elapsed_seconds的0.336秒只是环窗，wall_seconds另存，不作完整播放时长。A绑定scene的模型副本逐项比对原内容、源SHA和Q20后才提交。

所有调用先静音，计算在子进程，STOP不等待计算。旧驱动返回慢时显示收尾；等其返回才能开始下一硬件任务，排队CAL可被STOP撤销。软件验证与模拟通过不替代真实完整入口验收。

开发复用sim/feedback下test_recal_algorithm、test_recal_frozen、test_recal_runtime、test_recal_product和test_recal_closeout，及既有check_docs。不扩建测评平台，不重复无关旧全套。

## 本轮收口（A 22c88bb / B 0b09ef6）

历史审阅包shengdi-closeout-22c88bb-0b09ef6-review.zip及原回执保留；本次接入以本文A593版本及STATE为准。旧原件的回顾诊断不变，不重新派给B。[历史收口证据](../../report/verification/recal-product-v1/closeout-package-check.json)。
