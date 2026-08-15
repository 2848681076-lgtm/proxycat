#!/usr/bin/env python3
# proxycat —— 代理管理小工具喵~ (=^･ω･^=)
#
# 解决的问题：
#   FlClash 等代理软件关闭后，会在 gsettings 里残留「系统代理」设置，
#   导致 Firefox 等桌面应用报「代理服务器拒绝连接」，但 curl 一直正常。
#
# 用法：
#   python3 proxycat.py                      # 检测 + 修复代理残留
#   python3 proxycat.py flclash status       # 查看 FlClash 运行状态
#   python3 proxycat.py flclash restart      # 重启 FlClash（打不开时用它）
#   python3 proxycat.py flclash mode global  # 切内核模式 rule/global/direct
#   python3 proxycat.py flclash node 菲律宾  # 切 GLOBAL 节点（支持模糊匹配）
#   python3 proxycat.py proxy on/off         # 开关系统代理
#   python3 proxycat.py git                  # 检查 git 代理指向的端口死活
#
# 依赖：gsettings（GNOME 系统代理设置，几乎必装）

import argparse
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
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
# mihomo RESTful API 地址（FlClash 设置里开启「外部控制器」后可用）
API_BASE = "http://127.0.0.1:9090"
# 内核模式的三种取值 + 中文说明（list 和 mode 切换共用）
MODE_CHOICES = ("rule", "global", "direct")
MODE_DESC = {
    "rule": "按规则分流（国内直连、国外代理）",
    "global": "全局代理（所有流量走代理）",
    "direct": "全局直连（不走代理）",
}
# 订阅机场塞进节点列表的「信息条目」关键词（不是真节点，list 时跳过）
INFO_KEYWORDS = ("剩余流量", "重置", "套餐", "倍率", "请使用")


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


def clash_api(path, method="GET", body=None):
    """调用 mihomo RESTful API，返回解析后的 JSON。

    path 以 / 开头（如 "/configs"）；body 是 dict，序列化成 JSON 发送。
    连不上（API 没开、core 挂了）时返回 None，调用方自行判断。
    """
    url = API_BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = resp.read()
            # 204 等空响应体返回 {}，表示「成功但无数据」
            return json.loads(raw) if raw else {}
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


def _print_running(label, pids):
    """打印一行「程序 : 运行中(PID) / 未运行」"""
    if pids:
        print(f"  {label} : (^▽^) 运行中 (PID {' '.join(pids)})")
    else:
        print(f"  {label} : (╥﹏╥) 未运行")


def clash_status():
    """FlClash 状态：主程序 / 核心进程 / 代理端口 / 系统代理模式 / 内核信息"""
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

    # 内核信息走 API（core 活着但外部控制器没开时会返回 None，优雅跳过）
    config = clash_api("/configs")
    if config is None:
        print("  内核信息 : (╥﹏╥) API 不可用（外部控制器没开？）")
    else:
        print(f"  内核模式 : {config.get('mode', '?')}")
        proxies = clash_api("/proxies")
        if proxies:
            groups = {
                k: v for k, v in proxies["proxies"].items()
                if v.get("type") == "Selector"
            }
            if groups:
                print("  节点组   :")
                for name, g in groups.items():
                    print(f"    {name:<6} -> {g.get('now', '?')}")

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


def clash_mode(target):
    """切换内核模式：rule / global / direct（走 API）"""
    result = clash_api("/configs", method="PATCH", body={"mode": target})
    if result is None:
        print("  (╥﹏╥) API 不可用，切换失败（外部控制器没开？）")
        return
    print(f"  (^▽^) 已切换到 {target} 模式喵~")


def clash_node(name):
    """切换 GLOBAL 组的节点（支持模糊匹配，走 API）"""
    proxies = clash_api("/proxies")
    if proxies is None:
        print("  (╥﹏╥) API 不可用，切换失败（外部控制器没开？）")
        return
    group = proxies["proxies"].get("GLOBAL")
    if not group or group.get("type") != "Selector":
        print("  (╥﹏╥) 没找到 GLOBAL 组")
        return
    choices = group.get("all", [])
    # 先精确匹配，再模糊匹配（节点名包含输入的子串）
    match = name if name in choices else None
    if match is None:
        matches = [c for c in choices if name in c]
        if len(matches) == 1:
            match = matches[0]
        elif len(matches) > 1:
            print(f"  (；´Д`) 「{name}」匹配到多个节点，再精确点：")
            for m in matches:
                print(f"    - {m}")
            return
        else:
            print(f"  (；´Д`) 没找到节点「{name}」，用 flclash status 看可选节点")
            return
    result = clash_api("/proxies/GLOBAL", method="PUT", body={"name": match})
    if result is None:
        print("  (╥﹏╥) 切换失败")
        return
    print(f"  (^▽^) GLOBAL 已切换到「{match}」喵~")


def _list_modes(current_mode):
    """打印模式选项（内部辅助，list / mode 不带参数共用）"""
    print(f"  内核模式（当前 {current_mode}）：")
    for m in MODE_CHOICES:
        mark = "← 当前" if m == current_mode else ""
        print(f"    {m:<8} {mark}  {MODE_DESC[m]}")


