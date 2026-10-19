# 固定手机声源 ADC 对照及耳机短时直通：协作记录

- 任务 / 日期 / 负责人：在自定义 PL 已知音调可听后，继续验证箱内麦克风输入及 ADC→PL→DAC 直通；2026-10-15；AI 执行代码和板卡操作，现场接线、声源、耳机听感由用户负责。
- 可见模型：Codex；具体版本未知。
- 基线：`main`，HEAD `ebaa41d`；开始时已有大量未提交修改，本轮未提交或推送。
- 依据：README、`docs/progress.md`、团队 AI 规范、`audio_probe` RTL/脚本、板上独立 Notebook。原始对话在当前 Codex 会话；本文为摘要，不冒充逐字导出。

## 关键提示与人工确认

用户原文：“那请你继续”。用户随后确认“已停止且位置不变”，即手机停播、箱盖和麦克风位置不变；静音基线后回复“声源已开始”，即在箱外固定位置循环播放普通音量人声。用户又确认“有耳机，可以切换”，并回答“已换耳机，同意上传并测试”：已将音响音频插头从 HP+MIC 拔下，耳机在箱外佩戴，同意上传 `bounded_mic_trial.py` 到板卡 `base/audio/audio_probe/` 并做 0.5 秒限时直通。最后用户回答“已就位”，确认手机人声重新开始、耳机可随手摘下。这里的物理状态来自用户确认，AI 无法远程独立核验。

## 执行与证据

- 板上 Notebook `base/audio/audio_bringup_muted_smoke_2026-10-15.ipynb` 复用已有 `probe_level`，在 Codec 输出静音下读取 ADC 最近帧寄存器，无录音文件。无外部声源 2.001 秒、2900 次快照、97685 帧，左右去直流 RMS −35.72/−35.69 dBFS。手机声源 2.000 秒、2888 次快照、97680 帧，左右 −30.74/−30.72 dBFS，差约 +4.98/+4.97 dB。两次均打印官方 base 和原 PLL 已恢复。寄存器读取不均匀，不能当连续 PCM 或严格 SNR。
- `board/audio_probe/bounded_mic_trial.py` 从现有有界直通脚本缩小执行窗口，耳机确认参数为必填真值，Codec 音量上限 40，PL 右移 0–4 位，时间 0.25–0.75 秒，异常路径先清 PL 控制、再静音 Codec、恢复官方 base 与原 PLL。Python 语法检查通过；上传后 `%run` 只定义函数，打印签名，没有自动播放。脚本对应已有 `audio_probe.bit/.hwh`，没有重建 bitstream。
- 用户确认就位后调用 `bounded_mic_trial(headphones_confirmed=True, seconds=0.5, shift=0, hp_volume=30)`。输出：计划 0.5 秒、实测 0.501 秒、24476 帧，`muted_at_end=True`、`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。Notebook 已保存。

用户后来说明首次 0.5 秒运行时自己不在，故该轮没有有效听感。再次确认耳机在箱外佩戴、音响音频插头仍拔下、手机人声循环播放并可随手摘耳机后，运行同一函数，仅把时间改成 0.75 秒，Codec 音量 30、PL 右移 0 不变。Notebook In[24] 返回实测 0.751 秒、36693 帧、`muted_at_end=True`、`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。用户原文反馈：“完全无声”。因此连续有声直通仍未证明。Codec 参数 30 对应标称约 −27 dB；手机人声的 ADC 快照 RMS 约 −31 dBFS，输出可能过弱，但没有 DAC/耳机端电平测量，路由和数据格式问题也未排除。下一步先在耳机条件下做有界分级测试或进一步诊断；音响插回箱内后不得直接沿用耳机参数做闭环测试。

操作方式调整：用户指出浏览器自动化交互耗时，要求后续把已准备好的代码块及步骤交由其现场手动执行，以便听音时机可控。电脑对板卡 `192.168.2.99:22` 的 TCP 连接测试失败，当前不能把 SSH 当作已就绪的快速通道。此检查只证明该端口当前不可达，未诊断板卡 SSH 服务的具体状态。

## 手动对照的后续反馈

AI 预先交付 [手动诊断单](../../docs/experiments/manual-headphone-check-2026-10-15.md)，用户后续回复：`stock_tone(volume=40, amplitude_dbfs=-18)`“能听到清晰3声”；`%run audio_probe/bounded_mic_trial.py`“无结果”；`bounded_mic_trial(headphones_confirmed=True, seconds=0.75, shift=0, hp_volume=40)`“只能听到电流斯拉的声音”。`%run` 只定义函数，没有文字输出属预期。用户尚未粘贴最后一格的完整输出，因此这轮不能复核自动静音和恢复标记。现场没有报告可辨手机人声；不把沙沙声记作直通通过。

用户还指出“很早之前我们已经有代码验证过有尖锐啸叫通路”，随后明确确认正是在 `pAudio.select_line_in()`、`pAudio.set_volume(40)`、`pAudio.bypass(seconds=10)` 且音响接回箱内时发生。此前粘贴的官方音频 Notebook 文本有这段代码与“本次结束”输出，但没有运行期间信号或原始音频；啸叫听感来自用户追认。官方 bypass 声学闭环与自定义 PL 的证据范围分开。下一步停止增益试探，先用同条件官方 base 短录短播区分输入信噪比与 PL 实时数据路径问题。

用户又提供 B 的完整输出：`{'hp_volume': 40, 'hp_db': -17, 'pl_shift': 0, 'pl_db_approx': -0.0}`、`{'planned_seconds': 0.75, 'elapsed_seconds': 0.751, 'frames': 36693, 'muted_at_end': True}`、`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。这补足控制与恢复证据，不改变“只有沙沙声、没有可辨人声”的现场判断。

2026-10-16 追加：用户运行[官方录播对照](../../docs/experiments/stock-input-reference-2026-10-15.md)后，贴出 `RECORDED_SECONDS 3 FRAMES 144000` 和 `PLAYBACK_DONE_AND_CODEC_MUTED`，并报告“声音是有点底噪的清晰人声”。该结果是官方 base 的先录后播，不是实时 bypass，也不是自定义 PL；它排除了“当前输入根本没有可辨人声”这一简单解释。AI 下一步做自定义收发链的定向排查，不再让用户单纯逐档提高音量。

2026-10-16 静音连续捕获：用户明确回答“同意上传并运行静音诊断”，对象为新 `audio_capture.bit/.hwh` 和 `muted_frame_capture.py`，目的地板卡 Jupyter `base/audio/audio_capture/`，只采约 84 ms ADC 连续帧统计，结束恢复官方配置，不保存或上传原始录音。AI 已实际上传三文件并在独立 Notebook `muted_capture_2026-10-16.ipynb` 运行 `capture_stats('ambient')`。板上输出 4096 帧、`dac_muted=True`、左右 RMS −32.53/−32.51 dBFS、峰值 −18.89/−18.82 dBFS、左声道 100–5000 Hz 最大栅格 393.4 Hz；随后 `PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`，内核空闲。现场外部声源状态未核实，因此不把本轮标为安静底噪，也不将单一峰值判定为啸叫频率。此次仅证明自定义采样链可读回连续帧；没有人声听辨或反馈抑制证据。
