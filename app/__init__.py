"""包初始化：开发态把项目根加入 sys.path（PyInstaller 打包后不需要）。"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
