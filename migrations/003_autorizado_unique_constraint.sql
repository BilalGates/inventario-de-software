-- Evita duplicados: mismo software + departamento + equipo en software_autorizado.
-- Idempotente: solo añade el constraint si no existe.
SET @constraint_exists := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA    = DATABASE()
      AND TABLE_NAME      = 'software_autorizado'
      AND CONSTRAINT_NAME = 'uq_sa_software_dept_equipo'
);
SET @sql := IF(
    @constraint_exists = 0,
    'ALTER TABLE software_autorizado ADD CONSTRAINT uq_sa_software_dept_equipo UNIQUE (software_id, departamento_id, equipo_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
