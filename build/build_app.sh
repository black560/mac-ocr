#!/usr/bin/env bash
# 在 macOS arm64 上把 OcrTool.app 组装为可分发的 zip。
# 前置：python3.12 venv 已装 requirements.txt + pyinstaller；
#       models/paddleocr-vl 已由 scripts/download_models.sh 下载；
#       本机已安装 ollama（brew install ollama）且已 pull 目标模型。
# 产物：build/dist/OcrTool-macos-arm64.zip
set -euo pipefail
cd "$(dirname "$0")/.."

# pyinstaller 等装在 .venv 里，未激活 venv 时（如 CI）自动补 PATH
[ -x ".venv/bin/pyinstaller" ] && export PATH="$PWD/.venv/bin:$PATH"

ARCH=$(uname -m)
[ "$ARCH" = "arm64" ] || { echo "必须在 Apple Silicon 上构建，当前 $ARCH"; exit 1; }
[ -d models/paddleocr-vl ] || { echo "缺少 models/paddleocr-vl，先运行 scripts/download_models.sh"; exit 1; }

echo "==> PyInstaller 构建 OcrTool.app"
pyinstaller build/ocrtool.spec --noconfirm --distpath build/dist --workpath build/work
APP="build/dist/OcrTool.app"

echo "==> 提取 ollama 服务端二进制（来自官方 Ollama.app）"
mkdir -p "$APP/Contents/Resources/models"
curl -L -o /tmp/Ollama-darwin.zip "https://ollama.com/download/Ollama-darwin.zip"
unzip -q -o /tmp/Ollama-darwin.zip -d /tmp/ollama-app
# 官方 .app 内 Resources/ollama 是自包含的服务端+CLI 二进制
cp "/tmp/ollama-app/Ollama.app/Contents/Resources/ollama" "$APP/Contents/MacOS/ollama"
chmod +x "$APP/Contents/MacOS/ollama"

echo "==> 拷入模型权重（OCR ~1.8G + ollama qwen3 ~2.6G）"
cp -R models/paddleocr-vl "$APP/Contents/Resources/models/paddleocr-vl"
if [ ! -d models/ollama/models ]; then
  echo "==> 用本机 ollama 拉取 qwen3 到 models/ollama（首次约 2.6G）"
  OLLAMA_MODELS="$PWD/models/ollama" ollama serve &
  OLLAMA_PID=$!
  sleep 3
  OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/models/ollama" \
    ollama pull qwen3:4b-instruct-2507-q4_K_M
  kill $OLLAMA_PID || true
  sleep 1
fi
cp -R models/ollama "$APP/Contents/Resources/models/ollama"

echo "==> ad-hoc 签名 + 压缩"
codesign --force --deep -s - "$APP"
(cd build/dist && zip -qry OcrTool-macos-arm64.zip OcrTool.app)
echo "==> 完成: build/dist/OcrTool-macos-arm64.zip"
