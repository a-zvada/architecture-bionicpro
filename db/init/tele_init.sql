CREATE TABLE Telemetry (
    telemetry_id    BIGSERIAL PRIMARY KEY,
    sensor_id       INTEGER NOT NULL,
    recorded_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    value           numeric    
);

select * from telemetry