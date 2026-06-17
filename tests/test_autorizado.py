"""Tests de software autorizado (modules/autorizado.py)."""
import modules.autorizado as autorizado
from modules.autorizado import autorizar_exclusivos_automaticamente, autorizar_softwares

from tests.fakedb import FakeResult, RecordingDB


def _authorization_responder(existing: dict[int, dict] | None = None):
    existing = existing or {}

    def responder(sql, params):
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT") and "MIN(SWE.EQUIPO_ID)" in sql_upper:
            software_id = params["software_id"]
            return FakeResult(
                rows=[
                    {
                        "id": software_id,
                        "departamento_id": 3,
                        "nombre": f"Software {software_id}",
                        "fabricante": "Fabricante",
                        "version_referencia": "1.0",
                        "equipo_id": 13,
                    }
                ]
            )
        if sql_upper.startswith("SELECT") and "FROM SOFTWARE_AUTORIZADO" in sql_upper:
            row = existing.get(params["software_id"])
            return FakeResult(rows=[row] if row else [])
        if sql_upper.startswith("INSERT") or sql_upper.startswith("UPDATE"):
            return FakeResult(rows=[{"ok": 1}], lastrowid=1)
        return None

    return responder


class TestAutorizarSoftwares:
    def test_lista_vacia_no_ejecuta_nada(self):
        db = RecordingDB()
        assert autorizar_softwares(db, [], "motivo") == 0
        assert db.executed == []

    def test_autoriza_software_como_especifico_de_un_equipo(self):
        db = RecordingDB(responder=_authorization_responder())
        insertados = autorizar_softwares(db, [10, 11], "motivo demo")

        assert insertados == 2
        inserts = [(sql, p) for sql, p in db.executed if sql.strip().upper().startswith("INSERT")]
        assert len(inserts) == 2
        assert all("software_autorizado" in sql.lower() for sql, _ in inserts)
        assert all("equipo_id" in sql.lower() for sql, _ in inserts)
        assert {p["software_id"] for _, p in inserts} == {10, 11}
        assert {p["departamento_id"] for _, p in inserts} == {3}
        assert {p["equipo_id"] for _, p in inserts} == {13}
        assert all(p["motivo"] == "motivo demo" for _, p in inserts)

    def test_autorizacion_ya_activa_no_inserta_duplicado(self):
        db = RecordingDB(responder=_authorization_responder({10: {"id": 99, "activo": True}}))

        assert autorizar_softwares(db, [10], "motivo demo") == 0
        assert not any(sql.strip().upper().startswith("INSERT") for sql in db.executed_sql())
        assert not any(sql.strip().upper().startswith("UPDATE") for sql in db.executed_sql())

    def test_autorizacion_inactiva_se_reactiva(self):
        db = RecordingDB(responder=_authorization_responder({10: {"id": 99, "activo": False}}))

        assert autorizar_softwares(db, [10], "motivo demo") == 1
        updates = [(sql, p) for sql, p in db.executed if sql.strip().upper().startswith("UPDATE")]
        assert len(updates) == 1
        assert updates[0][1]["id"] == 99
        assert updates[0][1]["motivo"] == "motivo demo"
        assert not any(sql.strip().upper().startswith("INSERT") for sql in db.executed_sql())

    def test_varias_selecciones_mezcladas_devuelven_conteo_correcto(self):
        db = RecordingDB(
            responder=_authorization_responder(
                {
                    10: {"id": 90, "activo": True},
                    11: {"id": 91, "activo": False},
                }
            )
        )

        assert autorizar_softwares(db, [10, 11, 12], "motivo demo") == 2
        assert len([sql for sql in db.executed_sql() if sql.strip().upper().startswith("UPDATE")]) == 1
        assert len([sql for sql in db.executed_sql() if sql.strip().upper().startswith("INSERT")]) == 1

    def test_comprueba_la_clave_unica_real_antes_de_insertar(self):
        db = RecordingDB(responder=_authorization_responder({10: {"id": 99, "activo": True}}))

        autorizar_softwares(db, [10], "motivo demo")
        duplicate_checks = [
            sql
            for sql in db.executed_sql()
            if "FROM software_autorizado" in sql and "ORDER BY COALESCE" in sql
        ]
        assert len(duplicate_checks) == 1
        sql = duplicate_checks[0]
        assert "software_id = :software_id" in sql
        assert "departamento_id = :departamento_id" in sql
        assert "equipo_id = :equipo_id" in sql


class TestAutorizarExclusivos:
    def test_software_exclusivo_se_marca_autorizado(self, monkeypatch):
        db = RecordingDB(responder=_authorization_responder())
        monkeypatch.setattr(
            autorizado,
            "detectar_software_exclusivo",
            lambda _db, dept=None: [{"id": 10}, {"id": 11}],
        )
        n = autorizar_exclusivos_automaticamente(db)
        assert n == 2
        inserts = [sql for sql in db.executed_sql() if sql.strip().upper().startswith("INSERT")]
        assert len(inserts) == 2
