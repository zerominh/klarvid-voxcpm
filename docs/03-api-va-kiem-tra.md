# Bước 7–8: API, chạy, kiểm tra

## API v1

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/health` | — | JSON GPU, VRAM, busy, waiters |
| POST | `/v1/tts` | JSON | `audio/wav` |
| POST | `/v1/tts/stream` | JSON | chunked `audio/wav` |
| POST | `/v1/clone` | multipart | `audio/wav` |
| POST | `/v1/clone/stream` | multipart | chunked `audio/wav` |

JSON TTS:

```json
{
  "text": "Xin chào",
  "cfg_value": 2.0,
  "inference_timesteps": 10,
  "seed": 42
}
```

Voice design: mô tả trong ngoặc đầu câu, ví dụ `(giọng nữ trẻ, ấm)Xin chào`.

Clone multipart: `text`, file `reference_audio`, optional `prompt_text`, `denoise` mặc định `false`.

Lỗi: 400 text rỗng; 503 GPU bận quá timeout; 500 OOM.

GPU bận: request sau chờ lock tối đa 180s rồi 503.

## Chạy server

Nếu lỗi `running scripts is disabled`: xem [01-setup-windows.md](01-setup-windows.md) (Execution Policy).

```powershell
cd D:\minh\mydata\klarvid-voxcpm
.\scripts\start.ps1
```

Cách khác: `powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1`

Log kỳ vọng: load model, warmup, `Uvicorn running on http://127.0.0.1:8000`.

## Smoke

```powershell
.\scripts\smoke_test.ps1
```

Hai cửa sổ gọi TTS cùng lúc: request 2 chờ hoặc 503; **không** crash CUDA.

## Checklist

- `/health`: cuda, RTX 3070, `optimize: false`
- `smoke_tts.wav` nghe tiếng Việt rõ
- Stream phát được
- Clone gần giọng reference (file 3–10s)
- `nvidia-smi` lúc generate không đầy 8192 rồi chết process

## Troubleshooting

| Triệu chứng | Cách xử lý |
|-------------|------------|
| CUDA OOM | `VOXCPM_LOAD_DENOISER=false`, giảm `MAX_SENTENCE_CHARS`, đóng app GPU khác |
| Triton / `Python int too large` | giữ `VOXCPM_OPTIMIZE=false` |
| torchcodec / clone fail | FFmpeg trong PATH; engine ép backend `soundfile` |
| `torch.cuda.is_available() == False` | cài lại `torch` cu124, không dùng wheel CPU |
| Crash khi 2 process | chỉ `--workers 1`, tắt `--reload` |
| `running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

RTF ước lượng trên 3070 với `optimize=False`: **0.6–1.0** (đo sau lần chạy đầu, ghi vào README).
