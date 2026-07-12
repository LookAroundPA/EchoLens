CREATE TABLE IF NOT EXISTS creators (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    platform VARCHAR(32) NOT NULL,
    author_id VARCHAR(128) NOT NULL,
    creator_name VARCHAR(255) NULL,
    source_dir TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_creators_platform_author (platform, author_id)
);

CREATE TABLE IF NOT EXISTS videos (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    platform VARCHAR(32) NOT NULL,
    author_id VARCHAR(128) NOT NULL,
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
    status VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    processed_at DATETIME NULL,
    audio_path TEXT NULL,
    audio_size BIGINT UNSIGNED NULL,
    audio_created_at DATETIME NULL,
    error_message TEXT NULL,
    UNIQUE KEY uq_videos_platform_author_video (platform, author_id, video_id),
    KEY idx_videos_creator_id (creator_id),
    KEY idx_videos_status (status)
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    video_id BIGINT UNSIGNED NOT NULL,
    job_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    error_message TEXT NULL,
    KEY idx_jobs_video_id (video_id),
    KEY idx_jobs_status (status)
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
    model_name VARCHAR(128) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_analyses_video_id (video_id)
);
