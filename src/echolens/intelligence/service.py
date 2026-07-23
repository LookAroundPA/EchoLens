"""Application service for indexing and rebuilding investment intelligence."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from echolens.analysis.models import MarketInsight
from echolens.intelligence.repository import IntelligenceRepository

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any


@dataclass(frozen=True)
class IntelligenceRebuildResult:
    """Summary of one historical intelligence rebuild."""

    analyses_scanned: int
    analyses_indexed: int
    opinions_indexed: int
    invalid_insights: int
    orphan_topics_removed: int


class IntelligenceService:
    """Coordinate intelligence indexing from stored or new analysis results."""

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection
        self.repository = IntelligenceRepository(connection)

    def index_video(self, video_db_id: int, insights: list[MarketInsight]) -> int:
        """Index a newly completed analysis."""

        return self.repository.index_video_analysis(video_db_id, insights)

    def count_rebuild_candidates(self) -> int:
        """Count analyses produced by the market-insight-aware analyzer."""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT COUNT(*) AS item_count
            FROM analyses
            WHERE market_insights_json IS NOT NULL
            """
        )
        row = cursor.fetchone() or {}
        cursor.close()
        return int(row.get("item_count") or 0)

    def rebuild(self, limit: int | None = None) -> IntelligenceRebuildResult:
        """Re-index historical analysis JSON without calling the LLM."""

        limit_sql = ""
        params: tuple[Any, ...] = ()
        if limit is not None:
            limit_sql = " LIMIT %s"
            params = (limit,)

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT video_id, market_insights_json
            FROM analyses
            WHERE market_insights_json IS NOT NULL
            ORDER BY id
            """
            + limit_sql,
            params,
        )
        rows = list(cursor.fetchall())
        cursor.close()

        indexed = opinions = invalid = 0
        for row in rows:
            parsed, invalid_count = self._parse_insights(row.get("market_insights_json"))
            invalid += invalid_count
            if invalid_count:
                continue
            opinions += self.repository.index_video_analysis(int(row["video_id"]), parsed)
            indexed += 1

        orphan_topics_removed = self.repository.remove_unreferenced_pending_topics()
        return IntelligenceRebuildResult(
            analyses_scanned=len(rows),
            analyses_indexed=indexed,
            opinions_indexed=opinions,
            invalid_insights=invalid,
            orphan_topics_removed=orphan_topics_removed,
        )

    @staticmethod
    def _parse_insights(value: Any) -> tuple[list[MarketInsight], int]:
        if value is None:
            return [], 0
        try:
            payload = json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            return [], 1
        if not isinstance(payload, list):
            return [], 1

        insights: list[MarketInsight] = []
        invalid = 0
        for item in payload:
            try:
                insights.append(MarketInsight.model_validate(item))
            except (ValidationError, TypeError, ValueError):
                invalid += 1
        return insights, invalid
