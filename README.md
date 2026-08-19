# Klarvid VoxCPM TTS (Windows, RTX 3070)

Server FastAPI phương án A: **VoxCPM2** text-to-speech, 1 worker, bind `127.0.0.1:8000`.

Chi tiết từng bước: [docs/README.md](docs/README.md).

## Yêu cầu

- Windows + RTX 3070 8 GB
- Python 3.11
- FFmpeg trong PATH
- PyTorch CUDA 12.x

## Cài

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
copy .env.example .env
```

Smoke model (lần đầu tải ~5 GB):

```powershell
python .\scripts\smoke_load.py
```

## Chạy

```powershell
.\scripts\start.ps1
```

Chỉ `--workers 1`. Không `--reload`.

```powershell
.\scripts\smoke_test.ps1
# clone: .\scripts\smoke_test.ps1 D:\path\speaker.wav
```

## API (tích hợp)

Contract cho client và AI: [docs/api.md](docs/api.md) · spec [docs/openapi.yaml](docs/openapi.yaml).

Khi server chạy: `http://127.0.0.1:8000/docs` và `/openapi.json`.

- `GET /health`
- `POST /v1/tts` JSON `{ "text": "..." }` → WAV 48 kHz
- `POST /v1/tts/stream`
- `POST /v1/clone` multipart `text` + `reference_audio`
- `POST /v1/clone/stream`

Voice design: `(giọng nữ trẻ, ấm)Xin chào`.

Mặc định `VOXCPM_OPTIMIZE=false`, `VOXCPM_LOAD_DENOISER=false` (an toàn Windows / 8 GB VRAM).

RTF trên RTX 3070 (`optimize=False`): đo sau lần chạy đầu, ước lượng 0.6–1.0.
