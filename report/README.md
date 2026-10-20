# 证据库

**本目录只放证据，不放叙事，也不放现状。**

- 叙事与结论 → [docs/log/](../docs/log/)
- 现在是什么状态 → [docs/STATE.md](../docs/STATE.md)

| 路径 | 放什么 |
|---|---|
| `verification/<overlay>/` | 每次验证的原始材料：时序、资源、DRC、仿真日志、板上输出、结果 JSON |
| `ai-records/` | AI 协作的逐字提示、关键回答、人工纠错轨迹（评分项"大模型协作记录"主要靠这里） |
| `evidence-index.md` | 证据总索引：哪个结论对应哪个文件 |

## 规则

- 结论与证据分开：`docs/log/` 里每一条结论都要能链到本目录的一个文件。
- 失败与取消的记录同样保留，不删。只导成功项等于伪造证据。
- 摘要不能冒充原始对话；只保留摘要时必须标注，并给出原文位置。
- 板上原始 PCM、NPZ 未经同意不出库；本目录只存分析结果与可公开的命令输出。

团队执行规则见 [AI 开发规范](../docs/rules/ai-development-policy.md)，
记录模板见 [docs/templates/ai-session-record.md](../docs/templates/ai-session-record.md)，
最新的线间交接见 [docs/log/handoffs/](../docs/log/handoffs/)。
