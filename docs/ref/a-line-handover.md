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

## 三、未解决（按严重度）

### 1. 产品服务会把 PS 卡死（最严重）

三次记录：

| # | 触发 | 当时是否并发开 PYNQ 会话 |
|---|---|---|
| 1 | 服务运行时我并发开 PYNQ 会话做长轮询 | 是（我的错，已加 `hw_guard.sh`） |
| 2 | 装包后第一次 CAL | 否 |
| 3 | 仅 `systemctl restart` | 否 |

第 3 次证明**不是并发导致**，是服务自身在硬件流程中挂住。恢复手段只有**断电**。
已报 C，等其处理。

### 2. 上电后 AUX 寄存器为默认值 → 启动即失败

- codec `0x400B/0x400D` 上电为 `0x00`；
- `hw_api.Board.get_aux_gain_db()` 只映射 `5→0 dB`、`7→+6 dB`，`0x00` 返回 `None`；
- 产品在 `prepare` 之前做身份校验 → `None != 0.0` → `hardware_error: aux_db` → 服务进失败态、**按键无反应**（四灯全亮）。

**临时绕过**：`bash board/audio_replay/fix_aux_boot.sh`（停服务→写 `0x05`→启服务）。**每次断电都要跑。**

**根治（待做，需与 C 商定后一次改完）**：
- A 侧：`to_db()` 如实处理未知值；`create_product` 构造时先写一次 AUX；
- C 侧：首次身份校验前先 `set_aux_gain_db`，或豁免未初始化状态。

### 3. CAL 失败后必须重启服务才能重试

失败态下按 BTN0 无反应，现场像"按键坏了"。已请 C 允许失败后直接重按 CAL。

### 4. 时序偏紧

`quiet_seconds=2`、`speech_seconds=2.5`、`input_mode="embedded"`（**只有一次提示音**，讲话窗就是提示音之后那 2.5 秒）。现场人普遍反应不过来。已建议 C 调到 4/4。

### 5. 长时扩声做不到（产品语义，非缺陷）

单次 `run_seconds=30`；硬件上限 `MAX_RUN_FRAMES=3,000,000`（61.44 s）；C 的契约禁止拼段续播。
**若要长时间扩声**：RTL 常数 + 驱动循环条件 + C 的状态机语义，一天量级，需 C 同意。

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
