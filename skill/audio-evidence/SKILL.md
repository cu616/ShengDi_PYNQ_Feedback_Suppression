---
name: audio-evidence
description: 核对FPGA音频交付的位流/驱动/模型身份与黄金参考、源激活窗口和幅度单位。用于本仓库离线交付复核；不执行板卡或声音操作，不据此判定ASG。
---

# 音频交付身份与测量口径

适用：拿到按 `materials/work/c/assemble_candidate.py` 导出的候选目录，用Python 3.12和NumPy离线核对。工作目录为候选根。两个流程复用现有实现，不重写驱动或参考模型。

## 1. 先绑定版本，再解释结果

运行 `python materials/work/c/verify_candidate.py --candidate .`。正常退出0，`ok=true`，`payload_checks`十项全true，并给出候选Q20哈希6118e85d…。同时核对候选 `integration.json` 每文件来源与哈希；模型fixture、Codec40、采样率、lag_first=1必须一致。

失败例：只在临时复制品中将 `board/audio_replay/v3/replay_tools.py` 换成旧版或追加一个字节，再运行同一命令，必须退出2并出现`v3 identity mismatch`；不得通过改manifest批准这个坏版本。保留原目录，重新从固定来源导出恢复。文件哈希不是签名，跨项目须先建立可信的硬件/寄存器/参数manifest，不能直接沿用本项目常量。

## 2. 黄金参考、窗口与幅度

运行 `python board/audio_replay/v3/test_verify_replay_v3.py`，期望`VERIFY_REPLAY_V3_TEST PASS`。该脚本检查非对称signed24边界、截断前缀事件和可验输出；随后C消费者用例检查宽残差先增益再限幅。错误路径“先夹残差再增益”在专门反例中必须不匹配；实际检查数量以脚本输出为准。

运行 `python -m unittest discover -s sim/feedback -p test_replay_v3_consumer.py -k round -v`。正常覆盖：manifest指定同轮、共同含源窗、已知0.25FS峰值约-12.0412dBFS；失败覆盖：换源、换round、坏帧/副车、缺原件。坏输入必须阻断配对数字，保存未知或失败，不以空窗回退整窗。

实际既有数据仅在原件可见时运行 `python scripts/review_itemized_20261027.py --capture-dir <原件目录> --round-manifest <原manifest.json> --expected-round-id <实际整数> --out <派生JSON>`，不glob混轮。没有原件时保留板端派生JSON，说明本地仅做身份/窗口/差值算术审核。不得捏造PCM重算或让操作者重采补“通过”。

幅度峰值用20log10(A)；Hann FFT须除相干增益sum(w)，功率积分用N*sum(w*w)；RMS与峰值分列。322Hz加权正弦拟合包含直流项；源激活窗是实际捕获区间与板载源区间的交集。带外、非稳态、外部声源未知或低SNR都限制解释。观测末窗不证明全程声音稳定，计数覆盖不替代波形覆盖。

## 已验证范围与出处

本仓库PYNQ-Z2 v3的既有软件用例；本次候选具体通过项看 `materials/work/c/validation.json`（开发仓库回执，不一定随最小候选导出）。没有跨板实测。ASG、听众收益、端到端延迟均不能由上述离线检查得到。

- A `facd3de`：`board/audio_replay/v3/manifest.json`、`test_verify_replay_v3.py`，宽残差和历史排除规则。
- C `330e135`：`scripts/review_itemized_20261027.py`、`sim/feedback/test_replay_v3_consumer.py`，窗口/身份/单位反例。
- B `86061a7`：`sim/feedback/test_unit_scale_guard.py`，PCM单位与Q20动态范围纠错。
- 真实纠错与引用界限：`materials/work/c/claims.md`、`materials/work/c/technical-report.md`。旧经验入口见 `skill/ai-collaboration/SKILL.md`。

## 固定字段速查（指南 3.3.5.2）

- **适用场景**：拿到按 `materials/work/c/assemble_candidate.py` 导出的候选目录，用 Python 3.12 + NumPy 做离线身份/参考/窗口/单位核对。不执行板卡或声音操作。
- **使用方法**：按上文第 1、2 节命令依次执行；失败例必须保留原目录并重导，不得改 manifest 放行坏版本。
- **已验证效果**：本仓库 PYNQ-Z2 v3 软件用例通过（`test_verify_replay_v3.py`、`sim/feedback` 下的 round/窗口/单位反例）；候选具体通过项见 `materials/work/c/validation.json`。
- **失效条件**：仅离线核对；没有跨板实测，不能判定 ASG、听众收益、端到端延迟；无原件时只做身份/窗口/差值算术审核，不得捏造 PCM 重算。
- **来源**：本项目 2026-10 多轮"哈希/窗口/单位"纠错，原始记录见 `report/`、`docs/log/` 与上列提交号。

