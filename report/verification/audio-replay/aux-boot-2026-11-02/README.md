# 上电 AUX 失败的离线复现与补丁验证（2026-11-02）

**验证层次：软件复现 + 软件验证（把 codec 的 I2C 原语换成内存寄存器表）。未上板，未改冻结包。**

## 一句话

现场"断电后启动即失败、按键无反应"的原因能在电脑上**确定性复现**：codec 上电 `0x400B/0x400D = 0x00`，
`get_aux_gain_db()` 回 `aux_db=None`，C 的 `_identity()` 第一项就报 `硬件身份混搭或配置不符:aux_db`。
**在构造时写一次 AUX 就能让全部 10 个身份字段通过**；但同一个补丁会把 `helper_sha256` 改掉，
而它被 C 钉了 **4 处**，所以 A 侧单独改 `hw_api.py` 一定启动不了——必须与 C 同一轮重冻。

## 证据

- 逐字输出：[repro-output.txt](repro-output.txt)
- 复现脚本：[repro_aux_boot.py](repro_aux_boot.py)（无板可跑）
- 补丁生成器：[make_patch.py](make_patch.py) → [aux-fix.diff](aux-fix.diff)（3 处改动，84 行 diff）

```
RESULT  A reproduces the field failure : 硬件身份混搭或配置不符:aux_db
RESULT  B passes every identity field  : PASS
RESULT  C (the actual patch) passes    : 硬件身份混搭或配置不符:helper_sha256
pins of the current hw_api hash        : product-config.json x1, product-manifest.json x3
```

## 三个结论

1. **失败是确定性的，不是偶发**。只要 codec 停在上电值 `0x00`，`hw_api` 自己就返回 `aux_db=None`
   （`raw_left=0`），与 C 的 `expected_identity['aux_db']=0.0` 不等。三次现场现象与此一致。
2. **写一次 AUX 就够，没有第二个身份字段是坏的**。场景 B 把 `set_aux_gain_db(0.0)` 放在第一次读身份之前，
   `aux_db/aux_raw_left/aux_raw_right/hp_volume/gain_q12/sample_rate_hz` 与四个 sha 全部通过。
   这排除了"重冻后还会卡在别的字段"的风险。
3. **A 侧补丁不能单独发**。`identity()['helper_sha256']` 就是 `hw_api.py` 自己的 sha256，C 把它写进了
   `product-config.json`（1 处）和 `product-manifest.json`（3 处）。补丁先把 `aux_db` 修好，
   紧接着就报 `helper_sha256` 不符——**这是包身份机制在起作用，不是新故障**。
   所以"一次性改完、只冻一次"里的"一次"必须同时包含：A 的 `hw_api.py`、C 的 4 处 pin、整包重建。

## 补丁内容（未合入）

见 [aux-fix.diff](aux-fix.diff)，四处：

1. `get_aux_gain_db()`：把"没写过的编码"如实报出来（`recognized` / `unmapped_codes` / `power_on_like`），
   不再把未知值和"左右不一致"都压成同一个 `None`；`aux_gain_db` 字段名保持不变，C 的 `IDENTITY` 不用动。
2. `ProductHardware.__init__()`：`set_aux_gain_db(self.aux_db)` 写一次，失败只记录不抛出
   （否则服务会在构造函数里崩，比现在的"进失败态"更难诊断）；结果进 `capabilities()['aux_init']`。
3. 模块头注：原文还写着 `bit 2113a454`、"没有按键和 LED 接口"，与已冻结的 I/O 位流
   （`322350656986d91f`、`capture_status[30:27]`=BTN、`control[5:2]`=LD）不符。顺手改对，跟着同一次重冻走。
4. `capabilities()`：加 `'aux_init'`，把上电那次 AUX 写入的结果暴露出来，写入失败时能一眼看到原因，
   不必再从"四灯全亮"反推。

## 边界（不能从这份证据得出的结论）

- 是**模型化 codec**，不是真板：`0x00` 这个上电值来自现场记录（`fix_aux_boot.sh` 的注释与交接文档），
  本轮没有重新读板确认。
- 没有验证 systemd 启动顺序、没有验证写入时机与 codec 复位的关系（驱动 `replay_trial_repair` 只
  读回 AUX 校验、不重写，所以一次写入应当能保持；但这是从代码读出来的，不是实测）。
- 没有触及产品服务把 PS 卡死的问题（另一项，仍等 C）。

## 复现

```powershell
cd <仓库>\_a_work\wt-int\tmp\aux-boot-repro
$env:PYTHONIOENCODING='utf-8'
<bundled python> make_patch.py      # 生成 hw_api.AUXFIX.py 与 aux-fix.diff
<bundled python> repro_aux_boot.py  # 场景 A/B/C
```

`make_patch.py` 与 `repro_aux_boot.py` 都只读 `board/audio_replay/v3-io/hw_api.py`，不写回。
