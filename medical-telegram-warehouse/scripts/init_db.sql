-- Initialisation script — runs automatically when the PostgreSQL container first starts.
-- Creates the schemas needed by the pipeline.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- Grant all privileges to the warehouse user (already the owner via POSTGRES_USER)
GRANT ALL ON SCHEMA raw     TO CURRENT_USER;
GRANT ALL ON SCHEMA staging TO CURRENT_USER;
GRANT ALL ON SCHEMA marts   TO CURRENT_USER;
