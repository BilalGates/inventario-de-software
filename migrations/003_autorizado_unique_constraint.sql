-- Evita que se autorice el mismo software para el mismo equipo/departamento mas de una vez
ALTER TABLE software_autorizado
    ADD CONSTRAINT uq_sa_software_dept_equipo
    UNIQUE (software_id, departamento_id, equipo_id);
