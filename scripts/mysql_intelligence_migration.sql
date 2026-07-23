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
