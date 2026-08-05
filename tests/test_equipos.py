import pytest

from modules.equipos import eliminar_equipo_definitivo
from tests.fakedb import FakeResult, RecordingDB


def _equipo_responder(activo: bool):
    def responder(sql: str, params: dict):
        if "FROM equipos e" in sql:
            return FakeResult(
                rows=[
                    {
                        "id": params.get("equipo_id", 1),
                        "departamento_id": 1,
                        "nombre": "Asserta01",
                        "activo": activo,
                        "departamento_nombre": "IT",
                    }
                ]
            )
        if "information_schema.COLUMNS" in sql:
            return FakeResult(scalar=0)
        return None

    return responder


class TestEquipos:
    def test_no_elimina_equipo_activo(self):
        db = RecordingDB(responder=_equipo_responder(activo=True))

        with pytest.raises(ValueError):
            eliminar_equipo_definitivo(db, 1)

        sql = " ".join(db.executed_sql()).lower()
        assert "delete from equipos" not in sql

    def test_elimina_equipo_inactivo_y_relaciones(self):
        db = RecordingDB(responder=_equipo_responder(activo=False))

        eliminar_equipo_definitivo(db, 1)

        sql = " ".join(db.executed_sql()).lower()
        assert "delete from software_instalado" in sql
        assert "delete from software_importaciones" in sql
        assert "delete from equipos" in sql
