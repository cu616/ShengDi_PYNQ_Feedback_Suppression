# 冷启动软件复现

维护者C；用于10/28冻结前的离线资产与部署算术复现。只使用Python标准库和Git，
不安装依赖、不连接板卡、不调用PYNQ。真实人声、板端独立复现和全程声学仍另行验收。

在固定C提交的干净检出根目录执行一条命令：

```text
python tools/deliver_check.py cold-start
```

命令核对`tools/delivery-freeze.json`中的源文件和冻结实验ZIP，逐项检查bit/hwh/模型/Q20，
用部署系数独立复现−12/−6/0三点软件增益映射与FIR整数算术。版本与实际文件不符立即失败。
输出在`build/generated/delivery/`：`cold-start.zip`、`cold-start.json`、`docs/cold-start-reproduction.md`。
报告记录真实固定Git提交、检出是否干净、实际运行时和每个哈希；最后一行必须是
`PACKAGE_COMPLETE <该ZIP的SHA256>`且退出0才算交付。D1参数、D2哈希、D3缺项、D4语义/环境失败均返回2，
不打印完成行。其他来源的ZIP不能只靠自写的all_ok通过。

复核既有交付包无需重新生成：

```text
python tools/deliver_check.py build/packages/c-cold-start-r1.zip
```

## 在后续集成树中复核历史r1

`tools/delivery-freeze.json` 的五项 `source_sha256` 固定的是 `be3200e` 的历史r1源码，
仅将CRLF归一化为LF；不是当前v3提交候选的源清单。两项后续源文件变化不能触发重钉旧清单。
当仓库树任一源哈希与它不符时，该树不再是r1重建入口，直接运行仍应报D2，不能跳过检查。

需要重建r1时，从 `be3200ecf4a5b1df8901f1111da4685c0f8fedc8` 的独立干净工作树运行上述命令。
只读复核现有r1时，将 `build/packages/c-cold-start-r1.zip` 解压到独立目录，再用其中的
`tools/deliver_check.py` 检查原ZIP的绝对路径；只读核验不需要新建Git历史，也不操作板卡。
该ZIP的SHA256为 `aba7466c675dd1829cbfae8a0db03621bac21a210692eac50923da0cedee790a`。
全量软件测试中的 `test_delivery.py` 显式核验此归档哈希并读取其五项冻结源码；不跳过测试，
仍检查源篡改D2拒绝、资产篡改与重新计算外层哈希后伪造报告的拒绝。当前v3身份另由v3 manifest核对。

冻结真人包的实际资产字段是`preflight.a_assets`，不是空的`assets`。本次冷启动报告把它经实际文件核对后映射为
非空`assets`；源码生成器也增加同值兼容别名，并保留旧字段。已冻结真人ZIP不修改，本轮不另发真人包。

已验证环境及正式产物摘要在发布后的本文件下方记录；其他环境须以实际命令结果为准。
完整历史与不适用范围见[集中实验验收](../../report/verification/audio_closed/batch-control.md)。

## 本次干净检出实测


固定检出：`be3200ecf4a5b1df8901f1111da4685c0f8fedc8`；clean_checkout=true。

bit SHA256：`61bb71aabb824c57191edcea93d1333143cd959c16d43028585913c54a8f61fa`

hwh SHA256：`92b499a39d04de891632a89512bfff49f7482a332344128556b1506529d1b75b`

模型文件：`c8be7f78e7ccb73c8b023aa9e74ddaa0914bc4dabf1e2de91ce46114a0679f9a`；Q20：`c9d3b1e658fd2ed8b731904eaa1f2bec62677b732f5bebe1acf34f1d96fa2160`；taps=512，lag_first=1。

原包48个载荷逐项一致，三点部署算术与增益映射通过。

原冻结preflight的资产字段为a_assets；本报告assets为其经实际文件哈希核验的兼容映射。

仅离线资产/软件夹具复现；未操板，不完成另一位队友的现场独立复现。

已在CPython 3.14隔离模式（-I -S，无site-packages）通过，另从独立解压目录使用包内检查器复核退出0。
