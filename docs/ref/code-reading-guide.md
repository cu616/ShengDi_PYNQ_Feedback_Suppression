# 核心代码阅读顺序

先读 [STATE](../STATE.md) 确定版本，再按下面顺序理解主链路。旧的 probe → calibrate → residual 阅读顺序保存在 [历史原文](../archive/pre-freeze-guide-2026-10-29.md)，适合追溯基础 bring-up，不代表现行音频处理顺序。

| 顺序 | 文件 | 重点 |
|---|---|---|
| 1 | [上板版本索引](../../board/audio_replay/README.md) 与 [v3 manifest](../../board/audio_replay/v3/manifest.json) | 分清发布载荷、维护源码、旧位流和回退文件 |
| 2 | [audio_pl_replay.v](../../src/rtl/audio_pl_replay.v) | ADC、FIR、数字增益、注入、实际播放参考、帧调度及捕获之间的关系 |
| 3 | [feedback_fir.v](../../src/rtl/feedback_fir.v) | 预测历史、MAC、25位宽残差与24位诊断残差；增益前越界和输出饱和是不同量 |
| 4 | [v3/replay_trial.py](../../board/audio_replay/v3/replay_trial.py) | 整对身份检查、Codec配置、arm、停止原因、先停声再保存及恢复 |
| 5 | [v3/replay_tools.py](../../board/audio_replay/v3/replay_tools.py) | 位精确重放、截断历史排除、宽残差过增益和实际输出核对 |
| 6 | [tone_round_guard.py](../../board/audio_replay/tone_round_guard.py) | 配对资格、实际源、帧域、恢复副车和幅度归一化；正式复算入口另见 STATE 的 C 段 |
| 7 | [calibration.py](../../src/feedback/calibration.py) | 反馈通路拟合、系数量化与参考算法；必须绑定实际场景 |

PS 是板上 ARM，负责配置、运行控制与记录；PL 逐帧处理。先区分“用于估计反馈的实际播放字”和“送 DAC 的输出”，再读延迟。24位 PCM 的满幅归一化与 Q20 系数单位不能混用。

接口以 [audio-replay-v3](../contracts/audio-replay-v3.md) 与 [契约索引](../contracts/README.md) 为入口。想研究特定诊断时再读 `audio_probe`、`audio_capture`、`audio_calibrate` 或 `audio_residual`，不要求重新运行它们。
