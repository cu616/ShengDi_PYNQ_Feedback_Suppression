---
name: pynq-overlay-io
description: 在 PYNQ-Z2/Zynq 板上安全加载 overlay、用 MMIO 与自定义 IP 交互、装载大批源数据并校验的通用做法；与具体题目无关，换板卡/换工程仍可复用。
---

# PYNQ Overlay、MMIO 与自定义 IP 交互

## 适用场景

- 在 PYNQ（PYNQ-Z2 实测，其他 Zynq-7000 PYNQ 镜像同理）上用 Python 控制自建 RTL IP。
- 需要通过 AXI GPIO / AXI-Lite 寄存器与 PL 交互：写控制字、读状态、批量灌数据、读回结果。
- 一次实验里要反复重载 overlay、或同一进程里多次读写同一 IP。

前置：板卡镜像已装 PYNQ；已有配对的 `.bit` + `.hwh`；Python 能 import `pynq`。

## 使用方法

### 1. 加载 overlay 只有一种正确姿势：先绑定 `.hwh`，再取 `ip_dict` 地址

```python
from pynq import Overlay
ov = Overlay('/abs/path/design.bit', download=True)   # 同目录必须有同名 .hwh
ctrl = ov.ip_dict['audio_control']['phys_addr']        # 地址来自 .hwh，不要硬编码
```

- 任何“按旧地址写”的代码在重载或换工程后都会错位；地址一律运行时从 `ip_dict` 取。
- 校验 bit 与 hwh 是同一对：对两个文件算 sha256 并与工程记录比对，不匹配就拒绝运行。

### 2. 一个进程独占 PL；重载前必须让旧驱动“停手”

- 现象：一边有线程在循环 MMIO，一边 `Overlay(download=True)`，会把 PS/AXI 卡死，
  只能断电恢复。
- 做法：维护一个“MMIO 持有中”标志；重载前先停线程、置标志、等线程退出，再下载 bitstream。
- 现象：服务/进程已占用设备时，另一个进程加载 overlay 会报 `No Devices Found`；
  这是设备被占用，不是板卡坏。

### 3. 寄存器交互三原则：写后回读、先停再读计数、状态字分层解释

1. **写后回读**：配置类写入（增益、模式、使能）完成后立刻读回，把回读值写进证据；
   不要拿“我请求的值”当实际值。
2. **先停再读**：运行中的计数器/采样缓冲会继续变化；先撤销使能（写 0）、等一个周期，
   再读统计与缓冲区，否则拿到的是撕裂数据。
3. **状态字分层**：一个 32 位状态字里同时有“完成位、保护位、计数低位”，
   务必按位域分别解释；把“保护标志”和“我自己设的目标值”混着用会误判故障。

### 4. 批量灌数据（AXI GPIO 握手式 loader）的通用模式

- 典型 RTL 是“写数据 + 翻转一个标志位”表示一次有效写入；每次写都要**翻转**，
  不翻转会被下游当成重复数据。
- 灌完必须回读 loader 状态字：**已装载数量 == 请求数量**、无错误位、已就绪位为 1，
  三项不全就不要 arm。
- 大批量（十万级）逐样本写会慢：提前估算耗时（每次 MMIO 约 1–2 µs，十万次约 0.1–0.2 s），
  必要时在板端用批量循环 + 预分配数组。

### 5. 批量取数据（环形缓冲 + 地址计数器）

- 若 RTL 用“环形缓冲 + 完成计数”，PS 侧在运行中按“已完成的全局帧号”换算环形槽位
  `slot = frame_index % depth`，**边跑边取**；只在结束后读最后一窗会丢数据。
- 每次读取记录 `{起始帧, 结束帧, 读取前计数, 读取后计数}`，作为“没有读到被覆盖数据”的证明：
  要求 `读取后计数 - 起始帧 <= 环形深度`。
- 读回后做一次“位精确回放校验”：用同一组输入与系数重算，逐采样比对。

## 已验证效果

- 在 PYNQ-Z2（xc7z020clg400-1）+ Vivado 2018.3 构建的自定义音频 IP 上，按上述做法完成：
  - 单次 overlay 下载约 6–7 s（重载成本的主要部分）；
  - 十万级源样本装载 + 回读核对；16384 帧环形缓冲边跑边取；
  - 驱动 `bit/hwh` 哈希配对校验、逐采样位精确回放校验；
  - 服务占用设备时第二个进程加载 overlay 报 `No Devices Found`（已复现并记录）。
- 证据位置：`report/verification/` 下的驱动与位流记录；`board/audio_replay/v3/` 内的
  `manifest.json`、`replay_tools.py`、`test_verify_replay_v3.py`。

## 失效条件

- 本页来自 PYNQ-Z2 + Vivado 2018.3 的实测；其他 PYNQ 版本、MPSoC 器件、Vitis 流程未验证。
- “边跑边取”只有在 RTL 暴露“已完成计数”且环形缓冲足够大时成立；
  若 RTL 只有单次捕获、没有计数器，必须改 RTL，不能用本页办法硬凑。
- DMA 搬运与缓存一致性：**本队未用 DMA，本页不覆盖**。若你的设计用 DMA，
  需另行处理 cache flush/invalidate 与地址对齐（候选做法，未在本仓库验证）。
- 时序/资源结论不能由本页推断；资源与频率以 Vivado 实现报告为准。

## 来源

- 从本项目多次真实故障总结：PS 在 bitstream 重载期间被 MMIO 读卡死、进程占用设备导致
  `No Devices Found`、loader 回读不一致、运行结束后读环形缓冲只剩尾窗等
  （见 `report/verification/` 与 `docs/log/progress.md` 中的对应记录）。
- 相关项目内证据入口：`board/audio_replay/v3/replay_tools.py`、`board/audio_replay/v3-io/` 驱动、
  `report/verification/audio-replay/`。
