# 硬件交付：平台、分工、保护归属与构建复现

本文件是报告里硬件部分的来源片段。所有数字取自本仓库 A 分支的实测记录；
技术状态与证据入口以 [STATE](../../../docs/STATE.md) 为准，本文件不复述其结论表。

## 1. 平台与工具链

| 项 | 值 |
|---|---|
| 板卡 | PYNQ-Z2（`tul.com.tw:pynq-z2:part0:1.0`） |
| 器件 | `xc7z020clg400-1`（Zynq-7020） |
| 构建工具 | **Vivado 2018.3**（`D:\Xilinx\Vivado\2018.3`），批处理脚本 `build/scripts/create_audio_replay.tcl` |
| 运行环境 | PYNQ v2.4 overlay + `pynq` Python；驱动以 `replay_trial()` 为入口 |
| 采样率 | 48 828.125 Hz（100 MHz / 2048，整数分频） |
| 定点格式 | 系数 Q20（24 bit 有符号）；数字增益 `control[31:16]` 为无符号 16 位、12 位小数（Q4.12，0…8.0） |

工具链说明（对指南的偏离）：AMD 指南推荐 Vivado/Vitis 2025.2 或 2026.1，其他版本要求报告说明并保证脚本可复现。
本项目**保留已验证的 2018.3**：位流 `48e38f78…` 由该版本产生，Vivado 版本变化会改变实现结果，
而本轮不以重实现换取版本合规。复现步骤见第 4 节，脚本已随仓库提交。

## 2. PS / PL 分工（按实际 RTL）

| 侧 | 实际承担 |
|---|---|
| **PL（`audio_pl_replay.v` + `feedback_fir.v`）** | I2S 串并转换、512 抽头 Q20 预测 FIR、宽残差（25 位）→ 数字增益 → **增益后单次钳位** → 混音、16384 帧捕获环、四类饱和计数、输入满幅粘滞位（`capture_status[22]`）、帧计数与完成计数 |
| **PS（`replay_trial.py`）** | 装载 overlay、经 AXI-GPIO 下系数/声源/增益/帧数、2 ms 轮询状态、**判定是否停声**、写控制寄存器停声、冻结并落盘捕获与 `status.json`、静音 Codec 并恢复 stock overlay |

块设计中使用到的 IP：`processing_system7:5.5`、`axi_gpio:2.0`×6、`clk_wiz:6.0`、`xlconstant:1.1`；
厂商 VHDL `iis_ser.vhd` / `iis_deser.vhd` 为 PYNQ v2.4 原文件（保留原许可与出处）。

## 3. 保护实际归属（报告与视频必须照此表述）

**检测在硬件、判定与停声在软件**——不能写成“FPGA 检测啸叫并自动停声”。

| 事件 | 由谁产生 | 由谁判定与执行 |
|---|---|---|
| 预测 / 残差 / 增益 / 混音饱和 | PL 计数器 | PS 轮询（`stop_reason="guard"`）→ 写 `control=0` |
| 输入满幅（ADC 触轨） | PL 粘滞位 `bit22` | PS 轮询（`stop_reason="input_clip"`）→ 停声 |
| 配置被拒 / 固件故障 | PL 状态位 `bit17` / `bit18` | PS 判定（`stop_reason="fault"`） |
| 未跑满预算 | PS 依据帧数 | `stop_reason="incomplete"` |
| 异常 | PS 捕获异常 | 先停声，再冻结数据，再静音与恢复 |
| 输出不越界 | PL 的增益后钳位 | 硬件行为，与停声无关 |

v3 的语义要点：**增益乘的是未钳位的宽残差，钳位只在增益之后一次**；残差饱和计数只作诊断，
不再中断播放。v3 之前（v2）是在残差处先钳位/先中断，这一点在对照素材里要标清版本。

## 4. 从零复现位流

前提：Vivado 2018.3、Windows 或 Linux 均可，`$root` 为仓库根目录。

1. 生成工程并实现：
   ```
   vivado -mode batch -source build/scripts/create_audio_replay.tcl
   ```
   脚本会建 BD（PS7 + 6×AXI-GPIO + clk_wiz + 两段 RTL）、跑综合与实现、写位流；
   产物在 `build/work/audio_replay/` 下。
2. 取出 `audio_replay.bit` 与 `.hwh` 放入交付包（与 v3 包内同名文件逐字节一致才算同版本）。
3. 校验：`sha256sum` 与 `board/audio_replay/v3/manifest.json` 中 `audio_replay.bit` / `.hwh` 比较；
   不一致说明不是同一构建，不要混用驱动。
4. 上板：把包上传到板卡目录，先跑 `verify_delivered_v3.sh`（身份与位流配对校验，拒绝混搭），
   再跑演示入口；每次试次结束都会静音 Codec 并恢复 stock overlay。

**时序与资源**（实装版本，已施加约束满足）：

| 项 | 值 |
|---|---|
| WNS / WHS | **+0.548 ns / +0.015 ns** |
| TNS / THS | 0 / 0，18 128 个端点 |
| BRAM / DSP / LUT / FF | 80.00 % / 3 / 3 588 / 5 018 |

**如实标注**：这组时序是“已施加约束满足”，**不是完整时序签核**——四个外部 I/O 的输入/输出延迟约束仍未写，
因此对板外器件（Codec、I2S 走线）的建立/保持余量没有约束级证明。报告与视频不得写成“时序全部收敛”。

## 5. 回退与失败原件

- 回退包：板上 `audio_live`（v2 位流 `61bb71aa…`、驱动 `2127663…`）原样未动，可直接回退；
- v1 位流与之同目录；
- 失败试次的 npz 与 `status.json` 成对保留，不删、不改写；报告中引用失败结论时必须同时给版本与停止原因。

## 6. 交付文件清单

逐文件的哈希、用途、依赖见 [integration.json](integration.json)。该清单只列**本线交付所需**的文件，
不整目录混装：根目录旧位流、其它 Python 驱动一律不进交付包。
