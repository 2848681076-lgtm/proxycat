# proxycat (=^･ω･^=)

代理管理小工具：守护你的系统代理和 git 代理，免遭「残留」困扰。

一键检测并修复代理残留，查看/重启 FlClash、Clash Verge 两个代理客户端，
还能自动把 git 代理对齐到当前正在运行的客户端。

## 快速上手

```bash
python3 proxycat.py                     # 检测 + 修复代理残留
python3 proxycat.py flclash status      # 查看 FlClash 运行状态
python3 proxycat.py flclash restart     # 重启 FlClash（打不开时用它）
python3 proxycat.py verge status        # 查看 Clash Verge 运行状态
python3 proxycat.py verge restart       # 重启 Clash Verge
python3 proxycat.py git                 # 自动对齐 git 代理
```

## 解决什么问题

FlClash / Clash Verge 关闭后会在 gsettings 里残留「系统代理」设置，
导致 Firefox 等桌面应用报「代理服务器拒绝连接」，但 curl 一直正常。
这是最坑的一种残留：藏得深，症状却很明显。

直接运行 `proxycat.py` 自动检测：只要「设置了系统代理」，但用的代理端口
都没在监听，就判定为残留并恢复直连。

## git 代理也归我管

切换代理客户端后，git 的 `http.proxy` / `https.proxy` 容易残留旧客户端的端口，
导致 `git push` 连不上（连不上比没代理更隐蔽）。

`python3 proxycat.py git` 会自动探测当前在跑的客户端，然后：

- **有代理在跑** → 把 git 全局代理设成它的 `socks5h://127.0.0.1:<混合端口>`
- **没代理在跑** → 去掉 git 代理设置

## 代理客户端「打不开」怎么办？

这类代理客户端大多是**单实例**应用：后台已有进程在跑时（关窗口 ≠ 退出），
再点图标会被单实例锁忽略，表现为「点了没反应」。

`status` 显示主程序/核心**进程在跑**但觉得窗口打不开？用对应的 `restart`
杀掉残留进程重新启动。`restart` 会自动轮询等代理端口恢复连接，不用干等。

## 支持的客户端与端口

| 客户端 | 主程序进程 | 核心进程 | 混合端口 |
|---|---|---|---|
| FlClash | `FlClash` | `FlClashCore` | 7890 |
| Clash Verge Rev | `clash-verge` | `verge-mihomo` | 7897 |

客户端都收敛在 `proxycat.py` 顶部的 `CLIENTS` 配置表里，新增客户端只需加一行。
两个客户端共用 DNS 端口 1053，所以判断存活只用各自独有的混合端口。
如果在客户端设置里改过端口，记得同步这张表。

## 依赖

- `gsettings`（GNOME 系统代理设置，几乎必装）
- `pgrep` / `pkill`（procps，几乎必装）
- `git`（仅 `git` 子命令用到）