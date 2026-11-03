# A 线交接（2026-11-03）

给接手 A 线的下一个会话。读完这一份 + [ai-collaboration-habits.md](ai-collaboration-habits.md) 就能开工。
**权威状态以 [docs/STATE.md](../STATE.md) 为准，本文只写"接到什么、卡在哪、下一步怎么走"。**

本线是**唯一操板线**：板卡、驱动、现场实验都归 A；不要跨线改 B 的算法核与 C 的产品入口/判据。

## 一、当前结论（一句话）

**+1 dB 演示链路已打通并可用**（真人 60 秒扩声跑满、BTN2 保护恢复已验收）；
**批量采集驱动已实现但未上板验收**（等 C 重新钉包）；**+3 dB 仍不可用**（高频相位问题，队长/B 复算中）；
冻结位流的资源/时序/DRC 报告与构建来源**已交 C**。

## 二、已验证通过（有回执，勿重复验证）

| 项 | 证据 |
|---|---|
| C 的 BTN2 恢复包（上板中） | ZIP `b167d0b5…`、manifest `beb36216d26b6cbb`、release `/opt/shengdi/releases/beb36216d26b6cbb`；[验收记录](../../report/verification/recal-product-v1/resume3-acceptance.json) |
| 同一包 3 个单测 | 板上 Linux 环境 `Ran 3 tests in 7.719s, OK`（正常恢复 / 模型哈希不符拒绝 / 第 4 次拒绝） |
| +1 dB 真人 60 秒扩声 | 场景 `e964f858847a409c9d3df1b9f6d98842`：`completed_frames=2,929,687`（60.00 s）、`stop=completed`、零饱和、无麦克风满幅；视频素材①用这组数据 |
| BTN2 免标定恢复 | `protected → BTN2 → ready`，`resumed_from=protected`，`resume_count` 1→3；第 4 次被拒（保持 protected）；恢复后再扩声→正常停止→`ended`，旧包"结束后 failed"的 runtime 白名单问题已修 |
| 冻结位流资源/时序/DRC | [frozen-bitstream-32235065](../../report/verification/recal-product-v1/frozen-bitstream-32235065/build-provenance.md)：bit `322350656986d91f…`，Vivado 2018.3，时序全过（WNS 0.735/WHS 0.032），BRAM 112/140=80%、LUT 3587、FF 5030、DSP 3，DRC 4 条均 Warning |
| 上板包源码来源 | [resume3-source-map.md](../../report/verification/recal-product-v1/resume3-source-map.md)：代码来自 4 个历史提交，行为参数只在包内 `product-config.json` |
| 工作区与技能包整理 | 根 `README.md` 目录对照（指南 3.3.5.4）；`skill/README.md` + `skill/CONTRIBUTING.md`（指南 3.3.5.2）；指南摘录 [competition-guide-requirements.md](competition-guide-requirements.md) |
| 视频素材①数据 | 上述 60 秒运行记录（`RUN FINISHED`：completed / 60.00 s / 尾窗电平） |

## 三、未完成 / 卡在哪

### 1. 批量采集驱动：已实现，等 C 重钉后 A 上板验收（**最优先的待办**）

- 契约：`docs/contracts/recal-product-v1.md` 的「v3：一次 arm 的 capture_plan 批量入口」；
- A 已实现：`board/audio_replay/v3-io/replay_trial_repair.py` 的 `CAPTURE_PLAN_API="recal-capture-plan-v1"` 与
  `replay_capture_plan(...)`，提交 `c17ce77f8b7522b484a4be1d23137e1bf4bd91ea`，文件 sha `b65a8606…`；
- 现状：**未上板**（板卡期间被占用）；C 已接好调用层（main `433bf95`），下一步 **C 统一重钉整包**；
- 验收要做：一次 CAL 中 4 训练 + 2 验证的**实测墙钟**、逐段 NPZ/status、逐段 `bit_exact`、
  `read_proof` 与 `ring_overrun`；见 [capture-plan-driver.json](../../report/verification/recal-product-v1/capture-plan-driver.json)；
- 风险：Python MMIO 逐帧读环可能跟不上音频速率（运行 1.343 s 需读 65536 帧）；跟不上要如实返回
  `ring_overrun`，**不许用重复尾窗或二次下载掩盖**；优化手段只在驱动内部（去命令回读/调块大小），不改 RTL。

### 2. 视频素材

