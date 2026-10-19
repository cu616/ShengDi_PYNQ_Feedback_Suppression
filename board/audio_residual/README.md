# 开环残差验证操作单

2026-10-19更新：用户已完成首次板上开环验证，逐样本一致、无饱和、预测误差降低6.92 dB。详见 [实测记录](../../report/verification/audio_residual/board-result-2026-10-19.md)。下文构建/首次操作说明保留对应阶段边界。

本包将256抽头模型放进PL，同时记录实际DAC参考、麦克风、预测和残差。DAC只播放固定宽带激励，麦克风不回送DAC，**尚未构成闭环抑制**。

## 文件

- `audio_residual.bit/.hwh`：同一次构建的整板配置，是否已生成及验证看manifest和progress。
- `open_loop_residual.py`：加载模型、短时激励、四路读回、自动恢复官方base及PLL，并在板卡本地保存。
- `residual_tools.py`：校验候选系数，独立整数卷积与PL逐字对照。
- `manifest.json`：包和源码哈希，生成后才可核对上传。
- `residual_trial.ipynb`：上述手动流程的现成Notebook；第一代码格核对包哈希并定义函数，第二格才会发声。可上传后直接使用，不必自己拼代码。

第一格只核对bit/hwh及两个py文件。Notebook自身会随Jupyter执行计数、输出和保存而变化，不参与运行文件哈希校验。2026-10-19已修复旧版将Notebook自身列入校验导致的AssertionError；旧manifest仍可配合新版第一格使用。

## 现场执行（由操作者手动运行，勿 Run All）

1. 耳机摘下，音响接回既有固定箱体，停止外部声源。箱体、接线和增益保持标定时状态，并保留随手断电方式。一次只有一个操作者。
2. 将包中bit/hwh、两个py、manifest.json和residual_trial.ipynb放入板卡 `base/audio/audio_residual/`。现有模型留在 `../audio_calibrate/candidate_box_v1_256.json`。本包不含、也不要求传出任何原始录音。可直接打开residual_trial.ipynb逐格执行；下文也提供手工新建版本。
3. 在该目录新建Notebook，只运行定义格：

```python
%run open_loop_residual.py
```

4. 准备好约0.336秒短噪声和板卡本地保存后，手动运行一次：

```python
result = open_loop_residual(
    'residual_box_v1_001.npz',
    fixture_id='box_v1_20261016',
    model_path='../audio_calibrate/candidate_box_v1_256.json',
    seed_variant=1, shift=4, hp_volume=40,
    speaker_confirmed=True, local_capture_confirmed=True,
)
```

HP音量40沿用标定设置；没有旋钮调节要求。原始四路只存板卡，文件名不可覆盖。PS逐地址读回比发声时间长，读回前Codec已静音且PL已停止，不需持续播放手机人声。

5. 返回完整文字输出，重点看 `STOCK_BASE_RESTORED_AND_CODEC_MUTED`、`RESIDUAL_VERIFICATION` 的 `bit_exact=True`、两类mismatches均0、saturations均0。若出现RESTORE_ERRORS，不再发声，先断音响电源并处理恢复。

`prediction_reduction_db`采用训练模型bias和256帧预热；不与上轮统一512帧预热数字直接等同比较。非bit-exact时保留诊断数据，指标为None，不算通过。这里复用旧激励，是硬件实现验证，不是新的独立算法验收；新路径和新独立激励仍需后续安排。

恢复过程依次停止PL、静音Codec、恢复base.bit、恢复官方PLL并再次静音；仅脚本成功返回不能替代现场状态核对。当前包尚未上板验证，先以progress中的最新构建状态为准。
