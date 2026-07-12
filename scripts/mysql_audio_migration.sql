ALTER TABLE videos
    ADD COLUMN audio_path TEXT NULL AFTER processed_at,
    ADD COLUMN audio_size BIGINT UNSIGNED NULL AFTER audio_path,
    ADD COLUMN audio_created_at DATETIME NULL AFTER audio_size;
