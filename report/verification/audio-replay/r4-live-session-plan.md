# RC0.1-r4 真人场执行清单

> 状态：**已就绪，待人**　执行者：A（唯一操板者）　版本：C 的 r4（`eff553f`）+ A 的 `85f4967`

## 一、已搭好的部分（无需再动）

| 项 | 状态 |
|---|---|
| 板端位流 | **v2** `61bb71aa…` / hwh `92b499a3…`（`MAX_RUN_FRAMES=3000000`），v1 存为 `v1_audio_replay.*` |
| 驱动 | `live_run.py` @ `942fd5b`（含解静音次序与取消回执修正），已同步上板 |
| C 的包 | `c-sprint-rc01-r4` 已完整解压到 `/home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc01-r4/`（45 项） |
| 预检 | `preflight.all_ok=true`；15 项 `window_frames` 全 ≥14408；SHA256 与 C 声明一致 |
| 真人模式驱动 | `_a_work/run_rc4_human.sh`：听感题**不自动作答**，等待答复文件 |
| 答复通道 | `/home/xilinx/hearing_answer`，已自检 **PASS**（`_a_work/selftest_channel.sh`） |

## 二、现场需要的人和物

1. **一位说话人**（本人在桌边即可）—— real-voice 项要现场人声，约 5 秒/次，共 2–3 次
2. **一位固定听众** —— 坐在音响正前方 0.5 m，`listener-off` / `listener-on` 各判断一次
3. **音响电源伸手可及** —— 这是队长要求的现场值守条件，不因批跑取消

## 三、现场摆放（全程不得变动）

```
说话人 → 麦克风 15 cm
麦克风 放桌面，音响正立、面向麦克风、距 0.5 m
听众 坐音响前 0.5 m
手机不参与（本场用真人声，不用手机源）
```

## 四、执行流程

1. A 启动 `run_rc4_human.sh`，控制台出现 `RETURN_PACKAGE` 说明每项完成
2. 出现 `REAL_VOICE_CUE` + `SPEAK_05…01` 时，**说话人开始正常讲话 5 秒**
3. 出现 `HEARING_WAIT itemN` 时：
   - A 在群里问：**第 N 项，听众听到什么？**
   - 听众回答：`CLEAR`（清楚）/ `HOWL`（啸叫）/ `OTHER`（其他异常）
   - A 把该词写入 `/home/xilinx/hearing_answer`，驱动自动继续
4. 任何一次出现保护、削顶、门禁失败 → **立即停批留证**，不重试、不补跑、不升档

## 五、停止条件（任一触发即停）

- `stop_reason` 不是 `completed`
- 出现 `prediction` / `residual` / `gain` / `mix` 任一饱和计数非零
- 听众判断为 `HOWL`
- 音响出现明显失真或异常噪声

## 六、边界（必须如实写进回包）

- 本场 real-voice / listener 的结果**只代表这一次会话与这一套摆放**，不外推到其他位置或音量
- 连续 60 秒项的证据范围仍是**寄存器时间线 + 尾部 PCM**，不宣称全程音质
- `PROXY` 与 `HUMAN_LIVE_AND_LISTENING` 不得混记；本场全部按后者登记

## 七、预计用时

约 **20–25 分钟**（15 项 + 2–3 次人声 + 2 次听众判断）。
