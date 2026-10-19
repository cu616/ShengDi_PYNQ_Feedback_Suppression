# Vivado 2018.3 PYNQ-Z2 板卡定义安装

- 用户授权：检查 D:\Xilinx\Vivado\2018.3 的板卡安装并代劳。
- 日期：2026-10-14。执行者：AI；模型精确版本未知。本文为执行摘要。
- 仓库：main，已有未提交修改，未提交或推送。
- 目标：安装缺失的 PYNQ-Z2 定义并由实际 Vivado 识别。

## 来源和变更

TUL 旧产品页面返回 404，PYNQ 支持论坛提供的 CloudFront 下载链接出现 TLS EOF；GitHub API 限流、git ls-remote 连接重置。最终从 https://github.com/xupsh/pynq-supported-board-file 的 master/pynq-z2/A.0 下载四个文件。未能固定 Git 提交；以下载内容 SHA256 留证。第三方文件保留原文，本次没有将其纳入项目发布或赋予新许可证。

安装位置：D:/Xilinx/Vivado/2018.3/data/boards/board_files/pynq-z2/A.0。目标此前不存在，复制时明确拒绝覆盖已有目录。未改其他板卡文件。

| 文件 | SHA256 |
|---|---|
| board.xml | A565DCB39737D551CBBBB73C0053B973C40BB3DCE2274943370D3032C0FEA9AE |
| part0_pins.xml | 3C809473938E135A925B563B5371C8687EE05C4089376E7318C0C56524CC8A0F |
| preset.xml | 18528F84AEA4DA503CDB3104F7706FABFB3B6AD09B78B25199CC316AFA4C8CFE |
| pynq_z2.jpg | B6CF32FEBF4B1995F33C3372EF72F390ABF4A5596C73A6FD36810A45CCD0E1F7 |

## 实际验证

先用临时 board.repoPaths 预检查，再复制安装，最后在不传 repoPaths 的新 Vivado batch 会话运行：查询 get_board_parts、查询 get_parts、创建内存工程、设置 board_part 并回读。

结果：VIVADO_VERSION=2018.3；VERIFIED_BOARD=tul.com.tw:pynq-z2:part0:1.0；VERIFIED_PART=xc7z020clg400-1；BOARD_SETUP_PASS；进程退出码 0。

本地临时证据：tmp/board-setup/check_board.tcl、preflight.log、installed-check.log。首次沙箱启动报 Access is denied，获执行权限后同一命令成功。没有综合、实现、许可可用性验证、音频工程构建或板卡操作。

## 恢复和下一步

如需撤销，关闭 Vivado 后仅移出本次新增的 pynq-z2 目录，保留其他目录；本轮未执行撤销。已打开的 GUI 可保存工作后重启再查看 Boards 中的 pynq-z2。后续选择与 2018.3 配套的音频参考工程，不能由板卡定义识别成功推断新版 PYNQ 工程可直接重建。
