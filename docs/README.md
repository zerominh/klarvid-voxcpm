# Runbook phương án A — VoxCPM2 trên Windows

TTS server FastAPI cho Klarvid, chạy local trên **RTX 3070 8 GB**. Một process, một GPU lock, bind mặc định `127.0.0.1:8000`.

## Thứ tự đọc

1. [01-setup-windows.md](01-setup-windows.md) — GPU, Python 3.11, venv, tải model, smoke infer
2. [02-implement.md](02-implement.md) — cấu trúc code, engine, audio, FastAPI
3. [03-api-va-kiem-tra.md](03-api-va-kiem-tra.md) — API, start, smoke, troubleshooting
4. [api.md](api.md) — **contract tích hợp cho client / AI** ([openapi.yaml](openapi.yaml))

## Không làm gì

- Không `--workers` > 1, không `--reload` khi đã load model
- Không Nano-vLLM / vLLM-Omni trên card 8 GB Windows
- Không `optimize=True` trừ khi đã đo VRAM và Triton Windows ổn định
