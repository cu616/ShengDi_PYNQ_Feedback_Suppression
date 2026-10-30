# 仓库定位与同步

本地文件夹与远端仓库可以不同名。先用 `git worktree list`、`git branch --show-current` 和 `git rev-parse --show-toplevel` 确认所读版本；不要把主目录自动当成最新开发目录。

队长这台电脑的 A 工作区是 `D:/OCadence_Project/Flushbonading_FPGA_Contest/_a_work/wt-a`；根目录是另一个 main 工作区。其他电脑按自己的实际克隆路径定位，跨设备交接使用分支、提交与仓库相对路径。下面根目录路径只作定位示例。

## Git Bash 定位

```bash
cd /d/OCadence_Project/Flushbonading_FPGA_Contest
pwd
git rev-parse --show-toplevel
git remote -v
git status
```

工作区根目录以 `git rev-parse` 输出为准，也可以是独立 worktree。origin 应指向 `cu616/ShengDi_PYNQ_Feedback_Suppression`，HTTPS 或已配置的 SSH 均可。不要为匹配本文示例擅自修改远端。

也可在任意 Git Bash 目录执行：

```bash
source /d/OCadence_Project/Flushbonading_FPGA_Contest/scripts/enter-repo.sh
```

使用 source 才能改变当前终端的目录。脚本按自身位置定位项目，显示根目录、远端及状态。已经打开的其他 Git Bash 窗口不会自动切换目录。

## 日常同步

团队功能开发先按 [AI 开发规范](../rules/ai-development-policy.md) 在各自工作目录和任务分支进行，下面是当前任务分支上的提交操作。合并到 main 前由另一名队友核对改动和验证情况。

```bash
git status
git add <本次修改的文件路径>
git diff --cached
git commit -m "Describe the change"
git push -u origin HEAD
```

队友在其他电脑克隆同一远端。tmp/ 不上传；可交付证据放入 report/verification 并注明身份，原始录音保持既有授权范围，不能因整理目录自动上传。不要将账户凭据放入仓库。本次建仓沿用已有 Git 提交身份，不修改全局配置。
