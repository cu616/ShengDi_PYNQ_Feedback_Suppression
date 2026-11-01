# 常驻重标定产品接口 v1

状态：C接口/模拟实现；A/B真实适配及实体验收待交付。用户2026-11-01明确授权新接口，不改变原寄存器/算法语义。

统一版本`recal-product-v1`。C拥有唯一`recal_entry.sh`、`recal_product.py`及`assemble_experiment.py`产品分支。A拥有`hw_api.py`及驱动/实体I/O；B拥有`recal_algorithm.py`及数值依赖。A/B不再改入口。原`experiment.py`、`layout_experiment.py`保留离线验收用途，不是第二个正式产品入口。

## A硬件对象

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
