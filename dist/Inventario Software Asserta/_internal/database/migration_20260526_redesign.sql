USE inventario_software;

DELIMITER //

CREATE PROCEDURE migrate_20260526_redesign()
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'software'
          AND COLUMN_NAME = 'fecha_ultima_actualizacion'
    ) THEN
        ALTER TABLE software
            ADD COLUMN fecha_ultima_actualizacion DATE NULL AFTER observaciones_toni;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'software'
          AND COLUMN_NAME = 'fecha_ultima_revision'
    ) THEN
        UPDATE software s
        LEFT JOIN (
            SELECT software_id, MAX(fecha_ultima_deteccion) AS ultima_deteccion
            FROM software_equipo
            WHERE presente = TRUE
            GROUP BY software_id
        ) swe ON swe.software_id = s.id
        SET s.fecha_ultima_actualizacion = COALESCE(swe.ultima_deteccion, s.fecha_ultima_revision, s.fecha_ultima_actualizacion)
        WHERE s.fecha_ultima_actualizacion IS NULL;
    ELSE
        UPDATE software s
        LEFT JOIN (
            SELECT software_id, MAX(fecha_ultima_deteccion) AS ultima_deteccion
            FROM software_equipo
            WHERE presente = TRUE
            GROUP BY software_id
        ) swe ON swe.software_id = s.id
        SET s.fecha_ultima_actualizacion = COALESCE(s.fecha_ultima_actualizacion, swe.ultima_deteccion)
        WHERE s.fecha_ultima_actualizacion IS NULL;
    END IF;

    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'software' AND COLUMN_NAME = 'tipo'
    ) THEN
        ALTER TABLE software DROP COLUMN tipo;
    END IF;

    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'software' AND COLUMN_NAME = 'expuesto_internet'
    ) THEN
        ALTER TABLE software DROP COLUMN expuesto_internet;
    END IF;

    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'software' AND COLUMN_NAME = 'soporte_activo'
    ) THEN
        ALTER TABLE software DROP COLUMN soporte_activo;
    END IF;

    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'software' AND COLUMN_NAME = 'permitido'
    ) THEN
        ALTER TABLE software DROP COLUMN permitido;
    END IF;

    IF EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'software' AND COLUMN_NAME = 'fecha_ultima_revision'
    ) THEN
        ALTER TABLE software DROP COLUMN fecha_ultima_revision;
    END IF;
END//

DELIMITER ;

CALL migrate_20260526_redesign();
DROP PROCEDURE migrate_20260526_redesign;
