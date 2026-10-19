# 闭环试验操作单：每格做什么、怎么做、何时继续

当前四项基础试验均已返回通过，后续请使用 [批次操作单](BATCH_GUIDE.md)，不用重复本页基础步骤。本页保留供首次接手者使用。

## 首次上传（已上传者跳过）

在板卡Jupyter的base/audio新建audio_closed文件夹，将本地同名目录里的bit、hwh、三个py、manifest.json、closed_trial.ipynb上传。打开closed_trial.ipynb。

本次只更新操作说明，不改bit/hwh或脚本。已在板上运行的Notebook可以继续使用，按下列代码首行辨认即可，不必重新上传或覆盖带有结果的Notebook。

## 执行规则

点击要执行的代码格，按Shift+Enter。等待左侧[*]变回数字、输出停止，再看是否符合通过条件。不要点击Run All。首次执行顺序是1→2→3→4→5→6；已完成的试验不用重跑。

现场保持标定时的接线、箱体、麦克风和音响位置；音响接HP+MIC，不戴耳机，能立即切断音响电源。本轮无需讲话或播放手机声音，先保持环境安静。

## 代码格 1：检查文件、加载函数（不发声）
操作：执行下面整格。看到 PACKAGE_HASHES_OK 和 CLOSED_TRIAL_READY 才继续到代码格2。报错就停止并保留完整输出。

```python
import hashlib, json
from pathlib import Path
manifest = json.loads(Path('manifest.json').read_text())
for name in ('audio_closed.bit', 'audio_closed.hwh', 'closed_trial.py', 'closed_tools.py', 'residual_tools.py'):
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == manifest['hashes']['board/audio_closed/'+name], name
print('PACKAGE_HASHES_OK')
%run closed_trial.py

```

## 代码格 2：设置本轮参数（不发声）
目的：固定两模式的音量、时长、夹具和模型，使下一步只改变开关。
操作：现场已按顶部说明准备好、同意采样保存在板卡后，把下面 speaker_confirmed=False 和 local_capture_confirmed=False 的 False 都改为 True。其余参数保持原样，执行整格（包括 filename 函数）。只改文字而没执行，参数不会生效。
- hp_volume=40：Codec音量，与标定一致，不要调整。
- gain_db=-36.0：PL降低音量，首轮保持此值。
- seconds=0.5：每次半秒，首轮保持此值。
执行后通常没有输出，且没有红色报错，即可继续代码格3。此前“0 dB仿真”是电脑测试条件，不要求你把实物增益改成0。

```python
from datetime import datetime
params = dict(fixture_id='box_v1_20261016',
              model_path='../audio_calibrate/candidate_box_v1_256.json',
              gain_db=-36.0, seconds=0.5, hp_volume=40,
              speaker_confirmed=False, local_capture_confirmed=False)
def filename(label):
    return label+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.npz'

```

## 代码格 3：零模型＋旁路（会运行半秒闭环）
目的：检查新通路能否正确传递麦克风数据、按时结束。零模型表示预测系数全部为0。
操作：执行下面整格一次，保持环境安静，等待完整输出；听不到很低的声音不算失败。
通过条件：出现 STOCK_BASE_RESTORED_AND_CODEC_MUTED；verification.bit_exact 为 true；prediction_saturations、residual_saturations、gain_saturations 都为0；结束后现场安静。全部满足才执行代码格4。否则停止，发回完整输出；出现尖叫立即断音响电源。

```python
zero_bypass = closed_trial(filename('zero_bypass'), bypass=True, zero_coeff=True, **params)
print(json.dumps(zero_bypass, indent=2))
```

## 代码格 4：零模型＋抵消开启（会运行半秒闭环）
目的：系数为0时，启用相减仍应保持算术正确；验证另一个分支。
操作：不改参数，不重复代码格3，执行下面整格一次。通过条件与代码格3相同。两次麦克风输入会变化，不要求RMS或录音文件完全相同。
全部满足可继续代码格5；否则停在这里，发回输出。

```python
zero_cancel = closed_trial(filename('zero_cancel'), bypass=False, zero_coeff=True, **params)
print(json.dumps(zero_cancel, indent=2))
```

## 代码格 5：真实模型＋旁路（会运行半秒闭环）
目的：装入标定系数，但暂不从麦克风减去预测，取得对照记录。
操作：零模型两项通过后，参数仍保持 -36 dB、0.5秒、hp_volume=40，执行下面整格一次。不要启动手机声源或移动箱体。
通过条件与代码格3相同。通过后继续代码格6；有错误或饱和则停止。

```python
bypass_result = closed_trial(filename('model_bypass'), bypass=True, **params)
print(json.dumps(bypass_result, indent=2))
```

## 代码格 6：真实模型＋抵消开启（会运行半秒闭环）
目的：实际使用预测相减，再通过相同增益送到DAC。
操作：不改参数，执行下面整格一次。通过条件仍与代码格3相同。
完成后把代码格4、5、6的完整文字输出及是否听到声音、结束是否安静发回；已发过的格3不用重复发送。本轮到这里结束，不自行升高增益或延长时长。

```python
cancel_result = closed_trial(filename('model_cancel'), bypass=False, **params)
print(json.dumps(cancel_result, indent=2))
```

## 本轮完成后怎么理解结果
四项核对的是板上闭环执行、算术和结束恢复；它们不代表ASG已经提高。后续再单独安排较长时长及同增益对照。
每项本地保存NPZ，不上传原始录音；文件名中的时间来自板卡时钟，时钟不准不影响本轮按帧数计时。试验保存末尾16384帧，不能据此宣称全程无啸叫。
如果内核重启导致 closed_trial/params/filename 未定义，重新执行格1、格2，再继续未完成项；不用重跑已完成试验。

## 如何解释结果

- 零系数+单位增益的两模式逐样本等价已由确定性 RTL 输入验证。实物两次麦克风输入不同，不能要求文件逐字相同；也不必冒险一开始就用单位增益。
- `bit_exact` 核对预测、残差及实际播放参考与两帧前残差的关系，**不代表抗啸叫有效**。
- 运行可设0.02～10秒；只保存末尾16384帧，预测校验排除截断窗口的前256帧。饱和计数覆盖全程，预测/残差计数上限65535。
- 当前不含全程窄带增长检测。因此末尾缓存、无报错、无饱和或听感都不足以自动给出 MSG。先确认上板通路，再测同夹具、同 Codec 音量下两模式的可重复稳定增益阈值。ASG = MSG抵消 − MSG旁路。
- 默认静音、有限帧预算和输出饱和器仍可能允许短促大声；保护或削顶不能作为同增益下抵消成功。

## 时序与恢复

100 MHz /2048 = 48828.125 Hz，运行时 Codec PLL50 MHz；结束恢复官方48 kHz配置。FIR仍采用当前播放字入历史、从上一字开始卷积。线级仿真测得 ADC有效到顶层观察FIR输出772拍（7.72µs），到后续TX字装载2286拍（22.86µs）；`played[n+2]=gain(residual[n])`。这些起止点不同，不能相加成端到端延迟。ADC/DAC滤波、串行传输和模拟/声学延迟尚未测量。

正常/异常均尝试PL静音、Codec静音、base恢复、PLL恢复。出现 `RESTORE_ERRORS` 时先断音响电源，不继续试验；重新加载官方base并确认其音频配置后再诊断。

接口见 [closed v1](../../docs/interfaces/audio-closed-v1.md)，本地证据见 [验证记录](../../report/verification/audio_closed/README.md)。
