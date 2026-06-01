-- Indice para acelerar GROUP BY y filtros por nombre_norm en software
ALTER TABLE software
    ADD INDEX IF NOT EXISTS idx_software_nombre_norm (nombre_norm(191));
