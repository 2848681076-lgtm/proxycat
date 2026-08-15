# proxycat (=^･ω･^=)

代理管理小工具。清理 FlClash 残留的系统代理设置，并通过 API 控制 clash 内核。

## 依赖

- `gsettings`（GNOME 系统代理设置，几乎必装）
- `pgrep` / `pkill`（procps，几乎必装）
- FlClash 的「外部控制器」（`127.0.0.1:9090`，切 mode / node 时才需要）

## 用法

```bash
python3 proxycat.py                        # 检测 + 修复代理残留
python3 proxycat.py flclash status         # 查看 FlClash 运行状态
python3 proxycat.py flclash restart        # 重启 FlClash（打不开时用它）
python3 proxycat.py flclash mode global    # 切内核模式 rule/global/direct
python3 proxycat.py flclash node 菲律宾    # 切 GLOBAL 节点（支持模糊匹配）
python3 proxycat.py proxy on/off           # 开关系统代理
python3 proxycat.py git                    # 检查 git 代理指向的端口死活
```

## 功能说明

### 清理代理残留（默认，无参数）

FlClash 关闭后会在 gsettings 里残留「系统代理」设置，导致 Firefox 等桌面应用报「代理服务器拒绝连接」，但 curl 一直正常。直接运行 `proxycat.py` 自动检测并恢复直连。

### FlClash 管理（`flclash`）

- `status` — 查看主程序/核心进程、端口监听、系统代理、内核模式、节点组概览
- `restart` — 杀掉残留进程重新启动（解决「打不开」）
- `mode` — 切换内核模式 rule / global / direct
- `node` — 切换 GLOBAL 组节点，支持模糊匹配（如 `node 菲律宾`）

### 系统代理开关（`proxy`）

`proxy on` 设 `mode=manual` 指向 FlClash，`proxy off` 恢复直连。

### git 代理检查（`git`）

检查 git 的 `http.proxy` / `https.proxy` 是否指向活端口，指向死端口就清掉改直连。

## FlClash 打不开怎么办？

FlClash 是**单实例**应用：后台已有进程在跑时（关窗口 ≠ 退出），再点图标会被单实例锁忽略，表现为「点了没反应」。用 `flclash restart` 杀掉残留进程重新启动即可。

## 技术说明

- FlClash 进程名用 `pgrep/pkill -x` 精确匹配（`-f` 会误匹配命令行里含 "FlClash" 的进程，包括 proxycat 自己）
- 探测「代理是否活着」看 7890 混合端口或 1053 DNS 端口，**任一连通**即视为正常（FlClash 可能只开 DNS，7890 不一定监听）
- 切 mode 用 `PATCH /configs`（`PUT` 会把配置写回 config.yaml，而 FlClash 的 core 没有这个文件，会报 400）
- 切节点用 `PUT /proxies/GLOBAL`，成功返回 204 空 body
- 全程零第三方依赖（只用标准库 `urllib.request`）
