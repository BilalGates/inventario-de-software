-- Índice para acelerar GROUP BY y filtros por nombre_norm en software.
-- Usa PREPARE/EXECUTE para crear el índice solo si no existe (MySQL no soporta ADD INDEX IF NOT EXISTS).
SET @idx_exists := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'software'
      AND INDEX_NAME   = 'idx_software_nombre_norm'
);
SET @sql := IF(
    @idx_exists = 0,
    'ALTER TABLE software ADD INDEX idx_software_nombre_norm (nombre_norm(191))',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
