# Bước 3–6: Cấu trúc code

## Cây thư mục

```
klarvid-voxcpm/
  app/
    __init__.py
    config.py
    engine.py
    audio.py
    schemas.py
    main.py
  scripts/
    start.ps1
    smoke_test.ps1
    smoke_load.py
  voices/
  docs/
  .env.example
  requirements.txt
  README.md
```

## Ràng buộc Windows + RTX 3070

- `optimize=False` — Triton/`torch.compile` trên Windows hay lỗi
- `load_denoiser=False` — tiết kiệm VRAM 8 GB
- Uvicorn `--workers 1`
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
- Text dài: cắt câu rồi ghép PCM

Load model:

```python
model = VoxCPM.from_pretrained(
    "openbmb/VoxCPM2",
    device="cuda",
    load_denoiser=False,
    optimize=False,
)
```

## Engine (`app/engine.py`)

- Một instance load lúc FastAPI lifespan
- `asyncio.Lock` + timeout `GPU_LOCK_TIMEOUT` (mặc định 180s) → HTTP 503
- `generate` / `generate_streaming` trong `ThreadPoolExecutor(max_workers=1)`
- Giữ lock suốt streaming
- Warmup 1 câu ngắn khi start
- `/health` đọc VRAM qua `torch.cuda.memory_allocated()` / `memory_reserved()`

## Audio (`app/audio.py`)

- Cắt `. ! ? …` và xuống dòng; mỗi đoạn ≤ `MAX_SENTENCE_CHARS`
- float32 → PCM16 LE
- Non-stream: WAV 48 kHz mono
- Stream: WAV header size `0xFFFFFFFF` rồi chunk PCM16
- Clone: tempfile, xóa trong `finally`

## FastAPI (`app/main.py`)

Lifespan: load → warmup → serve.

Cấm `--reload` và `--workers` > 1 khi model đã nằm trên GPU.
