# PS 卡死根因与三处 A 侧修复（2026-11-02，真板）

**验证层次：上板（真板复现 + 真板验证）。所有改动只在测试副本 `/home/xilinx/shengdi-test`，
`/opt/shengdi/current` 保持冻结包原样。**

## 一句话

四次把 PS 卡死的根因是：**重下位流期间主循环还在读 MMIO**。单独重下位流安全、单独读 MMIO 安全，
两者重叠必死。加一道闸后，同样的压力 8/8 通过。同一轮里 CAL 首次完整走通（训练 6 + 验证 2 +
拟合 70 s + 装模型 → ready）。

## 三组对照（决定性）

同一段脚本、同一台板、同一模型，只改一个自变量：

| 组 | 重下位流 | 并发访问 | 结果 |
|---|---|---|---|
| 对照 | 有 | 无 | **8/8 成功**，57.5 s，`bit_exact=True`，无异常 |
| **A 组** | 有 | 只读 MMIO，20 ms | **卡死**（SSH/TCP 全断，只能断电） |
| 复用组 | 无（`reuse_overlay=True`） | 无 | 第 2 段 `source load incomplete: 52043e80` |

复用组说明：现有设计**依赖重下位流复位 PL**，把 `reuse_overlay` 翻成 `True` 会破坏 source
装载握手（RTL 的 `source_error` 只在复位时清）。所以"复用 overlay"这条改法作废。

## MMIO 闸的验证

闸：`Overlay()` 构造期间把 `_MM_HOLD` 加一，`_status_word()`/`_control_word()` 在此期间返回缓存值。

同一段"必卡"压力下：

```
CAP 00..07 全部 frames=16384 stop=completed
raw=0x00008001  clip22=0  fault18=0
reads=1904  held=361        # 8 段采集中被闸挡住 361 次 ≈ 每次下载 0.9 s
ISO_GUARD_RESULT ok=8/8 total=58.0s errs=[]
```

代价：闸门那约 0.9 秒内 `poll()` 读不到按键，**BTN3 急停最坏晚约 0.9 s**（现在 9.8 ms）。

## 完整 CAL 首次走通

```
preparing → input_capture → speaking → quiet
→ capturing ×6 → fitting（70 s，valid_pass：L1 2.181、峰位 121 = 实测延迟 121）
→ validating ×2 → installing → ready
```

期间 8 次重下位流、约 100 秒硬件活动，**PS 未卡死**。

同一轮还暴露并绕过两个非卡死问题：

1. **拟合超时**：交付包 `compute_timeout_seconds=30`，实测拟合需 70 s。测试副本改 150 后通过。
   （C 已把 `io_timeout_seconds` 改 150，compute 未改。）
2. **身份校验误报 `aux_raw_left`**：驱动每次调用先 `mute_codec()` 重置 codec，主循环这期间读
   AUX 会读到 `0x00`。修法：驱动调用期间 `identity()` 用上一次读到的 AUX 值。

## 未解决：产品侧 START 误判保护

按 BTN1（START）后 0.4–4.8 秒进 `protected`，**且没有 `running` 事件**；两次里一次留下
`run_00.status.json`（`frames=0`、`capture_status=0`），另一次连状态文件都没有。

**A 侧在产品外复现不出来**：同样的 `_run_v2`、同样的增益 1631、同样的装好模型 + 同样的 20 ms
`poll()` 轮询：

```
RUN reply ok=True status=completed frames=16384 wall=22.8s
polls=127  protected_events=0
```

所以问题在 C 的 `tick()`：START 那一刻 `if poll.get('protected'): raise` 先于 start 事件执行，
读到了什么（`_protect_baseline` 的刷新时机 / `ready` 时 PL 的粘滞位）。**归 C 判。**

## 三处 A 侧改动（测试副本，未进冻结包）

补丁脚本见 [full_cal_guard3.sh](full_cal_guard3.sh)（六处锚点，逐处断言唯一）。测试副本
`hw_api.py` 哈希 `7ae449af37f270503a8448892ee0dba03d790b54fb718c8b852e8de68843ee08`。

1. `_MM_HOLD` + 受保护的 `_status_word()`/`_control_word()`（卡死修复，已验证）；
2. `_op_hold` + `identity()` 用缓存 AUX（误报修复，未单独隔离验证）；
3. `_run_v2` 去掉预 arm（`arm=True` 在驱动加载新系数之前就举起来，RTL 的
   `if (!fresh …) fault<=1` 会立刻置故障位）。**已验证无副作用，但不是 START 误判的充分解释。**

## 复现

脚本都在本目录，用 `board_run2.py`（带超时）上传执行；`source /etc/profile.d/xrt_setup.sh`
是必须的，否则 PYNQ 报 `No Devices Found`。

| 脚本 | 用途 |
|---|---|
| `redownload_test.sh` | 对照组：8 段采集，无并发 |
| `iso_mmio.sh` | A 组：8 段 + 只读 MMIO 20 ms（**会卡死**） |
| `iso_guard.sh` | 打闸后的同一压力 |
| `full_cal_guard3.sh` | 三处修复 + compute 150，拉起完整产品 |
| `direct_run.sh` | 绕过产品直接跑 30 s 扩声（已验证 completed） |
| `start_repro.sh` | 产品外复现 START（结果：不触发保护） |

## 边界

- 全部在 `/home/xilinx/shengdi-test` 测试副本上做，冻结包与 `/opt/shengdi/current` 未改；
  因此这些结果**不是**对交付包的验收，只是根因与修法的证据。
- 三处改动进冻结包需要 C 同时重钉 `helper_sha256`（测试副本里已按新哈希重述 manifest）。
- `BTN3` 急停延迟代价（约 0.9 s）尚未在真板上量过。

## 2026-11-02 追加：按 C 的 guard150 要求补两项（已进根目录、v3-io 与清单）

C 独立复现出**基线漏报**：空闲时 `capture_status` 带 `fault`(bit18)，poll 把它记进
`_protect_baseline`；运行中同一 fault 再起，poll 因旧基线仍报 `protected=false`，真故障被吞掉
（证据 `report/verification/recal-product-v1/guard150-baseline-probe.json`）。

补的两项：

1. **在真正 arm 的时刻重建基线**：新增 `_arm_baseline(cancel_event)` 作为驱动的 `before_start`
   回调——先按原语义拒绝已取消的请求（返回 False、基线不动），通过后
   `_protect_baseline = self._status_word()`。五处 `before_start` 全部改走它。
2. **`poll()` 区分实读与缓存**：新增 `capture_status`、`control_word`、`mmio_held`、
   `protect_baseline` 四个字段；`mmio_held=true` 表示该次值来自位流重载期间的缓存。

软件序列复核（[probe_baseline.py](probe_baseline.py)，无板、无 pynq，MMIO 用两个寄存器替身）：

```
without rebaseline: idle protected=true -> new_fault_in_run protected=false   <- C 报的漏报
with    rebaseline: arm_baseline 返回 true、baseline 262144->0，
                    new_fault_in_run protected=true、fault=1
cancel_still_refuses: true        <- 取消语义仍在
VERDICT PASS
```

输出留存：[probe_baseline-output.json](probe_baseline-output.json)。改后 `hw_api.py`
（LF，59277 字节）哈希
`0cabfc17cca1fb0e2629e1b382c119b48f00e1fe9b2a437a0302ed04e06ed3c5`，已同步 `v3-io` 副本、
`v3-io/manifest.json` 与 `docs/contracts/product-adapter.json`。

