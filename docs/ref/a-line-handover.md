# A 线交接（2026-11-02）

给接手 A 线的下一个会话。读完这一份 + `docs/ref/ai-collaboration-habits.md` 就能开工。
**权威状态以 `docs/STATE.md` 为准，本文只写"接到什么、卡在哪、下一步怎么走"。**

## 一、当前结论（一句话）

硬件层、适配层、打包与安装**全部通过并已冻结**；**产品作为常驻服务在真板上不稳定**（三次把 PS 卡死），且**上电初始化有缺陷**导致每次重启后手感像"按键失灵"。**正式演示尚不能进行。**

## 二、已验证通过（有回执，勿重复验证）

| 项 | 证据 |
|---|---|
| 位流（含 BTN0–3 / LD0–3 / SW0–1） | `bit 322350656986d91f…`、`hwh bbe1eb4935b0931f…` |
| 硬件接口 `hw_api.create_product` | 契约方法齐全；`prepared_capture` 有硬件证据 |
| cue+input 单次调用 | `input_ready`：`cue_end_frame=21969 == valid_first_frame` |
| 6+2 标定计划 | 首档 −22.0 dBFS 通过；8 段 `bit22=0`；训练/验证源 SHA 不同 |
| install 装载核验 | `loaded_count=512`；系数哈希回读一致；校验期开环 0 增益 |
| 30 秒实时扩声 | `completed`；三类饱和 0；听感"有放大/清晰/无啸叫" |
| 急停 | `abort` 9.8–9.9 ms，`quiescent=true` |
| 物理控件（115 cm） | BTN0 长按→`start`；SW0 拨上→`sw0=1`；BTN3→`cancel` |
| C 官方入口检查 | `deployment_ready: true`、`missing: []`、`compatibility_issues: []` |
| 最终包 | `shengdi-recal-7bd365b-0b09ef6-final.zip`，sha256 `4be5083a…`；已安装到 `/opt/shengdi/current` |

## 三、状态（2026-11-02 C 回复 81b47e3 之后）

### 1. 产品服务会把 PS 卡死（最严重，**仍未解决**）

三次记录：

| # | 触发 | 当时是否并发开 PYNQ 会话 |
|---|---|---|
| 1 | 服务运行时我并发开 PYNQ 会话做长轮询 | 是（我的错，已加 `hw_guard.sh`） |
| 2 | 装包后第一次 CAL | 否 |
| 3 | 仅 `systemctl restart` | 否 |

第 3 次证明**不是并发导致**，是服务自身在硬件流程中挂住。恢复手段只有**断电**。
C 本轮（81b47e3）未处理该项，**在此之前不做正式演示**。

### 2. 上电后 AUX 为默认值 → 启动即失败：**已由 C 侧解决，A 不需要改**

- 现象（保留作背景）：codec `0x400B/0x400D` 上电为 `0x00`；`get_aux_gain_db()` 只映射 `5→0`、`7→+6`，
  `0x00` 返回 `None`；产品在 `prepare` 之前做身份校验 → `None != 0.0` → `hardware_error: aux_db`、
  服务进失败态、按键无反应（四灯全亮）。
- **C 方案（81b47e3）**：AUX 配置比较**延后到 prepare 成功回读**；代码/位流身份仍严格检查；
  未知值继续如实记录。
- **A 不要做**：不新增构造写 AUX，不加人工开机脚本。`fix_aux_boot.sh` 只作旧包的应急手段，
  新包上板后按新流程验证一次即可。
- 仍然成立的坑：`identity()['helper_sha256']` 是 `hw_api.py` 自己的 sha256，C 钉在
  `product-config.json`（1 处）与 `product-manifest.json`（3 处）。任何 `hw_api.py` 改动都必须与 C
  同轮重钉——本轮 run_dir 修复正撞上这一条。
- 证据：[aux-boot-2026-11-02](../../report/verification/audio-replay/aux-boot-2026-11-02/README.md)。

### 3. CAL 失败后必须重启服务：**已由 C 侧放开（81b47e3），尚未上板复核**

普通失败在确认静音后，**长按 BTN0 ≥1 秒**即可新建 scene 重来；身份混搭、无法确认停声仍锁定。
现场含义：失败后不用再重启服务，但"确认静音"这一步要等灯稳定再按。

### 4. 时序：**quiet 已改 4 s，speech 保留 2.5 s**

`quiet_seconds=4`（原 2）、`speech_seconds=2.5` 不变——C 的理由是当前源 RAM 装不下 4 秒计划。
现场仍只有**一次提示音**，讲话窗就是 LD1 亮起之后那 2.5 秒，必须一直说到 LD1 灭。

### 5. 长时扩声做不到（产品语义，非缺陷）

