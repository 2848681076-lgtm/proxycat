# proxycat 🐱

代理管理小工具。清理 FlClash 等代理软件关闭后残留的「系统代理」设置，还能检查/重启 FlClash。

## 依赖

- `gsettings`（GNOME 系统代理设置，几乎必装）
- `pgrep` / `pkill`（procps，几乎必装）

## 用法

```bash
python3 proxycat.py                    # 检测 + 修复代理残留
python3 proxycat.py flclash status     # 查看 FlClash 运行状态
python3 proxycat.py flclash restart    # 重启 FlClash（打不开时用它）
```

## 解决什么问题

FlClash 关闭后会在 gsettings 里残留「系统代理」设置，导致 Firefox 等桌面应用报「代理服务器拒绝连接」，但 curl 一直正常。直接运行 `proxycat.py` 会自动检测并恢复直连。

## FlClash 打不开怎么办？

FlClash 是**单实例**应用：后台已有进程在跑时（关窗口 ≠ 退出），再点图标会被单实例锁忽略，表现为"点了没反应"。用 `flclash restart` 杀掉残留进程重新启动即可。

## 技术说明

- FlClash 的两个进程名是 `FlClash`（主程序）和 `FlClashCore`（核心），用 `pgrep/pkill -x` 精确匹配，避免误杀
- 探测"代理是否活着"看 7890 混合端口或 1053 DNS 端口，**任一连通**即视为正常（FlClash 可能只开 DNS 服务，7890 不一定监听）
