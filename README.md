# proxycat (=^･ω･^=)

代理管理小工具：清理 FlClash / Clash Verge 残留的系统代理，查看/重启它们。

## 用法

```bash
python3 proxycat.py                    # 检测 + 修复代理残留
python3 proxycat.py flclash status     # 查看 FlClash 运行状态
python3 proxycat.py flclash restart    # 重启 FlClash（打不开时用它）
python3 proxycat.py verge status       # 查看 Clash Verge 运行状态
python3 proxycat.py verge restart      # 重启 Clash Verge
python3 proxycat.py git                # 自动对齐 git 代理（有代理指过去，没有则去掉）
```

## 解决什么问题

FlClash / Clash Verge 关闭后会在 gsettings 里残留「系统代理」设置，导致 Firefox 等桌面应用报「代理服务器拒绝连接」，但 curl 一直正常。直接运行 `proxycat.py` 自动检测并恢复直连。

## 打不开怎么办？

这类代理客户端大多是**单实例**应用：后台已有进程在跑时（关窗口 ≠ 退出），再点图标会被单实例锁忽略，表现为「点了没反应」。用对应的 `restart` 杀掉残留进程重新启动即可。

## 端口对照

| 客户端 | 混合端口 |
|---|---|
| FlClash | 7890 |
| Clash Verge Rev | 7897 |

两个客户端会共用 DNS 端口 1053，所以不能用它来判断是谁在跑，判断「某客户端是否存活」只看它自己的混合端口。

如果在客户端设置里改过端口，记得同步 `proxycat.py` 顶部的 `CLIENTS` 表。

## 依赖

- `gsettings`（GNOME 系统代理设置，几乎必装）
- `pgrep` / `pkill`（procps，几乎必装）
