# 首轮正常扩声 A/B 现场操作包

负责人：A。完整交互规则见[现场交互规范](operator-interaction-standard.md)。下面从打开板卡目录开始，按顺序完成一轮。针对软件包路径和缺失文件报错的Notebook修正版目前只在电脑本地；板卡上已有的旧版Notebook需要按下文单独更新。

## 本轮要做什么

在原反馈路径夹具和固定的箱外手机语音源下，比较相同PL增益时的旁路与模型抵消，判断普通语音扩声中抵消是否更稳定。结果用于决定下一轮是否围绕相邻增益复测阈值，或交B检查模型与夹具适用性。

最多8个增益级。每级旁路、抵消各播放2秒，共最多16次、累计发声最多32秒。上传、配置、输入和设备恢复也需要时间，整轮预计5–10分钟，实际依测得档位和现场操作速度变化；这是计划估计，未实测。完成后返回一份 `summary.json`。原始NPZ留在板卡。

现场使用关盖箱体，MAX4466留在箱内并接LINE_IN，PYNQ-Z2的HP+MIC接有源音响，不戴耳机。手机放箱外固定位置，循环播放同一段语音，整轮保持手机位置、方向和音量不变。现场人员负责确认供电和接线，并能立即切断音响电源。若原标定的箱体、麦克风/音响位置、接线或模拟增益已经变化，本模型适用性未知，本轮停止，不沿用旧fixture_id。

## 按顺序操作

### 第一步：在电脑找到本轮要上传的三个文件，并核查闭环包清单

电脑本地工作目录是 `D:\OCadence_Project\Flushbonading_FPGA_Contest`。需要上传的文件如下：

| 文件名 | 电脑本地完整路径 |
|---|---|
| `field_validation.py` | [电脑本地文件](../../../board/audio_closed/field_validation.py) |
| `field_setup.json` | [电脑本地文件](../../../board/audio_closed/field_setup.json) |
| `field_trial.ipynb` | [电脑本地文件](../../../board/audio_closed/field_trial.ipynb) |

板卡闭环包还必须有 `manifest.json`。它不是本轮新脚本，但代码格1会读取它核对bitstream和驱动版本。电脑本地文件为 [manifest.json](../../../board/audio_closed/manifest.json)。先在板卡目标目录查看是否已有此文件：已有则保留；没有才按第二步上传。不要把“本地有”当成“板卡已有”。

这三份文件目前只在电脑本地。它们不会自动出现在板卡上。候选模型 `candidate_box_v1_256.json` 已有项目记录称保存在板卡 `base/audio/audio_calibrate/`，无需下载，也不要传出原始PCM。

### 第二步：打开板卡的闭环目录并上传文件

1. 在浏览器打开板卡Jupyter文件页。
2. 在文件列表依次进入 `base → audio → audio_closed`。板卡完整目录是 `/home/xilinx/jupyter_notebooks/base/audio/audio_closed/`。
3. 点击页面的 `Upload`，从电脑选择第一步列出的三个 `field_*` 文件。文件选择后若再次出现 `Upload` 确认按钮，再点一次完成上传。
4. 只有当文件列表原本没有 `manifest.json` 时，再用同一个 `Upload` 流程上传电脑本地的 `manifest.json`；若原本已有则不要覆盖。
5. 上传完成后确认板卡文件列表出现 `field_validation.py`、`field_setup.json`、`field_trial.ipynb`，并且已有或刚上传的 `manifest.json` 也在列表中。不要只上传Notebook；`.py`脚本必须单独出现在同一目录。

本次不上传或覆盖 `audio_closed.bit/.hwh`、`closed_trial.py`、`closed_batch.py`、候选模型和已有NPZ。`field_trial.ipynb` 是本次修复对象：若板卡已有旧版，选择电脑本地修正版上传并确认覆盖此同名Notebook；其余同名 `field_*` 文件若不确定版本，先保留并核对。运行器SHA256应为 `BB56D866518814CECEA344C334099C9400D557C12A521C3292C20FD1AFA19EFA`。配置模板由现场填写后哈希会变化，最终哈希由脚本记入summary。

**完成标志：** 板卡Jupyter文件列表里能看到三个 `field_*` 文件和 `manifest.json`。若文件没出现或哈希不符，停在这里，不启动声源。

### 第三步：填写板卡上的现场配置

在Jupyter文件列表中点击 `field_setup.json` 打开文件，填写真实现场值并保存。配置文件完整路径是 `/home/xilinx/jupyter_notebooks/base/audio/audio_closed/field_setup.json`，列表位置是 `base → audio → audio_closed → field_setup.json`。

