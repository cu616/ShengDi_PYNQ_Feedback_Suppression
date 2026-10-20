# 目录迁移映射（2026-10-20）

> 旧的路径或旧提示词里写死了 `docs/` 下的文件位置，2026-10-20 重整过一次。
> 拿旧路径找不到文件时查这张表。新工作一律用右列。

## 为什么改

旧结构按「文件产生的时间」摊在目录里，导致：同一事实有十几处副本、
「当前状态」有 4 个家、文件名带日期不带主题、死文档无标记。
新结构按「变化速度」分层：现状（覆盖）/ 分工 / 契约（版本化）/ 时间线（追加）/ 参考 / 冻结。
见 [WORKFLOW](../WORKFLOW.md) 与 [INDEX](../INDEX.md)。

## 映射表

| 旧路径 | 新路径 |
|---|---|
| `docs/tasks/audio-closed-2026-10-19.md` | [docs/archive/tasks/audio-closed-2026-10-19.md](../archive/tasks/audio-closed-2026-10-19.md) |
| `docs/tasks/audio-residual-integration-2026-10-18.md` | [docs/archive/tasks/audio-residual-integration-2026-10-18.md](../archive/tasks/audio-residual-integration-2026-10-18.md) |
| `docs/tasks/closed-batch-control.md` | [docs/archive/tasks/closed-batch-control.md](../archive/tasks/closed-batch-control.md) |
| `docs/tasks/feedback-fir-optimization-2026-10-18.md` | [docs/archive/tasks/feedback-fir-optimization-2026-10-18.md](../archive/tasks/feedback-fir-optimization-2026-10-18.md) |
| `docs/tasks/open-loop-calibration-2026-10-16.md` | [docs/archive/tasks/open-loop-calibration-2026-10-16.md](../archive/tasks/open-loop-calibration-2026-10-16.md) |
| `docs/interfaces/audio-closed-v1.md` | [docs/contracts/audio-closed-v1.md](../contracts/audio-closed-v1.md) |
| `docs/interfaces/feedback-calibration-v1.md` | [docs/contracts/feedback-calibration-v1.md](../contracts/feedback-calibration-v1.md) |
| `docs/interfaces/feedback-fir-v1.md` | [docs/contracts/feedback-fir-v1.md](../contracts/feedback-fir-v1.md) |
| `docs/interfaces/audio-bringup-v1.md` | [docs/contracts/frozen/audio-bringup-v1.md](../contracts/frozen/audio-bringup-v1.md) |
| `docs/interfaces/audio-capture-v1.md` | [docs/contracts/frozen/audio-capture-v1.md](../contracts/frozen/audio-capture-v1.md) |
| `docs/interfaces/audio-diag-v1.md` | [docs/contracts/frozen/audio-diag-v1.md](../contracts/frozen/audio-diag-v1.md) |
| `docs/interfaces/audio-probe-v1.md` | [docs/contracts/frozen/audio-probe-v1.md](../contracts/frozen/audio-probe-v1.md) |
| `docs/interfaces/audio-residual-v1.md` | [docs/contracts/frozen/audio-residual-v1.md](../contracts/frozen/audio-residual-v1.md) |
| `docs/interfaces/audio-tone-v1.md` | [docs/contracts/frozen/audio-tone-v1.md](../contracts/frozen/audio-tone-v1.md) |
| `docs/interfaces/path-analysis-v1.md` | [docs/contracts/path-analysis-v1.md](../contracts/path-analysis-v1.md) |
| `docs/parallel-work/README.md` | [docs/lines/README.md](../lines/README.md) |
| `docs/parallel-work/prompt-a-field.md` | [docs/lines/a-field.md](../lines/a-field.md) |
| `docs/parallel-work/prompt-b-algorithm.md` | [docs/lines/b-algorithm.md](../lines/b-algorithm.md) |
| `docs/parallel-work/prompt-c-measurement.md` | [docs/lines/c-measurement.md](../lines/c-measurement.md) |
| `docs/experiments/manual-headphone-check-2026-10-15.md` | [docs/log/experiments/2026-10-15-headphone-check.md](../log/experiments/2026-10-15-headphone-check.md) |
| `docs/experiments/stock-input-reference-2026-10-15.md` | [docs/log/experiments/2026-10-15-stock-reference.md](../log/experiments/2026-10-15-stock-reference.md) |
| `docs/experiments/contiguous-adc-tone-check-2026-10-16.md` | [docs/log/experiments/2026-10-16-contiguous-tone.md](../log/experiments/2026-10-16-contiguous-tone.md) |
| `docs/experiments/audio-debug-log.md` | [docs/log/experiments/2026-10-audio-debug.md](../log/experiments/2026-10-audio-debug.md) |
| `docs/experiments/feedback-preflight.md` | [docs/log/experiments/preflight-plan.md](../log/experiments/preflight-plan.md) |
| `docs/handoff-2026-10-17.md` | [docs/log/handoffs/2026-10-17.md](../log/handoffs/2026-10-17.md) |
| `docs/handoff-2026-10-19.md` | [docs/log/handoffs/2026-10-19.md](../log/handoffs/2026-10-19.md) |
| `docs/handoff-b-2026-10-20.md` | [docs/log/handoffs/2026-10-20-b-to-a.md](../log/handoffs/2026-10-20-b-to-a.md) |
| `docs/progress.md` | [docs/log/progress.md](../log/progress.md) |
| `docs/core-code-reading-guide.md` | [docs/ref/code-reading-guide.md](../ref/code-reading-guide.md) |
| `docs/development-plan.md` | [docs/ref/development-plan.md](../ref/development-plan.md) |
| `docs/getting-started.md` | [docs/ref/getting-started.md](../ref/getting-started.md) |
| `docs/hardware/microphone-requirements.md` | [docs/ref/hardware-microphone.md](../ref/hardware-microphone.md) |
| `docs/procurement-review.md` | [docs/ref/procurement.md](../ref/procurement.md) |
| `docs/repository-guide.md` | [docs/ref/repository-guide.md](../ref/repository-guide.md) |
| `docs/workspace-architecture.md` | [docs/ref/workspace-architecture.md](../ref/workspace-architecture.md) |
| `docs/ai-development-policy.md` | [docs/rules/ai-development-policy.md](../rules/ai-development-policy.md) |
| `docs/IMPORTANT-ai-progress.md` | [docs/rules/progress-mandate.md](../rules/progress-mandate.md) |

## 目录级变化

| 旧目录 | 现在 |
|---|---|
| `docs/experiments/` | `docs/log/experiments/`（时间线） |
| `docs/handoff-*.md` | `docs/log/handoffs/`（时间线） |
| `docs/interfaces/` | `docs/contracts/`（现行）+ `docs/contracts/frozen/`（冻结） |
| `docs/parallel-work/` | `docs/lines/`（分工与任务卡） |
| `docs/hardware/` | 并入 `docs/ref/hardware-microphone.md` |
| `docs/tasks/` | 全部进 `docs/archive/tasks/`（均已失效） |
| `docs/progress.md` | `docs/log/progress.md`（只追加） |
| `docs/IMPORTANT-ai-progress.md` | `docs/rules/progress-mandate.md` |

## 新增的文件

- [STATE.md](../STATE.md) —— 「现在是什么状态」的唯一权威
- [INDEX.md](../INDEX.md) —— docs 的唯一入口
- [WORKFLOW.md](../WORKFLOW.md) —— 3×(人+AI) 协作协议
- [contracts/README.md](../contracts/README.md) —— 契约版本表与冻结清单
