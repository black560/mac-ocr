# mac-ocr 开发文档

> 桌面单文件（.app 包）版本的板材货物明细提取工具。目标平台 macOS Apple Silicon，
> 开发/调试主要在 Windows 上进行（headless + mock/CPU 模式）。

## 1. 架构总览

```
OcrTool.app
├── Contents/MacOS/
│   ├── OcrTool          主程序（PyInstaller 打包，Python）
│   │   ├── pywebview 窗口（WKWebView 加载 app/ui/index.html）
│   │   ├── uvicorn 本地 HTTP 服务 127.0.0.1:18765（见 §4 接口契约）
│   │   ├── OCR：进程内 transformers 推理（PaddleOCR-VL-1.6，MPS/CPU）
│   │   └── LLM：httpx → ollama OpenAI 兼容接口
│   └── ollama           sidecar（官方自包含二进制），监听 127.0.0.1:11435
└── Contents/Resources/models/
    ├── paddleocr-vl/    PaddleOCR-VL-1.6 权重 ~1.8G（HF 格式）
    └── ollama/          qwen3:4b-instruct-2507-q4_K_M ~2.6G
```

### 与 docker 版（../paddleocr-vl-web）的对应关系

| docker 版 | mac-ocr 版 | 说明 |
|---|---|---|
| web 容器 FastAPI | app/server.py（同样的 /analyze、/download 接口） | 端口 8080 → 18765 |
| ocr 容器 vLLM | app/ocr_local.py（transformers 推理） | 唯一的实质改动点 |
| llm 容器 ollama | 随包 sidecar ollama（同模型 tag） | 端口 8000 → 11435 |
| web/app/templates/index.html | app/ui/index.html | 仅提示文案微调 |

调用链：`上传 → PyMuPDF 转图(2x) → LocalOCR.ocr() 逐页 → apply_prompt() → ollama → build_xlsx()`。
xlsx 解析规则（容错、只取最后一个表格块）与 docker 版一致。

## 2. 目录结构

```
mac-ocr/
├── app/
│   ├── config.py       配置：路径、端口、模型名；开发/打包双态；环境变量覆盖
│   ├── ocr_local.py    OCR 适配层（transformers / mock 双后端，懒加载，单例）
│   ├── pipeline.py     PDF 转图、LLM 调用、xlsx 导出、analyze 流水线
│   ├── server.py       FastAPI 路由
│   ├── main_app.py     入口：ollama sidecar 管理 + uvicorn + pywebview 窗口
│   ├── default_prompt.py  默认提示词（与 docker 版同步维护）
│   └── ui/index.html   前端界面
├── scripts/
│   ├── gen_test_pdf.py        生成合成装箱单 PDF
│   ├── download_models.sh     下载 OCR 权重（hf-mirror）
│   ├── mock_model_server.py   mock LLM（OpenAI 兼容）
│   └── verify_real_ocr.py     真实 OCR + mock LLM 端到端验证
├── tests/test_pipeline_mock.py  无模型冒烟测试（OCR_BACKEND=mock）
├── build/
│   ├── ocrtool.spec   PyInstaller 配置（onedir + BUNDLE 出 .app）
│   └── build_app.sh   组装：pyinstaller → 拷 ollama/模型 → ad-hoc 签名 → zip
├── .github/workflows/build-mac.yml  macOS arm64 云端构建
└── docs/DEVELOPMENT.md  本文档
```

## 3. 本机开发（Windows）

```bash
cd mac-ocr
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # CPU 开发机可换装 CPU 版 torch：
                                                   # pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python tests/test_pipeline_mock.py   # 无模型冒烟测试（必过）
.venv/Scripts/python -m app.main_app --headless    # 起服务，浏览器开 127.0.0.1:18765
```

OCR 后端由环境变量 `OCR_BACKEND` 控制：

- `transformers`（默认）：真实模型。开发机首次运行需先 `bash scripts/download_models.sh`
  （或手动把权重放到 `models/paddleocr-vl`），CPU 推理单页约 1-3 分钟。
- `mock`：返回固定装箱单文本，用于无模型环境调试界面与流水线。

真实 OCR 链路（不含 LLM）的整体验证：`python scripts/verify_real_ocr.py`
（真实 OCR 推理 + mock LLM，本机没装 ollama 也能跑通全流程）。

LLM 在开发机连 `127.0.0.1:11434`（本机已装的 ollama），可用 `LLM_BASE_URL` 覆盖。
测试时用 `scripts/mock_model_server.py` 起一个假 LLM。

## 4. 接口契约（外部程序也用这套）

| 路由 | 方法 | 说明 |
|---|---|---|
| `/` | GET | 操作界面（HTML） |
| `/analyze` | POST | multipart：`files`（可多文件，PDF/PNG/JPG）+ `prompt`（文本）。返回 `{result, pages:[{page,source,ocr}], xlsx_url}` |
| `/download/{fid}/goods.xlsx` | GET | 下载 Excel，**一次性**（下载后失效） |

LLM 上游接口：OpenAI 兼容 `POST {LLM_BASE_URL}/chat/completions`，模型名
`qwen3:4b-instruct-2507-q4_K_M`，上下文 16K（KV q8_0 量化）。

## 5. 打包（macOS arm64）

两条路径：

### 5.1 GitHub Actions（推荐，无需 Mac）

推 tag `v*` 或手动 dispatch `.github/workflows/build-mac.yml`：
macos-14 runner 上装依赖 → 下载两套模型 → pyinstaller → 组装 → ad-hoc 签名 →
上传 artifact `OcrTool-macos-arm64.zip`（约 5G，注意 artifact 上限，必要时改用 release 上传）。

### 5.2 有 Mac 时本地构建