需要记录箱体尺寸和箱盖状态、麦克风/音响位置与朝向、接线和声道映射、MAX4466供电/增益、扬声器音量控制核对、手机位置/方向/音量/语音片段，以及 `operator_notes`。已知Codec音量固定为40，采样率48828.125 Hz，fixture_id为 `box_v1_20261016`。

仅在现场人员确认反馈路径与原标定夹具一致时，才把 `calibration_match_original` 和 `operator_verified` 设为 `true`；声道映射和扬声器音量控制核对也要按实际情况填写。模板中仍有空项、接线未确认或夹具不一致时，不进入下一步发声。脚本会拒绝不完整配置并保存停止原因。

**完成标志：** 保存后的JSON包含所有现场实值，并且确认原反馈路径夹具未变。若改动了箱体、接线、模拟增益或设备位置，停止使用当前模型，不要把标志设成true。

### 第四步：打开Notebook，核验代码和bitstream

在板卡Jupyter文件列表点击 `field_trial.ipynb`。按标题和首行定位代码格，不看左侧 `In [n]` 执行次数。

| 项目 | 说明 |
|---|---|
| 为什么做 | 核对板卡上的闭环bit/hwh、驱动和本轮现场脚本版本；此步保持静音。 |
| 在哪里做 | Notebook标题“代码格1：软件包核验（静音）”下面，代码首行是 `import hashlib, importlib, json`。 |
| 具体怎么做 | 点击该代码格，按 Shift+Enter 执行一次。代码会先切换工作目录到板卡闭环目录，再读取清单；因此无需手动猜Jupyter从哪个目录启动。 |
| 预期发生什么 | 完成哈希核对，最后显示 `FIELD_PACKAGE_OK; NO_AUDIO_STARTED`。此代码格不会播放。 |
| 接下来怎么办 | 显示通过标记后，继续第五步。若明确提示板卡缺少 `manifest.json`，按第二步仅补传该文件，然后重跑本代码格；其他哈希错误时保存完整输出并停止，不启动手机声源，也不运行旧批次。 |

#### 当前 `FileNotFoundError: manifest.json` 的最短恢复

这个错误发生在静音核验阶段，音频驱动尚未运行，也没有发声。先在板卡文件列表进入 `base → audio → audio_closed`，查看是否有 `manifest.json`：

1. **列表里有 `manifest.json`：** 先按第二步用电脑本地修正版覆盖板卡旧版 `field_trial.ipynb`，再打开该Notebook，重跑“代码格1：软件包核验（静音）”这格。修正版会自动切换到 `/home/xilinx/jupyter_notebooks/base/audio/audio_closed/` 后再读清单。
2. **列表里没有 `manifest.json`：** 从电脑本地 [manifest.json](../../../board/audio_closed/manifest.json) 上传到板卡 `/home/xilinx/jupyter_notebooks/base/audio/audio_closed/`（Jupyter位置 `base → audio → audio_closed`）。确认列表出现文件后，再重跑上述代码格1。

不需要重启Kernel或运行 `Run All`。只有看到 `FIELD_PACKAGE_OK; NO_AUDIO_STARTED` 才进入下一步。

#### 当前 `FileNotFoundError: field_validation.py` 的最短恢复

这个报错发生在代码格1的静音文件核验阶段。根据已返回的回溯，清单及前面列出的bit/hwh/驱动哈希已读过，失败的是现场运行器文件；尚未导入现场运行器，也没有开始发声。只补传缺失文件：

1. 在Jupyter文件列表进入板卡 `/home/xilinx/jupyter_notebooks/base/audio/audio_closed/`（`base → audio → audio_closed`），确认文件列表中没有 `field_validation.py`。
2. 从电脑本地 [field_validation.py](../../../board/audio_closed/field_validation.py) 选择该文件，点击 `Upload`。若出现第二个确认 `Upload` 按钮，再点击一次。
3. 等文件列表显示 `field_validation.py` 后，打开已修正的 `field_trial.ipynb`，只重跑标题“代码格1：软件包核验（静音）”、首行为 `import hashlib, importlib, json` 的代码格。
4. 预期显示 `FIELD_PACKAGE_OK; NO_AUDIO_STARTED` 才继续代码格2。SHA256十六进制字母大小写不影响摘要，核验不区分大小写；只有数字或字母内容不同才是哈希不匹配。不要运行代码格2，不用重启Kernel或重传bitstream、hwh、NPZ。

