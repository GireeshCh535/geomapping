-- Initialize PostGIS extensions
-- This script runs automatically when the database is first created

-- Connect to the geo_mapping_db database
\c geo_mapping_db;

-- Create PostGIS extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE geo_mapping_db TO postgres;

-- Show installed extensions
SELECT extname, extversion FROM pg_extension WHERE extname LIKE '%postgis%';