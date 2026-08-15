#!/usr/bin/env python3
# proxycat —— 代理管理小工具喵~ (=^･ω･^=)
#
# 解决的问题：
#   FlClash 等代理软件关闭后，会在 gsettings 里残留「系统代理」设置，
#   导致 Firefox 等桌面应用报「代理服务器拒绝连接」，但 curl 一直正常。
#
# 用法：
#   python3 proxycat.py                    # 检测 + 修复代理残留
#   python3 proxycat.py flclash status     # 查看 FlClash 运行状态
#   python3 proxycat.py flclash restart    # 重启 FlClash（打不开时用它）
#
# 依赖：gsettings（GNOME 系统代理设置，几乎必装）

import argparse
import socket
import subprocess
import time
from urllib.parse import urlparse

# gsettings 配置路径
GSETTINGS = "org.gnome.system.proxy"
# FlClash 默认混合端口（如果在设置里改过，记得同步）
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 7890
# FlClash 的 DNS 服务端口（core 活着时必监听，探测时的备用信号）
DNS_PORT = 1053
# FlClash 的两个进程名（主程序 + 核心）
CLASH_NAMES = ("FlClash", "FlClashCore")


def gsettings_get(key):
    """读取一个 gsettings 值，去掉两端引号"""
    result = subprocess.run(
        ["gsettings", "get", GSETTINGS, key],
        capture_output=True,
        text=True,
        check=False,  # 取不到就静默返回空
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


def proxy_still_alive():
    """代理进程还活着吗？探测 FlClash 的混合端口 7890。

    能连上   -> 代理在用，返回 True（别清理）
    连不上   -> 是残留，返回 False（可以清理）
    """
    return _port_open(PROXY_HOST, PROXY_PORT)


def clash_service_alive():
    """FlClash 的代理服务在服务吗？

    混合端口 7890 或 DNS 端口 1053 任一活着都算。
    （FlClash 可能只开着 DNS 服务、混合端口不监听，
     只看 7890 会把「正常运行」误判成「代理死了」）
    """
    return _port_open(PROXY_HOST, PROXY_PORT) or _port_open(PROXY_HOST, DNS_PORT)


def is_residue():
    """判断是不是「代理残留」：
    - 系统代理模式不是 none（设置了代理）
    - 但代理其实没在运行
    两者都满足 -> 是残留，可以清掉
    """
    mode = proxy_mode()
    if mode == "none":
        return False
    return not proxy_still_alive()


def fix():
    """把系统代理模式改回直连"""
    subprocess.run(["gsettings", "set", GSETTINGS, "mode", "none"], check=False)
    print("  (^▽^) 已恢复直连！快去上网喵~")


def clash_pids(name):
    """用 pgrep -x 精确匹配进程名，返回 PID 列表。

    不用 -f（全文匹配），否则会误匹配命令行里含 "FlClash" 的进程，
    比如 proxycat 自己（命令参数里就有 flclash）。
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


def clash_status():
    """FlClash 状态：主程序 / 核心进程 / 代理端口 / 系统代理模式"""
    main_pids = clash_pids("FlClash")
    core_pids = clash_pids("FlClashCore")
    print("(=^･ω･^=) FlClash 状态喵~")
    _print_running("  主程序  ", main_pids)
    _print_running("  核心进程", core_pids)
    if clash_service_alive():
        print(f"  代理服务 : (^▽^) 有端口在监听（混合 {PROXY_PORT} / DNS {DNS_PORT}）")
    else:
        print(f"  代理服务 : (╥﹏╥) {PROXY_HOST}:{PROXY_PORT} 和 :{DNS_PORT} 都不通")
    print(f"  系统代理 : {proxy_mode()}")

    if main_pids and clash_service_alive():
        print("  (・∀・) 进程在跑但觉得窗口打不开？那是单实例锁挡住新点击，用 restart~")
    elif main_pids and not clash_service_alive():
        print("  (・∀・) 进程在跑但代理服务不通，核心可能挂了，用 restart~")


def wait_proxy_up(seconds=10):
    """重启后等代理端口重新连通。

    TODO: 这一格留给你写 —— 现在只是探一次，可以改成轮询：
      每 0.5s 探一次 proxy_still_alive()，最多等 seconds 秒，超时放弃。
      取舍点：轮询间隔 vs 响应速度；等太久会让人以为卡死了。
    """
    return proxy_still_alive()


def clash_restart():
    """重启 FlClash：杀掉旧进程（主程序+核心）再重新启动"""
    print("(=^･ω･^=) 正在重启 FlClash...")
    for name in CLASH_NAMES:
        subprocess.run(["pkill", "-x", name], check=False)  # 没匹配到进程也不算错
    time.sleep(1)  # 等进程退出、端口释放
    subprocess.Popen(["flclash"])
    if wait_proxy_up():
        print("  (^▽^) 代理端口已恢复，重启完成喵~")
    else:
        print("  (；´Д`)  FlClash 已启动，但代理还没起来，稍等几秒再试~")


def git_get(key):
    """读取 git 全局配置的一个值（如 http.proxy），去掉换行"""
    result = subprocess.run(
        ["git", "config", "--global", "--get", key],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip()


def git_check():
    """检查 git 代理配置：指向的端口还活着吗？

    git 的 http.proxy / https.proxy 形如 http://127.0.0.1:7890。
    代理软件关闭/换端口后，这个地址就成「幽灵代理」，
    导致 clone 报 'Failed to connect ... over proxy'。这里把它揪出来清掉。
    """
    print("(=^･ω･^=) 检查 git 代理喵~")
    for key in ("http.proxy", "https.proxy"):
        url = git_get(key)
        if not url:
            print(f"  {key} : 未设置，直连走天下")
            continue
        # 解析出 host 和 port。urlparse 是标准库，专门拆 URL 的各个部分
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
        # 探测端口死活（_port_open 是文件里现成的：1 秒超时 connect）
        if _port_open(host, port):
            print(f"  {key} -> 代理活着 ({host}:{port})，没毛病")
        else:
            print(f"  {key} -> 指向死端口 {host}:{port}，清掉改直连")
            # 只有探测到死了才 unset —— 清配置不可逆，不能盲清
            subprocess.run(
                ["git", "config", "--global", "--unset", key], check=False
            )


def patrol():
    """原有的巡逻逻辑：检测代理残留并修复"""
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="proxycat —— 代理清理喵~ (=^･ω･^=)")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser(
        "flclash",
        help="FlClash 管理：status 查看 / restart 重启",
        description="FlClash 管理：status 查看运行状态，restart 杀掉重启（打不开时用它）",
    )
    p.add_argument(
        "action",
        choices=["status", "restart"],
        help="要执行的操作：status 查看状态 / restart 重启",
    )
    sub.add_parser(
        "git",
        help="检查 git 代理指向的端口死活，死了清掉直连",
        description="检查 git 的 http/https 代理是否指向活端口，指向死端口就清掉直连",
    )
    args = parser.parse_args(argv)

    if args.command == "flclash":
        if args.action == "status":
            clash_status()
        else:
            clash_restart()
    elif args.command == "git":
        git_check()
    else:
        patrol()


if __name__ == "__main__":
    main()
