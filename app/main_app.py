"""应用入口：启动本地 HTTP 服务（+ 随包 ollama sidecar），再打开桌面窗口。

用法：
    python -m app.main_app               # 开发态：窗口 + 本地服务
    python -m app.main_app --headless    # 无窗口（服务器/调试），Ctrl+C 退出
    OcrTool.app（打包态）               # 双击启动，行为同上
"""
import atexit
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import app.config as cfg


def _log(msg: str) -> None:
    import datetime
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] [app] {msg}"
    print(line, flush=True)
    try:
        with open(cfg.log_file(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ---------- 随包 ollama sidecar ----------

_ollama_proc: subprocess.Popen | None = None


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_ollama_sidecar() -> None:
    """打包态启动随包 ollama；开发态若本机已有 ollama 则直接复用。"""
    global _ollama_proc
    ollama_bin = cfg.bundle_dir() / "ollama"
    if not ollama_bin.exists():
        _log(f"未找到随包 ollama（{ollama_bin}），使用外部服务 {cfg.llm_base_url()}")
        return
    if _port_open(cfg.OLLAMA_PORT):
        _log(f"端口 {cfg.OLLAMA_PORT} 已有服务，复用外部 ollama")
        return

    models_res = cfg.resources_dir() / "models" / "ollama"
    env = dict(os.environ)
    env["OLLAMA_HOST"] = f"127.0.0.1:{cfg.OLLAMA_PORT}"
    env["OLLAMA_MODELS"] = str(models_res if models_res.exists()
                               else cfg.data_dir() / "ollama-models")
    env.setdefault("OLLAMA_FLASH_ATTENTION", "1")
    env.setdefault("OLLAMA_KV_CACHE_TYPE", "q8_0")
    env.setdefault("OLLAMA_CONTEXT_LENGTH", "16384")
    env.setdefault("OLLAMA_KEEP_ALIVE", "10m")
    _log(f"启动随包 ollama: {ollama_bin} (port {cfg.OLLAMA_PORT})")
    _ollama_proc = subprocess.Popen(
        [str(ollama_bin), "serve"], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    atexit.register(_ollama_proc.terminate)

    for _ in range(120):  # 最多等 60s
        if _ollama_proc.poll() is not None:
            _log("ollama 进程提前退出，请查看日志")
            return
        if _port_open(cfg.OLLAMA_PORT):
            _log("ollama sidecar 就绪")
            return
        time.sleep(0.5)


# ---------- HTTP 服务 ----------

def start_server() -> threading.Thread:
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(
        "app.server:app", host="127.0.0.1", port=cfg.PORT, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if _port_open(cfg.PORT):
            _log(f"HTTP 服务就绪: http://127.0.0.1:{cfg.PORT}")
            return t
        time.sleep(0.1)
    raise RuntimeError("HTTP 服务启动失败")


# ---------- 桌面窗口菜单 ----------

def _reveal(path: Path, select: bool) -> None:
    """用系统文件管理器/默认程序打开（select=True 时定位文件本身）。"""
    if sys.platform == "darwin":
        cmd = ["open", path] + (["-R"] if select else [])
        subprocess.Popen(cmd)
    elif os.name == "nt":
        if select:
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path.parent if select else path)])


def _open_log(*_args) -> None:
    log = cfg.log_file()
    if not log.exists():
        log.touch()
    _reveal(log, select=True)


def _open_data_dir(*_args) -> None:
    _reveal(cfg.data_dir(), select=False)


def _app_menus() -> "list":
    from webview.menu import Menu, MenuAction

    return [Menu("帮助", [
        MenuAction("查看日志", _open_log),
        MenuAction("打开数据目录", _open_data_dir),
    ])]


def main() -> None:
    _log(f"启动 {cfg.APP_TITLE}（frozen={cfg.is_frozen()}）")
    start_ollama_sidecar()
    start_server()
    url = f"http://127.0.0.1:{cfg.PORT}"

    if "--headless" in sys.argv or os.environ.get("MAC_OCR_NO_WINDOW"):
        _log("headless 模式运行中，Ctrl+C 退出")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        return

    import webview  # pywebview
    webview.create_window(cfg.APP_TITLE, url, width=1180, height=900)
    _log("打开桌面窗口")
    webview.start(menu=_app_menus())  # 阻塞至窗口关闭
    _log("窗口已关闭，退出")


if __name__ == "__main__":
    main()
