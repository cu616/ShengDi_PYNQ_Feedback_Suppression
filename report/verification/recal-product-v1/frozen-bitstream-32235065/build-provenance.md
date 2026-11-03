# 冻结位流 32235065… 的资源 / 时序 / DRC 报告与构建来源说明

本页交给 C 打包使用。所有报告**优先取自 2026-11-01 那次原始构建的输出**（未重新综合/布局布线/生成位流）；
仅"Routed 状态的利用率报告"是事后从同一次构建的 routed DCP 补导出的，已单独存放并标注导出时间。
无需操板，全部为本地文件核对。

## 1. 冻结位流身份

| 项 | 值 |
|---|---|
| 位流 sha256 | `322350656986d91f25a63735f87e5b0b9cc2f7ea977356ce9e988014648e738e` |
| 位流大小 | 4,045,674 字节 |
| 位流路径（原始构建） | `_a_work/wt-int/build/work/audio_replay_io/audio_replay.runs/impl_1/system_wrapper.bit` |
| 生成时间 | 2026-11-01 18:28:23（本机时区） |
| 仓库内同内容文件 | `board/audio_replay/v3-io/audio_replay.bit`（sha256 相同） |
| 产品侧身份 | 与上板包 `identity.bit_sha256` 一致（见 `docs/STATE.md`、包内 `product-manifest.json`） |
| 器件 | xc7z020clg400-1（PYNQ-Z2） |
| 工具版本 | **Vivado v.2018.3 (win64), Build 2405991**（所有报告头部一致） |

## 2. 对应的已布线 DCP（用于报告补导出与对应关系证明）

| 项 | 值 |
|---|---|
| DCP 路径（原始构建） | `_a_work/wt-int/build/work/audio_replay_io/audio_replay.runs/impl_1/system_wrapper_routed.dcp` |
| DCP sha256 | `99fbc007d50ec5cc071b9a3b3df6bff8fc48fe22a6836fcfc2c69aaa3edb04e2` |
| DCP 大小 | 5,087,364 字节 |
| DCP 时间 | 2026-11-01 18:27:55 |
| 入库副本 | [dcp/system_wrapper_routed.dcp](dcp/system_wrapper_routed.dcp)（sha256 相同） |

**DCP 与冻结位流对应的依据（同一构建运行内的时间链 + 哈希链）**：

1. 位流与 DCP 位于**同一个实现运行目录** `audio_replay.runs/impl_1`；
2. 该目录内只有一个 routed checkpoint（`system_wrapper_routed.dcp`，18:27:55），
   其后的 `write_bitstream` 阶段标记为 `.write_bitstream.begin.rst` 18:28:04 /
   `.write_bitstream.end.rst` 18:28:25，而位流文件时间 18:28:23 **落在该窗口内**；
3. `logs/runme.log`（本次运行的日志，sha `48d0b6d3…`）记录了 route_design → write_bitstream 的完整顺序；
4. 该目录产出的 `system_wrapper.bit` sha256 = `32235065…`，与冻结位流、仓库
   `board/audio_replay/v3-io/audio_replay.bit` 完全一致；
5. 事后用 Vivado 2018.3 打开该 DCP 补导出的 Routed 利用率报告，器件/设计名与上表一致。

> 说明：Vivado 本身不记录 git 提交号；"构建来源"由**工程引用的源文件哈希 + 构建时间 + 工作树**共同证明，见第 5 节。

## 3. 报告清单（原样入库，未二次编辑）

### 3.1 原始构建输出（2026-11-01 18:27–18:28，`impl_1/` 内自动生成）

| 文件 | 内容 | sha256 |
|---|---|---|
| [reports/original/system_wrapper_timing_summary_routed.rpt](reports/original/system_wrapper_timing_summary_routed.rpt) | 时序汇总（Routed, 2026-11-01 18:28:04） | `a62ce4db…` |
| [reports/original/system_wrapper_drc_routed.rpt](reports/original/system_wrapper_drc_routed.rpt) | DRC（Routed, 18:27:57） | `acdf48fe…` |
| [reports/original/system_wrapper_methodology_drc_routed.rpt](reports/original/system_wrapper_methodology_drc_routed.rpt) | Methodology DRC（Routed, 18:28:00） | `da299817…` |
| [reports/original/system_wrapper_utilization_placed.rpt](reports/original/system_wrapper_utilization_placed.rpt) | 利用率（Fully Placed, 18:27:17；Vivado 默认阶段报告） | `0d9d04cb…` |
| [reports/original/system_wrapper_clock_utilization_routed.rpt](reports/original/system_wrapper_clock_utilization_routed.rpt) | 时钟利用率（18:28:04） | `750119f6…` |

### 3.2 原始工程的导出报告（2026-11-01 18:28:44–18:28:46，构建完成后从打开的工程导出）

| 文件 | 内容 | sha256 |
|---|---|---|
| [reports/project-export-2026-11-01/timing.txt](reports/project-export-2026-11-01/timing.txt) | 时序汇总（Design State: **Fully Routed**） | `39bc8232…` |
| [reports/project-export-2026-11-01/drc.txt](reports/project-export-2026-11-01/drc.txt) | DRC（Fully Routed） | `8e34b446…` |
| [reports/project-export-2026-11-01/utilization.txt](reports/project-export-2026-11-01/utilization.txt) | 利用率（Design State: **Routed**） | `a29301ab…` |

### 3.3 事后从 DCP 补导出（仅此一份，标注导出时间）

