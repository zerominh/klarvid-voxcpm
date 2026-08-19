from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.audio import float_to_pcm16, pcm16_to_wav_bytes, wav_header_unknown_size
from app.config import settings
from app.engine import GPUBusyError, TtsEngine
from app.schemas import HealthResponse, TtsRequest, VoiceListResponse, VoiceResponse
from app.voices import InvalidVoiceId, VoiceNotFound, VoiceStore

engine = TtsEngine(settings)
store = VoiceStore(Path(settings.voices_dir))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await engine.startup()
    yield
    await engine.shutdown()


app = FastAPI(
    title="Klarvid VoxCPM TTS",
    version="0.1.0",
    description=(
        "Local VoxCPM2 TTS. Success synthesis responses are raw audio/wav. "
        "Not OpenAI-compatible. Integration contract: docs/api.md"
    ),
    lifespan=lifespan,
)


def _require_voice(voice_id: str):
    try:
        return store.get(voice_id)
    except InvalidVoiceId as exc:
        raise HTTPException(status_code=400, detail="voice_id không hợp lệ") from exc
    except VoiceNotFound as exc:
        raise HTTPException(status_code=404, detail="voice_id không tồn tại") from exc


def _busy_http() -> HTTPException:
    return HTTPException(status_code=503, detail="GPU bận, thử lại sau.")


def _voice_kwargs(voice_id: str | None) -> dict:
    if not voice_id:
        return {}
    voice = _require_voice(voice_id)
    return {
        "reference_wav_path": voice.audio_path,
        "prompt_wav_path": voice.audio_path,
        "prompt_text": voice.prompt_text,
    }


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    stats = engine.vram_stats()
    return {
        "status": "busy" if engine.busy else "ok",
        "gpu": stats["gpu"],
        "vram_allocated_gb": stats["vram_allocated_gb"],
        "vram_reserved_gb": stats["vram_reserved_gb"],
        "busy": engine.busy,
        "queue_waiters": engine.waiters,
        "optimize": settings.voxcpm_optimize,
        "load_denoiser": settings.voxcpm_load_denoiser,
        "model": settings.voxcpm_model,
        "device": settings.voxcpm_device,
        "sample_rate": engine.sample_rate,
    }


@app.post(
    "/v1/tts",
    tags=["tts"],
    response_class=Response,
    responses={
        200: {"content": {"audio/wav": {}}},
        404: {"description": "Unknown voice_id"},
        503: {"description": "GPU busy"},
    },
)
async def tts(body: TtsRequest):
    voice_kw = _voice_kwargs(body.voice_id)
    try:
        async with engine.gpu_slot():
            wav = await engine.generate(
                body.text,
                cfg_value=body.cfg_value,
                inference_timesteps=body.inference_timesteps,
                seed=body.seed,
                **voice_kw,
            )
    except GPUBusyError:
        raise _busy_http() from None
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=pcm16_to_wav_bytes(float_to_pcm16(wav), engine.sample_rate),
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="tts.wav"'},
    )


@app.post(
    "/v1/tts/stream",
    tags=["tts"],
    response_class=StreamingResponse,
    responses={
        200: {"content": {"audio/wav": {}}},
        404: {"description": "Unknown voice_id"},
        503: {"description": "GPU busy"},
    },
)
async def tts_stream(body: TtsRequest):
    voice_kw = _voice_kwargs(body.voice_id)

    async def chunks():
        try:
            async with engine.gpu_slot():
                yield wav_header_unknown_size(engine.sample_rate)
                async for pcm in engine.stream_pcm(
                    body.text,
                    cfg_value=body.cfg_value,
                    inference_timesteps=body.inference_timesteps,
                    seed=body.seed,
                    **voice_kw,
                ):
                    yield pcm
        except GPUBusyError:
            raise _busy_http() from None

    return StreamingResponse(chunks(), media_type="audio/wav")


