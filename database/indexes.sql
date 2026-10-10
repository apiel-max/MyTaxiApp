-- =====================================================================
-- indexes.sql
-- Performance indexes for the NYC Urban Mobility database.
-- Applied AFTER bulk insert (no overhead during loading).
-- =====================================================================

-- trips: the most-filtered columns
CREATE INDEX IF NOT EXISTS idx_trips_pickup_datetime   ON trips (pickup_datetime);
CREATE INDEX IF NOT EXISTS idx_trips_pickup_zone       ON trips (pickup_zone_id);
CREATE INDEX IF NOT EXISTS idx_trips_dropoff_zone      ON trips (dropoff_zone_id);
CREATE INDEX IF NOT EXISTS idx_trips_pickup_hour       ON trips (pickup_hour);
CREATE INDEX IF NOT EXISTS idx_trips_pickup_dow        ON trips (pickup_dow);
CREATE INDEX IF NOT EXISTS idx_trips_payment_type      ON trips (payment_type_id);
CREATE INDEX IF NOT EXISTS idx_trips_is_airport        ON trips (is_airport_trip);
CREATE INDEX IF NOT EXISTS idx_trips_fare              ON trips (fare_amount);
CREATE INDEX IF NOT EXISTS idx_trips_distance          ON trips (trip_distance);

-- Composite: the most common dashboard query pattern
CREATE INDEX IF NOT EXISTS idx_trips_zone_hour
    ON trips (pickup_zone_id, pickup_hour, pickup_dow);

-- zone_date_hour_stats: date-range + zone/borough filters
CREATE INDEX IF NOT EXISTS idx_zdhs_date       ON zone_date_hour_stats (pickup_date);
CREATE INDEX IF NOT EXISTS idx_zdhs_zone       ON zone_date_hour_stats (pickup_zone_id);
CREATE INDEX IF NOT EXISTS idx_zdhs_dow        ON zone_date_hour_stats (pickup_dow);
CREATE INDEX IF NOT EXISTS idx_zdhs_hour       ON zone_date_hour_stats (pickup_hour);

-- route_date_stats: date-range + zone filters
CREATE INDEX IF NOT EXISTS idx_rds_date        ON route_date_stats (pickup_date);
CREATE INDEX IF NOT EXISTS idx_rds_pickup_zone ON route_date_stats (pickup_zone_id);
CREATE INDEX IF NOT EXISTS idx_rds_dropoff_zone ON route_date_stats (dropoff_zone_id);
CREATE INDEX IF NOT EXISTS idx_rds_dow         ON route_date_stats (pickup_dow);

-- excluded_records: transparency log lookups
CREATE INDEX IF NOT EXISTS idx_excl_reason     ON excluded_records (reason_code);
