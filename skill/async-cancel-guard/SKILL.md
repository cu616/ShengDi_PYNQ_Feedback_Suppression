---
name: async-cancel-guard
description: 排查异步设备或计算任务取消后仍发布旧结果、安装候选或误清新任务的问题。提供代次隔离和失败回放清单；软件通过不代表底层设备已停机。
---

# 异步取消与迟到结果隔离

类型：踩坑清单。

## 适用场景

- 线程或子进程执行采集、计算、安装，界面仍需响应停止；用户可能在旧任务返回前取消或换场景。
- 有明确的任务身份、取消入口、结果接收点及生效入口，可以替换设备访问与计算返回做离线验证。
- 适合检查“停止后突然就绪”“旧结果清掉新任务”“新标定失败却继续用旧模型”；不替代驱动急停实现。

## 使用方法

1. 找出提交任务、停止、接收回包、发布结果四个位置。每个任务绑定代次 `epoch`、场景 `scene_id`、请求 `request_id`；工作线程保存提交时的代次和取消对象。新任务创建新的取消对象，不清除旧任务持有的 Event。
2. 停止时先置位取消并推进代次，让旧结果失去发布资格，再调用已有设备停止接口。把“已请求取消”“设备确认静止”“旧调用已返回”分别记录；前两项不能自动推导第三项。旧硬件调用没返回时，不并发提交下一次硬件任务；可记录待重试请求，等收尾后再启动。
3. 接收结果时，先比较代次；过期结果不能进入业务消费器，也不能清除当前 `pending`。代次有效后再校验场景/请求身份。停止失败要按产品现有规则锁住启动，不能仅靠忽略迟到回包证明设备不会重新动作。
4. 新场景开始即撤销旧模型的运行资格，旧文件可归档。候选通过验证、安装回读一致后，才提交本场景生效指针；哈希不符或指针写入失败，保持候选不可运行。只对新场景/未完成候选适用；同场景正常停止及已授权的保护恢复仍遵循产品原有规则。
5. 回放下表的取消与失败分支；保留原始结果，检查最终状态、生效指针和是否实际调用安装/运行，而非只检查日志出现“取消”。

| 注入/观察 | 预期结果 | 本仓库对应测试（位于下述测试文件） |
|---|---|---|
| 硬件任务各阶段取消，随后让调用收尾 | 保持静音，未完成候选不可运行，不能变回就绪 | `test_cancellation_in_every_hardware_phase_cannot_promote_late_result` |
| 计算阶段停止，随后检查回包消费 | 保持静音，候选无运行资格 | `test_calculation_phase_cancellation_rejects_late_results` |
| 安装返回错误哈希或生效指针写入异常 | 不留下可运行候选，不调用扩声 | `test_install_mismatch_or_atomic_pointer_failure_leaves_no_active_model` |
| 已有模型后换场景，新标定失败 | 旧文件保留，旧模型不能在新场景启动 | `test_recalibration_invalidates_old_scene_even_if_new_calibration_fails` |

在本仓库根目录执行（Python 3.12、NumPy；设备/数值判断均为模拟实现）：

```text
python -X utf8 -m unittest discover -s sim/feedback -p test_recal_product.py -k cancellation -v
python -X utf8 -m unittest discover -s sim/feedback -p test_recal_product.py -k install_mismatch -v
python -X utf8 -m unittest discover -s sim/feedback -p test_recal_product.py -k recalibration_invalidates -v
```

预期依次通过 2、1、1 个顶层用例，退出码均为 0。失败时看对应断言中的 `state/outcome`、模型指针 `eligible`、模拟硬件调用列表；不要通过放宽断言或允许旧场景启动来消除失败。换项目时映射这些可观察量与适配器，不能直接套用本仓库状态名。

## 已验证效果

- 2026-11-03 在 Windows / Python 3.12 的仓库基线 `4df8c36b2404742974a3cccdd76d0df1bf9c5cce` 上复跑上述 4 项，全部通过；硬件取消用例含 7 个阶段，计算取消含 3 个阶段，安装失败含哈希/写指针两种注入。未访问板卡。
- 可复跑定义：[test_recal_product.py](../../sim/feedback/test_recal_product.py)，该文件版本提交 `2384fb2c2e2178fd601d195369ad480fb9e4bff8`。历史逐项输出：[guard150-0cab-software.json](../../report/verification/recal-product-v1/guard150-0cab-software.json)，提交 `ffe8d10a3f762e4c033c0bb462bfd7185b1e3ac5`；其中包含上述四项通过记录，明确 `board_operations=0`。
- 已验证范围是模拟返回与失败注入下的状态/发布资格，不是任意第三方驱动强制终止、声学抑制效果或真实设备停止时延。

## 失效条件

- 仅设置 Event，底层不检查或初始化后仍能重新启动设备：代次隔离只能阻止旧结果被软件接受，不能停止硬件。需要驱动在真正启动前再查取消，并给出实际静止回执。
- 多进程共写生效指针、掉电持久性、跨机器时钟与请求身份冲突未由上述用例覆盖。这些扩展为**候选**，分别缺并发写入测试、掉电恢复实测及跨节点身份验证，不直接宣称可复用保证。
- 更换状态机、队列处理顺序或安装协议后，须重跑对应分支；归档文件存在本身不代表仍有运行资格。
- 正常停止和保护后恢复的允许条件由具体产品确定；本清单不授予新增运行、重试、现场操作或对外发布权限。

## 来源

- 硬件/计算取消后结果收尾的观察：上述测试文件中的两个 `cancellation` 用例；来源为软件阻塞与取消注入，未冒称真实板卡故障。
- 安装失败和旧场景误用的反例：同一测试文件中的 `install_mismatch...` 与 `recalibration_invalidates...`；分别注入安装回读/磁盘失败，以及新场景采集失败，检验失败出口。
- 对应实现：[recal_product.py](../../board/audio_replay/recal_product.py)，提交 `433bf95dc270214b99e1838724caaf36ad233754` 的 `_submit`、`stop/fail`、`tick`、`ModelStore`：保存提交代次，停止时推进代次，在消费回包和清 pending 前过滤旧代次，分开维护硬件调用收尾与模型资格。复用的是这些约束，不复制本项目增益、模型或音频数据。