```bash
brew install ollama && brew install python@3.12
python3.12 -m venv .venv && ./.venv/bin/pip install -r requirements.txt pyinstaller
bash scripts/download_models.sh
OLLAMA_MODELS="$PWD/models/ollama" ollama serve &   # 供 build_app.sh 拉取 qwen3
bash build/build_app.sh                              # 产出 build/dist/OcrTool-macos-arm64.zip
```

### 打包注意（踩过的坑提前写明）

- **onedir 而非 onefile**：PyInstaller 单文件模式每次启动解压 3G+ torch 到临时目录，
  冷启动要几分钟；onedir 的 .app 启动秒级。
- torch/transformers 依赖 pyinstaller-hooks-contrib 的 hooks，保持其较新版本。
- transformers 的远程代码（configuration_paddleocr_vl.py 等）已随模型目录本地化，
  打包时模型在 Resources/ 下，运行时 `trust_remote_code=True` 从本地加载，不联网。
- ad-hoc 签名（`codesign -s -`）只保证本机可跑；分发给别人需要开发者签名+公证，
  否则对方首次打开需右键 → 打开。

## 6. 运行行为

- 启动：拉起 ollama sidecar（打包态）→ uvicorn(18765) → pywebview 窗口。
  关闭窗口 = 退出整个应用（sidecar 由 atexit 终止）。
- 菜单栏"帮助"菜单：查看日志（定位到日志文件）、打开数据目录。macOS 上
  pywebview 6.x 的菜单回调无参调用，动作里不要依赖 window 参数。
- 前端完全离线：marked.min.js 已内置（app/ui/，由 /marked.min.js 提供），
  不从 CDN 加载。
- OCR 模型**懒加载**：首次点"开始提取"才载入（M1 上约 10-30 秒），之后常驻。
  加载失败会记录 load_error 并在下次请求时重试。
- 请求串行：OCR 持锁、ollama 单实例，排队处理；多页大单据 OCR 文本超过 LLM
  16K 上下文时尾部被截断（ollama 行为），建议分文件上传。

## 7. 排查指南（Troubleshooting）

### 7.1 日志在哪

- 运行日志：`~/Library/Application Support/mac-ocr/mac-ocr.log`（打包态）/
  `mac-ocr/data/mac-ocr.log`（开发态）。stdout 同时输出一份。
- ollama sidecar 的输出被丢弃（DEVNULL），需要看时用
  `OLLAMA_HOST=127.0.0.1:11435 ollama ps` 查看模型加载状态（GPU/CPU 分摊）。

### 7.2 常见故障

| 现象 | 排查 |
|---|---|
| 窗口打开但请求报 502 "LLM 服务返回错误 404 model does not exist" | ollama 未就绪或模型未拉取：`curl 127.0.0.1:11435/v1/models`；`ollama ps` 看是否加载；首次调用会加载模型（数十秒），期间 ollama 可能返回非 200 → 重试一次 |
| 排查问题找不到日志 | 打包态用菜单栏 帮助 → 查看日志；headless/开发态看 `data/mac-ocr.log` |
| 502 "处理失败：RuntimeError(...)" | OCR 推理崩溃，看 mac-ocr.log 中 `[ocr]` 行；MPS 显存不足时改用 CPU：环境变量 `MAC_OCR_FORCE_CPU=1`（见 ocr_local） |
| 模型加载慢/卡住 | 首次加载正常需 10-60s；超过 5 分钟看 log 是否卡在权重 mmap（磁盘慢），或杀进程重启 |
| 下载 xlsx 404 | 链接是一次性的；重新 /analyze 获取新链接 |
| 端口被占 | `MAC_OCR_PORT`（默认 18765）/`MAC_OCR_OLLAMA_PORT`（默认 11435）换端口；11435 被占时 sidecar 会放弃启动并复用已有服务 |
| PyInstaller 启动报 ModuleNotFoundError: uvicorn.xxx | hiddenimports 缺项，按报错补进 build/ocrtool.spec |
| .app 在别人机器上打不开 | Gatekeeper：右键 → 打开；或 `xattr -cr /Applications/OcrTool.app` |

### 7.3 环境变量速查

| 变量 | 默认 | 说明 |
|---|---|---|
| `MAC_OCR_PORT` | 18765 | 本地 HTTP 服务端口 |
| `MAC_OCR_OLLAMA_PORT` | 11435 | 随包 ollama 端口 |
| `LLM_BASE_URL` | 打包态 `http://127.0.0.1:11435/v1`，否则 `:11434/v1` | LLM 地址 |
| `LLM_MODEL` | qwen3:4b-instruct-2507-q4_K_M | LLM 模型名 |
| `OCR_BACKEND` | transformers | transformers / mock |
| `OCR_MODEL_ID` | PaddlePaddle/PaddleOCR-VL-1.6 | 无内置模型时的 HF 下载源 |
| `MAC_OCR_MODELS_DIR` | Resources/models/paddleocr-vl | 内置 OCR 模型目录 |
| `OCR_MAX_NEW_TOKENS` | 3584 | 单页 OCR 最大生成长度 |
| `MAC_OCR_NO_WINDOW` | - | 置 1 等效 `--headless` |

## 8. 已知局限与后续可做

- 单请求串行，不适合高并发对外服务（定位是个人桌面工具）。
- LLM 4B 量化模型算术偶有差错，靠提示词的"校验（必做）"条款兜底报告差异；
  追求精度可换更大模型（ollama 直接 `ollama pull qwen3:8b` 并改 `LLM_MODEL`）。
- Windows/macOS 双端共用同一套 /analyze 契约；若 docker 版提示词更新，同步
  app/default_prompt.py 即可。
