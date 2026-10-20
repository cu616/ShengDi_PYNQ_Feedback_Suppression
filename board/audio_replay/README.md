# 预录语音现场操作：按顺序做

先录2秒语音，再关掉手机外放，让音响独自发声；麦克风同时参与反馈闭环。
依次直放、旁路、抵消，各约2.4秒，最多发声7.2秒；上传及操作预计5–10分钟。
只由A操作板卡，只使用固定音响，勿戴耳机。音响持续尖叫时立即断电，输入框不能实时急停。

1. **上传程序。** 电脑文件在 `D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\board\audio_replay\`。在板卡Jupyter进入 `base → audio`，点击 `New → Folder`，将新目录重命名为 `audio_replay` 并进入。板卡完整目录为 `/home/xilinx/jupyter_notebooks/base/audio/audio_replay/`。点击 `Upload`，一次选择电脑该目录下全部10个交付文件（不选择 `__pycache__`），再点击出现的确认 `Upload`。首次新建文件；更新时只覆盖同名程序文件，保留板卡 `source.wav` 和 `replay_results`。
2. **静音核验。** 打开板卡 `/home/xilinx/jupyter_notebooks/base/audio/audio_replay/replay_trial.ipynb`。运行“第1格：核验文件”下面、首行为 `from pathlib import Path` 的代码格。看到 `SCENE_FILE_OK; NO_AUDIO_STARTED` 后继续。复用板卡 `/home/xilinx/jupyter_notebooks/base/audio/audio_closed/field_setup.json` 和 `/home/xilinx/jupyter_notebooks/base/audio/audio_calibrate/candidate_box_v1_256.json`，不重填、不覆盖。
3. **录音。** 关闭音响电源，箱盖和设备位置不动。运行“第2格：录一次语音”下面、首行为 `source_path = replay_session.record_source()` 的代码格。等 `RECORD` 提示出现，再播放手机语音并输入 `RECORD`；2秒后提示录完。**现在停止手机外放。**
4. **听三项。** 恢复音响供电，确认手机已静音。运行“第3格：手机静音，连续完成三项”下面、首行为 `result = replay_session.run_replay()` 的代码格。先输入 `READY`；每项配置完成后输入 `START`，立即播放并采样约2.4秒，然后自动静音。按提示输入 `0`无声、`1`清楚语音且结束安静、`2`杂音、`3`尖叫增长、`4`结束仍响。只有 `1` 继续；其他值停止。不要运行 Run All。
5. **返回结果。** 在板卡 `base → audio → audio_replay → replay_results → replay_<编号>` 下载 `summary.json`。完整路径 `/home/xilinx/jupyter_notebooks/base/audio/audio_replay/replay_results/replay_<编号>/summary.json`。只交回此文件，WAV/NPZ留板。

若已存在 `source.wav`，第2格复用它。要换录音，先在板卡文件列表将旧文件重命名备份，再运行第2格。更改配置后保存并重新运行第1格，之后才运行第3格。

报错时程序直接打印停止阶段和原因并保存摘要；返回摘要，不连续重跑。中断后先断音响电源；Kernel重启后重新执行第1格，既有录音和结果无需重做。

本包在同一夹具下增加独立数字声源，反馈增益保持−35 dB；声源峰值按模型估算限制。直放用于确认音响可听，不能算麦克风正常扩声或ASG验收。采集保存末尾16384帧及全程内部饱和计数，不能覆盖整段录音的所有异常。实现证据见仓库 `report/verification/audio-replay/`。
