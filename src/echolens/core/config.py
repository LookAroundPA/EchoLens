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
    redis_video_lock_prefix: str = "echolens:lock:video"

    scan_stability_seconds: int = 30


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached application settings."""

    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
