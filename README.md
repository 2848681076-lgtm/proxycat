# proxycat (=^･ω･^=)

清理 FlClash 等代理软件关闭后残留的「系统代理」设置。

## 解决什么问题

FlClash 关闭后会在 gsettings 里残留「系统代理」设置，导致 Firefox 等桌面应用报「代理服务器拒绝连接」，但 curl 一直正常。直接运行自动检测并恢复直连。

## 用法

```bash
python3 proxycat.py    # 检测 + 修复代理残留
```

## 依赖

- `gsettings`（GNOME 系统代理设置，几乎必装）
