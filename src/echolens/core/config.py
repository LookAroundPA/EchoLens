"""Application configuration for EchoLens."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    douyin_source_dir: Path = Field(
        default=Path(r"D:\BaiduNetdiskDownload\dy src"),
        description="Root directory where the external Douyin collector writes video files.",
    )
    douyin_source_host_dir: Path = Field(
        default=Path(r"D:\BaiduNetdiskDownload\dy src"),
        description="Host source root used to map legacy Windows database paths inside Docker.",
    )
    audio_output_dir: Path = Field(
        default=Path(r"D:\BaiduNetdiskDownload\dy out"),
        description="Directory where extracted WAV files are stored.",
    )

    whisper_model: str = "large-v3"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: str = ""
    whisper_beam_size: int = 5
    whisper_vad_filter: bool = True

    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_model: str = "deepseek-v4-flash"
    llm_base_url: str = "https://api.deepseek.com"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2048, ge=256)

    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_password: str = ""
    mysql_database: str = "echolens"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_db: int = 0

    redis_video_queue: str = "echolens:queue:video"
    redis_video_processing_queue: str = "echolens:queue:video:processing"
    redis_video_lock_prefix: str = "echolens:lock:video"

    redis_operation_queue: str = "echolens:queue:operations"
    redis_operation_processing_queue: str = "echolens:queue:operations:processing"

    scan_stability_seconds: int = 30

    def parsed_api_cors_origins(self) -> list[str]:
        """Return normalized browser origins allowed to call the HTTP API."""

        return [
            origin.strip().rstrip("/")
            for origin in self.api_cors_origins.split(",")
            if origin.strip()
        ]


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached application settings."""

    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