def _list_nodes(group):
    """打印 GLOBAL 组节点（内部辅助，过滤信息条目）"""
    now = group.get("now", "?")
    all_nodes = group.get("all", [])
    nodes = [n for n in all_nodes if not any(k in n for k in INFO_KEYWORDS)]
    print(f"  GLOBAL 节点（当前「{now}」，共 {len(nodes)} 个）：")
    for i, name in enumerate(nodes, 1):
        mark = " ← 当前" if name == now else ""
        print(f"    {i:>2}. {name}{mark}")


def clash_list():
    """列出所有可选项：内核模式 + GLOBAL 组节点"""
    config = clash_api("/configs")
    proxies = clash_api("/proxies")
    if config is None or proxies is None:
        print("  (╥﹏╥) API 不可用，拿不到列表（外部控制器没开？）")
        return
    print("(=^･ω･^=) 可选列表喵~")
    _list_modes(config.get("mode", "?"))
    group = proxies["proxies"].get("GLOBAL")
    if group:
        _list_nodes(group)


def clash_list_modes():
    """只列出内核模式选项（flclash mode 不带参数时调用）"""
    config = clash_api("/configs")
    if config is None:
        print("  (╥﹏╥) API 不可用，拿不到模式列表（外部控制器没开？）")
        return
    print("(=^･ω･^=) 内核模式喵~")
    _list_modes(config.get("mode", "?"))


def clash_list_nodes():
    """只列出 GLOBAL 组节点（flclash node 不带参数时调用）"""
    proxies = clash_api("/proxies")
    if proxies is None:
        print("  (╥﹏╥) API 不可用，拿不到节点列表（外部控制器没开？）")
        return
    group = proxies["proxies"].get("GLOBAL")
    if not group:
        print("  (╥﹏╥) 没找到 GLOBAL 组")
        return
    print("(=^･ω･^=) GLOBAL 节点喵~")
    _list_nodes(group)


def proxy_on():
    """打开系统代理：mode=manual，指向 FlClash 混合端口"""
    subprocess.run(["gsettings", "set", GSETTINGS, "mode", "manual"], check=False)
    if proxy_still_alive():
        print(f"  (^▽^) 系统代理已开启，指向 {PROXY_HOST}:{PROXY_PORT} 喵~")
    else:
        print(f"  (；´Д`) 系统代理已设，但 {PROXY_PORT} 端口没监听！")
        print("          FlClash 的代理开关可能没开，先去 FlClash 里开代理")


def proxy_off():
    """关闭系统代理：mode=none，恢复直连"""
    subprocess.run(["gsettings", "set", GSETTINGS, "mode", "none"], check=False)
    print("  (^▽^) 系统代理已关闭，恢复直连喵~")


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
    parser = argparse.ArgumentParser(
        prog="proxycat",
        description="proxycat —— 代理管理小工具 (=^･ω･^=)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  proxycat                        检测并修复代理残留\n"
            "  proxycat flclash status         查看 FlClash 状态\n"
            "  proxycat flclash list           列出可选的模式和节点\n"
            "  proxycat flclash restart        重启 FlClash\n"
            "  proxycat flclash mode global    切换内核模式\n"
            "  proxycat flclash node 菲律宾    切换节点\n"
            "  proxycat proxy on               开启系统代理\n"
            "  proxycat proxy off              关闭系统代理\n"
            "  proxycat git                    检查 git 代理"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser(
        "flclash",
        help="FlClash 管理",
        description="FlClash 管理：查看状态、重启、切模式、切节点",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  proxycat flclash list            列出可选模式和节点\n"
            "  proxycat flclash status          查看状态\n"
            "  proxycat flclash mode global     切全局模式\n"
            "  proxycat flclash node 菲律宾     切节点（支持模糊匹配）"
        ),
    )
    p.add_argument(
        "action",
        choices=["status", "list", "restart", "mode", "node"],
        help="status=状态  list=列选项  restart=重启  mode=切模式  node=切节点",
    )
    p.add_argument(
        "value",
        nargs="?",
        help="mode 取 rule/global/direct；node 取节点名。不带参数则列出选项",
    )

    pp = sub.add_parser(
        "proxy",
        help="系统代理开关",
        description="切换 GNOME 系统代理：on 指向 FlClash，off 恢复直连",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n  proxycat proxy on   开启\n  proxycat proxy off  关闭",
    )
    pp.add_argument("action", choices=["on", "off"], help="on 开启 / off 关闭")

    sub.add_parser(
        "git",
        help="检查 git 代理",
        description="检查 git 的 http/https 代理是否指向活端口，指向死端口就清掉改直连",
    )

    args = parser.parse_args(argv)

    if args.command == "flclash":
        if args.action == "status":
            clash_status()
        elif args.action == "list":
            clash_list()
        elif args.action == "restart":
            clash_restart()
        elif args.action == "mode":
            if args.value is None:
                clash_list_modes()  # 不带参数 → 列出可选模式
            elif args.value in MODE_CHOICES:
                clash_mode(args.value)
            else:
                parser.error("mode 的取值必须是 rule / global / direct")
        elif args.action == "node":
            if args.value is None:
                clash_list_nodes()  # 不带参数 → 列出可选节点
            else:
                clash_node(args.value)
    elif args.command == "proxy":
        proxy_on() if args.action == "on" else proxy_off()
    elif args.command == "git":
        git_check()
    else:
        patrol()


if __name__ == "__main__":
    main()
