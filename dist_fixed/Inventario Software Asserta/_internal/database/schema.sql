CREATE DATABASE IF NOT EXISTS inventario_software
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE inventario_software;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS departamentos (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    codigo          VARCHAR(30) UNIQUE NOT NULL,
    nombre          VARCHAR(100) NOT NULL,
    prefijo_id      VARCHAR(5) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS equipos (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    departamento_id     INT NOT NULL,
    nombre              VARCHAR(150) NOT NULL,
    nombre_norm         VARCHAR(150) NOT NULL,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    es_servidor         BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_alta          DATE NOT NULL DEFAULT (CURRENT_DATE),
    fecha_baja          DATE NULL,
    notas               TEXT NULL,
    tipo_dispositivo    VARCHAR(50) NULL,
    marca_modelo        VARCHAR(100) NULL,
    num_serie           VARCHAR(100) NULL,
    mac_address         VARCHAR(20) NULL,
    sistema_operativo   VARCHAR(100) NULL,
    procesador          VARCHAR(200) NULL,
    ram                 VARCHAR(20) NULL,
    almacenamiento      VARCHAR(50) NULL,
    responsable         VARCHAR(100) NULL,
    ubicacion           VARCHAR(100) NULL,
    coste               DECIMAL(10,2) NULL,
    fecha_adquisicion   DATE NULL,
    CONSTRAINT fk_equipo_dept FOREIGN KEY (departamento_id) REFERENCES departamentos(id),
    CONSTRAINT uq_equipo_dept UNIQUE (departamento_id, nombre_norm),
    INDEX idx_equipos_departamento_activo (departamento_id, activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS software (
    id                          INT PRIMARY KEY AUTO_INCREMENT,
    departamento_id             INT NOT NULL,
    codigo                      VARCHAR(20) NULL,
    nombre                      VARCHAR(500) NOT NULL,
    nombre_norm                 VARCHAR(500) NOT NULL,
    fabricante                  VARCHAR(300) NULL,
    version_referencia          VARCHAR(200) NULL,
    clasificacion_informacion   VARCHAR(80) NULL DEFAULT 'Media',
    en_guia_105                 BOOLEAN NULL,
    observaciones_elena         TEXT NULL,
    observaciones_toni          TEXT NULL,
    fecha_ultima_actualizacion  DATE NULL,
    activo                      BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_alta                  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sw_dept FOREIGN KEY (departamento_id) REFERENCES departamentos(id),
    CONSTRAINT uq_sw_dept UNIQUE (departamento_id, nombre_norm),
    INDEX idx_software_departamento_activo (departamento_id, activo),
    INDEX idx_software_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS software_equipo (
    id                      INT PRIMARY KEY AUTO_INCREMENT,
    software_id             INT NOT NULL,
    equipo_id               INT NOT NULL,
    version_detectada       VARCHAR(200) NULL,
    fecha_instalacion       DATE NULL,
    tamano                  VARCHAR(50) NULL,
    fecha_ultima_deteccion  DATE NOT NULL,
    presente                BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_swe_sw FOREIGN KEY (software_id) REFERENCES software(id),
    CONSTRAINT fk_swe_eq FOREIGN KEY (equipo_id) REFERENCES equipos(id),
    CONSTRAINT uq_sw_equipo UNIQUE (software_id, equipo_id),
    INDEX idx_swe_equipo_presente (equipo_id, presente),
    INDEX idx_swe_software_presente (software_id, presente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS software_autorizado (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    software_id          INT NULL,
    departamento_id     INT NULL,
    nombre              VARCHAR(500) NOT NULL,
    fabricante          VARCHAR(300) NULL,
    tipo                VARCHAR(100) NULL,
    version             VARCHAR(200) NULL,
    equipo_id           INT NULL,
    usuario_texto       VARCHAR(150) NULL,
    observaciones       TEXT NULL,
    motivo              TEXT NULL,
    fecha_autorizacion  DATETIME NULL,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_alta          DATE NOT NULL DEFAULT (CURRENT_DATE),
    CONSTRAINT fk_sa_sw FOREIGN KEY (software_id) REFERENCES software(id),
    CONSTRAINT fk_sa_dept FOREIGN KEY (departamento_id) REFERENCES departamentos(id),
    CONSTRAINT fk_sa_eq FOREIGN KEY (equipo_id) REFERENCES equipos(id),
    INDEX idx_sa_departamento (departamento_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS software_reactivacion_pendiente (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    software_id     INT NOT NULL,
    equipo_id       INT NOT NULL,
    fecha_deteccion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revisado        BOOLEAN NOT NULL DEFAULT FALSE,
    accion          ENUM('reactivar', 'ignorar') NULL,
    CONSTRAINT fk_srp_sw FOREIGN KEY (software_id) REFERENCES software(id),
    CONSTRAINT fk_srp_eq FOREIGN KEY (equipo_id) REFERENCES equipos(id),
    INDEX idx_srp_revisado_fecha (revisado, fecha_deteccion),
    INDEX idx_srp_sw_eq_revisado (software_id, equipo_id, revisado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS importaciones (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    equipo_id           INT NOT NULL,
    fecha_importacion   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metodo              ENUM('paste', 'file') NOT NULL,
    n_total             INT NULL,
    n_nuevos            INT NOT NULL DEFAULT 0,
    n_actualizados      INT NOT NULL DEFAULT 0,
    n_eliminados        INT NOT NULL DEFAULT 0,
    n_cambios_version   INT NOT NULL DEFAULT 0,
    confirmada          BOOLEAN NOT NULL DEFAULT FALSE,
    notas               TEXT NULL,
    CONSTRAINT fk_imp_eq FOREIGN KEY (equipo_id) REFERENCES equipos(id),
    INDEX idx_importaciones_equipo_fecha (equipo_id, fecha_importacion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
