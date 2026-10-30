# C 汇总 v3 的 B 侧消费核对

> 对象：C 固定提交 `b2ad47d`（`schema_version=3`、`calculation_version=c-measurement-2.1.0`）。
> 结论：**可以直接消费**，字段与门禁自洽；同时用同一份工具定位了历史 50 条的真实缺口。
> 工具：`scripts/consume_summary_v3.py`；测试：`sim/feedback/test_summary_v3.py`（4 项）。

## 1 怎么核对

```bash
# 取出 C 的汇总（不切分支）
git show b2ad47d:report/verification/audio_closed/b-request-software-summary-v3.json > /tmp/sw.json
python scripts/consume_summary_v3.py --summary /tmp/sw.json --csv /tmp/sw.csv
```

判据（脚本内实现）：`schema_version=3`/`calculation_version` 前缀、24 个必备字段、尾段空值一致性、
模型身份（文件哈希 + 系数哈希按 little-endian int32）、256 补零不得标 candidate、
配对身份十项一致（模型可不同）、`asg_db` 只在 `board_recording` 且两行达标时才允许非空。

## 2 软件夹具（`b-request-software-summary-v3`）

`consumable_as_is=true`、0 阻断项、`model_registry_hits=2/2`。
关键一条：两行分别是 `coef_hash_matches_raw_array=1` 与 `coef_hash_matches_padded512=1`——
即"256 模型补零装进 512 位流"这件事在**数据侧**被证实，不依赖任何声明。
`effect_eligible_real_pairs=0`，与 C 的自我标注一致。

## 3 历史 50 条（`b-request-historical-summary-v3`）

schema 同样可消费，但数据本身全部不可用：`category=invalid` 50/50、`tail_valid=false` 50/50、
`effect_eligible=false` 50/50、`model_pairs=0`。

阻断原因（脚本统计，行数）：

| 原因 | 行数 |
|---|---|
| `bitstream_capacity_unverified` | 44 |
| `actual_loaded_taps_missing` | 44 |
| `comparison_identity_missing` | 44 |
| `actual_gain_q12_missing_or_invalid`（及 hp/bit/coef） | 6 |
| `model_not_in_approved_registry` | 6 |

字段覆盖：`gain_q12`/`hp_volume`/`bit_sha256`/`coefficients_sha256`/`model_role`/`logical_taps` 各 44 行，
`loaded_taps` **0 行**，`tail_rms_dbfs`/`tail_slope_db_per_s`/三频带 **各 0 行**，`protection_triggered` **0 行**。

44 行都是 `box_v1/baseline_256`、`logical_taps=256`，且 `coefficients_sha256` 44/44 命中
**原数组**（0 行命中补零数组）→ 历史批从没加载过补零到 512 的数组。

### 3.1 两个位流的归属（本轮最重要的发现）

| bit_sha256 前 8 位 | 归属 | 行数 | 能不能当声学证据 |
|---|---|---|---|
| `4d49dfbe…` | `board/audio_closed/audio_closed.bit`（该 overlay 已退役） | 22 | **不能**：DAC 无输出是 A 已查明的结论，只有 PL 算术证据 |
| `dadbbbab…` | `audio_replay.bit`（256 抽头） | 22 | 可以，但要先在 `BIT_CAPACITIES` 里登记 256 |

`BIT_CAPACITIES` 目前只有 512 位流 `8b2426f4…`，所以 `dadbbbab…` 那 22 行永远被判
`bitstream_capacity_unverified`。这不是数据错，是登记缺失。

## 4 给 C 的三条最小补充（其余不用改）

1. `BIT_CAPACITIES` 增加 `dadbbbab…ddcb05` → 256（出处：`report/verification/audio-replay/2026-10-21-asg-field.md`
   第 17、215 行）。否则箱体 256 的基线行永远进不了配对。
2. `loaded_taps` 缺失时可从 `coefficients_sha256` 反推：等于原数组就是 `logical_taps`，
   等于补零数组就是 512。本脚本已按这个口径统计（44/44 命中原数组）。
3. **逐行导出 `positive_control_valid`**（或至少把
   `tail_or_safety_or_positive_control_not_validated` 拆成 tail / safety / positive_control 三个码）。
   现在 `effect_eligible=false` 时无法区分"尾段不合格"与"通路没接通/音响待机"——
   后者正是本项目反复踩的假阴性，B 侧无法从现有字段还原。

## 5 顺带修掉的两处 B 侧问题

`models/manifest.json` 结构改为 `models`（只放可部署的 3 个）+ `derived_artifacts`（补零产物）：

- 原先把补零产物的 `file` 写成 `models/room_v1/...`，相对 `models/` 解析会变成 `models/models/...`，
  C 的 `load_registry` 会找不到文件；
- 更严重的是重复命中：补零产物的 `coefficients_sha256` 与原模型的 `padded_512_sha256` 相同，
  两条记录同时命中会让"按系数反查模型"变成歧义，整行被判 `model_not_in_approved_registry`。
- 现在 `models` 仍是 3 条、哈希不变，C 的注册表语义完全不变；补零产物移到 `derived_artifacts`
  并补齐 `lag_first`/`sample_rate_hz`/`hp_volume`/`logical_taps`/`loaded_taps`/`coefficients_sha256`。
- 新增 `coefficients_sha256`（原数组）与 `padded_512_sha256`（补零后）两个字段，口径与 C 的
  `qhash()` 一致，可双向核对。
- 新 `manifest.json` sha256 `71d13ca927b23213b491ecc0af3a405210c99550dedb11f2878ddd6905573fcc`
  （旧的 `ce9aa371…` 作废）。三份模型文件本身一字未动，文件哈希与 `b2ad47d` 记录的相同。

## 6 完成边界

- 本轮没有任何板卡动作，没有新采集；软件夹具不当实测。
- `effect_eligible_real_pairs=0` 仍未改变：要变成非零，必须 A 静默复算后回传带尾段与正向对照的
  `board_recording` 配对，或重新采集。
- 模型预测的阈值、饱和点、保护点一律不写成实测 ASG。
