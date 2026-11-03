# 官方模板技术报告

由队长维护。此目录保存正文、模板副本和图源；最终文档位于 `materials/final/shengdi-technical-report-review.docx` 与同名 PDF。2026-11-03 交付为审阅稿，共 14 页，保留三个待拍照片位置。

## 修改入口

- [report.md](report.md)：报告正文，按官方五部分顺序组织。
- [build_report.py](build_report.py)：生成 Word、六张 SVG 和对应 PNG；需要 python-docx、Pillow，以及 Windows 微软雅黑字体。
- [figure-data.json](figure-data.json)：两张结果图的数据与来源；数字修改需同时修改生成器中的 `data` 和绘图参数。
- [artifact.md](artifact.md)：官方模板的版式与保留规则。
- [build-audit.json](build-audit.json)：模板哈希及包内原件保留检查。
- [figures](figures)：系统框图、连接图、重标定流程、定点数据通路、322 Hz 对照和拨码事件图；SVG 可用 Inkscape/浏览器打开编辑。

正文中的 `@figure`、`@photo`、`@equation` 和 `@break` 是生成器标记。Word 可直接编辑；若修改 Word，请勿直接重跑生成器覆盖，先将必要改动同步回正文。

在仓库根目录运行 `python materials/work/report/build_report.py` 生成 Word。用 Word 打开后导出同名 PDF。此次使用 Codex 捆绑 Python 生成，本机 Word 导出 PDF，pypdfium2 渲染后逐页查看；14 页无空白页。PDF 为 727834 字节，低于页面要求的 50 MB。

## 补拍与定稿

1. 整机正面：板卡、麦克风、音箱全部入镜，说明真实使用布局。
2. 斜 45° 全景：拍清设备相对位置、音箱朝向和讲话位置。
3. 接线近景：清楚显示 LINE_IN、HP+MIC、麦克风前放、供电及 SW0 区域。

手机横拍、原图保存即可。采用最终演示配置，画面避开校名、校徽、指导教师姓名和无关个人信息。照片补到第三部分对应位置；有真实终端运行画面时可补进 3.2.3。完成后删除待拍说明并重新导出 PDF。

代码阅读基线是 main `87ff28c`；同步时新增的 `8903a24` 仅涉及展示材料。本报告未修改工程代码、未操作板卡。当前判据修订与整机状态以 [STATE](../../../docs/STATE.md) 为准；收到最终整包验收后，更新 3.2.3、3.3.3 中的版本和完成情况，避免直接将历史 v3 数据标成新包实测。

## 证据索引

- 定点与宽残差实现：`src/rtl/feedback_fir.v`、`src/rtl/audio_pl_replay.v`。
- 当前算法与产品组织：`board/audio_replay/recal_algorithm.py`、`recal_product.py`、`hw_api.py`。
- 322 Hz 对照：`report/verification/audio-replay/wide-residual-v3/C-tone-1746930178556850644.json`；共同源激活窗，不使用整窗旧值。
- 最新按键标定和 SW0 事件：`report/verification/audio-replay/demo-protocol-2026-11-02/README.md` 第十七节及相关记录；事件时间线为日志重绘。
- 历史资源、时序和使用记录：`docs/STATE.md` 关键数字及其链接；报告逐项注明版本或配置。

定稿前保留实测条件；无需为完善报告重新开展参数扫描。需要补充的是实际照片与最终包的既有验收结论。

2026-11-03 初改：关键词改为声反馈抵消、逐帧定点处理、声学通路重标定；1.5 节以 FPGA 运算时序、定点余量和模型更新方式说明技术贡献。正文、Word/PDF 同步提交，其他人优先修改 report.md 后重新生成。
