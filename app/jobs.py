"""分析任务：把长耗时的 /analyze 拆成“提交 + 轮询”。

为什么需要：桌面窗口是 WKWebView（macOS），它对长时间收不到任何响应字节的
请求会中断连接，前端 fetch 表现为 `TypeError: Load failed`。而一次分析 =
逐页 OCR（每页几十秒）+ LLM 汇总，服务端要全部跑完才回包，几分钟内一字节
不发，必然被掐断。改成后台线程执行 + 前端轮询短请求后，任何阶段都不再有
长时间空闲的连接，顺便还能把进度显示出来。
"""
import threading
import time
import traceback
import uuid

from fastapi import HTTPException

import app.pipeline as pipeline
from app.logutil import log

_KEEP_JOBS = 20    # 只保留最近若干条，避免连跑多次后内存堆积
_TTL_S = 3600      # 已完成任务保留 1 小时，供迟到的轮询取结果

_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def _prune() -> None:
    now = time.time()
    for jid, job in list(_jobs.items()):
        if job["status"] != "running" and now - job["created"] > _TTL_S:
            _jobs.pop(jid, None)
    while len(_jobs) > _KEEP_JOBS:
        finished = [kv for kv in _jobs.items() if kv[1]["status"] != "running"]
        if not finished:
            break
        _jobs.pop(min(finished, key=lambda kv: kv[1]["created"])[0], None)


def submit(blobs: list[tuple[str, bytes, str]], prompt: str) -> str:
    jid = uuid.uuid4().hex[:12]
    with _lock:
        _prune()
        _jobs[jid] = {"id": jid, "status": "running", "stage": "排队中…",
                      "created": time.time(), "result": None, "error": None}
    threading.Thread(target=_run, args=(jid, blobs, prompt), daemon=True).start()
    return jid


def _set_stage(jid: str, stage: str) -> None:
    with _lock:
        if jid in _jobs:
            _jobs[jid]["stage"] = stage


def _run(jid: str, blobs: list[tuple[str, bytes, str]], prompt: str) -> None:
    started = time.time()
    mb = sum(len(b[1]) for b in blobs) / 1048576
    log("job", f"{jid} 开始：{len(blobs)} 个文件 / {mb:.1f} MB")
    try:
        result = pipeline.analyze(
            blobs, prompt, None, progress=lambda m: _set_stage(jid, m))
    except HTTPException as e:
        log("job", f"{jid} 失败（用时 {time.time() - started:.1f}s）：{e.detail}")
        with _lock:
            _jobs[jid].update(status="error", error=str(e.detail), stage="已失败")
        return
    except Exception as e:
        log("job", f"{jid} 异常（用时 {time.time() - started:.1f}s）：{e!r}")
        log("job", traceback.format_exc().rstrip())
        with _lock:
            _jobs[jid].update(status="error", error=f"处理失败：{e!r}", stage="已失败")
        return
    log("job", f"{jid} 完成，用时 {time.time() - started:.1f}s")
    with _lock:
        _jobs[jid].update(status="done", result=result, stage="已完成")


def get(jid: str) -> dict | None:
    with _lock:
        job = _jobs.get(jid)
        return dict(job) if job else None
