CREATE TABLE Users (
    user_id       SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(100) UNIQUE,
    date_of_birth DATE,
    registration_date DATE
);


CREATE TABLE Prostheses (
    prosthesis_id   SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    model           VARCHAR(50) NOT NULL,
    serial_number   VARCHAR(50) UNIQUE,
    purchase_date   DATE,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);


CREATE TABLE Sensors (
    sensor_id       SERIAL PRIMARY KEY,
    prosthesis_id   INTEGER NOT NULL,
    sensor_type     VARCHAR(60) NOT NULL,      -- "battery_level", "knee_angle", "pressure_sole", "gyroscope", "temperature_skin" и т.д.
    location        VARCHAR(80),               -- "wrist", "shin", "foot_sole", "knee_joint", "socket", "battery_compartment"...
    serial_number   VARCHAR(50),               -- опционально, если у датчика есть свой серийный номер
    installed_at    DATE,                      -- когда датчик был установлен/заменён
    is_active       BOOLEAN DEFAULT true,
    FOREIGN KEY (prosthesis_id) REFERENCES Prostheses(prosthesis_id) ON DELETE CASCADE
);
