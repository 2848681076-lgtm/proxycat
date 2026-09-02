#!/usr/bin/env python3
# proxycat —— 代理管理小工具喵~ (=^･ω･^=)
#
# 解决的问题：
#   FlClash / Clash Verge 等代理软件关闭后，会在 gsettings 里残留「系统代理」设置，
#   导致 Firefox 等桌面应用报「代理服务器拒绝连接」，但 curl 一直正常。
#
# 用法：
#   python3 proxycat.py                    # 检测 + 修复代理残留
#   python3 proxycat.py flclash status     # 查看 FlClash 运行状态
#   python3 proxycat.py flclash restart    # 重启 FlClash（打不开时用它）
#   python3 proxycat.py verge status       # 查看 Clash Verge 运行状态
#   python3 proxycat.py verge restart      # 重启 Clash Verge
#   python3 proxycat.py git                # 自动对齐 git 代理（有代理指过去，没有则去掉）
#
# 依赖：gsettings（GNOME 系统代理设置，几乎必装）

import argparse
import socket
import subprocess
import time

# gsettings 配置路径
GSETTINGS = "org.gnome.system.proxy"
PROXY_HOST = "127.0.0.1"

# 支持的代理客户端。每个客户端要填：主程序进程名、核心进程名、混合端口、启动命令。
# 混合端口在客户端设置里改过的话，记得同步这里。
CLIENTS = {
    "flclash": {
        "main": "FlClash",       # 主程序进程名
        "core": "FlClashCore",   # 核心进程名
        "port": 7890,            # 混合端口
        "cmd": ["flclash"],      # 启动命令
    },
    "verge": {
        "main": "clash-verge",
        "core": "verge-mihomo",
        "port": 7897,
        "cmd": ["clash-verge"],
    },
}


def gsettings_get(key):
    """读取一个 gsettings 值，去掉两端引号"""
    result = subprocess.run(
        ["gsettings", "get", GSETTINGS, key], capture_output=True, text=True
    )
    return result.stdout.strip().strip("'\"")


def proxy_mode():
    """当前系统代理模式：none / manual / auto"""
    return gsettings_get("mode")


def _port_open(host, port):
    """探测 host:port 能否连上（1 秒超时）"""
    try:
        socket.create_connection((host, port), timeout=1)
        return True
    except OSError:
        return False


def find_active_client():
    """返回当前代理服务还活着的第一个客户端配置；一个都没有返回 None。

    靠混合端口探测（verge 在跑返回 verge 的配置，FlClash 在跑返回 flclash），
    两个都没开返回 None。
    """
    for name, c in CLIENTS.items():
        if _port_open(PROXY_HOST, c["port"]):
            return c
    return None


def proxy_still_alive():
    """还有代理在跑吗？遍历所有客户端，任一混合端口能连上就算活着。

    （系统代理可能指向任意一个客户端，只要有一个在监听，就不该算残留）
    """
    return any(_port_open(PROXY_HOST, c["port"]) for c in CLIENTS.values())


def client_service_alive(client):
    """某个客户端的代理服务在服务吗？只看它自己的混合端口。

    为什么不用 DNS 端口辅助判断：两个客户端会共用 1053，
    用它没法区分是哪个在跑（比如 FlClash 没开、verge 开着 1053，
    会误判 FlClash 也活着）。混合端口每个客户端独有，才是可靠信号。
    """
    c = CLIENTS[client]
    return _port_open(PROXY_HOST, c["port"])


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


def pids_of(name):
    """用 pgrep -x 精确匹配进程名，返回 PID 列表。

    不用 -f（全文匹配），否则会误匹配命令行里含该名字的进程，
    比如 proxycat 自己（命令参数里就有 flclash/verge）。
    """
    result = subprocess.run(
        ["pgrep", "-x", name], capture_output=True, text=True, check=False
    )
    return result.stdout.split()


def _print_running(label, pids):
    """打印一行「程序 : 运行中(PID) / 未运行」"""
    if pids:
        print(f"  {label} : (^▽^) 运行中 (PID {' '.join(pids)})")
    else:
        print(f"  {label} : (╥﹏╥) 未运行")


