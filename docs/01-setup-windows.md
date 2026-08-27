# Cài lần đầu trên Windows

Làm **một lần** theo thứ tự bước 0 → 3. Các lần sau chỉ cần [chạy server](03-api-va-kiem-tra.md).

Repo ví dụ: `D:\minh\mydata\klarvid-voxcpm` (đổi `cd` cho đúng máy).

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

`nvidia-smi` phải hiện **RTX 3070**, Memory ~8192 MiB, cột CUDA Version ≥ 12.x. Nếu đã có ~1 GB VRAM bị Chrome/VS Code chiếm, tắt bớt trước khi load model.

Cài FFmpeg nếu thiếu:

```powershell
winget install Gyan.FFmpeg
```

Đóng/mở lại terminal rồi kiểm `ffmpeg -version`.

### Cho phép chạy script PowerShell

Windows mặc định chặn `.ps1`. Lỗi:

`cannot be loaded because running scripts is disabled on this system`

Sửa **một lần** cho user hiện tại (gõ `Y` nếu hỏi):

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Không muốn đổi policy thì mỗi lần start:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

## Bước 1 — Venv và dependency

```powershell
cd D:\minh\mydata\klarvid-voxcpm
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
copy .env.example .env
```

Cài `torch` CUDA **trước** `requirements.txt`. Prompt có `(.venv)` là đã activate.

Kiểm CUDA trong venv:

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None); print(torch.__version__, torch.version.cuda)"
```

Kỳ vọng: `True NVIDIA GeForce RTX 3070`. Nếu `False`:

```powershell
pip uninstall -y torch torchaudio
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
```

## Bước 2 — Tải model và smoke infer

```powershell
# Hugging Face chậm:
$env:HF_ENDPOINT = "https://hf-mirror.com"

python .\scripts\smoke_load.py
```

Lệnh này **không** mở API. Nó tải VoxCPM2 (~5 GB lần đầu), generate 1 câu tiếng Việt, ghi `vi_demo.wav` ở gốc repo.

**Pass:** nghe được `vi_demo.wav`, peak VRAM **< 7.5 GB**.  
**Fail OOM:** đóng Chrome/app GPU khác; giữ `optimize=False`, `load_denoiser=False`.

## Bước 3 — Khởi động server (lần đầu và các lần sau)

```powershell
cd D:\minh\mydata\klarvid-voxcpm
.\scripts\start.ps1
```

Hoặc không dùng script (venv đã activate):

```powershell
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1
```

Chỉ `--workers 1`. Không `--reload`. Lần đầu sau cài: load model + warmup vài phút.

Thành công khi log có `Uvicorn running on http://127.0.0.1:8001`.

Cửa sổ khác:

```powershell
curl.exe http://127.0.0.1:8001/health
start http://127.0.0.1:8001/docs
```

Tắt server: `Ctrl+C` ở cửa sổ `start.ps1`.
