-- Enable frontend-triggered scan/pipeline/video actions and job result polling.
ALTER TABLE processing_jobs
    MODIFY COLUMN video_id BIGINT UNSIGNED NULL,
    ADD COLUMN payload_json JSON NULL AFTER retry_count,
    ADD COLUMN result_json JSON NULL AFTER payload_json;

CREATE INDEX idx_jobs_type ON processing_jobs (job_type);
