# run_dir 一行修复（C 81b47e3，2026-11-02）

**验证层次：软件验证（不调驱动、不上板）。**

## 一句话

按 C 的要求在 `ProductHardwareV2.perform` 分派前补 `self.run_dir = request.get('run_dir') or self.run_dir`。
旧代码只有 `_run_plan` 自己赋这个值，所以 `input`+`cue` 的自动重说、`install`、`run` 三个分支都用着**上一次的**
目录，第二次写同一个 NPZ 时独占创建失败。改动已在源码与 `v3-io` 副本同步，新哈希
`8799f40b6d9f7ecbfa8f9b2491b084f046b4b9d8d7ffd013feca0c84dbca95e0`（原 `784acc6b…`）。

## 证据

[output.txt](output.txt) —— 同一份探测脚本跑两个版本，旧版从 git 里取（rev `4467906`，即冻结时的
`hw_api.py 784acc6b`），不是转述：

```
BEFORE  op input / install / run  -> self.run_dir 仍是上一次的目录   3/3
AFTER   op input / install / run  -> self.run_dir 取到请求里的目录   3/3
```

以及这一行的实际后果：

```
_capture_path with stale run_dir   -> ...\previous-scene\1\input\scene-A_1_input_00.npz
_capture_path with request run_dir -> ...\resay-scene\2\input\scene-A_1_input_00.npz
```

同一 scene/attempt 下，目录不同才不会撞名；目录相同就是 C 复现的"第二次独占创建失败"。

## 改动

`board/audio_replay/hw_api.py` L927（`ProductHardwareV2.perform` 内，`op = request.get('op')` 之后、
四个分派分支之前）：

```python
self.run_dir = request.get('run_dir') or self.run_dir
```

`board/audio_replay/v3-io/hw_api.py` 是逐字节副本（同哈希），`v3-io/manifest.json` 与
`docs/contracts/product-adapter.json` 的 `hw_api.py` / `helper_sha256` 已同步到 `8799f40b…`。

顺带修掉 `product-adapter.json` 里两处过期哈希：`replay_trial_repair.py` 实际是 `0dc80c23…`（文件里还写着
`22851d32…`），`package_files_sha256` 与 `expected_identity` 现已一致。

## 边界

- 未上板：本次没有验证真实产品在两次重说后确实落到两个目录、也没有验证第二次 CAL 能成功。
  C 侧已用隔离改动复现过"隔离后两次都保存到独立目录"，本轮只是把同一行同步到 A 的包。
- 未改契约语义：`request.run_dir` 本来就在 `v2_changes` 里写着"captures written into request.run_dir"，
  这行是让 `install`/`run`/`input` 也照做，不是新接口，故不升版本号。
- `helper_sha256` 变了，C 必须同轮重钉（见 [aux-boot 报告](../aux-boot-2026-11-02/README.md) 的 pin 结论）。

## 复现

```powershell
cd <仓库>\_a_work\wt-int\report\verification\audio-replay\run-dir-fix-2026-11-02
$env:PYTHONIOENCODING='utf-8'
<bundled python> check_dispatch.py
```
