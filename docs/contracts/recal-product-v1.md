# 常驻重标定产品接口 v3

现行实现与实体验收状态查[STATE](../STATE.md)。本页v3新增用户2026-11-03授权的批量调度接口，不改变原寄存器/算法语义。

统一版本`recal-product-v1`。C拥有唯一`recal_entry.sh`、`recal_product.py`及`assemble_experiment.py`产品分支。A拥有`hw_api.py`及驱动/实体I/O；B拥有`recal_algorithm.py`及数值依赖。A/B不再改入口。原`experiment.py`、`layout_experiment.py`保留离线验收用途，不是第二个正式产品入口。

## v2：保护后 BTN2 免标定恢复（2026-11-03）

本次只升文档修订版，消息`contract`仍为`recal-product-v1`，兼容原A事件。扩声保护停声进入`protected`（包括`input_overload`）后，短按BTN2/`confirm_quiet`可恢复到ready，再按BTN1扩声；同一scene最多3次，第4次保持protected并提示CAL，新CAL重置计数。failed/model_rejected/inconclusive/cancelled不能恢复。

恢复前须同场景已装模型文件存在且SHA匹配、硬件调用已退出、实际静音、没有硬件错误锁存。复用空闲粘滞位留证及原驱动arm基线逻辑，不改硬件基线/保护策略；仅重新提交既有验证模型的启动资格，不拟合、不装载、不自动发声。状态/导出增加`resumed_from`与`resume_count`。指示灯沿用ready图案，不新增配置键，`RESUME_MAX=3`为模块常量。

## A硬件对象

### v3：一次 arm 的 capture_plan 批量入口（2026-11-03）

wire仍为`recal-product-v1`。旧驱动没有批量入口时保持原串行路径，现有正式ZIP不修改、不冒称提速。仅当A驱动同时声明`CAPTURE_PLAN_API="recal-capture-plan-v1"`且提供下述函数，hw_api.capabilities才返回同值`capture_plan_batch`，C的training/validation自动改调`perform_capture_plan(request,cancel_event)`；声明与实现混搭必须失败，不回退串行掩盖故障。prepare/input/install/run不改。

文件所有权：C维护`recal_link.perform_capture_plan/check_capture_plan`、产品路由及hw_api的同名薄调用方法/能力字段；A只实现`board/audio_replay/v3-io/replay_trial_repair.py`的批量驱动入口及必要底层读取。A不要同时改C调用层。bit/hwh、RTL、算法、gain4596、run60、4训练2验证、阶段白名单和BTN2语义不变。新驱动落地后由C统一重钉整包；不得单换现有正式包文件。

#### A需实现的函数

```python
CAPTURE_PLAN_API = "recal-capture-plan-v1"

def replay_capture_plan(outputs, fixture_id, model_path, source_pcm16, *,
                        request_id, scene_id, op, hp_volume,
                        gain_q12, direct_only, zero_coeff,
                        speaker_confirmed, local_capture_confirmed,
                        restore_stock, before_start, cancel_event):
    # op仅training/validation；gain_q12=0，direct_only=zero_coeff=True。
    # 一次下载、一次完整source加载、一次系数加载、一次arm；不是循环replay_trial。
    ...
```

`outputs`是有序字典列表，每项包含capture_id、output_path、first_frame、end_frame、valid_frames、source_first_frame/source_end_frame、seed、level_dbfs。C生成与旧_make_stimulus相同的int16激励，不重采样/整形：每段16386源样本，保留旧运行的2帧零尾，段跨度16388。一次完整预载source为各段源和零尾拼接、去掉最终2个零；总budget为最后end_frame。4段source长度65550、budget65552；2段长度32774、budget32776，均小于131072源RAM。

4段输出窗依次为`[4,16388)`、`[16392,32776)`、`[32780,49164)`、`[49168,65552)`。每份NPZ仍16384帧，valid_frames仍16382。first_frame必须是真实批次全局帧号，不假称硬件每段复位；每份NPZ的source_pcm16保存本次完整预载源，使现有verify_replay(raw,q,...,first_frame)可独立复算。新增段源范围只解释有效激励段，不能改变原PCM。

C准备显式的当前scene模型副本（只改副本fixture_id，原模型及系数不动），用于开环zero_coeff加载；原/副本分别记录source_model_sha256/calibration_model_sha256，不把旧fixture伪报当前scene。原捕获不重写；这不会修复旧串行数据中已发现的fixture问题。

#### 环形缓存是必要前提

