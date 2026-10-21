# 逐档增益 A/B：只按这三格操作

## 优先使用按钮页（2026-10-21）

A已获SSH部署和静默调试授权；上传、版本核验、选档和读摘要均由A完成。用户打开A提供的现场链接即可，勿同时运行Notebook。
页面不会自动加载overlay或播放。先关闭音响电源，勾选条件、点“准备录音”；等提示后启动手机语音并点“开始录音 · 2秒”。
录完停止手机外放、恢复音响供电，点“开始本批”。每次按页面勾选现场条件后点“开始本项”，结束点听感。
“停止后续项目”不能保证实时急停；持续尖叫直接断音响电源。连接掉线时停止后续操作，A负责恢复；单次仍受PL帧预算限制。
已有source.wav则复用，用户无需重新录音。摘要由A通过SSH读回，原始PCM留板。

下面的Notebook步骤仅作手动备用。


本轮回答：手机停止外放后，同一录音、不同反馈增益下，抵消和旁路分别是否出现啸叫、失真或无声。先静默读取已有标定数据选档，不重新标定。

## 1. 上传一次

电脑本地完整包：`D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\build\packages\audio-replay.zip`。
解压后进入`audio_replay`，共有15个交付文件：

`audio_replay.bit`、`audio_replay.hwh`、`replay_trial.ipynb`、`manifest.json`、`README.md`、`replay_trial.py`、`replay_tools.py`、`replay_session.py`、`closed_tools.py`、`residual_tools.py`、`replay_calibration.py`、`sweep_plan.py`、`sweep_session.py`、`click_panel.py`、`click-panel.html`。

板卡Jupyter进入 **base → audio → audio_replay**；完整目录：
`/home/xilinx/jupyter_notebooks/base/audio/audio_replay/`。
没有目录则在`base → audio`点击`New → Folder`，命名`audio_replay`并进入。
点击`Upload`选择上述15个文件，再点击列表中的确认`Upload`；更新时覆盖同名程序文件。
**保留已有source.wav、replay_results及其他目录。** 上传后文件列表应有全部15项。

仅打开这个音频Notebook：
`/home/xilinx/jupyter_notebooks/base/audio/audio_replay/replay_trial.ipynb`。
不要同时运行其他音频Notebook，不用Run All。更新旧包后先重启该Notebook内核，关闭音响电源。

## 2. 第1格：静默选档

- 找标题“第1格：静默选档”，代码首行`from pathlib import Path`。点击代码格，Shift+Enter一次。
- 该格不加载overlay、不发声。复用板卡已有配置：
  `/home/xilinx/jupyter_notebooks/base/audio/audio_closed/field_setup.json`。
- 从板卡`/home/xilinx/jupyter_notebooks/base/audio/audio_calibrate/`读取：
  `training_box_v1.npz`、`validation_box_v1.npz`、`candidate_box_v1_256.json`。
- 等到列出全部可测档位并显示“静默选档完成”才继续。分析耗时依板卡而定；这时不用讲话或播放手机。
- 若缺文件、夹具不符、模型无改善或不足两档，返回屏幕打印路径的`summary.json`，到此结束。不要改限制强行通过。

## 3. 第2格：录2秒，然后停手机

- 音响保持断电，箱盖、麦克风与两只音响位置保持原标定状态。
- 找“第2格：录音2秒”，首行`assert plan_path is not None, ...`，Shift+Enter一次。
- 等到RECORD提示出现，再让手机在原位置播放语音，输入`RECORD`回车，立即录2秒。
- 录完**停止手机外放**。已有`source.wav`自动复用；如要换录音，先把旧文件改名备份。

## 4. 第3格：连续完成整批

- 手机已停止外放，恢复音响供电。只用固定音响，勿戴耳机；音响电源须能立即切断。
- 找“第3格：逐档听音”，首行`result = sweep_session.run_sweep(plan_path)`，Shift+Enter一次。
- 先看总项数、每项时长，现场就绪输入`READY`。
- 每项配置完成、提示START后，准备听再输入`START`。立即播放并采样，默认约2.4秒后自动静音。
- 先做一次直放可听确认；然后按升序每档**先抵消、后旁路**。只改变反馈增益和指定的bypass，整批录音电平固定。
- 每项结束输入：**0无声，1语音清楚且结束安静，2杂音失真，3啸叫增长，4结束仍响**。只有1继续，其他值停止整批。若旁路出现啸叫，同档抵消项已经完成。
- 持续尖叫时先断音响电源。输入框不是播放中的实时急停。饱和软件轮询会尝试提前停止，PL帧预算限制单次时长；都不能代替现场断电。

最多8档、17项；录2秒时总发声最多约40.8秒，整轮预留10–15分钟（含分析、上传和操作，非板上实测耗时）。不必每项回聊天。

## 5. 结束，只返回一个文件

在Jupyter **base → audio → audio_replay → replay_results → sweep_<编号>** 下载`summary.json`。
完整路径：`/home/xilinx/jupyter_notebooks/base/audio/audio_replay/replay_results/sweep_<编号>/summary.json`。
它包含选档依据、文件哈希、每档实际增益、配对、听感和停止原因。WAV/NPZ留板。

出错或中断：先关闭音响，保留摘要，不连续重跑；内核重启后可重跑第1格产生新批次，已有录音不需重录。配置若修改，必须保存并重新执行第1格，内存中的旧计划不会自动更新。

本流程是预录数字声源下的声反馈增益对照，直放可听不等同于正常麦克风扩声成立。若全部档位均正常，记录“已测范围未找到旁路失稳阈值”；不虚构MSG/ASG。已有数据不支持更高档位时，程序停止而非盲目升增益。


### 第1格报Notebook哈希不匹配的恢复

这是旧版把执行次数/输出也计入Notebook文件哈希导致的误判风险。新版只核验按顺序排列的代码格内容。
已有旧包时，只需从电脑`D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\board\audio_replay\`上传新版`replay_session.py`与`manifest.json`，覆盖板卡`/home/xilinx/jupyter_notebooks/base/audio/audio_replay/`同名文件；Upload后再次点击确认Upload。
保留Notebook、标定数据、录音和已有结果，然后只重跑“第1格：静默选档”（首行`from pathlib import Path`）。
这一步不发声；成功列出档位才继续第2格。若报“Notebook代码与程序包不匹配”，则需恢复配套Notebook，因为代码格内容确有差异。