若错误显示实际值 `bb56d866518814ce…`、预期值 `BB56D866518814CE…`，两者仅大小写不同，文件已匹配。把电脑本地修正版 [field_trial.ipynb](../../../board/audio_closed/field_trial.ipynb) 上传到同一板卡目录并覆盖旧Notebook，然后只重跑代码格1。不要重传 `field_validation.py`。

### 第五步：现场就绪后启动整批

代码、配置和版本核验都完成后，再准备声源和音响。一次只由A控制板卡，不要同时运行其他音频Notebook。

| 项目 | 说明 |
|---|---|
| 为什么做 | 在固定语音条件下逐级比较同增益的旁路与抵消，判断普通语音是否可听及哪种模式先出现增长或异常。 |
| 在哪里做 | `field_trial.ipynb` 标题“代码格2：运行一次配对批次”下面，代码首行是 `field_result = field_validation.run_field_validation()`。 |
| 具体怎么做 | 点击该代码格，按 Shift+Enter 一次。静音预检完成后，先阅读屏幕显示的模型哈希和估算增益范围；提示 `READY` 时启动固定位置的手机语音循环，确认音响可立即断电且同意数据仅保存在板卡，再输入 `READY`。看到批次范围后输入 `START` 确认开始。每项配置完成且保持静音时，准备听再输入该项的 `START`。 |
| 预期发生什么 | 脚本在静音状态读取候选模型并给出估算范围，再按每级旁路先行、抵消随后执行。每项持续2秒，结束后恢复官方base和Codec静音。累计最大发声32秒。 |
| 接下来怎么办 | 每项结束输入听感码：`0`无声且结束安静，`1`听到清楚人声且结束安静，`2`杂音，`3`尖叫或增长，`4`结束仍响，`q`主动停止。`0/1`继续；`2/3/4/q`停止剩余批次。出现算术错误、配置不一致、饱和或恢复错误也停止。尖叫仍持续时立即切断音响电源，输入框不能实时急停。 |

`READY`和`START`提示都在软件静音阶段出现。现场输入只用于确认准备完成；音频只在某一项配置完成后，用户再次输入该项的 `START` 时开启。不要执行Notebook的Run All，也不要重复运行代码格2来跳过失败项。

### 第六步：下载并返回唯一结果文件

Notebook结束或中途停止后，摘要位于板卡：

`/home/xilinx/jupyter_notebooks/base/audio/audio_closed/field_results/field_<id>/summary.json`

在Jupyter文件列表依次打开 `base → audio → audio_closed → field_results → field_<id>`，下载 `summary.json` 并返回。摘要保存配置、模型/bit哈希、每项听感和数字核对、停止原因、累计发声秒数及流程耗时。原始NPZ/PCM留在板卡，不要下载或上传。

之前的四项低增益基础结果已经归档，不用重复粘贴。本轮只返回新的summary和现场配置说明。

## 测试范围依据和结果解释

起点为−30 dB，比已完成但不可听的−35.99 dB提高6 dB；之后每级增加3 dB，最多8级。板卡脚本根据候选模型 `sum(abs(h))` 估算保守范围并留6 dB余量。候选模型是开环路径估计，这个数不是实测稳定阈值。若估算范围不足以覆盖−30 dB，脚本不播放。

每一对固定bit、模型/系数、Codec音量、声源、PL增益、时长和夹具，只切换bypass。听感和数字核对分别记录。“没有尖叫”“没有报错”和数字匹配不能互相代替。若旁路在本次范围都未失稳，写“已测范围内未找到阈值”；若抵消更差或没有改善，照实记录并把配置和摘要交B分析。当前缓存只覆盖末尾波形，不计算精确MSG/ASG。

## 故障时怎么做

- 配置预检失败：未发声。查看summary中的 `stop_reason`，补齐配置；重新执行代码格1，再执行代码格2一次。
- 文件或模型哈希错误：不发声，保留输出，检查文件版本，不要覆盖bitstream或候选模型。
- 听到尖叫或声音持续：立即切断音响电源；出现输入提示后输入 `q` 停止整批。
- 出现 `RESTORE_ERRORS`：先断音响电源，不继续试验；保留summary和完整输出，确认base与Codec恢复后再另行处理。
- 批次中途停止：保留本批已完成记录，不重跑来绕过失败原因；最终仍返回该目录的summary.json。

更改 `field_setup.json` 后保存，再重新执行代码格1核验，随后只执行代码格2一次。参数在代码格2运行时从JSON读取，本Notebook没有单独参数代码格。

## 操作前核对

每次操作都从第一步重新核对电脑本地文件与板卡文件列表；不要根据本说明推断上次上传仍然存在。板卡上缺哪个文件就按对应恢复步骤补齐，再运行静音核验代码格1。
