INSERT INTO users (user_id, name, date_of_birth, registration_date)
SELECT 
    n,
    (ARRAY['James','Michael','William','David','John','Robert','Thomas','Charles',
               'Christopher','Daniel','Matthew','Andrew','Joseph','Emma','Olivia',
               'Ava','Sophia','Isabella','Charlotte','Amelia','Mia','Harper','Evelyn',
               'Abigail','Ella','Elizabeth','Sofia','Avery'])[1 + floor(random()*28)::int] || ' ' ||
    (ARRAY['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis',
               'Rodriguez','Martinez','Hernandez','Lopez','Gonzalez','Wilson','Anderson',
               'Thomas','Taylor','Moore','Jackson','Martin','Lee','Perez','Thompson',
               'White','Harris','Sanchez','Clark','Ramirez'])[1 + floor(random()*28)::int],
                   
    timestamp '1936-01-01' + 
        (random() * ('2008-12-31'::date - '1936-01-01'::date))::int * interval '1 day',
    timestamp '2020-01-01' + 
        (random() * ('2025-12-31'::date - '2020-01-01'::date))::int * interval '1 day'        
FROM generate_series(1, 100) n
;

UPDATE users
SET email = lower(replace(name, ' ', '.')) || '.' || user_id::text ||
    '@' || 
    (ARRAY[
        'gmail.com',
        'yahoo.com',
        'hotmail.com',
        'outlook.com',
        'mail.ru',
        'yandex.ru',
        'icloud.com',
        'proton.me',
        'zoho.com',
        'aol.com'
    ])[1 + floor(random() * 10)::int]
;

INSERT INTO prostheses (prosthesis_id, user_id, model, serial_number, purchase_date)
SELECT 
    u.user_id,
    u.user_id,
    'Model' || floor(random() * 7),
    'SN-' ||  upper(substring(md5(random()::text || clock_timestamp()::text), 1, 13)),
    u.registration_date + (random() * 365)::int * interval '1 day'        
FROM users u
;

insert into sensors (prosthesis_id, sensor_type, location, installed_at)
SELECT
    p.prosthesis_id,
    (ARRAY[
    'EMG_surface',
    'EMG_intramuscular',
    'force_grip_finger',
    'pressure_tactile_array',
    'IMU_6axis',
    'angle_encoder_joint',
    'load_cell_axial',
    'temperature_skin',
    'humidity_socket',
    'proximity_infrared',
    'vibration_tactile',
    'pressure_socket_distributed',
    'gyroscope_standalone',
    'accelerometer_standalone',
    'force_shear',
    'hall_effect_position',
    'battery_level_voltage',
    'temperature_battery',
    'strain_gauge_structural',
    'vibrotactile_feedback'])[1 + floor(random() * 20)::int],
    (ARRAY[
    'forearm socket',
    'upper arm socket',
    'inner socket wall',
    'palm',
    'thumb tip',
    'index fingertip',
    'finger pads',
    'wrist unit',
    'knee joint',
    'shin socket',
    'foot sole',
    'heel',
    'toe area',
    'battery compartment',
    'elbow joint',
    'residual limb skin',
    'shoulder harness area',
    'tibial tubercle area',
    'gastrocnemius area',
    'fibular head area'])[1 + floor(random() * 20)::int],
    p.purchase_date
from prostheses AS p
CROSS JOIN generate_series(1, 10) AS gs(n);

Select * from Sensors