ALTER TABLE analyses
    ADD COLUMN market_insights_json JSON NULL AFTER key_points_json;
