# 首轮正常扩声 A/B 操作步骤

目的：在同一正常语音场景下比较旁路与抵消。现场暂不可用时，只完成文件准备和静音核验，不启动声源。

上次摘要显示配置通过，但模型估算上限为 `−34.54 dB`，原起点 `−30 dB` 超出范围，因此零播放。已把默认起点改为 `−35 dB`；按当前模型只会安排一个旁路/抵消配对，共4秒发声。若模型文件变化，脚本会重新计算允许档位。

## 第一步：填写电脑上的配置

打开 [field_setup_ready_to_edit.json](../../../board/audio_closed/field_setup_ready_to_edit.json)，核对坐标原点及数组顺序：模块1 `[12,6,3]`、模块2 `[6,12,3]`。核对无误后另存为 `field_setup.json`，覆盖本地空模板。麦克风增益为 `cantcontrol`；扬声器无外置音量按钮已单独记录。

另存为 `field_setup.json`，放在电脑目录 `D:\OCadence_Project\Flushbonading_FPGA_Contest\board\audio_closed\`。

## 第二步：上传到板卡

在板卡 Jupyter 文件页进入 `base → audio → audio_closed`，完整路径为 `/home/xilinx/jupyter_notebooks/base/audio/audio_closed/`。

上传以下电脑文件至该板卡目录：

| 电脑本地完整路径 | 上传名 |
|---|---|
| `D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\board\audio_closed\field_validation.py` | `field_validation.py` |
| `D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\board\audio_closed\field_trial.ipynb` | `field_trial.ipynb` |
| `D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\board\audio_closed\field_setup.json`（由上一步生成） | `field_setup.json` |
| `D:\OCadence_Project\Flushbonading_FPGA_Contest\tmp\a-feedback\board\audio_closed\manifest.json` | 仅板卡缺失时上传 |

点击 `Upload` 选择文件；若再次出现 `Upload` 确认按钮，再点一次。覆盖同名运行器和Notebook。确认文件出现在板卡目录后打开Notebook。

确认文件列表出现以上文件后，点击打开 `field_trial.ipynb`。不要运行 `Run All`。

## 第三步：静音核验

找到标题“代码格1：软件包核验（静音）”、首行为 `import hashlib, importlib, json` 的代码格，按 `Shift+Enter` 一次。

看到 `FIELD_PACKAGE_OK; NO_AUDIO_STARTED` 即完成准备。若报文件缺失，只补传报错指出的文件；若哈希不匹配，停止并把完整错误发回。此格不播放声音。

## 第四步：现场可用后运行一批

先确认箱盖、供电、接线、音响断电方式及固定位置手机循环语音；整批保持位置、Codec 音量、手机音量和接线不变。只有A操作板卡。输入框等待期间不能急停，尖叫或持续响声时立即切断音响电源。

找到标题“代码格2：运行一次配对批次”、首行为 `field_result = field_validation.run_field_validation()` 的代码格，按 `Shift+Enter` 一次。第一次提示输入 `READY`：确认声源已就绪且能断电后输入。第二次提示输入 `START`：核对范围后输入。每项配置完成、准备听时，再按第三种提示输入该项的 `START`。输错或不想继续时，输入其他内容会取消/停止，不会开始下一项。

每项听感按屏幕提示记录。听到尖叫、持续响声、杂音或出现恢复错误时停止；尖叫持续时先断音响电源。禁止运行无限循环或盲目提高增益。

## 第五步：取回结果

从板卡目录 `base → audio → audio_closed → field_results → field_<编号>` 下载 `summary.json` 并交回。原始NPZ/PCM留在板卡。若未开始发声，也交回摘要，确认 `sound_seconds_completed` 为 `0`。

### 本次现场配置

- 夹具：箱体 `17×17×7 cm`，关盖；MAX4466在箱内，接 `LINE_IN`。
- 输出：PYNQ-Z2 `HP+MIC` 接有源音响；两只音响模块按配置文件分别记录位置。
- 声源：手机固定在箱外，循环播放同一语音，位置及音量不变。
- 配置：Codec音量40；MAX4466供电5V；麦克风增益记录为 `cantcontrol`。
- 若实际接线、夹具或麦克风/音响位置与原标定不同，停止使用当前模型并先记录变化。
