# 开环标定开发协作记录

## 后续现场准备记录

两轮完成后的AI执行：经既有持续开发授权，将calibration.py上传到板卡、校验SHA256，运行固定256抽头训练/独立验证以及分段、Q20系数、错移参考检查。实际输出及限制记录于 `report/verification/audio_calibrate/board-analysis-2026-10-16.md`。验证误差降低9.6893 dB，不称ASG。本轮未操作音频硬件，原始PCM未传出；候选模型与摘要留在板卡，Notebook已保存。浏览器首次绑定超时后重试成功，没有因此重复触发音频。未提交或推送。

第一轮后续：用户反馈“能输出短噪声”，返回32768帧本地保存成功、参考校验True、麦克风RMS −21.11853362140025 dBFS、峰值−5.670635405233404 dBFS、满幅样本0，以及base/PLL恢复并静音和NO_DATA_UPLOADED标记。AI据此记录第一轮完成，未读取原始数据；向用户提供同条件种子1独立验证格。尚无真实模型评价或抵消效果。

用户回复“标定就绪”，承接此前说明的箱体音响连接、外部声源停止、可断电和短时PCM仅存板卡条件。通过Jupyter上传bit/hwh/脚本，板上SHA256逐项校验通过（`UPLOAD_HASHES_OK`），函数定义成功（`OPEN_LOOP_CAPTURE_READY`）。保存的 `base/audio/audio_calibrate/Untitled.ipynb` 第二格为种子0的手动采集命令，仍为 `In [ ]`，内核空闲。没有执行采集、加载overlay或发声，没有下载录音；待用户手动启动并返回输出。以下开发记录中“未上传”为此前本地阶段状态。

- 日期 / 负责人：2026-10-16，AI负责本地开发和验证；现场操作者下一步为用户。
- 模型：Codex，具体服务版本未知。
- 基线：main / ebaa41d1965e6d5b1f453a6b534730cfe6d9cba7；工作区原有修改保留，本轮未提交或推送。
- 用户原文：“可以，请你继续，在没有明确需要我配合环节的情况下，请由你不断开发”。
- 本文为协作摘要，原始对话保留在当前聊天，不冒充逐字导出。
- 输入依据：当前README/progress、development-plan中的开环先行路线、既有RTL及PYNQ v2.4串行器、接口模板和AI规范；无新的真实音频数据。

## 实现决策与纠错

先完成独立开环测量工具，不将实时麦克风反馈到扬声器。参考取实际串行器装载的DAC字，和同帧ADC左组成记录；用针脚级独立解码器核对，避免仅依据源发生器数值猜测参考对齐。两种子分别用于训练和独立验证，软件拒绝复用同一训练参考。系数明确前一帧起算，避免代数循环；定点范围不足时拒绝导出，不隐藏饱和。

第一次软件测试有8项通过、NPZ往返一项因Windows沙箱临时目录权限失败。将测试临时目录限定到仓库tmp后通过，没有修改数值判据。初次Vivado沙箱启动因安装目录执行权限失败；使用已安装工具的本机执行权限后仿真与构建正常，未操作板卡。构建脚本由capture版本改写时首次文本替换未改中audio_pl_capture引用，检查发现后在构建前更正。扩充仿真增加ADC无VALID与复位案例，最终通过。

## 实际验证

- Python：捆绑Python、NumPy2.3.5。`python -m unittest discover -s sim/feedback -p 'test_*.py' -v`，13项通过，输出见 `../verification/audio_calibrate/software-tests.txt`。模拟硬件测试不证明真实I2C/MMIO时序。
- 线级仿真：`vivado -mode batch -source build/scripts/test_audio_calibrate.tcl`，最终 `AUDIO_CALIBRATE_PASS`；16帧缩小实例，两个种子、序列对齐、DAC自动停止、ADC失败、手动停止及复位。
- 构建：`vivado -mode batch -source build/scripts/create_audio_calibrate.tcl -tclargs build`，生成32768帧版本bit/hwh；报告保存在 `../verification/audio_calibrate/`。WNS1.333ns、WHS0.044ns、DRC0、LUT1070、FF2158、RAMB36E1 48、DSP0。外部音频I/O约束不完整，未签核。
- 端到端离线CLI：`make_synthetic_calibration.py`生成不同种子的合成训练/验证数据，再运行 `fit_feedback_path.py --taps 256`；验证预测误差降低44.055dB。结果仅为合成数据，见synthetic-result.json；不得放入实物ASG表。
- Python语法：板卡新脚本及3秒耳机上限修改通过py_compile。新脚本导入不发声，采集需现场确认参数，恢复步骤分别尝试，文件默认仅存板上。

## 交接与限制

新增协议见 `docs/interfaces/feedback-calibration-v1.md`，任务验收见 `docs/tasks/open-loop-calibration-2026-10-16.md`，现场步骤见 `board/audio_calibrate/README.md`。bit/hwh和关键源码SHA256见board目录manifest。旧直通bit/hwh未改，未上传或执行新工程，板卡本轮未占用。现场声音测试、本地PCM保存须用户知情确认；数据不自动外传。

未执行真实标定、较长语音听辨、FIR抵消上板、闭环ASG或长期稳定性。真实Codec状态、信噪比、频响、非线性、箱体路径长度和外部时序仍需上板验证；纯音通过不能填补这些证据。恢复方式为保留原有工程并由脚本恢复base/PLL和Codec静音，异常时现场断开音响。下一项需现场开环采集，人工独立代码审阅尚未执行。