@app.post("/v1/voices", response_model=VoiceResponse, tags=["voices"], status_code=201)
async def create_voice(
    prompt_text: str = Form(..., description="Transcript đúng của file audio mẫu"),
    reference_audio: UploadFile = File(...),
    name: str | None = Form(None),
):
    if not prompt_text.strip():
        raise HTTPException(status_code=400, detail="prompt_text rỗng")
    data = await reference_audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="reference_audio rỗng")
    suffix = Path(reference_audio.filename or "ref.wav").suffix or ".wav"
    voice = store.create(
        prompt_text=prompt_text.strip(),
        audio=data,
        suffix=suffix,
        name=(name.strip() if name and name.strip() else None),
    )
    return voice.public()


@app.get("/v1/voices", response_model=VoiceListResponse, tags=["voices"])
async def list_voices():
    return {"voices": [v.public() for v in store.list()]}


@app.get("/v1/voices/{voice_id}", response_model=VoiceResponse, tags=["voices"])
async def get_voice(voice_id: str):
    return _require_voice(voice_id).public()


@app.delete("/v1/voices/{voice_id}", tags=["voices"])
async def delete_voice(voice_id: str):
    _require_voice(voice_id)
    store.delete(voice_id)
    return {"ok": True, "id": voice_id}


async def _save_upload(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "ref.wav").suffix or ".wav"
    fd, path = tempfile.mkstemp(prefix="voxcpm_ref_", suffix=suffix)
    os.close(fd)
    data = await upload.read()
    Path(path).write_bytes(data)
    return path


@app.post(
    "/v1/clone",
    tags=["clone"],
    response_class=Response,
    responses={200: {"content": {"audio/wav": {}}}, 503: {"description": "GPU busy"}},
)
async def clone(
    text: str = Form(...),
    reference_audio: UploadFile = File(...),
    prompt_text: str | None = Form(None),
    denoise: bool = Form(False),
    cfg_value: float | None = Form(None),
    inference_timesteps: int | None = Form(None),
    seed: int | None = Form(None),
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="text rỗng")
    path = await _save_upload(reference_audio)
    prompt_path = path if prompt_text else None
    try:
        async with engine.gpu_slot():
            wav = await engine.generate(
                text,
                cfg_value=cfg_value,
                inference_timesteps=inference_timesteps,
                seed=seed,
                reference_wav_path=path,
                prompt_wav_path=prompt_path,
                prompt_text=prompt_text,
                denoise=denoise,
            )
    except GPUBusyError:
        raise _busy_http() from None
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        Path(path).unlink(missing_ok=True)
    return Response(
        content=pcm16_to_wav_bytes(float_to_pcm16(wav), engine.sample_rate),
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="clone.wav"'},
    )


@app.post(
    "/v1/clone/stream",
    tags=["clone"],
    response_class=StreamingResponse,
    responses={200: {"content": {"audio/wav": {}}}, 503: {"description": "GPU busy"}},
)
async def clone_stream(
    text: str = Form(...),
    reference_audio: UploadFile = File(...),
    prompt_text: str | None = Form(None),
    denoise: bool = Form(False),
    cfg_value: float | None = Form(None),
    inference_timesteps: int | None = Form(None),
    seed: int | None = Form(None),
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="text rỗng")
    path = await _save_upload(reference_audio)
    prompt_path = path if prompt_text else None

    async def chunks():
        try:
            async with engine.gpu_slot():
                yield wav_header_unknown_size(engine.sample_rate)
                async for pcm in engine.stream_pcm(
                    text,
                    cfg_value=cfg_value,
                    inference_timesteps=inference_timesteps,
                    seed=seed,
                    reference_wav_path=path,
                    prompt_wav_path=prompt_path,
                    prompt_text=prompt_text,
                    denoise=denoise,
                ):
                    yield pcm
        except GPUBusyError:
            raise _busy_http() from None
        finally:
            Path(path).unlink(missing_ok=True)

    return StreamingResponse(chunks(), media_type="audio/wav")