现有RTL只有16384帧环形缓存（src/rtl/audio_pl_replay.v），当前驱动先停声再读最后一窗。延长budget后读RAM只剩尾窗，不能拆成4份冒充独立数据。新入口须在运行中及时读取并保留各窗，原硬件保护/取消仍优先；若读取赶不上生产、计数不可确认或需RTL才可保留，返回整批失败`streaming_unavailable/ring_overrun`，不要偷偷改位流、重复下载或返回重复尾窗。

每个capture返回`read_proof`：按顺序覆盖该窗的若干块，每块为`{first_frame,end_frame,completed_before,completed_after}`，均为实际硬件计数。C校验块连续覆盖且`end_frame <= completed_before <= completed_after <= first_frame+16384`，证明读取期间块内最老样本未被覆盖。只给bit_exact不够：重复激励的被覆盖窗也可能算术正确。

必须保留现有MMIO下载闸、codec/AUX行为和取消回调。使用当前模块的Overlay符号，以经过已有闸门；C调用层在整次调用期间保持_op_hold。before_start保留取消检查、仅在真正arm前重建基线；初始化期间取消不得重新unmute/arm。每段按原verify_replay执行bit_exact，通过后才可报成功，C还会从实际NPZ独立复算。

#### 返回结构与落盘

```json
{"contract":"recal-capture-plan-v1","request_id":"r1","scene_id":"s1","op":"training",
 "ok":true,"status":"completed","failed_index":null,"failed_check":null,
 "batch":{"overlay_downloads":1,"source_loads":1,"arm_count":1,
          "completed_segments":4,"ring_overrun":false,"wall_seconds":6.2},
 "captures":[{"capture_id":"s1-0-training-0","path":"/run/r1/training-00.npz",
   "status_path":"/run/r1/training-00.status.json","first_frame":4,"end_frame":16388,
   "valid_frames":16382,"source_sha256":"<完整预载源字节SHA>","content_kind":"onboard_excitation",
   "read_proof":[{"first_frame":4,"end_frame":2052,"completed_before":2052,"completed_after":4096}]}]}
```

示例省略其余capture及覆盖整个窗口的后续read_proof块；`6.2`仅为结构示例，不是实测。真实返回必须N个不同文件/ID，顺序与outputs一致。NPZ保留reference、microphone、prediction_pcm、residual_pcm、coefficients_q20、source_pcm16、sample_rate_hz、metadata_json；metadata保留原schema和全部身份/verification字段。fixture_id为scene_id，model_sha为传入副本真实SHA，gain0/zero_coeff/forward_path_open如实记录。completed_frames/capture_status等全批终态计数从实际硬件读取，不伪造成逐段独立arm；first_frame/frames标明各窗口范围。逐文件.status.json沿用原完整字段，记录最终恢复、保存和保护状态；全批数据到PS后停声、再落盘均可，但不能以落盘替代窗口保留。

任一段读取/保护/bit_exact/保存/身份检查失败：`ok=false`，status按原error/protected分类，failed_index为0起始段号（全局初始化错误为null），failed_check给具体检查名，保留已有文件和captures，completed_segments如实写，不能静默丢段。取消也整批失败，不把部分数据送拟合。C在硬件后台线程完成原始文件/bit_exact复核，主轮询继续处理停止，旧epoch结果不得安装；回包保留capture_plan_check和具体失败段。

验收由A一次执行：同模型/布局、逐段原始窗与旧模式字段/数值口径对照、全部bit_exact；训练4段硬件墙钟目标≤7秒、总CAL目标≤125秒，validation两段同路径；原3个BTN2恢复测试和面板流程保留。真实麦克风在不同录音时刻含噪声，不能把两次mic PCM逐字节相等当成可承诺结果；不得复制旧PCM制造等价。尚无批量驱动/实机计时时，不发布“已优化正式包”。

`hw_api.create_product(config)`返回对象，导入不发声。

| 方法 | dict输入/输出 |
|---|---|
| `mute()` / `abort()` | `{ok:true,muted:true}`；abort另须`quiescent:true`确认旧操作不会继续写硬件，可与操作并发，200ms内请求硬件停声，不能重新采集/初始化或等计算结束 |
| `capabilities()` | `{contract:"recal-product-v1",buttons:true,indicator:true,nonintrusive_events:true,abort_mutes:true,prepared_capture:true,bounded_run:true,mode_readback:true}`；缺任一项禁止正式运行 |
| `poll()` | 无音频副作用：`{ok:true,events:[{kind:"recalibrate/start/stop/cancel/confirm_quiet/mode",value:...}],protected:false,identity:{...},effective_mode:"muted/cancel/bypass"}`；去抖由A处理，模式来自实际读回 |
| `indicate(prompt)` | prompt含state/text/color/pattern/mode；A映射真实灯。无RGB时用LED组合/闪数配实体图例，不编造颜色 |
| `perform(request,cancel_event)` | op为prepare/cue/input/training/validation/install/run；C放后台线程，A必须响应取消；prepare完成预备后C才提示讲话 |

