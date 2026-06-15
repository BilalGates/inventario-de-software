"""
Tests del runner de migraciones (scripts/migrate_db.py).

No requieren MySQL: prueban la lógica pura de "qué migraciones aplicar" y la
mecánica de registrar/aplicar contra un cursor falso.
"""
import pytest

from scripts.init_database import DatabaseInitError
from scripts.migrate_db import _apply_migration, migration_files, pending_migrations


class FakeCursor:
    """Cursor falso que simula la tabla schema_version en memoria."""

    def __init__(self, fail_on: str | None = None):
        self.applied: list[str] = []
        self.fail_on = fail_on
        self._last: list[tuple] = []

    def execute(self, sql, params=None):
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("fallo simulado en migración")
        upper = sql.strip().upper()
        if upper.startswith("INSERT INTO SCHEMA_VERSION"):
            self.applied.append(params[0])
        elif "SELECT MIGRATION_NAME FROM SCHEMA_VERSION" in upper:
            self._last = [(name,) for name in self.applied]

    def fetchall(self):
        return self._last


class TestMigrationFiles:
    def test_hay_migraciones_y_estan_ordenadas(self):
        files = migration_files()
        assert files, "Debe haber al menos una migración en migrations/"
        names = [p.name for p in files]
        assert names == sorted(names)  # orden alfabético estable


class TestPendingMigrations:
    def test_todas_pendientes_si_no_hay_aplicadas(self):
        files = migration_files()
        assert pending_migrations(files, set()) == files

    def test_no_se_aplican_dos_veces(self):
        files = migration_files()
        # Primera pasada: se aplican todas.
        primera = pending_migrations(files, set())
        aplicadas = {p.name for p in primera}
        # Segunda pasada: ya no queda nada pendiente.
        segunda = pending_migrations(files, aplicadas)
        assert segunda == []

    def test_solo_aplica_las_no_registradas(self):
        files = migration_files()
        ya = {files[0].name}
        pendientes = pending_migrations(files, ya)
        assert files[0] not in pendientes
        assert pendientes == files[1:]


class TestApplyMigration:
    def test_registra_el_nombre_tras_aplicar(self, tmp_path):
        path = tmp_path / "001_demo.sql"
        path.write_text("SELECT 1;", encoding="utf-8")
        cursor = FakeCursor()
        _apply_migration(cursor, path)
        assert "001_demo.sql" in cursor.applied

    def test_falla_con_error_claro_y_no_registra(self, tmp_path):
        path = tmp_path / "002_rota.sql"
        path.write_text("SENTENCIA_ROTA;", encoding="utf-8")
        cursor = FakeCursor(fail_on="SENTENCIA_ROTA")
        with pytest.raises(DatabaseInitError) as exc:
            _apply_migration(cursor, path)
        assert "002_rota.sql" in str(exc.value)
        assert "002_rota.sql" not in cursor.applied  # no se registra si falla
