CREATE TABLE Telemetry (
    telemetry_id    BIGSERIAL PRIMARY KEY,
    sensor_id       INTEGER NOT NULL,
    recorded_at     TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    value           numeric    
);

select * from telemetry