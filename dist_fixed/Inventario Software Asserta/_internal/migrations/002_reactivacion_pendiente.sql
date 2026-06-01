USE inventario_software;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS software_reactivacion_pendiente (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  software_id     INT NOT NULL,
  equipo_id       INT NOT NULL,
  fecha_deteccion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revisado        BOOLEAN NOT NULL DEFAULT FALSE,
  accion          ENUM('reactivar', 'ignorar') NULL,
  CONSTRAINT fk_srp_sw FOREIGN KEY (software_id) REFERENCES software(id),
  CONSTRAINT fk_srp_eq FOREIGN KEY (equipo_id) REFERENCES equipos(id),
  INDEX idx_srp_revisado_fecha (revisado, fecha_deteccion),
  INDEX idx_srp_sw_eq_revisado (software_id, equipo_id, revisado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
