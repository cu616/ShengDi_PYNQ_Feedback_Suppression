# 2026-10-20 A：预录语音程序交付记录

用户要求：“能不能先录好再播放同时实时打开麦克风监听声音”，
随后确认“可以，下次结束工作时请交付可运行的程序”。
本次实现独立的数字声源注入路径，让手机停止外放后由音响发声，并同步采集麦克风。
未连接板卡、未加载overlay、未播放或传输现场录音。

## 交付

- [现场操作](../../../board/audio_replay/README.md)：完整路径、上传确认、三格Notebook定位及结束文件。
- [独立接口](../../../docs/contracts/audio-replay-v1.md)：新overlay与实际输出公式。
- `board/audio_replay/`包含配套bit/hwh、三格Notebook、驱动、manifest和说明，共10项。
- `scripts/package_audio_replay.py`从已通过时序的构建生成包及哈希；压缩包在`build/packages/audio-replay.zip`。
- B算法、C旧驱动和audio_closed旧RTL未修改；复制的两个纯计算辅助模块保持原字节。

配置复用板卡原`field_setup.json`及`candidate_box_v1_256.json`，运行时保存哈希。
固定Codec 40、256抽头Q20、48828.125 Hz。直放增益为0；
旁路/抵消请求−35 dB，实际Q12为73，其他配置及注入PCM完全相同。
录音默认2秒，播放含0.4秒尾段；只在静音配置完成后提示START。
源峰值按量化模型和实际环路增益限制，失败/取消均保存阶段和原因。

## 实际执行的检查

| 检查 | 结果与证据 |
|---|---|
| 软件回归 | 70项通过，含新增8项；[原始输出](software-tests.txt) |
| 混合Verilog/VHDL仿真 | `AUDIO_REPLAY_PASS`；[输出](rtl-simulation.txt)。独立解码I2S，覆盖声源叠加、实际DAC历史、bypass、环形缓存、饱和、超时/停止及无源拒绝 |
| Vivado 2018.3综合布局布线、bit生成 | 最终WNS +0.413 ns、WHS +0.035 ns，受约束路径满足时序；[完整报告](timing.txt) |
| 资源 | LUT 3203，寄存器5013，BRAM 112/140，DSP 3；[报告](utilization.txt) |
| DRC | 保留DSP流水寄存器建议等警告；[完整报告](drc.txt) |

第一次布局布线WNS为−0.348 ns，未交付该bit；[失败报告](initial-timing-failed.txt)保留。
在声源BRAM读出至混音路径增加一级寄存器后重新仿真和完整构建得到上表结果。
外部I/O仍缺1输入/3输出延迟约束，因此不是完整板级时序签核。
打包检查同时拒绝setup/hold/pulse-width失败或RTL晚于bit的构建。

复现入口：

```powershell
python -m unittest discover -s sim/feedback
vivado -mode batch -source build/scripts/test_audio_replay.tcl
vivado -mode batch -source build/scripts/create_audio_replay.tcl -tclargs build
python scripts/package_audio_replay.py
```

本机Python通过`-X utf8`运行；临时目录设在本克隆的`tmp`以避开系统临时目录权限。
打包后核对10个ZIP成员与本地文件逐字节一致，Notebook三格可编译，manifest核对通过。
最后修正异常时长标志后，8项新增测试再次通过。文档扫描101份，0错误/0警告。
文档检查器会错误跳过绝对路径中含`tmp`的整个克隆；本次通过以仓库相对路径过滤
`.git`与`tmp`的运行时适配执行检查，不改B的公共检查器。

## 剩余一次现场动作

按操作页上传10项，复用既有现场配置。音响断电录2秒，停止手机外放后恢复音响供电，
完成直放、旁路、抵消三项，最多约7.2秒发声。只有听感1且数字检查通过继续，
否则停止并返回该次summary；持续尖叫立即切断音响电源。

