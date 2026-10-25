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

冻结真人包的实际资产字段是`preflight.a_assets`，不是空的`assets`。本次冷启动报告把它经实际文件核对后映射为
非空`assets`；源码生成器也增加同值兼容别名，并保留旧字段。已冻结真人ZIP不修改，本轮不另发真人包。

已验证环境及正式产物摘要在发布后的本文件下方记录；其他环境须以实际命令结果为准。
完整历史与不适用范围见[集中实验验收](../../report/verification/audio_closed/batch-control.md)。
