# 接口契约

> 契约 = 生产方与消费方必须共同遵守的硬约定（格式、时序、寄存器、版本）。
> **改契约必须先通知消费方**，并在 [log/progress.md](../log/progress.md) 留一条"接口变更"。
> 契约只增不删：旧版本冻结，不覆盖。

## 现行契约

| 契约 | 覆盖什么 | 生产方 | 消费方 | 状态 |
|---|---|---|---|---|
| [recal-runtime-v9.md](recal-runtime-v9.md) | 150秒计算预算、START保护留证、A新arm基线与原始字接入 | C | A / C | 0cab原件软件复核通过，待A整包实机验收 |
| [recal-runtime-v8.md](recal-runtime-v8.md) | 150秒I/O阶段预算与安静/采集/讲话实体提示 | C | A / C | 软件验证，待现场复核 |
| [recal-runtime-v7.md](recal-runtime-v7.md) | 上电AUX初始化门槛、失败长按CAL恢复及原件目录 | C / A | A / C | 两侧已交，待上板复核 |
| [recal-runtime-v6.md](recal-runtime-v6.md) | 最终冻结、固定维护模型和按包身份导出的单一回包 | C | A / C | 冻结交付 |
| [recal-runtime-v5.md](recal-runtime-v5.md) | 用户授权的维护自检开放范围与当前模型身份 | C | A / C | 维护开放，正式流程按门槛 |
| [recal-runtime-v4.md](recal-runtime-v4.md) | 场景绑定模型事务、完整运行帧数和静音启动零模型 | C / A | A / C | 软件接入验证 |
| [recal-runtime-v3.md](recal-runtime-v3.md) | B冻结身份/直接evaluate、原件接入及同入口维护链路 | C / A / B | A / B / C | 实现待验证 |
| [recal-runtime-v2.md](recal-runtime-v2.md) | 整机编排扩展、原子提示与输入、B真实算法与预测口径 | C / A / B | A / B / C | 实现待验证 |
| [recalibration-algorithm-v1.md](recalibration-algorithm-v1.md) | B真实evaluate、六训练两验证和时间域预测判据 | B | C / A | 离线通过，待上板 |
| [recal-policy-consumer-v1.md](recal-policy-consumer-v1.md) | C消费B判定、四类cause、本轮延迟及验收缺项 | C | A / B / C | 实现待验证 |
| [recalibration-policy-v1.md](recalibration-policy-v1.md) | B采集/激励/拟合/三点判定；阈值唯一来源 | B | C / A | B已交库，待上板验证 |
| [recal-product-v1.md](recal-product-v1.md) | 常驻产品编排、A/B接口及原子模型事务 | C / A / B | A / B / C | C接口/模拟实现；实体适配待验 |
| [audio-closed-v1.md](audio-closed-v1.md) | 闭环 overlay 的控制位、增益编码、帧关系、缓存读回 | C | A / B | 已实现并构建，未上板验收 |
| [audio-replay-v1.md](audio-replay-v1.md) | 预录声源注入、实际混音反馈参考、限时播放及摘要 | A | A / B / C | 软件/仿真/构建完成，未上板 |
| [audio-replay-v3.md](audio-replay-v3.md) | **现行**：宽残差过增益后再钳位、输入满幅（bit22）**即停声**、增益前残差只作诊断、位流/驱动配对校验 | A | A / B / C | **冻结主线**（队长 2026-10-28）；软件验证 16 项通过；上板复验与 C 增量验收未闭合 |
| [audio-replay-sweep-v2.md](audio-replay-sweep-v2.md) | 已有数据选档、逐档成对试验与按钮操作 | A | A / B / C | 本地实现，未回归/上板 |
| [feedback-fir-v1.md](feedback-fir-v1.md) | 定点抵消核：24 位 PCM / Q20 系数 / 58 位累加 / 771 拍 | B | C / A | 已验证（仿真 + 板上逐样本） |
| [feedback-calibration-v1.md](feedback-calibration-v1.md) | 标定数据 NPZ 与模型 JSON 的字段、单位、拒绝条件 | B | A / C | 已验证（板卡实际执行） |
| [path-analysis-v1.md](path-analysis-v1.md) | 逐频点分析与稳定增益估算的输入输出 JSON | B | A / C | 已实现，待真实数据 |

原始音频链路契约之间的关系：

```
标定（calibration）→ 系数（fir）→ 闭环播放（closed）
                                    ↘ 分析（path-analysis，只读前三者的产物）
```

## 冻结契约（不要再改，也不要在新工作里引用）

这些是诊断阶段或中间版本留下的接口。**它们描述的东西现在仍然能跑，
但已经不再是当前工作路径**；`board/` 下对应的 bit/hwh 也一并归档保留。

| 契约 | 曾被用来 | 被谁取代 | 备注 |
|---|---|---|---|
| [frozen/audio-bringup-v1.md](frozen/audio-bringup-v1.md) | 最小 PL 直通、静音与帧计数 | audio-closed | 第一次证明 PL 能驱动 Codec |
| [frozen/audio-probe-v1.md](frozen/audio-probe-v1.md) | 读最近一帧 ADC 值 | audio-capture | 只能读快照，不是连续录音 |
| [frozen/audio-capture-v1.md](frozen/audio-capture-v1.md) | 片上缓存 4096 帧连续采样 | audio-residual | 只输出统计，不存 PCM |
| [frozen/audio-diag-v1.md](frozen/audio-diag-v1.md) | 强制 `sdata_o` 为 0，查 TX 是否真的在发 | audio-closed | 证明内部有活动≠有声 |
| [frozen/audio-tone-v1.md](frozen/audio-tone-v1.md) | PL 内部生成约 1 kHz 三声 | audio-closed | 证明 PL 能出声，不含 ADC 通路 |
| [frozen/audio-residual-v1.md](frozen/audio-residual-v1.md) | 开环残差：256 抽头 FIR + 四路缓存 | audio-closed | 现由 closed 的零系数模式覆盖 |

## 新增契约的格式

用 [templates/interface-contract.md](../templates/interface-contract.md)。
文件头必须有三行：

```
状态：草案 / 已协调 / 实现待验证 / 已验证 / 已冻结
生产方：  · 消费方：
最后变更：YYYY-MM-DD  原因：
```

没有"状态"行的契约，`scripts/check_docs.py` 会报错——因为无法判断它能不能被依赖。

## 版本索引更新（2026-10-27）

| 契约 | 现行版本 | 说明 |
|---|---|---|
| audio-replay | **v3** | 宽残差过增益后再钳位 + `capture_status` bit22 输入满幅；v1/v2 保留 |
| audio-closed | **v2** | 运行上限 488281 → 3000000 帧 |
| feedback-fir | v1 | 未变（v3 只新增一路宽残差输出，24 位语义与 `residual_saturated` 未变） |
| feedback-calibration | v1 | 未变 |
| audio-replay-sweep | v2 | 未变 |

v2 的差异只有运行上限，见 [audio-replay-v2](audio-replay-v2.md) 与 [audio-closed-v2](audio-closed-v2.md)。
v3 的差异只有残差乘宽与 bit22，见 [audio-replay-v3](audio-replay-v3.md)。

运行上限变更的批准记录见 [proposal-continuous-run](proposal-continuous-run.md)（已批准，结论并入 v2）。
