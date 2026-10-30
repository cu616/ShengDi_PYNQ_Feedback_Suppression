# 声堤：实时声反馈啸叫抑制系统

ShengDi_PYNQ_Feedback_Suppression 是基于 PYNQ-Z2 的声反馈抑制项目：
在 PL 侧用定点 FIR 抵消扬声器回到麦克风的反馈，目标是在真实硬件上提高稳定扩声音量，
并测量延迟、音质与 FPGA 资源开销。首版面向桌面扩声，助听场景留作后续探索。

## 现在是什么状态

**不要在本文件维护状态。** 唯一权威是 [docs/STATE.md](docs/STATE.md)：
已验证/未验证清单、关键数字口径、三条线各自进展、板卡占用、下一步，都在那里。

部署前先看 [上板版本索引](board/README.md) 与 [audio_replay 版本说明](board/audio_replay/README.md)。旧驱动和诊断材料保留供追溯；目录名或修改时间不能代替整组版本核验。

## 从哪里开始

| 你是 | 入口 |
|---|---|
| 接手本仓库的 AI | [AGENTS.md](AGENTS.md) → [docs/STATE.md](docs/STATE.md) → 用户本次转发消息 → [docs/lines/](docs/lines/) |
| 第一次看这个项目的人 | [docs/INDEX.md](docs/INDEX.md)（按"我要做什么"导航） |
| 想知道文档怎么组织、为什么这样组织 | [docs/WORKFLOW.md](docs/WORKFLOW.md) |
| 找旧路径找不到文件 | [docs/archive/MIGRATION-2026-10-20.md](docs/archive/MIGRATION-2026-10-20.md) |

## 目录

```text
src/         RTL、Python 算法源码及厂商依赖
sim/         仿真与软件测试
build/       Vivado 工程重建脚本
board/       上板 overlay、驱动与现场操作单
docs/        文档：现状、契约、时间线、参考（唯一入口 docs/INDEX.md）
skill/       可复用的开发与排查经验
report/      证据：验证报告与 AI 协作原始记录
references/  厂商手册、原理图与赛事资料
scripts/     仓库辅助脚本（含文档守门 scripts/check_docs.py）
data/        后续测试数据（当前为空，原始录音不入库）
tmp/         本地临时文件，不纳入 Git
```

`docs/` 内部分层（按变化速度，不按日期）：

```text
docs/STATE.md        现状，覆盖式更新（唯一权威）
docs/WORKFLOW.md     3×(人+AI) 协作协议与拉取对齐流程
docs/lines/          每条线的职责与边界
docs/contracts/      现行接口契约（frozen/ 为已冻结的诊断接口）
docs/log/            只追加的时间线：progress、experiments、handoffs
docs/ref/            长期参考：架构、计划、教程、硬件
docs/rules/          用户与团队的硬要求
docs/archive/        冻结内容与迁移映射
```

## 常用命令

```text
# 软件测试（Python 需 NumPy）
python -m unittest discover -s sim/feedback -p "test_*.py" -v

# 用已有标定数据做逐频点分析与稳定增益估算（不需要板卡在线）
python scripts/analyze_path.py --data-dir <含两个 npz 与候选 json 的目录> --output <结果.json>

# 30 秒对齐：三条线已记录的进度；协作任务另看用户转发消息
python scripts/brief.py          # 可加 --line a|b|c 只看自己那条线

# 文档守门：断链、孤儿、现状复述、契约状态头
python scripts/check_docs.py
```

## 资料使用与记录

按团队要求使用 GitHub 私有仓库。当前未授予全部内容统一开源许可证；
厂商 PDF 等第三方材料权利归原作者。赛前公开与许可证按届时规则处理，不自动改变可见性。

推测与实测必须分开写，历史计划保留原始日期。原始录音未经同意不传出板卡；
`data/` 中的原始音频不入库。
