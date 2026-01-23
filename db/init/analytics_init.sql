-- ./db/init/analytics-init.sql

CREATE DATABASE IF NOT EXISTS bionic_data;

USE bionic_data;

CREATE TABLE IF NOT EXISTS telemetry_analytics (
    -- Из Telemetry
    telemetry_id        UInt64,                     -- ID телеметрии (для ссылки на оригинал)
    recorded_at         DateTime64,                 -- Время записи (с миллисекундами для точности)
    value               Float64,                    -- Значение с сенсора (numeric → Float64 для аналитики)

    -- Из Sensors
    sensor_id           UInt32,                     -- ID сенсора
    sensor_type         LowCardinality(String),     -- Тип сенсора (низкая кардинальность для оптимизации)
    location            LowCardinality(String),     -- Локация сенсора
    sensor_serial_number Nullable(String),          -- Серийный номер сенсора (опционально)
    installed_at        Date,                       -- Дата установки сенсора
    is_active           UInt8,                      -- Флаг активности (0/1 для bool)

    -- Из Prostheses
    prosthesis_id       UInt32,                     -- ID протеза
    model               LowCardinality(String),     -- Модель протеза
    prosthesis_serial_number Nullable(String),      -- Серийный номер протеза
    purchase_date       Date,                       -- Дата покупки протеза

    -- Из Users
    user_id             UInt32,                     -- ID пользователя
    name                String,                     -- Имя пользователя
    email               String,                     -- Email (для фильтров, но без индексации для приватности)
    date_of_birth       Date,                       -- Дата рождения
    registration_date   Date,                       -- Дата регистрации
    age                 UInt8 MATERIALIZED toYear(recorded_at) - toYear(date_of_birth)  -- Вычисляемый возраст на момент записи

) ENGINE = MergeTree()
PARTITION BY toYYYYMM(recorded_at)  -- Партиционирование по году-месяцу для эффективного хранения
ORDER BY (recorded_at, user_id, sensor_id)  -- Ключ сортировки для быстрых запросов
PRIMARY KEY (recorded_at, user_id, sensor_id)  -- Оптимизация под типичные аналитические запросы
SETTINGS index_granularity = 8192;  -- Стандартная настройка для больших данных

CREATE INDEX IF NOT EXISTS idx_sensor_type ON telemetry_analytics (sensor_type) TYPE minmax GRANULARITY 1;
CREATE INDEX IF NOT EXISTS idx_model ON telemetry_analytics (model) TYPE minmax GRANULARITY 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS daily_averages
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, user_id, sensor_type)
POPULATE AS
SELECT
    toDate(recorded_at) AS date,
    user_id,
    sensor_type,
    avg(value) AS avg_value,
    min(value) AS min_value,
    max(value) AS max_value,
    count() AS readings_count
FROM telemetry_analytics
GROUP BY date, user_id, sensor_type;