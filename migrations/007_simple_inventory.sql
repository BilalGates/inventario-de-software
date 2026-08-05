-- Inventario simple: importaciones mensuales por equipo y software instalado.
-- Mantiene la estructura antigua, pero el flujo nuevo usa solo estas tablas.

CREATE TABLE IF NOT EXISTS software_importaciones (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    equipo_id           INT NOT NULL,
    departamento_id     INT NOT NULL,
    periodo             CHAR(7) NOT NULL,
    fecha_importacion   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_hash            CHAR(64) NOT NULL,
    raw_text            LONGTEXT NULL,
    estado              ENUM('confirmed', 'superseded', 'rejected') NOT NULL DEFAULT 'confirmed',
    n_programas         INT NOT NULL DEFAULT 0,
    n_errores           INT NOT NULL DEFAULT 0,
    origen              VARCHAR(20) NULL,
    notas               TEXT NULL,
    CONSTRAINT fk_simple_imp_equipo FOREIGN KEY (equipo_id) REFERENCES equipos(id),
    CONSTRAINT fk_simple_imp_dept FOREIGN KEY (departamento_id) REFERENCES departamentos(id),
    INDEX idx_simple_imp_period_dept_status (periodo, departamento_id, estado),
    INDEX idx_simple_imp_equipo_period_status (equipo_id, periodo, estado),
    INDEX idx_simple_imp_hash (raw_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS software_instalado (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    importacion_id      INT NOT NULL,
    equipo_id           INT NOT NULL,
    departamento_id     INT NOT NULL,
    periodo             CHAR(7) NOT NULL,
    source_row          INT NOT NULL,
    nombre              VARCHAR(500) NOT NULL,
    nombre_norm         VARCHAR(500) NOT NULL,
    fabricante          VARCHAR(300) NULL,
    fabricante_norm     VARCHAR(300) NULL,
    fecha_instalacion   DATE NULL,
    tamano              VARCHAR(50) NULL,
    version             VARCHAR(200) NULL,
    raw_line            TEXT NULL,
    CONSTRAINT fk_simple_sw_imp FOREIGN KEY (importacion_id) REFERENCES software_importaciones(id),
    CONSTRAINT fk_simple_sw_equipo FOREIGN KEY (equipo_id) REFERENCES equipos(id),
    CONSTRAINT fk_simple_sw_dept FOREIGN KEY (departamento_id) REFERENCES departamentos(id),
    CONSTRAINT uq_simple_sw_imp_row UNIQUE (importacion_id, source_row),
    INDEX idx_simple_sw_period_dept_name (periodo, departamento_id, nombre_norm(191)),
    INDEX idx_simple_sw_equipo_period (equipo_id, periodo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