单次 `run_seconds=30`；硬件上限 `MAX_RUN_FRAMES=3,000,000`（61.44 s）；C 的契约禁止拼段续播。
**若要长时间扩声**：RTL 常数 + 驱动循环条件 + C 的状态机语义，一天量级，需 C 同意。

### 6. 本轮 A 侧唯一代码改动：run_dir 一行（已并入，待统一重冻）

`ProductHardwareV2.perform` 分派前加 `self.run_dir = request.get('run_dir') or self.run_dir`。
旧代码只有 `_run_plan` 赋值，`input`+`cue`（自动重说）、`install`、`run` 都沿用上一次目录，
第二次写同一个 NPZ 时独占创建失败。源码与 `v3-io` 副本已同步，`manifest.json` 与
`product-adapter.json` 已改到新哈希 `8799f40b…`。证据：
[run-dir-fix-2026-11-02](../../report/verification/audio-replay/run-dir-fix-2026-11-02/README.md)。

### 7. 新包已到（`io150`），离线核验通过，等上板

`shengdi-recal-8799f40b-0b09ef6-io150-final.zip`，sha256
`a91db61e40756887beee7bec88903e8f991868c81245e93017857d28b0f758b5`。37 个受管文件哈希全对上，
6 处 pin 全指向 `8799f40b…`；A/B 字节未改。C 的两处修复（AUX 延后比较、普通失败可重按 CAL）
已在包内代码核对到了。**下一步就是装 + 上板三项复核**：断电重启后不跑 `fix_aux_boot.sh` 能否进待标定、
失败后 BTN0 重按能否新建 scene、两次重说是否落到两个目录。板子不可达时这一步做不了。
证据：[package-io150-2026-11-02](../../report/verification/audio-replay/package-io150-2026-11-02/README.md)。

## 四、现场操作要点（踩过的坑）

1. **`shengdi-product.service` 运行时禁止另开 PYNQ 会话**（会抢设备卡死 PS）。判据见 `board/audio_replay/hw_guard.sh`。只读 `status.json` 是安全的（需 sudo）。
2. **CAL 节奏**：LD0 闪烁 → **提示音一响就立刻说话**（只有一次提示音，不要等第二次）→ 说满 2.5 秒以上 → 之后白噪采集约 30–40 秒**保持安静** → 成功 LD3 亮。
3. **采集窗只保留最后 16384 帧（0.34 秒）**，所以必须说到最后一刻。
4. 每次采集前约 1 秒重下位流，**静音是正常的**。
5. 板子卡死无 SSH 时：**断电 10 秒**（SRST 不够）。

## 五、关键文件与路径

| 用途 | 全路径 |
|---|---|
| 硬件接口 | `D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-int\board\audio_replay\hw_api.py` |
| 驱动（含 `before_start` / `restore_stock`） | `…\board\audio_replay\v3-io\replay_trial_repair.py` |
| 发布包（9 件） | `…\board\audio_replay\v3-io\` + `manifest.json` |
| 现场速查 | `…\docs\ref\board-quickstart.md` |
| 接口清单 | `…\docs\contracts\product-adapter.json`、`physical-controls.json` |
| AUX 上电修复 | `…\board\audio_replay\fix_aux_boot.sh` |
| 并发保护 | `…\board\audio_replay\hw_guard.sh` |
| C 的产品包（本地解压） | `…\_a_work\final_pkg\`（zip 在仓库根目录） |
| 板上安装位置 | `/opt/shengdi/current`；状态 `/home/xilinx/.local/state/shengdi/status.json` |

## 六、常用命令

```bash
# 上板（需要密码环境变量）
$env:SHENGDI_SSH_PASSWORD='xilinx'
python board_run.py <本地脚本路径> --sudo

# 恢复上电后的 AUX 并重启服务
bash board/audio_replay/fix_aux_boot.sh

# 读产品状态（只读，安全）
echo xilinx | sudo -S cat /home/xilinx/.local/state/shengdi/status.json

# C 的回包命令（现场流程走完后执行）
sudo bash /opt/shengdi/current/recal_entry.sh \
  --state-dir /home/xilinx/.local/state/shengdi \
  --export /home/xilinx/shengdi-install/recal-product-return-7bd365b.zip
```

## 七、下一步建议顺序

1. **等 C 回复**上电初始化顺序与 CAL 可重试两项；
2. 拿到 C 方案后，A 侧一次性改完（`to_db` + 构造写 AUX），**只冻结一次**；
3. 稳定性若能确认是产品侧问题，优先修，**在修好前不做正式演示**；
4. 稳定后：一次真人窗口走完 CAL → 扩声 → SW0 对照 → STOP → 导出回包。

## 八、不要重复做的事

- 不要再验证已完成项（见第二节）；
- 不要为了让流程走通而放宽阈值、改 B 的判据、或把静音/低增益当成功；
- 不要私自替换冻结包内文件（破坏包身份）；
- 不要在服务运行时开第二个 PYNQ 会话。