每项结果含`contract,request_id,scene_id,ok,status,identity`。status为completed/protected/error。输入满幅另带`input_clip:true`。cue只能开环播放，返回`end_frame,tail_frames`；input返回`valid_first_frame`，不得早于cue结束加尾声。training/validation按B预封装plan执行，返回`captures:[{capture_id,path,sha256,first_frame,end_frame,source_sha256}]`；path在本次run_dir内，保留原件。install/run返回实际`model_sha256,coefficients_sha256`；run另有effective_mode/elapsed_seconds，到单次时限真实结束并静音，不拼段自动重启。

identity逐操作和poll实际回读：aux_db/aux_raw_left/aux_raw_right/hp_volume/gain_q12/sample_rate_hz/driver_sha256/bit_sha256/hwh_sha256/helper_sha256。不把请求值当回读。运行额外绑定模型与实际Q20。

expected_identity是就绪/运行的固定配置；开环标定允许按B封装的phase_gain_q12表使用实际0增益，不能把运行增益冒充开环回读。scope为prepare/cue/input/training/validation/install/run/runtime；未列scope只允许运行增益。prepare表须包含预备交接期允许值。除数字增益外上述identity字段全程不变。A适配清单给allowed_gain_q12，B所有阶段值必须为A允许集合子集；安装完成须回到严格运行配置。bundle绑定运行配置，原捕获保留各阶段真实配置。

cue与input帧号必须属于同一scene的统一时间域，不能直接比较两个重置计数器。A以真实完成/尾声和预备时序映射，不清楚就拒绝有效窗。prepare须让输入采集已预备，input仅消费已备好的捕获，不能等提示后再加载overlay。poll在running时另含实际model_sha256/coefficients_sha256；protected表示当前活动操作的保护事件，不把上一试次sticky状态当新试次事件。

捕获另给content_kind；只有`onboard_excitation`可自动回传原PCM，模拟为`software_fixture`。讲话为`human_private`或未知时原PCM留板。源/数据类型来自A实际计划，不从文件名猜测。计算日志留板，B不在结构化回复中写人声PCM。

A=f378262旧API缺按键/灯、非侵入poll、prepare/激励及即时abort，不能直接冒充本接口；当前产品不能声称实体完成。

## B算法函数

`recal_algorithm.evaluate(request)`纯数值、无硬件访问，C在可终止子进程执行。请求含contract/request_id/scene_id/phase/identity/attempt/run_dir/training/validation/plan；phase为input/fit/validate。

回复带同一contract/request_id/scene_id，decision只能为valid_pass/data_insufficient/model_rejected/retry，必须有reason。retry仅能前进到预封装策略下一个attempt；策略attempts为1..3项，每项含training/validation计划。C不猜阈值、不现场扫参数。

fit通过附model_path/model_sha256；模型沿用load_candidate的512 taps/Q20格式，fixture_id为scene_id。validate通过必须附同一model_sha256、实际validation_ids、qualifies_cancellation:true、evidence；独立验证不得重用训练capture_id/source_sha256。无保护不等于通过，不可评价就data_insufficient。

## 最小输入输出样例

请求（省略identity展开）：`{"contract":"recal-product-v1","request_id":"r1","scene_id":"s1","phase":"validate","model_sha256":"<64hex>","validation":[{"capture_id":"v1","path":"...","sha256":"<64hex>"}]}`。

回复：`{"contract":"recal-product-v1","request_id":"r1","scene_id":"s1","decision":"valid_pass","reason":"B既定判据通过","model_sha256":"<同一64hex>","validation_ids":["v1"],"qualifies_cancellation":true,"evidence":{"policy":"B版本/判据","metrics":"派生路径"}}`。

## 状态和事务

待标定→准备→讲话输入检查→安静→训练捕获→拟合→独立验证→安装→就绪→运行→真实结束。任一步可取消/失败/保护停声。移动后按重标定先静音、使旧current失效并生成新scene。候选独立验证后写不可变模型/配置bundle，静音安装核实际回读，最后原子替换current.json；失败不恢复旧场景模型。重启默认待标定。

结果分valid_pass/data_insufficient/model_rejected/input_overload/hardware_error/user_cancelled/protected；听感另列，不代替B数值判断。操作说明见[产品操作单](../ref/recal-product.md)。
