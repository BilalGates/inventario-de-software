USE inventario_software;
SET NAMES utf8mb4;

SET @column_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipos' AND COLUMN_NAME = 'es_servidor'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE equipos ADD COLUMN es_servidor BOOLEAN NOT NULL DEFAULT FALSE AFTER activo',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'equipos'
    AND INDEX_NAME = 'idx_equipos_servidor_activo'
);
SET @sql := IF(
  @idx_exists = 0,
  'CREATE INDEX idx_equipos_servidor_activo ON equipos (es_servidor, activo)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
