-- Evita duplicados: mismo software + departamento + equipo en software_autorizado.
-- Idempotente: deduplica primero y luego añade el constraint si no existe.

-- Paso 1: eliminar filas duplicadas, conservando la de id más bajo.
DELETE sa FROM software_autorizado sa
INNER JOIN software_autorizado sa2
    ON  sa.software_id      = sa2.software_id
    AND sa.departamento_id  = sa2.departamento_id
    AND sa.equipo_id        = sa2.equipo_id
    AND sa.id               > sa2.id;

-- Paso 2: añadir la constraint solo si no existe aún.
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
