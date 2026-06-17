"""
Tests del motor de importación Panda (modules/importacion.py).

`_compute_diff` es la parte pura (sin BD). `aplicar_diff` se prueba con una
conexión falsa que registra el SQL ejecutado para verificar que NO hay borrados
físicos (soft-delete con presente = FALSE).
"""
from modules.importacion import _compute_diff, aplicar_diff
from utils.normalizer import normalize_nombre

from tests.fakedb import FakeResult, RecordingDB


EQUIPO = {"departamento_id": 1, "prefijo_id": "IT"}


def _catalogo(*softwares: dict) -> dict:
    return {normalize_nombre(sw["nombre"]): sw for sw in softwares}


class TestComputeDiff:
    def test_detecta_software_nuevo_en_catalogo(self):
        programas = [{"nombre": "Programa Nuevo", "version": "1.0"}]
        diff = _compute_diff(EQUIPO, catalogo={}, enlaces={}, programas=programas)
        assert len(diff["nuevos"]) == 1
        assert len(diff["nuevos_en_catalogo"]) == 1
        assert diff["nuevos"][0]["departamento_id"] == 1
        assert diff["eliminados"] == []

    def test_software_en_catalogo_pero_no_enlazado_es_nuevo_no_de_catalogo(self):
        catalogo = _catalogo({"id": 7, "nombre": "App Existente"})
        programas = [{"nombre": "App Existente", "version": "1.0"}]
        diff = _compute_diff(EQUIPO, catalogo=catalogo, enlaces={}, programas=programas)
        assert len(diff["nuevos"]) == 1
        assert diff["nuevos"][0]["software_id"] == 7
        assert diff["nuevos_en_catalogo"] == []  # ya existía en el catálogo

    def test_detecta_software_eliminado(self):
        catalogo = _catalogo({"id": 3, "nombre": "App Vieja", "version_referencia": "1.0"})
        enlaces = {3: {"software_id": 3, "version_detectada": "1.0", "nombre": "App Vieja"}}
        # La nueva lista NO incluye "App Vieja" -> debe marcarse como eliminada.
        diff = _compute_diff(EQUIPO, catalogo=catalogo, enlaces=enlaces, programas=[])
        assert len(diff["eliminados"]) == 1
        assert diff["eliminados"][0]["software_id"] == 3

    def test_detecta_cambio_de_version(self):
        catalogo = _catalogo({"id": 3, "nombre": "App", "version_referencia": "1.0"})
        enlaces = {3: {"software_id": 3, "version_detectada": "1.0"}}
        programas = [{"nombre": "App", "version": "2.0"}]
        diff = _compute_diff(EQUIPO, catalogo=catalogo, enlaces=enlaces, programas=programas)
        assert len(diff["cambios_version"]) == 1
        cambio = diff["cambios_version"][0]
        assert cambio["version_anterior"] == "1.0"
        assert cambio["version_nueva"] == "2.0"
        assert diff["actualizados"] == []

    def test_misma_version_es_actualizado_no_cambio(self):
        catalogo = _catalogo({"id": 3, "nombre": "App", "version_referencia": "1.0"})
        enlaces = {3: {"software_id": 3, "version_detectada": "1.0"}}
        programas = [{"nombre": "App", "version": "1.0"}]
        diff = _compute_diff(EQUIPO, catalogo=catalogo, enlaces=enlaces, programas=programas)
        assert len(diff["actualizados"]) == 1
        assert diff["cambios_version"] == []

    def test_nombres_duplicados_en_input_se_procesan_una_vez(self):
        programas = [
            {"nombre": "Dup", "version": "1.0"},
            {"nombre": "DUP", "version": "1.0"},  # mismo nombre_norm
        ]
        diff = _compute_diff(EQUIPO, catalogo={}, enlaces={}, programas=programas)
        assert len(diff["nuevos"]) == 1


class TestAplicarDiffNoBorraHistorico:
    def test_eliminados_usan_soft_delete_no_delete_fisico(self):
        db = RecordingDB(
            responder=lambda sql, params: (
                FakeResult(rows=[{"departamento_id": 1}]) if "FROM equipos" in sql else None
            )
        )
        diff = {
            "nuevos": [],
            "actualizados": [],
            "cambios_version": [],
            "eliminados": [{"software_id": 5}],
        }

        importacion_id = aplicar_diff(equipo_id=1, programas=[], diff=diff, db=db, metodo="paste")

        sql_text = " ".join(db.executed_sql()).upper()
        # NUNCA debe ejecutarse un DELETE: el histórico se preserva.
        assert "DELETE" not in sql_text
        # El software eliminado se marca como no presente (soft-delete).
        assert "SOFTWARE_EQUIPO" in sql_text
        assert "PRESENTE = FALSE" in sql_text
        # Se registra la importación (trazabilidad ENS).
        assert "INSERT INTO IMPORTACIONES" in sql_text
        assert isinstance(importacion_id, int)
