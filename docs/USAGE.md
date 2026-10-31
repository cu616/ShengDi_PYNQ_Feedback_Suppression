# 使用说明：怎么跑起来

面向"拿到板子和这份仓库，想把系统跑起来"的人。技术状态与数字口径不在这里，一律看
[STATE](STATE.md)；本文件只讲**怎么做**。

---

## 0. 三分钟上手

```
① 板子上电联网（默认 xilinx@192.168.2.99，密码 xilinx）
② 把 board/audio_replay/v3-sw/ 整个目录上传到板卡的
   /home/xilinx/jupyter_notebooks/base/audio/audio_switch/
③ 先自检：verify_switch.sh         → 期望 completed、bit22=0、打印包身份 10/10
④ 再演示：拨 SW0 或用 live_toggle_v3.sh
```

> 只认一条铁律：**位流、驱动、hwh 必须同组**。三个包各自带 manifest，混装会被驱动当场拒绝（见 §6）。

---

## 1. 先选版本

| 包（板卡目录 / 仓库路径） | 位流 | 用途 | 能不能用于演示 |
|---|---|---|---|
| `audio_switch` / `board/audio_replay/v3-sw/` | `2113a454…` | **v3 + 物理开关**，含 SW0/SW1 | ✅ 已上板验证 |
| `audio_wide` / `board/audio_replay/v3/` | `48e38f78…` | v3 冻结基线，无物理开关 | ✅ 已上板验证 |
| `audio_live`（仅板上） | `61bb71aa…`（v2） | 回退用 | 只在 v3 出问题时 |

三个包**不能混装**：驱动里钉了自己的 bit/hwh 哈希，装错会直接报错而不是将就运行。

---

## 2. 环境

| 项 | 值 |
|---|---|
| 板卡 | PYNQ-Z2（Zynq-7020），PYNQ v2.4 镜像 |
| 板卡登录 | `ssh xilinx@192.168.2.99`，密码 `xilinx` |
| Python（板上） | `/usr/local/share/pynq-venv/bin/python`（带 pynq/numpy） |
| 板卡部署目录 | `/home/xilinx/jupyter_notebooks/base/audio/<包名>/` |
| 电脑侧工具 | Python 3（带 numpy）；重建位流用 Vivado 2018.3 |

板卡用 SSH 控制即可，不需要开 Jupyter。**注意**：板卡可能不回 ping（ICMP 被挡），
能连上 22 端口就是活的，不要因为 ping 失败以为板子掉线。

---

## 3. 部署一个包

把包内**这 11 个文件**放进板卡的一个新目录（不要覆盖正在用的目录）：

```
audio_replay.bit  audio_replay.hwh  manifest.json
replay_trial.py  replay_tools.py  closed_tools.py  residual_tools.py  tone_round_guard.py
test_runtime_stop.py  test_verify_replay_v3.py  test_tone_round_guard.py
```

外加模型 `rewired_512_20261026.json`（从 `models/room_v1/` 取，或从旧包目录拷）。

查看包身份：

```bash
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch
sha256sum audio_replay.bit    # 与 manifest.json 的 hashes 对照
```

---

## 4. 日常操作（按用途选一个）

所有现场脚本都要求一个**操作者确认令牌**：先写 `/home/xilinx/OPERATOR_READY` 再跑脚本，
脚本读走后删除——这是"有人在场"的记录，脚本自己绝不生成它。

### 4.1 物理开关（v3-sw 才有）

- **SW0 = M20**，**SW1 = M19**；拨到**上** = 强制旁路（关掉抵消），拨到**下** = 抵消生效。
- 运行中也可以拨，保护不会被触发（旁路不在故障条件里）。
- 状态位：`capture_status[25]` = SW0 原始引脚，`[24]` = SW0 同步后，`[23]` = SW1 同步后。

### 4.2 跑一段"静音 → 扩声 → 静音"（演示主段）

```bash
echo "operator here" > /home/xilinx/OPERATOR_READY
echo a02 > /home/xilinx/demo_mode.txt        # a02 = 20 秒，a05 = 60 秒
./demo_take_v3.sh
```

脚本开局先静音、跑 20 秒、结束时再静音，所以一次录制天然就是"静音→有声→静音"。

### 4.3 软件开关（同一轮里自动切）

```bash
printf 'period=2\ntotal=20\ngain_db=-8\nstart_bypass=0\n' > /home/xilinx/live_toggle.txt
echo "operator here" > /home/xilinx/OPERATOR_READY
./live_toggle_v3.sh
```

每 2 秒切一次，并打印 `TOGGLE 6.00s bypass=1` 与同名 `.timeline.json`，剪辑可对齐。

### 4.4 三点对照（开环 / 旁路 / 抵消）

```bash
echo tone > /home/xilinx/ac_mode.txt
echo "operator here" > /home/xilinx/OPERATOR_READY
./field_ac_segments_v3.sh      # 写 tone_round.json
./tone_analyze.sh              # 打印 CD / 环路提升 / 声学差 / 过冲
```

### 4.5 60 秒连续 / 拍手停声 / 只看电平

```bash
./long60_switch.sh      # 60 秒连续，看帧数与四类计数
./clap_test_switch.sh   # 距麦 2–3 cm 拍手，验证输入满幅停声
./listen_probe_v3.sh    # 3 秒只监听，不出声，看电平
```

---

## 5. 结果怎么看

每次运行落两个文件：`*.npz`（捕获）与 `*.status.json`（收尾状态）。先看 status：

| 字段 | 含义 |
|---|---|
| `stop_reason` | `completed` / `input_clip` / `guard` / `fault` / `incomplete` / `exception` |
| `recovery_ok` | 停声后是否成功恢复静音与 stock overlay |
| `completed_frames` | 实际跑完的帧数（预算内） |
| `capture_status` | 状态字，见下表 |
| `verification` | `bit_exact`、`wide_residual_frames`、`output_mismatches` 等 |

