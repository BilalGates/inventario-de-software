"""Migración desde las tablas legacy: sin pérdida de datos e idempotente."""
from sqlalchemy import create_engine, func, select, text

from app.legacy_import import LegacyImporter
from app.models import (
    Department,
    Device,
    DeviceAssignment,
    InventorySnapshot,
    SoftwareInstallation,
    SoftwarePolicy,
    SoftwareProduct,
)

LEGACY_DDL = """
CREATE TABLE departamentos (id INTEGER PRIMARY KEY, codigo TEXT, nombre TEXT, prefijo_id TEXT);
CREATE TABLE equipos (id INTEGER PRIMARY KEY, departamento_id INT, nombre TEXT, nombre_norm TEXT, activo BOOLEAN,
  es_servidor BOOLEAN, fecha_alta DATE, fecha_baja DATE, notas TEXT, tipo_dispositivo TEXT, marca_modelo TEXT,
  num_serie TEXT, mac_address TEXT, sistema_operativo TEXT, procesador TEXT, ram TEXT, almacenamiento TEXT,
  responsable TEXT, ubicacion TEXT, coste DECIMAL, fecha_adquisicion DATE);
CREATE TABLE software (id INTEGER PRIMARY KEY, departamento_id INT, nombre TEXT, version_referencia TEXT,
  clasificacion_informacion TEXT, observaciones_elena TEXT, observaciones_toni TEXT, activo BOOLEAN);
CREATE TABLE software_autorizado (id INTEGER PRIMARY KEY, software_id INT, departamento_id INT, nombre TEXT,
  fabricante TEXT, tipo TEXT, version TEXT, equipo_id INT, usuario_texto TEXT, observaciones TEXT, motivo TEXT,
  fecha_autorizacion DATETIME, activo BOOLEAN, fecha_alta DATE);
CREATE TABLE software_importaciones (id INTEGER PRIMARY KEY, equipo_id INT, departamento_id INT, periodo TEXT,
  fecha_importacion DATETIME, raw_hash TEXT, raw_text TEXT, estado TEXT, n_programas INT, n_errores INT,
  origen TEXT, notas TEXT);
CREATE TABLE software_instalado (id INTEGER PRIMARY KEY, importacion_id INT, equipo_id INT, departamento_id INT,
  periodo TEXT, source_row INT, nombre TEXT, nombre_norm TEXT, fabricante TEXT, fabricante_norm TEXT,
  fecha_instalacion DATE, tamano TEXT, version TEXT, raw_line TEXT);
"""

LEGACY_DATA = """
INSERT INTO departamentos VALUES (1,'it','IT','IT'),(2,'servidores','Servidores','SRV'),(3,'gerencia','Gerencia','GER');
INSERT INTO equipos (id,departamento_id,nombre,activo,es_servidor,fecha_alta,tipo_dispositivo,marca_modelo,num_serie,
  ram,almacenamiento,responsable,ubicacion,coste) VALUES
  (1,1,'PC-IT-01',1,0,'2025-01-15','Portátil','Dell / Latitude 5440','SN0001','16 GB','512 GB SSD','Persona A','Oficina',900),
  (2,2,'SRV-01',1,1,'2024-05-01','Servidor','HPE / ProLiant','SN0002','64 GB','2 TB',NULL,'CPD',NULL),
  (3,3,'PC-GER-OLD',0,0,'2020-01-01',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO software_importaciones VALUES
  (10,1,1,'2026-08','2026-08-03 10:00:00','h','raw','confirmed',2,0,'tabbed',NULL),
  (11,1,1,'2026-09','2026-09-02 10:00:00','h','raw','confirmed',2,0,'tabbed',NULL),
  (12,1,1,'2026-09','2026-09-01 09:00:00','h','raw','superseded',1,0,'tabbed',NULL);
INSERT INTO software_instalado (importacion_id,equipo_id,departamento_id,periodo,source_row,nombre,nombre_norm,fabricante,version) VALUES
  (10,1,1,'2026-08',1,'Google Chrome','GOOGLE CHROME','Google LLC','128.0'),
  (10,1,1,'2026-08',2,'AnyDesk','ANYDESK','AnyDesk Software GmbH','9.0.10'),
  (11,1,1,'2026-09',1,'Google Chrome','GOOGLE CHROME','Google LLC','129.0'),
  (11,1,1,'2026-09',2,'7-Zip 23.01 (x64)','7-ZIP','Igor Pavlov','23.01'),
  (12,1,1,'2026-09',1,'Malware','MALWARE','X','1');
INSERT INTO software_autorizado (id,departamento_id,nombre,fabricante,equipo_id,motivo,activo) VALUES
  (1,NULL,'7-Zip 23.01 (x64)','Igor Pavlov',1,'Compresión de ficheros',1),
  (2,1,'Wireshark','Wireshark Foundation',NULL,'Diagnóstico de red',1),
  (3,NULL,'Viejo','X',NULL,'baja',0);
INSERT INTO software (departamento_id,nombre,version_referencia,clasificacion_informacion,observaciones_elena,activo) VALUES
  (1,'Google Chrome','129.0','Media','Navegador corporativo',1);
"""


