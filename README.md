# mac-ocr — 板材货物明细提取（macOS 桌面版）

`paddleocr-vl-web`（Docker 版）的 macOS 单机桌面化：打包为自包含 `OcrTool.app`，
拷到任意 Apple Silicon Mac（16G 内存推荐）双击即用，完全离线。

- GUI + 流水线：Python（pywebview 窗口 + FastAPI 本地服务 + transformers 推理）
- LLM：随包 ollama sidecar（qwen3:4b-instruct-2507-q4_K_M）
- OCR：PaddleOCR-VL-1.6（进程内 transformers，MPS/CPU 自动选择）

## 快速开始（开发机，Windows 可用）

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt          # CPU 机器：torch 换 CPU 版
.venv/Scripts/python tests/test_pipeline_mock.py       # 无模型冒烟测试
bash scripts/download_models.sh                        # 下载 OCR 权重（~1.8G，走 hf-mirror）
.venv/Scripts/python -m app.main_app --headless        # 起服务（LLM 需本机 ollama）
# 浏览器打开 http://127.0.0.1:18765
```

## 打包出 Mac .app

- 有 Mac：`bash build/build_app.sh` → `build/dist/OcrTool-macos-arm64.zip`
- 无 Mac：推 tag `v*` 触发 `.github/workflows/build-mac.yml`，下载 artifact

**架构、接口契约、打包细节、故障排查全部见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。**
