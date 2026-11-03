# 队长 HF 相位诊断脚本：A 板卡执行回传（2026-11-03）

**来源**：队长提交 `main@e379c66`（`[队长] 依据场景收据修复历史fixture诊断阻塞`）
**脚本 sha256**：`bdc1ddf96c7b5e563c1811190e8a7ad341689053528ba36fe006e4308b1f68f1`（= 脚本内 `script_sha256`）
**执行命令**（板卡，root；新版自带路径，无需 `HOME`）：

```
/usr/local/share/pynq-venv/bin/python /home/xilinx/diag_highfreq_phase.py \
    --board-scene --out /tmp/hf-phase-captain-1747073733.json
```

**执行结果**：无报错，`status = "computed"`，产出 JSON 一个（板卡 `/tmp/hf-phase-captain-1747073733.json`）。
**原始 PCM 未导出**，仍留板 `~/.local/state/shengdi/runs/6b2e43d4…/io/`。

## 回传文件

- [hf-phase-captain-1747073733.json](hf-phase-captain-1747073733.json)
  sha256 `5b4b20d7507d552f8a832737aec6962b5a687c85aab4ba62e8c57e66e117f513`，4,922,975 字节。
- 场景 `6b2e43d4b77c4b73b84923ea17d4a5e6`；模型 `ba432ad195711069c5160480b21eb6ec2073c423144d4e21f15e93b8b2799580`，
  系数 `6507565c444929737d8b44486c7064d4226792070e4f6eac8a3f84827287f1cf`；6 个采集（4 training + 2 validation），
  共 826 频点/文件。
- `fixture_annotation`：`kind = documented_stale_fixture_label`，`raw_fixture_id = 9dc20d41…`，
  `receipt_scene_id = 6b2e43d4…`，`basis = A e553471`；`ignored_noncalibration_files` 列出被排除的 input/install/run 采集。
  即：队长已按 A 的 `e553471` 证据把历史 fixture 标签错误**标注**而非修改原件。

## 关键频点（每个采集的实测 H / 模型 Ĥ / 相位差 / 复残差 / 估计环路 @ gain_q12=5786）

| 文件 | 405 Hz | 4005 Hz | 4100 Hz | 7999 Hz | 8345 Hz | 8500 Hz | 9000 Hz |
|---|---|---|---|---|---|---|---|
| training_00 | H 0.994 / resid 0.062 / loop 0.087 | 0.449 / 0.203 / 0.287 | 0.844 / 0.082 / 0.116 | 0.542 / 0.115 / 0.163 | **1.334 / 0.403 / 0.569** | 1.199 / 0.190 / 0.268 | 0.321 / 0.099 / 0.140 |
| training_01 | 0.967 / 0.089 / 0.126 | 0.497 / 0.133 / 0.188 | 0.886 / 0.073 / 0.103 | 0.538 / 0.136 / 0.192 | **1.354 / 0.381 / 0.538** | 1.215 / 0.195 / 0.275 | 0.296 / 0.112 / 0.159 |
| training_02 | 1.155 / 0.162 / 0.228 | 0.568 / 0.223 / 0.315 | 0.879 / 0.147 / 0.208 | 0.488 / 0.118 / 0.167 | **1.374 / 0.453 / 0.639** | 1.232 / 0.273 / 0.386 | 0.323 / 0.072 / 0.102 |
| training_03 | 0.902 / 0.129 / 0.182 | 0.649 / 0.156 / 0.220 | 0.833 / 0.210 / 0.296 | 0.493 / 0.136 / 0.192 | **1.371 / 0.479 / 0.677** | 1.197 / 0.197 / 0.278 | 0.306 / 0.085 / 0.121 |
| validation_00 | 1.436 / 0.487 / 0.688 | 0.542 / 0.165 / 0.232 | 0.833 / 0.098 / 0.139 | 0.474 / 0.140 / 0.198 | **1.244 / 0.318 / 0.449** | 1.322 / 0.237 / 0.335 | 0.193 / 0.120 / 0.169 |
| validation_01 | 1.102 / 0.126 / 0.178 | 0.463 / 0.188 / 0.266 | 0.886 / 0.211 / 0.298 | 0.565 / 0.159 / 0.224 | … | … | … |

（`H_abs / residual_abs / estimated_loop_abs`；`gain_q12=5786` 即 +3 dB 假设；相位差见 JSON 每行 `phase_diff_deg`。）

**A 的读法（仅陈述数字，不做稳定性结论）**：8.345 kHz 处 6 个采集的 H 均为 1.24–1.37、模型 Ĥ≈1.07、
复残差 0.32–0.48、按 +3 dB 折算的估计环路 0.45–0.68；4.1 kHz 处 H 0.83–0.89、Ĥ 0.925、残差 0.07–0.21、环路 0.10–0.30。

---

# 附：增益阶梯（+1.5/+2.0/+3.0 dB）所用模型与板卡文件

**模型**（L1 = 3.961605，与场景 `6b2e43d4` 的旧模型分开）：

- 路径：`/home/xilinx/.local/state/shengdi/models/archive/e73eaed98e3c4ff585abd49f6ae01356-fe4c52445751d3b072b23fe85aa4cf6ee7211a471948e19c3a0b562fbd304891/model.json`
- 文件 sha256：`fe4c52445751d3b072b23fe85aa4cf6ee7211a471948e19c3a0b562fbd304891`
- Q20 系数 int32-LE sha256：`a39a73496b1dd274dd5457c2069ea1b731cfbe71e83e47d14dc76f0d0ca239a8`
- taps 512、lag_first 1、hp_volume 40、fixture_id `e73eaed98e3c4ff585abd49f6ae01356`（场景 e73eaed9 的标定产物）

**板卡文件**（`/home/xilinx/shengdi-install/ab_runs/`）：

| 目录 | 文件 | 说明 |
|---|---|---|
| `ladder_1747072677/` | `install/lad-install_1_install_00.npz`、`install/lad-install_model.json`、`plus1.5/plus1.5_1_run_00.npz`、`plus2.0/plus2.0_1_run_00.npz`（各含同名前缀 `.status.json`） | 第一次阶梯（静音，两段各 10 s） |
| `ladder_1747072777/` | 同上四个文件 | 第二次阶梯（真人说话，+1.5 通过 10 s、+2.0 0.15 s input_clip） |
| `p15_1747072866/` | `install/p15-install_1_install_00.npz`、`install/p15-install_model.json`、`p15/p15_1_run_00.npz`（各含 `.status.json`） | +1.5 dB 30 s 确认（15.97 s guard 停，主峰 4134 Hz） |

以上均为只读引用，A 未新增现场实验。
