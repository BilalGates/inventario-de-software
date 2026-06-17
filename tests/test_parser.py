"""Tests del parser de listados de Panda Adaptive Defense (utils/parser.py)."""
from utils.parser import parse_paste


PASTE_CON_CABECERA = (
    "Nombre\tEditor\tFecha de instalación\tTamaño\tVersión\n"
    "Adobe Acrobat Reader\tAdobe Systems\t18/05/2026\t1,2 GB\t26.001.21563\n"
    "\n"  # línea vacía -> debe ignorarse
    "AnyDesk\tAnyDesk Software GmbH\t10/03/2026\t2 MB\tad 9.0.10\n"
)


class TestParsePaste:
    def test_ignora_cabecera(self):
        programas = parse_paste(PASTE_CON_CABECERA)
        nombres = [p["nombre"] for p in programas]
        assert "Nombre" not in nombres
        assert nombres == ["Adobe Acrobat Reader", "AnyDesk"]

    def test_ignora_filas_vacias(self):
        programas = parse_paste(PASTE_CON_CABECERA)
        assert len(programas) == 2

    def test_version_se_preserva_como_texto(self):
        programas = parse_paste(PASTE_CON_CABECERA)
        versiones = {p["nombre"]: p["version"] for p in programas}
        assert versiones["Adobe Acrobat Reader"] == "26.001.21563"
        assert versiones["AnyDesk"] == "ad 9.0.10"
        assert all(isinstance(p["version"], str) for p in programas)

    def test_sin_cabecera(self):
        texto = "7-Zip\tIgor Pavlov\t12/02/2026\t5 MB\t23.01\n"
        programas = parse_paste(texto)
        assert len(programas) == 1
        assert programas[0]["nombre"] == "7-Zip"
        assert programas[0]["version"] == "23.01"

    def test_tamano_guion_se_convierte_en_none(self):
        texto = "Anaconda3\tAnaconda, Inc.\t30/01/2025\t-\t2022.05\n"
        programas = parse_paste(texto)
        assert programas[0]["tamano"] is None
        assert programas[0]["version"] == "2022.05"

    def test_no_rompe_con_columnas_de_mas(self):
        # Una fila con columnas inesperadas adicionales no debe romper el parseo.
        texto = "App X\tEditor\t01/01/2026\t10 MB\t1.2.3\tEXTRA\tOTRA\n"
        programas = parse_paste(texto)
        assert len(programas) == 1
        assert programas[0]["nombre"] == "App X"
        assert programas[0]["version"] == "1.2.3"

    def test_no_rompe_con_columnas_de_menos(self):
        # Solo nombre: el resto de campos quedan None, sin excepción.
        texto = "App Solo Nombre\n"
        programas = parse_paste(texto)
        assert len(programas) == 1
        assert programas[0]["nombre"] == "App Solo Nombre"
        assert programas[0]["fabricante"] is None
        assert programas[0]["version"] is None

    def test_fecha_invalida_no_rompe(self):
        texto = "App\tEditor\tfecha-mala\t1 MB\t1.0\n"
        programas = parse_paste(texto)
        assert programas[0]["fecha_instalacion"] is None

    def test_texto_vacio(self):
        assert parse_paste("") == []
        assert parse_paste(None) == []
