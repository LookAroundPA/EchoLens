"""MySQL persistence for normalized topics, opinion history, and changes."""

from __future__ import annotations

from datetime import datetime
import json
from typing import TYPE_CHECKING, Any

from echolens.analysis.models import MarketInsight
from echolens.intelligence.changes import build_change_summary, detect_opinion_change
from echolens.intelligence.normalization import find_seed_topic, normalize_topic_name

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any


class IntelligenceRepository:
    """Project analysis JSON into queryable investment-intelligence tables."""

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def index_video_analysis(self, video_db_id: int, insights: list[MarketInsight]) -> int:
        """Upsert one video's opinions and rebuild affected creator-topic histories."""

        context = self._get_analysis_context(video_db_id)
        if context is None:
            raise RuntimeError(f"Analysis row not found for video {video_db_id}")

        analysis_id = int(context["analysis_id"])
        creator_id = int(context["creator_id"])
        published_at = self._resolve_published_at(context)
        existing = self._get_existing_opinions(analysis_id)
        affected_pairs = {
            (int(row["creator_id"]), int(row["topic_id"])) for row in existing
        }
        current_indexes: set[int] = set()

        for insight_index, insight in enumerate(insights):
            topic_id, match_method, match_confidence = self._resolve_topic(
                insight.subject,
                insight.subject_type,
            )
            opinion_id = self._upsert_opinion(
                analysis_id=analysis_id,
                video_db_id=video_db_id,
                creator_id=creator_id,
                topic_id=topic_id,
                insight_index=insight_index,
                insight=insight,
                match_method=match_method,
                match_confidence=match_confidence,
                published_at=published_at,
            )
            current_indexes.add(insight_index)
            affected_pairs.add((creator_id, topic_id))
            self._delete_change_for_current_opinion(opinion_id)

        stale_ids = [
            int(row["id"])
            for row in existing
            if int(row["insight_index"]) not in current_indexes
        ]
        self._delete_stale_opinions(stale_ids)

        for pair_creator_id, pair_topic_id in sorted(affected_pairs):
            self.rebuild_change_history(pair_creator_id, pair_topic_id)
        return len(insights)

    def remove_video_analysis(self, video_db_id: int) -> int:
        """Remove stale normalized opinions after a video's transcript changes."""

        context = self._get_analysis_context(video_db_id)
        if context is None:
            return 0
        existing = self._get_existing_opinions(int(context["analysis_id"]))
        if not existing:
            return 0
        affected_pairs = {
            (int(row["creator_id"]), int(row["topic_id"])) for row in existing
        }
        opinion_ids = [int(row["id"]) for row in existing]
        self._delete_stale_opinions(opinion_ids)
        for creator_id, topic_id in sorted(affected_pairs):
            self.rebuild_change_history(creator_id, topic_id)
        self.remove_unreferenced_pending_topics()
        return len(opinion_ids)

    def rebuild_change_history(self, creator_id: int, topic_id: int) -> None:
        """Recompute one creator-topic change timeline after manual topic maintenance."""

        self._rebuild_change_history(creator_id, topic_id)

    def _get_analysis_context(self, video_db_id: int) -> dict[str, Any] | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                a.id AS analysis_id,
                v.creator_id,
                v.source_create_time,
                v.created_at
            FROM analyses AS a
            INNER JOIN videos AS v ON v.id = a.video_id
            WHERE a.video_id = %s
            LIMIT 1
            """,
            (video_db_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row

    def _get_existing_opinions(self, analysis_id: int) -> list[dict[str, Any]]:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, creator_id, topic_id, insight_index
            FROM creator_topic_opinions
            WHERE analysis_id = %s
            """,
            (analysis_id,),
        )
        rows = list(cursor.fetchall())
        cursor.close()
        return rows

    def _resolve_topic(self, subject: str, subject_type: str) -> tuple[int, str, str]:
        normalized_subject = normalize_topic_name(subject)
        if not normalized_subject:
            raise ValueError("Market insight subject cannot normalize to an empty topic")

        seed = find_seed_topic(subject, subject_type)
        if seed is not None:
            canonical_normalized = normalize_topic_name(seed.canonical_name)
            row = self._find_topic(subject_type, canonical_normalized)
            topic_id = (
                int(row["id"])
                if row is not None
                else self._create_topic(
                    seed.canonical_name,
                    canonical_normalized,
                    subject_type,
                    status="active",
                )
            )
            self._activate_topic(topic_id, seed.canonical_name)
            for alias in (seed.canonical_name, *seed.aliases, subject):
                self._ensure_alias(
                    topic_id,
                    alias,
                    normalize_topic_name(alias),
                    "seed",
                )
            return topic_id, "seed_alias", "high"

        row = self._find_topic_by_alias(subject_type, normalized_subject)
        if row is not None:
            return int(row["id"]), "exact_alias", "high"

        row = self._find_topic(subject_type, normalized_subject)
        if row is not None:
            topic_id = int(row["id"])
            self._ensure_alias(topic_id, subject, normalized_subject, "observed")
            return topic_id, "exact_topic", "high"

        topic_id = self._create_topic(
            subject.strip(),
            normalized_subject,
            subject_type,
            status="pending",
        )
        self._ensure_alias(topic_id, subject, normalized_subject, "observed")
        return topic_id, "created_pending", "medium"

    def _create_topic(
        self,
        canonical_name: str,
        normalized_name: str,
        subject_type: str,
        *,
        status: str,
    ) -> int:
        now = datetime.now()
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO topics (
                canonical_name,
                normalized_name,
                topic_type,
                status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                updated_at = VALUES(updated_at),
                id = LAST_INSERT_ID(id)
            """,
            (canonical_name, normalized_name, subject_type, status, now, now),
        )
        topic_id = int(cursor.lastrowid)
        cursor.close()
        if topic_id:
            return topic_id
        row = self._find_topic(subject_type, normalized_name)
        if row is None:
            raise RuntimeError(f"Failed to resolve topic: {canonical_name}")
        return int(row["id"])

    def _activate_topic(self, topic_id: int, canonical_name: str) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE topics
            SET canonical_name = %s,
                status = 'active',
                updated_at = %s
            WHERE id = %s
            """,
            (canonical_name, datetime.now(), topic_id),
        )
        cursor.close()

    def _find_topic_by_alias(
        self,
        subject_type: str,
        normalized_alias: str,
    ) -> dict[str, Any] | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT t.id
            FROM topic_aliases AS ta
            INNER JOIN topics AS t ON t.id = ta.topic_id
            WHERE t.topic_type = %s
              AND ta.normalized_alias = %s
              AND t.status <> 'archived'
            ORDER BY CASE WHEN t.status = 'active' THEN 0 ELSE 1 END, t.id
            LIMIT 1
            """,
            (subject_type, normalized_alias),
        )
        row = cursor.fetchone()
        cursor.close()
        return row

    def _find_topic(self, subject_type: str, normalized_name: str) -> dict[str, Any] | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id
            FROM topics
            WHERE topic_type = %s
              AND normalized_name = %s
            LIMIT 1
            """,
            (subject_type, normalized_name),
        )
        row = cursor.fetchone()
        cursor.close()
        return row

    def _ensure_alias(
        self,
        topic_id: int,
        alias: str,
        normalized_alias: str,
        source: str,
    ) -> None:
        if not normalized_alias:
            return
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO topic_aliases (
                topic_id,
                alias,
                normalized_alias,
                source,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                alias = VALUES(alias),
                source = CASE
                    WHEN topic_aliases.source = 'manual' THEN topic_aliases.source
                    ELSE VALUES(source)
                END
            """,
            (topic_id, alias.strip(), normalized_alias, source, datetime.now()),
        )
        cursor.close()

    def _upsert_opinion(
        self,
        *,
        analysis_id: int,
        video_db_id: int,
        creator_id: int,
        topic_id: int,
        insight_index: int,
        insight: MarketInsight,
        match_method: str,
        match_confidence: str,
        published_at: datetime,
    ) -> int:
        now = datetime.now()
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO creator_topic_opinions (
                creator_id,
                video_id,
                analysis_id,
                insight_index,
                topic_id,
                raw_subject,
                match_method,
                match_confidence,
                stance,
                source_type,
                time_horizon,
                confidence,
                conclusion,
                reasoning_json,
                risks_json,
                evidence_quote,
                published_at,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                topic_id = VALUES(topic_id),
                raw_subject = VALUES(raw_subject),
                match_method = VALUES(match_method),
                match_confidence = VALUES(match_confidence),
                stance = VALUES(stance),
                source_type = VALUES(source_type),
                time_horizon = VALUES(time_horizon),
                confidence = VALUES(confidence),
                conclusion = VALUES(conclusion),
                reasoning_json = VALUES(reasoning_json),
                risks_json = VALUES(risks_json),
                evidence_quote = VALUES(evidence_quote),
                published_at = VALUES(published_at),
                updated_at = VALUES(updated_at),
                id = LAST_INSERT_ID(id)
            """,
            (
                creator_id,
                video_db_id,
                analysis_id,
                insight_index,
                topic_id,
                insight.subject,
                match_method,
                match_confidence,
                insight.stance,
                insight.source_type,
                insight.time_horizon,
                insight.confidence,
                insight.conclusion,
                json.dumps(insight.reasoning, ensure_ascii=False),
                json.dumps(insight.risks, ensure_ascii=False),
                insight.evidence_quote,
                published_at,
                now,
                now,
            ),
        )
        opinion_id = int(cursor.lastrowid)
        cursor.close()
        return opinion_id

    def _delete_change_for_current_opinion(self, opinion_id: int) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "DELETE FROM opinion_changes WHERE current_opinion_id = %s",
            (opinion_id,),
        )
        cursor.close()

    def _delete_stale_opinions(self, opinion_ids: list[int]) -> None:
        if not opinion_ids:
            return
        placeholders = ", ".join(["%s"] * len(opinion_ids))
        cursor = self.connection.cursor()
        cursor.execute(
            f"""
            DELETE FROM opinion_changes
            WHERE current_opinion_id IN ({placeholders})
               OR previous_opinion_id IN ({placeholders})
            """,
            tuple(opinion_ids + opinion_ids),
        )
        cursor.execute(
            f"DELETE FROM creator_topic_opinions WHERE id IN ({placeholders})",
            tuple(opinion_ids),
        )
        cursor.close()

    def _rebuild_change_history(self, creator_id: int, topic_id: int) -> None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            "DELETE FROM opinion_changes WHERE creator_id = %s AND topic_id = %s",
            (creator_id, topic_id),
        )
        cursor.execute(
            """
            SELECT o.id, o.stance, o.published_at
            FROM creator_topic_opinions AS o
            INNER JOIN videos AS v ON v.id = o.video_id
            WHERE o.creator_id = %s
              AND o.topic_id = %s
              AND v.status = 'done'
            ORDER BY o.published_at, o.id
            """,
            (creator_id, topic_id),
        )
        opinions = list(cursor.fetchall())

        previous: dict[str, Any] | None = None
        for current in opinions:
            gap_days = None
            if previous is not None:
                gap_days = (current["published_at"] - previous["published_at"]).days
            change_type = detect_opinion_change(
                None if previous is None else str(previous["stance"]),
                str(current["stance"]),
                gap_days=gap_days,
            )
            if change_type is not None:
                previous_stance = None if previous is None else str(previous["stance"])
                cursor.execute(
                    """
                    INSERT INTO opinion_changes (
                        creator_id,
                        topic_id,
                        previous_opinion_id,
                        current_opinion_id,
                        change_type,
                        previous_stance,
                        current_stance,
                        change_summary,
                        detected_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        creator_id,
                        topic_id,
                        None if previous is None else int(previous["id"]),
                        int(current["id"]),
                        change_type,
                        previous_stance,
                        str(current["stance"]),
                        build_change_summary(
                            change_type,
                            previous_stance,
                            str(current["stance"]),
                        ),
                        current["published_at"],
                    ),
                )
            previous = current
        cursor.close()

    def remove_unreferenced_pending_topics(self) -> int:
        """Delete pending topics left unused after a controlled alias remap."""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT t.id
            FROM topics AS t
            LEFT JOIN creator_topic_opinions AS o ON o.topic_id = t.id
            WHERE t.status = 'pending'
              AND o.id IS NULL
            """
        )
        topic_ids = [int(row["id"]) for row in cursor.fetchall()]
        if not topic_ids:
            cursor.close()
            return 0

        placeholders = ", ".join(["%s"] * len(topic_ids))
        cursor.execute(
            f"DELETE FROM topic_aliases WHERE topic_id IN ({placeholders})",
            tuple(topic_ids),
        )
        cursor.execute(
            f"DELETE FROM topics WHERE id IN ({placeholders}) AND status = 'pending'",
            tuple(topic_ids),
        )
        removed = int(cursor.rowcount)
        cursor.close()
        return removed

    @staticmethod
    def _resolve_published_at(context: dict[str, Any]) -> datetime:
        value = context.get("source_create_time")
        if value is not None:
            timestamp = int(value)
            if timestamp > 10_000_000_000:
                timestamp //= 1000
            return datetime.fromtimestamp(timestamp)
        created_at = context.get("created_at")
        if isinstance(created_at, datetime):
            return created_at
        return datetime.now()
