-- Limpieza unica: marca como inactivos los registros de software_autorizado
-- cuyo software ya esta en 2+ dispositivos activos.
-- Ejecutar UNA SOLA VEZ antes de desplegar la nueva version.

UPDATE software_autorizado sa
SET sa.activo = FALSE
WHERE COALESCE(sa.activo, TRUE) = TRUE
  AND sa.software_id IS NOT NULL
  AND (
      SELECT COUNT(DISTINCT swe_chk.equipo_id)
      FROM software_equipo swe_chk
      JOIN equipos e_chk ON e_chk.id = swe_chk.equipo_id
      WHERE swe_chk.software_id = sa.software_id
        AND swe_chk.presente = TRUE
        AND e_chk.activo = TRUE
  ) >= 2;

-- Verificacion post-migracion
SELECT
    COUNT(*) AS registros_promovidos,
    'software_autorizado marcados inactivos por multidevice' AS descripcion
FROM software_autorizado
WHERE activo = FALSE
  AND software_id IS NOT NULL;
