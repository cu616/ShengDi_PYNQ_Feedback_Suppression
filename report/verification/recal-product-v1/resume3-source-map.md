# 当前上板工程（+1 dB / 60 秒 / 4 段训练 / BTN2 恢复）源码与产物清单

本页回答一个具体问题：**板上正在跑的那套东西，到底由哪些文件组成、分别来自仓库哪里**。
给其他 AI/同学整理代码时，请以本页和 [resume3-source-map.json](resume3-source-map.json) 为准。

## 1. 板上装的是什么（身份钉死）

| 项 | 值 |
|---|---|
| 交付 ZIP | `shengdi-recal-0cabfc17-alg1102-resume3-gain1-60s-final.zip`（41 文件） |
| ZIP sha256 | `b167d0b579df94e76065b067ada8feb2b3e050f7c44aa3541f57a47319d615b4` |
| manifest sha256 | `beb36216d26b6cbb510f6f211d139424943863693e48fee44511ad200d62d9ef` |
| 板上 release | `/opt/shengdi/releases/beb36216d26b6cbb`（`/opt/shengdi/current` 指向它） |
| 位流 sha256 | `322350656986d91f25a63735f87e5b0b9cc2f7ea977356ce9e988014648e738e` |
| 算法版本 | `recal-algorithm-2026-11-02.1`（文件 sha `3ed77482…`） |

ZIP 本体已随本页入库：`packages/shengdi-recal-0cabfc17-alg1102-resume3-gain1-60s-final.zip`。

**关键运行参数（来自包内 `product-config.json`，sha `d35dea40…`）**：

| 参数 | 值 |
|---|---|
| 工作增益 `expected_identity.gain_q12` | **4596**（+1.0 dB） |
| `run_seconds` | **60** |
| 训练段数 `attempts[*].training.segments` | **[4, 4, 4]**（4 段训练） |
| capture_plans 训练/验证段数 | 训练 4/4/4、验证 2/2/2 |
| `allowed_gain_q12` | [1631, 2303, 3254, 4096, 5786, 4596] |
| `phase_gain_q12` | prepare=[0,1631,2303,3254,4096,4596,5786]；cue/input/training/validation/install/run/**runtime**=[0,4596] |
| hp_volume / aux_db / 采样率 | 40 / 0 / 48828.125 Hz |

## 2. 代码来源：三类，别混

### A. 与当前仓库内容完全一致（hash 相同，直接用仓库文件）

| 包内文件 | 仓库路径 |
|---|---|
| `recal_algorithm.py` | `board/audio_replay/recal_algorithm.py` |
| `recal_policy_consumer.py` | `board/audio_replay/recal_policy_consumer.py` |
| `recal_runtime.py` | `board/audio_replay/recal_runtime.py` |
| `closed_tools.py` / `replay_tools.py` / `residual_tools.py` / `tone_round_guard.py` | `board/audio_replay/` 同名文件 |
| `recal_entry.sh` | `board/audio_replay/recal_product_entry.sh` |
| `product-install.sh` / `shengdi-product.service` | `board/audio_replay/` 同名文件 |
| `audio_replay.bit` / `audio_replay.hwh` | `board/audio_replay/v3-io/` 同名文件 |
| `ALGORITHM.md` / `POLICY.md` | `docs/contracts/recalibration-algorithm-v1.md` / `docs/contracts/recalibration-policy-v1.md` |
| `feedback/__init__.py`、`feedback/excitation.py`、`feedback/recal_policy.py` | `src/feedback/` 同名文件 |

### B. 上板版本 ≠ 当前仓库（**必须用历史提交，不能用 main 的最新文件冒充**）

| 包内文件 | 包内 sha256 | 对应仓库历史提交 | 当前 main 的差异 |
|---|---|---|---|
| `recal_product.py` | `7e0c9ba7…` | `4efd430`（[C] 最小实现 BTN2 保护恢复并冻结 4596 六十秒基线） | main 已加 capture_plan 批量路由（`433bf95`），内容不同 |
| `hw_api.py` | `0cabfc17…` | `0d349af`（[A] 按 C guard150 要求补齐…） | main 已加 `perform_capture_plan` 薄调用层 |
| `recal_link.py` | `72e2ab65…` | `de775e1`（[C] 组装固定 4.5dB 八秒演示配置…） | main 已加 capture plan 校验 |
| `replay_trial_repair.py` | `0dc80c23…` | `5939ee5`（[A] 修取消边界…，v3-io 驱动） | main 已有 A 的批量入口（`b65a8606…`），文件更大 |

取历史版本的方法（示例）：

```powershell
git show 4efd430:board/audio_replay/recal_product.py > recal_product.py
git show 0d349af:board/audio_replay/hw_api.py > hw_api.py
git show de775e1:board/audio_replay/recal_link.py > recal_link.py
git show 5939ee5:board/audio_replay/v3-io/replay_trial_repair.py > replay_trial_repair.py
```

### C. 仓库里没有对应文件（C 组装/生成，只存在于包内）

`product-config.json`（行为参数，sha `d35dea40…`）、`product-policy.json`（`a2c86b31…`）、
`bootstrap-model.json`、`manifest.json`、`product-manifest.json`（`beb36216…`）、
`hardware-provenance.json`、`physical-controls.json`、`upstream-product-adapter.json`、
`OPERATIONS.md`、`INTERFACE.md`、`RUNTIME.md`、`BOOT-RECOVERY.md`、`DEMO-RUNTIME.md`、
`FINAL-RUNTIME.md`、`FROZEN-RUNTIME.md`、`GUARD-RUNTIME.md`、`INSTALL-RUNTIME.md`、
`MAINTENANCE-RUNTIME.md`、`POLICY-CONSUMER.md`、`IO-INDICATOR.md`。

> 也就是说：**+1 dB、60 秒、4 段训练、BTN2 恢复这些行为，是由包内 `product-config.json` +
> `recal_product.py@4efd430` + `recal_link.py@de775e1` 决定的**；仓库 main 里没有等价的完整配置。
> 整理代码时如果要"能复现上板版本"，必须以包内文件为准，并保留本页的哈希。

## 3. 给整理代码的 AI 的一句话版本

```
上板版本 = ZIP b167d0b5…（manifest beb36216…，release beb36216d26b6cbb）。
其中代码来自 4 个历史提交（recal_product@4efd430、hw_api@0d349af、
recal_link@de775e1、replay_trial_repair@5939ee5），其余 .py 与当前 main 相同；
行为参数全部在包内 product-config.json（4596/60s/4段训练/2段验证/含 runtime 白名单），
仓库 main 没有这份配置。不要用 main 上更新的同名文件冒充上板版本；
要整理成可读源码树时，请为每个文件标注来源（repo 路径或历史提交号）并保留上述哈希。
```

完整逐文件哈希见 [resume3-source-map.json](resume3-source-map.json)。
