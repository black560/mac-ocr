"""Mock LLM 服务（OpenAI 兼容），供无 ollama 环境的测试使用。

只实现 /v1/chat/completions 与 /v1/models，OCR 侧用 OCR_BACKEND=mock 覆盖。
"""
import os

from fastapi import FastAPI, Request

LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:4b-instruct-2507-q4_K_M")

FAKE_OCR = """COMMERCIAL INVOICE / PACKING LIST
CNF SHANGHAI PORT
No Description of Goods Qnty (CBM) Unit Price CNF $/m3 Amount CNF $
1 COMMERCIAL PLYWOOD 1220X2440X5MM MR E1 POPLAR ARSER-PLY 12.36 285.00 3,522.60
2 COMMERCIAL PLYWOOD 1220X2440X5MM MR E1 POPLAR ARSER-PLY 8.40 285.00 2,394.00
3 COMMERCIAL PLYWOOD 1220X2440X12MM E2 COMBI ARSER-PLY 25.60 352.00 9,011.20
4 FILM FACED PLYWOOD 1220X2440X18MM BLACK FILM ECOPLY EUCA QUALITY 30.00 465.00 13,950.00
5 MELAMINE MDF 1220X2440X15MM Warm white YS003 SUNWELL 18.50 318.00 5,883.00
6 MELAMINE MDF 1220X2440X15MM Walnut 790-3 SUNWELL 6.25 318.00 1,987.50
7 PAPER OVERLAY MDF 1220X2440X17MM SATIN HANTEX 9.80 296.00 2,900.80
8 COMMERCIAL PLYWOOD 2135X915X5MM MR E1 POPLAR ARSER-PLY 4.32 302.00 1,304.64
TOTAL CNF SHANGHAI 40,953.74
Break Bulk Shipment. Payment by T/T within 15 days after B/L date."""

FAKE_RESULT = """| goods description | qnty m3 |  |  | CNF $/m3 | total amt (cnf) |
| --- | --- | --- | --- | --- | --- |
| PLY 5MM "ARSER-PLY" | 20.76 |  |  | 285.00 | 5,916.60 |
| PLY 12MM "ARSER-PLY" | 25.60 |  |  | 352.00 | 9,011.20 |
| FFP 18MM "ECOPLY" BLACK FILM EUCA QUALITY | 30.00 |  |  | 465.00 | 13,950.00 |
| MEL MDF 15MM "SUNWELL" | 24.75 |  |  | 318.00 | 7,870.50 |
| POL MDF 17MM "HANTEX" | 9.80 |  |  | 296.00 | 2,900.80 |
| PLY 2135X915X5MM "ARSER-PLY" | 4.32 |  |  | 302.00 | 1,304.64 |
| TOTAL | 115.23 |  |  |  | 40,953.74 |

与原单 Total 40,953.74 一致。"""

app = FastAPI()


@app.get("/v1/models")
def models():
    return {"data": [{"id": LLM_MODEL}]}


@app.post("/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": FAKE_RESULT},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