- ① 60 秒运行记录：数据已合格；若录屏丢失，需**先重新标定**（服务重启会清掉 `ended`）再录；
- ② Vivado 资源报告：用 `materials/video/a06_open_utilization.bat` 打开**实装位流的 routed DCP**，
  已在 bat 里加 `QT_SCALE_FACTOR=1.5` 解决 2018.3 无法滚轮放大的问题；
- 拍摄要求与说明模板：`materials/video/a06_recording_notes.md`；
- 纪律：原片不压缩/不转码、文件名 a01–a06、画面脱敏（用户名/IP/学校/私人路径）、微信勾"原视频"。

### 3. +3 dB：不可用，等结论（不要自己改 RTL/阈值）

- 实测：+3.0 dB 在 0.06–0.11 s 内输出饱和，主峰 **8353 Hz**；+1.5 dB 在 16 秒、+2.0 dB 在 0.15 秒
  先在 **4.13–4.15 kHz** 破；
- A 的解释曾被推进到"8.35 kHz 复残差 0.815、+3 dB 环路 1.15"的程度，但 **B/队长判定复频响表不自洽**，
  改为"待核"；**A 不据此改 RTL、不改判据、不自行造新算法**；
- 当前唯一可用工作点：**+1.0 dB（q12 4596）**。

### 4. 产品/服务稳定性（历史问题，继续观察）

- 仍偶发"进程占满 CPU、状态文件不更新"的卡死；恢复方式：先抓现场（`stuck_check.sh`：process/wchan/status），
  再 `systemctl restart shengdi-product.service`；
- **重启会清掉 `ended` 状态**，之后要重新 CAL 才能扩声；
- 若重启后仍异常，断电 10 秒（SRST 不够）。

## 四、板卡与工具

| 用途 | 位置/命令 |
|---|---|
| 上板执行脚本 | `_a_work\board_run2.py <本地脚本> [--sudo] [--timeout N]`（脚本先上传再跑） |
| 上传文件 | `_a_work\board_put.py <远端目录> <本地文件>` |
| 密码 | `$env:SHENGDI_SSH_PASSWORD='xilinx'` |
| 只读状态 | 板上 `/home/xilinx/.local/state/shengdi/status.json`（需 sudo） |
| 安装包 | `bash <解压目录>/product-install.sh`（`--check` 先跑） |
| 板上 Python | `/usr/local/share/pynq-venv/bin/python`（有 numpy）；需要 root 读状态/目录 |
| 产品服务 | `systemctl restart shengdi-product.service` |

**现场纪律**：产品服务运行时不要再开 PYNQ 会话（抢设备会卡死 PS）；只读 `status.json` 安全。

## 五、关键路径

| 内容 | 路径 |
|---|---|
| 上板包源码来源 | `report/verification/recal-product-v1/resume3-source-map.md` / `.json` |
| 冻结位流报告与来源 | `report/verification/recal-product-v1/frozen-bitstream-32235065/` |
| BTN2 恢复验收 | `report/verification/recal-product-v1/resume3-acceptance.json` |
| 批量采集驱动状态 | `report/verification/recal-product-v1/capture-plan-driver.json` |
| 视频材料与说明 | `materials/video/` |
| 指南规范摘录 | `docs/ref/competition-guide-requirements.md` |
| 技能包 | `skill/README.md`、`skill/CONTRIBUTING.md` |
| 协作习惯 | `docs/ref/ai-collaboration-habits.md` |

## 六、下一步建议顺序

1. **等 C 重钉批量采集包** → A 装包上板，一次 CAL 回报 4 训练/2 验证实测耗时与逐段校验结果；
2. 视频 ①/② 录制收尾（用户操作，A 配合确认板卡状态）；
3. +3 dB：等队长/B 的高频复算结论；若交付改善后的模型，A 用同一套增益阶梯
   （+1.5 / +2.0）复测，通过后请 C 出对应增益包；
4. 其他会话向 `skill/` 贡献技能（规范见 `skill/CONTRIBUTING.md`），A 审阅格式与证据。

## 七、不要重复做的事

- 不要重测第二节已通过的项目（除非有代码/包变化）；
- 不要用低增益、限幅、静音当"抑制成功"；
- 不要为了流程通过而放宽阈值、改 B 的判据或 C 的配置白名单；
- 不要私自替换冻结包内文件（破坏包身份）；
- 不要在服务运行时开第二个 PYNQ 会话；
- 不要把"已保存记录回放"包装成现场实测（录像素材必须真实）。
