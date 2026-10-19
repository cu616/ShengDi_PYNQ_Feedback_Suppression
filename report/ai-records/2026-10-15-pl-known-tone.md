# 官方播放阈值与自定义 PL 已知音调：协作记录

- 任务 / 日期 / 负责人：隔离两次麦克风直通“听不到”的原因；2026-10-15；AI 执行软件及板卡操作，现场听感和供电/插头核对由用户提供，队员姓名未知。
- 可见模型：Codex；具体内部版本未知。
- 基线：`main`，HEAD `ebaa41d`；开始时仓库已有大量未提交修改，本轮未提交、未推送、未重置。
- 输入：README、`docs/progress.md`、`docs/ai-development-policy.md`、既有诊断 RTL/脚本和板卡 Notebook；官方 PYNQ AudioADAU1761 驱动与 ADAU1761 Rev. F 数据手册。参考源码链接见已有音频诊断记录。原始对话保留在当前 Codex 会话；本文件是人工可核对的摘要，不冒充完整逐字导出。

## 提示、纠错与决策

用户本轮原文：“可以，另外也有可能是我录音你播放时声音与录音同步了没听出来，请你继续你的工作”。第一轮官方三声测试后，用户原文：“完全没听到”。随后用户确认音响供电和 HP+MIC 插头正常，箱外应可听到。第二轮官方三声测试，用户回答“清晰三声”。因此，实时声音重叠不足以解释第一轮已知音调无声；其峰值和 Codec 标称衰减合计约 -36 dBFS，可能低于现场可听阈值，但没有测量声压。

为将声学输入条件从自定义 PL 输出诊断中去除，AI 独立实现 `audio_tone`，以 PL 生成三段音调，不采用箱内麦克风样本。用户明确回答“同意上传并运行”，对象为 `audio_tone.bit`、`audio_tone.hwh`、`bounded_tone.py`，目的地为板卡 `base/audio/audio_tone/`，有声运行 1.5 秒，结束恢复官方配置。执行后用户原文：“我听到的三声很响，你刚才是播放了两组三声吗？”AI 解释当轮共两次独立实验：官方 base 一组三声、自定义 PL 另一组三声，不是 PL 一次播放两组。

## 实际验证与证据

| 层次 | 实际执行及结果 | 边界 |
|---|---|---|
| 官方播放 | `stock_tone(volume=45, amplitude_dbfs=-24)`：72000 帧、峰值 529285、`audio.play()` 1.496 秒，用户未听到；`stock_tone(volume=50, amplitude_dbfs=-18)`：72000 帧、峰值 1056063、1.494 秒，用户听到清晰三声。两次后 Codec 输出静音读回通过。 | 不等于自定义 PL 输出验证；两个幅度均非声压实测。 |
| 旧 WAV 只读检查 | 板上 `recording_0.wav` 双声道、24 位、48 kHz、240000 帧，峰值约 -69.83 dBFS；未下载或上传录音。 | 旧文件的先前可播放反馈不能直接标定当前箱体阈值。 |
| RTL 仿真 | Vivado 2018.3 运行 `build/scripts/test_audio_tone.tcl`，输出 `AUDIO_TONE_PASS`，覆盖 ADC 原路径、物理强制静音、注入音调内部输出活动及停止后静音。 | 自建激励，未验证真实引脚波形或声压。 |
| 综合、实现 | `create_audio_tone.tcl -tclargs build` 完成并生成 bit/hwh；DRC 0 违规，WNS 3.648 ns，WHS 0.030 ns。 | 外部音频 I/O 时序约束不完整，不能称板级时序签核。 |
| 板上 PL 音调 | Jupyter 独立 Notebook 执行 `%run audio_tone/bounded_tone.py`：计划 1.5 秒、实测 1.502 秒、73364 帧、36621 非零处理帧；`PL_CONTROL_MUTED True`、`STOCK_BASE_RESTORED`、`STOCK_PLL_READBACK 0271023c2103`。用户反馈三声“很响”。Notebook 已保存。 | 支持当前配置下 PL→Codec→音响的可听已知音调，不支持 ADC 连续直通或反馈抑制。 |

板卡证据位置：`http://192.168.2.99:9090/notebooks/base/audio/audio_bringup_muted_smoke_2026-10-15.ipynb` 的 In[16] 至 In[19]。该板卡地址仅限当前直连网络，Notebook 中前序失败单元与旧实验亦保留。Bit SHA256 `C6DFD6E64B2E60548142438DCCC9984387BD28C26201C13120A9BE9D49CE9A5D`；HWH SHA256 `F65F552D18EF666136AF725DCE65D737F4DB4D2E2244C7856DEDB977601E369D`；脚本 SHA256 `9D270ED967ED20A678B2109F79324AB8E0D2CAD3E5FD6D1289598AAC50BB5461`。接口说明见 `docs/interfaces/audio-tone-v1.md`。

## 限制与交接

本次没有闭环扩声，没有保存录音；从“可听三声”推断 PL 出口链路有声是基于用户现场反馈与已知音调条件，不是示波器或声压计测量。自定义 PL 的方波与官方正弦波频谱/RMS 不同，不能直接比较响度。两次先前低增益麦克风直通无声仍是保留的失败证据，不据此断言 ADC→DAC 通路故障或已成功。

脚本在 `finally` 清 PL 控制、静音 Codec、恢复官方 base.bit 与原 PLL；现场可切断音响电源。下一步先在**输出持续静音**条件下测当前固定声源进入自定义 ADC 的电平，再设计分级、短时、可停的麦克风直通与同条件对照。不能把降增益或静音当作同增益反馈抑制。结果对应未提交工作区，审阅人未知。
