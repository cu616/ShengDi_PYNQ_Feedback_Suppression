# AI 协作记录：PL 连续音频通路首版

- 日期：2026-10-15；用户提示：“昨天终止了，请继续”。此前用户提供 Vivado 2018.3 路径，并表示音响已通电可调用。本文为摘要，非完整对话导出。
- 仓库基线：main，ebaa41d1965e6d5b1f453a6b534730cfe6d9cba7，开始时已有未提交修改；本次未提交/推送。
- 负责人：AI 实现与本地验证；现场上板负责人待指定。模型精确版本未知。
- 目标：最小 PL 连续收发与静音保护；本任务未实现反馈估计或抑制。

## 参考和接口

官方 Xilinx/PYNQ v2.4 `boards/Pynq-Z2/base/base.tcl` 声明 Vivado 2018.3。`audio_codec_ctrl_v1.0` 的 `iis_deser.vhd`、`iis_ser.vhd` 按 BSD-3-Clause 保留于 `src/vendor/pynq_v2_4`。官方源中的 `user_logic.vhd` 记录 100 MHz/2048 帧率及 100 MHz/32 BCLK。PYNQ 3.1.1 板上现有音频驱动版本不同，不能据 v2.4 源直接认定旧 overlay 的物理时钟。

本项目处理接口见 `docs/interfaces/audio-bringup-v1.md`。自定义模块输出默认静音，启动一次最多 244141 帧（设计值约 5 秒），仅支持向下衰减。该计数不是独立硬件墙钟超时，接收停滞另有 4096 个 100 MHz 周期的静音保护。控制来自 AXI GPIO，综合得到基址 0x41200000；外部音频接口由板卡官方 XDC 对应引脚。

## 验证与失败证据

Vivado 2018.3 `build/scripts/test_audio_frame_path.tcl`：首次测试台以 Verilog 方言编译失败；保留 `report/verification/audio_bringup/frame_test_first_failure.txt`。修为 SystemVerilog 文件类型后输出 `FRAME_PATH_PASS`，覆盖 48 个带符号双声道数值组合及启动、到期、停滞、静音、复位。

`test_audio_i2s.tcl`：输出 `I2S_PATH_PASS`，独立线级激励检查 12 个左右声道字、负数衰减和串行静音。完整日志在 `report/verification/audio_bringup/`。

`create_audio_bringup.tcl` 生成工程并通过 `validate_bd_design`；`synthesize_audio_bringup.tcl` 输出 `AUDIO_SYNTH_COMPLETE`；`implement_audio_bringup.tcl` 输出 `AUDIO_BITSTREAM_CREATED`。实现报告保存于 `report/verification/audio_bringup/`：DRC 0 违规，WNS 3.908 ns，LUT 644，FF 1163，DSP 0，BRAM 0。bit/hwh SHA256 分别为 `10E56E5A007822032477CFF9125399D52246CD50C8586578263DA6B82C548E5A` 与 `3B690C0320D8A48359563F94EF99907B11328AE092FFDE06A369A5DECBE62475`。

Vivado 时序报告明确 1 个外部输入、3 个外部输出没有 I/O delay；内部 WNS 不等于 Codec 接口时序签核。PS 预设的 DDR DQS 负延迟触发警告，需与已工作的 base 配置继续比对。有声通路、实际帧率、延迟或运行稳定性仍未证明。用户原音响通电，但本轮未播放。

## 交接

匹配的 `board/audio_bringup/audio_bringup.bit/.hwh` 及 `muted_smoke.py` 已准备。用户明确同意上传并运行静音检查后，通过板卡 Jupyter 上传三文件到 `base/audio/`，在独立 Notebook 中仅运行 `%run muted_smoke.py`。实际输出为 `{'mute': True, 'frame_count_before': 2202, 'frame_count_after': 14427, 'counter_advanced': True}` 及 `STOCK_BASE_RESTORED`，内核回到空闲；没有播放或旁路。板卡 Notebook 为 `base/audio/audio_bringup_muted_smoke_2026-10-15.ipynb`，本地截图为 `report/verification/audio_bringup/muted_smoke_board.png`。这只证明自定义 overlay 加载、GPIO 静音读回与 PL 帧计数；帧计数是 PL 时钟驱动，不能证明 Codec 收发。后续仍须单一操作者、低音量限时有声实验，并先补板级时序约束与 Codec 初始化依据。若恢复失败，现场应切断音响、重启板卡并回到原成功 Notebook。
