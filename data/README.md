# 测试输入与参考结果

本目录提供可离线复核的非私人参考向量。现场测量的派生结果、运行身份和验证回执保存在
[report/verification](../report/verification/)；历史模型和系数保存在 [models](../models/)。

## 随包数据

| 文件 | 内容 | 用途 |
|---|---|---|
| [reference/ordinary.csv](reference/ordinary.csv) | 普通整数样本及对应播放、预测、残差列 | 检查基本算术一致性 |
| [reference/negative-rail.csv](reference/negative-rail.csv) | 合法负满幅边界样本 | 检查负满幅不被误计为宽残差溢出 |
| [reference/prefix-overflow.csv](reference/prefix-overflow.csv) | 截断窗口前缀的越界反例 | 检查前缀事件被保留和计数 |
| [reference/manifest.json](reference/manifest.json) | 列定义、参数、来源、SHA256及预期结果 | 自动复核入口 |

这些是从已有软件用例整理的合成输入，不是板卡采集或真人录音。
边界反例包含有意注入的越界数值，用于检验统计口径，不能作为有效现场音频或声学性能证据。

## 复核方法

工程RAR解压后，在项目根目录执行：

```text
python -B tools/submission/submission_reference.py --root . --verify
```

需要 Python 3.8 或以上及 NumPy。预期三组向量全部通过，退出码为0；完整字段说明和预期计数见manifest。
不调用板卡、不播放声音，不向设备安装这些参考参数。

## 现场数据的范围

提交包不包含私人语音PCM和现场返回录音压缩包。实机结论应按验证回执的模型、布局、增益及采样窗口解释；
合成参考向量用于验证软件口径，不能代替对应现场原始采集，也不能用于声称整机抗啸叫增益或听感收益。
