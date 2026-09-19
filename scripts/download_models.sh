#!/usr/bin/env bash
# 下载 PaddleOCR-VL-1.6 权重到 models/paddleocr-vl（国内走 hf-mirror）。
set -euo pipefail
cd "$(dirname "$0")/.."

export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
python - <<'EOF'
from huggingface_hub import snapshot_download
p = snapshot_download("PaddlePaddle/PaddleOCR-VL-1.6", local_dir="models/paddleocr-vl")
print("model at", p)
EOF