def client_status(client):
    """某个客户端的运行状态：主程序 / 核心进程 / 代理端口 / 系统代理模式"""
    c = CLIENTS[client]
    main_pids = pids_of(c["main"])
    core_pids = pids_of(c["core"])
    print(f"(=^･ω･^=) {client} 状态喵~")
    _print_running("主程序　", main_pids)   # 「主程序」+全角空格补到 8 列，和下面三行对齐
    _print_running("核心进程", core_pids)
    if client_service_alive(client):
        print(f"  代理服务 : (^▽^) 混合端口 {c['port']} 在监听")
    else:
        print(f"  代理服务 : (╥﹏╥) {PROXY_HOST}:{c['port']} 不通")
    print(f"  系统代理 : {proxy_mode()}")

    if main_pids and client_service_alive(client):
        print("  (・∀・) 进程在跑但觉得窗口打不开？那是单实例锁挡住新点击，用 restart~")
    elif main_pids and not client_service_alive(client):
        print("  (・∀・) 进程在跑但代理服务不通，核心可能挂了，用 restart~")


def wait_proxy_up(seconds=10):
    """重启后等代理端口重新连通，轮询最多等 seconds 秒。

    每 0.5s 探一次 proxy_still_alive()：间隔太短会空耗 CPU，
    太长又让「代理已恢复」的提示迟钝，0.5s 是两者间的平衡。
    """
    deadline = time.time() + seconds
    while time.time() < deadline:
        if proxy_still_alive():
            return True
        time.sleep(0.5)
    return False


def client_restart(client):
    """重启某个客户端：杀掉旧进程（主程序+核心）再重新启动"""
    c = CLIENTS[client]
    print(f"(=^･ω･^=) 正在重启 {client}...")
    for name in (c["main"], c["core"]):
        subprocess.run(["pkill", "-x", name], check=False)  # 没匹配到进程也不算错
    time.sleep(1)  # 等进程退出、端口释放
    subprocess.Popen(c["cmd"])
    if wait_proxy_up():
        print("  (^▽^) 代理端口已恢复，重启完成喵~")
    else:
        print(f"  (；´Д`)  {client} 已启动，但代理还没起来，稍等几秒再试~")


def git_proxy():
    """对齐 git 代理：检测当前在跑的代理客户端，把 git 的 http/https 代理指过去。

    有代理在跑 → 设为 socks5h://127.0.0.1:<它的混合端口>
    没代理在跑 → 去掉 git 代理设置（防止残留旧端口，连不上 GitHub）
    """
    print("(=^･ω･^=) 喵~ 帮你对齐 git 代理~")
    active = find_active_client()
    if active:
        proxy = f"socks5h://{PROXY_HOST}:{active['port']}"
        for key in ("http.proxy", "https.proxy"):
            subprocess.run(["git", "config", "--global", key, proxy], check=False)
        print(f"  (^▽^) 检测到 {active['main']}（混合 {active['port']}），git 代理 → {proxy}")
    else:
        for key in ("http.proxy", "https.proxy"):
            subprocess.run(
                ["git", "config", "--global", "--unset-all", key],
                stderr=subprocess.DEVNULL,  # 没设置过时 unset 报错，忽略即可
                check=False,
            )
        print("  (^▽^) 没有代理在跑，已去掉 git 代理设置")


def patrol():
    """检测代理残留并修复"""
    print("(=^･ω･^=) 喵~ proxycat 来巡逻网络啦")
    mode = proxy_mode()
    print(f"  当前系统代理模式: {mode}")

    if is_residue():
        print("  (；´Д`)  发现代理残留，但代理没在运行")
        fix()
    else:
        print("  (￣▽￣) 一切正常，没有残留，放心上网喵~")
        if mode != "none":
            print("   （代理正在运行中，不影响）")


def main(argv=None):
    parser = argparse.ArgumentParser(description="proxycat —— 代理清理喵~ (=^･ω･^=)")
    sub = parser.add_subparsers(dest="command")
    for name in CLIENTS:  # 每个客户端都生成 status/restart 两个子命令
        p = sub.add_parser(name, help=f"{name} 管理：status 查看 / restart 重启")
        p.add_argument(
            "action",
            choices=["status", "restart"],
            help="要执行的操作：status 查看状态 / restart 重启",
        )
    sub.add_parser(
        "git",
        help="自动对齐 git 代理：有代理在跑就指过去，没有就去掉",
    )
    args = parser.parse_args(argv)

    if args.command == "git":
        git_proxy()
    elif args.command in CLIENTS:
        if args.action == "status":
            client_status(args.command)
        else:
            client_restart(args.command)
    else:
        patrol()


if __name__ == "__main__":
    main()
