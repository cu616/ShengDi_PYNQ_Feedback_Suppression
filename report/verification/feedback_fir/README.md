# 定点抵消与算法优化结果（2026-10-18）

本轮完成独立定点FIR预测/残差核、软件参考和研究用NLMS原型，并实际执行软件测试、RTL仿真、独立核综合布线及合成对照。尚未接入音频overlay，没有新的实物抑制结果。

## 硬件计算核

- 源码：`src/rtl/feedback_fir.v`；接口：`docs/interfaces/feedback-fir-v1.md`。
- 256抽头，24位PCM和Q20系数，58位累加，显式前一帧参考，预测与残差各自饱和。
- 3组不同系数共2304帧，与Python整数参考的预测、残差及饱和标志逐项一致；包含边界采样、旁路、系数重载清历史、忙时输入报错及复位中断。
- 固定延迟771拍（100MHz下7.71微秒），小于当前2048拍帧周期；不是ADC到DAC总延迟。
- Vivado2018.3独立核out-of-context布线：LUT876、寄存器406、DSP2、BRAM0；内部WNS2.341ns、WHS0.053ns。
- 这不是完整板级签核：OOC缺少系统端口延迟/实际时钟源信息，DRC保留DSP流水、无外部负载、缺PS7等警告。没有生成可直接上板的完整bit/hwh。

初版虽然行为仿真正确，但输出长组合路径WNS −2.033ns；拆分舍入、饱和与减法后仍有RAM寻址到乘法路径 −0.323ns。增加独立读操作数阶段后满足内部时序。两次失败报告保留为initial-timing-failed.txt和second-timing-failed.txt。最终数值结果保持一致。

## 算法比较（仅合成数据）

最新版结果文件为synthetic-ablation-v2.json。v2在所有长度统一跳过512帧，保证同一区间比较，并使用最终三拍MAC周期估计；早期synthetic-ablation.json保留作过程记录，不作为当前表格依据。

| 抽头 | 浮点预测误差降低 | 完整整数预测误差降低 | 估计核周期 |
|---|---:|---:|---:|
| 128 | 10.2408 dB | 10.2408 dB | 387 |
| 256 | 11.7571 dB | 11.7571 dB | 771 |
| 512 | 31.5084 dB | 31.5084 dB | 1539 |

该用例故意包含512抽头衰减尾部和第330抽头回声，因此更长模型能覆盖256抽头遗漏的成分；不能用此结果直接决定真实箱体也必须改成512。三组残差饱和样本均为0。当前RTL实际仿真/实现为256抽头，其余长度周期是公式估计，尚未各自布局布线。

另一个独立激励用例在第8000帧将路径整体延迟7帧并缩放0.85倍。最后2048帧上固定模型预测误差降低−3.5437 dB，受控NLMS为30.0997 dB。NLMS具有显式更新许可、低参考能量冻结、系数越界拒绝；冻结时系数保持不变。该结果只说明在独立开环激励下可以跟踪所设路径变化，没有验证闭环语音相关性、自动双讲检测或实际箱体适应能力，不部署普通NLMS到扩声闭环。

## 已执行及下一步

19项软件测试通过，见software-tests.txt；RTL成功标记见rtl-simulation.txt。最终实现报告为core-timing.txt、core-utilization.txt、core-drc.txt。源文件哈希见source-manifest.json。

复现顺序（在仓库根目录，Python需NumPy，Vivado需2018.3）：

```text
python -m unittest discover -s sim/feedback -p "test_*.py" -v
python scripts/make_fir_vectors.py
vivado -mode batch -source build/scripts/test_feedback_fir.tcl
vivado -mode batch -source build/scripts/implement_feedback_fir.tcl
python scripts/compare_feedback_models.py --output tmp/new-comparison.json
```

连接恢复后，`board/audio_calibrate/compare_lengths.py`已上传并在板卡执行完成。真实数据128/256/512抽头分别4.2800/9.7974/10.1671 dB，完整整数与浮点基本一致；首版保留256抽头，见 [板卡结果与决策](board-length-comparison-2026-10-18.md)。此前访问超时属于过程故障，不再是当前阻塞。

真实数据比较会复用已经看过的验证集，结果只能叫开发比较。如果据此选择长度或调整参数，最终验收需新的独立记录。下一阶段是实际数据选型与音频工程的开环残差集成，而非继续调整环境或重做基础有无声音排查。
