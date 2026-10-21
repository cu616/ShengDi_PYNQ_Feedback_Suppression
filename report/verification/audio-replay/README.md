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
不能直接重跑。2026-10-21同步新版[协作规范](../../../docs/WORKFLOW.md#8-线间协调人来做)后，旧诉求表已撤销；接口依据保留在契约中，给B/C的提示词交由用户微信转发。


## 2026-10-21 逐档批次交付

用户要求“那就请你继续干，一次性交付”，针对上一版只运行固定−35 dB的缺口。
新增A的`sweep_plan.py`、`sweep_session.py`，复制B的calibration原字节为`replay_calibration.py`供独立上传。
未改B算法或C驱动。新版13文件包/三格Notebook先读已有数据选档，源PCM与电平整批固定，
每档抵消→旁路，异常停止升档，先前完成项留在summary。原固定档入口保留兼容。
新增[逐档批次契约](../../../docs/contracts/audio-replay-sweep-v1.md)，硬件寄存器/bit不变。

语法编译、文件打包与文档检查已执行；未执行新版软件单元/回归测试、板卡静默分析或声音试验。
上表70项测试属于旧版，不构成本版选档/批次逻辑已验证的证据。RTL未改，未重复仿真/综合。
本克隆没有真实训练/验证NPZ，因此不能预先填写实际增益档位或宣称已能达到正常音量。
各档由真实数据规划；不足两档或没有模型改善会保存停止原因，不自动退回单档低增益重复试验。

源电平用拟合模型的分组级数峰值上界约束，频响范围含格点间导数补偿、训练/验证差异与6 dB裕量。
它依赖夹具与已有数据的适用性，不能保证实物稳定。实际停止依赖硬件预算、饱和轮询和现场断电；
听感逐项记录，未找到阈值如实结束。第1格失败返回摘要，不进入录音/播放。


## 2026-10-21 Notebook文件哈希误判修复

用户返回`sweep_cf1d5905f628`摘要：status=stopped，stage=package，trials/pairs为空，sound_seconds_completed=0，stop_reason指向replay_trial.ipynb文件哈希不匹配。
未拿到板卡Notebook原文件，不能确定是否仅输出变化；确认旧实现会把Jupyter保存的执行次数/输出/元数据变化误当版本变化。
修复为Notebook按顺序的代码格source规范JSON摘要，其他程序/bit/hwh仍逐字节哈希。Notebook代码变化继续拒绝。
同步更新打包脚本及manifest；现场只覆盖replay_session.py和manifest.json再运行第1格，无需重录。
未执行新版软件回归或板卡运行；只执行语法、打包和文档检查。此报错没有新增采样或发声证据。
