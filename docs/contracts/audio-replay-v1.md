# 预录语音闭环接口 v1

状态：实现待验证（软件、RTL仿真、布局布线完成；未上板）
生产方：A · 消费方：A / B / C
最后变更：2026-10-20 原因：用户要求先录音，关闭手机外放，再播放且实时采集麦克风。

## 使用边界

新增独立 `audio_replay` overlay；不替换 [audio-closed-v1](audio-closed-v1.md)。
操作入口为 [现场步骤](../../board/audio_replay/README.md)，证据见
[构建记录](../../report/verification/audio-replay/README.md)。
保持256抽头Q20、24位PCM、48828.125 Hz、两帧反馈调度与旧缓存接口。
不能用旧工具的“播放值=增益×残差”验证这个新路径。

## 声源与帧关系

静音时预装1～131072个有符号16位样本，播放期间不依赖PS流送。
设预装声源为 `s[n]`，麦克风为 `m[n]`，实际播放为 `u[n]`：

```text
p[n] = FIR_Q20(u[n-1], u[n-2], ...)
e[n] = bypass ? m[n] : sat24(m[n] - p[n])
u[n] = sat24((s[n] << 8) + sat24(round_Q12(g * e[n-2])))
```

最初两帧反馈项为0；超出声源长度后声源项为0。FIR的参考是实际混音输出，
并非仅反馈项。舍入与饱和沿用旧定点契约。直放检查设 `g=0`，也使用真实系数；
旁路/抵消对固定同一个源数组、系数、增益、音量、帧预算，只改bypass。

## 新增AXI GPIO

地址从配套HWH的IP名称读取，禁止沿用旧overlay地址或句柄。

| IP / 偏移 | 方向 | 含义 |
|---|---|---|
| audio_source / 0 | PS写 | bit15:0为PCM16；bit16翻转提交样本；bit17翻转开始新装载 |
| audio_source / 8 | PS读 | bit31:24=0x52；bit23:20=0；bit19=fresh；bit18=error；bit17:0=已装载数 |
| audio_source_length / 0 | PS写 | 本次声源样本数 |
| audio_source_length / 8 | PS读 | 全次混音饱和计数 |

先静音、写length、翻转begin，再逐样本翻转data；全部装载后检查数量、fresh及error。
装载完成不自动发声。每次运行都必须重新装载声源及系数。
`frame_limit >= source_length + 2` 且不超过488281帧。
运行中修改声源或长度将触发故障并静音。保留旧的时限、协议故障和停止保护。

## 程序与结果

`replay_session.run_replay()`是现场入口，自动保存独立目录下的`summary.json`。
录音只保留板卡。输入WAV支持单/双声道PCM16/24/32，8～48 kHz、
0.5～2.5秒，双声道取左；去直流、重采样、首尾淡入淡出后限制注入峰值。
源峰值限制使用量化系数L1和实际Q12增益估算，不是实测稳定性保证。

摘要schema_version=1，含setup及哈希、model哈希、source原文件及处理后PCM哈希、
每项metadata与听感、阶段、停止原因。metadata的artifact_kind=`replay_trial`，
含bit/coefficients哈希、实际gain_q12、hp_volume、completed_frames、
first_frame、source_frames、source_pcm16_sha256、mix_saturations以及数字核对结果。
异常发生在发声授权后时，明确标记该失败项实际发声时长未知。

保存末尾16384帧，默认录音后还有0.4秒声源关闭尾段，因此回读主要用于尾段衰减与数字核对。
内部预测/残差/增益/混音饱和计数覆盖全次；麦克风满幅检查仅覆盖回读窗口，
不能冒充全程ADC监测。NPZ/WAV不自动上传。

此流程回答“手机停止后音响能否清楚播放、两模式是否出现异常”，
不把数字注入直放通过算作正常麦克风扩声成立；不输出实测MSG/ASG。
