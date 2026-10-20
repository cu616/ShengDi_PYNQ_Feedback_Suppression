# 官方录播对照：区分输入声源与自定义 PL 故障

状态：**已由用户现场执行**。输出为 `RECORDED_SECONDS 3 FRAMES 144000`、`PLAYBACK_DONE_AND_CODEC_MUTED`；用户听感“有点底噪的清晰人声”。执行人是现场板卡操作者；只用箱外耳机，不接箱内音响音频插头。目标是在同一 MAX4466→LINE_IN 输入下听辨官方 `base.bit` 录播的人声。结果支持输入在官方配置下可辨；应优先调查自定义 PL 的真实 ADC 数据连续性、位对齐和 Codec 串口时序。此对照未保存录音文件，未进入声学闭环，未测试抑制算法。

在 `base/audio/audio_bringup_muted_smoke_2026-10-15.ipynb` 的**一个新代码格**粘贴全部代码。先确认音响音频插头拔下、耳机在箱外，手机在之前固定位置循环播放连续人声；耳机先离开耳朵一点，保证可随手摘下。只运行这一格，不运行整本 Notebook。

```python
import fcntl
import os
from pynq.overlays.base import BaseOverlay

def stock_linein_record_play(seconds=3, volume=40):
    assert 1 <= seconds <= 3 and 30 <= volume <= 40
    audio = BaseOverlay("base.bit").audio
    audio.configure()
    try:
        audio.select_line_in()
        audio.record(seconds)
    finally:
        audio.deselect_inputs()
    print("RECORDED_SECONDS", seconds, "FRAMES", audio.sample_len, flush=True)
    try:
        audio.set_volume(volume)
        audio.play()
    finally:
        fd = os.open("/dev/i2c-1", os.O_RDWR)
        try:
            fcntl.ioctl(fd, 0x0703, 0x3B)
            for addr, val in ((0x401C, 0), (0x401E, 0),
                              (0x4023, 0xE5), (0x4024, 0xE5)):
                data = addr.to_bytes(2, "big") + bytes([val])
                assert os.write(fd, data) == len(data)
        finally:
            os.close(fd)
    print("PLAYBACK_DONE_AND_CODEC_MUTED")

stock_linein_record_play()
```

记录播放时听到“能听懂手机人声 / 有人声但很弱 / 只有沙沙声 / 完全无声”，以及上述两行文字输出。代码先录 3 秒、随后播放 3 秒，耳机中声音应在录音结束后才出现；不要把时间差误判成实时延迟。`FRAMES` 预期约 144000（48 kHz×3 秒），但以板上返回为准。出现异常或刺耳声时立即摘下耳机；若未打印 `PLAYBACK_DONE_AND_CODEC_MUTED`，不要继续下一项，请报告异常原文。录音仅存在 Notebook 内存，**不保存 WAV、不上传私人语音**。

如果当前位置的官方录播仍只有沙沙声，可把手机靠近箱内麦克风、或短时开盖让手机人声更直接到达麦克风，再运行同一格一次；**音响音频插头始终拔下**。这次改变了声学条件，只用于诊断输入质量，不能与原箱体测试直接比较增益。

下一步判据：官方录播清楚而自定义 PL 只沙沙声 → 暂停闭环，做连续 I2S/ADC 样本捕获和位对齐核对；官方录播也不清楚 → 优先查声源电平、箱体遮挡、MAX4466 供电/增益与 LINE_IN 接线。已有官方 `bypass` 产生尖锐啸叫的用户反馈仍有效，但它是另一条通路、另一种声学条件，不代替当前对照。
