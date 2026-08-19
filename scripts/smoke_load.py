"""Load VoxCPM2 and synthesize one Vietnamese sentence. Run from repo root with venv active."""

from voxcpm import VoxCPM
import soundfile as sf
import torch

print("CUDA:", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")

model = VoxCPM.from_pretrained(
    "openbmb/VoxCPM2",
    device="cuda",
    load_denoiser=False,
    optimize=False,
)

kwargs = dict(
    text="Xin chào, đây là thử nghiệm chuyển văn bản thành giọng nói.",
    cfg_value=2.0,
    inference_timesteps=10,
)
try:
    wav = model.generate(**kwargs, seed=42)
except TypeError:
    wav = model.generate(**kwargs)
sf.write("vi_demo.wav", wav, model.tts_model.sample_rate)
print("saved vi_demo.wav")
if torch.cuda.is_available():
    print("peak VRAM GB", round(torch.cuda.max_memory_allocated() / 1e9, 3))
