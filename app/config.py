"""集中管理路径、端口、模型名等配置。

规则：
- 开发态（非 frozen）：数据写到项目根 data/，模型在 models/（可从 HF 下载）
- 打包态（PyInstaller frozen）：数据写到 ~/Library/Application Support/mac-ocr，
  只读资源（UI、内置模型、ollama 二进制）从 .app 包内 Resources/MacOS 读取
- 一切可用环境变量覆盖，便于排查
"""
import os
import sys
from pathlib import Path

APP_TITLE = "单据货物明细提取"

def is_frozen() -> bool:
    return getattr(sys, "frozen", False)

def project_root() -> Path:
    """开发态项目根目录（frozen 时无意义）。"""
    return Path(__file__).resolve().parent.parent

def bundle_dir() -> Path:
    """.app 内 Contents/MacOS 目录（frozen），开发态为项目根。"""
    if is_frozen():
        return Path(sys.executable).parent
    return project_root()

def resources_dir() -> Path:
    """.app 内 Contents/Resources 目录（frozen），开发态为项目根。"""
    if is_frozen():
        return Path(sys.executable).parent.parent / "Resources"
    return project_root()

def data_dir() -> Path:
    """可写数据目录（设置、上传暂存、日志）。"""
    if is_frozen():
        base = Path.home() / "Library" / "Application Support" / "mac-ocr"
    else:
        base = project_root() / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base

def models_dir() -> Path | None:
    """内置 PaddleOCR-VL 模型目录；不存在则返回 None（走 HF 在线下载）。"""
    env = os.environ.get("MAC_OCR_MODELS_DIR")
    if env:
        p = Path(env)
        return p if p.exists() else None
    p = resources_dir() / "models" / "paddleocr-vl"
    return p if p.exists() else None

# ---- Web 服务 ----
PORT = int(os.environ.get("MAC_OCR_PORT", "18765"))

# ---- OCR（进程内 transformers）----
OCR_BACKEND = os.environ.get("OCR_BACKEND", "transformers")  # transformers | mock
OCR_MODEL_ID = os.environ.get("OCR_MODEL_ID", "PaddlePaddle/PaddleOCR-VL-1.6")
OCR_MAX_NEW_TOKENS = int(os.environ.get("OCR_MAX_NEW_TOKENS", "3584"))

# ---- LLM（ollama OpenAI 兼容接口）----
OLLAMA_PORT = int(os.environ.get("MAC_OCR_OLLAMA_PORT", "11435"))
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:4b-instruct-2507-q4_K_M")

def llm_base_url() -> str:
    env = os.environ.get("LLM_BASE_URL")
    if env:
        return env.rstrip("/")
    # 打包态优先用随包 ollama（11435），开发态通常连本机已装的 ollama（11434）
    if is_frozen() and (bundle_dir() / "ollama").exists():
        return f"http://127.0.0.1:{OLLAMA_PORT}/v1"
    return os.environ.get("LLM_BASE_URL_DEFAULT", "http://127.0.0.1:11434/v1")

# ---- 流水线 ----
MAX_PDF_PAGES = 30
# LLM 在 GPU 被其他进程占用时会 CPU 分摊，生成可能超过 10 分钟，给足余量
CALL_TIMEOUT_S = int(os.environ.get("MAC_OCR_CALL_TIMEOUT", "1800"))

def log_file() -> Path:
    return data_dir() / "mac-ocr.log"