def legacy_conn():
    eng = create_engine("sqlite://", future=True)
    conn = eng.connect()
    for stmt in (LEGACY_DDL + LEGACY_DATA).split(";"):
        if stmt.strip():
            conn.execute(text(stmt))
    conn.commit()
    return conn


def count(db, model, *where):
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar()


def test_legacy_import_maps_everything_and_is_idempotent(db):
    legacy = legacy_conn()
    report = LegacyImporter(legacy, db).run()
    db.commit()
    c = report["counts"]
    # Sin pérdida: todos los equipos legacy existen (activos y retirados)
    assert c["legacy.equipos"] == c["new.devices"] == 3
    assert count(db, Device) == 3
    assert set(db.execute(select(Department.code)).scalars()) == {"it", "gerencia"}  # 'servidores' no es depto
    srv = db.execute(select(Device).where(Device.hostname == "SRV-01")).scalar_one()
    assert srv.device_type.code == "server" and srv.department_id is None
    pc = db.execute(select(Device).where(Device.hostname == "PC-IT-01")).scalar_one()
    assert pc.ram_bytes == 16 * 1024**3 and pc.manufacturer == "Dell" and pc.model == "Latitude 5440"
    assert "Persona A" in pc.notes
    old = db.execute(select(Device).where(Device.hostname == "PC-GER-OLD")).scalar_one()
    assert old.status == "retired"
    assert count(db, DeviceAssignment) == 3
    # Software: solo el último inventario confirmado queda como instalado; el 'superseded' se ignora
    names = set(db.execute(select(SoftwareProduct.name).join(SoftwareInstallation,
                SoftwareInstallation.product_id == SoftwareProduct.id)).scalars())
    assert names == {"Google Chrome", "7-Zip 23.01 (x64)"}
    assert count(db, SoftwareProduct, SoftwareProduct.name == "Malware") == 0
    # Histórico mensual comparable
    snaps = db.execute(select(InventorySnapshot).order_by(InventorySnapshot.period)).scalars().all()
    assert [(s.period, s.status, s.totals["installations"]) for s in snaps] == [("2026-08", "legacy", 2),
                                                                               ("2026-09", "legacy", 2)]
    # Autorizaciones activas -> políticas; la inactiva no
    assert count(db, SoftwarePolicy) == 2
    assert count(db, SoftwarePolicy, SoftwarePolicy.scope == "device") == 1
    chrome = db.execute(select(SoftwareProduct).where(SoftwareProduct.name == "Google Chrome")).scalar_one()
    assert chrome.ens_classification == "Media" and chrome.authorization_status == "unclassified"

    before = {m.__name__: count(db, m) for m in (Device, Department, SoftwareInstallation, SoftwarePolicy,
                                                  InventorySnapshot, SoftwareProduct)}
    report2 = LegacyImporter(legacy, db).run()
    db.commit()
    after = {m.__name__: count(db, m) for m in (Device, Department, SoftwareInstallation, SoftwarePolicy,
                                                 InventorySnapshot, SoftwareProduct)}
    assert before == after
    assert report2["counts"]["skip.devices_already_migrated"] == 3


def test_legacy_tables_are_not_modified(db):
    legacy = legacy_conn()
    snapshot = {t: legacy.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                for t in ("departamentos", "equipos", "software_instalado", "software_autorizado")}
    LegacyImporter(legacy, db).run()
    db.rollback()
    assert snapshot == {t: legacy.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in snapshot}
