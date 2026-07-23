CREATE TABLE IF NOT EXISTS creators (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    platform VARCHAR(32) NOT NULL,
    sec_uid VARCHAR(255) NOT NULL,
    platform_uid VARCHAR(128) NULL,
    provider_author_id VARCHAR(255) NULL,
    creator_name VARCHAR(255) NULL,
    source_dir TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_creators_platform_sec_uid (platform, sec_uid),
    KEY idx_creators_platform_uid (platform, platform_uid),
    KEY idx_creators_provider_author (platform, provider_author_id)
);

CREATE TABLE IF NOT EXISTS videos (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    platform VARCHAR(32) NOT NULL,
    creator_sec_uid VARCHAR(255) NOT NULL,
    provider_author_id VARCHAR(255) NULL,
    author_uid VARCHAR(128) NULL,
    video_id VARCHAR(128) NOT NULL,
    creator_id BIGINT UNSIGNED NOT NULL,
    file_path TEXT NOT NULL,
    metadata_path TEXT NOT NULL,
    file_name VARCHAR(512) NOT NULL,
    file_size BIGINT UNSIGNED NOT NULL,
    file_mtime DOUBLE NOT NULL,
    description TEXT NULL,
    source_create_time BIGINT NULL,
    downloaded_at VARCHAR(64) NULL,
    statistics_json JSON NULL,
    metadata_json JSON NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    processed_at DATETIME NULL,
    audio_path TEXT NULL,
    audio_size BIGINT UNSIGNED NULL,
    audio_created_at DATETIME NULL,
    error_message TEXT NULL,
    UNIQUE KEY uq_videos_platform_creator_video (platform, creator_sec_uid, video_id),
    KEY idx_videos_creator_id (creator_id),
    KEY idx_videos_provider_author (platform, provider_author_id),
    KEY idx_videos_status (status)
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    video_id BIGINT UNSIGNED NULL,
    job_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    payload_json JSON NULL,
    result_json JSON NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    error_message TEXT NULL,
    KEY idx_jobs_video_id (video_id),
    KEY idx_jobs_status (status),
    KEY idx_jobs_type (job_type)
);

CREATE TABLE IF NOT EXISTS transcripts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    video_id BIGINT UNSIGNED NOT NULL,
    transcript_text LONGTEXT NOT NULL,
    segments_json JSON NULL,
    language VARCHAR(32) NULL,
    model_name VARCHAR(128) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_transcripts_video_id (video_id)
);

CREATE TABLE IF NOT EXISTS analyses (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    video_id BIGINT UNSIGNED NOT NULL,
    summary TEXT NULL,
    tags_json JSON NULL,
    key_points_json JSON NULL,
    market_insights_json JSON NULL,
    model_name VARCHAR(128) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_analyses_video_id (video_id)
);

CREATE TABLE IF NOT EXISTS topics (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    canonical_name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    topic_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_topics_type_normalized (topic_type, normalized_name),
    KEY idx_topics_status (status)
);

CREATE TABLE IF NOT EXISTS topic_aliases (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    topic_id BIGINT UNSIGNED NOT NULL,
    alias VARCHAR(255) NOT NULL,
    normalized_alias VARCHAR(255) NOT NULL,
    source VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uq_topic_aliases_topic_normalized (topic_id, normalized_alias),
    KEY idx_topic_aliases_normalized (normalized_alias),
    KEY idx_topic_aliases_topic (topic_id)
);

CREATE TABLE IF NOT EXISTS creator_topic_opinions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    creator_id BIGINT UNSIGNED NOT NULL,
    video_id BIGINT UNSIGNED NOT NULL,
    analysis_id BIGINT UNSIGNED NOT NULL,
    insight_index INT UNSIGNED NOT NULL,
    topic_id BIGINT UNSIGNED NOT NULL,
    raw_subject VARCHAR(255) NOT NULL,
    match_method VARCHAR(32) NOT NULL,
    match_confidence VARCHAR(16) NOT NULL,
    stance VARCHAR(32) NOT NULL,
    source_type VARCHAR(16) NOT NULL,
    time_horizon VARCHAR(32) NOT NULL,
    confidence VARCHAR(16) NOT NULL,
    conclusion TEXT NOT NULL,
    reasoning_json JSON NULL,
    risks_json JSON NULL,
    evidence_quote TEXT NULL,
    published_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_creator_topic_opinions_analysis_index (analysis_id, insight_index),
    KEY idx_creator_topic_opinions_creator_topic_time (creator_id, topic_id, published_at),
    KEY idx_creator_topic_opinions_topic_time (topic_id, published_at),
    KEY idx_creator_topic_opinions_video (video_id)
);

CREATE TABLE IF NOT EXISTS opinion_changes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    creator_id BIGINT UNSIGNED NOT NULL,
    topic_id BIGINT UNSIGNED NOT NULL,
    previous_opinion_id BIGINT UNSIGNED NULL,
    current_opinion_id BIGINT UNSIGNED NOT NULL,
    change_type VARCHAR(32) NOT NULL,
    previous_stance VARCHAR(32) NULL,
    current_stance VARCHAR(32) NOT NULL,
    change_summary TEXT NOT NULL,
    detected_at DATETIME NOT NULL,
    UNIQUE KEY uq_opinion_changes_current (current_opinion_id),
    KEY idx_opinion_changes_creator_topic_time (creator_id, topic_id, detected_at),
    KEY idx_opinion_changes_topic_time (topic_id, detected_at)
);

CREATE TABLE IF NOT EXISTS topic_merge_history (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_topic_id BIGINT UNSIGNED NOT NULL,
    target_topic_id BIGINT UNSIGNED NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    target_name VARCHAR(255) NOT NULL,
    source_aliases_json JSON NULL,
    moved_opinion_count INT UNSIGNED NOT NULL DEFAULT 0,
    merged_at DATETIME NOT NULL,
    KEY idx_topic_merge_history_source (source_topic_id),
    KEY idx_topic_merge_history_target_time (target_topic_id, merged_at)
);

CREATE TABLE IF NOT EXISTS reference_assets (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    asset_type VARCHAR(32) NOT NULL,
    code VARCHAR(64) NOT NULL,
    normalized_code VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    market VARCHAR(32) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_reference_assets_identity (asset_type, market, normalized_code),
    KEY idx_reference_assets_name (name),
    KEY idx_reference_assets_status (status)
);

CREATE TABLE IF NOT EXISTS topic_asset_mappings (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    topic_id BIGINT UNSIGNED NOT NULL,
    asset_id BIGINT UNSIGNED NOT NULL,
    relation_type VARCHAR(32) NOT NULL DEFAULT 'related',
    note VARCHAR(500) NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'manual',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_topic_asset_mappings_topic_asset (topic_id, asset_id),
    KEY idx_topic_asset_mappings_topic (topic_id),
    KEY idx_topic_asset_mappings_asset (asset_id)
);
