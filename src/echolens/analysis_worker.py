"""Minimal database-driven worker for DeepSeek content analysis."""

from dataclasses import dataclass

from echolens.analysis.deepseek import DeepSeekAnalyzer
from echolens.analysis.models import AnalysisResult
from echolens.core.config import Settings, get_settings
from echolens.storage.analysis_repository import AnalysisRepository
from echolens.storage.mysql import mysql_connection


@dataclass(frozen=True)
class AnalysisWorkerResult:
    """Result of processing at most one transcribed video."""

    handled: bool
    completed: bool
    failed: bool
    video_db_id: int | None = None
    error_message: str | None = None


class AnalysisWorker:
    """Advance videos from transcribed to done with DeepSeek."""

    def __init__(
        self,
        settings: Settings | None = None,
        analyzer: DeepSeekAnalyzer | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.analyzer = analyzer or DeepSeekAnalyzer(self.settings)

    def process_one(self) -> AnalysisWorkerResult:
        """Claim and analyze at most one transcribed video."""

        with mysql_connection(self.settings) as connection:
            repository = AnalysisRepository(connection)
            video = repository.claim_next_video()
            connection.commit()

        if video is None:
            return AnalysisWorkerResult(handled=False, completed=False, failed=False)

        video_db_id = int(video["id"])
        try:
            result: AnalysisResult = self.analyzer.analyze(
                transcript_text=str(video["transcript_text"]),
                description=video.get("description"),
            )
            with mysql_connection(self.settings) as connection:
                AnalysisRepository(connection).save_result(
                    video_db_id,
                    result,
                    model_name=self.settings.llm_model,
                )
                connection.commit()
            return AnalysisWorkerResult(
                handled=True,
                completed=True,
                failed=False,
                video_db_id=video_db_id,
            )
        except Exception as exc:
            error_message = str(exc)
            with mysql_connection(self.settings) as connection:
                AnalysisRepository(connection).mark_failed(video_db_id, error_message)
                connection.commit()
            return AnalysisWorkerResult(
                handled=True,
                completed=False,
                failed=True,
                video_db_id=video_db_id,
                error_message=error_message,
            )
