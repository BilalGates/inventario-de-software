USE inventario_software;
SET NAMES utf8mb4;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'tipo_dispositivo'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN tipo_dispositivo VARCHAR(50) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'marca_modelo'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN marca_modelo VARCHAR(100) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'num_serie'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN num_serie VARCHAR(100) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'mac_address'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN mac_address VARCHAR(20) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'sistema_operativo'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN sistema_operativo VARCHAR(100) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'procesador'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN procesador VARCHAR(200) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'ram'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN ram VARCHAR(20) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'almacenamiento'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN almacenamiento VARCHAR(50) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'responsable'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN responsable VARCHAR(100) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'ubicacion'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN ubicacion VARCHAR(100) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'coste'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN coste DECIMAL(10,2) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'fecha_adquisicion'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE equipos ADD COLUMN fecha_adquisicion DATE NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'software_autorizado' AND COLUMN_NAME = 'software_id'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE software_autorizado ADD COLUMN software_id INT NULL AFTER id', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'software_autorizado' AND COLUMN_NAME = 'motivo'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE software_autorizado ADD COLUMN motivo TEXT NULL AFTER observaciones', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'software_autorizado' AND COLUMN_NAME = 'fecha_autorizacion'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE software_autorizado ADD COLUMN fecha_autorizacion DATETIME NULL AFTER motivo', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'software_autorizado' AND COLUMN_NAME = 'activo'
);
SET @sql := IF(@column_exists = 0, 'ALTER TABLE software_autorizado ADD COLUMN activo BOOLEAN NOT NULL DEFAULT TRUE AFTER fecha_autorizacion', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'software_autorizado'
    AND CONSTRAINT_NAME = 'fk_sa_sw'
);
SET @sql := IF(
  @fk_exists = 0,
  'ALTER TABLE software_autorizado ADD CONSTRAINT fk_sa_sw FOREIGN KEY (software_id) REFERENCES software(id)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'software_autorizado'
    AND INDEX_NAME = 'idx_sa_software_activo'
);
SET @sql := IF(
  @idx_exists = 0,
  'CREATE INDEX idx_sa_software_activo ON software_autorizado (software_id, activo)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
