from modules.simple_inventory import confirm_software_import
from tests.fakedb import FakeResult, RecordingDB
from utils.panda_parser import parse_panda_text


PASTE = (
    "App A\n"
    "Vendor\n"
    "01/08/2026\n"
    "1 MB\n"
    "1.0\n"
    "App B\n"
    "Vendor\n"
    "02/08/2026\n"
    "2 MB\n"
    "2.0\n"
)


def _db_with_equipo() -> RecordingDB:
    return RecordingDB(
        responder=lambda sql, params: (
            FakeResult(rows=[{"id": params.get("equipo_id", 1), "departamento_id": 3}])
            if "FROM equipos" in sql and "activo = TRUE" in sql
            else None
        )
    )


class TestSimpleInventory:
    def test_confirmacion_guarda_importacion_y_filas(self):
        parsed = parse_panda_text(PASTE)
        db = _db_with_equipo()

        importacion_id = confirm_software_import(1, "2026-08", parsed.rows, PASTE, db=db)

        sql = " ".join(db.executed_sql()).lower()
        assert importacion_id
        assert "update software_importaciones" in sql
        assert "estado = 'superseded'" in sql
        assert "insert into software_importaciones" in sql
        assert sql.count("insert into software_instalado") == 2
