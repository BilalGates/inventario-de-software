import datetime

from modules.simple_inventory import confirm_software_import, ultima_importacion_equipo
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

    def test_ultima_importacion_devuelve_la_confirmada_mas_reciente(self):
        previa = {
            "id": 7,
            "periodo": "2026-08",
            "fecha_importacion": datetime.datetime(2026, 8, 4, 9, 30),
            "n_programas": 87,
            "equipo_nombre": "PC-01",
            "horas_desde": 30.5,
        }
        db = RecordingDB(responder=lambda sql, params: FakeResult(rows=[previa]))

        result = ultima_importacion_equipo(5, db=db)

        sql = " ".join(db.executed_sql()).lower()
        assert result is not None
        assert result["equipo_nombre"] == "PC-01"
        assert result["horas_desde"] == 30.5
        # Solo cuentan las importaciones vigentes, y la mas reciente primero.
        assert "estado = 'confirmed'" in sql
        assert "order by imp.fecha_importacion desc" in sql

    def test_ultima_importacion_sin_datos_devuelve_none(self):
        db = RecordingDB(responder=lambda sql, params: FakeResult(rows=[]))

        assert ultima_importacion_equipo(5, db=db) is None


class TestExportarExcel:
    EQUIPO = {
        "id": 1,
        "departamento_id": 3,
        "departamento_nombre": "IT",
        "nombre": "PC-01",
        "notas": "Ana",
        "activo": 1,               # MySQL devuelve 0/1, no True/False
        "es_servidor": 0,
        "tipo_dispositivo": "Portatil",
        "marca_modelo": "Dell Latitude",
        "num_serie": "ABC123",
        "mac_address": "00:11:22:33:44:55",
        "sistema_operativo": "Windows 11 Pro",
        "procesador": "Intel i7",
        "ram": "16GB",
        "almacenamiento": "512GB SSD",
        "responsable": "Ana",
        "ubicacion": "Oficina",
        "coste": None,
        "fecha_adquisicion": None,
        "fecha_alta": datetime.date(2026, 5, 27),
        "fecha_baja": None,
        "total_software_activo": 42,
        "ultima_importacion": datetime.datetime(2026, 8, 4, 12, 17),
    }

    def _export(self):
        import io

        from openpyxl import load_workbook

        from modules.simple_inventory import exportar_inventario_excel

        def responder(sql, params):
            if "FROM equipos" in sql:
                return FakeResult(rows=[self.EQUIPO])
            if "FROM departamentos" in sql:
                return FakeResult(rows=[{"id": 3, "nombre": "IT", "codigo": "it"}])
            return FakeResult(rows=[])

        data = exportar_inventario_excel("2026-08", db=RecordingDB(responder=responder))
        return load_workbook(io.BytesIO(data))

    def test_hoja_equipos_incluye_los_datos_de_hardware(self):
        ws = self._export()["Equipos"]
        headers = [c.value for c in ws[1]]
        fila = dict(zip(headers, [c.value for c in ws[2]]))

        # El export antiguo solo traia estas cuatro columnas.
        assert fila["Departamento"] == "IT"
        assert fila["Equipo"] == "PC-01"
        assert fila["Usuario"] == "Ana"
        # Y estas son las que faltaban.
        assert fila["N serie"] == "ABC123"
        assert fila["MAC"] == "00:11:22:33:44:55"
        assert fila["Sistema operativo"] == "Windows 11 Pro"
        assert fila["Procesador"] == "Intel i7"
        assert fila["RAM"] == "16GB"
        assert fila["Almacenamiento"] == "512GB SSD"
        assert fila["Ubicacion"] == "Oficina"
        assert fila["Programas"] == 42

    def test_booleanos_y_fechas_se_formatean(self):
        ws = self._export()["Equipos"]
        headers = [c.value for c in ws[1]]
        fila = dict(zip(headers, [c.value for c in ws[2]]))

        # activo llega como 1 (no True) y debe leerse "Si", no "1".
        assert fila["Activo"] == "Si"
        assert fila["Servidor"] == "No"
        assert fila["Fecha alta"] == "27/05/2026"
        assert fila["Ultima importacion"] == "04/08/2026 12:17"
