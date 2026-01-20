INSERT INTO Telemetry (sensor_id, recorded_at, value)
SELECT 
    floor(random() * 1000 + 1)::int,
    '2025-12-01 00:00:00+01'::timestamptz
    + (random() * 31)::int * interval '1 day'
    + (random() * 86400)::int * interval '1 second',
    random() * 100

FROM generate_series(1, 100000) n
;
