# 声堤：实时声反馈啸叫抑制系统

> **只想让它跑起来** → [使用说明 docs/USAGE.md](docs/USAGE.md)（三分钟上手 + 四个现场入口）
> **只想看交付件** → [materials/](materials/README.md) + [board/audio_replay/v3-sw/](board/audio_replay/v3-sw/)
> **想知道现在到哪一步** → [docs/STATE.md](docs/STATE.md)（唯一权威）

ShengDi_PYNQ_Feedback_Suppression 是基于 PYNQ-Z2 的声反馈抑制项目：
在 PL 侧用定点 FIR 抵消扬声器回到麦克风的反馈，目标是在真实硬件上提高稳定扩声音量，
并测量延迟、音质与 FPGA 资源开销。首版面向桌面扩声，助听场景留作后续探索。

## 三十秒内容地图

| 分类 | 目录 | 里面是什么 |
|---|---|---|
| **交付件** | `materials/` | 视频脚本、报告片段、离线教程、提交清单 |
| | `board/audio_replay/v3-sw/`、`v3/` | 上板载荷（位流+驱动+manifest，**二选一，不可混装**） |
| | `skill/` | 可复用的排查与证据核验技能 |
| **工程** | `src/`、`sim/` | RTL、算法源码、仿真与软件测试 |
| | `build/` | Vivado 重建脚本与约束 |
| | `board/` | 板端驱动、现场脚本、历史 overlay（分类见 [board/README.md](board/README.md)） |
| | `models/`、`scripts/`、`tools/` | 模型与 registry、辅助脚本、交付核查 |
| **过程与证据** | `docs/` | 现状、契约、时间线、参考（入口 [docs/INDEX.md](docs/INDEX.md)） |
| | `report/` | 实测证据与 AI 协作原始记录（只追加，不改写） |
| | `references/` | 厂商手册与赛事资料 |

历史 overlay 的位流（8 个目录约 34 MB）**保留在原位是有意的**：它们被 56 篇证据与日志按路径引用，
搬动等于改写历史记录。当前要用的只有 `v3/` 与 `v3-sw/`。

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
board/       上板 overlay、驱动与现场操作单（board/audio_replay/ 内按"当前/已作废/archive/"分层）
docs/        文档：现状、契约、时间线、参考（唯一入口 docs/INDEX.md）
materials/   参赛材料：教程、报告片段、视频与提交清单（materials/README.md）
models/      候选与基线模型 + registry（身份以 manifest 哈希为准）
tools/       交付冻结与交付核查脚本（tools/delivery-freeze.json）
skill/       可复用的开发与排查经验
report/      证据：验证报告与 AI 协作原始记录
references/  厂商手册、原理图与赛事资料
scripts/     仓库辅助脚本（含文档守门与综合软件测试）
data/        后续测试数据（当前为空，原始录音不入库）
tmp/         本地临时文件，不纳入 Git
```

### 交付件在哪（按提交要求对号）

| 提交项 | 位置 |
|---|---|
| 视频 | `materials/final/shengdi-demo.mp4`（脚本与字幕：`materials/work/a/script.md`） |
| 技术报告 | `materials/work/c/technical-report.md`（硬件片段 `materials/work/a/hardware.md`、算法片段 `materials/work/b/algorithm.md`） |
| 源码包 | 本仓库（构建入口 `build/scripts/create_audio_replay.tcl`） |
| 可复现/验证入口 | `python -X utf8 scripts/software_sweep.py`（12 项）、`python -m unittest discover -s sim/feedback` |
| 离线教程 | `materials/learning/index.html`（双击打开，无需联网） |
| 技能包 | `skill/README.md`（索引；单项入口 `skill/*/SKILL.md`） |
| 板卡部署载荷 | `board/audio_replay/v3/`（先核 `v3/manifest.json`，不混装 `archive/` 里的旧件） |

### 目录对照（评测指南 3.3.5.4）

指南推荐结构为 `README.md / src/ / sim/ / build/ / board/ / data/ / skill/ / report/`，
明确说明**推荐而非强制**，采用其他组织方式的仓库须在本文件给出目录对照说明。本仓库对照如下：

| 指南推荐 | 本仓库 | 说明 |
|---|---|---|
| `README.md` | `README.md` | 本文件；项目简介、目录对照、复现入口 |
| `src/` | `src/` | RTL、算法源码与厂商依赖 |
| `sim/` | `sim/` | 仿真与软件测试 |
| `build/` | `build/` | Vivado 重建脚本、约束与实现报告 |
| `board/` | `board/` | 上板 overlay、驱动、现场脚本与实测输出 |
| `data/` | `data/` | 测试数据与参考结果；原始录音不入库 |
| `skill/` | `skill/` | 技能包（索引 `skill/README.md`，贡献规范 `skill/CONTRIBUTING.md`） |
| `report/` | `report/` | 验证证据与 AI 协作原始记录 |
| （推荐结构之外） | `docs/` | 现状/契约/流程/日志；`docs/STATE.md` 是唯一现状入口 |
| （推荐结构之外） | `materials/` | 参赛材料：报告、视频、教程、提交清单 |
| （推荐结构之外） | `records/`→`report/`、`models/`、`scripts/`、`tools/` | 证据归档、模型 registry、辅助脚本、交付核查 |
| （推荐结构之外） | `references/` | 厂商手册与赛事指南 |

命名规则（指南 3.3.5.4 原文要求）：仓库内目录名与文件名使用纯英文（小写字母、数字、下划线或连字符），
不得出现中文、空格或特殊字符；中文只出现在文件正文。`README.md`、`SKILL.md` 等惯例大写名沿用原有写法。
根目录的本地交付 ZIP、Vivado 日志与临时工作区已进 `.gitignore`，不随提交归档。


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