| 文件 | 内容 | 导出时间 | sha256 |
|---|---|---|---|
| [reports/re-exported-from-dcp/utilization_routed-exported-2026-11-03.rpt](reports/re-exported-from-dcp/utilization_routed-exported-2026-11-03.rpt) | 利用率（Routed），`open_checkpoint` + `report_utilization -file` | **2026-11-03 15:06:15**（Vivado 2018.3） | `4cb6f6d7…` |

> 为什么补这一份：原构建自动生成的利用率报告是 *placed* 阶段（Vivado 默认），
> 补导出得到同一次构建的 *Routed* 阶段利用率，两者资源数完全一致（见第 4 节），
> 供打包时按需选用。**未做综合、未做布局布线、未生成位流。**

## 4. 关键结论（摘自上述原始报告）

### 4.1 资源占用（xc7z020clg400-1）

| 资源 | 使用 | 可用 | 占比 |
|---|---|---|---|
| Slice LUTs | 3,587 | 53,200 | 6.74 % |
| Slice Registers（FF） | 5,030 | 106,400 | 4.73 % |
| Block RAM Tile | 112 | 140 | **80.00 %** |
| DSP48E1 | 3 | 220 | 1.36 % |
| Bonded IOB | 19 | 125 | 15.20 % |

### 4.2 时序（`system_wrapper_timing_summary_routed.rpt`）

- 结论原文：**"All user specified timing constraints are met."**
- 汇总：WNS **0.735 ns**，TNS 0.000 ns（失败端点 0）
- 保持：WHS **0.032 ns**，THS 0.000 ns（失败端点 0）
- 脉宽：WPWS **3.000 ns**，TPWS 0.000 ns（失败端点 0）
- 统计端点：18,146（setup/hold），5,841（pulse width）

### 4.3 DRC（Routed，`system_wrapper_drc_routed.rpt`）

- **Violations found: 4**，全部为 **Warning**，没有 Error 级违规：
  - `DPOP-1` ×1：PREG Output pipelining（DSP 输出未加流水寄存器的建议）
  - `DPOP-2` ×3：MREG Output pipelining（DSP 乘数寄存器流水建议）
- Methodology DRC（`system_wrapper_methodology_drc_routed.rpt`）：**16 条，全部 Warning**：
  - `TIMING-4` ×1（时钟树上级主时钟重定义，本设计为自定义时钟结构，属已知）
  - `TIMING-18` ×14（缺输入/输出延迟约束，本设计为内部 I2S/GPIO 接口，属已知）
  - `TIMING-27` ×1（层级引脚上定义主时钟，同上）
- 以上均为建议级/方法论告警，**不影响位流可用性**；如打包需要"零告警"版本需另行立项，不在本页范围。

## 5. 构建来源

| 项 | 值 |
|---|---|
| 构建工作树 | `_a_work/wt-int`（git worktree，分支 `codex/integrate-abc`，当前该工作树 HEAD 为 `cd76620`） |
| Vivado 工程 | `_a_work/wt-int/build/work/audio_replay_io/audio_replay.xpr`（Project Version 7） |
| 构建根目录 | `_a_work/wt-int/build/work/audio_replay_io/`（创建于 2026-11-01 18:21） |
| 构建时间 | 2026-11-01 18:21–18:28（本机时区） |
| 工具版本 | Vivado 2018.3（Build 2405991） |

**工程引用的源文件（来自 .xpr）与其仓库对应**（构建文件 sha256 与当前 main 相同，可直接核对）：

| .xpr 引用 | 仓库路径 | sha256（构建文件，前16位） | 最近匹配提交 |
|---|---|---|---|
| `$PPRDIR/../../../src/rtl/audio_pl_replay.v` | `src/rtl/audio_pl_replay.v` | `87bc9617…` | `8e3882e`（I/O 集成：BTN0-3/LED0-3） |
| `$PPRDIR/../../../src/rtl/feedback_fir.v` | `src/rtl/feedback_fir.v` | `d57e2f53…` | `851b9d4`（宽残差过增益） |
| `$PPRDIR/../../../src/vendor/pynq_v2_4/iis_deser.vhd` | `src/vendor/pynq_v2_4/iis_deser.vhd` | `af72dd18…` | `af01b18` |
| `$PPRDIR/../../../src/vendor/pynq_v2_4/iis_ser.vhd` | `src/vendor/pynq_v2_4/iis_ser.vhd` | `0ca9f3da…` | `af01b18` |
| `$PPRDIR/../../scripts/audio_replay_io.xdc` | `build/scripts/audio_replay_io.xdc` | `1df6971e…` | `8e3882e` |

参考：项目引用的 block design 包装文件由工程内 `audio_replay.srcs` 生成（Vivado 生成物，非手写源）。

**诚实说明**：

- Vivado 不记录构建时的 git 提交；上表证明的是"构建所用源文件与仓库对应提交内容一致"，
  加上构建时间与工作树路径，可复现同一位流所需的源文件组合。
- 精确到"构建时刻工作树指向哪个提交"无法从 Vivado 输出反推；如需更严格证明，
  可对比构建目录中的源副本与历史提交（已做：全部与当前 main 相同）。

## 6. 提交前注意（给 C）

1. 报告头部含**构建主机名**（`Host: LAPTOP-…`）与本地绝对路径（`D:/OCadence_Project/…`）；
   对外提交（PDF/压缩包）前请脱敏或重排，本目录保留原件仅供核验。
2. 若打包要求"Routed 资源报告"，用 `reports/re-exported-from-dcp/` 下那份并保留导出时间；
   若接受 Vivado 默认阶段报告，用 `reports/original/system_wrapper_utilization_placed.rpt`。
3. DCP 入库副本仅作对应关系证据，**不要求**随提交包分发（体积 5 MB）。
4. 本目录所有文件哈希见 [sha256sums.txt](sha256sums.txt)。
