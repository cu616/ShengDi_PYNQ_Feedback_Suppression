# 仓库定位与同步

本地目录保持为 D:/OCadence_Project/Flushbonading_FPGA_Contest。远端名为 ShengDi_PYNQ_Feedback_Suppression；本地文件夹和远端不同名不影响使用。

## Git Bash 定位

```bash
cd /d/OCadence_Project/Flushbonading_FPGA_Contest
pwd
git rev-parse --show-toplevel
git remote -v
git status
```

根目录应为 D:/OCadence_Project/Flushbonading_FPGA_Contest 或对应的 /d/...。origin 应为 https://github.com/cu616/ShengDi_PYNQ_Feedback_Suppression.git。

也可在任意 Git Bash 目录执行：

```bash
source /d/OCadence_Project/Flushbonading_FPGA_Contest/scripts/enter-repo.sh
```

使用 source 才能改变当前终端的目录。脚本按自身位置定位项目，显示根目录、远端及状态。已经打开的其他 Git Bash 窗口不会自动切换目录。

## 日常同步

团队功能开发先按 [AI 开发规范](ai-development-policy.md) 在各自工作目录和任务分支进行，下面是当前任务分支上的提交操作。合并到 main 前由另一名队友核对改动和验证情况。

```bash
git status
git add <本次修改的文件路径>
git diff --cached
git commit -m "Describe the change"
git push -u origin HEAD
```

队友在其他电脑克隆同一远端。tmp/ 不上传，正式实验数据放入 data/ 并写说明。不要将账户凭据放入仓库。本次建仓沿用已有 Git 提交身份，不修改全局配置。
