# Bước 0–2: Chuẩn bị máy Windows

## Bước 0 — Điều kiện máy

- Windows 10/11, GPU **RTX 3070 8 GB**
- Không chạy game / LLM khác trên cùng GPU lúc serve
- NVIDIA driver mới; wheel PyTorch CUDA 12.x (không bắt buộc CUDA Toolkit đầy đủ)
- Python **3.11.x** (không 3.13+)
- FFmpeg trong PATH (clone MP3/WAV)
- Disk trống ≥ 15 GB, RAM ≥ 16 GB (32 GB tốt hơn)

```powershell
nvidia-smi
py -3.11 --version
ffmpeg -version
```

`nvidia-smi` phải hiện **RTX 3070**, Memory ~8192 MiB.

Cài FFmpeg nếu thiếu:

```powershell
winget install Gyan.FFmpeg
```

Đóng/mở lại terminal rồi kiểm `ffmpeg -version`.

## Bước 1 — Venv và dependency

```powershell
cd D:\ai\klarvid-voxcpm
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
```

Nếu `requirements.txt` chưa ghim torch CUDA, cài torch **trước** rồi mới `pip install -r requirements.txt`.

Kiểm CUDA:

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Kỳ vọng: `True NVIDIA GeForce RTX 3070`. Nếu `False`: đang dùng wheel CPU — gỡ torch rồi cài lại cu124.

## Bước 2 — Tải model và smoke infer

```powershell
# Hugging Face chậm:
$env:HF_ENDPOINT = "https://hf-mirror.com"

python -c "from huggingface_hub import snapshot_download; snapshot_download('openbmb/VoxCPM2'); print('ok')"
python .\scripts\smoke_load.py
```

**Pass:** `vi_demo.wav` nghe được, peak VRAM **< 7.5 GB**.  
**Fail OOM:** giữ `optimize=False`, `load_denoiser=False`; đóng app GPU khác.
