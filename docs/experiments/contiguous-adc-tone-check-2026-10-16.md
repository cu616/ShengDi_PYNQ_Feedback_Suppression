# 自定义 PL 连续 ADC 样本：停播 / 已知音调对照

目的：区分 `audio_capture` 的连续样本是否含有与外部声源一致的频率信息。此检查全程保持 Codec 与 PL 输出静音，不作啸叫或抑制测试。2026-10-16 的 ambient 首轮已经完成，但当时外部声源状态未核实，不能代替以下停播基线。

准备：箱盖、麦克风、LINE_IN 接线和手机位置保持固定。音响音频插头继续拔下，耳机可不佩戴；手机音量固定在上次普通人声播放的档位。打开板卡 Jupyter 的 `base/audio/audio_capture/muted_capture_2026-10-16.ipynb`。只执行下面指定的单元，不要运行旧 Notebook 的 `bypass` 或直通单元。

1. 手机停止播放，等待环境稳定。在空白代码单元运行：

   ```python
   %run muted_frame_capture.py
   quiet = capture_stats('quiet')
   ```

2. 手机放在同一位置，以固定音量循环播放约 1 kHz 的单一正弦测试音（建议 997 Hz；避免系统提示音和其他节目声音）。播放开始且稳定后，在**另一空白单元**运行：

   ```python
   tone = capture_stats('tone')
   print('RMS_CHANGE_DB_LR', [round(tone['rms_dbfs'][i] - quiet['rms_dbfs'][i], 2) for i in (0, 1)])
   ```

3. 停止手机测试音。保存 Notebook，把两次完整文字输出、实际音调频率、手机音量档位、手机到箱体大致距离和是否保持原接线记录下来。不要上传原始语音录音。

每次应打印 4096 帧、`dac_muted: True`、`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED` 与 `STOCK_PLL_READBACK 0271023c2103`。约 4096 帧的 FFT 频率间隔为 11.92 Hz；997 Hz 测试音若进入 ADC，左声道最大频率格点应靠近该频率，并相对停播有可解释的电平变化。只看到一个“最大格点”不能证明纯音质量；若格点不在附近或电平不升，先检查手机声源是否真的到达箱内麦克风，再查 I²S 接收时序/Codec 输入配置。若 Notebook 出现异常或未打印恢复标记，先停止后续测试并核对板卡实际 overlay 与 Codec 状态。

本步骤不涉及实时播放，不能以它的通过宣布自定义 PL 直通或反馈抑制通过。
