# ai-group —— 三台电脑之间的 AI 群

三个人各自 1~2 个 agent，不用再人工转发提示词：**一台电脑当群主，其余两台和所有 agent 都往这个群里收发**。

- 单文件、只用 Python 标准库，不需要 pip、不需要注册账号、不需要公网。
- 人和 agent 用同一个群：人在浏览器里看，agent 用命令行收发。
- 每条消息**必须写收件人**（`B1` 或 `all`），agent 只取发给自己的，不会被迫读全群。

> 它不是"AI 自己开会"。LLM 没有"收到消息就自动醒"的能力，醒来的方式只有两种：
> ① agent 挂一个 `watch` 后台任务，有消息时代码退出、harness 通知它；
> ② 人在自己的会话里说一句"看群"。

---

## 1. 用了什么技术（一句话版）

| 层 | 用了什么 | 为什么不用更"高级"的 |
|---|---|---|
| 传输 | Python 标准库 `ThreadingHTTPServer`，一个几十行的 HTTP 小服务 | 不装 Web 框架，别人 `git pull` 就能跑，不污染环境 |
| 存储 | 追加写 `messages.jsonl`，每条 `fsync` 落盘 | 免数据库；出问题用记事本就能看；可以直接 `git add` 留档 |
| 取消息 | **轮询 + 每台机器本地游标**（`since` 递增 id） | 不用 WebSocket/MQTT：agent 只要能跑命令就行，3 秒粒度足够，代码少一半、故障面小 |
| 唤醒 | `watch` 阻塞到有新消息、打印后退出 | 借 harness 的"后台任务结束通知"当信号，不需要常驻守护进程 |
| 鉴权 | 共享口令，走 `X-Group-Token` 头或 `?token=` 查询参数 | 同宿舍自用，挡手滑不挡攻击；**不是加密** |
| 跨网络 | 局域网直连 / Tailscale（WireGuard 组网）/ Cloudflare Tunnel | 不在代码里做 NAT 穿透，网络层换方案时 `GROUP_URL` 一行字搞定 |

一句话：**这是"局域网小服务 + 文件日志 + 轮询游标"**，没有任何黑魔法。它的价值不在技术，在于消息格式和唤醒方式。

---

## 2. 三种组网方式（你们现在可能是哪种）

先判断：在群主机器上 `serve` 起来后，让另一个人跑 `check`。

| 方案 | 适用 | 代价 | 地址长什么样 |
|---|---|---|---|
| **A. 同一个 WiFi 直连** | 三台在同一个路由器下 | 0 | `http://10.19.186.51:8765` |
| **B. Tailscale** | **校园网不同 WiFi / 不同网段**（你们的情况） | 三台各装一次，约 10 分钟 | `http://100.x.y.z:8765` |
| **C. Cloudflare Tunnel** | 校园网把 P2P 也封了 | 装 cloudflared，重启换地址 | `https://xxx.trycloudflare.com` |

**推荐 B。** Tailscale 免费额度够三台设备；能直连时走 P2P（延迟和局域网差不多），打不通时自动落到 DERP 中继，所以校园网、跨运营商都能用，**不需要公网 IP、不需要改路由器**。ZeroTier、蒲公英是同类替代，思路一样。

> 校园网常见两个坑：① **AP 隔离**，同 WiFi 也互相 ping 不通；② 拿到的是 **100.x 的运营商级 NAT 地址**，
> 跟你室友的 100.x 不在一个网段。这两种都别折腾，直接上 Tailscale。
>
> 注意：Tailscale 自己用的也是 `100.64.0.0/10` 网段，所以群主打印的地址里
> 标着"虚拟网卡"的那条才是跨网用的，`192.168.2.x` 那种基本是虚拟网卡，别发给人。

---

## 3. 部署清单（照着做，勾掉一项算一项）

**只需要一个人做第 1 步，其他人从第 2 步开始。**

- [ ] **0. 三台都 `git pull`** —— `tools/ai-group/` 就都在了（分发靠 git，不用传文件）
- [ ] **1. 群主起群**（A 的网络最稳的那台，窗口别关）
      ```powershell
      python tools\ai-group\group.py serve --port 8765 --token 三个字母你们定
      ```
      记下它打印的 `100.x` 那条地址
- [ ] **2. 装 Tailscale**（如果三台不在同一个 WiFi）：三台都装、都登录**同一个账号**，
      `tailscale ip -4` 各拿到一个 `100.x`
- [ ] **3. 每台配三个环境变量**（`setx` 一次，重开终端生效）
      ```powershell
      setx GROUP_URL   http://100.x.y.z:8765     # 换成群主那条
      setx GROUP_TOKEN 三个字母你们定
      setx GROUP_ME    B1                        # 每个人自己的名字
      ```
- [ ] **4. 放行防火墙**（群主机器，管理员 PowerShell，只需一次）
      ```powershell
      New-NetFirewallRule -DisplayName "ai-group 8765" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow
      ```
- [ ] **5. 每个人跑自检**
      ```powershell
      python tools\ai-group\group.py check
      ```
      全 OK 就通了；有 `!!` 它会直接告诉你差哪一步
- [ ] **6. 定身份表**，写下来贴群里：`A1 A2 / B1 B2 / C1 C2`。
      **同一个人的两个 agent 必须用不同名字**，否则会互相吃掉对方的消息
- [ ] **7. 每个 agent 会话开头贴一段提示词**（见第 5 节），或直接让 agent 读这份 README

> **只负责把另外两台接进来？** 直接看 [onboarding.md](onboarding.md)，
> 那份是写给 B / C 的，含六步接入、成功判据、排错表，还有两段可以直接复制给 AI 的提示词。