**状态更正（2026-10-28）**：这条路径自 2026-10-20 起已在板上运行，v3 位流自 2026-10-27 起在板上
（`48e38f78…`；驱动当前为 `c2b2a86a…`）。本文件下方按当时状态保留的叙述不再代表现状，现状只看
[STATE](../../../docs/STATE.md)。不能预先保证音响响度、音质或抵消有效。保存的末尾 16384 帧主要是
声源关闭后的尾段，不代表整个语音段。全程内部饱和计数也不等于全程 ADC 监测
（v3 起另有 `capture_status` bit22 输入满幅粘滞位，并可让驱动停声）。
若两模式均正常，结论是已测范围未找到旁路失稳阈值；不输出精确MSG/ASG。
如直放无声，停止后续两项，依据输出电平和现场音量处理可听性问题。

恢复：关闭音响，重启Notebook内核，再执行文件核验；保留已有source.wav及结果。
运行器正常结束/异常均尝试恢复base overlay和Codec静音；恢复失败须先处理错误，
不能直接重跑。2026-10-21同步新版[协作规范](../../../docs/WORKFLOW.md#8-线间协调人来做)后，旧诉求表已撤销；接口依据保留在契约中，给B/C的提示词交由用户微信转发。


## 2026-10-21 逐档批次交付

用户要求“那就请你继续干，一次性交付”，针对上一版只运行固定−35 dB的缺口。
新增A的`sweep_plan.py`、`sweep_session.py`，复制B的calibration原字节为`replay_calibration.py`供独立上传。
未改B算法或C驱动。新版13文件包/三格Notebook先读已有数据选档，源PCM与电平整批固定，
每档抵消→旁路，异常停止升档，先前完成项留在summary。原固定档入口保留兼容。
新增[逐档批次契约](../../../docs/contracts/audio-replay-sweep-v1.md)，硬件寄存器/bit不变。

语法编译、文件打包与文档检查已执行；未执行新版软件单元/回归测试、板卡静默分析或声音试验。
上表70项测试属于旧版，不构成本版选档/批次逻辑已验证的证据。RTL未改，未重复仿真/综合。
本克隆没有真实训练/验证NPZ，因此不能预先填写实际增益档位或宣称已能达到正常音量。
各档由真实数据规划；不足两档或没有模型改善会保存停止原因，不自动退回单档低增益重复试验。

源电平用拟合模型的分组级数峰值上界约束，频响范围含格点间导数补偿、训练/验证差异与6 dB裕量。
它依赖夹具与已有数据的适用性，不能保证实物稳定。实际停止依赖硬件预算、饱和轮询和现场断电；
听感逐项记录，未找到阈值如实结束。第1格失败返回摘要，不进入录音/播放。


## 2026-10-21 Notebook文件哈希误判修复

用户返回`sweep_cf1d5905f628`摘要：status=stopped，stage=package，trials/pairs为空，sound_seconds_completed=0，stop_reason指向replay_trial.ipynb文件哈希不匹配。
未拿到板卡Notebook原文件，不能确定是否仅输出变化；确认旧实现会把Jupyter保存的执行次数/输出/元数据变化误当版本变化。
修复为Notebook按顺序的代码格source规范JSON摘要，其他程序/bit/hwh仍逐字节哈希。Notebook代码变化继续拒绝。
同步更新打包脚本及manifest；现场只覆盖replay_session.py和manifest.json再运行第1格，无需重录。
未执行新版软件回归或板卡运行；只执行语法、打包和文档检查。此报错没有新增采样或发声证据。


## 2026-10-21 SSH接管与按钮页

用户授权使用默认xilinx账号登录，后续代码/调试由A承担，现场希望只点按钮判断听感。
固定SSH主机密钥后确认板卡仍装旧manifest（含Notebook整文件字节哈希），且Jupyter目录属root。
首轮SFTP直接写入被权限拒绝；部署辅助脚本文本替换错误在执行前产生SyntaxError，没有改程序。
修正后经sudo先板上备份，再更新程序并逐文件核对。备用目录为板卡audio_replay下的deploy-backup-*。
密码、会话令牌及临时认证材料未提交仓库。

包核验通过后执行真实标定数据静默分析；第一版3 dB网格不足两档而停止。
按原上限以内追加向下取整的0.5 dB末档，再次分析成功，实际Q12均不越原保护上限。
见[原始静默摘要](board-plan-2026-10-21.json)；该文件不含PCM，声音试验项仍为空。

增加标准库按钮页：服务启动不加载overlay；用户确认音响断电后录音，READY/START/听感改为按钮。
页面单工作线程与提示ID拒绝重复输入；停止后续按钮不作为实时急停。
SSH部署15项核对通过，HTTP只读读取确认busy=false、plan_ready=true、source_exists=false、waiting=null。
内置浏览器打开尝试超时，未据此宣称界面截图验收；电脑通过HTTP读取页面与状态成功。
未点击录音/播放，未执行本版自动化回归；本轮验证范围为语法、部署、板卡静默分析和HTTP连通。
按钮页及源文件受manifest校验；未修改RTL、未重复综合仿真。服务器当前由A独占管理。


## 2026-10-21 按钮页录音环境修复

- 用户反馈点击录音后没有后续按钮。HTTP状态：busy=false、source_exists=false，日志重复ModuleNotFoundError: No module named 'pynq'；实际录音未开始。
- 原服务用了/usr/bin/python3。通过SSH仅导入确认/usr/local/share/pynq-venv/bin/python可加载pynq、BaseOverlay及录音API，未实例化硬件。
- 更新click_panel.py、click-panel.html、manifest.json；部署后15项文件哈希核对通过。错误直接显示，阻止失败后重复点击；录音完成提示点击“2 开始本批”。
- 确认服务空闲及PID命令行匹配后重启自己的服务，使用正确解释器。保留原计划、会话链接；启动加入PYNQ导入检查。
- 重启后HTTP：busy=false、error=null、source_exists=false、plan_ready=true；运行日志记录正确解释器路径。未触发录音、播放或传输原始PCM。实际现场操作仍待用户点击。


## 2026-10-21 SSH环境缺少XRT

用户截图显示RuntimeError: No Devices Found，仍未生成录音。读取板卡pl_server/__init__.py确认只有XILINX_XRT环境存在时才注册EmbeddedDevice。系统/etc/profile.d/xrt_setup.sh设置XILINX_XRT=/usr；boardname.sh读取实际板型。加载后设备枚举结果为EmbeddedDevice / embedded_xrt0，BOARD=Pynq-Z2。本次仅枚举，未下载overlay或启动音频。

新增start-panel.sh统一加载官方环境及PYNQ虚拟环境；面板启动预检设备，避免再次把环境错误留到用户点击录音后。部署核对16项文件，备份目录deploy-backup-20261021-173758。旧服务确认空闲且PID身份匹配后重启，保留会话与计划。实际录音、播放仍待用户触发。


## 2026-10-21 录音初始化线程事件循环

用户截图报RuntimeError: There is no current event loop in thread 'Thread-278 (work)'。板卡pynq/uio.py第74行在构造UIO控制器时调用asyncio.get_event_loop().add_reader；旧面板每次新建后台线程且未设置事件循环。

面板改为max_workers=1的持久执行器，线程初始化时创建并设置事件循环，录音、批次和清理复用同一线程，避免UIO对象跨任务失去所属循环。启动预检向实际工作线程提交get_event_loop，异常保留完整栈。16项部署文件核对通过，备份deploy-backup-20261021-174532；重启前确认busy=false及PID命令行身份。未触发录音、播放；此次设备与事件循环预检不代表完整音频初始化已通过。

## 2026-10-25 只读独立复核证据

[复核数据](independent-review-2026-10-25.json) 保存包哈希核验、相位穿越反例、闭环元数据和频域重算方法/输出。计算在前一轮只读复核执行，本轮归档；没有新增板卡试验。解释见 [复核答复](../../analysis/2026-10-24-situation-and-limits.md#独立复核答复2026-10-25)，发布数字以 [STATE](../../../docs/STATE.md) 为准。
