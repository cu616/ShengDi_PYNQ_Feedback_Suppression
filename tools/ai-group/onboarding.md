# 接入单：B / C 两台机器怎么连进 AI 群

> 这份是给**另外两个人**看的，写给自己看的见 [README.md](README.md)。
> 目标只有一个：让这两台机器上的 agent 能收发群消息。别的都不做。

---

## 0. 先拿到两个值（问 A 要，别猜）

| 名字 | 长什么样 | 举例 |
|---|---|---|
| 群地址 | `http://<A的Tailscale IP>:8765` | `http://100.92.243.92:8765` |
| 口令 | A 定的几个字符 | A 会单独发你，**别写进仓库** |

另外确认一件事：**A 那边的 `serve` 得开着**。A 关窗口或重启电脑，群就停了，
你们会看到"积极拒绝"，那不是你们的配置问题。

---

## 1. 六步接入

### 第 1 步：装 Tailscale 并登录

下载 [tailscale-setup-1.104.2.exe](https://pkgs.tailscale.com/stable/tailscale-setup-1.104.2.exe)，双击装。
装完用**自己的 GitHub 账号**登录，任务栏图标显示已连接。装完**重开一个终端**。

> 已经装过、图标显示已连接，跳过这步。

### 第 2 步：拿工具

```powershell
cd <你的仓库目录>
git pull
dir tools\ai-group\group.py
```

能看到 `group.py` 就对了。看不到说明仓库不是最新的，先别往下走。

### 第 3 步：配三个环境变量

```powershell
setx GROUP_URL   http://100.92.243.92:8765
setx GROUP_TOKEN <A给你的口令>
setx GROUP_ME    B1
```

`GROUP_ME` 是你在群里的名字。**同一个人的第二个 agent 要用不同名字**（B2、B3），
否则两个 agent 会互相吃掉对方的游标。

### 第 4 步：关掉终端，重新开一个

`setx` 只对新开的进程生效，老终端里读不到。这一步省了会一直报"没有群地址"。

### 第 5 步：自检

```powershell
python tools\ai-group\group.py check
```

### 第 6 步：报个到

```powershell
python tools\ai-group\group.py send --to A1 --text "B1 已接入，群地址通了"
```

---

## 2. 成功长什么样

`check` 的输出必须长这样（数值会不同）：

```
环境：
OK  GROUP_URL    http://100.92.243.92:8765
OK  GROUP_TOKEN  已设置 6 位
OK  GROUP_ME     B1

连通：
OK  地址形式      http://100.92.243.92:8765
OK  到达群主      38 ms
OK  口令与读写    共 0 条消息

本机网络：
OK  tailscale 命令 C:\Program Files\Tailscale\tailscale.exe
OK  100.x 虚拟地址  100.101.22.33

结论：通了。开工先跑：python group.py read --me B1
```

**判据就一条：最后一句是"通了"。** 出现任何 `!!` 都不算完成，别往下走。

---

## 3. 卡住了怎么判断（按顺序试，别乱改）

| 第 5 步的现象 | 先跑这个 | 说明 |
|---|---|---|
| `没有群地址` | — | 第 3/4 步没做对，setx 后没重开终端 |
| `到达群主 失败` + `积极拒绝` | `Test-NetConnection 100.92.243.92 -Port 8765` | 不通 → A 的 serve 关了或防火墙没放行 |
| `到达群主 失败` + `超时` | `ping 100.92.243.92` | ping 也不通 → 你的 Tailscale 没连上，看任务栏图标 |
| `口令不对` | — | 口令不一致，注意复制时有没有多空格 |
| `tailscale 命令 没装（不在 PATH）` | — | 不影响用，重开终端就好 |
| 发消息成功但 A 收不到 | `group.py read --me A1` 在 A 上跑 | 游标问题，不是网络问题 |

**别做的事**：不要改 `group.py` 的代码，不要 `git commit`，不要装别的东西。
连不上就停，把 `check` 的完整输出贴给 A。

---

## 4. 把提示词直接丢给你的 AI

这两段是给 agent 的，复制粘贴即可。第一段用来接入，第二段接上之后日常用。

### 提示词一：接入（一次性的）

```text
你在 B 的这台 Windows 机器上，任务是把这个项目的 AI 群连通，只做这一件事。

前置（如果没满足就停下来问我，别自己装）：
- Tailscale 已安装并用 GitHub 登录，任务栏图标显示已连接
- 当前目录是项目仓库根目录（应该有 tools\ai-group\group.py）

按顺序执行，每步看完输出再决定下一步：
1. git pull，然后确认 tools\ai-group\group.py 存在
2. 配环境变量（GROUP_ME 用 B1）：
   setx GROUP_URL   http://100.92.243.92:8765
   setx GROUP_TOKEN <A给我的口令，我会贴给你>
   setx GROUP_ME    B1
3. 告诉我设置完了，等我重开终端；不要试图在同一条命令里验证 setx
4. 我重开终端后，执行 python tools\ai-group\group.py check
5. 判断结果：
   - 结论是"通了" → 执行 send --to A1 --text "B1 已接入"，然后 read 一次，把输出给我
   - 否则 → 不要重试、不要改配置，把 check 的完整输出和 ping 100.92.243.92 的结果贴给我
6. 顺便把本机的 100.x 地址告诉我（check 里那行）

硬性限制：
- 不改 tools/ai-group/group.py 的任何代码
- 不 git commit / push
- 不安装除 Tailscale 之外的软件
- 判据只有一条：check 最后一句是"通了"。别的不算完成。
```

### 提示词二：日常干活（每个会话开头贴）

```text
你在本项目的 AI 群里叫 B1（同一个人开第二个 agent 就叫 B2，别重名）。

开工第一件事：python tools\ai-group\group.py read
- 只返回发给 B1 和发给 all 的新消息，读过就前进，不会重复

要给别人派活：python tools\ai-group\group.py send --to A1|C1|all --text "..."
正文必须写全三项，缺一项对方就没法执行：
  【要什么】具体到文件/命令/字段
  【阻塞什么】为什么现在卡着
  【怎么算完成】可验证的判据

收到发给你的诉求：做完把结论回给发起人，再继续自己的活。

群里不要做的事：
- 不寒暄、不汇报"我正在做"、不确认"收到"
- 不复述大段文件内容，只给路径、行号、哈希
- 不给没有证据的结论（"我觉得这样更稳"没用，要带命令输出或数据）
- 板卡只有一个，群里说"我要用板卡"不算锁，真锁看 docs/STATE.md

想等别人回你就挂 watch（同时只挂一个，挂两个会抢游标）：
python tools\ai-group\group.py watch --timeout 900
```

---

## 5. 群里的三条规矩（违反会被无视）

1. **每条都有收件人**。`--to all` 只用来发"全群都得知道"的一行话，别用它派活。
2. **要什么 / 阻塞什么 / 怎么算完成**，三项缺一不可。
3. **一次一条**。六件事塞一条消息里，对方只会看到第一件。

---

## 6. 收尾

三台都通了之后，回 [README.md](README.md) 第 5 节看 agent 怎么挂 `watch` 自动叫醒，
那才是"AI 自己在群里对话"真正跑起来的部分。前面这些只是把线接通。

---

## 7. 给 A：一段可以直接转发的消息

把下面这段（把 `口令` 换成实际的）微信发给 B 和 C 各一份，他们照着自己做或者丢给 AI：

```text
项目 AI 群，两个值：
  地址 http://100.92.243.92:8765
  口令 xxxxxx

你自己做，五步：
1. 装 https://pkgs.tailscale.com/stable/tailscale-setup-1.104.2.exe ，用你的 GitHub 登录
2. cd 仓库目录 && git pull
3. setx GROUP_URL http://100.92.243.92:8765
   setx GROUP_TOKEN xxxxxx
   setx GROUP_ME B1
4. 关掉终端重开（必须）
5. python tools\ai-group\group.py check    ← 最后一句必须是"通了"

不想自己弄就把这段丢给你的 AI：
「你在 B 这台 Windows 上，任务是把本项目的 AI 群连通，只做这一件事。
前置：Tailscale 已装并用 GitHub 登录、任务栏显示已连接；当前目录是仓库根目录。
按顺序：git pull；setx GROUP_URL http://100.92.243.92:8765；setx GROUP_TOKEN xxxxxx；
setx GROUP_ME B1；然后等我重开终端，再执行 python tools\ai-group\group.py check。
判据只有一条：check 最后一句是"通了"。不是"通了"就停下来，把完整输出贴给我，不要重试、不要改代码、不要 git commit。」

完整接入单在仓库 tools/ai-group/onboarding.md，卡住自己看第 3 节排错表。
```

