from __future__ import annotations

import asyncio
import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Mapping

import numpy as np

from app.audio import float_to_pcm16, split_text
from app.config import Settings

logger = logging.getLogger(__name__)


class GPUBusyError(Exception):
    pass


def _unwrap_generate(method) -> Any:
    """VoxCPM.generate is `def generate(*args, **kwargs)` wrapping `_generate`.

    inspect.signature(generate) has no named clone params, so callers that
    filter by parameter names would silently drop reference_wav_path / seed.
    """
    inst = getattr(method, "__self__", None)
    inner = getattr(inst, "_generate", None) if inst is not None else None
    return inner if callable(inner) else method


def _accepts(params: Mapping[str, inspect.Parameter], name: str) -> bool:
    if name in params:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())


class GPUBusyError(Exception):
    pass


class TtsEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = None
        self.sample_rate = 48000
        self.lock = asyncio.Lock()
        self.waiters = 0
        self.busy = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voxcpm")

    def _load_and_warmup(self) -> None:
        from voxcpm import VoxCPM

        try:
            import torchaudio

            torchaudio.set_audio_backend("soundfile")
        except Exception:
            pass

        self.model = VoxCPM.from_pretrained(
            self.settings.voxcpm_model,
            device=self.settings.voxcpm_device,
            load_denoiser=self.settings.voxcpm_load_denoiser,
            optimize=self.settings.voxcpm_optimize,
        )
        rate = getattr(getattr(self.model, "tts_model", None), "sample_rate", None)
        if rate:
            self.sample_rate = int(rate)

        self.model.generate(
            text="Xin chào.",
            cfg_value=self.settings.cfg_value,
            inference_timesteps=self.settings.inference_timesteps,
        )

    async def startup(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self.executor, self._load_and_warmup)

    async def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    @asynccontextmanager
    async def gpu_slot(self):
        self.waiters += 1
        try:
            try:
                await asyncio.wait_for(self.lock.acquire(), timeout=self.settings.gpu_lock_timeout)
            except asyncio.TimeoutError as exc:
                raise GPUBusyError("GPU bận, thử lại sau.") from exc
            self.waiters -= 1
            self.busy = True
            try:
                yield
            finally:
                self.busy = False
                self.lock.release()
        except GPUBusyError:
            self.waiters -= 1
            raise

    def vram_stats(self) -> dict[str, Any]:
        import torch

        if not torch.cuda.is_available():
            return {
                "gpu": None,
                "vram_allocated_gb": 0.0,
                "vram_reserved_gb": 0.0,
            }
        return {
            "gpu": torch.cuda.get_device_name(0),
            "vram_allocated_gb": round(torch.cuda.memory_allocated() / 1e9, 3),
            "vram_reserved_gb": round(torch.cuda.memory_reserved() / 1e9, 3),
        }

    def _call_kwargs(
        self,
        *,
        cfg_value: float | None,
        inference_timesteps: int | None,
        seed: int | None,
        reference_wav_path: str | None,
        prompt_wav_path: str | None,
        prompt_text: str | None,
        denoise: bool,
        method,
    ) -> dict[str, Any]:
        params = inspect.signature(_unwrap_generate(method)).parameters
        kwargs: dict[str, Any] = {
            "cfg_value": cfg_value if cfg_value is not None else self.settings.cfg_value,
            "inference_timesteps": (
                inference_timesteps
                if inference_timesteps is not None
                else self.settings.inference_timesteps
            ),
        }
        if seed is not None and _accepts(params, "seed"):
            kwargs["seed"] = seed
        if reference_wav_path and _accepts(params, "reference_wav_path"):
            kwargs["reference_wav_path"] = reference_wav_path
        if prompt_wav_path and _accepts(params, "prompt_wav_path"):
            kwargs["prompt_wav_path"] = prompt_wav_path
        if prompt_text and _accepts(params, "prompt_text"):
            kwargs["prompt_text"] = prompt_text
        if _accepts(params, "denoise"):
            kwargs["denoise"] = bool(denoise and self.settings.voxcpm_load_denoiser)
        if reference_wav_path and "reference_wav_path" not in kwargs:
            raise RuntimeError(
                "Không truyền được reference_wav_path vào VoxCPM.generate — clone bị bỏ silent."
            )
        if seed is not None and "seed" not in kwargs:
            raise RuntimeError("Không truyền được seed vào VoxCPM.generate.")
        logger.info(
            "voxcpm generate clone=%s seed=%s keys=%s",
            bool(kwargs.get("reference_wav_path")),
            kwargs.get("seed"),
            sorted(kwargs),
        )
        return kwargs

    def _generate_sync(
        self,
        text: str,
        cfg_value: float | None,
        inference_timesteps: int | None,
        seed: int | None,
        reference_wav_path: str | None,
        prompt_wav_path: str | None,
        prompt_text: str | None,
        denoise: bool,
    ) -> np.ndarray:
        assert self.model is not None
        kwargs = self._call_kwargs(
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
            seed=seed,
            reference_wav_path=reference_wav_path,
            prompt_wav_path=prompt_wav_path,
            prompt_text=prompt_text,
            denoise=denoise,
            method=self.model.generate,
        )
        pieces: list[np.ndarray] = []
        for sentence in split_text(text, self.settings.max_sentence_chars):
            wav = self.model.generate(text=sentence, **kwargs)
            pieces.append(np.asarray(wav, dtype=np.float32).reshape(-1))
        if not pieces:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(pieces)

    def _stream_sync(
        self,
        text: str,
        cfg_value: float | None,
        inference_timesteps: int | None,
        seed: int | None,
        reference_wav_path: str | None,
        prompt_wav_path: str | None,
        prompt_text: str | None,
        denoise: bool,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue,
    ) -> None:
        assert self.model is not None
        kwargs = self._call_kwargs(
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
            seed=seed,
            reference_wav_path=reference_wav_path,
            prompt_wav_path=prompt_wav_path,
            prompt_text=prompt_text,
            denoise=denoise,
            method=self.model.generate_streaming,
        )
        try:
            for sentence in split_text(text, self.settings.max_sentence_chars):
                for chunk in self.model.generate_streaming(text=sentence, **kwargs):
                    pcm = float_to_pcm16(np.asarray(chunk, dtype=np.float32))
                    asyncio.run_coroutine_threadsafe(queue.put(pcm), loop).result()
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(queue.put(exc), loop).result()

    async def generate(
        self,
        text: str,
        *,
        cfg_value: float | None = None,
        inference_timesteps: int | None = None,
        seed: int | None = None,
        reference_wav_path: str | None = None,
        prompt_wav_path: str | None = None,
        prompt_text: str | None = None,
        denoise: bool = False,
    ) -> np.ndarray:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            self._generate_sync,
            text,
            cfg_value,
            inference_timesteps,
            seed,
            reference_wav_path,
            prompt_wav_path,
            prompt_text,
            denoise,
        )

    async def stream_pcm(
        self,
        text: str,
        *,
        cfg_value: float | None = None,
        inference_timesteps: int | None = None,
        seed: int | None = None,
        reference_wav_path: str | None = None,
        prompt_wav_path: str | None = None,
        prompt_text: str | None = None,
        denoise: bool = False,
    ) -> AsyncIterator[bytes]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | Exception | None] = asyncio.Queue()
        future = loop.run_in_executor(
            self.executor,
            self._stream_sync,
            text,
            cfg_value,
            inference_timesteps,
            seed,
            reference_wav_path,
            prompt_wav_path,
            prompt_text,
            denoise,
            loop,
            queue,
        )
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            await future
