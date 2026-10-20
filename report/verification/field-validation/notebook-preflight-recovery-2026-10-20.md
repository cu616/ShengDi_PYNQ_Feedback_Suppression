# 现场Notebook缺少运行器文件：静音恢复记录

## 观察到的错误

现场人员执行 `field_trial.ipynb` 的首个软件包核验代码格时，回溯落在 `Path('field_validation.py').read_bytes()`，抛出 `FileNotFoundError`。用户提供的输出显示此前已读取 `manifest.json` 并完成闭环包文件哈希循环，失败发生在现场运行器的哈希核验处。

## 阶段与影响

该异常发生在代码格1的静音预检；模块导入语句尚未执行，配对批次代码格2也未运行。本次没有板卡播放结果。结合代码先切换到 `/home/xilinx/jupyter_notebooks/base/audio/audio_closed/`，可判断板卡目标目录缺少 `field_validation.py`，或该脚本没有上传至此目录。

## 恢复步骤

电脑本地 [运行器](../../../board/audio_closed/field_validation.py) 上传到板卡目录 `/home/xilinx/jupyter_notebooks/base/audio/audio_closed/`（Jupyter文件列表 `base → audio → audio_closed`）。确认列表出现文件后，只重跑标题“代码格1：软件包核验（静音）”、首行为 `import hashlib, importlib, json` 的代码格。预期 `FIELD_PACKAGE_OK; NO_AUDIO_STARTED`。哈希不匹配时停止，核对上传文件 SHA256 为 `BB56D866518814CECEA344C334099C9400D557C12A521C3292C20FD1AFA19EFA`；不运行代码格2，不重传bit/hwh或原始数据。

Notebook已增加缺文件与哈希不匹配的明确报错，并把同一单文件恢复步骤加入[现场操作包](../../../docs/experiments/field-validation/README.md)。

## 后续核验纠错

用户补传运行器后，第二次代码格1报告实际 SHA256 为小写 `bb56...19efa`、预期为大写 `BB56...19EFA`。两串十六进制内容相同，仅大小写不同；Notebook 原比较是区分大小写的字符串比较，导致错误拒绝了正确文件。已将比较改为大小写归一后再判断。电脑本地 `field_validation.py` 不需重传；将修正版 `field_trial.ipynb` 覆盖上传到同一板卡目录，再重跑代码格1。仍处静音核验阶段，没有运行代码格2或播放音频。

用户随后报告代码格1无法找到板卡 `field_setup.json`。运行器已通过哈希核验，停止在配置文件存在性检查，仍未导入并运行批次。只需上传电脑本地 `board/audio_closed/field_setup.json` 模板到相同板卡目录，再重跑代码格1。模板不含现场实值；现场条件未核对时不要臆填，也不要运行代码格2。操作步骤已补入[现场操作包](../../../docs/experiments/field-validation/README.md)。

## READY交互位置说明

用户运行代码格2后，截图中的执行编号已返回数字，输出了 `结果：field_results/field_<id>/summary.json`，但没有显示READY提示。这表示函数已经退出，不存在可继续输入的交互框；脚本异常退出时也会保存summary并打印该路径。当前停止原因未知，必须先从板卡Jupyter文件列表打开 `base → audio → audio_closed → field_results → field_<id> → summary.json`，读取 `status` 与 `stop_reason`，再决定恢复步骤。未要求用户重跑或开始发声。
