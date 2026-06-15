"""Tests de software autorizado (modules/autorizado.py)."""
import modules.autorizado as autorizado
from modules.autorizado import autorizar_exclusivos_automaticamente, autorizar_softwares

from tests.fakedb import FakeResult, RecordingDB


def _insert_responder(sql, params):
    # Hace que cada INSERT cuente como 1 fila insertada (rowcount = 1).
    if sql.strip().upper().startswith("INSERT"):
        return FakeResult(rows=[{"ok": 1}], lastrowid=1)
    return None


class TestAutorizarSoftwares:
    def test_lista_vacia_no_ejecuta_nada(self):
        db = RecordingDB()
        assert autorizar_softwares(db, [], "motivo") == 0
        assert db.executed == []

    def test_autoriza_software_como_especifico_de_un_equipo(self):
        db = RecordingDB(responder=_insert_responder)
        insertados = autorizar_softwares(db, [10, 11], "motivo demo")

        assert insertados == 2
        inserts = [(sql, p) for sql, p in db.executed if sql.strip().upper().startswith("INSERT")]
        assert len(inserts) == 2
        # La autorización queda enlazada a un equipo concreto (MIN(swe.equipo_id)).
        assert all("software_autorizado" in sql.lower() for sql, _ in inserts)
        assert all("equipo_id" in sql.lower() for sql, _ in inserts)
        assert {p["software_id"] for _, p in inserts} == {10, 11}
        assert all(p["motivo"] == "motivo demo" for _, p in inserts)


class TestAutorizarExclusivos:
    def test_software_exclusivo_se_marca_autorizado(self, monkeypatch):
        db = RecordingDB(responder=_insert_responder)
        # Simulamos que la detección encuentra 2 programas exclusivos (1 solo equipo).
        monkeypatch.setattr(
            autorizado,
            "detectar_software_exclusivo",
            lambda _db, dept=None: [{"id": 10}, {"id": 11}],
        )
        n = autorizar_exclusivos_automaticamente(db)
        assert n == 2
        inserts = [sql for sql in db.executed_sql() if sql.strip().upper().startswith("INSERT")]
        assert len(inserts) == 2
