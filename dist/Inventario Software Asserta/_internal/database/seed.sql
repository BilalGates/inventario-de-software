USE inventario_software;
SET NAMES utf8mb4;

INSERT INTO departamentos (codigo, nombre, prefijo_id) VALUES
('gerencia',        'Dirección',                 'GER'),
('it',              'IT',                        'IT'),
('silicon',         'Silicon',                   'SIL'),
('data_science',    'Data Science / Analytics',  'ANA'),
('administracion',  'Administración',            'ADM'),
('servidores',      'Servidores',                'SRV')
ON DUPLICATE KEY UPDATE
    nombre = VALUES(nombre),
    prefijo_id = VALUES(prefijo_id);
