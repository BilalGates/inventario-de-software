-- Ejecutar manualmente para reclasificar dispositivos que deben ser servidores.
-- Ajusta los nombres segun el inventario real.

-- Opcion A: marcar por departamento Servidores
UPDATE equipos e
JOIN departamentos d ON d.id = e.departamento_id
SET e.es_servidor = TRUE
WHERE e.es_servidor = FALSE
  AND (d.codigo = 'servidores' OR LOWER(d.nombre) = 'servidores');

-- Opcion B: marcar por tipo_dispositivo
UPDATE equipos
SET es_servidor = TRUE
WHERE es_servidor = FALSE
  AND LOWER(COALESCE(tipo_dispositivo, '')) IN (
      'servidor', 'server', 'nas', 'rack', 'tower server', 'blade'
  );

-- Opcion C: marcar por nombre (ejemplo)
-- UPDATE equipos SET es_servidor = TRUE WHERE nombre LIKE 'SRV-%';

-- Verificacion
SELECT es_servidor, COUNT(*) AS total FROM equipos GROUP BY es_servidor;
