# 新包 `shengdi-recal-8799f40b-0b09ef6-io150-final.zip` 离线核验（2026-11-02）

**验证层次：静态/字节级核验（解包、逐文件哈希、pin 对账、代码路径确认）。未上板、未安装。**

## 一句话

包是完整自洽的：38 个文件、`product-manifest.json` 覆盖的 37 个哈希逐个对上，`hw_api.py` 与
`helper_sha256` 的 6 处引用**全部**指向 `8799f40b6d9f7ecbfa8f9b2491b084f046b4b9d8d7ffd013feca0c84dbca95e0`。
A/B 字节未改（位流、hwh、驱动、`replay_tools`、B 的算法文件与上一包逐字节相同），A 侧只有 `hw_api.py` 变了。
**可以装**；但 C 说的两项（overlay 复用、PS 卡死）确认仍未修，且板子现在连不上，装完没法验。

| 项 | 值 |
|---|---|
| ZIP | `shengdi-recal-8799f40b-0b09ef6-io150-final.zip` |
| ZIP sha256 | `a91db61e40756887beee7bec88903e8f991868c81245e93017857d28b0f758b5` |
| 大小 / 文件数 | 373119 字节 / 38 个文件 |
| 包内 `source_commit` | `98663a4d5ce3d035d0ed68273d0e3bb5139f8277`（`[C] 允许慢采集完成并修正讲话与采集实体提示`，是 `origin/C` 上 `cdcaa56242a84a296b32daf8e8972436197fbfca` 的父提交） |
| C 的提交 | `cdcaa56242a84a296b32daf8e8972436197fbfca`（已 fetch，与 `origin/C` 一致） |

## 核验结果（逐字输出见 [verify-output.txt](verify-output.txt)）

```
1 product-manifest hashes              files=37  bad=0  missing=0  PASS
2 hardware adapter hashes              files=11  bad=0  missing=0  PASS
3 A's manifest.json                    files=8   bad=0  missing=0  PASS
4 uncovered files (self-manifest allowed) 0     PASS
```

6 处 pin 全部 = `8799f40b…`：包内 `hw_api.py` 实际哈希、`manifest.json`、`product-manifest.json`、
`adapters.hardware.hashes`、`adapters.hardware.expected_identity.helper_sha256`、`product-config.json`。

## 与上一包（7bd365b）的差异

| 类型 | 文件 | 归属 |
|---|---|---|
| 改 | `hw_api.py` | **A（唯一一处）** |
| 改 | `OPERATIONS.md`、`manifest.json`、`product-config.json`、`product-manifest.json`、`product-policy.json`、`recal_link.py`、`recal_product.py` | C |
| 增 | `BOOT-RECOVERY.md`、`IO-INDICATOR.md`、`upstream-product-adapter.json` | C |

位流 `322350656986d91f…`、hwh `bbe1eb4935b0931f…`、驱动 `0dc80c23…`、`replay_tools` `bba22102…`、
B 的 `recal_algorithm.py`、`feedback/*` 与 `bootstrap-model.json` **全部字节未变**。

`upstream-product-adapter.json` 与 A 侧 `docs/contracts/product-adapter.json` **语义完全相同**
（逐键比较 `a == b` 为真），只是序列化后 3247 vs 3311 字节，属格式差，不是内容差。

## 代码层确认：C 的两处修复确实在交付字节里

不是只听 C 说，是在包内 `recal_product.py` 里核对到的：

1. **AUX 延后比较**：新增 `AUX_IDENTITY = ('aux_db','aux_raw_left','aux_raw_right')`；
   `_identity(actual, prepared=False)` 里 `defer_aux = not self.configuration_ready and not prepared`，
   未就绪时跳过这三个键；`if prepared: self.configuration_ready = True`；调用处
   `self._identity(reply['identity'], prepared=(req['op']=='prepare' and reply.get('ok') is True))`
   ——即**prepare 成功回读之后**才比 AUX，与 C 说的一致。
2. **CAL 可重试**：按键分支在 `if self.fatal: return` 之后才新建 scene；`self.fatal` 只在身份混搭、
   sha 不符、无法确认停声这几处被置位。普通失败不置 `fatal`，所以确认静音后长按 BTN0 能重来。
3. `quiet_seconds=4`、`speech_seconds=2.5`、`input_mode="embedded"`、`expected_identity.aux_db=0.0` 均在
   `product-config.json` 中核对无误。

## 边界

- **未上板、未安装**：`192.168.2.99:22` 仍不可达，所以 AUX 延后比较、CAL 重试在真板上的实际行为
  还没验过；`--check` / `--adapter-check` 也没跑。
- **C 明说仍未修**：overlay 复用、产品服务把 PS 卡死。这两项直接决定能不能做正式演示。
- `source_commit` 记的是 `98663a4…`（功能提交），不是包提交 `cdcaa56…`。如果 C 的本意是"包子集提交"，
  这不是缺陷；若要精确对账可让 C 确认一句。

## 复现

```powershell
cd <仓库>\_a_work\wt-int\tmp\zipcheck
$env:PYTHONIOENCODING='utf-8'
<bundled python> verify_pkg.py
```
