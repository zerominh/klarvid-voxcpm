from pydantic import BaseModel, Field


class TtsRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Text to speak. Voice design: '(description)spoken text'.",
        examples=["Xin chào, Klarvid."],
    )
    cfg_value: float | None = Field(default=None, description="Guidance scale. Server default 2.0.")
    inference_timesteps: int | None = Field(
        default=None, description="Diffusion steps. Server default 10."
    )
    seed: int | None = Field(default=None, description="Optional reproducibility seed.")
    voice_id: str | None = Field(
        default=None,
        description="Saved voice from POST /v1/voices. Uses stored sample audio + prompt_text.",
    )


class VoiceResponse(BaseModel):
    id: str
    name: str | None
    prompt_text: str
    created_at: str


class VoiceListResponse(BaseModel):
    voices: list[VoiceResponse]


class HealthResponse(BaseModel):
    status: str
    gpu: str | None
    vram_allocated_gb: float
    vram_reserved_gb: float
    busy: bool
    queue_waiters: int
    optimize: bool
    load_denoiser: bool
    model: str
    device: str
    sample_rate: int
