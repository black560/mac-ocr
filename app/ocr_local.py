"""进程内 PaddleOCR-VL 推理适配层。

- transformers 后端：懒加载模型（首次 OCR 时才加载，避免拖慢启动），
  设备自动选择 mps（Apple GPU）> cpu；整个应用只用一个模型实例。
- mock 后端：返回固定文本，供无模型环境的开发/测试使用。
"""
import io
import os
import threading


def _log(msg: str) -> None:
    from app.config import log_file
    import datetime
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] [ocr] {msg}"
    print(line, flush=True)
    try:
        with open(log_file(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


class LocalOCR:
    def __init__(self, backend: str | None = None):
        import app.config as cfg
        self.backend = backend or cfg.OCR_BACKEND
        self._model = None
        self._processor = None
        self._device = None
        self._lock = threading.Lock()
        self.load_error: str | None = None

    def _resolve_model_path(self) -> str | None:
        import app.config as cfg
        local = cfg.models_dir()
        if local is not None:
            _log(f"使用内置模型目录: {local}")
            return str(local)
        _log(f"未找到内置模型，将从 HF 下载: {cfg.OCR_MODEL_ID}")
        return None

    def _load(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor
        import app.config as cfg

        # 兼容垫片：模型仓库的 remote code 用旧拼写 inputs_embeds 调
        # create_causal_mask，transformers 4.57 已改名 input_embeds
        from transformers import masking_utils
        if not getattr(masking_utils, "_ocrgo_compat", False):
            _orig = masking_utils.create_causal_mask

            def _create_causal_mask(*args, **kwargs):
                if "inputs_embeds" in kwargs and "input_embeds" not in kwargs:
                    kwargs["input_embeds"] = kwargs.pop("inputs_embeds")
                return _orig(*args, **kwargs)

            masking_utils.create_causal_mask = _create_causal_mask
            masking_utils._ocrgo_compat = True

        src = self._resolve_model_path() or cfg.OCR_MODEL_ID
        # 设备：默认自动 mps > cuda > cpu；MAC_OCR_DEVICE=mps|cpu|cuda 可显式
        # 指定（CI 与排查用），MAC_OCR_FORCE_CPU=1 等效 cpu
        want = os.environ.get("MAC_OCR_DEVICE", "").strip().lower()
        if not want and os.environ.get("MAC_OCR_FORCE_CPU"):
            want = "cpu"
        if want == "cpu":
            dev = "cpu"
        elif want == "mps":
            dev = "mps"
        elif want == "cuda":
            dev = "cuda"
        elif want:
            raise ValueError(f"未知 MAC_OCR_DEVICE={want!r}（可选 mps/cpu/cuda）")
        elif torch.backends.mps.is_available():
            dev = "mps"
        elif torch.cuda.is_available():
            dev = "cuda"  # Windows 开发机有 N 卡时
        else:
            dev = "cpu"
        # CPU 用 bf16：与原始权重同精度，内存减半（fp32 会翻倍到 3.6G）
        self._device, dtype = (
            dev, torch.float16 if dev in ("mps", "cuda") else torch.bfloat16)
        _log(f"加载 {src} 到 {self._device}（首次约需 10-60 秒）...")
        self._processor = AutoProcessor.from_pretrained(src, trust_remote_code=True)
        # 模型仓库把 PaddleOCRVLForConditionalGeneration 注册在 AutoModelForCausalLM
        # （transformers 4.57 的 AutoModelForImageTextToText 不识别该远端类）
        self._model = AutoModelForCausalLM.from_pretrained(
            src, trust_remote_code=True, dtype=dtype
        ).to(self._device)
        self._model.eval()
        _log("OCR 模型加载完成")

    def ensure_loaded(self) -> None:
        with self._lock:
            if self._model is None and self.load_error is None:
                try:
                    self._load()
                except Exception as e:  # 延迟到下次请求再重试
                    self.load_error = str(e)
                    _log(f"模型加载失败: {e!r}")
                    raise

    def ocr(self, png_bytes: bytes, max_new_tokens: int | None = None) -> str:
        """输入 PNG 页面图，返回该页识别文本。"""
        if self.backend == "mock":
            from scripts.mock_model_server import FAKE_OCR
            return FAKE_OCR

        self.ensure_loaded()
        with self._lock:  # 单请求串行，保护模型实例
            import torch
            from PIL import Image
            import app.config as cfg

            image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
            messages = [{
                "role": "user",
                "content": [{"type": "image", "image": image},
                            {"type": "text", "text": "OCR:"}],
            }]
            prompt = self._processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            inputs = self._processor(
                text=[prompt], images=[image], return_tensors="pt"
            ).to(self._device)
            with torch.inference_mode():
                out = self._model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens or cfg.OCR_MAX_NEW_TOKENS,
                    do_sample=False)
            text = self._processor.batch_decode(
                out[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
            return text.strip()

    def selftest(self) -> str:
        """打包自检：加载模型并对纯白图跑一次极短推理。

        走的是与真实请求完全相同的代码路径（processor → 前向 → 解码），
        用于在 CI 里验证 frozen 产物，避免"mock 冒烟通过、真机 import 失败"。
        """
        import io as _io
        from PIL import Image
        buf = _io.BytesIO()
        Image.new("RGB", (512, 512), "white").save(buf, format="PNG")
        return self.ocr(buf.getvalue(), max_new_tokens=8)


# 全局单例
ocr = LocalOCR()
