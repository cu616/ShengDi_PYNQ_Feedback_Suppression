# 开环反馈标定：现场执行单

> **保留的开环标定工具及历史操作样例。** 下文状态、箱体和模型只属于当时场次；“实时抵消仍待开发”等描述不是项目现状。重新标定必须绑定实际夹具与模拟设置，接手不默认重跑。现状见 [STATE](../../docs/STATE.md)，版本选择见 [board 索引](../README.md)。

本目录的 bit/hwh 是独立工程，不能和 audio_probe/audio_capture 混用。本地仿真、综合实现和模拟硬件脚本测试已通过；2026-10-16用户返回第一轮32768帧采集成功、参考序列校验通过及恢复静音输出，后续独立验证轮和真实路径拟合亦已完成，预测误差降低9.69 dB，见report/verification/audio_calibrate/board-analysis-2026-10-16.md；实时抵消仍待开发。现场同一时间只运行这一份 Notebook。

## 本次需要现场配合的内容

1. 停止手机及其他测试声源。箱体、MAX4466、模拟增益和接线保持固定，并给这套条件起一个标识，例如 `box_v1_20261016`。
2. 摘下耳机，将 HP+MIC 接回有源音响；确认可以立即切断音响电源。不要戴耳机运行本标定。
3. 本次每轮播放约0.67秒的低电平已知噪声，麦克风不会实时送回音响；采集麦克风及输出参考，并将短时PCM只存板卡本地 `.npz`。需同意这一声音测试和本地保存。程序不会将录音上传电脑或云端。
4. 将本目录 `audio_calibrate.bit`、`audio_calibrate.hwh`、`open_loop_capture.py` 三文件一起上传到新目录 `base/audio/audio_calibrate/`，在该目录新建Python Notebook。既有基线文件不覆盖。

## 先定义，准备好后再运行

第一格只定义函数，不发声：

```python
%run open_loop_capture.py
```

现场条件确认后，第二格启动**一轮**。下面两个True仅在上述条件实际满足且同意本地保存时填写：

```python
training_meta = open_loop_capture(
    'training_box_v1.npz', fixture_id='box_v1_20261016',
    seed_variant=0, shift=4, hp_volume=40,
    speaker_confirmed=True, local_capture_confirmed=True,
)
```

先核对输出包含 `STOCK_PLL_READBACK 0271023c2103`、`STOCK_BASE_RESTORED_AND_CODEC_MUTED`、`LOCAL_CAPTURE_SAVED`、32768帧和 `reference_sequence_verified: True`，无 `RESTORE_ERRORS` 或Traceback；本轮声音结束。采集完成后读RAM可能需要额外时间，这段时间Codec已经静音。若失败或声音未停，切断音响电源，保留输出，停止后续步骤。

在完全相同的箱体和增益条件下，再单独运行一格作为独立验证数据：

```python
validation_meta = open_loop_capture(
    'validation_box_v1.npz', fixture_id='box_v1_20261016',
    seed_variant=1, shift=4, hp_volume=40,
    speaker_confirmed=True, local_capture_confirmed=True,
)
```

每轮使用新文件名，不覆盖旧数据。源幅度最大约−24.1dBFS，Codec参数40标称衰减约17dB；这是数字/寄存器尺度，不是声压测量。若信号太弱，先依据样本评价原因，不直接连续加音量。不要改接线或旋钮后仍沿用同一个fixture_id。

请先只提供两格文字输出与听感。原始npz保留板上；后续若需传到电脑做离线分析，另明确授权传输这两份文件，或将算法模块部署到板上本地分析。

## 恢复和代码位置

脚本会恢复官方base与原PLL，并将Codec输出静音。旧Notebook的音频/MMIO对象失效，后续重新初始化。出现恢复异常时不要继续播放。软件估计器位于 `src/feedback/calibration.py`，电脑命令行入口为 `scripts/fit_feedback_path.py`；协议与限制见 `docs/contracts/feedback-calibration-v1.md`。

本目录校验值见 `manifest.json`。已知的外部音频I/O时序约束缺口仍保留，不以WNS正数宣称板级签核。
