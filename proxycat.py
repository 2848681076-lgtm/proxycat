#!/usr/bin/env python3
# proxycat —— 清理代理残留喵~ (=^･ω･^=)
#
# 解决的问题：
#   FlClash 等代理软件关闭后，会在 gsettings 里残留「系统代理」设置，
#   导致 Firefox 等桌面应用报「代理服务器拒绝连接」，但 curl 一直正常。
#
# 用法：
#   python3 proxycat.py          # 检测 + 修复
#
# 依赖：gsettings（GNOME 系统代理设置，几乎必装）

import socket
import subprocess

# gsettings 配置路径
GSETTINGS = "org.gnome.system.proxy"
# FlClash 默认混合端口（如果在设置里改过，记得同步）
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 7890


def gsettings_get(key):
    """读取一个 gsettings 值，去掉两端引号"""
    result = subprocess.run(
        ["gsettings", "get", GSETTINGS, key], capture_output=True, text=True
    )
    return result.stdout.strip().strip("'\"")


def proxy_mode():
    """当前系统代理模式：none / manual / auto"""
    return gsettings_get("mode")


def proxy_still_alive():
    """代理进程还活着吗？连一下 7890 端口，连得上就说明代理还在用"""
    try:
        socket.create_connection((PROXY_HOST, PROXY_PORT), timeout=1)
        return True
    except OSError:
        return False


def is_residue():
    """判断是不是「代理残留」：设置了代理，但代理其实没在运行"""
    mode = proxy_mode()
    if mode == "none":
        return False
    return not proxy_still_alive()


def fix():
    """把系统代理模式改回直连"""
    subprocess.run(["gsettings", "set", GSETTINGS, "mode", "none"])
    print("  (^▽^) 已恢复直连！快去上网喵~")


def main():
    print("(=^･ω･^=) 喵~ proxycat 来巡逻网络啦")
    mode = proxy_mode()
    print(f"  当前系统代理模式: {mode}")

    if is_residue():
        print(f"  (；´Д`)  发现代理残留 ({PROXY_HOST}:{PROXY_PORT}) 但代理没在运行")
        fix()
    else:
        print("  (￣▽￣) 一切正常，没有残留，放心上网喵~")
        if mode != "none":
            print("   （代理正在运行中，不影响）")


if __name__ == "__main__":
    main()
