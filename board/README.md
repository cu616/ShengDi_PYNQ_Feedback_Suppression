# 上板程序

各audio_*目录包含独立overlay的bit/hwh和Python操作脚本，分别用于基础通路、快照、数字诊断、音调、连续采样及开环标定。它们互相替换，不是依次串联的处理模块；脚本、bit和hwh必须匹配。

各文件用途见 [工作区系统框图](../docs/workspace-architecture.md)。板上原始Notebook、训练/验证NPZ及候选模型JSON尚未备份进本地工作区，位置见 [交接说明](../docs/handoff-2026-10-17.md)。不要Run All重复执行声音测试。
