"""统一日志出口：stdout 一份 + 数据目录 mac-ocr.log 一份。

打包态（.app 双击启动）没有终端可看，文件是唯一的现场，因此所有模块
都走这里，用 tag 区分来源（app / ocr / pipe / job）。
"""
import datetime


def log(tag: str, msg: str) -> None:
    from app.config import log_file  # 延迟导入，避免与 config 的导入顺序纠缠
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] [{tag}] {msg}"
    print(line, flush=True)
    try:
        with open(log_file(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
