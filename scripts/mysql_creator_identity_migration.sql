-- Migrate an existing EchoLens database from provider author_id identity
-- to the stable Douyin author.sec_uid identity.
--
-- Existing rows keep sec_uid / creator_sec_uid NULL until the next
-- `echolens scan --enqueue`. The ingest repository backfills those rows from
-- each sidecar metadata file without re-enqueueing already known videos.

ALTER TABLE creators
    CHANGE COLUMN author_id provider_author_id VARCHAR(255) NULL,
    ADD COLUMN sec_uid VARCHAR(255) NULL AFTER platform,
    ADD COLUMN platform_uid VARCHAR(128) NULL AFTER sec_uid,
    DROP INDEX uq_creators_platform_author,
    ADD UNIQUE KEY uq_creators_platform_sec_uid (platform, sec_uid),
    ADD KEY idx_creators_platform_uid (platform, platform_uid),
    ADD KEY idx_creators_provider_author (platform, provider_author_id);

ALTER TABLE videos
    CHANGE COLUMN author_id provider_author_id VARCHAR(255) NULL,
    ADD COLUMN creator_sec_uid VARCHAR(255) NULL AFTER platform,
    ADD COLUMN author_uid VARCHAR(128) NULL AFTER provider_author_id,
    ADD COLUMN statistics_json JSON NULL AFTER downloaded_at,
    ADD COLUMN metadata_json JSON NULL AFTER statistics_json,
    DROP INDEX uq_videos_platform_author_video,
    ADD UNIQUE KEY uq_videos_platform_creator_video (platform, creator_sec_uid, video_id),
    ADD KEY idx_videos_provider_author (platform, provider_author_id);
