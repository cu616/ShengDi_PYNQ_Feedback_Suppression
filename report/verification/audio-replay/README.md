# 2026-10-20 A：预录语音程序交付记录

用户要求：“能不能先录好再播放同时实时打开麦克风监听声音”，
随后确认“可以，下次结束工作时请交付可运行的程序”。
本次实现独立的数字声源注入路径，让手机停止外放后由音响发声，并同步采集麦克风。
未连接板卡、未加载overlay、未播放或传输现场录音。

## 交付

- [现场操作](../../../board/audio_replay/README.md)：完整路径、上传确认、三格Notebook定位及结束文件。
- [独立接口](../../../docs/contracts/audio-replay-v1.md)：新overlay与实际输出公式。
- `board/audio_replay/`包含配套bit/hwh、三格Notebook、驱动、manifest和说明，共10项。
- `scripts/package_audio_replay.py`从已通过时序的构建生成包及哈希；压缩包在`build/packages/audio-replay.zip`。
- B算法、C旧驱动和audio_closed旧RTL未修改；复制的两个纯计算辅助模块保持原字节。

配置复用板卡原`field_setup.json`及`candidate_box_v1_256.json`，运行时保存哈希。
固定Codec 40、256抽头Q20、48828.125 Hz。直放增益为0；
旁路/抵消请求−35 dB，实际Q12为73，其他配置及注入PCM完全相同。
录音默认2秒，播放含0.4秒尾段；只在静音配置完成后提示START。
源峰值按量化模型和实际环路增益限制，失败/取消均保存阶段和原因。

## 实际执行的检查

| 检查 | 结果与证据 |
|---|---|
| 软件回归 | 70项通过，含新增8项；[原始输出](software-tests.txt) |
| 混合Verilog/VHDL仿真 | `AUDIO_REPLAY_PASS`；[输出](rtl-simulation.txt)。独立解码I2S，覆盖声源叠加、实际DAC历史、bypass、环形缓存、饱和、超时/停止及无源拒绝 |
| Vivado 2018.3综合布局布线、bit生成 | 最终WNS +0.413 ns、WHS +0.035 ns，受约束路径满足时序；[完整报告](timing.txt) |
| 资源 | LUT 3203，寄存器5013，BRAM 112/140，DSP 3；[报告](utilization.txt) |
| DRC | 保留DSP流水寄存器建议等警告；[完整报告](drc.txt) |

第一次布局布线WNS为−0.348 ns，未交付该bit；[失败报告](initial-timing-failed.txt)保留。
在声源BRAM读出至混音路径增加一级寄存器后重新仿真和完整构建得到上表结果。
外部I/O仍缺1输入/3输出延迟约束，因此不是完整板级时序签核。
打包检查同时拒绝setup/hold/pulse-width失败或RTL晚于bit的构建。

复现入口：

```powershell
python -m unittest discover -s sim/feedback
vivado -mode batch -source build/scripts/test_audio_replay.tcl
vivado -mode batch -source build/scripts/create_audio_replay.tcl -tclargs build
python scripts/package_audio_replay.py
```

本机Python通过`-X utf8`运行；临时目录设在本克隆的`tmp`以避开系统临时目录权限。
打包后核对10个ZIP成员与本地文件逐字节一致，Notebook三格可编译，manifest核对通过。
最后修正异常时长标志后，8项新增测试再次通过。文档扫描101份，0错误/0警告。
文档检查器会错误跳过绝对路径中含`tmp`的整个克隆；本次通过以仓库相对路径过滤
`.git`与`tmp`的运行时适配执行检查，不改B的公共检查器。

## 剩余一次现场动作

按操作页上传10项，复用既有现场配置。音响断电录2秒，停止手机外放后恢复音响供电，
完成直放、旁路、抵消三项，最多约7.2秒发声。只有听感1且数字检查通过继续，
否则停止并返回该次summary；持续尖叫立即切断音响电源。

新路径尚未上板；不能预先保证音响响度、音质或抵消有效。保存的末尾16384帧主要是
声源关闭后的尾段，不代表整个语音段。全程内部饱和计数也不等于全程ADC监测。
若两模式均正常，结论是已测范围未找到旁路失稳阈值；不输出精确MSG/ASG。
如直放无声，停止后续两项，依据输出电平和现场音量处理可听性问题。

恢复：关闭音响，重启Notebook内核，再执行文件核验；保留已有source.wav及结果。
运行器正常结束/异常均尝试恢复base overlay和Codec静音；恢复失败须先处理错误，
不能直接重跑。B/C诉求已写入[REQUESTS](../../../docs/REQUESTS.md)的R-005/R-006。
