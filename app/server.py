"""本地 HTTP 服务：与桌面窗口解耦，也便于用 curl/脚本排查。"""
import io
from pathlib import Path

import anyio
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse

import app.config as cfg
import app.jobs as jobs
import app.pipeline as pipeline
from app.default_prompt import DEFAULT_PROMPT

app = FastAPI(title=cfg.APP_TITLE)

_UI = Path(__file__).parent / "ui"
TEMPLATE = (_UI / "index.html").read_text(encoding="utf-8")
MARKED_JS = (_UI / "marked.min.js").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def index():
    return TEMPLATE.replace(
        "{{DEFAULT_PROMPT}}",
        DEFAULT_PROMPT.replace("\\", "\\\\").replace("</", "<\\/"))


@app.get("/marked.min.js",
         response_class=Response,
         responses={200: {"content": {"text/javascript": {}}}})
def marked_js():
    # 本地内置，不依赖 CDN，保证打包后离线可用
    return Response(MARKED_JS, media_type="text/javascript")


async def _read_uploads(files: list[UploadFile]) -> list[tuple[str, bytes, str]]:
    blobs = []
    for f in files:
        blobs.append((f.filename, await f.read(), f.content_type or ""))
    return blobs


@app.post("/analyze")
async def analyze(files: list[UploadFile] = File(...), prompt: str = Form(...)):
    """同步接口：一次请求跑到完（脚本、docker 版调用方用）。

    注意：整个过程可能几分钟不产生任何响应字节，浏览器（WKWebView）会中断
    这种长空闲请求，前端因此改走 /analyze/start + /analyze/status 轮询。
    """
    blobs = await _read_uploads(files)
    try:
        # OCR 推理是同步阻塞调用，丢进线程池避免卡死事件循环
        result = await anyio.to_thread.run_sync(
            lambda: pipeline.analyze(blobs, prompt, None))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"处理失败：{e!r}") from e
    return result


@app.post("/analyze/start")
async def analyze_start(files: list[UploadFile] = File(...), prompt: str = Form(...)):
    """提交分析任务，立即返回 job_id，由 /analyze/status/{jid} 轮询取进度与结果。"""
    blobs = await _read_uploads(files)
    if not any(b[1] for b in blobs):
        raise HTTPException(400, "未收到有效的 PDF 或图片文件")
    return {"job_id": jobs.submit(blobs, prompt)}


@app.get("/analyze/status/{jid}")
def analyze_status(jid: str):
    job = jobs.get(jid)
    if job is None:
        raise HTTPException(404, "任务不存在或已过期")
    if job["status"] == "running":
        return {"status": "running", "stage": job["stage"]}
    if job["status"] == "error":
        return {"status": "error", "stage": job["stage"], "error": job["error"]}
    return {"status": "done", "stage": job["stage"], **job["result"]}


@app.get("/download/{fid}/{filename}")
def download(fid: str, filename: str):
    data = pipeline.pop_xlsx(fid)
    if data is None:
        raise HTTPException(404, "文件不存在或已下载过")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})