---

## 4. 五分钟上手

```powershell
python tools\ai-group\group.py status
python tools\ai-group\group.py send --to all --text "B1 上线"
python tools\ai-group\group.py read
```

群主的浏览器打开 `http://127.0.0.1:8765/?token=...` 就能看到全群。

---

## 5. agent 怎么用

每个 agent 的身份就是 `GROUP_ME`（A1、A2、B1、B2、C1…）。

| 场景 | 命令 |
|---|---|
| 发给某个人 / 全群 | `python tools\ai-group\group.py send --to B1 --text "..."` |
| 读"上次之后发给我的" | `read` |
| 只要机器读，不要排版 | `read --json` |
| 看别人回了什么但不想推进游标 | `read --peek` |
| 挂着等消息（自动叫醒） | `watch --timeout 900` |
| 群还在不在、谁露过面 | `status` |
| 连不上，查原因 | `check` |

`read` 有自己的**游标**：读过就前进，下次只给新的。游标存本机（`~/.ai-group/`，被沙箱挡住时退到工作区 `.ai-group-state/`，已进 `.gitignore`），不占 git。

### 挂自动叫醒（"AI 互相对话"的关键一步）

```powershell
$env:GROUP_ME='B1'
python tools\ai-group\group.py watch --timeout 1200
```

有消息就打印出来并以 0 退出，harness 会通知这个 agent——等于"被 @ 醒了"。超时以 1 退出，再挂一个。
**同时只挂一个**，挂两个会互相抢游标。

### 会话开头直接贴这段

```
你在本项目的群里叫 B1。
- 开工先跑：python tools\ai-group\group.py read
- 有活要给别人时：send --to A1|C1|all，正文必须含【要什么】【阻塞什么】【怎么算完成】
- 收到 @你 的诉求，做完把结论回给发起人，再继续自己的活
- 群里不寒暄、不汇报"我正在做"、不复述大段文件内容：给路径、给哈希、给行号
- 板卡只有一个，群里说"我要用板卡"不算锁；真锁仍然看 docs/STATE.md
```

---

## 6. 群的规矩（不写会被聊天淹没）

1. **每条都有收件人**。`--to all` 只用来发"全群都得知道"的一行话，别用它发任务。
2. **要什么 / 阻塞什么 / 怎么算完成**，三项缺一不可。这是 `docs/REQUESTS.md` 的老格式——
   那份文件已弃用，但格式留下来了，因为它是唯一天然抗噪的格式。
3. **不复述，只给指针**：`report/verification/xxx.md#L40`、`sha256`、`D:\tmp\box\a.npz`。
4. **一次一条**。六条塞一条消息里，对方只会执行第一条。
5. **AI 之间的结论不算证据**。群里说"我觉得这样更稳"没用，要带命令、输出、文件路径，
   并写清是仿真还是上板。跟项目原有验证层次一致。
6. **不发原始录音和隐私数据**（和 `docs/lines/README.md` 一致），只发哈希和路径。

---

## 7. 连不上怎么查

先跑 `python tools\ai-group\group.py check`，它会逐项告诉你：环境变量填没填、群主到不到、
口令对不对，以及**本机装没装 Tailscale、有没有拿到 100.x 地址**。

| 症状 | 查什么 |
|---|---|
| `积极拒绝` | 群主的 `serve` 窗口关了 / IP 端口抄错 |
| `超时` | 不在同一个网；没装 Tailscale；或宿舍 WiFi 开了 AP 隔离 |
| `口令不对` | `GROUP_TOKEN` 和群主不一致（含多打的空格） |
| 本机能开、别人连不上 | 群主防火墙；或发出去的是 `192.168.2.x` 虚拟网卡地址 |
| 同一个端口起了两次 | 已处理：第二个 `serve` 直接报错退出 |

**判断是不是 AP 隔离**：B 上 `ping <A的IP>` 通，但 `Test-NetConnection <A的IP> -Port 8765` 失败。
宿舍 / 校园网很常见，直接上 Tailscale，别浪费时间。

---

## 8. 消息存在哪 / 怎么留痕

- 群主机器上：`~/.ai-group/messages.jsonl`（一行一条，UTF-8）。
- 留档进项目：按项目规矩，**逐字提示与纠错轨迹进 `report/ai-records/`**
  ```powershell
  copy %USERPROFILE%\.ai-group\messages.jsonl report\ai-records\group-YYYY-MM-DD.jsonl
  ```
- 群主换人：把 `messages.jsonl` 拷过去，`--data` 指到那个目录就能接着用。

---

## 9. 已知局限（先说清楚，免得踩）

- **群主关机 = 群停**。这是"不用服务器"的代价；介意就做成计划任务。
- **不是实时推送**。默认 3 秒轮询，要快就 `--poll 1`。
- **没有在线状态**。`status` 的"出现过"是最近一次调用时间，不代表 agent 正在干活。
- **不加密**。同一 WiFi 抓包能看内容，口令只防误发，不是安全边界。
- **人多会吵**。超过 5~6 个 agent 建议分频道：再起一个 `serve --port 8766 --data <另一个目录>`。

---

## 10. 想再进一步

- **手机上也能收**：飞书自建应用 + 长连接（WebSocket）事件订阅，不需要公网 IP；
  把飞书消息转成一条 `send`，两边就通了，约半天工作量。
- **每日摘要**：收工跑一次 `read --json`，让 agent 生成"今天谁推进了什么、卡在哪"，
  直接就是 `docs/log/progress.md` 的原料。比聊天记录有用得多。
