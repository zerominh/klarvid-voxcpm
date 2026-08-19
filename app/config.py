from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    host: str = "127.0.0.1"
    port: int = 8000
    voxcpm_model: str = "openbmb/VoxCPM2"
    voxcpm_device: str = "cuda"
    voxcpm_optimize: bool = False
    voxcpm_load_denoiser: bool = False
    cfg_value: float = 2.0
    inference_timesteps: int = 10
    gpu_lock_timeout: float = 180
    max_sentence_chars: int = 400


settings = Settings()