`capture_status` 位表：

| 位 | 含义 |
|---|---|
| 0 | done |
| [16:1] | 已捕获帧数 |
| 17 | arm 了但配置不合法 |
| 18 | 故障 / FIR 错误 |
| 19 / 20 / 21 | 预测 / 残差 / 增益后饱和**曾经**出现 |
| 22 | **输入满幅**（ADC 触轨），v3 起会停声 |
| 23 | SW1 同步后（v3-sw） |
| 24 | SW0 同步后（v3-sw） |
| 25 | SW0 原始引脚（v3-sw） |

**别把"停声"读成"检测到啸叫"**：v3 里没有啸叫检测器，停声来自输入满幅、饱和计数或故障。

---

## 6. 出问题先看这里

| 现象 | 原因与处理 |
|---|---|
| `RuntimeError: bit/hwh mismatch` 或配对错误 | 包与驱动不是同一组；换回该包自带的驱动，别把 v3 驱动指向 v3-sw 的位流 |
| 拨码没反应 | 检查约束是否给该引脚写了 `PULLUP true`——这会把输入顶死成 1（我们踩过）。厂商 base.xdc 对拨码不设内部上下拉 |
| `ping` 不通 | 正常，ICMP 常被挡；用 `ssh` 或 22 端口判断 |
| 运行报 `input_clip` | 输入太大：降音量或后退 5 cm，**不要**放宽门禁 |
| 读到明显过期的结果 | 检查脚本是否复用了旧的 `*.npz`；我们的验证脚本会先删捕获与副车再跑 |
| 上电后运行报 overlay 错 | 先跑自检脚本（`verify_switch.sh` / `verify_delivered_v3.sh`）确认身份 |

---

## 6.5 一键重标定（换了摆位之后）

**这一节回答的问题是**：麦克风与音响的距离/角度一变，旧的模型就失配了，怎么办？

**重标定全程不需要人出声**，所以不存在"先安静、再开口"的配合问题：

```bash
# 板上需要一份拟合器源码：scripts/fit_newlayout_candidate.py 及其同目录依赖
./prep_recalibrate.sh        # 写确认令牌与参数（level_db / segments / seconds / gain_db）
./recalibrate_oneclick.sh    # 一条命令跑完，最后一行给 PASS 或 FAIL
```

六个阶段，每个阶段打一行，日志读起来像清单：

| 阶段 | 做什么 | 失败了会怎样 |
|---|---|---|
| `[1] capture` | 6 段开环激励（旁路+零系数、数字增益 0） | 若削顶，**自动把激励降 6 dB 重试**，最多 3 次，不用人管 |
| `[2] package` | 生成拟合器要的 manifest（逐文件 sha256、`gain_q12=0`） | 缺文件直接失败，不会拿错的包去拟合 |
| `[3] fit` | 调用拟合器产出候选模型 | 拟合失败 → `RECAL_FAIL`，旧模型不动 |
| `[4] install` | 先存成候选，**不切换** | — |
| `[5] verify` | 用**候选模型**跑 322 Hz 三点，按 B 的规则判 | 任一臂停声或判据不过 → FAIL |
| `[6] verdict` | PASS 才落成 `model_recalibrated.json`；FAIL 改名 `.rejected.json` 并保留 | 失败不会留下半装状态 |

判据（与测量入口一致）：**声学差 ≥ 环路提升 − 1.5 dB，且过冲在 ±1.5 dB 内**。

**首次上板结果（2026-10-31）**：流程 6 阶段全部跑通、判定生效、失败自动回退（旧模型未被破坏），
但**这次重拟合本身没有通过判据**：CD(322)=8.26 dB 说明残差被压下去了，可声学差 −0.22 dB、
过冲 −2.19 dB → FAIL。同一轮测到环路提升只有 1.98 dB（C 那次是 3.70 dB），说明两次的声学布置不同。
证据见 [recalibration-2026-10-31](../../report/verification/audio-replay/recalibration-2026-10-31/README.md)。
所以：**"一键重标定"作为流程已验证；作为"换了摆位就能自动成功"还不行**，需要先弄清激励是否够、对齐是否一致。

收据在 `recal_pkt_<时间戳>/recalibration_receipt.json`，含激励电平、六段文件哈希、候选模型哈希、
三臂的 `stop`/`capture_status`、三个量与最终判定。

**注意两点**：
1. 重标定**只换模型**，不换位流、不改算法结构；换过模型之后要重新记录模型哈希（`identity` 会变）；
2. 重标定能补偿的是**同一种布局内的声学变化**（距离/角度/房间），不能补偿"换到完全不同的房间"——那种情况需要重新采集并重新评估可用频段。

## 7. 不接板卡能验证什么

```bash
python -X utf8 scripts/software_sweep.py          # 12 项：JSON/编译/载荷/registry/文档/导入/三项RTL仿真/哈希
python -m unittest discover -s sim/feedback -p "test_*.py"   # 全量软件测试
python -X utf8 scripts/check_docs.py              # 文档断链与状态检查
```

这三条不需要板卡，也不需要人配合；它们证明的是**软件与仿真层**，不等于上板效果。

---

## 8. 重建位流

```bash
vivado -mode batch -source build/scripts/create_audio_replay.tcl      -tclargs build   # v3
vivado -mode batch -source build/scripts/create_audio_replay_sw.tcl   -tclargs build   # v3-sw
```

两个脚本各自写 `build/work/audio_replay*/`，互不覆盖。**改 RTL 就要重新跑上板四项检查**，
不能沿用旧位流的结论；位流字节是交付身份的一部分。
