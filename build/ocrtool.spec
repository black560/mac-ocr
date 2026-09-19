# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：产出 OcrTool.app（macOS）。

用法（必须在 macOS arm64 上执行）：
    pyinstaller build/ocrtool.spec --noconfirm
构建后由 build/build_app.sh 拷入 ollama 二进制与模型并压缩。

设计要点：
- onedir 模式产出 .app（Contents/MacOS/OcrTool），不打包成单文件可执行——
  单文件模式每次启动要解压 3G+ 的 PyTorch 到临时目录，冷启动极慢。
- 模型与 ollama 不放进 spec 的 datas，由 build_app.sh 放入 Resources/，
  这样换模型无需重新 pyinstaller。
"""
import os

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

datas = [
    ("../app/ui/index.html", "app/ui"),
    ("../app/ui/marked.min.js", "app/ui"),
]
# pyobjc 没有 PyInstaller hook：.bridgesupport 等元数据不收集的话，
# 打包后 macOS 上 import AppKit 可能失败（窗口起不来）
for _m in ("objc", "AppKit", "Foundation", "WebKit", "Quartz", "PyObjCTools"):
    try:
        datas += collect_data_files(_m)
    except Exception:
        pass
hiddenimports = [
    "app.config", "app.ocr_local", "app.pipeline", "app.server",
    "app.default_prompt", "app.main_app",
    # pywebview 的后端在函数内 import，显式声明防漏
    "webview.platforms.cocoa",
    "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
]

a = Analysis(
    ["../run.py"],
    pathex=[".."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy.tests"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="OcrTool",
    console=False,           # macOS 上 .app 无所谓，Windows 调试用时改 True
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    name="OcrTool",
    upx=False,
)
app = BUNDLE(
    coll,
    name="OcrTool.app",
    icon=None,
    bundle_identifier="com.local.ocrgoodsextract",
    info_plist={
        "CFBundleDisplayName": "OcrTool",
        "CFBundleShortVersionString": os.environ.get("APP_VERSION", "0.1.0"),
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.3",
    },
)
