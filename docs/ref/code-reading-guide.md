# 核心代码阅读顺序

先分清两条通路：实时直通把麦克风送到音响；开环标定让音响播放已知信号，麦克风只负责记录。目前audio_residual已接入256抽头FIR，残差只记录，不回送DAC；闭环抑制待验证。

| 顺序 | 文件 | 建议先看什么 |
|---|---|---|
| 1 | [audio_pl_probe.v](../../src/rtl/audio_pl_probe.v) | 顶层接线：receiver、path、transmitter三个实例 |
| 2 | [audio_frame_path.v](../../src/rtl/audio_frame_path.v) | valid采样事件、使能上升沿、衰减、预算耗尽和静音 |
| 3 | [audio_pl_calibrate.v](../../src/rtl/audio_pl_calibrate.v) | 独立激励如何生成，scheduled/captured为何分开，参考和ADC怎样成对入RAM |
| 4 | [open_loop_capture.py](../../board/audio_calibrate/open_loop_capture.py) | Python如何配置Codec和PL、启动采集、读RAM、恢复及保存 |
| 5 | [calibration.py](../../src/feedback/calibration.py) | history_matrix→fit_path→evaluate_path，再读quantize_coefficients与fixed_fir |

先读中文注释，再对照 [接口说明](../contracts/feedback-calibration-v1.md)。PS是板上ARM处理器，运行Python及寄存器配置；PL是FPGA逻辑，负责逐帧收发。I2C控制Codec，MMIO控制PL寄存器，两者地址不能混用。

PCM为24位补码，除以2^23转为满幅浮点；系数有20位小数，除以2^20还原。模型的h[0]乘前一帧参考u[n-1]。定点软件参考返回的是预测反馈，尚不是已接入实时链路的麦克风残差。

注释添加于2026-10-17，仅修改本地源码。两份Python的AST一致，三份RTL去掉注释和空白后文本一致，结果与前后SHA256见 [检查记录](../../report/verification/core-comment-check-2026-10-17.json)。本轮未重新综合、未上传或运行板卡。

新增注释改变了文件SHA256。`board/audio_calibrate/manifest.json`仍保留10月16日构建/上传版本的原始校验值，不覆盖历史证据；其中脚本和RTL哈希不再等于本地注释版。板上Notebook仍校验旧脚本，运行不受此次本地改动影响。以后部署注释版时应明确更新版本及校验清单，不能直接把当前源码哈希说成原构建哈希。

最新实现继续读src/rtl/feedback_fir.v、src/rtl/audio_pl_residual.v及board/audio_residual/residual_tools.py，接口见docs/contracts/frozen/audio-residual-v1.md。
