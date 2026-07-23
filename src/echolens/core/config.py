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
    llm_max_tokens: int = Field(default=8192, ge=256)

    qa_model: str = "deepseek-v4-pro"
    qa_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    qa_max_tokens: int = Field(default=4096, ge=512)
    qa_default_sources: int = Field(default=8, ge=2, le=20)

    semantic_model: str = "BAAI/bge-small-zh-v1.5"
    semantic_model_cache_dir: Path = Path("data/models/fastembed")
    semantic_query_prefix: str = "为这个句子生成表示以用于检索相关文章："
    semantic_index_path: Path = Path("data/semantic/echolens.sqlite3")
    semantic_auto_sync: bool = True
    semantic_chunk_max_chars: int = Field(default=420, ge=80, le=2000)
    semantic_chunk_max_segments: int = Field(default=3, ge=1, le=8)
    semantic_max_chunks_per_video: int = Field(default=2, ge=1, le=10)
    semantic_min_score: float = Field(default=0.18, ge=0.0, le=1.0)

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
