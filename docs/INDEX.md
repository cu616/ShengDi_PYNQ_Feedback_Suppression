# docs 目录索引

> 本文件是 `docs/` 的唯一入口。**先看这里，不要从文件列表里猜。**
> 你是一个 AI：按下面的"我要做什么"选路径，不要通读全部文档——
> 那会浪费掉你大部分上下文，而且大部分内容已经过期。

## 一、按"我要做什么"找

| 我要… | 读这个 | 不要读 |
|---|---|---|
| 知道现在是什么状态、什么已验证 | [STATE.md](STATE.md) | progress.md（那是历史） |
| 知道 A/B/C 谁负责什么、边界在哪 | [lines/README.md](lines/README.md) | 旧 prompt 文件 |
| 按我这条线开工 | [lines/a-field.md](lines/a-field.md) · [b](lines/b-algorithm.md) · [c](lines/c-measurement.md) | — |
| 查某个接口 / 寄存器 / 系数格式 | [contracts/README.md](contracts/README.md) | frozen/ 下的诊断接口 |
| 改代码前先懂结构 | [ref/workspace-architecture.md](ref/workspace-architecture.md)、[ref/code-reading-guide.md](ref/code-reading-guide.md) | — |
| 查某次实验到底做过什么 | [log/experiments/](log/experiments/) | — |
| 知道用户明确提出过哪些硬要求 | [rules/progress-mandate.md](rules/progress-mandate.md) | — |
| 写 AI 协作记录（评分项） | [templates/ai-session-record.md](templates/ai-session-record.md) | — |
| 找不到某个旧路径 | [archive/MIGRATION-2026-10-20.md](archive/MIGRATION-2026-10-20.md) | — |

## 二、目录是什么、什么时候读

| 目录 | 放什么 | 更新方式 | 谁维护 | AI 何时读 |
|---|---|---|---|---|
| `STATE.md` | 现状、已验证/未验证、关键数字、板卡占用 | **原地覆盖** | 三条线各改自己那段 | **每次会话开始，必读** |
| `WORKFLOW.md` | 3×(人+AI) 协作协议、文档规则 | 很少改 | 团队共识 | 首次接手时读一遍 |
| `lines/` | 每条线的职责、边界、验收 | 任务变更时改 | 各线自己 | 开工时读自己那份 |
| `contracts/` | 现行接口契约（格式、时序、寄存器） | **版本化**，改前通知 | 生产方 | 涉及接口时读 |
| `contracts/frozen/` | 已冻结的诊断版接口 | 不改 | — | 除非挖历史，否则不读 |
| `log/` | 时间线：进度、实验、交接 | **只追加，不改写** | 各线 | 只在查具体事件时按需 grep |
| `ref/` | 长期参考：架构、硬件、计划、教程 | 事实变化时改 | 相关线 | 按需 |
| `rules/` | 用户与团队的硬要求、开发规范 | 用户提出新要求时改 | 全体 | 首次接手时读 |
| `templates/` | 模板 | 很少改 | — | 需要写记录时读 |
| `archive/` | 冻结内容 + 迁移映射 | **不改** | — | 只在旧链接失效时查 |

## 三、三条铁规则

1. **一条事实只有一个权威位置。** 其他位置只能写链接，不能复述。
   复述就会漂移——本项目已经出现过"6.92 dB"被 19 个文件各写一遍、
   最后互相矛盾的情况。
2. **现状只在 `STATE.md`。** 任何 `log/` 条目、`ref/` 文档里出现的"当前状态"
   都视为历史快照，不作为行动依据。
3. **默认不新建文件。** 新内容先找既有位置的合适小节放进去；
   只有"确实是一类新东西、且会长期存在"时才新建（判据见 WORKFLOW 第 5 节）。

## 四、证据在哪

本目录只放"叙事与结论"。**原始输出、JSON、截图、命令日志一律放 `report/`：**

- `report/verification/<overlay>/` —— 每次验证的原始证据（时序、资源、仿真、板上结果）
- `report/ai-records/` —— AI 协作的逐字提示与纠错轨迹（评分项）
- `report/evidence-index.md` —— 证据总索引

规则：`log/` 里每一条结论都必须能链到一个 `report/` 里的证据文件。
没有证据的结论，写进 `STATE.md` 的"未验证"一节，不要写进"已验证"。
