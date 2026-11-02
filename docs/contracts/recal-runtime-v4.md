# C 整机安装与运行证据扩展 v4

状态：软件接入验证；真实运行按冻结包门槛执行。
生产方：C 编排 / A 硬件；消费方：A / C；B 数值接口不变。
最后变更：2026-11-02；适用 A 28051a6 及后续兼容版本。

沿用 [v3](recal-runtime-v3.md) 的唯一 recal_entry.sh、B identity/evaluate、三档计划及停止收尾语义。本扩展接收 A 已提供的字段，不要求 B 修改阈值、模型或返回结构。

## 安装事务

安装期间允许静音开环增益0；安装完成后必须回读封装的运行增益，再提交当前指针。真实包要求 loaded_count=taps=512、reported_coefficients_sha256 与已验证候选的 Q20 SHA 一致。

A 可返回 scene 绑定副本的 model_sha256，同时提供 source_model_sha256 指向 C 发出的已验证原模型。C 只在本轮目录内找 SHA 吻合的副本，逐项比较 JSON 内容；仅允许 fixture_id 绑定本轮 scene，其他字段和 Q20 不变。副本再次经过既有模型格式检查后归档、原子提交；保存原模型 SHA、原数值验证回执和安装回执。源身份缺失、内容改变、读回不全或安装失败都不能启用候选。一个回包保存拟合原件和实际安装模型两份身份。

## 运行时长

A 28051a6 的 elapsed_seconds/audio_frames 是最后采集环窗的时长和帧数，wall_seconds 是初始化加等待的墙钟。C 原样保留，不把16384帧当完整运行。C 从该次原 NPZ metadata_json 复核 completed_frames、first_frame+frames、sample_rate_hz、done、stop_reason 和模型/Q20 SHA；计算 audio_elapsed_seconds=completed_frames/sample_rate_hz，再与请求时限比较。缺证据或提前结束均不会自动拼段或记为完成。

## 静音启动零模型

真实包可含 bootstrap-model.json：512个零系数，仅满足 A 开环初始化的文件协议，bootstrap_only=true、eligible=false，来源写明程序生成、没有测量模型证据。路径和字节列入包清单，启动时解析为绝对路径，不依赖当前工作目录或用户选择模型。ModelStore 拒绝将它安装为有效标定结果；每次启动和移动后的 current 仍先失效，只有本轮拟合、独立验证及装载核验成功才能扩声。初始已静音的 prepare 阶段允许 A 已批准的上次增益，开环开始后为0；就绪/扩声仍严格绑定本包运行增益，不放宽运行白名单。

A 返回原件可能落在上次硬件调用目录，C仅从自身独立 state 根内按本次请求/场景标记和原件 SHA 接入当前 scene，保留路径/字节。移动后不因落盘位置兼容而恢复旧模型。

## 四灯提示

产品入口向 A 传显式 pattern，不沿用硬件层示例程序的 ready 图案。LD3 在运行时独立显示实际模式，因此就绪/自然结束用0110，运行抵消用0001，运行旁路由 A 加 LD3 成1001。0001准备阶段须继续等待；嵌入 input 同样保持等待灯，只有三连音结束才提示讲话，避免在重新下载前亮“请讲话”。0100表示安静采样，1111表示未通过/保护并静音；普通用户按操作单执行，不依赖颜色或日志。

## 取消边界

cancel_event 是 perform 的第二个参数；必须传给包括 install/prepare 在内的驱动调用。驱动初始化后、解除 codec 静音和 arm 之前，使用现有 before_start 再检查该 Event。预取消及初始化中取消都不得继续开声。C 已即时 abort 并等待旧调用返回，不要求强杀线程；等待本身不能阻止旧调用重新 arm。存在该缺口的源包仅供审阅，现场/维护启动均关闭。

操作及取件见 [统一操作单](../ref/recal-product.md)。
